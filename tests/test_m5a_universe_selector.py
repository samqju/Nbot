"""M5A deterministic, fail-closed tests. No exchange/API/Docker/orders."""
from __future__ import annotations
import copy
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import m5a_universe_selector as m

ASOF=1792137600000  # synthetic scheduled UTC 8h boundary, not real market quote
ASOF=(ASOF//(8*m.HOUR_MS))*(8*m.HOUR_MS)
INC=["BTCUSDT"]+[f"C{i:03d}USDT" for i in range(1,25)]
ALL=INC+[f"N{i:03d}USDT" for i in range(25,50)]
FLAGS=("five_minute_continuity","one_hour_continuity","btc_context",
       "funding_and_mark_history","labels_mature","model_trained",
       "purged_validation_passed","schema_compatible","prediction_fresh")

def market(symbol:str,high_quality:bool,at:int=ASOF)->dict:
    p=100
    return {"symbol":symbol,"status":"TRADING","contractType":"PERPETUAL",
            "quoteAsset":"USDT","marginAsset":"USDT","onboardDate":at-90*24*m.HOUR_MS,
            "bidPrice":p,"askPrice":p*(1.0003 if high_quality else 1.001),
            "bidQty":200 if high_quality else 12,"askQty":200 if high_quality else 12,
            "quoteVolume":400000000 if high_quality else 25000000,
            "highPrice":105,"lowPrice":100,
            "lastFundingRate":.0001,"book_at_ms":at,"ticker_at_ms":at,
            "funding_at_ms":at}

def snapshot():
    return {"schema":"m5a-snapshot-v1","source":"historical_verified_asof",
            "asof_ms":ASOF,"review_start_ms":ASOF,"captured_at_ms":ASOF,
            "review_boundary_aligned":True,
            "contracts":[market(x,x.startswith("N")) for x in ALL]}
def readiness():
    return {"schema":"m5a-readiness-attestation-v1","asof_ms":ASOF,
            "verified_by":"independent_offline_verifier","no_live_activation":True,
            "pairs":[{"symbol":x,"evidence_latest_ms":ASOF-3000,
                       **{k:True for k in FLAGS}} for x in ALL]}
def timestamps():
    return {x:ASOF-48*m.HOUR_MS for x in INC}
def run(s=None,r=None,**kwargs):
    return m.select(s or snapshot(),INC,r if r is not None else readiness(),
                    previous_since_ms=timestamps(),**kwargs)

class M5ASelectorTests(unittest.TestCase):
    def test_exact_25_never_more_than_10_churn_and_pinned_btc(self):
        res=run()
        self.assertEqual(res["status"],"PROPOSAL_ONLY")
        self.assertEqual(len(res["proposed_25"]),25)
        self.assertEqual(len(set(res["proposed_25"])),25)
        self.assertEqual(res["turnover"],10)
        self.assertIn("BTCUSDT",res["proposed_25"])
        self.assertGreaterEqual(len(set(res["original_25"])&set(res["proposed_25"])),15)
        self.assertTrue(res["never_auto_activate"])
        self.assertTrue(res["never_place_orders"])
    def test_protect_open_position_as_well_as_btc(self):
        res=run(pinned={"C001USDT","C024USDT"})
        self.assertIn("C001USDT",res["proposed_25"])
        self.assertIn("C024USDT",res["proposed_25"])
        self.assertEqual(res["turnover"],10)
    def test_untested_model_never_eligible_for_activation(self):
        res=run(r={})
        self.assertEqual(res["status"],"HOLD")
        self.assertEqual(res["proposed_25"],INC)
        self.assertIn("INSUFFICIENT_MODEL_READY_COINS",res["hold_reasons"])
        self.assertGreater(res["eligible_contracts"],25)
        self.assertEqual(res["model_ready_eligible_contracts"],0)
    def test_readiness_without_prediction_is_invalid(self):
        r=readiness()
        r["pairs"][-1]["prediction_fresh"]=False
        res=run(r=r)
        self.assertNotIn("N049USDT",res["proposed_25"])
        self.assertNotEqual(res["status"],"HOLD")  # enough other ready coins
        self.assertNotEqual(res["model_ready_eligible_contracts"],50)
    def test_no_change_when_all_equally_liquid(self):
        s=snapshot()
        for r in s["contracts"]:r.update(market(r["symbol"],False))
        self.assertEqual(run(s=s)["turnover"],0)
    def test_no_rotation_without_verified_tenure(self):
        res=m.select(snapshot(),INC,readiness())
        self.assertEqual(res["turnover"],0)
    def test_stale_and_future_book_fail_closed(self):
        s=snapshot()
        s["contracts"][0]["book_at_ms"]=ASOF-4*m.MAX_SNAPSHOT_AGE_MS
        self.assertEqual(run(s=s)["status"],"HOLD")
        self.assertIn("UNSAFE_INCUMBENT_REQUIRES_SEPARATE_REVIEW",run(s=s)["hold_reasons"])
        s=snapshot()
        s["contracts"][0]["funding_at_ms"]=ASOF+10
        self.assertEqual(run(s=s)["status"],"HOLD")
    def test_invalid_contract_type_and_suspended_rejected(self):
        s=snapshot()
        s["contracts"][0]["contractType"]="CURRENT_QUARTER"
        self.assertEqual(run(s=s)["status"],"HOLD")
        s=snapshot();s["contracts"][1]["status"]="BREAK"
        self.assertEqual(run(s=s)["status"],"HOLD")
    def test_8h_boundary_and_snapshot_source_must_be_authentic(self):
        s=snapshot();s["review_start_ms"]+=m.HOUR_MS
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_OUTSIDE_EIGHT_HOUR_REVIEW_WINDOW"):
            run(s=s)
        s=snapshot();s["source"]="fabricated_backtest"
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_SNAPSHOT_SOURCE"):run(s=s)
        s=snapshot();s["captured_at_ms"]=ASOF+5000
        with self.assertRaisesRegex(ValueError,"SNAPSHOT_CAPTURED_AFTER_DECISION"):run(s=s)
    def test_no_historical_symbol_from_current_metadata(self):
        s=snapshot()
        s["contracts"][30]["onboardDate"]=ASOF+100000
        result=run(s=s)
        self.assertIn("INSUFFICIENT_VERIFIED_AGE",result["rejections"]["N030USDT"])
        self.assertNotIn("N030USDT",result["proposed_25"])
    def test_no_ready_if_future_model_label_used(self):
        r=readiness()
        r["pairs"][0]["evidence_latest_ms"]=ASOF+60000
        with self.assertRaisesRegex(ValueError,"FUTURE_READINESS_EVIDENCE"):run(r=r)
    def test_pin_unknown_and_duplicate_universe_rejected(self):
        with self.assertRaisesRegex(ValueError,"PINNED_COIN_NOT_INCUMBENT"):
            run(pinned={"N025USDT"})
        with self.assertRaisesRegex(ValueError,"REQUIRE_25_UNIQUE_INCUMBENTS"):
            m.select(snapshot(),INC[:-1]+["BTCUSDT"],readiness())
    def test_stale_readiness_holds_strictly(self):
        r=readiness();r["asof_ms"]=ASOF-5*m.MAX_SNAPSHOT_AGE_MS
        with self.assertRaisesRegex(ValueError,"STALE_OR_FUTURE_READINESS"):run(r=r)
    def test_illiquid_high_spread_markets_are_not_ranked(self):
        s=snapshot()
        s["contracts"][-1]["askPrice"]=150
        s["contracts"][-2]["quoteVolume"]=12345
        res=run(s=s)
        self.assertIn("SPREAD_TOO_WIDE",res["rejections"]["N049USDT"])
        self.assertIn("INSUFFICIENT_24H_TURNOVER",res["rejections"]["N048USDT"])
        self.assertNotIn("N049USDT",res["proposed_25"])
    def test_strict_volatility_toxic_funding_minimum_age(self):
        s=snapshot()
        x=s["contracts"][-1]
        x["lastFundingRate"]=0.007
        x["highPrice"]=180
        x["onboardDate"]=ASOF-10*m.HOUR_MS
        res=run(s=s)
        reasons=res["rejections"]["N049USDT"]
        self.assertIn("EXCESS_FUNDING",reasons)
        self.assertIn("RANGE_OUTSIDE_EXPLORATORY_BOUNDS",reasons)
        self.assertIn("INSUFFICIENT_VERIFIED_AGE",reasons)
    def test_liquidity_only_baseline_retains_25_pins(self):
        res=run(policy="liquidity")
        self.assertEqual(res["turnover"],10)
        self.assertIn("BTCUSDT",res["proposed_25"])
        self.assertEqual(res["policy"],"liquidity")
    def test_deterministic_for_replay_and_hashes(self):
        self.assertEqual(run(),run())
        self.assertEqual(m.sha_obj(run()),m.sha_obj(run()))
    def test_missing_or_nonfinite_quotes_fail_closed(self):
        s=snapshot();s["contracts"][0]["bidPrice"]="NaN"
        r=run(s=s)
        self.assertEqual(r["status"],"HOLD")
        self.assertIn("INVALID_MARKET_VALUES",r["rejections"]["BTCUSDT"])
    def test_safe_symbol_pair_roundtrip(self):
        for x in INC:self.assertEqual(m.symbol_from_pair(m.pair(x)),x)

if __name__=="__main__":unittest.main()
