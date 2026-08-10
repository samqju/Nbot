import json
import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("TRADING_ENV", "LIVE")
os.environ.setdefault("EXECUTION_MODE", "SHADOW")
os.environ.setdefault("LIVE_BASE_URL", "https://fapi.binance.com")
os.environ.setdefault(
    "LIVE_MARKET_WS_URL",
    "wss://fstream.binance.com/market/ws/!ticker@arr",
)

from execution.binance_market_client import BinanceMarketClient
from strategy.decision_cycle import FiveMinuteDecisionCycleCoordinator
from strategy.strategy import Strategy
from utils.observation_health import ObservationHealthMonitor
from workers.observation_worker import ObservationWorker
from observation.recommendation import LatestRecommendationStore


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


class Phase6B2MarketDataIntegrityTests(unittest.TestCase):
    def test_tick_freshness_distinguishes_fresh_delayed_stale_unseen(self):
        monitor = ObservationHealthMonitor()
        monitor.set_universes(
            execution_symbols=["BTCUSDT"],
            observation_symbols=[
                "BTCUSDT",
                "ETHUSDT",
                "XRPUSDT",
                "SOLUSDT",
            ],
            observation_target_count=200,
        )
        monitor.record_tick("BTCUSDT", now_monotonic=100.0)
        monitor.record_tick("ETHUSDT", now_monotonic=120.0)
        monitor.record_tick("XRPUSDT", now_monotonic=139.0)

        snapshot = monitor.snapshot(now_monotonic=140.0)
        universe = snapshot["universe"]

        self.assertEqual(universe["symbols_seen"], 3)
        self.assertEqual(universe["symbols_unseen"], 1)
        self.assertEqual(universe["symbols_fresh"], 1)
        self.assertEqual(universe["symbols_delayed"], 1)
        self.assertEqual(universe["symbols_stale"], 1)
        self.assertEqual(universe["unseen_symbols_sample"], ["SOLUSDT"])
        self.assertEqual(
            universe["stale_symbols_sample"][0]["symbol"],
            "BTCUSDT",
        )
        self.assertAlmostEqual(universe["oldest_tick_age_seconds"], 40.0)
        self.assertAlmostEqual(universe["newest_tick_age_seconds"], 1.0)

    def test_decision_cycle_reports_missing_symbol_identity(self):
        coordinator = FiveMinuteDecisionCycleCoordinator(
            minimum_coverage=0.66,
            settle_seconds=1.0,
        )
        coordinator.set_symbols(["BTCUSDT", "ETHUSDT", "XRPUSDT"])
        coordinator.mark_rollover(
            symbol="BTCUSDT",
            new_bucket=123,
            now_monotonic=10.0,
        )
        coordinator.mark_rollover(
            symbol="ETHUSDT",
            new_bucket=123,
            now_monotonic=10.0,
        )

        ready = coordinator.ready_buckets(now_monotonic=12.0)

        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["symbols_completed"], 2)
        self.assertEqual(ready[0]["symbols_expected"], 3)
        self.assertEqual(ready[0]["missing_symbols_count"], 1)
        self.assertEqual(ready[0]["missing_symbols_sample"], ["XRPUSDT"])

    def test_strategy_records_candle_gaps_without_changing_transition(self):
        strategy = Strategy.__new__(Strategy)
        strategy._market_data_integrity_lock = threading.Lock()
        strategy._candle_gap_events = 0
        strategy._candle_gap_buckets = 0
        strategy._out_of_order_tick_events = 0
        strategy._latest_candle_gap_by_symbol = {}
        strategy._latest_out_of_order_by_symbol = {}
        strategy._market_data_symbol_sample_limit = 20

        strategy._record_candle_transition_integrity(
            symbol="BTCUSDT",
            previous_bucket=100,
            new_bucket=103,
        )
        strategy._record_candle_transition_integrity(
            symbol="ETHUSDT",
            previous_bucket=105,
            new_bucket=104,
        )

        metrics = strategy.get_market_data_integrity_metrics()
        self.assertEqual(metrics["candle_gap_events"], 1)
        self.assertEqual(metrics["missing_candle_buckets"], 2)
        self.assertEqual(metrics["out_of_order_tick_events"], 1)
        self.assertEqual(metrics["gap_symbols_count"], 1)
        self.assertEqual(metrics["out_of_order_symbols_count"], 1)
        self.assertEqual(
            metrics["gap_symbols_sample"][0]["symbol"],
            "BTCUSDT",
        )

    def test_market_client_exposes_transport_and_event_lag(self):
        client = BinanceMarketClient(system_log=Log())
        with patch(
            "execution.binance_market_client.time.time",
            return_value=1_000.0,
        ):
            ticks = client._parse_ws_ticker_message(
                json.dumps([
                    {
                        "s": "BTCUSDT",
                        "c": "65000.0",
                        "E": 999_875,
                    }
                ])
            )

        snapshot = client.market_data_integrity_snapshot()
        self.assertEqual(len(ticks), 1)
        self.assertEqual(snapshot["transport_mode"], "WEBSOCKET")
        self.assertEqual(snapshot["latest_ws_event_lag_ms"], 125)
        self.assertEqual(snapshot["max_ws_event_lag_ms"], 125)
        self.assertIsNotNone(snapshot["last_ws_message_age_seconds"])


if __name__ == "__main__":
    unittest.main()
