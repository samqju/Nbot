"""Pure offline checks: after-cost opportunity learning + router + model locks.

These do not prove FreqAI backtests, realistic exchange fills or a trading edge.
"""
from __future__ import annotations
import json
import sys
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"user_data"/"strategies"))
if "freqtrade.strategy" not in sys.modules:
    sys.modules["freqtrade"] = types.ModuleType("freqtrade")
    ft = types.ModuleType("freqtrade.strategy")
    ft.IStrategy = type("IStrategy", (), {})
    sys.modules["freqtrade.strategy"] = ft

from nbot_trade_outcome import (
    CostPolicy, KINDS, setups, outcome, opportunity_table,
    training_labels, decision_features, priority_kind
)
from nbot_strategy_router import CandidateScore, choose_candidate
from NbotV6TradeOutcomeResearch import NbotV6TradeOutcomeResearch


def candles(n=120, drift=0.002):
    x=100*np.exp(np.arange(n)*drift)
    return pd.DataFrame({
        "date":pd.date_range("2026-07-01",periods=n,freq="5min",tz="UTC"),
        "open":x, "high":x*1.001, "low":x*.999,
        "close":x,"volume":np.full(n,100.0),
    })


def flat(n=100):
    return pd.DataFrame({
        "open":np.full(n,100.0), "high":np.full(n,100.5),
        "low":np.full(n,99.5), "close":np.full(n,100.0),
        "volume":np.full(n,50.0)
    })


class M2ResearchLearningTests(unittest.TestCase):
    def test_setup_breakout_uses_prior_completed_high(self):
        frame=candles()
        flags=setups(frame)
        self.assertTrue(flags["breakout_long"].iloc[90])
        self.assertFalse(flags["breakout_long"].iloc[10])
        altered=frame.copy()
        altered.loc[110:,"high"]=1e8
        pd.testing.assert_frame_equal(flags.iloc[:110],setups(altered).iloc[:110])

    def test_keep_rejected_opportunities_and_no_future_tail_label(self):
        frame=candles()
        table=opportunity_table(frame)
        self.assertGreater(len(table), 25)
        self.assertIn("candidate",table)
        self.assertIn("net_return",table)
        self.assertTrue((table["entry_index"]>table["decision_index"]).all())
        self.assertTrue((table["exit_index"]<=table["decision_index"]+12).all())
        labels=training_labels(frame)["&-trade_net_return"]
        self.assertTrue(labels.tail(12).isna().all())
        self.assertTrue(labels.notna().sum()>0)

    def test_next_open_is_entry_and_cost_penalty_always_applied(self):
        frame=flat()
        frame.loc[61,"open"]=110
        frame.loc[61,"high"]=111
        frame.loc[61,"low"]=109
        frame.loc[61,"close"]=110
        frame.loc[62:72,["open","high","low","close"]]=[110,110.5,109.5,110]
        got=outcome(frame,60,1)
        self.assertIsNotNone(got)
        self.assertEqual(got["exit_reason"],"time")
        self.assertAlmostEqual(got["net_return"],-CostPolicy().cost_roundtrip)

    def test_stop_wins_if_same_bar_hits_both_limits(self):
        df=flat()
        df.loc[61,["open","high","low","close"]]=[100,106,97,100]
        result=outcome(df,60,1)
        self.assertEqual(result["exit_reason"],"stop_first")
        self.assertAlmostEqual(result["gross_return"],-.02)
        self.assertLess(result["net_return"],-.02)

    def test_long_target_and_short_stop(self):
        df=flat()
        df.loc[61,["open","high","low","close"]]=[100,106,99,100]
        long=outcome(df,60,1)
        self.assertEqual(long["exit_reason"],"target")
        self.assertAlmostEqual(long["gross_return"],.05)
        short=outcome(df,60,-1)
        self.assertEqual(short["exit_reason"],"stop_first")
        self.assertAlmostEqual(short["gross_return"],-.02)

    def test_gap_stop_uses_worse_open(self):
        df=flat()
        df.loc[62,["open","high","low","close"]]=[95,96,94,95]
        result=outcome(df,60,1)
        self.assertEqual(result["exit_reason"],"gap_stop")
        self.assertAlmostEqual(result["gross_return"],-.05)

    def test_fee_slippage_and_funding_reduce_label(self):
        df=flat()
        low=outcome(df,60,1,CostPolicy(fee_side=.0005,slippage_side=.0001,funding_reserve=.0001))
        high=outcome(df,60,1,CostPolicy(fee_side=.001,slippage_side=.001,funding_reserve=.0003))
        self.assertLess(high["net_return"],low["net_return"])
        self.assertAlmostEqual(high["net_return"]-low["net_return"],-(.001-.0005)*2-(.001-.0001)*2-(.0003-.0001))

    def test_invalid_candles_never_create_fake_winners(self):
        df=candles()
        df.loc[105,"low"]=np.nan
        self.assertIsNone(outcome(df,100,1))
        with self.assertRaisesRegex(ValueError,"MISSING_OHLCV"):
            setups(df.drop(columns="high"))
        self.assertFalse(setups(df)["breakout_long"].iloc[105])

    def test_missing_future_and_ineligible_setups_are_nan_not_zero(self):
        df=flat()
        labels=training_labels(df)["&-trade_net_return"]
        self.assertTrue(labels.isna().all())
        self.assertIsNone(outcome(df,90,1))

    def test_label_future_does_not_change_past_features(self):
        old=candles(100)
        longer=candles(160)
        longer.loc[100:,"close"]=1e6
        shorter_features=decision_features(old)
        longer_features=decision_features(longer)
        cols=[c for c in shorter_features if c.startswith("%-")]
        pd.testing.assert_frame_equal(shorter_features[cols],longer_features.iloc[:100][cols])

    def test_priority_is_stable_and_covers_all_kinds(self):
        df=candles()
        priority=priority_kind(setups(df))
        self.assertTrue(priority.isin([0,1,2,3,4]).all())
        self.assertEqual(len(KINDS),4)

    def test_bad_research_cost_policy_rejected(self):
        for kwargs in ({"horizon":0},{"horizon":1.5},{"fee_side":-.01},
                       {"slippage_side":float("nan")},{"stop":0},{"target":1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                CostPolicy(**kwargs)

    def test_research_router_default_no_trade(self):
        out=choose_candidate([])
        self.assertEqual(out.action,"NO_TRADE")
        self.assertTrue(out.for_research_only)

    def test_research_router_selects_strongest_without_trading(self):
        def score(kind,pred):
            return CandidateScore(kind,pred,.001,True,2,100000,1000,.001)
        out=choose_candidate([score("breakout_long",.016),score("pullback_long",.012)])
        self.assertEqual(out.action,"breakout_long")
        self.assertTrue(out.for_research_only)
        self.assertGreater(out.selected_score_after_reserve,.004)

    def test_router_rejects_stale_low_liquidity_unknown_and_nan(self):
        cases=[
            CandidateScore("breakout_long",.1,0,True,30,100000,1000),
            CandidateScore("breakout_long",.1,0,True,0,10,1000),
            CandidateScore("invented_new_strategy",.1,0,True,0,100000,1000),
            CandidateScore("breakout_long",float("nan"),0,True,0,100000,1000),
            CandidateScore("breakout_long",.1,0,False,0,100000,1000),
            CandidateScore("breakout_long",.001,0,True,0,100000,1000),
        ]
        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertEqual(choose_candidate([candidate]).action,"NO_TRADE")

    def test_research_strategy_rejects_all_paper_and_live_modes(self):
        config=json.loads((ROOT/"user_data"/"config.json").read_text())
        overlay=json.loads((ROOT/"user_data"/"config.m2r-trade-outcome.json").read_text())
        config.update(overlay)
        config["freqai"]={**json.loads((ROOT/"user_data"/"config.json").read_text())["freqai"],**overlay["freqai"]}
        bot=NbotV6TradeOutcomeResearch()
        bot.config=config
        bot.freqai_info=config["freqai"]
        config["runmode"]="backtest"
        bot.bot_start()
        config["runmode"]="dry_run"
        with self.assertRaisesRegex(RuntimeError,"HISTORICAL_ONLY"):
            bot.bot_start()
        self.assertFalse(bot.confirm_trade_entry("BTC/USDT:USDT","limit",1,100,"gtc",None,None,"long"))
        config["runmode"]="backtest"
        config["dry_run"]=False
        with self.assertRaisesRegex(RuntimeError,"HISTORICAL_ONLY"):
            bot.bot_start()
        config["dry_run"]=True
        config["exchange"]["key"]="bad"
        with self.assertRaisesRegex(RuntimeError,"HISTORICAL_ONLY"):
            bot.bot_start()

    def test_historical_challenger_enforces_one_hour_research_hold(self):
        from datetime import datetime, timedelta, timezone
        bot=NbotV6TradeOutcomeResearch()
        bot.freqai_info={"feature_parameters":{"label_period_candles":12}}
        start=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        trade=type("ResearchTrade", (), {"open_date_utc":start})()
        self.assertIsNone(bot.custom_exit("BTC/USDT:USDT",trade,
            start+timedelta(minutes=55),100,0))
        self.assertEqual(bot.custom_exit("BTC/USDT:USDT",trade,
            start+timedelta(minutes=60),100,0),"m2r_time_horizon")
        with self.assertRaisesRegex(RuntimeError,"HORIZON"):
            bot.freqai_info["feature_parameters"]["label_period_candles"]=0
            bot.custom_exit("BTC/USDT:USDT",trade,start,100,0)

    def test_after_cost_freqai_target_is_distinct_from_original_price_target(self):
        bot=NbotV6TradeOutcomeResearch()
        bot.freqai_info={"feature_parameters":{"label_period_candles":12}}
        frame=bot.set_freqai_targets(candles())
        self.assertIn("&-trade_net_return",frame.columns)
        self.assertNotIn("&-forward_return",frame.columns)
        self.assertTrue(frame["&-trade_net_return"].tail(12).isna().all())

    def test_after_cost_strategy_never_trades_without_model_or_good_forecast(self):
        bot=NbotV6TradeOutcomeResearch()
        frame=candles().iloc[-3:].copy()
        frame["long_setup"]=True
        frame["short_setup"]=False
        frame["do_predict"]=[0,1,1]
        frame["&-trade_net_return"]=[.4,.002,.009]
        frame=bot.populate_entry_trend(frame,{})
        self.assertEqual(list(frame["enter_long"]),[0,0,1])


if __name__ == "__main__":
    unittest.main()
