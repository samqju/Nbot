"""E2/E3 deliberately synthetic replay tests; import E1 fixture helpers."""
import hashlib
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from test_v5_execution_engine import NOW, MODELS, KEYS, quote, request
from nbot.v5.execution_engine import OfflineExecutionEngine, sign_for_synthetic_test
from nbot.v5.execution_replay import ReplayRules, ReplayRefused, SyntheticReplay

RECEIPT_KEY = b"offline-receipts-fixture-only-not-prod"
RULES = ReplayRules(NOW-1000, NOW+3*24*60*60*1000)


def frame(i=1, now=NOW, symbol="BTCUSDT", event=None, **qchanges):
    event = event or f"event-{i:04d}"
    return {"frame_id": f"frame-{i:08d}", "event_id": event, "at_ms": now,
            "quote": quote(symbol, now=now, **qchanges)}


def proposal(portfolio="CHAMPION_PAPER", seq=1, i=1, now=NOW,
             symbol="BTCUSDT", side="LONG", **updates):
    r = request(portfolio, side=side, sequence=seq, symbol=symbol,
                event=f"event-{i:04d}", now=now, **updates)
    return {"payload": r, "signature": sign_for_synthetic_test(r, KEYS[portfolio])}


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name)/"offline-replay.sqlite"
        self.eng = OfflineExecutionEngine(self.db_path, MODELS, KEYS)
        self.replay = SyntheticReplay(self.eng, RULES, RECEIPT_KEY)

    def tearDown(self):
        self.eng.close_database()
        self.tmp.cleanup()

    def test_dual_book_both_trade_at_identical_tick(self):
        result = self.replay.advance(frame(), [proposal(),
                          proposal("CHALLENGER_PAPER")])
        self.assertTrue(self.replay.verify_receipt(result))
        self.assertEqual(result["receipt"]["source"], "SYNTHETIC")
        self.assertEqual(result["receipt"]["decisions"]["CHAMPION_PAPER"]["status"], "ACCEPTED")
        self.assertEqual(result["receipt"]["decisions"]["CHALLENGER_PAPER"]["status"], "ACCEPTED")
        self.assertEqual(self.eng.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 2)

    def test_replay_identical_event_no_double_fill_even_after_restart(self):
        f, p = frame(), [proposal()]
        a = self.replay.advance(f, p)
        self.eng.close_database()
        self.eng = OfflineExecutionEngine(self.db_path, MODELS, KEYS)
        self.replay = SyntheticReplay(self.eng, RULES, RECEIPT_KEY)
        b = self.replay.advance(f, p)
        self.assertTrue(b["duplicate"])
        self.assertEqual(a["receipt"], b["receipt"])
        self.assertTrue(self.replay.verify_receipt(b))
        self.assertEqual(self.eng.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 1)

    def test_replay_conflict_with_same_frame_id_rejected(self):
        self.replay.advance(frame(), [])
        with self.assertRaisesRegex(ReplayRefused, "FRAME_REPLAY_CONFLICT"):
            self.replay.advance(frame(bid="99.5"), [])
        self.assertEqual(self.eng.db.execute("SELECT COUNT(*) FROM replay_frames").fetchone()[0], 1)

    def test_wrong_receipt_signature_refused(self):
        a = self.replay.advance(frame(), [])
        self.assertTrue(self.replay.verify_receipt(a))
        forged = dict(a, signature="0"*64)
        self.assertFalse(self.replay.verify_receipt(forged))
        altered = dict(a, receipt=dict(a["receipt"], source="LIVE"))
        self.assertFalse(self.replay.verify_receipt(altered))

    def test_fail_closed_on_stale_synthetic_feed(self):
        bad = frame(observed_at_ms=NOW-10000)
        with self.assertRaisesRegex(ReplayRefused, "QUOTE_STALE_OR_FUTURE"):
            self.replay.advance(bad, [proposal()])
        self.assertEqual(self.eng.db.execute("SELECT COUNT(*) FROM replay_frames").fetchone()[0], 0)
        self.assertEqual(self.eng.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)

    def test_bad_btc_feed_does_not_settle_or_enter(self):
        self.replay.advance(frame(), [proposal()])
        bad = frame(2, NOW+1000, bid="80", ask="80.1", btc_healthy=False)
        with self.assertRaisesRegex(ReplayRefused, "MARKET_DATA_UNVERIFIED"):
            self.replay.advance(bad, [])
        self.assertEqual(self.eng.report("CHAMPION_PAPER")["settled_count"], 0)
        self.assertEqual(len(self.eng.report("CHAMPION_PAPER")["open_positions"]), 1)

    def test_stop_gap_uses_adverse_quote_not_optimistic_stop(self):
        self.replay.advance(frame(), [proposal()])
        f = frame(2, NOW+1000, bid="88", ask="88.2")
        result = self.replay.advance(f, [])
        closed = result["receipt"]["closed"]["CHAMPION_PAPER"]
        self.assertEqual(closed["trigger"], "STOP")
        self.assertLess(Decimal(closed["result"]["net_pnl"]), 0)
        self.assertEqual(self.eng.report("CHAMPION_PAPER")["settled_count"], 1)
        fill = self.eng.db.execute("SELECT price FROM fills ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertLess(Decimal(fill), Decimal("88"))

    def test_short_stop_uses_adverse_ask(self):
        self.replay.advance(frame(), [proposal(side="SHORT")])
        result = self.replay.advance(frame(2, NOW+1000, bid="110", ask="110.1"), [])
        self.assertEqual(result["receipt"]["closed"]["CHAMPION_PAPER"]["trigger"], "STOP")

    def test_time_exit_on_max_hold_but_not_before(self):
        self.replay.advance(frame(), [proposal()])
        t = NOW+RULES.max_holding_ms
        result = self.replay.advance(frame(2, t), [])
        self.assertEqual(result["receipt"]["closed"]["CHAMPION_PAPER"]["trigger"], "MAX_HOLD")
        self.assertGreater(Decimal(result["receipt"]["closed"]["CHAMPION_PAPER"]["result"]["funding"]), 0)

    def test_exit_is_not_fabricated_if_no_qualified_future_quote(self):
        self.replay.advance(frame(), [proposal()])
        result = self.replay.common_window_report(NOW)
        self.assertEqual(result["status"], "HOLD_REVIEW_REQUIRED")
        self.assertIn("UNDER_100_SETTLED_PER_MODEL", result["reasons"])
        self.assertEqual(self.eng.report("CHAMPION_PAPER")["settled_count"], 0)

    def test_nonchronological_market_time_does_not_mutate(self):
        self.replay.advance(frame(), [])
        with self.assertRaisesRegex(ReplayRefused, "NONCHRONOLOGICAL_MARKET_FRAME"):
            self.replay.advance(frame(2, NOW-100), [])
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM replay_frames").fetchone()[0], 1)

    def test_wrong_event_and_double_book_packet_rejected(self):
        with self.assertRaisesRegex(ReplayRefused, "PROPOSAL_EVENT_MISMATCH"):
            self.replay.advance(frame(2), [proposal()])
        with self.assertRaisesRegex(ReplayRefused, "DUPLICATE_OR_UNKNOWN_BOOK"):
            self.replay.advance(frame(), [proposal(), proposal()])
        self.assertEqual(self.eng.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)

    def test_atomic_fault_rollback_then_exact_retry(self):
        self.eng.db.execute("""CREATE TRIGGER synthetic_crash BEFORE INSERT ON replay_frames
                              BEGIN SELECT RAISE(ABORT,'simulated crash'); END;""")
        with self.assertRaises(sqlite3.DatabaseError):
            self.replay.advance(frame(), [proposal()])
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM orders").fetchone()[0], 0)
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM decisions").fetchone()[0], 0)
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM replay_marks").fetchone()[0], 0)
        self.eng.db.execute("DROP TRIGGER synthetic_crash")
        self.assertEqual(self.replay.advance(frame(), [proposal()])["receipt"]["decisions"]["CHAMPION_PAPER"]["status"], "ACCEPTED")

    def test_frozen_contest_window_and_receipt_key_after_restart(self):
        self.eng.close_database()
        self.eng = OfflineExecutionEngine(self.db_path, MODELS, KEYS)
        with self.assertRaisesRegex(ValueError, "FROZEN_REPLAY_RULES"):
            SyntheticReplay(self.eng, ReplayRules(NOW-1000, NOW+3*24*60*60*1000, max_holding_ms=1234), RECEIPT_KEY)
        with self.assertRaisesRegex(ValueError, "FROZEN_REPLAY_RULES"):
            SyntheticReplay(self.eng, RULES, b"wrong-receipt-synthetic-key-12345")
        self.replay = SyntheticReplay(self.eng, RULES, RECEIPT_KEY)

    def test_mark_to_market_paper_only_and_fee_conservative(self):
        a = self.replay.advance(frame(), [proposal()])
        mark = a["receipt"]["marks"]["CHAMPION_PAPER"]
        self.assertEqual(mark["reason"], "QUALIFIED_SYNTHETIC_MARK")
        self.assertLess(Decimal(mark["equity"]), Decimal("10000"))
        self.assertEqual(a["receipt"]["marks"]["CHALLENGER_PAPER"]["equity"], "10000")

    def test_stale_symbol_mark_explicitly_unverifiable(self):
        self.replay.advance(frame(), [proposal()])
        a = self.replay.advance(frame(2, NOW+5000, symbol="ETHUSDT"), [])
        self.assertIsNone(a["receipt"]["marks"]["CHAMPION_PAPER"]["equity"])
        self.assertEqual(a["receipt"]["marks"]["CHAMPION_PAPER"]["reason"], "HOLD_MISSING_FRESH_MARK")

    def test_common_window_uses_identical_end_and_never_promotes(self):
        self.replay.advance(frame(), [proposal(), proposal("CHALLENGER_PAPER")])
        a = self.replay.advance(frame(2, NOW+1000, bid="101", ask="101.02"), [])
        c = self.replay.common_window_report(NOW+1000)
        self.assertEqual(c["common_endpoint_ms"], NOW+1000)
        self.assertEqual(c["status"], "HOLD_REVIEW_REQUIRED")
        self.assertEqual(c["paper_promotion_authority"], "NONE")
        self.assertEqual(c["real_order_authority"], "NONE")
        self.assertIn("INDEPENDENT_REGIME_AND_UNCERTAINTY_UNVERIFIED", c["reasons"])
        self.assertEqual(c["portfolios"]["CHAMPION_PAPER"]["equity"],
                         a["receipt"]["marks"]["CHAMPION_PAPER"]["equity"])

    def test_future_tick_rejected(self):
        with self.assertRaisesRegex(ReplayRefused, "FRAME_ID_OR_CLOCK_INVALID"):
            self.replay.advance(frame(now=RULES.contest_end_ms+1), [])
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM replay_frames").fetchone()[0], 0)

    def test_maximum_market_count(self):
        for i in range(64):
            sym = f"ASSET{i:03d}USDT"
            self.replay.advance(frame(i+1, NOW, symbol=sym), [])
        with self.assertRaisesRegex(ReplayRefused, "MAX_MARKETS_LIMIT"):
            self.replay.advance(frame(65, NOW, symbol="EXTRAUSDT"), [])
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM replay_frames").fetchone()[0], 64)

    def test_signed_wrong_authority_is_veto_not_live(self):
        r = proposal()
        r["payload"]["authority"] = "LIVE"
        r["signature"] = sign_for_synthetic_test(r["payload"], KEYS["CHAMPION_PAPER"])
        result = self.replay.advance(frame(), [r])
        self.assertEqual(result["receipt"]["decisions"]["CHAMPION_PAPER"]["reason"],
                         "CONTRACT_OR_AUTHORITY_INVALID")
        self.assertEqual(self.eng.db.execute("SELECT count(*) FROM fills").fetchone()[0], 0)

if __name__ == "__main__":
    unittest.main()
