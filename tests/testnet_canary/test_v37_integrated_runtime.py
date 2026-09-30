from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import run_execution
from nbot.communication.client import ObservationClientError
from nbot.communication.integration import (
    TESTNET_OPERATIONAL_CANARY_AUTHORITY,
    TESTNET_LEARNED_AUTHORITY,
    V37IntegratedObservationClient,
)


RELEASE = "a" * 40


class FakeRemote:
    def __init__(self, *, health: dict | None = None) -> None:
        self.health_payload = health or {
            "status": "READY",
            "profile": "testnet-trade",
            "market_environment": "TESTNET",
            "evidence_lineage": "TESTNET_OPERATIONAL_ONLY",
            "protocol_version": "NBOT_V3_EXECUTION_V1",
            "release_sha": RELEASE,
            "recommendation_authority": TESTNET_OPERATIONAL_CANARY_AUTHORITY,
            "order_authority": "NONE",
        }
        self.calls: list[tuple] = []
        self.proposal = object()

    def health(self):
        self.calls.append(("health",))
        return dict(self.health_payload)

    def request_proposal(self, **kwargs):
        self.calls.append(("proposal", kwargs))
        return self.proposal

    def send_outcome(self, **kwargs):
        self.calls.append(("outcome", kwargs))
        return kwargs["outcome_id"]

    def record_veto(self, **kwargs):
        self.calls.append(("veto", kwargs))


class V37IntegratedObservationClientTests(unittest.TestCase):
    def test_proposal_and_outcome_are_health_gated_but_veto_is_local(self):
        remote = FakeRemote()
        client = V37IntegratedObservationClient(
            remote=remote,
            profile_name="testnet-trade",
            release_sha=RELEASE,
        )

        proposal = client.request_proposal(
            profile="testnet-trade",
            market_environment="TESTNET",
            execution_instance_id="EXEC-1",
            requested_at_ms=1_800_000_000_000,
        )
        self.assertIs(proposal, remote.proposal)
        self.assertEqual(remote.calls[0], ("health",))
        self.assertEqual(remote.calls[1][0], "proposal")

        remote.calls.clear()
        self.assertEqual(
            client.send_outcome(outcome_id="OUT-1", payload={"x": 1}),
            "OUT-1",
        )
        self.assertEqual(remote.calls[0], ("health",))
        self.assertEqual(remote.calls[1][0], "outcome")

        remote.calls.clear()
        client.record_veto(
            proposal_id="P-1",
            reason="SPREAD_TOO_WIDE",
            rejected_at_ms=1_800_000_000_001,
        )
        self.assertEqual(remote.calls[0][0], "veto")
        self.assertFalse(any(call[0] == "health" for call in remote.calls))

    def test_release_mismatch_fails_before_proposal_delegate(self):
        remote = FakeRemote()
        remote.health_payload["release_sha"] = "b" * 40
        client = V37IntegratedObservationClient(
            remote=remote,
            profile_name="testnet-trade",
            release_sha=RELEASE,
        )
        with self.assertRaisesRegex(
            ObservationClientError,
            "OBSERVATION_HEALTH_RELEASE_SHA_MISMATCH",
        ):
            client.request_proposal(
                profile="testnet-trade",
                market_environment="TESTNET",
                execution_instance_id="EXEC-1",
                requested_at_ms=1_800_000_000_000,
            )
        self.assertEqual(remote.calls, [("health",)])

    def test_order_authority_mismatch_fails_before_outcome_delegate(self):
        remote = FakeRemote()
        remote.health_payload["order_authority"] = "BINANCE"
        client = V37IntegratedObservationClient(
            remote=remote,
            profile_name="testnet-trade",
            release_sha=RELEASE,
        )
        with self.assertRaisesRegex(
            ObservationClientError,
            "OBSERVATION_HEALTH_ORDER_AUTHORITY_MISMATCH",
        ):
            client.send_outcome(outcome_id="OUT-1", payload={"x": 1})
        self.assertEqual(remote.calls, [("health",)])


class FakeSnapshot:
    def __init__(self) -> None:
        self.entries_enabled = False


class FakeState:
    def __init__(self) -> None:
        self.open_position = None
        self.snapshot = FakeSnapshot()


class StopRuntime(RuntimeError):
    pass


class FakeWorker:
    def __init__(self) -> None:
        self.state = FakeState()
        self.events: list[str] = []

    def prepare(self):
        self.events.append("prepare")
        return type("Prepared", (), {"status": "FLAT"})()

    def disable_new_entries(self):
        self.events.append("disable")
        self.state.snapshot.entries_enabled = False

    def enable_new_entries(self):
        self.events.append("enable")
        self.state.snapshot.entries_enabled = True
        return type("Prepared", (), {"status": "FLAT"})()

    def process_flat_cycle(self):
        self.events.append("flat")
        raise StopRuntime("stop after wiring proof")


class FakeExchange:
    def __init__(self) -> None:
        self.disconnected = False

    def disconnect(self):
        self.disconnected = True


class V37RuntimeWiringTests(unittest.TestCase):
    def test_runtime_wires_remote_client_into_proposal_and_outcome_boundaries(self):
        worker = FakeWorker()
        exchange = FakeExchange()
        observation = object()
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(run_execution, "profile_is_armed", return_value=True), \
             mock.patch.object(run_execution, "build_testnet_exchange", return_value=exchange), \
             mock.patch.object(run_execution, "build_v37_testnet_client", return_value=observation) as build_client, \
             mock.patch.object(run_execution, "build_execution_worker", return_value=worker) as build_worker:
            root = Path(td)
            with self.assertRaisesRegex(StopRuntime, "wiring proof"):
                run_execution.run_testnet_runtime(
                    repo_root=root,
                    environment={},
                    idle_poll_seconds=0.01,
                    open_poll_seconds=0.01,
                )

        build_client.assert_called_once_with(
            repo_root=root,
            profile_name="testnet-trade",
            environ=mock.ANY,
        )
        kwargs = build_worker.call_args.kwargs
        self.assertIs(kwargs["proposal_client"], observation)
        self.assertIs(kwargs["outcome_client"], observation)
        self.assertEqual(
            kwargs["allowed_entry_authorities"],
            frozenset({TESTNET_OPERATIONAL_CANARY_AUTHORITY, TESTNET_LEARNED_AUTHORITY}),
        )
        self.assertEqual(worker.events[:4], ["prepare", "disable", "enable", "flat"])
        self.assertTrue(exchange.disconnected)

    def test_runtime_refuses_to_start_disarmed_before_exchange_construction(self):
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(run_execution, "profile_is_armed", return_value=False), \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(
                ValueError,
                "NBOT_TESTNET_RUNTIME_REQUIRES_EXPLICIT_ARM",
            ):
                run_execution.run_testnet_runtime(
                    repo_root=Path(td),
                    environment={},
                    idle_poll_seconds=0.01,
                    open_poll_seconds=0.01,
                )
        build_exchange.assert_not_called()


if __name__ == "__main__":
    unittest.main()
