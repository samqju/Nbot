import ast
import json
import math
import unittest
from pathlib import Path

from communication import (
    ExecutionOutcome,
    ExecutionProposal,
    OutcomeAcknowledgement,
    PROTOCOL_VERSION,
    ProtocolValidationError,
    TradeRequest,
    TradeResponse,
)


class Phase6A02CommunicationContractTests(unittest.TestCase):
    NOW = 1_786_179_000_000

    def _proposal(self, **overrides):
        values = {
            "protocol_version": PROTOCOL_VERSION,
            "proposal_id": "PROP-123",
            "generated_at": self.NOW,
            "expires_at": self.NOW + 30_000,
            "environment": "LIVE",
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "pattern": "TREND_CONTINUATION",
            "entry_reference_price": 65_000.0,
            "candidate_score": 0.82,
            "candidate_observation_id": "OBS-1",
            "decision_batch_id": "BATCH-1",
            "market_event_id": "EVENT-1",
            "strategy_version": "STRUCTURE_RULES_V1",
            "strategy_variant_id": "STRUCTURE_CANDIDATE_GENERATOR_V1",
            "model_version": "RULE_SYSTEM_V1",
            "selection_authority": "RULES",
            "structure_fingerprint": {"regime": "TREND"},
            "advisory_risk_plan": {"risk_usd": 10.0},
            "experiment_context": {
                "candle_interval": "5m",
                "nested": {"values": [1, 2, 3]},
            },
            "paper_risk_multiplier": 1.0,
        }
        values.update(overrides)
        return ExecutionProposal(**values)

    def _make_outcome(self, **overrides):
        values = {
            "protocol_version": PROTOCOL_VERSION,
            "outcome_id": "OUT-123",
            "proposal_id": "PROP-123",
            "environment": "LIVE",
            "execution_mode": "SHADOW",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": 65_000.0,
            "exit_price": 65_500.0,
            "quantity": 0.01,
            "realized_pnl_usd": 5.0,
            "initial_risk_usd": 10.0,
            "r_multiple": 0.5,
            "mae_usd": -2.0,
            "mfe_usd": 8.0,
            "mae_r": -0.2,
            "mfe_r": 0.8,
            "entry_timestamp": self.NOW,
            "closed_timestamp": self.NOW + 120_000,
            "holding_seconds": 120,
            "candidate_observation_id": "OBS-1",
            "decision_batch_id": "BATCH-1",
            "market_event_id": "EVENT-1",
            "entry_order_id": "ORDER-1",
            "entry_client_order_id": "nbot-client-1",
            "initial_stop_loss": 64_000.0,
            "final_stop_loss": 65_200.0,
            "exit_reason": "STOP_LOSS",
            "pattern": "TREND_CONTINUATION",
            "strategy_version": "STRUCTURE_RULES_V1",
            "strategy_variant_id": "STRUCTURE_CANDIDATE_GENERATOR_V1",
            "model_version": "RULE_SYSTEM_V1",
            "selection_authority": "RULES",
            "experiment_context": {"paper_policy": {"variant_id": "V1"}},
        }
        values.update(overrides)
        return ExecutionOutcome(**values)

    @staticmethod
    def _json_round_trip(contract):
        encoded = json.dumps(contract.to_dict(), allow_nan=False)
        return json.loads(encoded)

    def test_trade_request_json_round_trip(self):
        request = TradeRequest.create(
            request_id="REQ-1",
            requested_at=self.NOW,
            environment="live",
            execution_mode="shadow",
            previous_proposal_id="PROP-OLD",
            previous_proposal_result="REJECTED",
            previous_rejection_reason="SPREAD_TOO_HIGH",
        )
        restored = TradeRequest.from_dict(self._json_round_trip(request))
        self.assertEqual(restored, request)
        self.assertEqual(restored.execution_state, "FLAT")
        self.assertEqual(restored.environment, "LIVE")

    def test_trade_request_requires_flat_state(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "TRADE_REQUEST_REQUIRES_FLAT",
        ):
            TradeRequest(
                protocol_version=PROTOCOL_VERSION,
                request_id="REQ-1",
                requested_at=self.NOW,
                environment="LIVE",
                execution_mode="SHADOW",
                execution_state="POSITION_OPEN",
            )

    def test_trade_request_feedback_requires_proposal_id(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "PREVIOUS_PROPOSAL_ID_REQUIRED",
        ):
            TradeRequest.create(
                request_id="REQ-1",
                requested_at=self.NOW,
                environment="LIVE",
                execution_mode="SHADOW",
                previous_rejection_reason="SPREAD_TOO_HIGH",
            )

    def test_execution_proposal_json_round_trip(self):
        proposal = self._proposal()
        restored = ExecutionProposal.from_dict(
            self._json_round_trip(proposal)
        )
        self.assertEqual(restored, proposal)
        self.assertEqual(restored.experiment_context["nested"]["values"], [1, 2, 3])

    def test_execution_proposal_expiry_helper(self):
        proposal = self._proposal()
        self.assertFalse(proposal.is_expired(now_ms=proposal.expires_at))
        self.assertTrue(proposal.is_expired(now_ms=proposal.expires_at + 1))

    def test_proposal_rejects_invalid_expiry(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "PROPOSAL_EXPIRY_INVALID",
        ):
            self._proposal(expires_at=self.NOW)

    def test_proposal_rejects_invalid_symbol(self):
        with self.assertRaisesRegex(ProtocolValidationError, "SYMBOL_INVALID"):
            self._proposal(symbol="BTC-USD")

    def test_proposal_rejects_invalid_direction(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "DIRECTION_INVALID",
        ):
            self._proposal(direction="BUY")

    def test_proposal_rejects_invalid_candidate_score(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "CANDIDATE_SCORE_INVALID",
        ):
            self._proposal(candidate_score=1.1)

    def test_proposal_rejects_nan(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "ENTRY_REFERENCE_PRICE_INVALID",
        ):
            self._proposal(entry_reference_price=math.nan)

    def test_proposal_rejects_non_json_experiment_context(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "EXPERIMENT_CONTEXT_NOT_JSON_SAFE",
        ):
            self._proposal(experiment_context={"bad": object()})

    def test_canary_proposal_requires_model_and_allocation(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "PAPER_MODEL_ID_REQUIRED",
        ):
            self._proposal(selection_authority="PAPER_CANARY")

        with self.assertRaisesRegex(
            ProtocolValidationError,
            "PAPER_ALLOCATION_ID_REQUIRED",
        ):
            self._proposal(
                selection_authority="PAPER_CANARY",
                paper_canary_model_id="MODEL-A",
            )

    def test_canary_proposal_accepts_existing_intent_semantics(self):
        proposal = self._proposal(
            selection_authority="paper_canary",
            paper_canary_model_id="MODEL-A",
            paper_allocation_id="CANARY-10",
            paper_risk_multiplier=1.0,
        )
        self.assertEqual(proposal.selection_authority, "PAPER_CANARY")

    def test_model_selected_proposal_requires_normal_risk_multiplier(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "MODEL_RISK_MUST_EQUAL_ONE",
        ):
            self._proposal(
                selection_authority="PAPER_CHAMPION",
                paper_canary_model_id="MODEL-A",
                paper_risk_multiplier=0.5,
            )

    def test_trade_response_proposal_round_trip(self):
        response = TradeResponse.proposal_response(
            request_id="REQ-1",
            responded_at=self.NOW + 1,
            proposal=self._proposal(),
        )
        restored = TradeResponse.from_dict(self._json_round_trip(response))
        self.assertEqual(restored, response)
        self.assertIsInstance(restored.proposal, ExecutionProposal)

    def test_trade_response_no_trade(self):
        response = TradeResponse.no_trade(
            request_id="REQ-1",
            responded_at=self.NOW,
            reason="NO_EXECUTION_ELIGIBLE_CANDIDATE",
        )
        self.assertEqual(response.status, "NO_TRADE")
        self.assertIsNone(response.proposal)

    def test_trade_response_not_ready(self):
        response = TradeResponse.not_ready(
            request_id="REQ-1",
            responded_at=self.NOW,
            reason="OBSERVATION_WARMUP",
        )
        self.assertEqual(response.status, "NOT_READY")
        self.assertIsNone(response.proposal)

    def test_non_proposal_response_cannot_carry_proposal(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "PROPOSAL_NOT_ALLOWED",
        ):
            TradeResponse(
                protocol_version=PROTOCOL_VERSION,
                request_id="REQ-1",
                status="NO_TRADE",
                responded_at=self.NOW,
                proposal=self._proposal(),
            )

    def test_execution_outcome_json_round_trip(self):
        outcome = self._make_outcome()
        restored = ExecutionOutcome.from_dict(self._json_round_trip(outcome))
        self.assertEqual(restored, outcome)

    def test_execution_outcome_allows_degraded_zero_exit_price(self):
        outcome = self._make_outcome(exit_price=0.0, realized_pnl_usd=0.0)
        self.assertEqual(outcome.exit_price, 0.0)

    def test_execution_outcome_rejects_bad_timestamp_order(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "OUTCOME_TIMESTAMP_ORDER_INVALID",
        ):
            self._make_outcome(closed_timestamp=self.NOW - 1)

    def test_outcome_acknowledgement_round_trip(self):
        acknowledgement = OutcomeAcknowledgement.create(
            outcome_id="OUT-1",
            acknowledged_at=self.NOW,
            status="ALREADY_RECORDED",
        )
        restored = OutcomeAcknowledgement.from_dict(
            self._json_round_trip(acknowledgement)
        )
        self.assertEqual(restored, acknowledgement)

    def test_unknown_protocol_version_rejected(self):
        payload = self._proposal().to_dict()
        payload["protocol_version"] = "NBOT_EXECUTION_V999"
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "VERSION_UNSUPPORTED",
        ):
            ExecutionProposal.from_dict(payload)

    def test_invalid_environment_rejected(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "ENVIRONMENT_INVALID",
        ):
            self._proposal(environment="PROD")

    def test_invalid_execution_mode_rejected(self):
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "EXECUTION_MODE_INVALID",
        ):
            self._make_outcome(execution_mode="REAL")

    def test_unknown_payload_fields_rejected(self):
        payload = self._proposal().to_dict()
        payload["unexpected"] = True
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "UNKNOWN_FIELDS",
        ):
            ExecutionProposal.from_dict(payload)

    def test_missing_required_payload_fields_rejected(self):
        payload = self._proposal().to_dict()
        del payload["proposal_id"]
        with self.assertRaisesRegex(
            ProtocolValidationError,
            "MISSING_FIELDS",
        ):
            ExecutionProposal.from_dict(payload)

    def test_communication_layer_has_no_runtime_dependencies(self):
        communication_root = Path(__file__).resolve().parents[1] / "communication"
        forbidden_roots = {
            "config",
            "engine",
            "execution",
            "learning",
            "risk",
            "state",
            "strategy",
        }
        violations = []
        for path in sorted(communication_root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    continue
                bad = roots & forbidden_roots
                if bad:
                    violations.append((path.name, sorted(bad)))
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
