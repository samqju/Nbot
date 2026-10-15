"""Synthetic-only quote-constrained economic contract tests; no actual trades."""
import unittest

from nbot.v5.g4_economics import assess_quote_constrained_net
from nbot.v5.g4_price_path import replay_aggtrade_price_path
from tests.test_v5_g4_price_path import DECISION, MATURITY, make

SHA="f"*64


def fake():
    c,p,rows,m=make()
    path=replay_aggtrade_price_path(candidate=c,policy=p,original_rows=rows,
                                   source_manifest=m,audit_at_ms=MATURITY+1)
    entry={"symbol":"BTCUSDT","sampled_at_ms":DECISION-250,
           "receipt_sha256":SHA,"source_verified":True,"bid":"99.95","ask":"100.05"}
    exit_={"symbol":"BTCUSDT","sampled_at_ms":path.exit_at_ms+100,
           "receipt_sha256":SHA,"source_verified":True,"bid":"109.90","ask":"110.10"}
    eco={"source_grade":"ORIGINAL_QUOTE_FEE_FUNDING_WITNESSES",
         "quote_source_sha256":SHA,"fee_source_sha256":SHA,
         "slippage_policy_sha256":SHA,"funding_source_sha256":SHA,
         "independently_source_verified":True, "max_quote_age_ms":1000,
         "taker_fee_rate":"0.0005","slippage_rate":"0.0001",
         "funding_quote_per_unit":"0.01",
         "funding_coverage_through_ms":MATURITY}
    return path,c,p,entry,exit_,eco


def run(change=None):
    path,c,p,entry,exit_,eco=fake()
    if change:
        replacements=change(path,c,p,entry,exit_,eco)
        if replacements is not None:
            path=replacements
    return assess_quote_constrained_net(path=path,candidate=c,policy=p,
        entry_quote=entry,exit_quote=exit_,economic_witness=eco,
        audit_at_ms=MATURITY+10)


class G4EconomicTests(unittest.TestCase):
    def test_after_cost_scenario_is_not_exchange_fill(self):
        result=run()
        self.assertEqual(result.state,"COST_REPLAYED")
        self.assertEqual(result.source_grade,"QUOTE_CONSTRAINED_SIMULATION")
        self.assertEqual(result.filled_orders,0)
        self.assertEqual(result.financial_authority,"NONE")
        self.assertLess(float(result.modeled_net_r),float(result.modeled_gross_r))
        self.assertIsNotNone(result.modeled_funding_quote)

    def test_identical_inputs_are_deterministic(self):
        self.assertEqual(run(),run())

    def test_net_r_uses_frozen_risk_unit_and_exact_side_correct_costs(self):
        from decimal import Decimal,localcontext
        result=run()
        with localcontext() as ctx:
            ctx.prec=34
            entry=Decimal("100.05")*Decimal("1.0001")
            exit_=Decimal("109.90")*Decimal("0.9999")
            expected=(exit_-entry-Decimal("0.0005")*(entry+exit_)-Decimal("0.01"))/Decimal("5")
        self.assertEqual(Decimal(result.modeled_net_r),expected)

    def test_missing_entry_quote_is_hold(self):
        self.assertIn("ENTRY_ORIGINAL_QUOTE_INVALID",
                      run(lambda pa,c,p,e,x,w:e.update(receipt_sha256=None)).reasons)

    def test_future_entry_quote_is_hold(self):
        self.assertIn("ENTRY_ORIGINAL_QUOTE_INVALID",
                      run(lambda pa,c,p,e,x,w:e.update(sampled_at_ms=DECISION+1)).reasons)

    def test_stale_entry_quote_is_hold(self):
        self.assertIn("ENTRY_ORIGINAL_QUOTE_INVALID",
                      run(lambda pa,c,p,e,x,w:e.update(sampled_at_ms=DECISION-9000)).reasons)

    def test_future_or_stale_exit_quote_is_hold(self):
        self.assertIn("EXIT_ORIGINAL_QUOTE_INVALID",
                      run(lambda pa,c,p,e,x,w:x.update(sampled_at_ms=pa.exit_at_ms+5000)).reasons)

    def test_crossed_quote_is_hold(self):
        self.assertIn("ENTRY_ORIGINAL_QUOTE_INVALID",
                      run(lambda pa,c,p,e,x,w:e.update(bid="110",ask="100")).reasons)

    def test_missing_fee_receipt_is_hold(self):
        self.assertIn("FEE_SOURCE_SHA256_MISSING",
                      run(lambda pa,c,p,e,x,w:w.update(fee_source_sha256=None)).reasons)

    def test_missing_slippage_policy_is_hold(self):
        self.assertIn("SLIPPAGE_POLICY_SHA256_MISSING",
                      run(lambda pa,c,p,e,x,w:w.update(slippage_policy_sha256=None)).reasons)

    def test_missing_funding_cannot_be_defaulted_zero(self):
        self.assertIn("MODELED_FEE_SLIPPAGE_FUNDING_RISK_INVALID",
                      run(lambda pa,c,p,e,x,w:w.update(funding_quote_per_unit=None)).reasons)

    def test_funding_coverage_is_horizon_specific(self):
        self.assertIn("FUNDING_INTERVALS_NOT_COVERED",
                      run(lambda pa,c,p,e,x,w:w.update(funding_coverage_through_ms=DECISION)).reasons)

    def test_unverified_economic_sources_hold(self):
        self.assertIn("ECONOMIC_SOURCE_NOT_INDEPENDENTLY_VERIFIED",
                      run(lambda pa,c,p,e,x,w:w.update(independently_source_verified=False)).reasons)

    def test_zero_fees_allowed_only_with_explicit_source_witness(self):
        x=run(lambda pa,c,p,e,x,w:w.update(taker_fee_rate="0",
               slippage_rate="0",funding_quote_per_unit="0"))
        self.assertEqual(x.state,"COST_REPLAYED")
        self.assertEqual(x.modeled_fee_quote,"0.00")

    def test_negative_signed_funding_credit_is_accounted(self):
        paid=run()
        credit=run(lambda pa,c,p,e,x,w:w.update(funding_quote_per_unit="-0.01"))
        self.assertGreater(float(credit.modeled_net_r),float(paid.modeled_net_r))

    def test_wrong_symbol_quote_rejected(self):
        self.assertIn("EXIT_ORIGINAL_QUOTE_INVALID",
                      run(lambda pa,c,p,e,x,w:x.update(symbol="ETHUSDT")).reasons)

    def test_bad_canonical_fee_bounds_fail(self):
        self.assertIn("MODELED_FEE_SLIPPAGE_FUNDING_RISK_INVALID",
                      run(lambda pa,c,p,e,x,w:w.update(taker_fee_rate="0.02")).reasons)

    def test_no_source_price_path_means_no_economics(self):
        from dataclasses import replace
        def edit(pa,c,p,e,x,w):
            return replace(pa,state="HOLD",gross_path_r=None)
        self.assertIn("PRICE_PATH_NOT_INDEPENDENTLY_REPLAYED",run(edit).reasons)

    def test_negative_or_missing_risk_geometry_holds(self):
        self.assertIn("MODELED_RISK_GEOMETRY_INVALID",
                      run(lambda pa,c,p,e,x,w:p.update(stop_price="130")).reasons)


if __name__=="__main__":
    unittest.main()
