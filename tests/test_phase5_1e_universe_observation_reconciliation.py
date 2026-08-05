import unittest
from unittest.mock import patch

from engine.universe import UniverseManager


class Strategy:
    WARMUP_WINDOW = 50

    def set_universes(self, **kwargs):
        pass

    def get_retained_observation_symbols(self):
        return set()


class Log:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def info(self, message):
        pass

    def error(self, message):
        pass


class Phase51EUniverseObservationReconciliationTests(unittest.TestCase):
    def test_ineligible_execution_symbols_are_replaced(self):
        log = Log()
        manager = UniverseManager(Strategy(), log)
        manager.symbols = [f"C{i}USDT" for i in range(30)]
        eligible = [f"C{i}USDT" for i in range(2, 32)]
        manager._persist_snapshot = lambda symbols: None

        with patch(
            "observation_universe.build_observation_universe",
            side_effect=[eligible, eligible],
        ):
            result = manager._build_observation_universe()

        self.assertEqual(len(manager.symbols), 30)
        self.assertNotIn("C0USDT", manager.symbols)
        self.assertNotIn("C1USDT", manager.symbols)
        self.assertIn("C30USDT", manager.symbols)
        self.assertIn("C31USDT", manager.symbols)
        self.assertEqual(result, sorted(eligible))
        self.assertTrue(any(
            "EXECUTION_UNIVERSE_OBSERVATION_RECONCILED" in message
            for message in log.warnings
        ))


if __name__ == "__main__":
    unittest.main()
