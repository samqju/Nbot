import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("TRADING_ENV", "LIVE")
os.environ.setdefault("EXECUTION_MODE", "SHADOW")
os.environ.setdefault("LIVE_BASE_URL", "https://fapi.binance.com")
os.environ.setdefault(
    "LIVE_MARKET_WS_URL",
    "wss://fstream.binance.com/market/ws/!ticker@arr",
)

from engine.universe import UniverseManager
from observation.recommendation import LatestRecommendationStore
from utils.observation_health import ObservationHealthMonitor
from workers.observation_worker import ObservationWorker


class Log:
    def info(self, _message):
        pass

    def warning(self, _message):
        pass

    def error(self, _message):
        pass

    def critical(self, _message):
        pass

    def debug(self, _message):
        pass


class Strategy:
    WARMUP_WINDOW = 50

    def __init__(self):
        self.retained = {"ETHUSDT"}

    def get_retained_observation_symbols(self):
        return set(self.retained)

    def set_universes(self, *, execution_symbols, observation_symbols):
        self.execution = set(execution_symbols)
        self.observation = set(observation_symbols)

    def seed_candle_history(self, symbol, candles):
        return len(candles)

    def is_warmed_up(self):
        return True

    def on_price(self, **_kwargs):
        pass

    def process_ready_decision_cycles(self, *, paper_entry_allowed):
        return []

    def consume_observation_recommendation(self):
        return None

    def get_virtual_trade_metrics(self):
        return {}


class Exchange:
    def get_historical_candles(self, **_kwargs):
        return [(1, 2, 0.5, 1.5)] * 60


class FakeMarketClient:
    def connect(self):
        pass


class FakeOutcomeReceiver:
    def receive(self, outcome):
        return outcome


class RefreshingUniverse:
    def __init__(self, strategy):
        self.strategy = strategy
        self.symbols = ["BTCUSDT"]
        self.observation_symbols = ["BTCUSDT", "ETHUSDT"]
        self.status = "NOT_RUN"

    def load(self):
        pass

    def warmup(self, _market):
        pass

    def maybe_reload(self, *, force, **_kwargs):
        if force:
            self.status = "NO_CHANGE"
            return
        self.symbols = ["BTCUSDT", "SOLUSDT"]
        self.observation_symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
        ]
        self.status = "SUCCESS"

    def scale_composition_snapshot(self):
        return {
            "ranked_universe_count": 2,
            "effective_universe_count": len(self.observation_symbols),
            "retained_symbol_count": 1,
            "retained_extra_count": max(
                0, len(self.observation_symbols) - 2
            ),
            "execution_symbol_count": len(self.symbols),
            "last_reload_status": self.status,
        }


class Phase6B3ScaleCoverageTests(unittest.TestCase):
    def test_universe_composition_distinguishes_retained_overlap_and_extra(self):
        strategy = Strategy()
        manager = UniverseManager(strategy, Log())
        manager.symbols = ["BTCUSDT"]
        manager.observation_symbols = ["BTCUSDT", "ETHUSDT"]
        manager._ranked_observation_symbols = ["BTCUSDT", "SOLUSDT"]
        manager._last_reload_status = "SUCCESS"

        snapshot = manager.scale_composition_snapshot()

        self.assertEqual(snapshot["ranked_universe_count"], 2)
        self.assertEqual(snapshot["effective_universe_count"], 2)
        self.assertEqual(snapshot["retained_symbol_count"], 1)
        self.assertEqual(snapshot["retained_extra_count"], 1)
        self.assertEqual(snapshot["execution_symbol_count"], 1)
        self.assertEqual(snapshot["last_reload_status"], "SUCCESS")

    def test_existing_rotation_behavior_updates_ranked_composition(self):
        strategy = Strategy()
        manager = UniverseManager(strategy, Log())
        manager.symbols = ["BTCUSDT"]
        manager.observation_symbols = ["BTCUSDT", "ETHUSDT"]
        manager._ranked_observation_symbols = ["BTCUSDT", "ETHUSDT"]
        manager._build_universe = Mock(return_value=["BTCUSDT"])
        manager._build_observation_universe = Mock(
            return_value=["BTCUSDT", "SOLUSDT"]
        )
        manager._persist_observation_snapshot = Mock()

        manager.maybe_reload(exchange=Exchange(), force=True)
        snapshot = manager.scale_composition_snapshot()

        self.assertEqual(manager.observation_symbols, [
            "BTCUSDT", "ETHUSDT", "SOLUSDT"
        ])
        self.assertEqual(snapshot["ranked_universe_count"], 2)
        self.assertEqual(snapshot["effective_universe_count"], 3)
        self.assertEqual(snapshot["retained_extra_count"], 1)
        self.assertEqual(snapshot["last_reload_status"], "SUCCESS")

    def test_health_reports_rates_process_peaks_and_scale(self):
        monitor = ObservationHealthMonitor()
        monitor._started_monotonic = 100.0
        monitor._sample_monotonic = 100.0
        monitor._sample_counters = dict(monitor._counters)
        monitor.set_universes(
            execution_symbols=["BTCUSDT"],
            observation_symbols=["BTCUSDT", "ETHUSDT"],
            observation_target_count=200,
        )
        monitor.record_tick("BTCUSDT", now_monotonic=105.0)
        monitor.record_tick("ETHUSDT", now_monotonic=106.0)

        health = monitor.snapshot(
            scale_metrics={"effective_universe_count": 249},
            now_monotonic=110.0,
        )

        self.assertEqual(health["scale"]["effective_universe_count"], 249)
        self.assertAlmostEqual(
            health["rates"]["total_ticks_per_second"], 0.2
        )
        self.assertAlmostEqual(
            health["rates"]["selected_universe_ticks_per_second"], 0.2
        )
        self.assertGreaterEqual(
            health["process"]["cpu_utilization_percent"], 0.0
        )
        self.assertGreaterEqual(health["process"]["peak_rss_mb"], 0.0)
        self.assertGreaterEqual(health["process"]["cpu_count"], 1)

    def test_worker_records_runtime_refresh_churn_and_duration(self):
        strategy = Strategy()
        universe = RefreshingUniverse(strategy)
        worker = ObservationWorker(
            system_log=Log(),
            market_client=FakeMarketClient(),
            strategy=strategy,
            universe=universe,
            recommendation_store=LatestRecommendationStore(
                environment="LIVE"
            ),
            outcome_receiver=FakeOutcomeReceiver(),
        )
        worker.prepare()
        worker._last_universe_refresh_monotonic = -1_000_000_000.0
        worker.process_tick(SimpleNamespace(
            symbol="BTCUSDT",
            price=100.0,
            timestamp=1_786_170_000_000,
        ))

        scale = worker.observation_health_snapshot()["scale"]
        self.assertEqual(scale["refresh_attempts"], 1)
        self.assertEqual(scale["refresh_successes"], 1)
        self.assertEqual(scale["refresh_failures"], 0)
        self.assertEqual(scale["last_execution_added"], 1)
        self.assertEqual(scale["last_observation_added"], 1)
        self.assertEqual(scale["last_warmup_symbols_count"], 1)
        self.assertEqual(scale["peak_effective_universe_count"], 3)
        self.assertGreaterEqual(scale["last_refresh_duration_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
