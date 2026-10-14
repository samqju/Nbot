"""E3 read-only contest audit tests; synthetic observations only."""
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests.test_v5_execution_engine import NOW, MODELS, KEYS, quote, request
from tests.test_v5_execution_replay import frame, proposal, RECEIPT_KEY, RULES
from nbot.v5.execution_engine import OfflineExecutionEngine, sign_for_synthetic_test
from nbot.v5.execution_replay import SyntheticReplay
from nbot.v5.contest_audit import audit_synthetic_contest


class E3ContestAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = OfflineExecutionEngine(Path(self.tmp.name)/"offline.sqlite", MODELS, KEYS)
        self.replay = SyntheticReplay(self.engine, RULES, RECEIPT_KEY)

    def tearDown(self):
        self.engine.close_database()
        self.tmp.cleanup()

    def test_absent_shared_events_holds(self):
        report = audit_synthetic_contest(self.replay, NOW)
        self.assertEqual(report["status"], "HOLD_NO_SHARED_EVENTS")
        self.assertEqual(report["promotion_recommendation"], "NONE")

    def test_no_trade_is_explicit_zero_percent_reference(self):
        self.replay.advance(frame(), [])
        r = audit_synthetic_contest(self.replay, NOW)
        self.assertEqual(r["no_trade_baseline_return"], "0")
        self.assertEqual(r["same_initial_equity_per_book"], "10000")
        for book in MODELS:
            self.assertEqual(Decimal(r["books"][book]["equity_return_on_same_initial_capital"]), 0)
            self.assertEqual(r["books"][book]["decisions"]["not_emitted"], 1)
            self.assertEqual(r["books"][book]["settled_count"], 0)
        self.assertEqual(r["promotion_recommendation"], "NONE")

    def test_same_utc_window_normalizes_both_paper_wallets(self):
        self.replay.advance(frame(), [proposal(), proposal("CHALLENGER_PAPER",side="SHORT")])
        self.replay.advance(frame(2, NOW+1000, bid="101", ask="101.02"), [])
        r = audit_synthetic_contest(self.replay, NOW+1000)
        self.assertEqual(r["actual_first_observation_ms"], NOW)
        self.assertEqual(r["common_endpoint_ms"], NOW+1000)
        self.assertEqual(r["common_event_count"], 2)
        self.assertEqual(r["books"]["CHAMPION_PAPER"]["decisions"]["accepted"], 1)
        self.assertEqual(r["books"]["CHALLENGER_PAPER"]["decisions"]["accepted"], 1)
        self.assertIsNotNone(r["challenger_minus_champion_equity_return"])
        self.assertEqual(r["independent_event_blocked_uncertainty"], "NOT_AVAILABLE")
        self.assertEqual(r["paper_promotion_authority"], "NONE")

    def test_missing_price_mark_blocks_complete_drawdown_claim(self):
        self.replay.advance(frame(), [proposal()])
        self.replay.advance(frame(2, NOW+5000, symbol="ETHUSDT"), [])
        r = audit_synthetic_contest(self.replay, NOW+5000)
        self.assertIn("UNVERIFIABLE_EQUITY_PATH", r["hold_reasons"])
        self.assertIsNone(r["books"]["CHAMPION_PAPER"]["max_observed_sampled_equity_drawdown_fraction"])
        self.assertIsNone(r["books"]["CHAMPION_PAPER"]["equity_return_on_same_initial_capital"])

    def test_both_losing_to_no_trade_is_reported_not_promoted(self):
        self.replay.advance(frame(), [proposal(), proposal("CHALLENGER_PAPER")])
        self.replay.advance(frame(2, NOW+1000, bid="85", ask="85.01"), [])
        r = audit_synthetic_contest(self.replay, NOW+1000)
        self.assertIn("BOTH_UNDER_ZERO_RETURN_NO_TRADE_BENCHMARK", r["hold_reasons"])
        for book in MODELS:
            self.assertLess(Decimal(r["books"][book]["realized_return_on_same_initial_capital"]), 0)
        self.assertEqual(r["promotion_recommendation"], "NONE")

    def test_direct_unlinked_decisions_are_audit_holds(self):
        self.replay.advance(frame(), [])
        rec = request()
        direct = self.engine.submit(rec, sign_for_synthetic_test(rec, KEYS["CHAMPION_PAPER"]),
                                    quote(), NOW)
        self.assertEqual(direct["status"], "ACCEPTED")
        r = audit_synthetic_contest(self.replay, NOW)
        self.assertIn("UNLINKED_DIRECT_ENGINE_DECISIONS", r["hold_reasons"])
        self.assertEqual(r["books"]["CHAMPION_PAPER"]["unlinked_decision_count"], 1)

    def test_cutoff_does_not_see_later_outcome(self):
        self.replay.advance(frame(), [proposal()])
        old = audit_synthetic_contest(self.replay, NOW)
        self.replay.advance(frame(2, NOW+1000, bid="88", ask="88.02"), [])
        historical = audit_synthetic_contest(self.replay, NOW)
        self.assertEqual(historical["books"]["CHAMPION_PAPER"]["settled_count"], 0)
        self.assertEqual(historical["books"]["CHAMPION_PAPER"]["realized_wallet"],
                         old["books"]["CHAMPION_PAPER"]["realized_wallet"])
        self.assertEqual(historical["books"]["CHAMPION_PAPER"]["common_endpoint_equity"],
                         old["books"]["CHAMPION_PAPER"]["common_endpoint_equity"])

    def test_100_trade_gate_and_market_diversity_cannot_automatically_promote(self):
        self.replay.advance(frame(), [])
        r = audit_synthetic_contest(self.replay, NOW)
        self.assertIn("MODEL_PROMOTION_NOT_AUTHORIZED", r["hold_reasons"])
        self.assertIn("INDEPENDENT_REGIME_AND_UNCERTAINTY_UNVERIFIED", r["hold_reasons"])
        self.assertFalse(r["may_train_on_contest_period"])
        self.assertEqual(r["live_order_authority"], "NONE")

    def test_direct_settlement_bypassing_replay_causes_hold(self):
        self.replay.advance(frame(), [proposal()])
        direct = self.engine.settle_synthetic("CHAMPION_PAPER", "BTCUSDT",
                                              quote(now=NOW+500, bid="88", ask="88.02"), NOW+500)
        self.assertEqual(direct["status"], "SETTLED")
        self.replay.advance(frame(2, NOW+1000), [])
        r = audit_synthetic_contest(self.replay, NOW+1000)
        self.assertIn("UNLINKED_SYNTHETIC_SETTLEMENT", r["hold_reasons"])
        self.assertEqual(r["books"]["CHAMPION_PAPER"]["unlinked_settlement_count"], 1)

    def test_signing_identity_is_frozen_on_restart(self):
        path = self.engine.db.execute("PRAGMA database_list").fetchone()[2]
        self.engine.close_database()
        keys = dict(KEYS)
        keys["CHAMPION_PAPER"] = b"changed-only-synthetic-fixture-key"
        with self.assertRaisesRegex(ValueError, "FROZEN_MODEL_MISMATCH"):
            OfflineExecutionEngine(path, MODELS, keys)
        self.engine = OfflineExecutionEngine(path, MODELS, KEYS)
        self.replay = SyntheticReplay(self.engine, RULES, RECEIPT_KEY)

    def test_audit_is_read_only(self):
        self.replay.advance(frame(), [])
        before = self.engine.db.total_changes
        audit_synthetic_contest(self.replay, NOW)
        self.assertEqual(before, self.engine.db.total_changes)


if __name__ == "__main__":
    unittest.main()
