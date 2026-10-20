"""Causal, fail-closed checks for development-only FreqAI/Qlib/FinRL-style trials."""
from datetime import datetime,timezone
import sqlite3
import unittest

from scripts.v7_three_coin_challenger_methods import FrozenGateBrain, calibration_april
from nbot_v7.experiment import month_start
from nbot_v7.lab import SCHEMA


class DummyBrain:
    version="FROZEN_A_TEST"
    cutoff_ms=0
    def score(self,rows,kind):
        return [(0.002,3.0) for _ in rows]


class ChallengerMethodsTests(unittest.TestCase):
    def test_trade_calibration_and_zero_exposure_gate_do_not_touch_watch(self):
        base=DummyBrain()
        row={"regime":"range","decision_ms":1,"side":"LONG"}
        bias=FrozenGateBrain(base,"CAL",bias=.0015,margin=.0025)
        self.assertEqual(bias.score([row],"opportunity"),[(-.002,3.0)])
        self.assertEqual(bias.score([row],"watch"),[(.002,3.0)])
        conservative=FrozenGateBrain(base,"BANDIT",q_by_regime={"range":-.001,"up":.0004})
        self.assertEqual(conservative.score([row],"opportunity"),[(-1.0,3.0)])
        self.assertEqual(conservative.score([dict(row,regime="up")],"opportunity"),[(.002,3.0)])

    def test_only_labels_matured_before_calibration_cutoff(self):
        c=sqlite3.connect(":memory:")
        c.row_factory=sqlite3.Row
        c.executescript(SCHEMA)
        self.addCleanup(c.close)
        april=month_start("2026-04")
        may=month_start("2026-05")
        data=[]
        opportunities=[]
        for j in range(650):
            t=april+j*3600000
            if t>=may:break
            for symbol in ("BTCUSDT","ETHUSDT"):
                data.append((t,symbol,"LONG","test","range","{}","a"*64))
                # The ETH label for the first event matures after the cutoff;
                # filtering by decision timestamp alone would wrongly include it.
                available=may+1 if j==0 and symbol=="ETHUSDT" else t+300000
                opportunities.append((t,available,symbol,"LONG","test","range","{}",.0005,
                                       0.01,-0.01,available,"HORIZON","COARSE_5M_OHLC_PATH_PROXY","a"*64))
        c.executemany("INSERT INTO candidate VALUES(?,?,?,?,?,?,?)",data)
        c.executemany("INSERT INTO opportunity VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",opportunities)
        result=calibration_april(c,DummyBrain(),april,may)
        self.assertEqual(result["n"],len(opportunities)-1)
        self.assertAlmostEqual(result["bias"],.0015)
        self.assertEqual(result["outcomes_matured_before_ms"],may)


if __name__=="__main__":
    unittest.main()
