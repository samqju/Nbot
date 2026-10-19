"""Test one-shot shadow boundary and refusal to make tradeable models."""
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from tests.test_m5a_universe_selector import snapshot,readiness,INC
from m5a_shadow_cycle import run_cycle

CONFIG={"exchange":{"pair_whitelist":[x[:-4]+"/USDT:USDT" for x in INC],
                    "name":"binance"},
        "trading_mode":"futures","dry_run":True}

class ShadowCycleTests(unittest.TestCase):
    def test_8h_review_without_model_ready_always_holds(self):
        result=run_cycle(CONFIG,snapshot())
        self.assertEqual(result["status"],"HOLD")
        self.assertEqual(result["selector"]["proposed_25"],INC)
        self.assertEqual(result["selector"]["turnover"],0)
        self.assertFalse(result["orders_submitted"])
    def test_outside_review_does_not_make_fake_asof_proposal(self):
        s=snapshot()
        s["review_boundary_aligned"]=False
        s["captured_at_ms"]+=3600000
        result=run_cycle(CONFIG,s)
        self.assertEqual(result["status"],"DIAGNOSTIC_ONLY_OUTSIDE_REVIEW_WINDOW")
        self.assertNotIn("selector",result)
        self.assertFalse(result["actual_freqai_watchlist_changed"])
    def test_model_ready_needs_real_tenure_before_rotation(self):
        result=run_cycle(CONFIG,snapshot(),readiness())
        self.assertEqual(result["status"],"PROPOSAL_ONLY")
        self.assertEqual(result["selector"]["turnover"],0)
        self.assertTrue(result["selector"]["never_auto_activate"])
    def test_readiness_prevents_unverified_live_activation(self):
        r=readiness()
        r["verified_by"]="user_says_it_is_ready"
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_MODEL_READINESS"):
            run_cycle(CONFIG,snapshot(),r)
if __name__=="__main__":unittest.main()
