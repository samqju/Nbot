import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from communication.execution_proposal import ExecutionProposal
from communication.observation_client import ObservationClient, ObservationClientError
from communication.observation_server import ObservationHTTPServer
from communication.responses import OutcomeAcknowledgement, TradeResponse
from config import EXECUTION_MODE, TRADING_ENV
from execution.outcome_builder import build_execution_outcome
from observation.execution_outcome_receiver import LocalExecutionOutcomeReceiver
from state.state import StateManager
from strategy.experiment_contract import build_experiment_context
from workers.execution_worker import ExecutionWorker


class Log:
    def __init__(self):
        self.messages = []

    def __getattr__(self, level):
        return lambda message, *args, **kwargs: self.messages.append(
            (level, str(message))
        )


class FakeExchange:
    def __init__(self, *, price=101.0):
        self.price = price

    def connect(self):
        return None

    def disconnect(self):
        return None

    def price_stream(self):
        return iter(())

    def get_position(self):
        return None

    def get_last_price(self, _symbol):
        return self.price

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request_best_trade(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


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


class FakeEntry:
    def __init__(self, *, result=False):
        self.result = result
        self.calls = []
        self.entry_in_progress = False

    def maybe_execute(self, *, intent, market_state):
        self.calls.append((intent, market_state))
        return self.result


class FakeDaily:
    def handle(self, *, timestamp):
        return True


class FakeReconciliation:
    def run(self, reason):
        return None


class FakePositionLifecycle:
    def manage(self, *, market_state):
        return None


def proposal(**overrides):
    now_ms = int(time.time() * 1000)
    values = {
        "proposal_id": "PROP-6A07-DUPLICATE",
        "generated_at": now_ms - 100,
        "expires_at": now_ms + 30_000,
        "environment": TRADING_ENV,
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "pattern": "TREND_CONTINUATION",
        "entry_reference_price": 100.0,
        "candidate_observation_id": "candidate-6a07",
        "decision_batch_id": "batch-6a07",
        "market_event_id": "event-6a07",
        "strategy_version": "STRUCTURE_RULES_V1",
        "strategy_variant_id": "VARIANT-1",
        "model_version": "RULE_SYSTEM_V1",
        "selection_authority": "RULES",
    }
    values.update(overrides)
    return ExecutionProposal.create(**values)


def proposal_response(value):
    return TradeResponse.proposal_response(
        request_id="fake-request",
        responded_at=int(time.time() * 1000),
        proposal=value,
    )


def tick():
    return SimpleNamespace(
        symbol="ETHUSDT",
        price=2000.0,
        timestamp=int(time.time() * 1000),
    )


def worker_for(
    *,
    state,
    client,
    entry=None,
    publisher=None,
    outcome_retry_interval_seconds=5.0,
    proposal_max_future_skew_seconds=5.0,
):
    return ExecutionWorker(
        exchange=FakeExchange(),
        observation_client=client,
        system_log=Log(),
        trade_log=Log(),
        state=state,
        risk=SimpleNamespace(),
        outcome_publisher=publisher or FakePublisher(),
        emergency=SimpleNamespace(),
        daily_lifecycle=FakeDaily(),
        entry_lifecycle=entry or FakeEntry(),
        reconciliation=FakeReconciliation(),
        position_lifecycle=FakePositionLifecycle(),
        request_interval_seconds=0,
        outcome_retry_interval_seconds=outcome_retry_interval_seconds,
        proposal_max_future_skew_seconds=proposal_max_future_skew_seconds,
    )


def execution_outcome():
    position = {
        "symbol": "BTCUSDT",
        "side": "LONG",
        "entry_price": 100.0,
        "qty": 2.0,
        "entry_timestamp": 1_786_170_000_000,
        "entry_order_id": "ORDER-1",
        "entry_client_order_id": "CLIENT-1",
        "initial_stop_loss": 95.0,
        "stop_loss": 101.0,
        "initial_risk_usd": 10.0,
        "risk_usd": 10.0,
        "mae": -3.0,
        "mfe": 14.0,
        "candidate_observation_id": "candidate-6a07",
        "decision_batch_id": "batch-6a07",
        "market_event_id": "event-6a07",
        "pattern": "RANGE_BREAKOUT",
        "strategy_version": "STRUCTURE_RULES_V1",
        "strategy_variant_id": "VARIANT-1",
        "model_version": "RULE_SYSTEM_V1",
        "selection_authority": "RULES",
        "proposal_id": "PROP-6A07-OUTCOME",
        "experiment_context": build_experiment_context(
            decision_batch_id="batch-6a07",
            market_event_id="event-6a07",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="VARIANT-1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=12345,
            structure_fingerprint={"trend": "UP"},
            paper_taker_fee_rate=0.0005,
            paper_entry_slippage_pct=0.02,
            paper_exit_slippage_pct=0.02,
            virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            virtual_target_r=2.0,
            virtual_max_candles=24,
            paper_variant_id="PAPER_TRAILING_SL_V1",
        ),
    }
    return build_execution_outcome(
        open_position=position,
        environment="LIVE",
        execution_mode="SHADOW",
        exit_price=106.0,
        realized_pnl_usd=12.0,
        exit_reason="STOP_LOSS",
        closed_timestamp=1_786_170_060_000,
        holding_seconds=60,
    )


class ProcessedProposalSafetyTests(unittest.TestCase):
    def test_state_load_backfills_processed_proposal_history(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "balance": 0.0,
                        "engine_state": "RUNNING",
                        "open_position": None,
                        "daily_realized_pnl": 0.0,
                        "daily_peak_pnl": 0.0,
                    }
                )
            )
            state = StateManager(str(path))
            state.load()
            self.assertEqual(state.get_state()["processed_proposal_ids"], [])

    def test_processed_proposal_id_survives_restart_and_blocks_replay(self):
        with tempfile.TemporaryDirectory() as root:
            state_path = str(Path(root) / "state.json")
            p = proposal()

            first_state = StateManager(state_path)
            first_entry = FakeEntry(result=True)
            first = worker_for(
                state=first_state,
                client=FakeClient(proposal_response(p)),
                entry=first_entry,
            )
            self.assertEqual(first.process_tick(tick()), "ENTRY_OPENED")
            self.assertTrue(first_state.has_processed_proposal(p.proposal_id))
            self.assertEqual(len(first_entry.calls), 1)

            restarted_state = StateManager(state_path)
            restarted_state.load()
            second_entry = FakeEntry(result=True)
            restarted = worker_for(
                state=restarted_state,
                client=FakeClient(proposal_response(p)),
                entry=second_entry,
            )
            self.assertEqual(
                restarted.process_tick(tick()),
                "PROPOSAL_REJECTED",
            )
            self.assertEqual(second_entry.calls, [])
            self.assertEqual(
                restarted._previous_rejection_reason,
                "DUPLICATE_PROPOSAL",
            )

    def test_proposal_is_durably_reserved_even_when_local_entry_rejects(self):
        with tempfile.TemporaryDirectory() as root:
            state = StateManager(str(Path(root) / "state.json"))
            p = proposal(proposal_id="PROP-LOCAL-REJECT")
            worker = worker_for(
                state=state,
                client=FakeClient(proposal_response(p)),
                entry=FakeEntry(result=False),
            )
            self.assertEqual(worker.process_tick(tick()), "PROPOSAL_REJECTED")
            reloaded = StateManager(state.filename)
            reloaded.load()
            self.assertTrue(reloaded.has_processed_proposal(p.proposal_id))

    def test_future_dated_proposal_is_rejected(self):
        now_ms = int(time.time() * 1000)
        p = proposal(
            proposal_id="PROP-FUTURE",
            generated_at=now_ms + 60_000,
            expires_at=now_ms + 90_000,
        )
        with tempfile.TemporaryDirectory() as root:
            state = StateManager(str(Path(root) / "state.json"))
            entry = FakeEntry(result=True)
            worker = worker_for(
                state=state,
                client=FakeClient(proposal_response(p)),
                entry=entry,
                proposal_max_future_skew_seconds=5,
            )
            self.assertEqual(worker.process_tick(tick()), "PROPOSAL_REJECTED")
            self.assertEqual(entry.calls, [])
            self.assertEqual(
                worker._previous_rejection_reason,
                "PROPOSAL_FUTURE_TIMESTAMP",
            )


class RetryPolicyTests(unittest.TestCase):
    def test_pending_outcome_retry_is_backed_off_between_ticks(self):
        publisher = FakePublisher(pending=1, clear_on_retry=False)
        with tempfile.TemporaryDirectory() as root:
            state = StateManager(str(Path(root) / "state.json"))
            response = TradeResponse.no_trade(
                request_id="fake-request",
                responded_at=int(time.time() * 1000),
                reason="NONE",
            )
            worker = worker_for(
                state=state,
                client=FakeClient(response),
                publisher=publisher,
                outcome_retry_interval_seconds=10,
            )
            self.assertEqual(worker.process_tick(tick()), "PENDING_OUTCOME")
            self.assertEqual(worker.process_tick(tick()), "PENDING_OUTCOME")
            self.assertEqual(publisher.retry_calls, 1)

            worker._last_outcome_retry_monotonic -= 11
            self.assertEqual(worker.process_tick(tick()), "PENDING_OUTCOME")
            self.assertEqual(publisher.retry_calls, 2)


class ObservationBoundaryFailureTests(unittest.TestCase):
    class Target:
        class Store:
            def readiness(self):
                return True, "READY_NO_RECOMMENDATION"

        recommendation_store = Store()

        def handle_trade_request(self, request):
            return TradeResponse.no_trade(
                request_id=request.request_id,
                responded_at=int(time.time() * 1000),
                reason="READY_NO_RECOMMENDATION",
            )

        def receive_execution_outcome(self, outcome):
            return OutcomeAcknowledgement.create(
                outcome_id=outcome.outcome_id,
                acknowledged_at=int(time.time() * 1000),
                status="RECORDED",
            )

    def test_authenticated_server_rejects_wrong_token_and_accepts_right_token(self):
        token = "a" * 32
        server = ObservationHTTPServer(
            target=self.Target(),
            host="127.0.0.1",
            port=0,
            auth_token=token,
        )
        address = server.start()
        try:
            wrong = ObservationClient(
                host=address[0],
                port=address[1],
                auth_token="b" * 32,
            )
            with self.assertRaisesRegex(
                ObservationClientError,
                "status=401",
            ):
                wrong.request_best_trade(
                    environment=TRADING_ENV,
                    execution_mode=EXECUTION_MODE,
                    request_id="REQ-WRONG-AUTH",
                )

            right = ObservationClient(
                host=address[0],
                port=address[1],
                auth_token=token,
            )
            response = right.request_best_trade(
                environment=TRADING_ENV,
                execution_mode=EXECUTION_MODE,
                request_id="REQ-RIGHT-AUTH",
            )
            self.assertEqual(response.status, "NO_TRADE")
        finally:
            server.stop()

    def test_malformed_trade_response_is_normalized_to_boundary_error(self):
        client = ObservationClient()
        with patch.object(
            client,
            "_post",
            return_value={"protocol_version": "NBOT_EXECUTION_V1"},
        ):
            with self.assertRaisesRegex(
                ObservationClientError,
                "OBSERVATION_TRADE_RESPONSE_INVALID",
            ):
                client.request_best_trade(
                    environment=TRADING_ENV,
                    execution_mode=EXECUTION_MODE,
                    request_id="REQ-MALFORMED",
                )

    def test_malformed_outcome_ack_is_normalized_to_boundary_error(self):
        client = ObservationClient()
        with patch.object(client, "_post", return_value={"status": "RECORDED"}):
            with self.assertRaisesRegex(
                ObservationClientError,
                "OBSERVATION_OUTCOME_ACK_INVALID",
            ):
                client.deliver_execution_outcome(execution_outcome())

    def test_timeout_is_fail_closed_boundary_error(self):
        client = ObservationClient(timeout_seconds=0.1)
        with patch(
            "communication.observation_client.http.client.HTTPConnection.request",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaisesRegex(
                ObservationClientError,
                "OBSERVATION_CLIENT_TIMEOUT:/trade-request",
            ):
                client.request_best_trade(
                    environment=TRADING_ENV,
                    execution_mode=EXECUTION_MODE,
                    request_id="REQ-TIMEOUT",
                )


class ConcurrentOutcomeIdempotencyTests(unittest.TestCase):
    def test_concurrent_duplicate_outcomes_create_one_learning_row(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes.jsonl"
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            outcome = execution_outcome()
            with ThreadPoolExecutor(max_workers=8) as pool:
                acknowledgements = list(
                    pool.map(lambda _index: receiver.receive(outcome), range(16))
                )

            statuses = [ack.status for ack in acknowledgements]
            self.assertEqual(statuses.count("RECORDED"), 1)
            self.assertEqual(statuses.count("ALREADY_RECORDED"), 15)
            self.assertEqual(len(path.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
