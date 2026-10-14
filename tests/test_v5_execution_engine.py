"""Synthetic, offline-only acceptance tests for V5 Execution foundation."""
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from nbot.v5.execution_engine import (
    CONTRACT, FrozenModel, OfflineExecutionEngine, PaperPolicy,
    sign_for_synthetic_test,
)

NOW = 1_800_000_000_000
MODELS = {
    "CHAMPION_PAPER": FrozenModel("champion-1", "a" * 64, "experiment-v5", "contest-a"),
    "CHALLENGER_PAPER": FrozenModel("challenger-1", "b" * 64, "experiment-v5", "contest-a"),
}
KEYS = {
    "CHAMPION_PAPER": b"champion-only-synthetic-test-key-32",
    "CHALLENGER_PAPER": b"challenger-only-synthetic-test-key-32",
}


def request(portfolio="CHAMPION_PAPER", side="LONG", sequence=1, *,
            symbol="BTCUSDT", event="event-0001", now=NOW, **changes):
    m = MODELS[portfolio]
    rec = {
        "contract_version": CONTRACT, "authority": "PAPER_ONLY",
        "experiment_id": m.experiment_id, "contest_id": m.contest_id,
        "model_id": m.model_id, "model_sha": m.model_sha,
        "portfolio_id": portfolio, "event_id": event,
        "as_of_ms": now - 100, "expires_at_ms": now + 1000,
        "symbol": symbol, "side": side, "strategy_tag_ids": ["TREND_CONTINUATION_V1"],
        "btc_regime_version": "btc-context-v1",
        "coin_structure_version": "structure-v1",
        "expected_after_cost_net_r": "0.8", "confidence": "0.90",
        "entry_quote_reference": "synthetic-quote-v1",
        "stop_price": "98" if side != "SHORT" else "102",
        "execution_policy_version": "mock-paper-v1",
        "sequence": sequence, "idempotency_key": f"key-{portfolio}-{event}-{sequence}",
    }
    rec.update(changes)
    return rec


def quote(symbol="BTCUSDT", *, bid="99.99", ask="100.01", now=NOW, **changes):
    q = {
        "source": "SYNTHETIC", "healthy": True, "btc_healthy": True,
        "symbol": symbol, "bid": bid, "ask": ask, "observed_at_ms": now,
        "reference": "synthetic-quote-v1",
    }
    q.update(changes)
    return q


class DualBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "mock-paper.sqlite"
        self.engine = OfflineExecutionEngine(self.db, MODELS, KEYS)

    def tearDown(self):
        self.engine.close_database()
        self.tmp.cleanup()

    def send(self, rec, q=None, now=NOW, signature=None):
        return self.engine.submit(rec, signature or sign_for_synthetic_test(rec, KEYS[rec["portfolio_id"]]),
                                  quote(rec["symbol"], now=now) if q is None else q, now)

    def test_two_books_same_event_same_coin_independent(self):
        champion = self.send(request())
        challenger = self.send(request("CHALLENGER_PAPER"))
        self.assertEqual(champion["status"], "ACCEPTED")
        self.assertEqual(challenger["status"], "ACCEPTED")
        self.assertEqual(len(self.engine.report("CHAMPION_PAPER")["open_positions"]), 1)
        self.assertEqual(len(self.engine.report("CHALLENGER_PAPER")["open_positions"]), 1)
        self.assertEqual(self.engine.integrity(), "ok")

    def test_opposite_directions_and_separate_wallets(self):
        self.send(request())
        self.send(request("CHALLENGER_PAPER", side="SHORT"))
        result = self.engine.settle_synthetic("CHAMPION_PAPER", "BTCUSDT",
                                               quote(bid="90", ask="90.02", now=NOW+60000), NOW+60000)
        self.assertEqual(result["status"], "SETTLED")
        self.assertLess(Decimal(result["net_pnl"]), 0)
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["settled_count"], 1)
        self.assertEqual(self.engine.report("CHALLENGER_PAPER")["settled_count"], 0)
        self.assertEqual(len(self.engine.report("CHALLENGER_PAPER")["open_positions"]), 1)

    def test_idempotency_restart_reuses_decision(self):
        r = request()
        accepted = self.send(r)
        self.engine.close_database()
        self.engine = OfflineExecutionEngine(self.db, MODELS, KEYS)
        again = self.send(r, now=NOW+50)
        self.assertTrue(again["duplicate"])
        self.assertEqual(accepted["decision_id"], again["decision_id"])
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 1)
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["last_sequence"], 1)

    def test_idempotency_key_tampering_does_not_trade(self):
        r = request()
        self.send(r)
        altered = dict(r, stop_price="96")
        self.assertEqual(self.send(altered)["reason"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 1)

    def test_signature_wrong_portfolio_or_unsigned_field(self):
        r = request()
        self.assertEqual(self.send(r, signature="0" * 64)["reason"], "INVALID_SIGNATURE")
        r["authority"] = "LIVE"
        self.assertEqual(self.send(r)["reason"], "CONTRACT_OR_AUTHORITY_INVALID")
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 0)

    def test_stale_or_future_recommendation_refused(self):
        self.assertEqual(self.send(request(as_of_ms=NOW-10000))["reason"],
                         "RECOMMENDATION_EXPIRED_OR_FUTURE")
        self.assertEqual(self.send(request(event="event2", sequence=2,
                                           as_of_ms=NOW+100))["reason"], "RECOMMENDATION_EXPIRED_OR_FUTURE")

    def test_stale_missing_btc_and_crossed_quote_refused(self):
        for q, reason in [
            (quote(observed_at_ms=NOW-3000), "QUOTE_STALE_OR_FUTURE"),
            (quote(btc_healthy=False), "MARKET_DATA_UNVERIFIED"),
            (quote(source="REAL_UNVERIFIED"), "NO_INDEPENDENT_SYNTHETIC_QUOTE"),
            (quote(bid="101", ask="100"), "CROSSED_QUOTE"),
            (quote(observed_at_ms=NOW+1), "QUOTE_STALE_OR_FUTURE"),
        ]:
            with self.subTest(reason=reason):
                sequence = self.engine.report("CHAMPION_PAPER")["last_sequence"] + 1
                self.assertEqual(self.send(request(event=f"quote-case-{sequence}", sequence=sequence),
                                           q=q)["reason"], reason)

    def test_invalid_model_and_stop_geometry_and_cost(self):
        for i, (changes, reason) in enumerate([
            ({"model_sha": "f"*64}, "MODEL_OR_CONTEST_NOT_PINNED"),
            ({"stop_price": "101"}, "INVALID_STOP_GEOMETRY"),
            ({"stop_price": "100.03"}, "INVALID_STOP_GEOMETRY"),
            ({"stop_price": "100.005"}, "COST_TO_R_TOO_HIGH"),
            ({"expected_after_cost_net_r": "-1"}, "INSUFFICIENT_NET_EDGE"),
            ({"confidence": "0.2"}, "INSUFFICIENT_CONFIDENCE"),
        ], start=1):
            with self.subTest(reason=reason):
                self.assertEqual(self.send(request(sequence=i, event=f"risk-case-{i}", **changes))["reason"], reason)

    def test_sequence_and_duplicate_event(self):
        self.assertEqual(self.send(request(sequence=3, event="out-of-order"))["reason"], "REORDERED_SEQUENCE")
        self.assertEqual(self.send(request())["status"], "ACCEPTED")
        self.assertEqual(self.send(request(event="event-0001", sequence=2,
                                            idempotency_key="different-key-999"))["reason"], "DUPLICATE_EVENT")
        self.assertEqual(self.send(request(event="event-0002", sequence=2))["reason"], "DUPLICATE_OPEN_SYMBOL")

    def test_abstain_has_no_fill_and_consumes_sequence(self):
        self.assertEqual(self.send(request(side="ABSTAIN"))["status"], "ABSTAINED")
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["last_sequence"], 1)
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 0)

    def test_book_kill_does_not_stop_other_book(self):
        self.engine.kill_book("CHAMPION_PAPER")
        self.assertEqual(self.send(request())["reason"], "BOOK_KILLED")
        self.assertEqual(self.send(request("CHALLENGER_PAPER"))["status"], "ACCEPTED")
        self.engine.close_database()
        self.engine = OfflineExecutionEngine(self.db, MODELS, KEYS)
        self.assertTrue(self.engine.report("CHAMPION_PAPER")["killed"])

    def test_frozen_model_cannot_change_on_restart(self):
        self.engine.close_database()
        models = dict(MODELS)
        models["CHAMPION_PAPER"] = FrozenModel("swapped", "c"*64, "experiment-v5", "contest-a")
        with self.assertRaisesRegex(ValueError, "FROZEN_MODEL_MISMATCH"):
            altered = OfflineExecutionEngine(self.db, models, KEYS)
            altered.close_database()
        self.engine = OfflineExecutionEngine(self.db, MODELS, KEYS)

    def test_durable_fee_funding_accounting_and_restart(self):
        self.assertEqual(self.send(request())["status"], "ACCEPTED")
        opened = self.engine.report("CHAMPION_PAPER")
        self.assertLess(Decimal(opened["wallet"]), Decimal("10000"))
        result = self.engine.settle_synthetic("CHAMPION_PAPER", "BTCUSDT",
                                               quote(bid="103", ask="103.02", now=NOW+28800000),
                                               NOW+28800000)
        self.assertEqual(result["status"], "SETTLED")
        self.assertGreater(Decimal(result["funding"]), 0)
        self.assertLess(abs(Decimal(result["wallet"]) -
                            (Decimal("10000")+Decimal(result["net_pnl"]))), Decimal("1e-20"))
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["settled_count"], 1)
        self.engine.close_database()
        self.engine = OfflineExecutionEngine(self.db, MODELS, KEYS)
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["wallet"], result["wallet"])

    def test_unverifiable_exit_cannot_manufacture_settlement(self):
        self.send(request())
        self.assertEqual(self.engine.settle_synthetic("CHAMPION_PAPER", "BTCUSDT",
                          quote(btc_healthy=False, now=NOW+60000), NOW+60000)["reason"], "MARKET_DATA_UNVERIFIED")
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["settled_count"], 0)

    def test_immutable_decision_and_ledger_rows(self):
        self.send(request())
        with self.assertRaises(sqlite3.DatabaseError):
            self.engine.db.execute("DELETE FROM decisions")
        with self.assertRaises(sqlite3.DatabaseError):
            self.engine.db.execute("UPDATE ledger SET delta='1000'")
        self.assertEqual(self.engine.integrity(), "ok")

    def test_quote_reference_must_be_same_frozen_source(self):
        self.assertEqual(self.send(request(), q=quote(reference="wrong-event"))["reason"],
                         "QUOTE_REFERENCE_MISMATCH")

    def test_policy_swap_rejected_across_restart(self):
        self.engine.close_database()
        with self.assertRaisesRegex(ValueError, "FROZEN_MODEL_MISMATCH"):
            changed = OfflineExecutionEngine(self.db, MODELS, KEYS,
                                             PaperPolicy(taker_fee_rate=Decimal("0.001")))
            changed.close_database()
        self.engine = OfflineExecutionEngine(self.db, MODELS, KEYS)

    def test_legacy_path_forbidden(self):
        with self.assertRaisesRegex(ValueError, "LEGACY_DIRECTORY_FORBIDDEN"):
            OfflineExecutionEngine("/home/ubuntu/Nbot/legacy.sqlite", MODELS, KEYS)

    def test_drawdown_switch_blocks_new_entries_but_not_settlement(self):
        self.send(request())
        self.engine.settle_synthetic("CHAMPION_PAPER", "BTCUSDT",
                                      quote(bid="1", ask="1.02", now=NOW+60000), NOW+60000)
        self.assertTrue(self.engine.report("CHAMPION_PAPER")["killed"])
        self.assertEqual(self.send(request(sequence=2, event="after-drawdown",
                                            symbol="ETHUSDT"),
                                   q=quote("ETHUSDT"))["reason"], "BOOK_KILLED")

    def test_shared_event_snapshot_cannot_change_for_challenger(self):
        self.assertEqual(self.send(request())["status"], "ACCEPTED")
        r = request("CHALLENGER_PAPER")
        self.assertEqual(self.send(r, q=quote(bid="99.50", ask="99.52"))["reason"],
                         "SHARED_MARKET_SNAPSHOT_MISMATCH")
        self.assertEqual(self.engine.report("CHALLENGER_PAPER")["open_positions"], [])

    def test_transaction_rollback_on_simulated_fill_storage_failure(self):
        self.engine.db.execute("""CREATE TRIGGER fail_test_fill BEFORE INSERT ON fills
                                   BEGIN SELECT RAISE(ABORT,'synthetic fault'); END;""")
        with self.assertRaises(sqlite3.DatabaseError):
            self.send(request())
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["wallet"], "10000")
        self.engine.db.execute("DROP TRIGGER fail_test_fill")
        self.assertEqual(self.send(request())["status"], "ACCEPTED")

    def test_authenticated_message_size_is_bounded(self):
        rec = request(strategy_tag_ids=["A"*1000]*20)
        self.assertEqual(self.send(rec)["reason"], "MESSAGE_SIZE_LIMIT")
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)

    def test_unknown_fields_not_execution_authority(self):
        self.assertEqual(self.send(request(real_order=True))["reason"], "CONTRACT_OR_AUTHORITY_INVALID")


if __name__ == "__main__":
    unittest.main()
