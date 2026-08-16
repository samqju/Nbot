import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, UniverseRow
from nbot.config import CONFIG
from nbot.db import EvidenceDB


class DBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = replace(CONFIG, database_path=Path(self.tmp.name) / "observer.db", observation_universe_size=1)
        self.db = EvidenceDB(cfg)
        self.db.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def _row(self):
        return UniverseRow("BTCUSDT", 1, 1_000_000_000.0, 100.0, 100.1, 0.09995, 100.05, 100.04, 0.0001, 123)

    def _candle(self):
        return Candle("BTCUSDT", 0, 299_999, 100, 101, 99, 100.5, 10, 1000, 20, 5, 500)

    def test_complete_event_is_idempotently_replaceable(self):
        status = self.db.store_event(
            event_open_ms=0,
            event_close_ms=299_999,
            captured_at_ms=400_000,
            requested_symbols=1,
            universe_rows=[self._row()],
            candles={"BTCUSDT": self._candle()},
            error_count=0,
            capture_duration_ms=10,
        )
        self.assertEqual(status, "COMPLETE")
        self.assertTrue(self.db.has_complete_event(0))
        snapshot = self.db.status()
        self.assertEqual(snapshot["events"], 1)
        self.assertEqual(snapshot["candles"], 1)
        self.assertEqual(snapshot["snapshots"], 1)

    def test_partial_event_is_not_complete(self):
        status = self.db.store_event(
            event_open_ms=0,
            event_close_ms=299_999,
            captured_at_ms=400_000,
            requested_symbols=1,
            universe_rows=[self._row()],
            candles={},
            error_count=1,
            capture_duration_ms=10,
        )
        self.assertEqual(status, "PARTIAL")
        self.assertFalse(self.db.has_complete_event(0))


if __name__ == "__main__":
    unittest.main()
