import ast
import http.client
import json
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from communication.observation_server import ObservationHTTPServer
from communication.protocol import ProtocolValidationError
from communication.trade_request import TradeRequest
from observation.recommendation import LatestRecommendationStore
from observation.trade_service import ObservationTradeService
from strategy.strategy import Strategy
from strategy.trade_intent import TradeIntent
from workers.observation_worker import ObservationWorker


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def make_intent(**overrides):
    values = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "pattern": "TREND_CONTINUATION",
        "entry_price": None,
        "generated_at": datetime.fromtimestamp(
            1_786_170_000,
            tz=timezone.utc,
        ),
        "structure_fingerprint": {"trend": "UP"},
        "advisory_risk_plan": {"risk_budget_usd": 10.0},
        "candidate_observation_id": "candidate-1",
        "decision_batch_id": "batch-1",
        "market_event_id": "event-1",
        "strategy_version": "STRUCTURE_RULES_V1",
        "strategy_variant_id": "STRUCTURE_CANDIDATE_GENERATOR_V1",
        "model_version": "RULE_SYSTEM_V1",
        "experiment_context": None,
        "selection_authority": "RULES",
        "paper_canary_model_id": None,
        "paper_risk_multiplier": 1.0,
        "paper_allocation_id": None,
    }
    values.update(overrides)
    return TradeIntent(**values)


class RecommendationTests(unittest.TestCase):
    def test_store_converts_intent_to_short_lived_proposal(self):
        store = LatestRecommendationStore(environment="LIVE")
        proposal = store.publish_intent(make_intent())
        self.assertEqual(proposal.environment, "LIVE")
        self.assertEqual(proposal.symbol, "BTCUSDT")
        self.assertEqual(proposal.decision_batch_id, "batch-1")
        self.assertEqual(proposal.expires_at - proposal.generated_at, 30_000)
        self.assertTrue(proposal.proposal_id.startswith("PROP-"))

    def test_same_decision_identity_builds_stable_proposal_id(self):
        first = LatestRecommendationStore(environment="LIVE").publish_intent(
            make_intent()
        )
        second = LatestRecommendationStore(environment="LIVE").publish_intent(
            make_intent()
        )
        self.assertEqual(first.proposal_id, second.proposal_id)

    def test_expired_recommendation_is_not_served(self):
        store = LatestRecommendationStore(environment="LIVE")
        proposal = store.publish_intent(make_intent())
        current, reason = store.current(now_ms=proposal.expires_at + 1)
        self.assertIsNone(current)
        self.assertEqual(reason, "RECOMMENDATION_EXPIRED")

    def test_rejection_invalidates_matching_snapshot(self):
        store = LatestRecommendationStore(environment="LIVE")
        proposal = store.publish_intent(make_intent())
        self.assertTrue(store.reject(proposal.proposal_id, reason="SPREAD_TOO_WIDE"))
        current, reason = store.current(now_ms=proposal.generated_at)
        self.assertIsNone(current)
        self.assertEqual(reason, "SPREAD_TOO_WIDE")


class TradeServiceTests(unittest.TestCase):
    def request(self, **overrides):
        values = {
            "request_id": "request-1",
            "requested_at": 1_786_170_000_000,
            "environment": "LIVE",
            "execution_mode": "SHADOW",
        }
        values.update(overrides)
        return TradeRequest.create(**values)

    def test_not_ready_is_distinct_from_no_trade(self):
        store = LatestRecommendationStore(environment="LIVE")
        service = ObservationTradeService(
            recommendation_store=store,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        response = service.handle_trade_request(
            self.request(),
            now_ms=1_786_170_000_100,
        )
        self.assertEqual(response.status, "NOT_READY")

        store.set_ready(True, reason="READY_NO_RECOMMENDATION")
        response = service.handle_trade_request(
            self.request(),
            now_ms=1_786_170_000_100,
        )
        self.assertEqual(response.status, "NO_TRADE")

    def test_fresh_snapshot_returns_proposal_without_consuming_it(self):
        store = LatestRecommendationStore(environment="LIVE")
        proposal = store.publish_intent(make_intent())
        service = ObservationTradeService(
            recommendation_store=store,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        first = service.handle_trade_request(
            self.request(request_id="request-1"),
            now_ms=proposal.generated_at + 1,
        )
        second = service.handle_trade_request(
            self.request(request_id="request-2"),
            now_ms=proposal.generated_at + 2,
        )
        self.assertEqual(first.status, "PROPOSAL")
        self.assertEqual(second.status, "PROPOSAL")
        self.assertEqual(first.proposal.proposal_id, second.proposal.proposal_id)

    def test_rejected_previous_proposal_is_not_returned_again(self):
        store = LatestRecommendationStore(environment="LIVE")
        proposal = store.publish_intent(make_intent())
        service = ObservationTradeService(
            recommendation_store=store,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        response = service.handle_trade_request(
            self.request(
                previous_proposal_id=proposal.proposal_id,
                previous_proposal_result="REJECTED",
                previous_rejection_reason="SPREAD_TOO_WIDE",
            ),
            now_ms=proposal.generated_at + 1,
        )
        self.assertEqual(response.status, "NO_TRADE")
        self.assertEqual(response.reason, "SPREAD_TOO_WIDE")

    def test_environment_and_mode_mismatch_fail_closed(self):
        store = LatestRecommendationStore(environment="LIVE")
        store.set_ready(True)
        service = ObservationTradeService(
            recommendation_store=store,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        with self.assertRaises(ProtocolValidationError):
            service.handle_trade_request(
                self.request(environment="TESTNET"),
                now_ms=1_786_170_000_100,
            )
        with self.assertRaises(ProtocolValidationError):
            service.handle_trade_request(
                self.request(execution_mode="TRADE"),
                now_ms=1_786_170_000_100,
            )


class StrategyBoundaryTests(unittest.TestCase):
    @staticmethod
    def candidate():
        return SimpleNamespace(
            symbol="BTCUSDT",
            direction="LONG",
            pattern="TREND_CONTINUATION",
            risk_plan=None,
            score_breakdown=None,
            experiment_context=None,
            structure_fingerprint={"trend": "UP"},
            observation_id="candidate-1",
            decision_batch_id="batch-1",
            market_event_id="event-1",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            model_version="RULE_SYSTEM_V1",
        )

    def bare_strategy(self):
        strategy = Strategy.__new__(Strategy)
        strategy.system_log = None
        strategy._warmed_up = True
        strategy._coordinated_runtime_enabled = True
        strategy._pending_paper_candidate = self.candidate()
        strategy._pending_paper_route = None
        strategy._last_trade_info = {}
        strategy._current_candle = {"BTCUSDT": {"bucket": 123}}
        return strategy

    def test_observation_recommendation_does_not_claim_trade_governor(self):
        strategy = self.bare_strategy()
        intent = strategy.consume_observation_recommendation()
        self.assertIsNotNone(intent)
        self.assertEqual(strategy._last_trade_info, {})

    def test_legacy_propose_intent_still_updates_trade_governor(self):
        strategy = self.bare_strategy()
        intent = strategy.propose_intent()
        self.assertIsNotNone(intent)
        self.assertEqual(strategy._last_trade_info["BTCUSDT"], (123, "LONG"))


class FakeMarketClient:
    def __init__(self):
        self.connected = False

    def connect(self):
        self.connected = True


class FakeUniverse:
    def __init__(self, strategy):
        self.strategy = strategy
        self.symbols = ["BTCUSDT"]
        self.observation_symbols = ["BTCUSDT", "ETHUSDT"]
        self.loaded = False
        self.reloaded = False
        self.warmed = False

    def load(self):
        self.loaded = True

    def maybe_reload(self, **_kwargs):
        self.reloaded = True

    def warmup(self, _market):
        self.warmed = True
        self.strategy.warmed = True


class FakeStrategy:
    def __init__(self):
        self.warmed = False
        self.ticks = []
        self.intent = make_intent()

    def is_warmed_up(self):
        return self.warmed

    def on_price(self, **kwargs):
        self.ticks.append(kwargs)

    def process_ready_decision_cycles(self, *, paper_entry_allowed):
        self.paper_entry_allowed = paper_entry_allowed
        return [{"decision_batch_id": "batch-1"}]

    def consume_observation_recommendation(self):
        intent, self.intent = self.intent, None
        return intent


class FakeOutcomeReceiver:
    def __init__(self):
        self.received = []

    def receive(self, outcome):
        self.received.append(outcome)
        return "ACK"


class ObservationWorkerTests(unittest.TestCase):
    def test_worker_prepares_public_observation_and_serves_recommendation(self):
        strategy = FakeStrategy()
        market = FakeMarketClient()
        universe = FakeUniverse(strategy)
        receiver = FakeOutcomeReceiver()
        worker = ObservationWorker(
            system_log=Log(),
            market_client=market,
            strategy=strategy,
            universe=universe,
            recommendation_store=LatestRecommendationStore(environment="LIVE"),
            outcome_receiver=receiver,
        )
        worker.prepare()
        self.assertTrue(market.connected)
        self.assertTrue(universe.loaded)
        self.assertTrue(universe.reloaded)
        self.assertTrue(universe.warmed)

        worker._last_universe_refresh_monotonic = time.monotonic()
        tick = SimpleNamespace(
            symbol="BTCUSDT",
            price=100.0,
            timestamp=1_786_170_000_000,
        )
        processed = worker.process_tick(tick)
        self.assertEqual(len(processed), 1)
        self.assertTrue(strategy.paper_entry_allowed)

        request = TradeRequest.create(
            request_id="request-1",
            requested_at=1_786_170_000_000,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        proposal, _ = worker.recommendation_store.current(
            now_ms=1_786_170_000_001
        )
        response = worker.handle_trade_request(
            request,
            now_ms=proposal.generated_at + 1,
        )
        self.assertEqual(response.status, "PROPOSAL")
        self.assertEqual(response.proposal.symbol, "BTCUSDT")

    def test_worker_delegates_execution_outcome_to_observation_receiver(self):
        strategy = FakeStrategy()
        receiver = FakeOutcomeReceiver()
        worker = ObservationWorker(
            system_log=Log(),
            market_client=FakeMarketClient(),
            strategy=strategy,
            universe=FakeUniverse(strategy),
            recommendation_store=LatestRecommendationStore(environment="LIVE"),
            outcome_receiver=receiver,
        )
        result = worker.receive_execution_outcome("OUTCOME")
        self.assertEqual(result, "ACK")
        self.assertEqual(receiver.received, ["OUTCOME"])

    def test_worker_module_has_no_execution_lifecycle_or_private_factory_imports(self):
        tree = ast.parse(
            (PROJECT_ROOT / "workers" / "observation_worker.py").read_text()
        )
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        forbidden = {
            "engine.entry_lifecycle",
            "engine.position_lifecycle",
            "engine.reconciliation",
            "risk.risk",
            "state.state",
            "execution.exchange_factory",
            "execution.live_exchange",
            "execution.paper_exchange",
        }
        self.assertFalse(imported & forbidden, imported & forbidden)
        self.assertIn("execution.binance_market_client", imported)

    def test_observation_entrypoint_does_not_import_trading_engine(self):
        tree = ast.parse((PROJECT_ROOT / "run_observation.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        self.assertNotIn("engine", imported)
        self.assertNotIn("runtime_runner", imported)
        self.assertNotIn("execution.exchange_factory", imported)
        self.assertIn("workers.observation_worker", imported)


class ObservationHTTPServerTests(unittest.TestCase):
    class Target:
        def __init__(self):
            self.recommendation_store = LatestRecommendationStore(
                environment="LIVE"
            )
            self.service = ObservationTradeService(
                recommendation_store=self.recommendation_store,
                environment="LIVE",
                execution_mode="SHADOW",
            )

        def handle_trade_request(self, request):
            return self.service.handle_trade_request(
                request,
                now_ms=1_786_170_000_100,
            )

        def receive_execution_outcome(self, _outcome):
            raise AssertionError("not used")

    def post(self, address, path, payload):
        connection = http.client.HTTPConnection(address[0], address[1], timeout=2)
        body = json.dumps(payload).encode("utf-8")
        connection.request(
            "POST",
            path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_server_is_loopback_only(self):
        with self.assertRaises(ValueError):
            ObservationHTTPServer(
                target=self.Target(),
                host="0.0.0.0",
                port=0,
            )

    def test_local_trade_request_endpoint_returns_not_ready(self):
        target = self.Target()
        server = ObservationHTTPServer(
            target=target,
            host="127.0.0.1",
            port=0,
        )
        address = server.start()
        try:
            request = TradeRequest.create(
                request_id="request-http-1",
                requested_at=1_786_170_000_000,
                environment="LIVE",
                execution_mode="SHADOW",
            )
            status, payload = self.post(
                address,
                "/trade-request",
                request.to_dict(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "NOT_READY")
        finally:
            server.stop()

    def test_local_trade_request_endpoint_returns_current_proposal(self):
        target = self.Target()
        proposal = target.recommendation_store.publish_intent(make_intent())
        server = ObservationHTTPServer(
            target=target,
            host="127.0.0.1",
            port=0,
        )
        address = server.start()
        try:
            request = TradeRequest.create(
                request_id="request-http-2",
                requested_at=proposal.generated_at,
                environment="LIVE",
                execution_mode="SHADOW",
            )
            status, payload = self.post(
                address,
                "/trade-request",
                request.to_dict(),
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "PROPOSAL")
            self.assertEqual(
                payload["proposal"]["proposal_id"],
                proposal.proposal_id,
            )
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
