import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, UniverseRow
from nbot.config import CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver


class FakeClient:
    def server_time_ms(self):
        return 900_001

    def eligible_universe(self):
        return [UniverseRow("BTCUSDT", 1, 10_000_000, 100, 100.1, 0.09995, 100.05, 100.04, 0.0001, 123)]

    def closed_candles(self, symbols, open_time_ms):
        candle = Candle("BTCUSDT", open_time_ms, open_time_ms + 299_999, 100, 101, 99, 100.5, 10, 1000, 20, 5, 500)
        return {"BTCUSDT": candle}, {}

    def now_ms(self):
        return 900_100


class ObserverTests(unittest.TestCase):
    def test_collect_once_writes_market_before_strategy_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = replace(CONFIG, database_path=Path(tmp) / "observer.db", observation_universe_size=1)
            db = EvidenceDB(cfg)
            db.initialize()
            observer = MarketEvidenceObserver(cfg, FakeClient(), db)
            result = observer.collect_once()
            self.assertEqual(result.status, "COMPLETE")
            self.assertEqual(result.stored_symbols, 1)
            self.assertTrue(db.has_complete_event(600_000))

    def test_second_collection_skips_complete_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = replace(CONFIG, database_path=Path(tmp) / "observer.db", observation_universe_size=1)
            db = EvidenceDB(cfg)
            db.initialize()
            observer = MarketEvidenceObserver(cfg, FakeClient(), db)
            observer.collect_once()
            second = observer.collect_once()
            self.assertTrue(second.skipped)


if __name__ == "__main__":
    unittest.main()
