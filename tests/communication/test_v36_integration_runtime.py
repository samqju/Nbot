from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.communication.config import (
    control_link_config_for_profile,
    control_link_environment,
)
from nbot.communication.integration import (
    TESTNET_OPERATIONAL_CANARY_AUTHORITY,
    V36_DISARMED_VETO_REASON,
    run_v36_disarmed_cycle,
)
from nbot.config.profiles import get_profile
from nbot.execution.entry import EntryProposal
from nbot.execution.outcomes import ExecutionDurableStore


REPO = Path(__file__).resolve().parents[2]
SHA = "5" * 40


class FakeClient:
    instance = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent = []
        self.vetoes = []
        self.proposal = None
        self.health_payload = {
            "protocol_version": "NBOT_V3_EXECUTION_V1",
            "profile": "testnet-trade",
            "market_environment": "TESTNET",
            "evidence_lineage": "TESTNET_OPERATIONAL_ONLY",
            "release_sha": SHA,
            "order_authority": "NONE",
            "recommendation_authority": TESTNET_OPERATIONAL_CANARY_AUTHORITY,
            "status": "READY",
            "reason": None,
        }
        FakeClient.instance = self

    def health(self):
        return dict(self.health_payload)

    def send_outcome(self, *, outcome_id, payload):
        self.sent.append((outcome_id, dict(payload)))
        return outcome_id

    def request_proposal(self, **_kwargs):
        return self.proposal

    def record_veto(self, *, proposal_id, reason, rejected_at_ms):
        self.vetoes.append((proposal_id, reason, rejected_at_ms))


class V36IntegrationRuntimeTests(unittest.TestCase):
    def _root(self, tmp):
        root = Path(tmp)
        (root / ".nbot-role").write_text("EXECUTION\n", encoding="utf-8")
        store = ExecutionDurableStore(root, profile="testnet-trade")
        store.state.set_entries_enabled(False)
        return root, store

    def _run(self, root):
        with mock.patch(
            "nbot.communication.integration._git_sha", return_value=SHA
        ), mock.patch(
            "nbot.communication.integration.control_link_config_for_profile"
        ) as config, mock.patch(
            "nbot.communication.integration.RemoteObservationClient", FakeClient
        ):
            config.return_value.base_url = "http://127.0.0.1:18766"
            config.return_value.auth_token = "x" * 64
            config.return_value.timeout_seconds = 2.0
            config.return_value.ca_file = None
            return run_v36_disarmed_cycle(
                repo_root=root,
                profile_name="testnet-trade",
                now_ms=1_787_154_000_000,
            )

    def test_control_secret_file_requires_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "config/secrets/control-link.env"
            path.parent.mkdir(parents=True)
            path.write_text("NBOT_CONTROL_AUTH_TOKEN=" + "x" * 64 + "\n")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "MODE_INVALID"):
                control_link_environment(root, environ={})

    def test_control_profile_prefers_testnet_specific_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "config/secrets/control-link.env"
            path.parent.mkdir(parents=True)
            path.write_text(
                "NBOT_CONTROL_AUTH_TOKEN=" + "x" * 64 + "\n"
                "NBOT_OBSERVATION_URL=http://127.0.0.1:1\n"
                "NBOT_OBSERVATION_TESTNET_URL=http://127.0.0.1:18766\n"
            )
            path.chmod(0o600)
            config = control_link_config_for_profile(
                root, get_profile("testnet-trade"), environ={}
            )
            self.assertEqual(config.base_url, "http://127.0.0.1:18766")

    def test_dry_cycle_refuses_armed_testnet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._root(tmp)
            arm = root / "runtime/execution/testnet/TESTNET_TRADING_ARMED"
            arm.parent.mkdir(parents=True, exist_ok=True)
            arm.write_text("armed\n")
            with self.assertRaisesRegex(ValueError, "REQUIRES_TESTNET_DISARMED"):
                self._run(root)

    def test_dry_cycle_refuses_enabled_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, store = self._root(tmp)
            store.state.set_entries_enabled(True)
            with self.assertRaisesRegex(ValueError, "ENTRIES_MUST_BE_DISABLED"):
                self._run(root)

    def test_dry_proposal_is_vetoed_never_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._root(tmp)
            original_init = FakeClient.__init__

            def init_with_proposal(client, **kwargs):
                original_init(client, **kwargs)
                client.proposal = EntryProposal(
                    proposal_id="PROP-V36",
                    generated_at_ms=1_787_153_999_000,
                    expires_at_ms=1_787_154_030_000,
                    profile="testnet-trade",
                    market_environment="TESTNET",
                    symbol="BTCUSDT",
                    side="LONG",
                    reference_price=100.0,
                    entry_authority=TESTNET_OPERATIONAL_CANARY_AUTHORITY,
                    exit_policy_version="INTEGER_R_STEP_CONTROL",
                )

            with mock.patch.object(FakeClient, "__init__", init_with_proposal):
                result = self._run(root)
            self.assertEqual(result.status, "DRY_PROPOSAL")
            self.assertEqual(result.proposal_id, "PROP-V36")
            self.assertEqual(
                FakeClient.instance.vetoes[0][1], V36_DISARMED_VETO_REASON
            )
            self.assertFalse(
                (root / "runtime/execution/testnet/TESTNET_TRADING_ARMED").exists()
            )

    def test_pending_outcome_is_acked_before_proposal_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, store = self._root(tmp)
            store.outbox.enqueue("OUT-1", {"outcome_id": "OUT-1", "value": 1})
            order = []

            class OrderedClient(FakeClient):
                def send_outcome(self, *, outcome_id, payload):
                    order.append("outcome")
                    return outcome_id

                def request_proposal(self, **kwargs):
                    order.append("proposal")
                    return None

            with mock.patch(
                "nbot.communication.integration._git_sha", return_value=SHA
            ), mock.patch(
                "nbot.communication.integration.control_link_config_for_profile"
            ) as config, mock.patch(
                "nbot.communication.integration.RemoteObservationClient", OrderedClient
            ):
                config.return_value.base_url = "http://127.0.0.1:18766"
                config.return_value.auth_token = "x" * 64
                config.return_value.timeout_seconds = 2.0
                config.return_value.ca_file = None
                result = run_v36_disarmed_cycle(
                    repo_root=root,
                    profile_name="testnet-trade",
                    now_ms=1_787_154_000_000,
                )
            self.assertEqual(order, ["outcome", "proposal"])
            self.assertEqual(result.pending_before, 1)
            self.assertEqual(result.pending_after, 0)
            self.assertEqual(store.outbox.pending_count(), 0)

    def test_invalid_ack_retains_outbox_and_blocks_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, store = self._root(tmp)
            store.outbox.enqueue("OUT-1", {"outcome_id": "OUT-1", "value": 1})
            order = []

            class BadAckClient(FakeClient):
                def send_outcome(self, *, outcome_id, payload):
                    order.append("outcome")
                    return "WRONG"

                def request_proposal(self, **kwargs):
                    order.append("proposal")
                    return None

            with mock.patch(
                "nbot.communication.integration._git_sha", return_value=SHA
            ), mock.patch(
                "nbot.communication.integration.control_link_config_for_profile"
            ) as config, mock.patch(
                "nbot.communication.integration.RemoteObservationClient", BadAckClient
            ):
                config.return_value.base_url = "http://127.0.0.1:18766"
                config.return_value.auth_token = "x" * 64
                config.return_value.timeout_seconds = 2.0
                config.return_value.ca_file = None
                result = run_v36_disarmed_cycle(
                    repo_root=root,
                    profile_name="testnet-trade",
                    now_ms=1_787_154_000_000,
                )
            self.assertEqual(result.status, "PENDING_OUTCOME")
            self.assertEqual(order, ["outcome"])
            self.assertEqual(store.outbox.pending_count(), 1)

    def test_release_mismatch_fails_before_trade_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = self._root(tmp)

            class BadHealthClient(FakeClient):
                def health(self):
                    body = super().health()
                    body["release_sha"] = "a" * 40
                    return body

                def request_proposal(self, **kwargs):
                    raise AssertionError("trade request must not happen")

            with mock.patch(
                "nbot.communication.integration._git_sha", return_value=SHA
            ), mock.patch(
                "nbot.communication.integration.control_link_config_for_profile"
            ) as config, mock.patch(
                "nbot.communication.integration.RemoteObservationClient", BadHealthClient
            ):
                config.return_value.base_url = "http://127.0.0.1:18766"
                config.return_value.auth_token = "x" * 64
                config.return_value.timeout_seconds = 2.0
                config.return_value.ca_file = None
                result = run_v36_disarmed_cycle(
                    repo_root=root,
                    profile_name="testnet-trade",
                    now_ms=1_787_154_000_000,
                )
            self.assertEqual(result.status, "OBSERVATION_UNAVAILABLE")
            self.assertIn("RELEASE_SHA_MISMATCH", result.reason)

    def test_tracked_testnet_service_is_profile_isolated(self):
        text = (
            REPO / "deploy/systemd/nbot-observation-testnet-control.service.in"
        ).read_text()
        self.assertIn("--profile testnet-trade", text)
        self.assertIn("--control-port 8766", text)
        self.assertIn("EnvironmentFile=@NBOT_ROOT@/config/secrets/control-link.env", text)
        self.assertNotIn("execution-testnet.env", text)

    def test_tunnel_service_is_loopback_and_batch_mode(self):
        text = (
            REPO / "deploy/systemd/nbot-control-tunnel-testnet.service.in"
        ).read_text()
        self.assertIn("BatchMode=yes", text)
        self.assertIn("127.0.0.1:18766:127.0.0.1:8766", text)
        self.assertIn("StrictHostKeyChecking=yes", text)

    def test_execution_entrypoint_exposes_disarmed_dry_action(self):
        text = (REPO / "run_execution.py").read_text()
        self.assertIn("--v36-dry-cycle", text)
        self.assertIn('"integrated_order_gate": "DISARMED"', text)
        self.assertIn('"order_write_attempted": False', text)


if __name__ == "__main__":
    unittest.main()
