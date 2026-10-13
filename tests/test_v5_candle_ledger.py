"""V5 durable candle ledger: crash/restart, gaps, provenance and no-trade gates.

Every test uses disposable local SQLite files. No Binance network, credentials,
old V4 ledger, systemd, champion/challenger or real/paper orders.
"""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nbot.v5.candle_ledger import CandleEvidenceLedger, EvidenceHold
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.ws_contract import decode_frame
from tests.test_v5_public_market import klines

EVENT = INTERVAL_MS * 1_000_000
RECEIVED = EVENT + INTERVAL_MS + 2_000
SYMBOL = "BTCUSDT"


def verified_final(open_ms=EVENT + INTERVAL_MS, *, close="100"):
    event_at = open_ms + INTERVAL_MS + 10
    recv = event_at + 1000
    msg = json.dumps({
        "stream": "btcusdt@kline_5m",
        "data": {
            "e": "kline", "E": event_at, "s": SYMBOL,
            "k": {"t": open_ms, "T": open_ms + INTERVAL_MS - 1,
                  "s": SYMBOL, "i": "5m", "x": True,
                  "o": "100", "h": "101", "l": "99",
                  "c": close, "v": "10"}
        },
    })
    return decode_frame("market", msg, received_ms=recv,
                        subscribed_symbols=(SYMBOL,))


class CandleLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "new_v5_candles.db"

    def ledger(self):
        return CandleEvidenceLedger(self.path)

    def boot(self, db):
        return db.bootstrap_rest(
            SYMBOL, klines(), event_open_ms=EVENT, observed_ms=RECEIVED
        )

    def test_bootstrap_96_bars_and_restart_integrity(self):
        with self.ledger() as db:
            self.assertEqual(self.boot(db), 96)
            report = db.inspect(SYMBOL)
            self.assertEqual(report["closed_bar_count"], 96)
            self.assertEqual(report["last_event_open_ms"], EVENT)
            self.assertTrue(report["candle_contiguous"])
            self.assertFalse(report["research_ready"])
            self.assertEqual(report["training_labels_matured"], 0)
        with self.ledger() as db:
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)
            self.assertEqual(self.boot(db), 0)
            with self.assertRaisesRegex(EvidenceHold, "ALREADY_BOOTSTRAPPED"):
                db.bootstrap_rest(SYMBOL, klines(EVENT + INTERVAL_MS),
                                  event_open_ms=EVENT + INTERVAL_MS,
                                  observed_ms=EVENT + 2 * INTERVAL_MS + 1000)

    def test_parsed_genuine_wss_final_is_idempotently_appended(self):
        with self.ledger() as db:
            self.boot(db)
            wss = verified_final()
            self.assertEqual(db.append_wss_final(wss), "APPENDED_WSS_FINAL")
            self.assertEqual(db.append_wss_final(wss), "UNCHANGED_REPLAY")
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 97)
        with self.ledger() as db:
            self.assertEqual(db.inspect(SYMBOL)["last_event_open_ms"],
                             EVENT + INTERVAL_MS)
            self.assertEqual(
                db.append_wss_final(verified_final(EVENT + 2 * INTERVAL_MS)),
                "APPENDED_WSS_FINAL",
            )
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 98)

    def test_unclosed_or_unauthorized_wss_never_appends(self):
        with self.ledger() as db:
            self.boot(db)
            bad = dict(verified_final())
            for patchdata in (
                {"closed": False},
                {"route": "public"},
                {"order_authority": "LIVE"},
                {"kind": "aggTrade"},
                {"received_ms": EVENT},
            ):
                with self.subTest(data=patchdata), self.assertRaises(EvidenceHold):
                    db.append_wss_final({**bad, **patchdata})
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)

    def test_wss_pre_bootstrap_holds_and_initial_rest_resolves(self):
        with self.ledger() as db:
            self.assertEqual(db.append_wss_final(verified_final()),
                             "HOLD_NOT_BOOTSTRAPPED")
            self.assertIn("NOT_BOOTSTRAPPED", db.inspect(SYMBOL)["open_candle_gates"])
        with self.ledger() as db:
            self.boot(db)
            self.assertNotIn("NOT_BOOTSTRAPPED",
                             db.inspect(SYMBOL)["open_candle_gates"])

    def test_gap_is_persisted_and_recovered_only_with_matching_rest(self):
        with self.ledger() as db:
            self.boot(db)
            self.assertEqual(
                db.append_wss_final(verified_final(EVENT + 2 * INTERVAL_MS)),
                "HOLD_CANDLE_GAP"
            )
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)
            self.assertIn("CANDLE_GAP", db.inspect(SYMBOL)["open_candle_gates"])
        with self.ledger() as db:
            self.assertIn("CANDLE_GAP", db.inspect(SYMBOL)["open_candle_gates"])
            self.assertEqual(db.append_wss_final(verified_final()),
                             "HOLD_UNRESOLVED_SOURCE")
            self.assertEqual(db.reconcile_rest_gap(
                SYMBOL, klines(EVENT + 2 * INTERVAL_MS),
                event_open_ms=EVENT + 2 * INTERVAL_MS,
                observed_ms=EVENT + 3 * INTERVAL_MS + 2000
            ), 2)
            report = db.inspect(SYMBOL)
            self.assertEqual(report["closed_bar_count"], 98)
            self.assertEqual(report["open_candle_gates"], ())
            self.assertTrue(report["candle_contiguous"])
            self.assertEqual(report["quote_health"], "UNVERIFIED")
            self.assertEqual(report["trade_health"], "UNVERIFIED")
            self.assertFalse(report["research_ready"])

    def test_mismatched_rest_overlap_leaves_sticky_source_conflict(self):
        with self.ledger() as db:
            self.boot(db)
            db.append_wss_final(verified_final(EVENT + 2 * INTERVAL_MS))
            payload = klines(EVENT + 2 * INTERVAL_MS)
            # Changing a past close is conflicting source evidence, not repair.
            payload[-3][4] = "100.25"
            with self.assertRaisesRegex(EvidenceHold, "REST_WSS_MISMATCH"):
                db.reconcile_rest_gap(
                    SYMBOL, payload, event_open_ms=EVENT + 2 * INTERVAL_MS,
                    observed_ms=EVENT + 3 * INTERVAL_MS + 2000,
                )
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)
        with self.ledger() as db:
            self.assertIn("SOURCE_CONFLICT", db.inspect(SYMBOL)["open_candle_gates"])
            with self.assertRaisesRegex(EvidenceHold, "MANUAL_REVIEW"):
                db.reconcile_rest_gap(
                    SYMBOL, klines(EVENT + 2 * INTERVAL_MS),
                    event_open_ms=EVENT + 2 * INTERVAL_MS,
                    observed_ms=EVENT + 3 * INTERVAL_MS + 2000,
                )

    def test_conflicting_wss_replay_does_not_overwrite_row(self):
        with self.ledger() as db:
            self.boot(db)
            wss = verified_final()
            db.append_wss_final(wss)
            with self.assertRaisesRegex(EvidenceHold, "SOURCE_CONFLICT"):
                db.append_wss_final(verified_final(close="100.5"))
            self.assertEqual(db._stored(SYMBOL, EVENT + INTERVAL_MS)[4], 100.0)
            self.assertIn("SOURCE_CONFLICT", db.inspect(SYMBOL)["open_candle_gates"])

    def test_gapped_invalid_and_oversize_rest_recovery_are_held(self):
        with self.ledger() as db:
            self.boot(db)
            db.append_wss_final(verified_final(EVENT + 2 * INTERVAL_MS))
            with self.assertRaisesRegex(EvidenceHold, "REST_RECOVERY_INVALID"):
                db.reconcile_rest_gap(
                    SYMBOL, klines(EVENT + 2 * INTERVAL_MS)[:-1],
                    event_open_ms=EVENT + 2 * INTERVAL_MS,
                    observed_ms=EVENT + 3 * INTERVAL_MS + 2000,
                )
            far = EVENT + 97 * INTERVAL_MS
            with self.assertRaisesRegex(EvidenceHold, "OVERLAP_REQUIRED"):
                db.reconcile_rest_gap(
                    SYMBOL, klines(far), event_open_ms=far,
                    observed_ms=far + INTERVAL_MS + 1000,
                )
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)

    def test_recovery_batch_rolls_back_atomically(self):
        with self.ledger() as db:
            self.boot(db)
            db.append_wss_final(verified_final(EVENT + 2 * INTERVAL_MS))
            original = db._insert
            seen = [0]
            def broken(*args):
                seen[0] += 1
                if seen[0] == 2:
                    raise RuntimeError("INJECTED_STORAGE_FAILURE")
                return original(*args)
            with patch.object(db, "_insert", side_effect=broken):
                with self.assertRaisesRegex(RuntimeError, "INJECTED"):
                    db.reconcile_rest_gap(
                        SYMBOL, klines(EVENT + 2 * INTERVAL_MS),
                        event_open_ms=EVENT + 2 * INTERVAL_MS,
                        observed_ms=EVENT + 3 * INTERVAL_MS + 2000,
                    )
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)
            self.assertIn("CANDLE_GAP", db.inspect(SYMBOL)["open_candle_gates"])
        with self.ledger() as db:
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)

    def test_sqlite_candle_gate_and_evidence_tables_append_only(self):
        with self.ledger() as db:
            self.boot(db)
            db.append_wss_final(verified_final(EVENT + 2 * INTERVAL_MS))
            for table in ("candle_rows", "gate_events", "evidence_events"):
                with self.subTest(table=table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.db.execute(f"DELETE FROM {table}")
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.db.execute(f"UPDATE {table} SET rowid=rowid")
            db.db.rollback()
        with self.ledger() as db:
            self.assertEqual(db.inspect(SYMBOL)["closed_bar_count"], 96)

    def test_no_historical_v4_path_may_be_created_or_reused(self):
        for name in (
            "/home/ubuntu/Nbot/data/observation/v4/research_ledger.db",
            "/home/ubuntu/Nbot/data/observation/live/observer.db",
        ):
            with self.subTest(path=name), self.assertRaisesRegex(
                EvidenceHold, "LEGACY_PATH_FORBIDDEN"
            ):
                CandleEvidenceLedger(name)

    def test_last_event_not_started_rejects_early_arrival(self):
        with self.ledger() as db:
            with self.assertRaisesRegex(EvidenceHold, "NOT_FULLY_CLOSED"):
                db.bootstrap_rest(SYMBOL, klines(), event_open_ms=EVENT,
                                  observed_ms=EVENT + INTERVAL_MS - 1)
            self.assertIsNone(db.inspect(SYMBOL)["last_event_open_ms"])

    def test_rest_recovery_is_never_a_trade_or_quote_gate_repair(self):
        with self.ledger() as db:
            self.boot(db)
            with self.assertRaisesRegex(EvidenceHold, "RECOVERY_NOT_REQUESTED"):
                db.reconcile_rest_gap(
                    SYMBOL, klines(EVENT + INTERVAL_MS),
                    event_open_ms=EVENT + INTERVAL_MS,
                    observed_ms=EVENT + 2 * INTERVAL_MS + 1,
                )
            report = db.inspect(SYMBOL)
            self.assertEqual(report["quote_health"], "UNVERIFIED")
            self.assertEqual(report["trade_health"], "UNVERIFIED")
            self.assertFalse(report["research_ready"])


if __name__ == "__main__":
    unittest.main()
