"""NBOT V6 strategy library: chronological causality and risk gate unit contracts.

Runs without Freqtrade or exchange access, with real numpy/pandas and the
actual candidate indicator functions. Official Freqtrade discovery runs in
the separate Docker CI job. No historical profitability is inferred here.
"""
from __future__ import annotations
from datetime import timedelta
import importlib
import json
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"user_data"/"strategies"))

from m2r_strategy_library_selector import (
    CandidateBlock, choose_validated_strategy, parse_blocks, VALID_FAMILIES
)
from m2r_v6_library_native_job import CANDIDATES, OVERLAYS, PERIODS, plan


def make_block(family="ema_cross",regime="trend_up",start="2026-05-01T00:00:00Z",
               end="2026-05-15T00:00:00Z", trained="2026-04-30T00:00:00Z",
               count=30, net=55., stress=24., dd=.02):
    return CandidateBlock(
        family=family,regime=regime,evaluated_from=start,evaluated_until=end,
        model_trained_until=trained,native_zip_sha256="a"*64,
        market_history_sha256="b"*64,trade_count=count,pnl_net_usdt=net,
        stressed_net_usdt=stress,max_drawdown_fraction=dd,
        native_audit_passed=True,decision_boundary_passed=True,
    )


class TestNativeSelector(unittest.TestCase):
    def setUp(self):
        self.first=make_block()
        self.second=make_block(start="2026-05-16T00:00:00Z",
            end="2026-05-31T00:00:00Z",trained="2026-05-15T00:00:00Z")
        self.decision="2026-06-01T00:00:00Z"

    def test_requires_two_nonoverlapping_profitable_stressed_native_blocks(self):
        yes=choose_validated_strategy([self.first,self.second],
            decision_at=self.decision,regime="trend_up")
        self.assertEqual((yes.action,yes.family),("SELECT","ema_cross"))
        self.assertGreater(yes.estimated_conservative_stressed_profit_per_trade,0)
        no=choose_validated_strategy([self.first],
            decision_at=self.decision,regime="trend_up")
        self.assertTrue(no.is_no_trade)
        overlapping=make_block(start="2026-05-14T00:00:00Z",
            end="2026-05-31T00:00:00Z",trained="2026-05-13T00:00:00Z")
        self.assertTrue(choose_validated_strategy([self.first,overlapping],
            decision_at=self.decision,regime="trend_up").is_no_trade)

    def test_strict_asof_future_is_not_used(self):
        decision="2026-05-16T00:00:00Z"
        result=choose_validated_strategy([self.first,self.second],
            decision_at=decision,regime="trend_up")
        self.assertTrue(result.is_no_trade)
        future=make_block(start="2026-06-01T00:00:00Z",
            end="2026-06-15T00:00:00Z",trained="2026-05-31T00:00:00Z")
        self.assertTrue(choose_validated_strategy([self.first,self.second,future],
            decision_at=self.decision,regime="trend_up").is_no_trade
            is False)  # the two completed past blocks still qualify
        self.assertTrue(choose_validated_strategy([future],
            decision_at=self.decision,regime="trend_up").is_no_trade)

    def test_risk_cost_and_regime_fail_closed(self):
        self.assertTrue(choose_validated_strategy([self.first,self.second],
            decision_at=self.decision,regime="high_volatility").is_no_trade)
        self.assertTrue(choose_validated_strategy([self.first,self.second],
            decision_at=self.decision,regime="range").is_no_trade)
        bad=make_block(start="2026-05-16T00:00:00Z",end="2026-05-31T00:00:00Z",
                       trained="2026-05-15T00:00:00Z",stress=-1)
        self.assertTrue(choose_validated_strategy([self.first,bad],
            decision_at=self.decision,regime="trend_up").is_no_trade)
        risk=make_block(start="2026-05-16T00:00:00Z",end="2026-05-31T00:00:00Z",
                        trained="2026-05-15T00:00:00Z",dd=.08)
        self.assertTrue(choose_validated_strategy([self.first,risk],
            decision_at=self.decision,regime="trend_up").is_no_trade)
        with self.assertRaises(ValueError):
            choose_validated_strategy([self.first,self.second],
                decision_at="2026-06-01T03:00:00Z",regime="trend_up")

    def test_scorecard_schema_and_train_overlap_rejected(self):
        with self.assertRaises(ValueError):
            make_block(trained="2026-05-10T00:00:00Z").validate()
        with self.assertRaises(ValueError):
            parse_blocks([{"family":"ema_cross"}])
        with self.assertRaises(ValueError):
            make_block(stress=56,net=55).validate()
        with self.assertRaises(ValueError):
            make_block(family="unknown").validate()


class TestLibraryIndicators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Unit test strategy signal calculations without importing Freqtrade.
        # Production official strategy discovery is separately tested in Docker.
        fake=types.ModuleType("freqtrade")
        sub=types.ModuleType("freqtrade.strategy")
        class Param:
            def __init__(self,*args,default=None,**kwargs):
                self.value=default
        sub.IStrategy=object
        sub.IntParameter=Param
        sub.DecimalParameter=Param
        with patch.dict(sys.modules,{"freqtrade":fake,"freqtrade.strategy":sub}):
            module=importlib.import_module("NbotV6LibraryResearch")
        cls.m=module

    @classmethod
    def df(cls):
        n=460
        t=np.arange(n,dtype=float)
        close=100+0.03*t+np.sin(t/11)*3
        high=close+0.3
        low=close-0.3
        return pd.DataFrame({
            "open":close-0.05,"high":high,"low":low,"close":close,
            "volume":400+100*(np.sin(t/5)+1),
            "date":pd.date_range("2026-01-01",periods=n,freq="5min",tz="UTC")})

    def test_indicators_do_not_change_when_future_candles_are_appended(self):
        df=self.df()
        indicators=self.m.library_indicators(df)
        self.assertEqual(set(self.m.FAMILIES),VALID_FAMILIES)
        for family in self.m.FAMILIES:
            full=self.m.library_signals(indicators,family)
            self.assertFalse(bool((full["long"] & full["short"]).any()))
            self.assertFalse(bool(full.iloc[:100].any().any()))
            for prefix in (260,320,430):
                clipped=self.m.library_signals(self.m.library_indicators(df.iloc[:prefix].copy()),family)
                pd.testing.assert_frame_equal(clipped,full.iloc[:prefix])
        altered=df.copy()
        altered.loc[430:,"close"]=50000
        for col in ("open","high","low"):
            altered.loc[430:,col]=50000 if col=="open" else (50001 if col=="high" else 49999)
        future=self.m.library_indicators(altered)
        pd.testing.assert_frame_equal(
            indicators.iloc[:430],future.iloc[:430])

    def test_missing_candle_and_invalid_history_produce_no_signal(self):
        df=self.df()
        df.loc[300,"volume"]=0
        result=self.m.library_signals(self.m.library_indicators(df),"donchian_breakout")
        self.assertFalse(result.iloc[300].any())
        with self.assertRaises(ValueError):
            self.m.library_signals(df,"unregistered_external_strategy")


class TestResearchExecutionSafety(unittest.TestCase):
    def test_all_candidates_get_native_and_independent_lgbm(self):
        self.assertEqual(len(CANDIDATES),8)
        self.assertEqual(len({name for classes in CANDIDATES.values() for name in classes}),16)
        for family, (plain,ai) in CANDIDATES.items():
            cmd=plan("native",family,"validation_july")
            self.assertIn("--enable-protections",cmd)
            self.assertIn(plain,cmd)
            self.assertIn("--memory=6g",cmd)
            ai_cmd=plan("lgbm",family,"validation_july")
            self.assertIn(ai,ai_cmd)
            self.assertIn("NbotV6PurgedLightGBMRegressor",ai_cmd)
        with self.assertRaises(ValueError):
            plan("hyperopt","ema_cross","replication_september")
        with self.assertRaises(ValueError):
            plan("native","nonexistent","validation_july")

    def test_rl_and_adaptive_are_isolated_and_empty_manifest_no_auto_winner(self):
        self.assertIn("NbotV6CostAwareRLResearch",plan("rl","ema_cross","validation_july"))
        self.assertIn("NbotV6AdaptiveLibraryResearch",plan("adaptive","ema_cross","validation_july"))
        record=json.loads((ROOT/"user_data/v6_library_scorecards.offline.json").read_text())
        self.assertEqual(record["blocks"],[])
        self.assertEqual(record["schema"],"nbot-v6-native-verified-blocks-v1")
        self.assertTrue(choose_validated_strategy([],
            decision_at="2026-07-01T00:00:00Z",regime="trend_up").is_no_trade)

    def test_json_profiles_are_research_only(self):
        for overlay in OVERLAYS.values():
            d=json.loads((ROOT/"user_data"/overlay).read_text())
            self.assertTrue(d["dry_run"])
            self.assertFalse(d["nbot_live_mode"])
            self.assertFalse(d["nbot_paper_research_mode"])
            self.assertEqual(d["exchange"],{"key":"","secret":""})
            self.assertEqual(d["max_open_trades"],1)
            self.assertEqual(d["stake_amount"],1000)
            self.assertFalse(d["telegram"]["enabled"])
            self.assertFalse(d["api_server"]["enabled"])


if __name__=="__main__":
    unittest.main()
