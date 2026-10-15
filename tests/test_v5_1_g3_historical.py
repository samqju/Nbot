"""Exact V4 historical positive fixture equivalence, offline no legacy imports.

Pinned fixture source: tests/test_candidate_setups.py blob
e5bb49e7541cf042dd1eb67914578e44db2a37e4, V4 commit
b1a3c4a8d2a82c994669df7adb0d345e0415ffbf.
No V4 implementation is imported into V5.1 runtime or tests.
"""
from __future__ import annotations
import unittest
from nbot_v5_1 import detector_rules as rules

def bars(closes=None):
    closes = closes or [100.] * 60
    return [(i*300000, x, x+.5, x-.5, x, 10.) for i,x in enumerate(closes)]


def candle(seq, index, o,h,l,close,v=10.):
    seq[index] = (seq[index][0],o,h,l,close,v)


def mirrored(seq):
    return [(t,300-o,300-l,300-h,300-close,v) for t,o,h,l,close,v in seq]


def examples():
    result={}
    b=bars(); candle(b,-1,100,103,99.8,102,30)
    for name in ("DONCHIAN_BREAKOUT","VOLUME_BREAKOUT","EMA_CROSS","MACD_CROSS","VWAP_RECLAIM"):
        result[name]=b
    b=bars(); candle(b,-2,100,102.5,99.8,102); candle(b,-1,101,103,100.5,102.5)
    result["BREAKOUT_RETEST"]=b
    b=bars(); candle(b,-1,99.6,101,99,100.8)
    result["FAILED_BREAKOUT"]=b
    b=bars(); candle(b,-1,99.6,100.7,99.5,100.5)
    result["RANGE_EDGE_REJECTION"]=b
    b=bars(); candle(b,-2,100,100.5,96.5,97); candle(b,-1,97,100.5,96.9,100)
    result["BOLLINGER_REENTRY"]=b
    b=bars([100-i*.1 for i in range(59)]+[98.])
    candle(b,-1,94.1,98.5,94,98)
    result["RSI_RECLAIM"]=b
    b=bars([90+i*.2 for i in range(60)]); candle(b,-1,101,103,99,102)
    result["EMA_PULLBACK"]=b
    result["MULTITIMEFRAME_TREND"]=b
    b=bars([100+(i%2)*2 for i in range(49)]+[101.]*10+[104.])
    result["SQUEEZE_BREAKOUT"]=b
    b=bars(); candle(b,-3,100,102,98,100); candle(b,-2,100,101,99,100); candle(b,-1,100,104,99.5,103)
    result["INSIDE_BAR_BREAKOUT"]=b
    b=bars(); candle(b,-2,101,102,99,100); candle(b,-1,99.5,103,98,102.5)
    result["OUTSIDE_BAR_REVERSAL"]=b
    result["ENGULFING_REVERSAL"]=b
    b=bars(); candle(b,-1,100,101,96,100.5)
    result["PIN_BAR_REJECTION"]=b
    b=bars([90+i*.2 for i in range(60)])
    candle(b,-12,99.6,100,96,99.6); candle(b,-6,100.8,101.3,98,100.8)
    candle(b,-1,101.8,104,101,103)
    result["CONFIRMED_SWING_CONTINUATION"]=b
    result["BTC_RELATIVE_MOMENTUM"]=bars()
    return result


class HistoricalDetectorParity(unittest.TestCase):
    def test_H01_catalog_exact_ids_5_plus_19(self):
        self.assertEqual(len(rules.REGISTRY),24)
        self.assertEqual(len({r.id for r in rules.REGISTRY}),24)
        self.assertEqual(len(examples()),19)
        self.assertEqual(tuple(r.id for r in rules.REGISTRY[:5]),
            ("TREND_CONTINUATION_V1","TREND_PULLBACK_V1","STRETCHED_REVERSAL_V1",
             "VOLATILITY_EXPANSION_V1","RELATIVE_STRENGTH_V1"))

    def test_H02_all_19_original_positive_rules_both_directions(self):
        vector={"ret_1h_side":.03,"btc_ret_1h_side":.01,"ret_15m_side":.01,
                "atr14_frac":.02,"candidate_btc_available":1}
        for name, history in examples().items():
            for side,bars_ in (("LONG",history),("SHORT",mirrored(history))):
                with self.subTest(detector=name,side=side):
                    results=rules.technical_conditions(bars_,side,vector)
                    self.assertEqual(len(results),19)
                    self.assertTrue(results[name+"_V1"],name+" "+side)

    def test_H03_all_five_original_context_tags_positive(self):
        cases={
            "TREND_CONTINUATION":{"ret_4h_side":.02,"ret_15m_side":.01},
            "TREND_PULLBACK":{"ret_4h_side":.02,"ret_15m_side":-.01},
            "STRETCHED_REVERSAL":{"ret_4h_side":-.03,"ret_15m_side":.01},
            "VOLATILITY_EXPANSION":{"range_frac":.02,"ret_5m_side":.01},
            "RELATIVE_STRENGTH":{"ret_1h_percentile_side":.8},
        }
        for name,vector in cases.items():
            with self.subTest(name=name):
                result=rules.describe(dict(vector,atr14_frac=.01))
                self.assertEqual(result["setup"],name)

    def test_H04_all_zero_flat_history_does_not_invent_rules(self):
        for side in ("LONG","SHORT"):
            self.assertFalse(any(rules.technical_conditions(bars(),side,{}).values()))

    def test_H05_unconfirmed_swing_not_lookahead(self):
        b=bars([90+i*.2 for i in range(60)])
        candle(b,-12,99.6,100,96,99.6)
        candle(b,-2,101.6,102,98,101.6)
        candle(b,-1,101.8,104,101,103)
        self.assertFalse(rules.technical_conditions(b,"LONG",{})["CONFIRMED_SWING_CONTINUATION_V1"])

    def test_H06_btc_missing_is_not_zero_proxy_match(self):
        vector={"ret_1h_side":.03,"btc_ret_1h_side":0.,
                "ret_15m_side":.01,"atr14_frac":.02}
        self.assertFalse(rules.technical_conditions(bars(),"LONG",vector)["BTC_RELATIVE_MOMENTUM_V1"])
        vector["candidate_btc_available"]=1
        self.assertTrue(rules.technical_conditions(bars(),"LONG",vector)["BTC_RELATIVE_MOMENTUM_V1"])

    def test_H07_bounded_history_gap_and_bad_prices(self):
        self.assertEqual(rules.technical_conditions(bars()[:48],"LONG",{}),{})
        b=bars()
        b[20]=(b[20][0]+1,*b[20][1:])
        with self.assertRaises(ValueError):rules.technical_conditions(b,"LONG",{})
        b=bars()
        candle(b,-1,100,100,101,100)
        with self.assertRaises(ValueError):rules.technical_conditions(b,"LONG",{})
        with self.assertRaises(ValueError):rules.technical_conditions(bars(),"BUY",{})


if __name__ == "__main__":unittest.main()
