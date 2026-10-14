"""E4 bounded, synthetic-only 100-trade checkpoint/recovery acceptance.

A successful mock count demonstrates accounting/replay consistency, NOT a
valid Champion, predictive edge, or model promotion permission.
"""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from test_v5_execution_engine import NOW, MODELS, KEYS
from test_v5_execution_replay import frame, proposal, RECEIPT_KEY
from nbot.v5.execution_engine import OfflineExecutionEngine, PaperPolicy
from nbot.v5.execution_replay import ReplayRules, SyntheticReplay
from nbot.v5.contest_audit import audit_synthetic_contest


class E4BoundedMockContestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpath = Path(self.tmp.name) / "synthetic-contest.sqlite"
        self.policy = PaperPolicy(max_gross_notional_multiple=Decimal("0.1"),
                                  max_risk_per_trade=Decimal("0.001"),
                                  max_total_open_risk=Decimal("0.002"),
                                  max_realized_drawdown=Decimal("0.8"))
        self.rules = ReplayRules(NOW-1000, NOW+86400000, max_holding_ms=2000,
                                 min_settled_per_model=100,
                                 min_shared_frames=200,
                                 min_shared_duration_ms=60000)
        self.engine = OfflineExecutionEngine(self.dbpath, MODELS, KEYS, self.policy)
        self.replay = SyntheticReplay(self.engine, self.rules, RECEIPT_KEY)

    def tearDown(self):
        self.engine.close_database()
        self.tmp.cleanup()

    def test_100_each_same_forward_period_restart_midway_remains_hold(self):
        checkpoint = None
        last_now = NOW
        for i in range(100):
            event_number = i*2 + 1
            open_at = NOW + i*3000
            p = [proposal("CHAMPION_PAPER", seq=i+1, i=event_number, now=open_at),
                 proposal("CHALLENGER_PAPER", seq=i+1, i=event_number, now=open_at)]
            a = self.replay.advance(frame(event_number, open_at), p)
            self.assertEqual(a["receipt"]["decisions"]["CHAMPION_PAPER"]["status"], "ACCEPTED")
            self.assertEqual(a["receipt"]["decisions"]["CHALLENGER_PAPER"]["status"], "ACCEPTED")
            last_now = open_at+2000
            result = self.replay.advance(frame(event_number+1, last_now), [])
            self.assertEqual(set(result["receipt"]["closed"]), set(MODELS))
            if i == 49:
                checkpoint = self.replay.common_window_report(last_now)
                self.assertIn("UNDER_100_SETTLED_PER_MODEL", checkpoint["reasons"])
                self.engine.close_database()
                self.engine = OfflineExecutionEngine(self.dbpath, MODELS, KEYS, self.policy)
                self.replay = SyntheticReplay(self.engine, self.rules, RECEIPT_KEY)
        shared = self.replay.common_window_report(last_now)
        self.assertEqual(shared["shared_frames"], 200)
        self.assertNotIn("UNDER_100_SETTLED_PER_MODEL", shared["reasons"])
        self.assertNotIn("SHARED_WINDOW_INSUFFICIENT", shared["reasons"])
        self.assertIn("MODEL_PROMOTION_NOT_AUTHORIZED", shared["reasons"])
        self.assertIn("INDEPENDENT_REGIME_AND_UNCERTAINTY_UNVERIFIED", shared["reasons"])
        self.assertEqual(shared["status"], "HOLD_REVIEW_REQUIRED")
        for book in MODELS:
            self.assertEqual(shared["portfolios"][book]["settled_count"], 100)
            self.assertEqual(len(self.engine.report(book)["open_positions"]), 0)
            self.assertFalse(self.engine.report(book)["killed"])
        report = audit_synthetic_contest(self.replay, last_now)
        self.assertEqual(report["promotion_recommendation"], "NONE")
        self.assertEqual(report["no_trade_baseline_return"], "0")
        self.assertFalse(report["may_train_on_contest_period"])
        self.assertEqual(report["common_endpoint_ms"], last_now)
        self.assertEqual(report["books"]["CHAMPION_PAPER"]["decisions"]["accepted"], 100)
        self.assertEqual(report["books"]["CHALLENGER_PAPER"]["decisions"]["accepted"], 100)
        self.assertEqual(report["books"]["CHAMPION_PAPER"]["unlinked_settlement_count"], 0)
        self.assertEqual(report["books"]["CHALLENGER_PAPER"]["unlinked_settlement_count"], 0)
        self.assertEqual(self.engine.integrity(), "ok")

    def test_up_to_50_quote_universe_is_bounded_without_auto_trading(self):
        for n in range(50):
            symbol = f"SYM{n:03d}USDT"
            self.replay.advance(frame(n+1, NOW+n, symbol=symbol), [])
        self.assertEqual(self.engine.db.execute(
            "SELECT count(*) FROM replay_quote_latest").fetchone()[0], 50)
        self.assertEqual(self.engine.db.execute(
            "SELECT count(*) FROM orders").fetchone()[0], 0)
        self.assertEqual(self.engine.db.execute(
            "SELECT count(*) FROM fills").fetchone()[0], 0)
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["wallet"], "10000")
        self.assertEqual(self.engine.report("CHALLENGER_PAPER")["wallet"], "10000")

if __name__ == "__main__":
    unittest.main()
