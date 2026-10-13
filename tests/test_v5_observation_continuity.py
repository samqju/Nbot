"""G1d synthetic live-WSS persistence/recovery and explicit BTC health refusal."""
import asyncio
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import time
import unittest

from nbot.v5.candle_ledger import CandleEvidenceLedger, EvidenceHold
from nbot.v5.live_final_probe import run_probe
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.ws_contract import UnsafeStream
from tests.test_v5_public_market import klines

EVENT = INTERVAL_MS * 1_000_000
RECEIVED = EVENT + INTERVAL_MS + 4_000
SYMBOLS = ("BTCUSDT", "ETHUSDT")


def finalized(symbol="BTCUSDT", *, open_ms=EVENT + INTERVAL_MS,
              close="100"):
    at = open_ms + INTERVAL_MS + 10
    obj = {
        "stream": symbol.lower() + "@kline_5m",
        "data": {"e": "kline", "E": at, "s": symbol,
                 "k": {"t": open_ms, "T": open_ms + INTERVAL_MS - 1,
                       "s": symbol, "i": "5m", "x": True,
                       "o": "100", "h": "101", "l": "99",
                       "c": close, "v": "10"}},
    }
    return json.dumps(obj), at + 1000


def quote(symbol="BTCUSDT", *, update=100):
    obj = {"stream": symbol.lower() + "@depth5@500ms",
           "data": {"e": "depthUpdate", "E": RECEIVED - 10,
                    "s": symbol, "U": update - 1, "u": update,
                    "b": [["99.5", "2"]], "a": [["100.5", "1"]]}}
    return json.dumps(obj)


def trade(symbol="BTCUSDT", *, agg=10):
    obj = {"stream": symbol.lower() + "@aggTrade",
           "data": {"e": "aggTrade", "E": RECEIVED - 10,
                    "T": RECEIVED - 15, "s": symbol,
                    "a": agg, "p": "100", "q": "1"}}
    return json.dumps(obj)


class G1dContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "g1d.db"

    def initialize(self, *, boot=True):
        result = ObservationContinuity(SYMBOLS, self.path)
        if boot:
            for symbol in SYMBOLS:
                self.assertEqual(result.restore_rest(
                    symbol, klines(), event_open_ms=EVENT,
                    observed_ms=RECEIVED), ("BOOTSTRAPPED", 96))
        result.connect("market")
        result.connect("public")
        return result

    def test_real_format_wss_final_appends_both_and_survives_reopen(self):
        with self.initialize() as session:
            for symbol in SYMBOLS:
                frame, received = finalized(symbol)
                self.assertEqual(session.consume(
                    "market", frame, received_ms=received), "APPENDED_WSS_FINAL")
                self.assertEqual(session.consume(
                    "market", frame, received_ms=received), "UNCHANGED_REPLAY")
            report = session.snapshot(event_open_ms=EVENT + INTERVAL_MS,
                                      now_ms=EVENT + 2 * INTERVAL_MS + 2000)
            self.assertFalse(report["research_ready"])
            self.assertEqual(report["totals"]["wss_final_appended"], 2)
            self.assertEqual(report["totals"]["wss_final_replayed"], 2)
            self.assertEqual(report["symbols"]["BTCUSDT"]["persisted"], 97)
            self.assertFalse(report["symbols"]["BTCUSDT"]["research_ready"])
        with CandleEvidenceLedger(self.path) as reopened:
            for symbol in SYMBOLS:
                result = reopened.inspect(symbol)
                self.assertEqual(result["closed_bar_count"], 97)
                self.assertEqual(result["last_event_open_ms"], EVENT + INTERVAL_MS)
                self.assertEqual(result["quote_health"], "UNVERIFIED")
                self.assertFalse(result["research_ready"])

    def test_missing_btc_quote_and_trade_independently_block_coins(self):
        with self.initialize() as session:
            session.consume("public", quote("ETHUSDT"), received_ms=RECEIVED)
            session.consume("market", trade("ETHUSDT"), received_ms=RECEIVED)
            frame, received = finalized("ETHUSDT")
            session.consume("market", frame, received_ms=received)
            ok, issues = session.gate("ETHUSDT",
                                       event_open_ms=EVENT + INTERVAL_MS,
                                       now_ms=received)
            self.assertFalse(ok)
            self.assertIn("BTCUSDT_QUOTE_STALE_OR_MISSING", issues)
            self.assertIn("BTCUSDT_TRADE_STALE_OR_MISSING", issues)
            self.assertIn("BTCUSDT_CANDLE_EVENT_MISSING", issues)
            self.assertIn("RESEARCH_COHORT_NOT_CERTIFIED", issues)

    def test_delayed_or_not_final_is_not_written(self):
        with self.initialize() as session:
            frame, recv = finalized()
            data = json.loads(frame)
            data["data"]["k"]["x"] = False
            self.assertEqual(session.consume(
                "market", json.dumps(data), received_ms=recv
            ), "UNFINISHED_CANDLE_IGNORED")
            self.assertEqual(session.ledger.inspect("BTCUSDT")["closed_bar_count"], 96)
            with self.assertRaises(UnsafeStream):
                session.consume("market", frame, received_ms=EVENT + INTERVAL_MS)
            self.assertEqual(session.ledger.inspect("BTCUSDT")["closed_bar_count"], 96)

    def test_restart_uses_verified_overlap_without_renewing_quote_and_trades(self):
        with self.initialize() as session:
            session.consume("public", quote(), received_ms=RECEIVED)
            session.consume("market", trade(), received_ms=RECEIVED)
            session.disconnect("market")
            session.disconnect("public")
        with ObservationContinuity(SYMBOLS, self.path) as restarted:
            label, count = restarted.restore_rest(
                "BTCUSDT", klines(EVENT + 2 * INTERVAL_MS),
                event_open_ms=EVENT + 2 * INTERVAL_MS,
                observed_ms=EVENT + 3 * INTERVAL_MS + 2500,
            )
            self.assertEqual((label, count), ("REST_CANDLE_RECOVERED", 2))
            checked = restarted.ledger.inspect("BTCUSDT")
            self.assertEqual(checked["closed_bar_count"], 98)
            self.assertEqual(checked["last_event_open_ms"], EVENT + 2 * INTERVAL_MS)
            self.assertFalse(checked["research_ready"])
            self.assertEqual(restarted.store.health.last_quote_ms, {})
            self.assertEqual(restarted.store.health.last_trade_ms, {})
            self.assertFalse(restarted.store.health.cohort_valid)
            _, reasons = restarted.gate(
                "BTCUSDT", event_open_ms=EVENT + 2 * INTERVAL_MS,
                now_ms=EVENT + 3 * INTERVAL_MS + 2500,
            )
            self.assertIn("BTCUSDT_QUOTE_DISCONNECTED", reasons)
            self.assertIn("BTCUSDT_TRADE_DISCONNECTED", reasons)
        with CandleEvidenceLedger(self.path) as check:
            self.assertEqual(check.inspect("BTCUSDT")["closed_bar_count"], 98)

    def test_rest_mismatch_is_sticky_across_crash_and_cannot_advance(self):
        with self.initialize() as session:
            bad = klines(EVENT + INTERVAL_MS)
            bad[-2][4] = "100.2"
            with self.assertRaisesRegex(EvidenceHold, "SOURCE_MISMATCH"):
                session.restore_rest(
                    "BTCUSDT", bad, event_open_ms=EVENT + INTERVAL_MS,
                    observed_ms=EVENT + 2 * INTERVAL_MS + 2500,
                )
            self.assertIn("SOURCE_CONFLICT",
                          session.ledger.inspect("BTCUSDT")["open_candle_gates"])
        with ObservationContinuity(SYMBOLS, self.path) as restarted:
            with self.assertRaisesRegex(EvidenceHold, "SOURCE_CONFLICT"):
                restarted.restore_rest(
                    "BTCUSDT", klines(EVENT + INTERVAL_MS),
                    event_open_ms=EVENT + INTERVAL_MS,
                    observed_ms=EVENT + 2 * INTERVAL_MS + 2500,
                )

    def test_96_bar_history_window_refuses_missing_recovery_overlap(self):
        with self.initialize() as session:
            future = EVENT + 98 * INTERVAL_MS
            with self.assertRaisesRegex(EvidenceHold, "OVERLAP_REQUIRED"):
                session.restore_rest("BTCUSDT", klines(future),
                                     event_open_ms=future,
                                     observed_ms=future + INTERVAL_MS + 2000)
            self.assertEqual(session.ledger.inspect("BTCUSDT")["closed_bar_count"], 96)

    def test_injected_partial_recovery_sqlite_failure_is_atomic(self):
        with self.initialize() as session:
            base_insert = session.ledger._insert
            seen = [0]
            def failed(*args, **kwargs):
                seen[0] += 1
                if seen[0] == 2:
                    raise RuntimeError("SIMULATED_POWER_FAILURE")
                return base_insert(*args, **kwargs)
            from unittest.mock import patch
            with patch.object(session.ledger, "_insert", side_effect=failed):
                with self.assertRaisesRegex(RuntimeError, "POWER_FAILURE"):
                    session.restore_rest(
                        "BTCUSDT", klines(EVENT + 2 * INTERVAL_MS),
                        event_open_ms=EVENT + 2 * INTERVAL_MS,
                        observed_ms=EVENT + 3 * INTERVAL_MS + 2500,
                    )
            self.assertEqual(session.ledger.inspect("BTCUSDT")["closed_bar_count"], 96)
        with CandleEvidenceLedger(self.path) as reopened:
            self.assertEqual(reopened.inspect("BTCUSDT")["closed_bar_count"], 96)
            self.assertIn("CANDLE_GAP", reopened.inspect("BTCUSDT")["open_candle_gates"])

    def test_gapped_wss_cannot_be_automatically_accepted(self):
        with self.initialize() as session:
            frame, recv = finalized(open_ms=EVENT + 2 * INTERVAL_MS)
            self.assertEqual(session.consume("market", frame, received_ms=recv),
                             "HOLD_CANDLE_GAP")
            self.assertEqual(session.ledger.inspect("BTCUSDT")["closed_bar_count"], 96)
            self.assertIn("CANDLE_GAP",
                          session.ledger.inspect("BTCUSDT")["open_candle_gates"])
            self.assertFalse(session.gate(
                "BTCUSDT", event_open_ms=EVENT + 2 * INTERVAL_MS,
                now_ms=recv,
            )[0])

    def test_probe_arguments_cannot_expand_memory_or_time(self):
        for invalid in ((0, 90), (4, 90), (2, 10), (2, 999)):
            with self.subTest(args=invalid), self.assertRaises(EvidenceHold):
                asyncio.run(run_probe(top=invalid[0], seconds=invalid[1]))


if __name__ == "__main__":
    unittest.main()
