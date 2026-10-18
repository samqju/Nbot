"""Safety and executable contract tests for the finite 25x8 global research.

Only synthetic fixtures; nothing places or transmits exchange orders.
"""
from __future__ import annotations
from pathlib import Path
import ast
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import m2r_v6_global_batch as batch
from m2r_v6_global_opportunity_ranker import (
    choose_global_opportunity,Opportunity,RankPolicy)

class TestGlobalOfflineResearchSafety(unittest.TestCase):
    def test_pipeline_is_finite_four_windows_two_native_exit_policies(self):
        self.assertEqual(batch.WINDOWS,(30,60,90,180))
        self.assertEqual(batch.PROFILES,("fixed","trailing"))
        self.assertEqual(batch.STAGES,12)

    def test_explicit_execution_optin_and_prerequisite_blocks(self):
        # We are not root in ordinary CI; missing opt-in MUST fail BEFORE jobs.
        from unittest.mock import patch
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"CONSENT"):
                batch.ensure_prerequisites()

    def test_native_zip_rejects_fake_strategy(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            results=folder/"backtest_results"
            results.mkdir()
            report={"strategy":{"PretendProfitableBot":{
                "trading_mode":"futures","max_open_trades":1,
                "pairlist":["BTC/USDT:USDT"]*25,
                "stake_amount":1000,"starting_balance":100000,
                "trades":[],"total_trades":0,"profit_total_abs":1000000}}}
            with zipfile.ZipFile(results/"fake.zip","w") as z:
                z.writestr("result.json",json.dumps(report))
            with self.assertRaisesRegex(RuntimeError,"UNEXPECTED_NATIVE_STRATEGY"):
                batch.native_audit(folder,"fixed",30)

    def test_native_zip_rejects_corrupted_file(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"backtest_results"
            p.mkdir()
            (p/"broken.zip").write_bytes(b"not a genuine Freqtrade archive")
            with self.assertRaises(zipfile.BadZipFile):
                batch.native_audit(Path(root),"trailing",60)

    def test_all_implementation_source_parses_and_no_live_commands(self):
        paths=("scripts/m2r_v6_global_dataset.py",
               "scripts/m2r_v6_global_batch.py",
               "user_data/strategies/NbotV6GlobalOfflineResearch.py")
        for p in paths:
            with self.subTest(path=p):
                text=(ROOT/p).read_text()
                ast.parse(text,filename=p)
                self.assertNotIn("create_order(",text)
                self.assertNotIn("trade_live",text)

class TestDatasetProxyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import pandas as pd
            import numpy as np
            import lightgbm
            from freqtrade.strategy import IStrategy
            import m2r_v6_global_dataset as dataset
            cls.pd=pd
            cls.module=dataset
            cls.available=True
        except (ImportError,ModuleNotFoundError):
            cls.available=False

    def setUp(self):
        if not self.available:self.skipTest("FreqAI official Docker dependencies not installed on host")

    def test_proxy_does_not_look_at_signal_candle_for_entry(self):
        pd=self.pd
        base=pd.Timestamp("2026-04-01T00:00:00Z")
        candles=[{"date":base+pd.Timedelta(minutes=5*i),
                   "open":100.0,"high":101.0,"low":99.0,
                   "close":100.0,"volume":10} for i in range(14)]
        candles[0]["high"]=300.0  # Signal candle high must NEVER determine outcome.
        candles[1]["high"]=106.0
        candles[1]["low"]=97.0 # BOTH stop 98 and take 105; stop-first.
        result=self.module.proxy_label(pd.DataFrame(candles),0,"long")
        self.assertAlmostEqual(result[0],-.021,places=8)
        result_short=self.module.proxy_label(pd.DataFrame(candles),0,"short")
        self.assertAlmostEqual(result_short[0],-.021,places=8)

    def test_training_features_distinguish_coin_and_family(self):
        pd=self.pd
        a=dict(pair="BTC/USDT:USDT",family="ema_cross",side="long")
        b=dict(pair="ETH/USDT:USDT",family="bollinger_reversion",side="short")
        for feature in self.module.BASE_FEATURES:
            a[feature]=.1
            b[feature]=.1
        d=pd.DataFrame([a,b])
        m=self.module.numeric_matrix(d,["BTC/USDT:USDT","ETH/USDT:USDT"])
        self.assertEqual(m.shape,(2,len(self.module.BASE_FEATURES)+8+1+2))
        self.assertFalse((m[0]==m[1]).all())

    def test_chronological_lightgbm_scoring_retains_all_rejected_candidates(self):
        import numpy as np
        pd=self.pd
        start=pd.Timestamp("2026-08-01T00:00:00Z")
        pairs=("BTC/USDT:USDT","ETH/USDT:USDT")+tuple(
            f"TEST{i}/USDT:USDT" for i in range(23))
        rows=[]
        times=list(pd.date_range(start-pd.Timedelta(days=28),
                                 start-pd.Timedelta(days=8),periods=260))
        times+=list(pd.date_range(start-pd.Timedelta(days=5),
                                  start-pd.Timedelta(days=2),periods=75))
        times+=list(pd.date_range(start,start+pd.Timedelta(hours=1),periods=26))
        for n,t in enumerate(times):
            row=dict(date=t,pair=pairs[n%2],
                     family=self.module.FAMILIES[n%8],
                     side="short" if n%3==0 else "long",
                     label_observed_at=t+pd.Timedelta(minutes=60),
                     net_proxy=(.022 if n%3 else -.024),
                     liquidity_turnover_proxy_usdt=25000)
            for j,key in enumerate(self.module.BASE_FEATURES):
                row[key]=float(.01*(j+1)+np.sin(n/7.0+j)*.003)
            rows.append(row)
        df=pd.DataFrame(rows)
        audit,selected,forecasts=self.module.learn_and_rank(
            df,30,start,start+pd.Timedelta(days=1),None,pairs)
        self.assertEqual(audit["status"],"complete")
        self.assertEqual(len(forecasts),26)
        self.assertEqual(audit["candidate_count"],26)
        self.assertLessEqual(len(selected),26)
        self.assertTrue(all("reason" in x for x in forecasts))
        self.assertTrue(all(x["exploratory_not_economically_validated"]
                            for x in forecasts))
        self.assertTrue(all("net_proxy" not in x for x in forecasts))

if __name__=="__main__":unittest.main()
