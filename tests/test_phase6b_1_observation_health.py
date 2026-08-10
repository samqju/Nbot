import unittest
from types import SimpleNamespace

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


class FakeMarketClient:
    def connect(self):
        pass


class FakeOutcomeReceiver:
    def receive(self, outcome):
        return outcome


class FakeStrategy:
    def __init__(self):
        self.warmed = False

    def is_warmed_up(self):
        return self.warmed

    def on_price(self, **_kwargs):
        pass

    def process_ready_decision_cycles(self, *, paper_entry_allowed):
        self.paper_entry_allowed = paper_entry_allowed
        return [
            {
                "decision_batch_id": "batch-1",
                "candle_bucket": 123,
                "candidate_count": 4,
                "cycle_coverage": {
                    "symbols_completed": 2,
                    "symbols_expected": 2,
                    "coverage": 1.0,
                    "settled_seconds": 0.25,
                },
            }
        ]

    def consume_observation_recommendation(self):
        return None

    def get_virtual_trade_metrics(self):
        return {
            "active_experiments": 7,
            "active_candidates": 4,
            "runtime_enrollments": 9,
            "runtime_closures": 2,
        }


class FakeUniverse:
    def __init__(self, strategy):
        self.strategy = strategy
        self.symbols = ["BTCUSDT"]
        self.observation_symbols = ["BTCUSDT", "ETHUSDT"]

    def load(self):
        pass

    def maybe_reload(self, **_kwargs):
        pass

    def warmup(self, _market):
        self.strategy.warmed = True


class ObservationHealthMonitorTests(unittest.TestCase):
    def test_monitor_distinguishes_configured_from_seen_symbols(self):
        monitor = ObservationHealthMonitor()
        monitor.set_universes(
            execution_symbols=["BTCUSDT"],
            observation_symbols=["BTCUSDT", "ETHUSDT"],
            observation_target_count=200,
        )

        monitor.record_tick("BTCUSDT")
        monitor.record_tick("XRPUSDT")
        monitor.record_decision_cycles([
            {
                "decision_batch_id": "batch-1",
                "candle_bucket": 100,
                "candidate_count": 3,
                "cycle_coverage": {
                    "symbols_completed": 1,
                    "symbols_expected": 2,
                    "coverage": 0.5,
                    "settled_seconds": 1.5,
                },
            }
        ])

        snapshot = monitor.snapshot()

        self.assertEqual(snapshot["counters"]["total_ticks"], 2)
        self.assertEqual(
            snapshot["counters"]["selected_universe_ticks"],
            1,
        )
        self.assertEqual(snapshot["counters"]["decision_cycles"], 1)
        self.assertEqual(snapshot["counters"]["candidates_seen"], 3)

        self.assertEqual(
            snapshot["universe"]["execution_symbol_count"],
            1,
        )
        self.assertEqual(
            snapshot["universe"]["observation_symbol_count"],
            2,
        )
        self.assertEqual(
            snapshot["universe"]["observation_target_count"],
            200,
        )
        self.assertEqual(snapshot["universe"]["symbols_seen"], 1)
        self.assertEqual(snapshot["universe"]["symbols_unseen"], 1)

        cycle = snapshot["latest_decision_cycle"]
        self.assertEqual(cycle["candle_bucket"], 100)
        self.assertEqual(cycle["candidate_count"], 3)
        self.assertEqual(cycle["symbols_completed"], 1)
        self.assertEqual(cycle["symbols_expected"], 2)
        self.assertEqual(cycle["coverage"], 0.5)

    def test_recommendation_snapshot_is_observational(self):
        store = LatestRecommendationStore(environment="LIVE")

        first = store.status_snapshot()
        self.assertEqual(first["status"], "NOT_READY")
        self.assertFalse(first["proposal_present"])

        store.set_ready(
            True,
            reason="READY_NO_RECOMMENDATION",
        )
        second = store.status_snapshot()
        self.assertEqual(second["status"], "NO_TRADE")
        self.assertEqual(
            second["reason"],
            "READY_NO_RECOMMENDATION",
        )

    def test_worker_aggregates_realtime_observation_metrics(self):
        strategy = FakeStrategy()
        universe = FakeUniverse(strategy)
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

        worker.process_tick(
            SimpleNamespace(
                symbol="BTCUSDT",
                price=100.0,
                timestamp=1_786_170_000_000,
            )
        )

        health = worker.observation_health_snapshot()

        self.assertEqual(health["counters"]["total_ticks"], 1)
        self.assertEqual(
            health["counters"]["selected_universe_ticks"],
            1,
        )
        self.assertEqual(health["counters"]["decision_cycles"], 1)
        self.assertEqual(health["counters"]["candidates_seen"], 4)

        self.assertEqual(
            health["universe"]["execution_symbol_count"],
            1,
        )
        self.assertEqual(
            health["universe"]["observation_symbol_count"],
            2,
        )
        self.assertEqual(health["universe"]["symbols_seen"], 1)

        self.assertEqual(
            health["virtual"]["active_experiments"],
            7,
        )
        self.assertEqual(
            health["virtual"]["runtime_enrollments"],
            9,
        )
        self.assertEqual(
            health["virtual"]["runtime_closures"],
            2,
        )

        self.assertEqual(
            health["recommendation"]["status"],
            "NO_TRADE",
        )
        self.assertEqual(
            health["recommendation"]["reason"],
            "NO_EXECUTION_ELIGIBLE_CANDIDATE",
        )

        self.assertGreaterEqual(
            health["process"]["cpu_seconds"],
            0.0,
        )
        self.assertGreater(
            health["process"]["rss_mb"],
            0.0,
        )


class HealthTarget:
    def __init__(self):
        self.recommendation_store = LatestRecommendationStore(
            environment="LIVE"
        )
        self.recommendation_store.set_ready(
            True,
            reason="READY_NO_RECOMMENDATION",
        )

    def observation_health_snapshot(self):
        return {
            "counters": {"total_ticks": 123},
            "universe": {
                "observation_symbol_count": 200,
                "symbols_seen": 198,
            },
        }


class ObservationHealthHTTPTests(unittest.TestCase):
    def test_health_endpoint_exposes_observation_snapshot(self):
        import http.client
        import json

        from communication.observation_server import ObservationHTTPServer

        target = HealthTarget()
        server = ObservationHTTPServer(
            target=target,
            host="127.0.0.1",
            port=0,
        )
        address = server.start()
        try:
            connection = http.client.HTTPConnection(
                address[0],
                address[1],
                timeout=2,
            )
            connection.request("GET", "/health")
            response = connection.getresponse()
            payload = json.loads(
                response.read().decode("utf-8")
            )
            connection.close()

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["status"], "READY")
            self.assertEqual(
                payload["order_authority"],
                "NONE",
            )
            self.assertEqual(
                payload["health"]["counters"]["total_ticks"],
                123,
            )
            self.assertEqual(
                payload["health"]["universe"][
                    "observation_symbol_count"
                ],
                200,
            )
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
