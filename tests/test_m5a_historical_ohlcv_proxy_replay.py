"""No-future-feature and conservative 2/3% touch tests for M5A 1h proxy."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import m5a_historical_ohlcv_proxy_replay as m

def fake(slope=0.0,base=100):
    rows=[]
    for i in range(50*24+50):
        v=base+i*slope
        rows.append([i*m.HOUR,v,v*1.004,v*.996,v,10_000_000])
    return ([x[0] for x in rows],rows)
class M5AHistoricalProxyTests(unittest.TestCase):
    def test_only_fully_closed_candles_enter_asof_features(self):
        data={"BTCUSDT":fake(0.0003)}
        t=46*24*m.HOUR
        a=m.features(data,t)
        self.assertIn("BTCUSDT",a)
        # Price movement after t, including the OPEN hour itself, can
        # never change a known as-of feature or score.
        ts,rows=data["BTCUSDT"]
        n=t//m.HOUR
        rows[n][2]=999999
        rows[n][4]=999999
        b=m.features(data,t)
        self.assertEqual(a,b)
    def test_initial_history_maturity_and_missing_bar_rejected(self):
        ts,bars=fake()
        self.assertNotIn("BTCUSDT",m.features({"BTCUSDT":(ts,bars)},40*24*m.HOUR))
        ts[45*24-1]-=m.HOUR
        self.assertNotIn("BTCUSDT",m.features({"BTCUSDT":(ts,bars)},45*24*m.HOUR))
    def test_one_per_review_price_label_conservative_when_both_hit(self):
        t=10*m.HOUR
        ts,bars=fake()
        i=t//m.HOUR
        bars[i][2]=104;bars[i][3]=96
        x=m.outcome((ts,bars),t,100,"long",.03)
        self.assertEqual(x["kind"],"LOSS_SAME_HOUR_AMBIGUOUS_STOP_FIRST")
        x=m.outcome((ts,bars),t,100,"short",.03)
        self.assertEqual(x["kind"],"LOSS_SAME_HOUR_AMBIGUOUS_STOP_FIRST")
    def test_target_long_and_short_hit_before_stop(self):
        t=10*m.HOUR
        ts,bars=fake()
        for i in range(t//m.HOUR,t//m.HOUR+24):
            bars[i][2]=101;bars[i][3]=99
        bars[t//m.HOUR+2][2]=103
        self.assertEqual(m.outcome((ts,bars),t,100,"long",.02)["kind"],"TARGET_FIRST")
        bars[t//m.HOUR+2][2]=101
        bars[t//m.HOUR+3][3]=97
        self.assertEqual(m.outcome((ts,bars),t,100,"short",.03)["kind"],"TARGET_FIRST")
    def test_no_future_candles_returns_unknown_not_winning(self):
        ts,bars=fake()
        self.assertIsNone(m.outcome((ts,bars),ts[-1],100,"long",.02))
    def test_rotation_pins_btc_caps_ten_and_requires_history(self):
        allcoins=["BTCUSDT"]+[f"C{i:03d}USDT" for i in range(24)]
        newcoins=[f"NEW{i:03d}USDT" for i in range(20)]
        feat={s:{"quality":0.1,"liquidity":0.1} for s in allcoins}
        feat.update({s:{"quality":0.9,"liquidity":0.9} for s in newcoins})
        since={s:0 for s in allcoins}
        result,changes,holds=m.choose(allcoins,feat,"quality",since,50*m.HOUR)
        self.assertEqual(len(result),25)
        self.assertEqual(len(changes),10)
        self.assertIn("BTCUSDT",result)
        self.assertEqual(len(set(result)&set(allcoins)),15)
        self.assertFalse(holds)
    def test_unknown_incumbent_tenure_cannot_rotate_discretionarily(self):
        allcoins=["BTCUSDT"]+[f"C{i:03d}USDT" for i in range(24)]
        feat={s:{"quality":0.1,"liquidity":0.1} for s in allcoins}
        feat.update({"NEWUSDT":{"quality":1,"liquidity":1}})
        proposal,changes,hold=m.choose(allcoins,feat,"quality",{},50*m.HOUR)
        self.assertEqual(proposal,allcoins)
        self.assertFalse(changes)
if __name__=="__main__":
    unittest.main()
