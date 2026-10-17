"""M2R chronological split: training outcomes must finish before cutoff."""
import sys
from pathlib import Path
import unittest

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from m2r_purged_split import purged_opportunity_split


class M2RPurgeTests(unittest.TestCase):
    def test_future_trade_label_overlapping_test_start_is_purged(self):
        rows=pd.DataFrame([
            {"decision_index":85,"exit_index":93,"candidate":"breakout_long","net_return":.01},
            {"decision_index":89,"exit_index":101,"candidate":"pullback_long","net_return":-.02},
            {"decision_index":100,"exit_index":110,"candidate":"breakout_short","net_return":-.01},
            {"decision_index":102,"exit_index":109,"candidate":"pullback_short","net_return":.02},
        ])
        train,test,purged=purged_opportunity_split(rows,100)
        self.assertEqual(len(train),1)
        self.assertEqual(len(test),2)
        self.assertEqual(len(purged),1)
        self.assertLess(train["exit_index"].max(),100)
        self.assertGreaterEqual(test["decision_index"].min(),100)

    def test_cutoff_must_be_positive(self):
        with self.assertRaisesRegex(ValueError,"CUTOFF"):
            purged_opportunity_split(pd.DataFrame(),0)

    def test_invalid_exit_index_fails(self):
        rows=pd.DataFrame([{"decision_index":10,"exit_index":9,
                            "candidate":"breakout_long","net_return":.01}])
        with self.assertRaisesRegex(ValueError,"TRADE_WINDOW"):
            purged_opportunity_split(rows,100)

    def test_empty_train_and_test_are_valid(self):
        rows=pd.DataFrame([{"decision_index":90,"exit_index":101,
                            "candidate":"breakout_long","net_return":.01}])
        train,test,purged=purged_opportunity_split(rows,100)
        self.assertTrue(train.empty)
        self.assertTrue(test.empty)
        self.assertEqual(len(purged),1)

if __name__=="__main__":
    unittest.main()
