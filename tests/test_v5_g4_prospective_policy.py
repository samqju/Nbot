"""Predeclared G4 virtual-research geometry: strict no-future synthetic cases."""
import copy
import unittest

from nbot.v5.g4_prospective_policy import (
    freeze_template,bind_at_decision,TEMPLATE_VERSION,
    ENTRY_CONVENTION,EXIT_POLICY_ID,RISK_POLICY_ID,COST_POLICY_ID,
)

EVENT=1800000000000
DECISION=EVENT+301000

def fixture():
    policy={
        "declared_at_ms":EVENT-600000,
        "activates_at_ms":EVENT-300000,
        "horizon_ms":4*3600000,
        "max_quote_age_ms":1000,
        "atr_risk_multiple":"1.5",
        "target_r_multiple":"2.0",
        "min_risk_fraction":"0.005",
        "entry_convention":ENTRY_CONVENTION,
        "exit_policy_id":EXIT_POLICY_ID,
        "risk_policy_id":RISK_POLICY_ID,
        "cost_policy_id":COST_POLICY_ID,
        "research_authority":"OBSERVE_ONLY"}
    candidate={
        "decision_id":"a"*64,"status":"OBSERVED","reason_codes":[],
        "order_authority":"NONE","event_open_ms":EVENT,
        "decision_at_ms":DECISION,"symbol":"BTCUSDT",
        "side":"LONG","source_digest":"b"*64}
    g3={"state":"AVAILABLE","reasons":[],
        "valid_from_ms":DECISION,"feature_sha256":"d"*64,
        "atr14_fraction":"0.01"}
    quote={"symbol":"BTCUSDT","sampled_at_ms":DECISION-200,
           "source_verified":True,"receipt_sha256":"c"*64,
           "bid":"100.0","ask":"100.1"}
    return policy,candidate,g3,quote

def run(change=None):
    p,c,g,q=fixture()
    if change:change(p,c,g,q)
    return bind_at_decision(template=freeze_template(p),
                            candidate=c,g3_coin=g,quote=q)


class ProspectivePolicyTests(unittest.TestCase):
    def test_long_geometry_is_causal_predefined_and_not_a_fill(self):
        p,c,g,q=fixture()
        t=freeze_template(p)
        x=bind_at_decision(template=t,candidate=c,g3_coin=g,quote=q)
        self.assertEqual(x.state,"GEOMETRY_RECORDED")
        self.assertEqual(x.frozen_policy["entry_reference_price"],"100.1")
        self.assertEqual(x.frozen_policy["stop_price"],"98.5985")
        self.assertEqual(x.frozen_policy["target_price"],"103.10300")
        self.assertEqual(x.frozen_policy["declared_at_ms"],DECISION)
        self.assertEqual(x.scored_outcomes,0)
        self.assertEqual(x.order_authority,"NONE")
        self.assertEqual(x.training_authority,"NONE")

    def test_short_geometry_side_correct_no_fill(self):
        x=run(lambda p,c,g,q:c.update(side="SHORT"))
        self.assertEqual(x.state,"GEOMETRY_RECORDED")
        self.assertEqual(x.frozen_policy["entry_reference_price"],"100.0")
        self.assertEqual(x.frozen_policy["stop_price"],"101.5000")
        self.assertEqual(x.frozen_policy["target_price"],"97.00000")

    def test_repeated_identical_inputs_produce_identical_sha(self):
        self.assertEqual(run(),run())
        self.assertEqual(freeze_template(fixture()[0]),
                         freeze_template(fixture()[0]))

    def test_template_activation_must_precede_event_open(self):
        x=run(lambda p,c,g,q:p.update(activates_at_ms=EVENT+300000))
        self.assertEqual(x.state,"HOLD")
        self.assertIn("CANDIDATE_BEFORE_POLICY_ACTIVATION_OR_EVENT_FINAL",x.reasons)

    def test_cannot_change_template_after_five_minute_start(self):
        x=run(lambda p,c,g,q:p.update(activates_at_ms=EVENT+600000,
                                       declared_at_ms=EVENT+300000))
        self.assertEqual(x.state,"HOLD")
        self.assertIn("CANDIDATE_BEFORE_POLICY_ACTIVATION_OR_EVENT_FINAL",x.reasons)

    def test_wrong_policy_authority_rejected(self):
        p,_,_,_=fixture()
        p["research_authority"]="BINANCE_TRADING"
        with self.assertRaisesRegex(ValueError,"G4_RISK_TEMPLATE_AUTHORITY_OR_RULES_INVALID"):
            freeze_template(p)

    def test_hindsight_future_quote_is_not_entry(self):
        x=run(lambda p,c,g,q:q.update(sampled_at_ms=DECISION+1))
        self.assertIn("ENTRY_QUOTE_STALE_FUTURE_OR_UNPROVEN",x.reasons)
        self.assertIsNone(x.frozen_policy)

    def test_old_quote_not_source(self):
        x=run(lambda p,c,g,q:q.update(sampled_at_ms=DECISION-6000))
        self.assertIn("ENTRY_QUOTE_STALE_FUTURE_OR_UNPROVEN",x.reasons)

    def test_quote_without_source_hash_never_binds_geometry(self):
        x=run(lambda p,c,g,q:q.update(receipt_sha256=None))
        self.assertIn("ENTRY_QUOTE_STALE_FUTURE_OR_UNPROVEN",x.reasons)

    def test_future_g3_features_not_accepted(self):
        x=run(lambda p,c,g,q:g.update(valid_from_ms=DECISION+100))
        self.assertIn("G3_FEATURE_NOT_CAUSAL",x.reasons)

    def test_held_candidate_no_synthetic_geometry(self):
        x=run(lambda p,c,g,q:c.update(status="UNSCORABLE",
                                       reason_codes=["MARKET_QUOTE_HOLD"]))
        self.assertIn("CANDIDATE_SOURCE_OR_IDENTITY_UNQUALIFIED",x.reasons)

    def test_no_btc_market_validity_means_hold(self):
        x=run(lambda p,c,g,q:g.update(state="UNKNOWN",
                                       atr14_fraction=None))
        self.assertIn("G3_FEATURE_NOT_CAUSAL",x.reasons)
        self.assertIn("ATR_NOT_SOURCE_QUALIFIED",x.reasons)

    def test_crossed_or_extreme_spread_rejected(self):
        x=run(lambda p,c,g,q:q.update(bid="110",ask="100"))
        self.assertIn("ENTRY_QUOTE_INVALID",x.reasons)
        x=run(lambda p,c,g,q:q.update(bid="90",ask="100"))
        self.assertEqual(x.reasons,("ENTRY_SPREAD_TOO_LARGE",))

    def test_unverified_nan_atr_blocks_geometry(self):
        x=run(lambda p,c,g,q:g.update(atr14_fraction="NaN"))
        self.assertIn("ATR_NOT_SOURCE_QUALIFIED",x.reasons)

    def test_invalid_template_horizon_and_numeric_no_hindsight(self):
        p,_,_,_=fixture()
        p["horizon_ms"]=599999
        with self.assertRaisesRegex(ValueError,"G4_RISK_TEMPLATE_FUTURE_OR_HORIZON_INVALID"):
            freeze_template(p)
        p,_,_,_=fixture()
        p["target_r_multiple"]="NaN"
        with self.assertRaisesRegex(ValueError,"G4_RISK_TEMPLATE_NUMERIC_INVALID"):
            freeze_template(p)

    def test_binding_does_not_modify_input(self):
        p,c,g,q=fixture()
        before=copy.deepcopy((p,c,g,q))
        run()
        self.assertEqual((p,c,g,q),before)

    def test_template_requires_all_authority_cost_and_exit_fields(self):
        p,_,_,_=fixture()
        del p["cost_policy_id"]
        with self.assertRaisesRegex(ValueError,"G4_RISK_TEMPLATE_SHAPE_INVALID"):
            freeze_template(p)


if __name__=="__main__":
    unittest.main()
