from __future__ import annotations
import json
import unittest
from nbot_v7.brain import fit_head, BASE_KEYS

class LearningContract(unittest.TestCase):
    def test_ranker_learns_grouped_without_future_fields(self):
        try:
            import lightgbm
        except ImportError:
            self.skipTest("lightgbm unavailable")
        rows=[]
        for t in range(25):
            for k in range(3):
                f={key:(t%3)*.001+(k+.5)*.001 for key in BASE_KEYS}
                rows.append({"decision_ms":t*300000,"label_available_ms":t*300000+1000,
                             "symbol":("BTCUSDT","ETHUSDT","SOLUSDT")[k],
                             "features":json.dumps(f),"side":"LONG","family":"structure_generic",
                             "net":(-.02,.01,.03)[k]})
        h=fit_head(rows,"opportunity",10**11,"net")
        self.assertEqual(h.n_rank_groups,25)
        self.assertIsNotNone(h.rank)
        self.assertEqual(len(h.predict(rows[:3])),3)

    def test_future_labels_rejected(self):
        from nbot_v7.brain import fit_head
        rows=[]
        for t in range(45):
            rows.append({"decision_ms":t*300000,"label_available_ms":10**12,
                         "symbol":"BTCUSDT","features":json.dumps({k:0 for k in BASE_KEYS}),
                         "side":"LONG","family":"structure_generic","net":.01})
        with self.assertRaisesRegex(RuntimeError,"FUTURE_LABEL_LEAKAGE"):
            fit_head(rows,"opportunity",10**9,"net")

if __name__=="__main__":unittest.main()
