"""Research-only deterministic funding and purged-model regression tests."""
from __future__ import annotations
import importlib.util
import json
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"user_data"/"strategies"))
from m2r_event_cost_labels import FundingSchedule, funding_adjusted_outcome, event_funding_training_labels
from nbot_trade_outcome import CostPolicy, outcome


class TestEventAwareFunding(unittest.TestCase):
    def setUp(self):
        start=pd.Timestamp("2026-10-08T00:00:00Z")
        self.candles=pd.DataFrame({
            "date":pd.date_range(start, periods=20,freq="5min"),
            "open":100.0,"high":100.1,"low":99.9,"close":100.0,
            "volume":100.0,
        })
        self.funding=pd.DataFrame({
            "date":[start+pd.Timedelta(hours=1)],
            "funding_rate":[.001],
        })
        self.mark=pd.DataFrame({
            "date":[start-pd.Timedelta(hours=1),start],
            "close":[120.0,100.0],
        })
        self.schedule=FundingSchedule.from_candles(self.funding,self.mark)

    def test_positive_funding_charges_long_credits_short(self):
        a=self.schedule.hypothetical_charge(
            self.candles.date.iloc[1],
            self.candles.date.iloc[12]+pd.Timedelta(minutes=5),100,1)
        b=self.schedule.hypothetical_charge(
            self.candles.date.iloc[1],
            self.candles.date.iloc[12]+pd.Timedelta(minutes=5),100,-1)
        self.assertAlmostEqual(a[0],.001)
        self.assertAlmostEqual(b[0],-.001)
        self.assertEqual((a[1],b[1]),(1,1))
        self.assertFalse(a[2])

    def test_marks_are_only_from_completed_hour(self):
        # At 01:00, 00:00 hourly mark close (100) has completed;
        # 01:00 mark bar (future) must never be incorporated.
        self.assertEqual(self.schedule.mark_proxy[0],100.0)

    def test_next_open_label_funding_not_used_as_feature(self):
        cost=CostPolicy()
        long=funding_adjusted_outcome(self.candles,0,1,self.schedule,cost)
        short=funding_adjusted_outcome(self.candles,0,-1,self.schedule,cost)
        self.assertIsNotNone(long)
        self.assertIsNotNone(short)
        raw=outcome(self.candles,0,1,cost)
        self.assertAlmostEqual(long["event_aware_label_net_return"],
                               raw["net_return"]+cost.funding_reserve-.001)
        self.assertAlmostEqual(short["event_aware_label_net_return"],
                               raw["net_return"]+cost.funding_reserve+.001)
        self.assertEqual(long["funding_events_crossed_estimate"],1)
        self.assertNotIn("event_aware_label_net_return",self.candles.columns)

    def test_event_funding_training_target_never_labels_unknown_trailing_horizon(self):
        n=130
        prices=100*np.exp(np.arange(n)*.002)
        frame=pd.DataFrame({
            "date":pd.date_range("2026-10-08",periods=n,freq="5min",tz="UTC"),
            "open":prices,"close":prices,
            "high":prices*1.001,"low":prices*.999,"volume":100.0,
        })
        start=frame.date.iloc[0]
        rates=pd.DataFrame({
            "date":[start+pd.Timedelta(hours=h) for h in (2,4,6,8)],
            "funding_rate":[.0001]*4,
        })
        mark=pd.DataFrame({
            "date":pd.date_range(start-pd.Timedelta(hours=1),periods=12,freq="1h"),
            "close":[100.0]*12,
        })
        schedule=FundingSchedule.from_candles(rates,mark)
        out=event_funding_training_labels(frame,schedule,CostPolicy())
        self.assertTrue(out["&-trade_net_return"].iloc[-12:].isna().all())
        self.assertGreater(int(out["&-trade_net_return"].iloc[:-12].notna().sum()),0)
        self.assertFalse(any(k.startswith("%-") for k in out.columns))
        self.assertEqual(len(out),n)

    def test_settlement_at_exit_boundary_is_flagged(self):
        t=self.funding.date.iloc[0]
        signed,count,ambiguous=self.schedule.hypothetical_charge(
            t-pd.Timedelta(minutes=15),t,100,1)
        self.assertTrue(ambiguous)
        self.assertEqual(count,1)
        self.assertAlmostEqual(signed,.001)

    def test_invalid_past_mark_or_rates_rejected(self):
        invalid=self.mark.loc[self.mark.date>=self.mark.date.max()].copy()
        invalid["date"] = self.funding.date.iloc[0]  # closes AFTER settlement; invalid
        self.assertRaises(ValueError,FundingSchedule.from_candles,self.funding,invalid)
        bad=self.funding.copy()
        bad["funding_rate"]=float("nan")
        self.assertRaises(ValueError,FundingSchedule.from_candles,bad,self.mark)


def _has_real_freqtrade_runtime():
    # Other existing offline unit tests inject a stub module with
    # __spec__=None; find_spec then raises ValueError on GitHub CI.
    # A stub must NEVER run our native 2026.9 model tests.
    module=sys.modules.get("freqtrade")
    if module is not None and getattr(module,"__spec__",None) is None:
        return False
    try:
        return importlib.util.find_spec("freqtrade") is not None
    except (ImportError,ValueError):
        return False


@unittest.skipUnless(_has_real_freqtrade_runtime(),"requires installed Freqtrade runtime")
class TestNativePurgedModelContract(unittest.TestCase):
    def test_sparse_split_already_has_safe_gap_without_removal(self):
        sys.path.insert(0,str(ROOT/"user_data"/"freqaimodels"))
        from NbotV6PurgedLightGBMRegressor import apply_strict_training_embargo
        d=pd.Series(pd.date_range("2026-10-01",periods=400,freq="5min",tz="UTC"))
        frame={
            "train_features":pd.DataFrame({"x":[1.0]*200},index=range(200)),
            "train_labels":pd.DataFrame({"y":[1.0]*200},index=range(200)),
            "train_weights":np.ones(200),
            "test_features":pd.DataFrame({"x":[1.0]*50},index=range(250,300)),
            "test_labels":pd.DataFrame({"y":[1.0]*50},index=range(250,300)),
            "test_weights":np.ones(50),
        }
        out,stats=apply_strict_training_embargo(
            frame,d.iloc[:200],d.iloc[250:300],pd.Timedelta(minutes=60))
        self.assertEqual(stats["removed_train_rows"],0)
        self.assertEqual(stats["post_embargo_boundary_violations"],0)
        self.assertEqual(len(out["train_features"]),200)

    def test_native_chronological_internal_embargo(self):
        sys.path.insert(0,str(ROOT/"user_data"/"freqaimodels"))
        from NbotV6PurgedLightGBMRegressor import apply_strict_training_embargo
        n=1000
        times=pd.Series(pd.date_range("2026-10-01",periods=n,freq="5min",tz="UTC"))
        result={
            "train_features":pd.DataFrame({"%-a":np.ones(800)},index=np.arange(800)),
            "train_labels":pd.DataFrame({"&-a":np.ones(800)},index=np.arange(800)),
            "train_weights":np.ones(800),
            "test_features":pd.DataFrame({"%-a":np.ones(200)},index=np.arange(800,n)),
            "test_labels":pd.DataFrame({"&-a":np.ones(200)},index=np.arange(800,n)),
            "test_weights":np.ones(200),
        }
        clean,audit=apply_strict_training_embargo(
            result,times.iloc[:800],times.iloc[800:],pd.Timedelta(minutes=60)
        )
        self.assertEqual(audit["removed_train_rows"],12)
        self.assertEqual(len(clean["train_features"]),788)
        self.assertEqual(audit["post_embargo_boundary_violations"],0)
        self.assertTrue((times.iloc[clean["train_features"].index].max()
                         +pd.Timedelta(minutes=60)) < times.iloc[800])
        config=json.loads((ROOT/"user_data"/"config.m2r-native-purged-frozen.json").read_text())
        self.assertTrue(config["nbot_m2r_purge_internal"])
        self.assertEqual(config["exchange"],{"key":"","secret":""})
        self.assertTrue(config["dry_run"])


if __name__=="__main__":
    unittest.main()
