import unittest
from unittest.mock import Mock

from engine.universe import UniverseManager


class Strategy:
    WARMUP_WINDOW = 50

    def __init__(self):
        self.execution = {"BTCUSDT"}
        self.observation = {"BTCUSDT", "ETHUSDT"}

    def get_retained_observation_symbols(self):
        return set()

    def set_universes(self, *, execution_symbols, observation_symbols):
        self.execution = set(execution_symbols)
        self.observation = set(observation_symbols)

    def seed_candle_history(self, symbol, candles):
        return len(candles)


class Log:
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []

    def warning(self, message):
        self.warnings.append(message)

    def error(self, message):
        self.errors.append(message)

    def info(self, message):
        self.infos.append(message)

    def debug(self, _message):
        pass


class SelectiveExchange:
    def __init__(self, short_symbols=None):
        self.short_symbols = set(short_symbols or ())

    def get_historical_candles(self, *, symbol, **_kwargs):
        count = 10 if symbol in self.short_symbols else 60
        return [(i * 300000, 1.0, 2.0, 0.5, 1.5) for i in range(count)]


class Phase71AUniverseWarmupAdmissionTests(unittest.TestCase):
    def _manager(self):
        strategy = Strategy()
        log = Log()
        manager = UniverseManager(strategy, log)
        manager.symbols = ["BTCUSDT"]
        manager.observation_symbols = ["BTCUSDT", "ETHUSDT"]
        manager._ranked_observation_symbols = ["BTCUSDT", "ETHUSDT"]
        manager._persist_snapshot = Mock()
        manager._persist_observation_snapshot = Mock()
        return manager, strategy, log

    def test_insufficient_new_observation_symbol_rejects_refresh_without_crash(self):
        manager, strategy, log = self._manager()
        manager._build_universe = Mock(return_value=["BTCUSDT"])
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "ETHUSDT", "DOSUSDT"]
        )

        manager.maybe_reload(
            exchange=SelectiveExchange(short_symbols={"DOSUSDT"}),
            force=True,
        )

        self.assertEqual(manager.symbols, ["BTCUSDT"])
        self.assertEqual(manager.observation_symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(strategy.execution, {"BTCUSDT"})
        self.assertEqual(strategy.observation, {"BTCUSDT", "ETHUSDT"})
        self.assertEqual(manager._last_reload_status, "FAILED_WARMUP")
        manager._persist_snapshot.assert_not_called()
        manager._persist_observation_snapshot.assert_not_called()
        self.assertTrue(any(
            "UNIVERSE_REFRESH_WARMUP_REJECTED" in message
            and "DOSUSDT" in message
            and "KEEP_CURRENT_UNIVERSE" in message
            for message in log.warnings
        ))

    def test_insufficient_prospective_execution_symbol_is_not_committed(self):
        manager, strategy, _ = self._manager()
        manager._build_universe = Mock(
            return_value=["BTCUSDT", "DOSUSDT"]
        )
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "ETHUSDT", "DOSUSDT"]
        )

        manager.maybe_reload(
            exchange=SelectiveExchange(short_symbols={"DOSUSDT"}),
            force=True,
        )

        self.assertEqual(manager.symbols, ["BTCUSDT"])
        self.assertEqual(manager.observation_symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(strategy.execution, {"BTCUSDT"})
        self.assertEqual(manager._last_reload_status, "FAILED_WARMUP")
        manager._persist_snapshot.assert_not_called()
        manager._persist_observation_snapshot.assert_not_called()

    def test_rejected_refresh_still_allows_existing_universe_startup_warmup(self):
        manager, strategy, _ = self._manager()
        manager._build_universe = Mock(return_value=["BTCUSDT"])
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "ETHUSDT", "DOSUSDT"]
        )
        exchange = SelectiveExchange(short_symbols={"DOSUSDT"})

        manager.maybe_reload(exchange=exchange, force=True)
        manager.warmup(exchange)

        self.assertEqual(manager._last_reload_status, "FAILED_WARMUP")
        self.assertEqual(manager.observation_symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(strategy.observation, {"BTCUSDT", "ETHUSDT"})

    def test_sufficient_new_symbol_still_commits_normally(self):
        manager, strategy, _ = self._manager()
        manager._build_universe = Mock(return_value=["BTCUSDT"])
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        )

        manager.maybe_reload(
            exchange=SelectiveExchange(),
            force=True,
        )

        self.assertEqual(
            manager.observation_symbols,
            ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        )
        self.assertEqual(
            strategy.observation,
            {"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        )
        self.assertEqual(manager._last_reload_status, "SUCCESS")
        manager._persist_observation_snapshot.assert_called_once_with(
            ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        )


if __name__ == "__main__":
    unittest.main()
