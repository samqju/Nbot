"""M5A chronological eight-hour shadow replay tests; no market API/orders."""
from __future__ import annotations
import copy
import pathlib
import random
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from tests.test_m5a_universe_selector import (
    ASOF,ALL,INC,FLAGS,market,readiness,snapshot,timestamps
)
import m5a_shadow_replay as replay
from m5a_universe_selector import HOUR_MS,select

def event(i:int):
    step=8*HOUR_MS*i
    s=snapshot()
    s["asof_ms"]+=step
    s["review_start_ms"]+=step
    s["captured_at_ms"]+=step
    for c in s["contracts"]:
        for field in ("book_at_ms","ticker_at_ms","funding_at_ms"):
            c[field]+=step
    r=readiness()
    r["asof_ms"]+=step
    for x in r["pairs"]:x["evidence_latest_ms"]+=step
    return {"snapshot":s,"readiness":r,"pinned":["BTCUSDT"]}

class M5AShadowReplayTests(unittest.TestCase):
    def test_quality_vs_liquidity_and_fixed_25_across_real_8h_decision_clock(self):
        rows=[event(i) for i in range(7)]
        r=replay.replay(rows,INC,timestamps())
        self.assertEqual(r["snapshot_events_replayed"],7)
        self.assertEqual(r["policies"]["fixed25"]["total_virtual_replacements"],0)
        self.assertGreater(r["policies"]["quality25"]["total_virtual_replacements"],0)
        self.assertGreater(r["policies"]["liquidity25"]["total_virtual_replacements"],0)
        self.assertLessEqual(r["policies"]["quality25"]["total_virtual_replacements"],70)
        self.assertEqual(len(r["policies"]["quality25"]["end_shadow_25"]),25)
        self.assertTrue(r["no_trading_pnl_or_prediction_quality_evidence"])
        self.assertTrue(r["shadow_only_never_changes_actual_pairlist"])
        for cycle in r["ledger"]:
            self.assertLessEqual(cycle["quality25"]["turnover"],10)
            self.assertEqual(len(set(cycle["quality25"]["proposed_25"])),25)
            self.assertIn("BTCUSDT",cycle["quality25"]["proposed_25"])
    def test_no_model_ready_is_zero_churn_across_all_policies(self):
        rows=[event(i) for i in range(5)]
        for x in rows:x["readiness"]={}
        r=replay.replay(rows,INC,timestamps())
        self.assertEqual(r["policies"]["quality25"]["total_virtual_replacements"],0)
        self.assertEqual(r["policies"]["quality25"]["reviews_blocked"],5)
        self.assertEqual(r["policies"]["liquidity25"]["reviews_blocked"],5)
    def test_out_of_order_and_duplicate_future_snapshots_rejected(self):
        with self.assertRaisesRegex(ValueError,"UNSORTED_OR_DUPLICATE_REPLAY_TIMESTAMP"):
            replay.replay([event(1),event(0)],INC,timestamps())
        with self.assertRaisesRegex(ValueError,"UNSORTED_OR_DUPLICATE_REPLAY_TIMESTAMP"):
            replay.replay([event(0),event(0)],INC,timestamps())
    def test_no_lookahead_in_synthetic_300_cycle_stress(self):
        rng=random.Random(17012026)
        state=list(INC)
        since=timestamps()
        for i in range(300):
            e=event(i)
            s=e["snapshot"]
            r=e["readiness"]
            # Distort hypothetical market quality without future labels.
            for c in s["contracts"]:
                if rng.random()<.07:
                    c["quoteVolume"]=0
                if rng.random()<.02:
                    c["lastFundingRate"]=.01
            for entry in r["pairs"]:
                if rng.random()<.12:entry["prediction_fresh"]=False
            pinned={"BTCUSDT"}
            if i%6==0:pinned.add(rng.choice(state))
            out=select(s,state,r,pinned=pinned,
                       previous_since_ms=since)
            self.assertLessEqual(out["turnover"],10)
            self.assertEqual(len(out["proposed_25"]),25)
            self.assertEqual(len(set(out["proposed_25"])),25)
            self.assertTrue(pinned.issubset(set(out["proposed_25"])))
            if out["status"]=="PROPOSAL_ONLY":
                earlier=set(state)
                state=list(out["proposed_25"])
                since={k:v for k,v in since.items() if k in state}
                for added in set(state)-earlier:since[added]=s["asof_ms"]
            else:
                self.assertEqual(out["turnover"],0)
                self.assertEqual(out["proposed_25"],state)

if __name__=="__main__":
    unittest.main()
