import unittest
from types import SimpleNamespace
from unittest.mock import patch

from communication.responses import TradeResponse
from test_phase6a0_7_failure_duplicate_safety import (
    FakeClient,
    FakeEntry,
    FakePublisher,
    proposal,
    proposal_response,
    tick,
    worker_for,
)


class DisabledState:
    def __init__(self, *, open_position=None):
        self.open_position = open_position
        self.state = {
            "engine_state": "TRADING_DISABLED",
            "engine_halt_reason": "OPERATOR_DISABLE",
        }
        self.saved = 0
        self.heartbeats = []

    def get_open_position(self):
        return self.open_position

    def get_state(self):
        return self.state

    def set_engine_state(self, engine_state, reason=None):
        self.state["engine_state"] = engine_state
        self.state["engine_halt_reason"] = reason

    def save(self):
        self.saved += 1

    def heartbeat(self, now_ms):
        self.heartbeats.append(now_ms)


class OperatorDisableSafetyTests(unittest.TestCase):
    def test_disabled_shadow_blocks_new_proposal_request(self):
        state = DisabledState()
        entry = FakeEntry(result=True)
        client = FakeClient(
            proposal_response(
                proposal(proposal_id="PROP-DISABLED-SHADOW")
            )
        )
        worker = worker_for(
            state=state,
            client=client,
            entry=entry,
        )

        with patch("workers.execution_worker.EXECUTION_MODE", "SHADOW"):
            result = worker.process_tick(tick())

        self.assertEqual(result, "ENTRY_DISABLED")
        self.assertEqual(client.calls, [])
        self.assertEqual(entry.calls, [])

    def test_disabled_worker_still_retries_pending_outcome(self):
        state = DisabledState()
        publisher = FakePublisher(
            pending=1,
            clear_on_retry=True,
        )
        response = TradeResponse.no_trade(
            request_id="fake-request",
            responded_at=tick().timestamp,
            reason="NONE",
        )
        worker = worker_for(
            state=state,
            client=FakeClient(response),
            publisher=publisher,
        )

        self.assertEqual(worker.process_tick(tick()), "ENTRY_DISABLED")
        self.assertEqual(publisher.retry_calls, 1)
        self.assertEqual(publisher.pending, 0)

    def test_disabled_worker_still_manages_open_position(self):
        state = DisabledState(open_position={"symbol": "ETHUSDT"})
        response = TradeResponse.no_trade(
            request_id="fake-request",
            responded_at=tick().timestamp,
            reason="NONE",
        )
        client = FakeClient(response)
        worker = worker_for(state=state, client=client)
        manage_calls = []
        worker.position_lifecycle = SimpleNamespace(
            manage=lambda **kwargs: manage_calls.append(kwargs)
        )
        worker._last_persist_ms = tick().timestamp

        self.assertEqual(worker.process_tick(tick()), "POSITION_MANAGED")
        self.assertEqual(len(manage_calls), 1)
        self.assertEqual(client.calls, [])

    def test_enable_command_restores_running_state(self):
        state = DisabledState()
        response = TradeResponse.no_trade(
            request_id="fake-request",
            responded_at=tick().timestamp,
            reason="NONE",
        )
        worker = worker_for(
            state=state,
            client=FakeClient(response),
        )

        with patch("workers.execution_worker.send_info"):
            worker._handle_operator_command("/enable")

        self.assertEqual(state.state["engine_state"], "RUNNING")
        self.assertIsNone(state.state["engine_halt_reason"])
        self.assertEqual(state.saved, 1)


if __name__ == "__main__":
    unittest.main()
