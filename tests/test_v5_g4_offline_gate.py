"""G4 fake-input-only tests. Zero database writes, network calls or trades."""
import copy
import unittest

from nbot.v5.g4_offline_gate import (
    CONTRACT_VERSION, DEFAULT_HORIZON_MS, assess_replay_prerequisites,
)
from nbot.v5.observation_contract import PATTERN_IDS

EVENT = 1_800_000_000_000
DECISION = EVENT + 301_000
MATURITY = DECISION + DEFAULT_HORIZON_MS
SHA = lambda c: c * 64


def fixtures():
    candidate = {
        "decision_id": SHA("a"), "event_open_ms": EVENT,
        "decision_at_ms": DECISION, "symbol": "BTCUSDT", "side": "LONG",
        "status": "OBSERVED", "reason_codes": [], "action": "OBSERVE_ONLY",
        "order_authority": "NONE", "source_digest": SHA("b"),
        "btc_source_digest": SHA("c"), "detector_version": "FROZEN_DETECTOR_V1",
        "patterns": {p: "NO_MATCH" for p in PATTERN_IDS},
    }
    candidate["patterns"][PATTERN_IDS[0]] = "MATCH"
    g3 = {"event_open_ms": EVENT, "valid_from_ms": DECISION,
          "feature_sha256": SHA("d")}
    policy = {
        "horizon_ms": DEFAULT_HORIZON_MS, "declared_at_ms": DECISION,
        "policy_sha256": SHA("e"), "entry_convention": "FROZEN_ASK_AT_ENTRY",
        "exit_policy_id": "PREDECLARED_4H_V1", "risk_policy_id": "RISK_V1",
    }
    path = {
        "grade": "HISTORICAL_AGGTRADE_PATH", "path_sha256": SHA("f"),
        "start_ms": DECISION, "end_ms": MATURITY,
        "captured_at_ms": MATURITY + 100, "continuous": True,
        "source_verified": True,
    }
    costs = {
        "quote_sha256": SHA("1"), "fee_schedule_sha256": SHA("2"),
        "slippage_model_sha256": SHA("3"), "funding_sha256": SHA("4"),
        "coverage_end_ms": MATURITY, "source_verified": True,
    }
    return candidate, g3, policy, path, costs


def run(*, at=MATURITY + 5_000, change=None):
    candidate, g3, policy, path, cost = fixtures()
    if change:
        change(candidate, g3, policy, path, cost)
    return assess_replay_prerequisites(
        candidate=candidate, g3_context=g3, frozen_policy=policy,
        path_witness=path, cost_witness=cost, audit_at_ms=at,
    )


class G4OfflineOnlyGateTests(unittest.TestCase):
    def test_complete_witness_provides_replay_ready_not_scored(self):
        result = run()
        self.assertEqual(result.state, "REPLAY_READY")
        self.assertEqual(result.evidence_grade, "HISTORICAL_AGGTRADE_PATH")
        self.assertEqual(result.contract_version, CONTRACT_VERSION)
        self.assertEqual(result.scored_outcomes, 0)
        self.assertEqual(result.order_authority, "NONE")
        self.assertEqual(result.recommendation_authority, "NONE")
        self.assertEqual(result.training_authority, "NONE")

    def test_horizon_not_yet_mature_does_not_use_future_path(self):
        result = run(at=MATURITY - 1)
        self.assertEqual(result.state, "PENDING")
        self.assertEqual(result.reasons, ("G4_HORIZON_NOT_MATURE",))

    def test_no_future_path_after_maturity_is_hold_not_loss(self):
        c, g, p, _, _ = fixtures()
        result = assess_replay_prerequisites(
            candidate=c, g3_context=g, frozen_policy=p,
            path_witness=None, cost_witness=None, audit_at_ms=MATURITY)
        self.assertEqual(result.state, "HOLD")
        self.assertIn("G4_PATH_MISSING_AFTER_MATURITY", result.reasons)

    def test_unscorable_candidate_never_replays(self):
        result = run(change=lambda c,g,p,pa,co:c.update(status="UNSCORABLE"))
        self.assertIn("G4_CANDIDATE_NOT_SOURCE_QUALIFIED", result.reasons)

    def test_source_digest_required(self):
        result = run(change=lambda c,g,p,pa,co:c.update(source_digest=None))
        self.assertEqual(result.state, "HOLD")
        self.assertIn("G4_CANDIDATE_SOURCE_DIGEST_MISSING", result.reasons)

    def test_missing_pattern_is_not_a_valid_full_denominator(self):
        result = run(change=lambda c,g,p,pa,co:c["patterns"].pop(PATTERN_IDS[-1]))
        self.assertIn("G4_PATTERN_DENOMINATOR_UNQUALIFIED", result.reasons)

    def test_unavailable_pattern_is_not_scored_as_no_match(self):
        result = run(change=lambda c,g,p,pa,co:c["patterns"].update({PATTERN_IDS[-1]:"UNAVAILABLE"}))
        self.assertIn("G4_PATTERN_DENOMINATOR_UNQUALIFIED", result.reasons)

    def test_g3_feature_from_future_is_rejected(self):
        result = run(change=lambda c,g,p,pa,co:g.update(valid_from_ms=DECISION+1))
        self.assertIn("G4_G3_CONTEXT_FUTURE_OR_UNKNOWN", result.reasons)

    def test_g3_wrong_event_is_rejected(self):
        result = run(change=lambda c,g,p,pa,co:g.update(event_open_ms=EVENT+300000))
        self.assertIn("G4_G3_CONTEXT_NOT_MATCHED", result.reasons)

    def test_unfrozen_policy_is_rejected(self):
        result = run(change=lambda c,g,p,pa,co:p.update(declared_at_ms=DECISION+1))
        self.assertIn("G4_POLICY_NOT_FROZEN_ASOF_DECISION", result.reasons)

    def test_exit_risk_policy_must_be_explicit(self):
        result = run(change=lambda c,g,p,pa,co:p.update(exit_policy_id=""))
        self.assertIn("G4_EXIT_ENTRY_RISK_POLICY_INCOMPLETE", result.reasons)

    def test_path_gaps_cannot_generate_profit_or_loss(self):
        result = run(change=lambda c,g,p,pa,co:pa.update(continuous=False))
        self.assertIn("G4_PATH_GAPPED_OR_UNPROVEN", result.reasons)

    def test_path_must_cover_full_maturation_horizon(self):
        result = run(change=lambda c,g,p,pa,co:pa.update(end_ms=MATURITY-1))
        self.assertIn("G4_PATH_CLOCK_OR_COVERAGE_INVALID", result.reasons)

    def test_future_capture_at_audit_clock_fails_closed(self):
        result = run(change=lambda c,g,p,pa,co:pa.update(captured_at_ms=MATURITY+30_000))
        self.assertIn("G4_PATH_CLOCK_OR_COVERAGE_INVALID", result.reasons)

    def test_unsupported_forward_paper_grade_not_research(self):
        result = run(change=lambda c,g,p,pa,co:pa.update(grade="FORWARD_PAPER"))
        self.assertEqual(result.state, "HOLD")
        self.assertIn("G4_UNSUPPORTED_PATH_GRADE", result.reasons)

    def test_quote_grade_requires_all_cost_and_funding_witnesses(self):
        result = run(change=lambda c,g,p,pa,co:(pa.update(grade="QUOTE_CONSTRAINED_SIMULATION"),
                                                    co.update(funding_sha256=None)))
        self.assertEqual(result.state, "HOLD")
        self.assertIn("G4_EXECUTABLE_FUNDING_SHA256_MISSING", result.reasons)

    def test_quote_grade_with_verified_costs_is_only_ready_for_replay(self):
        result = run(change=lambda c,g,p,pa,co:pa.update(grade="QUOTE_CONSTRAINED_SIMULATION"))
        self.assertEqual(result.state, "REPLAY_READY")
        self.assertEqual(result.scored_outcomes, 0)

    def test_quote_grade_rejects_missing_coverage(self):
        result = run(change=lambda c,g,p,pa,co:(pa.update(grade="QUOTE_CONSTRAINED_SIMULATION"),
                                                    co.update(coverage_end_ms=MATURITY-1)))
        self.assertIn("G4_COST_HORIZON_NOT_VERIFIED", result.reasons)

    def test_short_side_and_overlapping_pattern_tags_count_as_one_candidate(self):
        def transform(c,g,p,pa,co):
            c["side"]="SHORT"
            c["patterns"][PATTERN_IDS[5]]="MATCH"
        result=run(change=transform)
        self.assertEqual(result.state,"REPLAY_READY")
        self.assertEqual(result.scored_outcomes,0)

    def test_deterministic_pure_gate(self):
        a=run()
        b=run()
        self.assertEqual(a,b)

    def test_invalid_boolean_audit_clock_rejected(self):
        c,g,p,path,cost=fixtures()
        with self.assertRaisesRegex(ValueError,"G4_INVALID_AUDIT_CLOCK"):
            assess_replay_prerequisites(candidate=c,g3_context=g,
                frozen_policy=p,path_witness=path,cost_witness=cost,audit_at_ms=True)


if __name__ == "__main__":
    unittest.main()
