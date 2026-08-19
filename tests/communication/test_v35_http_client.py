from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from nbot.communication.client import ObservationClientError, RemoteObservationClient
from nbot.communication.server import ObservationControlServer
from nbot.config.profiles import get_profile
from nbot.observation.recommendation import ObservationControlTarget
from nbot.execution.execution import ExecutionWorker
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.risk import RiskManager, RiskConfig
from tests.test_v3110_execution_worker import FakeEntry, FakeExchange, FakePosition, FakeReconciliation
from tests.communication.test_v35_control_target import database, seed_event


TOKEN = "control-token-" + "x" * 32
SHA = "a" * 40


def execution_payload(entry_proposal, *, now_ms: int, outcome_id: str = "OUT-1"):
    return {
        "outcome_id": outcome_id,
        "proposal_id": entry_proposal.proposal_id,
        "profile": "testnet-trade",
        "market_environment": "TESTNET",
        "symbol": entry_proposal.symbol,
        "side": entry_proposal.side,
        "entry_price": 100.5,
        "exit_price": 101.0,
        "quantity": 1.0,
        "initial_risk_usd": 10.0,
        "realized_pnl_usd": 0.5,
        "r_multiple": 0.05,
        "mfe_r": 0.2,
        "mae_r": -0.1,
        "entry_timestamp_ms": now_ms + 1_000,
        "closed_timestamp_ms": now_ms + 61_000,
        "entry_order_id": "ORDER-1",
        "entry_client_order_id": "CID-1",
        "entry_authority": entry_proposal.entry_authority,
        "exit_policy_version": entry_proposal.exit_policy_version,
        "final_stop_price": 99.5,
        "final_stop_id": "STOP-1",
        "exit_reason": "TEST_CLOSE",
        "close_source": "TEST",
    }


class V35HTTPClientTests(unittest.TestCase):
    def test_non_loopback_plain_http_client_is_forbidden(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "TLS_REQUIRED_FOR_NON_LOOPBACK"):
                RemoteObservationClient(
                    base_url="http://10.0.0.10:8765",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=Path(td),
                    execution_release_sha=SHA,
                )

    def test_non_loopback_server_requires_tls(self):
        with self.assertRaisesRegex(ValueError, "TLS_REQUIRED_FOR_NON_LOOPBACK"):
            ObservationControlServer(
                target=object(),
                auth_token=TOKEN,
                host="0.0.0.0",
                port=8765,
            )

    def test_live_trade_remote_client_is_forbidden_before_v3_10(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "LIVE_TRADE_FORBIDDEN"):
                RemoteObservationClient(
                    base_url="http://127.0.0.1:8765",
                    profile="live-trade",
                    auth_token=TOKEN,
                    receipt_directory=Path(td),
                    execution_release_sha=SHA,
                )

    def test_authentication_failure_returns_no_control_data(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = database(root, "testnet-trade")
            now = int(time.time() * 1000)
            seed_event(db, captured_at_ms=now)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
            )
            target.refresh_recommendation()
            server = ObservationControlServer(target=target, auth_token=TOKEN, port=0)
            host, port = server.start()
            try:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token="wrong-token-" + "y" * 32,
                    receipt_directory=root / "receipts",
                    execution_release_sha=SHA,
                )
                with self.assertRaisesRegex(ObservationClientError, "OBSERVATION_HTTP_ERROR:401"):
                    client.health()
            finally:
                server.stop()

    def test_local_roundtrip_proposal_outcome_and_duplicate_ack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = database(root, "testnet-trade")
            now = int(time.time() * 1000)
            seed_event(db, captured_at_ms=now)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
            )
            target.refresh_recommendation()
            server = ObservationControlServer(target=target, auth_token=TOKEN, port=0)
            host, port = server.start()
            try:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=root / "receipts",
                    execution_release_sha=SHA,
                )
                health = client.health()
                self.assertEqual(health["order_authority"], "NONE")
                self.assertEqual(health["recommendation_authority"], "TESTNET_OPERATIONAL_CANARY_V1")
                entry = client.request_proposal(
                    profile="testnet-trade",
                    market_environment="TESTNET",
                    execution_instance_id="EXEC-1",
                    requested_at_ms=int(time.time() * 1000),
                )
                self.assertIsNotNone(entry)
                assert entry is not None
                self.assertEqual(entry.entry_authority, "TESTNET_OPERATIONAL_CANARY_V1")
                receipt = client.receipts.get(entry.proposal_id)
                self.assertEqual(receipt["proposal"]["selector_version"], "TESTNET_OPERATIONAL_CANARY_V1")
                payload = execution_payload(entry, now_ms=now)
                self.assertEqual(client.send_outcome(outcome_id="OUT-1", payload=payload), "OUT-1")
                self.assertEqual(client.send_outcome(outcome_id="OUT-1", payload=payload), "OUT-1")
                audit = target.audit()
                self.assertTrue(audit["healthy"])
                self.assertEqual(audit["served_proposals"], 1)
                self.assertEqual(audit["received_outcomes"], 1)
            finally:
                server.stop()


    def test_execution_worker_removes_pending_outcome_only_after_remote_valid_ack(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = database(root, "testnet-trade")
            now = int(time.time() * 1000)
            seed_event(db, captured_at_ms=now)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
            )
            target.refresh_recommendation()
            server = ObservationControlServer(target=target, auth_token=TOKEN, port=0)
            host, port = server.start()
            try:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=root / "receipts",
                    execution_release_sha=SHA,
                )
                entry = client.request_proposal(
                    profile="testnet-trade",
                    market_environment="TESTNET",
                    execution_instance_id="EXEC-OUTBOX",
                    requested_at_ms=int(time.time() * 1000),
                )
                assert entry is not None
                payload = execution_payload(entry, now_ms=now)

                durable = ExecutionDurableStore(root, profile="testnet-trade")
                durable.outbox.enqueue("OUT-1", payload)
                events = []
                risk = RiskManager(RiskConfig())
                exchange = FakeExchange(events)
                entry_lifecycle = FakeEntry(durable.state, exchange, risk, events)
                position = FakePosition(durable.state, exchange, risk, events)
                reconciliation = FakeReconciliation(durable.state, exchange, risk, events)
                worker = ExecutionWorker(
                    exchange=exchange,
                    durable=durable,
                    risk=risk,
                    entry=entry_lifecycle,
                    position=position,
                    reconciliation=reconciliation,
                    proposal_client=client,
                    outcome_client=client,
                    now_ms=lambda: now,
                )
                self.assertEqual(worker.process_flat_cycle(), "ENTRY_DISABLED")
                self.assertEqual(durable.outbox.pending_count(), 0)
                self.assertEqual(target.audit()["received_outcomes"], 1)
            finally:
                server.stop()

    def test_veto_feedback_is_delivered_on_next_flat_request(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = database(root, "testnet-trade")
            now = int(time.time() * 1000)
            seed_event(db, captured_at_ms=now)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
            )
            target.refresh_recommendation()
            server = ObservationControlServer(target=target, auth_token=TOKEN, port=0)
            host, port = server.start()
            try:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=root / "receipts",
                    execution_release_sha=SHA,
                )
                entry = client.request_proposal(
                    profile="testnet-trade",
                    market_environment="TESTNET",
                    execution_instance_id="EXEC-1",
                    requested_at_ms=int(time.time() * 1000),
                )
                assert entry is not None
                client.record_veto(
                    proposal_id=entry.proposal_id,
                    reason="SPREAD_TOO_WIDE",
                    rejected_at_ms=int(time.time() * 1000),
                )
                second = client.request_proposal(
                    profile="testnet-trade",
                    market_environment="TESTNET",
                    execution_instance_id="EXEC-1",
                    requested_at_ms=int(time.time() * 1000),
                )
                self.assertIsNone(second)
                self.assertIsNone(client.receipts.pending_feedback())
                audit = target.audit()
                self.assertEqual(audit["veto_feedback"], 1)
                self.assertEqual(audit["received_outcomes"], 0)
            finally:
                server.stop()

    def test_live_paper_service_stays_not_ready_without_research_champion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = database(root, "live-paper")
            target = ObservationControlTarget(
                db,
                get_profile("live-paper"),
                release_sha=SHA,
            )
            target.refresh_recommendation()
            server = ObservationControlServer(target=target, auth_token=TOKEN, port=0)
            host, port = server.start()
            try:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="live-paper",
                    auth_token=TOKEN,
                    receipt_directory=root / "receipts",
                    execution_release_sha=SHA,
                )
                self.assertIsNone(
                    client.request_proposal(
                        profile="live-paper",
                        market_environment="LIVE",
                        execution_instance_id="EXEC-1",
                        requested_at_ms=int(time.time() * 1000),
                    )
                )
                self.assertEqual(target.audit()["served_proposals"], 0)
            finally:
                server.stop()
