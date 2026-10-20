"""Artificial nine-month data proves the pipeline executes, not that trading is viable."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
import json

from nbot_v7.lab import con,LABEL_POLICY
from nbot_v7.brain import BASE_KEYS
from nbot_v7.experiment import nine_month_bounds,experiment
from nbot_v7.data import BAR_MS

class NineMonthResearchSmoke(unittest.TestCase):
    def test_frozen_a_retrain_b1_and_adaptive_b2_on_disjoint_months(self):
        try:
            import lightgbm
        except ImportError:
            self.skipTest("LightGBM required for learning")
        a,b,c,d=nine_month_bounds("2026-01")
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"offline.sqlite"
            out=Path(tmp)/"artifacts"
            conn=con(db)
            for key,val in (("policy",LABEL_POLICY),("registry_sha256","f"*64),
                            ("start_ms",str(a)),("end_ms",str(d))):
                conn.execute("INSERT INTO meta VALUES(?,?)",(key,val))
            symbols=("BTCUSDT","ETHUSDT","SOLUSDT")
            records_w=[];records_o=[]
            t=a
            counter=0
            while t < d:
                day=(t-a)//(24*3600*1000)
                for r in range(3):
                    review=t+r*8*3600*1000
                    if review+9*3600*1000>=d:continue
                    regime=("up","range","down")[day%3]
                    for j,s in enumerate(symbols):
                        perf=(.025 if j==(day%3) else -.016)
                        features={k:(j+1)*.005+((day%17)+1)*.0004 for k in BASE_KEYS}
                        features["btc_r48"]= .012 if regime=="up" else -.012 if regime=="down" else 0.0
                        f=json.dumps(features,sort_keys=True)
                        records_w.append((review,review+9*3600*1000,s,regime,f,perf,1,"0"*64))
                        decision=review+BAR_MS
                        exitms=decision+60*60*1000
                        records_o.append((decision,exitms,s,"LONG","structure_generic",regime,
                             f,perf,max(0,perf+.003),min(0,perf-.005),
                             exitms,"HORIZON","COARSE_5M_OHLC_PATH_PROXY","0"*64))
                t+=24*3600*1000
                counter+=1
            conn.executemany("INSERT INTO watch VALUES(?,?,?,?,?,?,?,?)",records_w)
            conn.executemany("INSERT INTO opportunity VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",records_o)
            conn.commit();conn.close()
            result=experiment(db,"2026-01",out)
            self.assertEqual(len(result["stage_c"]),3)
            self.assertEqual(result["train_cutoffs"]["A_3MONTH_FROZEN"],b)
            self.assertEqual(result["train_cutoffs"]["B1_SAME_ARCH_MORE_DATA"],c)
            self.assertEqual(result["train_cutoffs"]["B2_CONTEXTUAL_CHALLENGER"],c)
            self.assertEqual(result["economic_approval"],"NOT_EVALUATED")
            self.assertTrue((out/"summary.json").exists())
            for model in ("A_3MONTH_FROZEN","B1_SAME_ARCH_MORE_DATA","B2_CONTEXTUAL_CHALLENGER"):
                self.assertTrue((out/model/"manifest.json").exists())
            self.assertTrue(len(records_o)>1000)

if __name__=="__main__":
    unittest.main()
