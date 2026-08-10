import unittest
from unittest.mock import Mock, patch

from engine.universe import UniverseManager


class Strategy:
    WARMUP_WINDOW = 50

    def __init__(self):
        self.execution = {"BTCUSDT"}
        self.observation = {"BTCUSDT", "ETHUSDT"}
        self.retained = {"ETHUSDT"}

    def get_retained_observation_symbols(self):
        return set(self.retained)

    def set_universes(
        self,
        *,
        execution_symbols,
        observation_symbols,
    ):
        self.execution = set(execution_symbols)
        self.observation = set(observation_symbols)

    def seed_candle_history(self, symbol, candles):
        return len(candles)


class Log:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        pass

    def error(self, message):
        self.errors.append(message)


class Exchange:
    def get_historical_candles(self, **kwargs):
        return [(1, 2, 0.5, 1.5)] * 60


class Phase36B3UniverseRotationTests(unittest.TestCase):
    def _manager(self):
        strategy = Strategy()
        log = Log()
        manager = UniverseManager(strategy, log)
        manager.symbols = ["BTCUSDT"]
        manager.observation_symbols = ["BTCUSDT", "ETHUSDT"]
        return manager, strategy, log

    def test_retained_symbol_survives_ranked_removal(self):
        manager, strategy, _ = self._manager()
        manager._build_universe = Mock(
            return_value=["BTCUSDT"]
        )
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "SOLUSDT"]
        )
        manager._persist_observation_snapshot = Mock()

        manager.maybe_reload(
            exchange=Exchange(),
            force=True,
        )

        self.assertEqual(
            strategy.observation,
            {"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        )
        manager._persist_observation_snapshot.assert_called_once_with(
            ["BTCUSDT", "SOLUSDT"]
        )

    def test_unretained_symbol_is_removed(self):
        manager, strategy, _ = self._manager()
        strategy.retained = set()
        manager._build_universe = Mock(
            return_value=["BTCUSDT"]
        )
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "SOLUSDT"]
        )
        manager._persist_observation_snapshot = Mock()

        manager.maybe_reload(
            exchange=Exchange(),
            force=True,
        )

        self.assertEqual(
            strategy.observation,
            {"BTCUSDT", "SOLUSDT"},
        )

    def test_refresh_interval_prevents_unnecessary_rebuild(self):
        manager, _, _ = self._manager()
        manager._build_universe = Mock(
            return_value=["BTCUSDT"]
        )
        manager._build_observation_universe = Mock()

        with patch.object(
            manager,
            "_observation_refresh_due",
            return_value=False,
        ):
            manager.maybe_reload(
                exchange=Exchange(),
                    force=False,
            )

        manager._build_observation_universe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
