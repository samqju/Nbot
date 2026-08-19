from __future__ import annotations

from pathlib import Path
import unittest

from nbot.communication import (
    ExecutionOutcome,
    ExecutionProposal,
    OutcomeAcknowledgement,
    PROTOCOL_VERSION,
    ProtocolValidationError,
    TradeRequest,
    TradeResponse,
)


SHA = "a" * 40
DIGEST = "b" * 64
NOW = 1_800_000_000_000


def proposal(**overrides):
    values = dict(
        proposal_id="PROP-1",
        generated_at_ms=NOW,
        expires_at_ms=NOW + 30_000,
        profile="testnet-trade",
        market_environment="TESTNET",
        evidence_lineage="TESTNET_OPERATIONAL_ONLY",
        symbol="BTCUSDT",
        side="LONG",
        market_event_id="ME-1799999700000",
        data_generation_id="DG-1",
        feature_version="FEATURE-V1",
        selector_version="SELECTOR-V1",
        entry_authority="TESTNET_OPERATIONAL_CANARY_V1",
        exit_policy_version="INTEGER_R_STEP_CONTROL",
        reference_price=100.0,
        selection_score=0.25,
        selection_rank=1,
        expected_after_cost_net_r=None,
        source_digest=DIGEST,
        model_digest=None,
        experiment_context={"research_evidence": False},
    )
    values.update(overrides)
    return ExecutionProposal.create(**values)


def outcome(**overrides):
    values = dict(
        outcome_id="OUT-1",
        proposal_id="PROP-1",
        request_id="REQ-1",
        profile="testnet-trade",
        market_environment="TESTNET",
        execution_mode="TRADE",
        evidence_lineage="TESTNET_OPERATIONAL_ONLY",
        symbol="BTCUSDT",
        side="LONG",
        market_event_id="ME-1799999700000",
        feature_version="FEATURE-V1",
        selector_version="SELECTOR-V1",
        entry_authority="TESTNET_OPERATIONAL_CANARY_V1",
        exit_policy_version="INTEGER_R_STEP_CONTROL",
        reference_price=100.0,
        selection_score=0.25,
        selection_rank=1,
        expected_after_cost_net_r=None,
        proposal_source_digest=DIGEST,
        proposal_model_digest=None,
        entry_price=100.0,
        exit_price=101.0,
        quantity=1.0,
        initial_risk_usd=10.0,
        realized_pnl_usd=1.0,
        r_multiple=0.1,
        mae_usd=-2.0,
        mfe_usd=5.0,
        mae_r=-0.2,
        mfe_r=0.5,
        entry_timestamp_ms=NOW,
        closed_timestamp_ms=NOW + 60_000,
        holding_seconds=60,
        exit_reason="TEST",
        close_source="TEST",
        execution_payload_digest="c" * 64,
        entry_order_id="ORDER-1",
        entry_client_order_id="CID-1",
        final_stop_price=100.5,
        final_stop_id="STOP-1",
        experiment_context={"research_evidence": False},
    )
    values.update(overrides)
    return ExecutionOutcome.create(**values)


class V35ContractTests(unittest.TestCase):
    def test_trade_request_roundtrip_and_feedback(self):
        request = TradeRequest.create(
            request_id="REQ-1",
            requested_at_ms=NOW,
            profile="testnet-trade",
            market_environment="TESTNET",
            execution_mode="TRADE",
            execution_state="FLAT",
            execution_instance_id="EXEC-1",
            execution_release_sha=SHA,
            previous_proposal_id="PROP-OLD",
            previous_proposal_result="REJECTED",
            previous_rejection_reason="SPREAD_TOO_WIDE",
        )
        self.assertEqual(TradeRequest.from_dict(request.to_dict()), request)
        self.assertEqual(request.protocol_version, PROTOCOL_VERSION)

    def test_request_rejects_profile_environment_mismatch(self):
        with self.assertRaisesRegex(ProtocolValidationError, "PROFILE_ENVIRONMENT_MISMATCH"):
            TradeRequest.create(
                request_id="REQ-1",
                requested_at_ms=NOW,
                profile="live-paper",
                market_environment="TESTNET",
                execution_mode="PAPER",
                execution_state="FLAT",
                execution_instance_id="EXEC-1",
                execution_release_sha=SHA,
            )

    def test_request_rejects_incomplete_veto_feedback(self):
        with self.assertRaisesRegex(ProtocolValidationError, "FEEDBACK_INCOMPLETE"):
            TradeRequest.create(
                request_id="REQ-1",
                requested_at_ms=NOW,
                profile="testnet-trade",
                market_environment="TESTNET",
                execution_mode="TRADE",
                execution_state="FLAT",
                execution_instance_id="EXEC-1",
                execution_release_sha=SHA,
                previous_proposal_id="PROP-1",
            )

    def test_proposal_roundtrip_and_expiry(self):
        item = proposal()
        self.assertEqual(ExecutionProposal.from_dict(item.to_dict()), item)
        self.assertFalse(item.is_expired(now_ms=NOW + 29_999))
        self.assertTrue(item.is_expired(now_ms=NOW + 30_001))

    def test_proposal_rejects_unknown_field(self):
        payload = proposal().to_dict()
        payload["quantity"] = 1.0
        with self.assertRaisesRegex(ProtocolValidationError, "UNKNOWN_FIELDS"):
            ExecutionProposal.from_dict(payload)

    def test_trade_response_shapes_are_strict(self):
        item = proposal()
        proposed = TradeResponse.proposal_response(
            request_id="REQ-1",
            responded_at_ms=NOW,
            proposal=item,
        )
        self.assertEqual(TradeResponse.from_dict(proposed.to_dict()), proposed)
        self.assertEqual(
            TradeResponse.no_trade(
                request_id="REQ-2", responded_at_ms=NOW, reason="NONE"
            ).status,
            "NO_TRADE",
        )
        self.assertEqual(
            TradeResponse.not_ready(
                request_id="REQ-3", responded_at_ms=NOW, reason="WARMING"
            ).status,
            "NOT_READY",
        )

    def test_outcome_roundtrip_preserves_optional_excursion_truth(self):
        item = outcome(mae_usd=None, mfe_usd=None, mae_r=None, mfe_r=None)
        self.assertEqual(ExecutionOutcome.from_dict(item.to_dict()), item)

    def test_outcome_rejects_holding_time_inconsistency(self):
        with self.assertRaisesRegex(ProtocolValidationError, "HOLDING_SECONDS_MISMATCH"):
            outcome(holding_seconds=58)

    def test_ack_roundtrip(self):
        ack = OutcomeAcknowledgement.create(
            outcome_id="OUT-1",
            status="RECORDED",
            recorded_at_ms=NOW,
            observation_store_id="OBS-1",
        )
        self.assertEqual(OutcomeAcknowledgement.from_dict(ack.to_dict()), ack)


    def test_frozen_protocol_document_matches_v35_authority_boundary(self):
        repo = Path(__file__).resolve().parents[2]
        text = (repo / "docs/PROTOCOL_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("NBOT_V3_EXECUTION_V1", text)
        self.assertIn("TESTNET_OPERATIONAL_CANARY_V1", text)
        self.assertIn("live-paper", text)
        self.assertIn("NOT_READY", text)
        self.assertIn("open-position hot path", text)

    def test_live_trade_contract_is_parseable_but_not_granted_authority(self):
        # Wire validation knows the profile contract.  V3.5 runtime/client code
        # separately forbids LIVE real-capital use before V3.10.
        request = TradeRequest.create(
            request_id="REQ-REAL",
            requested_at_ms=NOW,
            profile="live-trade",
            market_environment="LIVE",
            execution_mode="TRADE",
            execution_state="FLAT",
            execution_instance_id="EXEC-1",
            execution_release_sha=SHA,
        )
        self.assertEqual(request.profile, "live-trade")
