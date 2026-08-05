import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from strategy.learning_runtime_state import (
    LearningRuntimeStateStore,
)


class Phase37PendingSimulationRecoveryTests(unittest.TestCase):
    def _simulation(self):
        return {
            "candidate_observation_id": "candidate-2",
            "symbol": "ETHUSDT",
            "direction": "SHORT",
            "entry_price": 200.0,
            "risk_distance": 2.0,
            "candles_seen": 4,
            "mae": 0.3,
            "mfe": 0.8,
            "structure_fingerprint": None,
            "short_range": 0.01,
            "long_range": 0.02,
            "trend_score": -7.0,
            "wick_ratio_recent": 0.4,
            "body_ratio_recent": 0.6,
            "range_acceleration": 0.5,
            "dist_high": -0.01,
            "dist_low": 0.03,
            "directional_consistency": 4.0,
        }

    def test_strategy_restores_pending_simulation(self):
        with tempfile.TemporaryDirectory() as root:
            state_path = Path(root) / "state.json"
            store = LearningRuntimeStateStore(
                str(state_path)
            )
            store.replace_section(
                "pending_simulations",
                [self._simulation()],
            )

            with patch(
                "strategy.strategy.LEARNING_RUNTIME_STATE_PATH",
                str(state_path),
            ):
                from strategy.strategy import Strategy
                strategy = Strategy()

            self.assertEqual(
                len(strategy._pending_simulations),
                1,
            )
            self.assertEqual(
                strategy._pending_simulations[0][
                    "candidate_observation_id"
                ],
                "candidate-2",
            )

    def test_add_pending_simulation_persists(self):
        with tempfile.TemporaryDirectory() as root:
            state_path = Path(root) / "state.json"

            with patch(
                "strategy.strategy.LEARNING_RUNTIME_STATE_PATH",
                str(state_path),
            ):
                from strategy.strategy import Strategy
                strategy = Strategy()
                added = strategy.add_pending_simulation(
                    self._simulation()
                )

            self.assertTrue(added)
            reloaded = LearningRuntimeStateStore(
                str(state_path)
            )
            self.assertEqual(
                len(
                    reloaded.get_section(
                        "pending_simulations"
                    )
                ),
                1,
            )


if __name__ == "__main__":
    unittest.main()
