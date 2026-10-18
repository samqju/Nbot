"""Offline NBOT V6 global all-25, all-strategy forecasting selector contracts.

Tests never run a bot and contain only synthetic illustrative forecasts.
This is NOT evidence that any strategy is profitable or trained yet.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from m2r_v6_global_opportunity_ranker import (
    Opportunity, RankPolicy, choose_global_opportunity, FAMILIES,
)

PAIRS=tuple(["BTC/USDT:USDT"]+[f"TEST{i}/USDT:USDT" for i in range(24)])
NOW="2026-09-01T12:00:00Z"

def sample(pair="BTC/USDT:USDT",family="breakout",side="long",pred=.020,
           risk=.010,uncertainty=.004,extra_cost=.002):
    return Opportunity(
        pair=pair,family=family,side=side,regime="trend_up",
        signal_candle_closed_utc="2026-09-01T11:55:00Z",
        prediction_generated_utc="2026-09-01T11:55:00Z",
        model_training_last_feature_utc="2026-08-31T08:00:00Z",
        model_fitted_utc="2026-08-31T12:00:00Z",
        exit_policy="frozen_60m_exit_after_2pct_stop",
        prediction_target="net_return_fraction_after_base_costs",
        predicted_net_return_fraction=pred,
        uncertainty_fraction=uncertainty,
        additional_execution_cost_fraction=extra_cost,
        downside_risk_fraction=risk,
        available_market_depth_usdt=25000,
        intended_stake_usdt=1000,
        has_valid_signal=True,historical_oos_approved=True,
        calibrated_same_target_and_exit=True,
        valid_model_prediction=True,
        historical_market_eligible=True,
        training_label_embargo_verified=True,
    )

def select(records,occupied=False):
    return choose_global_opportunity(records,decision_at_utc=NOW,
        original_25_pairs=PAIRS,portfolio_has_open_position=occupied)

class TestFull25CoinGlobalForecastRanking(unittest.TestCase):
    def test_choose_best_across_coins_directions_and_strategy_families(self):
        a=sample(pred=.014)
        b=sample(pair=PAIRS[1],family="ema_cross",pred=.021)
        c=sample(pair=PAIRS[2],family="donchian_breakout",pred=.018)
        d=select([a,b,c])
        self.assertEqual(d.action,"SELECT")
        self.assertEqual(d.winner,b.identity)
        self.assertEqual(d.candidates_considered,3)
        self.assertEqual(d.eligible_candidates,3)
        self.assertTrue(d.research_only)

    def test_dont_confuse_high_raw_prediction_with_conservative_expected_result(self):
        high_raw=sample(pred=.030,uncertainty=.014,extra_cost=.008,risk=.020)
        safer=sample(pair=PAIRS[1],family="pullback",pred=.016,
                     uncertainty=.002,extra_cost=.001,risk=.004)
        selected=select([high_raw,safer])
        self.assertEqual(selected.winner,safer.identity)

    def test_no_trade_is_a_real_choice_even_when_many_signals_exist(self):
        inputs=[sample(pair=pair, family="macd_momentum",pred=.007,
                       uncertainty=.004,extra_cost=.003,risk=.020)
                for pair in PAIRS]
        out=select(inputs)
        self.assertTrue(out.is_no_trade)
        self.assertEqual(out.eligible_candidates,0)
        self.assertEqual(len(out.rejected_reasons),25)
        self.assertTrue(all(reason=="NO_POSITIVE_RISK_ADJUSTED_EDGE"
                            for _,reason in out.rejected_reasons))

    def test_portfolio_one_open_slot_refuses_all_candidates(self):
        c=sample()
        out=select([c],occupied=True)
        self.assertEqual(out.action,"NO_TRADE")
        self.assertIn("ONE_GLOBAL_SLOT_ALREADY_OCCUPIED",str(out.rejected_reasons))

    def test_reject_unproven_model_exit_mismatch_and_missing_real_world_eligibility(self):
        a=sample()
        variants=[
            replace(a,historical_oos_approved=False),
            replace(a,training_label_embargo_verified=False),
            replace(a,calibrated_same_target_and_exit=False),
            replace(a,exit_policy="trailing_plus_two"),
            replace(a,prediction_target="gross_price_return"),
            replace(a,historical_market_eligible=False),
            replace(a,valid_model_prediction=False),
            replace(a,has_valid_signal=False),
            replace(a,available_market_depth_usdt=4000),
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(select([variant]).is_no_trade)

    def test_reject_future_prediction_or_model_training_after_decision(self):
        c=sample()
        cases=[
            replace(c,prediction_generated_utc="2026-09-01T12:05:00Z"),
            replace(c,model_fitted_utc="2026-09-01T12:05:00Z"),
            replace(c,model_training_last_feature_utc="2026-09-01T11:50:00Z"),
            replace(c,signal_candle_closed_utc="2026-09-01T12:05:00Z"),
            replace(c,prediction_generated_utc="2026-09-01T10:55:00Z"),
            replace(c,model_fitted_utc="2026-08-01T12:00:00Z"),
        ]
        for variant in cases:
            with self.subTest(variant=variant):
                self.assertTrue(select([variant]).is_no_trade)

    def test_unknown_coin_fails_without_changing_25_pair_universe(self):
        self.assertTrue(select([sample(pair="EXTERNAL/USDT:USDT")]).is_no_trade)
        with self.assertRaisesRegex(ValueError,"VERIFIED_FIXED_ORIGINAL_25"):
            choose_global_opportunity([sample()],
                decision_at_utc=NOW,original_25_pairs=PAIRS[:24],
                portfolio_has_open_position=False)

    def test_side_regime_constraints(self):
        self.assertTrue(select([replace(sample(side="short"),regime="trend_up")]).is_no_trade)
        self.assertTrue(select([replace(sample(),regime="high_volatility")]).is_no_trade)
        chosen=select([replace(sample(side="short"),regime="trend_down")])
        self.assertEqual(chosen.winner[2],"short")

    def test_duplicate_opportunity_or_bad_time_fails_closed(self):
        c=sample()
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            select([c,c])
        with self.assertRaisesRegex(ValueError,"SHARED_5M"):
            choose_global_opportunity([c],decision_at_utc="2026-09-01T12:01:00Z",
                original_25_pairs=PAIRS,portfolio_has_open_position=False)
        with self.assertRaisesRegex(ValueError,"UTC_OFFSET"):
            choose_global_opportunity([c],decision_at_utc="2026-09-01T12:00:00",
                original_25_pairs=PAIRS,portfolio_has_open_position=False)

    def test_never_uses_realized_future_profit_and_does_not_allow_model_without_past_evidence(self):
        from m2r_v6_global_opportunity_ranker import Opportunity
        keys=set(Opportunity.__dataclass_fields__)
        self.assertNotIn("actual_future_return",keys)
        self.assertNotIn("realized_trade_profit",keys)
        self.assertNotIn("forward_best_price",keys)
        self.assertEqual(len(FAMILIES),10)
        self.assertTrue(select([replace(sample(),historical_oos_approved=False)]).is_no_trade)


if __name__=="__main__":
    unittest.main()
