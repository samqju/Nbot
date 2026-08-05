import tempfile
import unittest
from pathlib import Path

from strategy.learning_runtime_state import (
    LearningRuntimeStateStore,
)
from strategy.virtual_trade_engine import VirtualTradeEngine


class Phase37VirtualRecoveryTests(unittest.TestCase):
    def _trade(self):
        return {
            "candidate_observation_id": "candidate-1",
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "risk_distance": 1.0,
            "target_price": 102.0,
            "candles_seen": 3,
            "mae_r": 0.4,
            "mfe_r": 0.9,
            "opened_at_ms": 123456,
        }

    def test_active_virtual_trade_restores(self):
        with tempfile.TemporaryDirectory() as root:
            store = LearningRuntimeStateStore(
                str(Path(root) / "state.json")
            )
            store.replace_section(
                "active_virtual_trades",
                [self._trade()],
            )

            engine = VirtualTradeEngine(
                runtime_store=store,
            )

            self.assertEqual(engine.active_count(), 1)
            self.assertEqual(
                engine.active_symbols(),
                {"BTCUSDT"},
            )

    def test_candle_progress_is_persisted(self):
        with tempfile.TemporaryDirectory() as root:
            store = LearningRuntimeStateStore(
                str(Path(root) / "state.json")
            )
            store.replace_section(
                "active_virtual_trades",
                [self._trade()],
            )
            engine = VirtualTradeEngine(
                runtime_store=store,
            )

            engine.on_candle(
                "BTCUSDT",
                (100.0, 100.5, 99.8, 100.2),
            )

            rows = store.get_section(
                "active_virtual_trades"
            )
            self.assertEqual(rows[0]["candles_seen"], 4)
            self.assertGreaterEqual(rows[0]["mfe_r"], 0.9)


if __name__ == "__main__":
    unittest.main()
