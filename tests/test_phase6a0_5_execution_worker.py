import ast
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from communication.execution_outcome import ExecutionOutcome
from communication.execution_proposal import ExecutionProposal
from communication.observation_client import (
    ObservationClient,
    ObservationClientError,
)
from communication.observation_server import ObservationHTTPServer
from communication.responses import OutcomeAcknowledgement, TradeResponse
from config import EXECUTION_MODE, TRADING_ENV
from execution.proposal_adapter import proposal_to_execution_intent
from workers.execution_worker import ExecutionWorker


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Log:
    def __init__(self):
        self.messages = []

    def __getattr__(self, level):
        return lambda message, *args, **kwargs: self.messages.append(
            (level, str(message))
        )


class FakeExchange:
    def __init__(self, *, position=None, price=101.0):
        self.position = position
        self.price = price
        self.connected = False
        self.disconnected = False
        self.price_stream_calls = 0
        self.position_stream_symbols = []
        self.position_stream_ticks = []

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.disconnected = True

    def price_stream(self):
        self.price_stream_calls += 1
        return iter(())

    def position_price_stream(self, symbol):
        self.position_stream_symbols.append(symbol)
        return iter(self.position_stream_ticks)

    def get_position(self):
        return self.position

    def get_last_price(self, _symbol):
        return self.price

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class FakeState:
    def __init__(self, *, open_position=None, engine_state="RUNNING"):
        self.open_position = open_position
        self.state = {
            "engine_state": engine_state,
            "engine_halt_reason": None,
            "open_position": open_position,
            "balance": 10000.0,
            "daily_realized_pnl": 0.0,
            "daily_peak_pnl": 0.0,
        }
        self.loaded = 0
        self.saved = 0
        self.heartbeats = []

    def load(self):
        self.loaded += 1

    def save(self):
        self.saved += 1

    def get_open_position(self):
        return self.open_position

    def get_state(self):
        self.state["open_position"] = self.open_position
        return dict(self.state)

    def heartbeat(self, value):
        self.heartbeats.append(value)

    def set_engine_state(self, value, reason=None):
        self.state["engine_state"] = value
        self.state["engine_halt_reason"] = reason


class FakePublisher:
    def __init__(self, *, pending=0, clear_on_retry=False):
        self.pending = pending
        self.clear_on_retry = clear_on_retry
        self.retry_calls = 0

    def pending_count(self):
        return self.pending

    def retry_pending(self):
        self.retry_calls += 1
        delivered = self.pending if self.clear_on_retry else 0
        if self.clear_on_retry:
            self.pending = 0
        return delivered


class FakeDaily:
    def __init__(self):
        self.timestamps = []

    def handle(self, *, timestamp):
        self.timestamps.append(timestamp)
        return True


class FakeEntry:
    def __init__(self, *, result=False):
        self.result = result
        self.calls = []
        self.entry_in_progress = False

    def maybe_execute(self, *, intent, market_state):
        self.calls.append((intent, market_state))
        return self.result


class FakeReconciliation:
    def __init__(self):
        self.reasons = []

    def run(self, reason):
        self.reasons.append(reason)


class FakePositionLifecycle:
    def __init__(self):
        self.calls = []

    def manage(self, *, market_state):
        self.calls.append(market_state)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def request_best_trade(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response

    def receive(self, _outcome):
        raise AssertionError("not expected in these unit tests")


def fresh_proposal(**overrides):
    now_ms = int(time.time() * 1000)
    values = {
        "proposal_id": "PROP-EXECUTION-TEST",
        "generated_at": now_ms - 100,
        "expires_at": now_ms + 30_000,
        "environment": TRADING_ENV,
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "pattern": "TREND_CONTINUATION",
        "entry_reference_price": 100.0,
        "candidate_score": 0.8,
        "candidate_observation_id": "candidate-1",
        "decision_batch_id": "batch-1",
        "market_event_id": "event-1",
        "strategy_version": "STRUCTURE_RULES_V1",
        "strategy_variant_id": "VARIANT-1",
        "model_version": "RULE_SYSTEM_V1",
        "selection_authority": "RULES",
        "structure_fingerprint": {"trend": "UP"},
        "advisory_risk_plan": {"risk_budget_usd": 10.0},
        "experiment_context": {"decision_batch_id": "batch-1"},
    }
    values.update(overrides)
    return ExecutionProposal.create(**values)


def proposal_response(proposal):
    return TradeResponse.proposal_response(
        request_id="fake-request",
        responded_at=int(time.time() * 1000),
        proposal=proposal,
    )


def make_worker(
    *,
    state=None,
    client=None,
    publisher=None,
    entry=None,
    position=None,
    reconciliation=None,
    daily=None,
    exchange=None,
):
    state = state or FakeState()
    client = client or FakeClient(
        TradeResponse.no_trade(
            request_id="fake-request",
            responded_at=int(time.time() * 1000),
            reason="NONE",
        )
    )
    publisher = publisher or FakePublisher()
    entry = entry or FakeEntry()
    position = position or FakePositionLifecycle()
    reconciliation = reconciliation or FakeReconciliation()
    daily = daily or FakeDaily()
    exchange = exchange or FakeExchange(position=state.get_open_position())
    worker = ExecutionWorker(
        exchange=exchange,
        observation_client=client,
        system_log=Log(),
        trade_log=Log(),
        state=state,
        risk=SimpleNamespace(),
        outcome_publisher=publisher,
        emergency=SimpleNamespace(),
        daily_lifecycle=daily,
        entry_lifecycle=entry,
        reconciliation=reconciliation,
        position_lifecycle=position,
        request_interval_seconds=0,
    )
    return worker, state, client, publisher, entry, position, reconciliation, daily, exchange


class ProposalAdapterTests(unittest.TestCase):
    def test_proposal_converts_without_strategy_trade_intent(self):
        proposal = fresh_proposal(proposal_id="PROP-ABC")
        intent = proposal_to_execution_intent(proposal)
        self.assertEqual(intent.proposal_id, "PROP-ABC")
        self.assertEqual(intent.symbol, "BTCUSDT")
        self.assertEqual(intent.direction, "LONG")
        self.assertEqual(intent.entry_price, 100.0)
        self.assertEqual(intent.candidate_observation_id, "candidate-1")
        self.assertEqual(intent.structure_fingerprint, {"trend": "UP"})


class ObservationClientTests(unittest.TestCase):
    class Target:
        class Store:
            @staticmethod
            def readiness():
                return True, "READY"

        recommendation_store = Store()

        def __init__(self):
            self.outcomes = []

        def handle_trade_request(self, request):
            return TradeResponse.no_trade(
                request_id=request.request_id,
                responded_at=int(time.time() * 1000),
                reason="NO_CURRENT_CANDIDATE",
            )

        def receive_execution_outcome(self, outcome):
            self.outcomes.append(outcome)
            return OutcomeAcknowledgement.create(
                outcome_id=outcome.outcome_id,
                acknowledged_at=int(time.time() * 1000),
                status="RECORDED",
            )

    def test_client_is_loopback_only(self):
        with self.assertRaisesRegex(ValueError, "LOCALHOST_ONLY"):
            ObservationClient(host="0.0.0.0")

    def test_client_parses_trade_response_from_local_server(self):
        server = ObservationHTTPServer(target=self.Target(), port=0)
        host, port = server.start()
        try:
            client = ObservationClient(host=host, port=port)
            response = client.request_best_trade(
                environment=TRADING_ENV,
                execution_mode=EXECUTION_MODE,
                request_id="REQ-LOCAL-1",
            )
            self.assertEqual(response.status, "NO_TRADE")
            self.assertEqual(response.request_id, "REQ-LOCAL-1")
        finally:
            server.stop()

    def test_client_connection_failure_is_explicit(self):
        client = ObservationClient(port=1, timeout_seconds=0.1)
        with self.assertRaises(ObservationClientError):
            client.request_best_trade(
                environment=TRADING_ENV,
                execution_mode=EXECUTION_MODE,
                request_id="REQ-DOWN",
            )

    def test_client_delivers_execution_outcome_and_parses_ack(self):
        target = self.Target()
        server = ObservationHTTPServer(target=target, port=0)
        host, port = server.start()
        try:
            client = ObservationClient(host=host, port=port)
            now_ms = int(time.time() * 1000)
            outcome = ExecutionOutcome.create(
                outcome_id="OUT-LOCAL-1",
                proposal_id="PROP-LOCAL-1",
                environment=TRADING_ENV,
                execution_mode=EXECUTION_MODE,
                symbol="BTCUSDT",
                side="LONG",
                entry_price=100.0,
                exit_price=101.0,
                quantity=1.0,
                realized_pnl_usd=1.0,
                initial_risk_usd=10.0,
                r_multiple=0.1,
                mae_usd=-0.5,
                mfe_usd=1.5,
                mae_r=-0.05,
                mfe_r=0.15,
                entry_timestamp=now_ms - 10_000,
                closed_timestamp=now_ms,
                holding_seconds=10,
            )
            ack = client.receive(outcome)
            self.assertEqual(ack.status, "RECORDED")
            self.assertEqual(ack.outcome_id, "OUT-LOCAL-1")
            self.assertEqual(target.outcomes, [outcome])
        finally:
            server.stop()


class ExecutionWorkerTests(unittest.TestCase):
    def tick(self, symbol="ETHUSDT"):
        return SimpleNamespace(
            symbol=symbol,
            price=99.0,
            timestamp=int(time.time() * 1000),
        )

    def test_prepare_reconciles_before_any_flat_request(self):
        worker, state, client, publisher, _, _, reconciliation, _, exchange = make_worker()
        worker.prepare()
        self.assertTrue(exchange.connected)
        self.assertEqual(state.loaded, 1)
        self.assertEqual(reconciliation.reasons, ["EXECUTION_STARTUP"])
        self.assertEqual(client.calls, [])
        self.assertEqual(publisher.retry_calls, 0)

    def test_prepare_open_position_does_not_contact_observation(self):
        open_position = {"symbol": "BTCUSDT", "side": "LONG", "qty": 1.0}
        state = FakeState(open_position=open_position)
        publisher = FakePublisher(pending=1, clear_on_retry=True)
        worker, _, client, _, _, _, _, _, _ = make_worker(
            state=state,
            publisher=publisher,
        )
        worker.prepare()
        self.assertEqual(client.calls, [])
        self.assertEqual(publisher.retry_calls, 0)

    def test_prepare_flat_retries_pending_outcome(self):
        publisher = FakePublisher(pending=1, clear_on_retry=True)
        worker, _, _, _, _, _, _, _, _ = make_worker(publisher=publisher)
        worker.prepare()
        self.assertEqual(publisher.retry_calls, 1)
        self.assertEqual(publisher.pending_count(), 0)

    def test_flat_control_cycle_does_not_require_market_stream(self):
        worker, _, client, _, _, _, _, _, exchange = make_worker()
        worker.prepare()

        with patch(
            "workers.execution_worker.time.sleep",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_forever()

        self.assertEqual(exchange.price_stream_calls, 0)
        self.assertEqual(exchange.position_stream_symbols, [])
        self.assertGreaterEqual(len(client.calls), 1)

    def test_open_runtime_requests_only_position_symbol_stream(self):
        open_position = {"symbol": "BTCUSDT", "side": "LONG", "qty": 1.0}
        state = FakeState(open_position=open_position)
        exchange = FakeExchange(position=open_position)
        exchange.position_stream_ticks = [self.tick("BTCUSDT")]

        class ClosingPositionLifecycle:
            def manage(self, *, market_state):
                state.open_position = None

        worker, _, client, _, _, _, _, _, _ = make_worker(
            state=state,
            exchange=exchange,
            position=ClosingPositionLifecycle(),
        )
        worker._run_open_position_stream(symbol="BTCUSDT")

        self.assertEqual(exchange.position_stream_symbols, ["BTCUSDT"])
        self.assertEqual(exchange.price_stream_calls, 0)
        self.assertEqual(client.calls, [])

    def test_open_position_tick_never_requests_trade_or_retries_outcome(self):
        open_position = {"symbol": "BTCUSDT", "side": "LONG", "qty": 1.0}
        state = FakeState(open_position=open_position)
        publisher = FakePublisher(pending=1, clear_on_retry=True)
        worker, _, client, _, entry, position, _, _, _ = make_worker(
            state=state,
            publisher=publisher,
        )
        result = worker.process_tick(self.tick("BTCUSDT"))
        self.assertEqual(result, "POSITION_MANAGED")
        self.assertEqual(len(position.calls), 1)
        self.assertEqual(client.calls, [])
        self.assertEqual(entry.calls, [])
        self.assertEqual(publisher.retry_calls, 0)

    def test_open_position_ignores_irrelevant_symbol_before_remote_work(self):
        state = FakeState(
            open_position={"symbol": "BTCUSDT", "side": "LONG", "qty": 1.0}
        )
        worker, _, client, publisher, _, position, _, _, _ = make_worker(
            state=state,
            publisher=FakePublisher(pending=1),
        )
        result = worker.process_tick(self.tick("ETHUSDT"))
        self.assertEqual(result, "POSITION_OPEN_OTHER_SYMBOL")
        self.assertEqual(client.calls, [])
        self.assertEqual(publisher.retry_calls, 0)
        self.assertEqual(position.calls, [])

    def test_pending_outcome_blocks_new_trade_when_delivery_still_fails(self):
        publisher = FakePublisher(pending=1, clear_on_retry=False)
        worker, _, client, _, entry, _, _, _, _ = make_worker(
            publisher=publisher,
        )
        result = worker.process_tick(self.tick())
        self.assertEqual(result, "PENDING_OUTCOME")
        self.assertEqual(publisher.retry_calls, 1)
        self.assertEqual(client.calls, [])
        self.assertEqual(entry.calls, [])

    def test_pending_outcome_is_delivered_before_trade_request(self):
        publisher = FakePublisher(pending=1, clear_on_retry=True)
        worker, _, client, _, _, _, _, _, _ = make_worker(
            publisher=publisher,
        )
        result = worker.process_tick(self.tick())
        self.assertEqual(result, "NO_TRADE")
        self.assertEqual(publisher.retry_calls, 1)
        self.assertEqual(len(client.calls), 1)

    def test_no_trade_and_not_ready_keep_execution_flat(self):
        for status in ("NO_TRADE", "NOT_READY"):
            with self.subTest(status=status):
                response = (
                    TradeResponse.no_trade(
                        request_id="fake-request",
                        responded_at=int(time.time() * 1000),
                        reason="NONE",
                    )
                    if status == "NO_TRADE"
                    else TradeResponse.not_ready(
                        request_id="fake-request",
                        responded_at=int(time.time() * 1000),
                        reason="WARMING",
                    )
                )
                worker, _, _, _, entry, _, _, _, _ = make_worker(
                    client=FakeClient(response)
                )
                self.assertEqual(worker.process_tick(self.tick()), status)
                self.assertEqual(entry.calls, [])

    def test_observation_failure_keeps_execution_flat(self):
        client = FakeClient(error=ObservationClientError("down"))
        worker, _, _, _, entry, _, _, _, _ = make_worker(client=client)
        self.assertEqual(
            worker.process_tick(self.tick()),
            "OBSERVATION_UNAVAILABLE",
        )
        self.assertEqual(entry.calls, [])

    def test_fresh_proposal_uses_execution_market_truth_and_entry_lifecycle(self):
        proposal = fresh_proposal(entry_reference_price=10.0)
        entry = FakeEntry(result=True)
        exchange = FakeExchange(price=123.45)
        worker, _, _, _, _, _, _, _, _ = make_worker(
            client=FakeClient(proposal_response(proposal)),
            entry=entry,
            exchange=exchange,
        )
        result = worker.process_tick(self.tick())
        self.assertEqual(result, "ENTRY_OPENED")
        self.assertEqual(len(entry.calls), 1)
        intent, market_state = entry.calls[0]
        self.assertEqual(intent.proposal_id, proposal.proposal_id)
        self.assertEqual(intent.entry_price, 10.0)
        self.assertEqual(market_state.get_price("BTCUSDT"), 123.45)

    def test_expired_proposal_is_rejected_before_entry(self):
        now_ms = int(time.time() * 1000)
        proposal = fresh_proposal(
            generated_at=now_ms - 31_000,
            expires_at=now_ms - 1,
        )
        worker, _, _, _, entry, _, _, _, _ = make_worker(
            client=FakeClient(proposal_response(proposal))
        )
        self.assertEqual(worker.process_tick(self.tick()), "PROPOSAL_REJECTED")
        self.assertEqual(entry.calls, [])
        self.assertEqual(worker._previous_proposal_id, proposal.proposal_id)
        self.assertEqual(worker._previous_rejection_reason, "PROPOSAL_EXPIRED")

    def test_wrong_environment_proposal_is_rejected(self):
        other = "TESTNET" if TRADING_ENV == "LIVE" else "LIVE"
        proposal = fresh_proposal(environment=other)
        worker, _, _, _, entry, _, _, _, _ = make_worker(
            client=FakeClient(proposal_response(proposal))
        )
        self.assertEqual(worker.process_tick(self.tick()), "PROPOSAL_REJECTED")
        self.assertEqual(entry.calls, [])
        self.assertEqual(
            worker._previous_rejection_reason,
            "PROPOSAL_ENVIRONMENT_MISMATCH",
        )

    def test_local_entry_rejection_is_reported_on_next_request(self):
        first_proposal = fresh_proposal(proposal_id="PROP-FIRST")
        second_response = TradeResponse.no_trade(
            request_id="fake-request",
            responded_at=int(time.time() * 1000),
            reason="INVALIDATED",
        )

        class SequenceClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.responses = [
                    proposal_response(first_proposal),
                    second_response,
                ]

            def request_best_trade(self, **kwargs):
                self.calls.append(kwargs)
                return self.responses.pop(0)

        client = SequenceClient()
        worker, _, _, _, _, _, _, _, _ = make_worker(
            client=client,
            entry=FakeEntry(result=False),
        )
        self.assertEqual(worker.process_tick(self.tick()), "PROPOSAL_REJECTED")
        self.assertEqual(worker.process_tick(self.tick()), "NO_TRADE")
        self.assertEqual(client.calls[1]["previous_proposal_id"], "PROP-FIRST")
        self.assertEqual(client.calls[1]["previous_proposal_result"], "REJECTED")
        self.assertEqual(
            client.calls[1]["previous_rejection_reason"],
            "ENTRY_REJECTED_BY_LOCAL_VALIDATION",
        )
        self.assertIsNone(worker._previous_proposal_id)

    def test_paper_model_authority_is_blocked_outside_shadow(self):
        proposal = fresh_proposal(
            selection_authority="PAPER_CANARY",
            paper_canary_model_id="model-1",
            paper_allocation_id="allocation-1",
            paper_risk_multiplier=1.0,
        )
        worker, _, _, _, entry, _, _, _, _ = make_worker(
            client=FakeClient(proposal_response(proposal))
        )
        with patch("workers.execution_worker.EXECUTION_MODE", "TRADE"):
            self.assertEqual(
                worker.process_tick(self.tick()),
                "PROPOSAL_REJECTED",
            )
        self.assertEqual(entry.calls, [])
        self.assertEqual(
            worker._previous_rejection_reason,
            "PAPER_MODEL_AUTHORITY_REQUIRES_SHADOW",
        )


class ArchitectureBoundaryTests(unittest.TestCase):
    @staticmethod
    def imported_modules(path):
        tree = ast.parse(path.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        return imported

    def test_execution_worker_source_has_no_strategy_learning_observation_or_universe_imports(self):
        imported = self.imported_modules(
            PROJECT_ROOT / "workers" / "execution_worker.py"
        )
        forbidden_prefixes = ("strategy", "learning", "observation")
        self.assertFalse(
            {
                name
                for name in imported
                if name == "engine.universe"
                or name.startswith(forbidden_prefixes)
            }
        )
        self.assertNotIn("engine.intent_lifecycle", imported)
        self.assertIn("communication.observation_client", imported)
        self.assertIn("engine.entry_lifecycle", imported)
        self.assertIn("engine.position_lifecycle", imported)

    def test_execution_entrypoint_does_not_import_legacy_engine_or_runtime_runner(self):
        imported = self.imported_modules(PROJECT_ROOT / "run_execution.py")
        self.assertNotIn("engine", imported)
        self.assertNotIn("engine.core", imported)
        self.assertNotIn("runtime_runner", imported)
        self.assertNotIn("strategy", imported)
        self.assertNotIn("learning", imported)
        self.assertIn("workers.execution_worker", imported)

    def test_importing_execution_worker_does_not_load_strategy_or_learning(self):
        code = r'''
import sys
import workers.execution_worker
bad = [
    name for name in sys.modules
    if name == "strategy" or name.startswith("strategy.")
    or name == "learning" or name.startswith("learning.")
    or name == "observation" or name.startswith("observation.")
    or name == "engine.core"
]
print(json.dumps(sorted(bad)))
'''
        result = subprocess.run(
            [sys.executable, "-c", "import json\n" + code],
            cwd=PROJECT_ROOT,
            env=dict(__import__("os").environ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_engine_and_workers_packages_are_lazy(self):
        code = r'''
import json
import sys
import engine
import workers
print(json.dumps({
    "engine_core": "engine.core" in sys.modules,
    "observation_worker": "workers.observation_worker" in sys.modules,
    "execution_worker": "workers.execution_worker" in sys.modules,
}))
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            env=dict(__import__("os").environ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "engine_core": False,
                "observation_worker": False,
                "execution_worker": False,
            },
        )

    def test_importing_execution_entrypoint_does_not_load_research_runtime(self):
        code = r'''
import json
import sys
import run_execution
bad = [
    name for name in sys.modules
    if name == "strategy" or name.startswith("strategy.")
    or name == "learning" or name.startswith("learning.")
    or name == "observation" or name.startswith("observation.")
    or name == "engine.core"
]
print(json.dumps(sorted(bad)))
'''
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            env=dict(__import__("os").environ),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_execution_lifecycles_accept_no_universe(self):
        from engine.position_lifecycle import PositionLifecycle
        from engine.reconciliation import ReconciliationLifecycle

        common = {
            "exchange": SimpleNamespace(),
            "state": SimpleNamespace(),
            "risk": SimpleNamespace(),
            "emergency": SimpleNamespace(),
            "system_log": Log(),
            "trade_log": Log(),
        }
        reconciliation = ReconciliationLifecycle(**common)
        position = PositionLifecycle(
            **common,
            reconciliation=reconciliation,
        )
        self.assertIsNone(reconciliation.universe)
        self.assertIsNone(position.universe)


if __name__ == "__main__":
    unittest.main()
