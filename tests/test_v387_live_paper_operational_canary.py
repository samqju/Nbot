from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from nbot.communication.authorities import LIVE_PAPER_LEARNED_AUTHORITY, LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY
from nbot.communication.client import ObservationClientError, RemoteObservationClient
from nbot.communication.contracts import ExecutionProposal
from nbot.communication.integration import (
    V38LivePaperOperationalClient,
    _validate_health,
)
from nbot.exchange.contracts import Quote
from nbot.execution.entry import EntryProposal


SHA = "a" * 40
NOW = 1_800_000_000_000
TOKEN = "x" * 64


def wire_proposal(*, side: str = "LONG") -> ExecutionProposal:
    return ExecutionProposal.create(
        proposal_id="PROP-V387",
        generated_at_ms=NOW,
        expires_at_ms=NOW + 30_000,
        profile="live-paper",
        market_environment="LIVE",
        evidence_lineage="LIVE_PAPER_OPERATIONAL",
        symbol="BTCUSDT",
        side=side,
        market_event_id="ME-1799999700000",
        data_generation_id="LIVE-PAPER-1799999700000-abcdef1234567890",
        feature_version="LIVE_PAPER_OPERATIONAL_CANARY_NO_MODEL_FEATURES_V1",
        selector_version="LIVE_PAPER_OPERATIONAL_CANARY_HASH_V1",
        entry_authority=LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
        exit_policy_version="INTEGER_R_STEP_CONTROL",
        reference_price=100.0,
        selection_score=0.5,
        selection_rank=1,
        expected_after_cost_net_r=None,
        source_digest="b" * 64,
        model_digest=None,
        experiment_context={
            "authority_class": "LIVE_PAPER_OPERATIONAL_ONLY",
            "research_evidence": False,
            "economic_claim": False,
            "research_champion": None,
        },
    )


def learned_wire_proposal(*, side: str = "LONG") -> ExecutionProposal:
    return ExecutionProposal.create(
        proposal_id="PROP-V387-LEARNED",
        generated_at_ms=NOW,
        expires_at_ms=NOW + 30_000,
        profile="live-paper",
        market_environment="LIVE",
        evidence_lineage="LIVE_PAPER_OPERATIONAL",
        symbol="BTCUSDT",
        side=side,
        market_event_id="ME-1799999700000",
        data_generation_id="LEARNED-LIVE-PAPER-1799999700000",
        feature_version="CANONICAL_FEATURES_TEST",
        selector_version="SELECTIVE_ML_V2_RIDGE_LIGHTGBM_REALTIME_ENTRY",
        entry_authority=LIVE_PAPER_LEARNED_AUTHORITY,
        exit_policy_version="INTEGER_R_STEP_CONTROL",
        reference_price=100.0,
        selection_score=0.5,
        selection_rank=1,
        expected_after_cost_net_r=0.2,
        source_digest="c" * 64,
        model_digest="d" * 64,
        experiment_context={
            "authority_class": LIVE_PAPER_LEARNED_AUTHORITY,
            "research_evidence": False,
            "economic_claim": False,
            "entry_gate_mode": "EXECUTION_REALTIME_ONLY",
        },
    )


def local_proposal(*, side: str = "LONG") -> EntryProposal:
    return EntryProposal(
        proposal_id="PROP-V387",
        generated_at_ms=NOW,
        expires_at_ms=NOW + 30_000,
        profile="live-paper",
        market_environment="LIVE",
        symbol="BTCUSDT",
        side=side,
        reference_price=100.0,
        entry_authority=LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
        exit_policy_version="INTEGER_R_STEP_CONTROL",
    )


class FakeBase:
    profile_name = "live-paper"

    def __init__(self, proposal=None):
        self.proposal = proposal
        self.contexts = []
        self.health_payload = {
            "protocol_version": "NBOT_V3_EXECUTION_V1",
            "profile": "live-paper",
            "market_environment": "LIVE",
            "evidence_lineage": "LIVE_PAPER_OPERATIONAL",
            "release_sha": SHA,
            "order_authority": "NONE",
            "recommendation_authority": LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
            "status": "READY",
            "reason": None,
        }

    def health(self):
        return dict(self.health_payload)

    def request_proposal(self, **_kwargs):
        return self.proposal

    def record_entry_context(self, **kwargs):
        self.contexts.append(dict(kwargs))

    def send_outcome(self, *, outcome_id, payload):
        return outcome_id

    def record_veto(self, **_kwargs):
        return None


class FakeExchange:
    def quote(self, symbol):
        return Quote(symbol=symbol, bid=100.1, ask=100.2, timestamp_ms=NOW + 100)


class V387LivePaperOperationalCanaryTests(unittest.TestCase):
    def test_authority_is_explicitly_operational_only(self):
        self.assertEqual(
            LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
            "LIVE_PAPER_OPERATIONAL_CANARY_V1",
        )
        proposal = wire_proposal()
        self.assertIsNone(proposal.expected_after_cost_net_r)
        self.assertFalse(proposal.experiment_context["research_evidence"])
        self.assertFalse(proposal.experiment_context["economic_claim"])
        self.assertIsNone(proposal.experiment_context["research_champion"])
        self.assertEqual(proposal.expires_at_ms - proposal.generated_at_ms, 30_000)

    def test_health_accepts_exact_live_authority_and_rejects_other(self):
        health = FakeBase().health()
        _validate_health(health=health, profile_name="live-paper", release_sha=SHA)
        health["recommendation_authority"] = "TESTNET_OPERATIONAL_CANARY_V1"
        with self.assertRaisesRegex(ObservationClientError, "RECOMMENDATION_AUTHORITY"):
            _validate_health(health=health, profile_name="live-paper", release_sha=SHA)

    def test_ready_health_requires_authority(self):
        health = FakeBase().health()
        health["recommendation_authority"] = None
        with self.assertRaisesRegex(ObservationClientError, "READY_AUTHORITY_REQUIRED"):
            _validate_health(health=health, profile_name="live-paper", release_sha=SHA)

    def test_wrapper_captures_execution_quote_before_returning_proposal(self):
        base = FakeBase(local_proposal(side="LONG"))
        client = V38LivePaperOperationalClient(base=base, exchange=FakeExchange())
        result = client.request_proposal(
            profile="live-paper", market_environment="LIVE",
            execution_instance_id="EXEC-1", requested_at_ms=NOW,
        )
        self.assertIs(result, base.proposal)
        self.assertEqual(len(base.contexts), 1)
        context = base.contexts[0]
        self.assertEqual(context["proposal_id"], "PROP-V387")
        self.assertEqual(context["bid"], 100.1)
        self.assertEqual(context["ask"], 100.2)
        self.assertEqual(context["expected_entry_price"], 100.2)

    def test_short_expected_entry_uses_bid(self):
        base = FakeBase(local_proposal(side="SHORT"))
        client = V38LivePaperOperationalClient(base=base, exchange=FakeExchange())
        client.request_proposal(
            profile="live-paper", market_environment="LIVE",
            execution_instance_id="EXEC-1", requested_at_ms=NOW,
        )
        self.assertEqual(base.contexts[0]["expected_entry_price"], 100.1)

    def _client_with_receipt(self, root: Path, *, side: str = "LONG"):
        client = RemoteObservationClient(
            base_url="http://127.0.0.1:18765",
            profile="live-paper",
            auth_token=TOKEN,
            receipt_directory=root / "receipts",
            execution_release_sha=SHA,
        )
        proposal = wire_proposal(side=side)
        client.receipts.record(
            request_id="REQ-V387", proposal=proposal, recorded_at_ms=NOW + 500
        )
        return client, proposal

    @staticmethod
    def _outcome_payload(*, side: str = "LONG"):
        return {
            "outcome_id": "OUT-V387",
            "proposal_id": "PROP-V387",
            "profile": "live-paper",
            "market_environment": "LIVE",
            "symbol": "BTCUSDT",
            "side": side,
            "entry_price": 100.25 if side == "LONG" else 99.75,
            "exit_price": 101.0 if side == "LONG" else 99.0,
            "quantity": 1.0,
            "initial_risk_usd": 10.0,
            "realized_pnl_usd": 0.75,
            "r_multiple": 0.075,
            "mfe_r": 0.2,
            "mae_r": -0.1,
            "entry_timestamp_ms": NOW + 1_000,
            "closed_timestamp_ms": NOW + 61_000,
            "entry_order_id": "PAPER-ENTRY-1",
            "entry_client_order_id": "CID-1",
            "entry_authority": LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
            "exit_policy_version": "INTEGER_R_STEP_CONTROL",
            "final_stop_price": 99.5 if side == "LONG" else 100.5,
            "final_stop_id": "STOP-1",
            "exit_reason": "TEST_CLOSE",
            "close_source": "PAPER",
        }

    def test_live_outcome_requires_preentry_execution_context(self):
        with tempfile.TemporaryDirectory() as td:
            client, _ = self._client_with_receipt(Path(td))
            with self.assertRaisesRegex(ObservationClientError, "ENTRY_CONTEXT_MISSING"):
                client._wire_outcome(
                    outcome_id="OUT-V387", payload=self._outcome_payload()
                )

    def test_live_outcome_embeds_operational_degradation_without_economic_claim(self):
        with tempfile.TemporaryDirectory() as td:
            client, _ = self._client_with_receipt(Path(td))
            client.receipts.record_entry_context(
                proposal_id="PROP-V387",
                observed_at_ms=NOW + 600,
                quote_timestamp_ms=NOW + 550,
                bid=100.1,
                ask=100.2,
                mid=100.15,
                spread_pct=0.09985022466300567,
                expected_entry_price=100.2,
            )
            outcome = client._wire_outcome(
                outcome_id="OUT-V387", payload=self._outcome_payload()
            )
            operational = outcome.experiment_context["execution_operational"]
            self.assertEqual(operational["proposal_receive_latency_ms"], 500)
            self.assertAlmostEqual(operational["execution_mid"], 100.15)
            self.assertGreater(operational["reference_to_actual_fill_deterioration_pct"], 0)
            self.assertIsNone(operational["expected_after_cost_net_r"])
            self.assertIsNone(operational["economic_delta_r"])
            self.assertEqual(operational["actual_paper_r"], 0.075)

    def test_learned_paper_outcome_records_realtime_entry_without_next_bar_context(self):
        with tempfile.TemporaryDirectory() as td:
            client = RemoteObservationClient(
                base_url="http://127.0.0.1:18765",
                profile="live-paper",
                auth_token=TOKEN,
                receipt_directory=Path(td) / "receipts",
                execution_release_sha=SHA,
            )
            proposal = learned_wire_proposal()
            client.receipts.record(
                request_id="REQ-V387-LEARNED",
                proposal=proposal,
                recorded_at_ms=NOW + 400,
            )
            payload = self._outcome_payload()
            payload.update({
                "proposal_id": proposal.proposal_id,
                "entry_authority": LIVE_PAPER_LEARNED_AUTHORITY,
            })
            outcome = client._wire_outcome(
                outcome_id="OUT-V387-LEARNED",
                payload={**payload, "outcome_id": "OUT-V387-LEARNED"},
            )
            entry = outcome.experiment_context["execution_entry"]
            self.assertEqual(entry["mode"], "REALTIME_MARKET_ENTRY")
            self.assertEqual(entry["proposal_receive_latency_ms"], 400)
            self.assertEqual(entry["proposal_to_fill_latency_ms"], 1000)
            self.assertAlmostEqual(entry["reference_to_actual_fill_deterioration_pct"], 0.25)
            self.assertEqual(entry["expected_after_cost_net_r"], 0.2)
            self.assertEqual(entry["actual_paper_r"], 0.075)
            self.assertAlmostEqual(entry["economic_delta_r"], -0.125)
            self.assertNotIn("execution_operational", outcome.experiment_context)

    def test_runtime_source_consumes_one_entry_permission_and_keeps_private_writes_false(self):
        text = (Path(__file__).resolve().parents[1] / "run_execution.py").read_text()
        self.assertIn("attempt_authorized = bool(worker.state.snapshot.entries_enabled)", text)
        self.assertIn("if attempt_authorized:", text)
        self.assertIn("worker.disable_new_entries()", text)
        self.assertIn("ONE_FLAT_ATTEMPT_PER_EXPLICIT_OPERATOR_ENABLE", text)
        self.assertIn('"binance_private_order_writes": False', text)
        self.assertIn("LIVE_PAPER_OPERATIONAL_CANARY", text)


if __name__ == "__main__":
    unittest.main()
