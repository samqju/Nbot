from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.exchange.contracts import Quote
from nbot.execution.canary import (
    MechanicalCanaryError,
    MechanicalCanaryOutcomeClient,
    OneShotMechanicalProposalClient,
    TESTNET_MECHANICAL_AUTHORITY,
    make_mechanical_proposal,
    mechanical_outcome_path,
)

import run_execution


class V321MechanicalCanaryTests(unittest.TestCase):
    def quote(self) -> Quote:
        return Quote(symbol="BTCUSDT", bid=99.0, ask=101.0, timestamp_ms=1_000_000)

    def proposal(self, *, side="LONG"):
        return make_mechanical_proposal(self.quote(), side=side, now_ms=lambda: 1_000_000)

    def test_manual_proposal_is_explicit_testnet_mechanical_only(self):
        proposal = self.proposal()
        self.assertEqual(proposal.profile, "testnet-trade")
        self.assertEqual(proposal.market_environment, "TESTNET")
        self.assertEqual(proposal.entry_authority, TESTNET_MECHANICAL_AUTHORITY)
        self.assertEqual(proposal.reference_price, 101.0)
        self.assertEqual(proposal.expires_at_ms - proposal.generated_at_ms, 30_000)

    def test_short_manual_proposal_uses_bid_reference(self):
        proposal = self.proposal(side="SHORT")
        self.assertEqual(proposal.reference_price, 99.0)

    def test_manual_proposal_client_is_single_use(self):
        client = OneShotMechanicalProposalClient()
        proposal = self.proposal()
        client.offer(proposal)
        kwargs = dict(
            profile="testnet-trade",
            market_environment="TESTNET",
            execution_instance_id="EXEC-1",
            requested_at_ms=1_000_001,
        )
        self.assertIs(client.request_proposal(**kwargs), proposal)
        self.assertIsNone(client.request_proposal(**kwargs))
        with self.assertRaisesRegex(MechanicalCanaryError, "ALREADY_OFFERED"):
            client.offer(self.proposal())

    def test_manual_proposal_client_rejects_wrong_request_environment(self):
        client = OneShotMechanicalProposalClient()
        client.offer(self.proposal())
        with self.assertRaisesRegex(MechanicalCanaryError, "REQUEST_ENVIRONMENT_MISMATCH"):
            client.request_proposal(
                profile="testnet-trade",
                market_environment="LIVE",
                execution_instance_id="EXEC-1",
                requested_at_ms=1_000_001,
            )

    def test_mechanical_outcome_client_persists_nonresearch_label_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mechanical.jsonl"
            client = MechanicalCanaryOutcomeClient(path)
            payload = {
                "outcome_id": "OUT-1",
                "proposal_id": "PROP-1",
                "profile": "testnet-trade",
                "market_environment": "TESTNET",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_authority": TESTNET_MECHANICAL_AUTHORITY,
            }
            self.assertEqual(client.send_outcome(outcome_id="OUT-1", payload=payload), "OUT-1")
            self.assertEqual(client.send_outcome(outcome_id="OUT-1", payload=payload), "OUT-1")
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            saved = rows[0]["payload"]
            self.assertEqual(saved["evidence_class"], "TESTNET_MECHANICAL_ONLY")
            self.assertIs(saved["research_evidence"], False)

    def test_mechanical_outcome_client_rejects_nonmechanical_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = MechanicalCanaryOutcomeClient(Path(tmp) / "mechanical.jsonl")
            with self.assertRaisesRegex(MechanicalCanaryError, "OUTCOME_AUTHORITY_MISMATCH"):
                client.send_outcome(
                    outcome_id="OUT-1",
                    payload={
                        "outcome_id": "OUT-1",
                        "profile": "testnet-trade",
                        "market_environment": "TESTNET",
                        "entry_authority": "RESEARCH_CHAMPION",
                    },
                )

    def test_canary_requires_yes_before_exchange_is_built(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(run_execution, "profile_is_armed", return_value=True), \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(ValueError, "REQUIRES_EXPLICIT_YES"):
                run_execution.run_testnet_canary(
                    repo_root=Path(tmp), environment={}, symbol="BTCUSDT", side="LONG",
                    confirmed=False, open_poll_seconds=0.01,
                )
            build_exchange.assert_not_called()

    def test_canary_requires_arm_before_exchange_is_built(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(run_execution, "profile_is_armed", return_value=False), \
             mock.patch.object(run_execution, "build_testnet_exchange") as build_exchange:
            with self.assertRaisesRegex(ValueError, "REQUIRES_EXPLICIT_ARM"):
                run_execution.run_testnet_canary(
                    repo_root=Path(tmp), environment={}, symbol="BTCUSDT", side="LONG",
                    confirmed=True, open_poll_seconds=0.01,
                )
            build_exchange.assert_not_called()

    def test_cli_rejects_conflicting_testnet_actions(self):
        import subprocess

        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                str(repo / "run_execution.py"),
                "--profile", "testnet-trade",
                "--preflight-only",
                "--testnet-canary",
            ],
            cwd=repo, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("not allowed with argument", result.stderr)

    def test_mechanical_outcome_path_is_profile_scoped_testnet(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                mechanical_outcome_path(tmp),
                Path(tmp) / "data/execution/testnet/mechanical_canary_outcomes.jsonl",
            )

    def test_execution_worker_builder_accepts_only_explicit_local_canary_clients(self):
        # V3.2 wires clients through the existing transport-neutral worker; it
        # does not add Observation/communication implementation here.
        text = (Path(__file__).resolve().parents[1] / "run_execution.py").read_text()
        self.assertIn("proposal_client=proposal_client", text)
        self.assertIn("outcome_client=outcome_client", text)
        # Later V3 phases add only the transport boundary to this entrypoint;
        # Execution must still never import Observation implementation modules.
        self.assertNotIn("from nbot.observation", text)
        self.assertNotIn("import nbot.observation", text)


if __name__ == "__main__":
    unittest.main()
