import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, FundingEvent, SourceCapture, UniverseCapture, UniverseRow
from nbot.config import CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver


class FakeClient:
    def __init__(self):
        self.clock = 900_100

    def server_time_ms(self):
        return 900_001

    def eligible_universe_capture(self):
        row = UniverseRow("BTCUSDT", 1, 10_000_000, 100, 100.1, 0.09995, 100.05, 100.04, 0.0001, 123)
        return UniverseCapture((row,), (SourceCapture("ticker_24h", 900_010, 900_020),))

    def closed_candles(self, symbols, open_time_ms):
        candle = Candle("BTCUSDT", open_time_ms, open_time_ms + 299_999, 100, 101, 99, 100.5, 10, 1000, 20, 5, 500)
        return {"BTCUSDT": candle}, {}

    def historical_candles_for_symbols(self, symbols, open_times):
        opens = list(open_times)
        return {
            "BTCUSDT": {
                open_ms: Candle("BTCUSDT", open_ms, open_ms + 299_999, 100, 101, 99, 100.5, 10, 1000, 20, 5, 500)
                for open_ms in opens
            }
        }, {}

    def funding_history(self, start_ms, end_ms):
        return [FundingEvent("BTCUSDT", start_ms, 0.0001, 100.0)]

    def now_ms(self):
        self.clock += 1
        return self.clock


class PartialClient(FakeClient):
    def closed_candles(self, symbols, open_time_ms):
        return {}, {"BTCUSDT": "simulated failure"}


class LateContextClient(FakeClient):
    def eligible_universe_capture(self):
        row = UniverseRow("BTCUSDT", 1, 10_000_000, 100, 100.1, 0.09995, 100.05, 100.04, 0.0001, 123)
        return UniverseCapture((row,), (SourceCapture("ticker_24h", 939_990, 940_000),))


class ClockSkewClient(FakeClient):
    def now_ms(self):
        return 910_000


class ObserverTests(unittest.TestCase):
    def _make(self, client=None):
        tmp = tempfile.TemporaryDirectory()
        cfg = replace(
            CONFIG,
            database_path=Path(tmp.name) / "observer.db",
            observation_universe_size=1,
            funding_sync_interval_seconds=1,
        )
        db = EvidenceDB(cfg)
        db.initialize()
        observer = MarketEvidenceObserver(cfg, client or FakeClient(), db)
        return tmp, db, observer

    def test_collect_once_writes_point_in_time_market_before_strategy_exists(self):
        tmp, db, observer = self._make()
        try:
            result = observer.collect_once()
            self.assertEqual(result.status, "COMPLETE")
            self.assertEqual(result.stored_symbols, 1)
            self.assertTrue(db.has_complete_event(600_000))
            self.assertEqual(db.status()["research_ready_events"], 1)
        finally:
            tmp.cleanup()

    def test_second_collection_skips_complete_event(self):
        tmp, _db, observer = self._make()
        try:
            observer.collect_once()
            second = observer.collect_once()
            self.assertTrue(second.skipped)
        finally:
            tmp.cleanup()

    def test_partial_capture_is_rejected_atomically(self):
        tmp, db, observer = self._make(PartialClient())
        try:
            with self.assertLogs("nbot.v2.observer", level="WARNING") as captured:
                result = observer.collect_once()
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(db.status()["events"], 0)
            self.assertTrue(any("simulated failure" in line for line in captured.output))
        finally:
            tmp.cleanup()

    def test_late_point_in_time_context_is_rejected_atomically(self):
        tmp, db, observer = self._make(LateContextClient())
        try:
            with self.assertLogs("nbot.v2.observer", level="WARNING") as captured:
                result = observer.collect_once()
            self.assertEqual(result.status, "PARTIAL")
            self.assertEqual(db.status()["events"], 0)
            with db._connect() as conn:
                detail = conn.execute("SELECT detail FROM collection_attempts ORDER BY id DESC LIMIT 1").fetchone()[0]
            self.assertIn("__LATE_CONTEXT__", detail)
            self.assertTrue(any("__LATE_CONTEXT__" in line for line in captured.output))
        finally:
            tmp.cleanup()

    def test_clock_skew_fails_closed_before_capture(self):
        tmp, db, observer = self._make(ClockSkewClient())
        try:
            with self.assertRaisesRegex(RuntimeError, "clock skew"):
                observer.collect_once()
            self.assertEqual(db.status()["events"], 0)
        finally:
            tmp.cleanup()

    def test_gap_recovery_is_candle_only(self):
        tmp, db, observer = self._make()
        try:
            row = UniverseRow("BTCUSDT", 1, 10_000_000, 100, 100.1, 0.09995, 100.05, 100.04, 0.0001, 123)
            db.store_event(
                event_open_ms=0,
                event_close_ms=299_999,
                captured_at_ms=400_000,
                requested_symbols=1,
                universe_rows=[row],
                candles={"BTCUSDT": Candle("BTCUSDT", 0, 299_999, 100, 101, 99, 100.5, 10, 1000, 20, 5, 500)},
                error_count=0,
                capture_duration_ms=10,
            )
            result = observer.recover_gaps(max_events=2)
            self.assertEqual(result["recovered"], 2)
            status = db.status()
            self.assertEqual(status["events"], 3)
            self.assertEqual(status["research_ready_events"], 1)
            self.assertEqual(status["recovered_events"], 2)
            self.assertEqual(status["snapshots"], 1)
        finally:
            tmp.cleanup()

    def test_funding_sync_records_coverage(self):
        tmp, db, observer = self._make()
        try:
            observer.collect_once()
            result = observer.sync_funding_history(force=True)
            self.assertFalse(result["skipped"])
            self.assertEqual(result["rows"], 1)
            self.assertEqual(db.status()["funding_events"], 1)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
