"""Causal rule fixtures and selected-candidate outcome attribution."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from nbot.observation import candidate_setups as c
from nbot.observation.paper_feedback import PaperFeedback, group_keys
from nbot.observation.paper_learning_report import paper_learning_report
from tests import test_paper_feedback as feedback_fixtures
from tests.communication.test_v35_control_target import NOW, SHA


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


class CandidateRuleTests(unittest.TestCase):
    def test_catalogue_unique_and_24_rules(self):
        self.assertEqual(len(c.REGISTRY),24)
        self.assertEqual(len(c.BY_ID),24)
        self.assertEqual(len(examples()),19)

    def test_known_long_and_short_patterns(self):
        vector={"ret_1h_side":.03,"btc_ret_1h_side":.01,"ret_15m_side":.01,"atr14_frac":.02,"candidate_btc_available":1}
        for name,b in examples().items():
            for side,history in (("LONG",b),("SHORT",mirrored(b))):
                with self.subTest(rule=name,side=side):
                    self.assertTrue(c.technical_conditions(history,side,vector)[name+"_V1"])

    def test_missing_btc_is_not_treated_as_zero_return(self):
        vector={"ret_1h_side":.03,"btc_ret_1h_side":0.,"ret_15m_side":.01,"atr14_frac":.02}
        self.assertFalse(c.technical_conditions(bars(),"LONG",vector)["BTC_RELATIVE_MOMENTUM_V1"])
        vector["candidate_btc_available"]=1
        self.assertTrue(c.technical_conditions(bars(),"LONG",vector)["BTC_RELATIVE_MOMENTUM_V1"])

    def test_flat_market_does_not_invent_patterns(self):
        for side in ("LONG","SHORT"):
            self.assertFalse(any(c.technical_conditions(bars(),side,{}).values()))
            self.assertFalse(any(c.technical_conditions(bars([100.5]*60),side,{}).values()))
            self.assertEqual(c.matches({},side,bars()),[])

    def test_legacy_five_remain_identifiable(self):
        cases = {
            "TREND_CONTINUATION":{"ret_4h_side":.02,"ret_15m_side":.01},
            "TREND_PULLBACK":{"ret_4h_side":.02,"ret_15m_side":-.01},
            "STRETCHED_REVERSAL":{"ret_4h_side":-.03,"ret_15m_side":.01},
            "VOLATILITY_EXPANSION":{"range_frac":.02,"ret_5m_side":.01},
            "RELATIVE_STRENGTH":{"ret_1h_percentile_side":.8},
        }
        for name,vector in cases.items():
            self.assertIn(name+"_V1",[item["id"] for item in c.matches(dict(vector,atr14_frac=.01),"LONG",[])])

    def test_missing_history_never_feeds_technical_rules(self):
        self.assertEqual(c.technical_conditions(bars()[:48],"LONG",{}),{})
        b=bars(); b[20]=(b[20][0]+1,*b[20][1:])
        with self.assertRaisesRegex(ValueError,"HISTORY_INVALID"):
            c.technical_conditions(b,"LONG",{})
        with self.assertRaisesRegex(ValueError,"HISTORY_LIMIT"):
            c.technical_conditions(bars([100.]*97),"LONG",{})

    def test_invalid_prices_volume_and_side_fail_closed(self):
        for index,value in ((1,float("nan")),(2,99),(3,101),(4,0),(5,-1)):
            b=bars(); row=list(b[-1]);row[index]=value;b[-1]=tuple(row)
            with self.subTest(index=index),self.assertRaises(ValueError):
                c.technical_conditions(b,"LONG",{})
        with self.assertRaises(ValueError):
            c.technical_conditions(bars(),"BUY",{})

    def test_tie_attribution_is_reproducible_and_not_alphabetical(self):
        ids=[item.id for item in c.REGISTRY]
        chosen={min(ids,key=lambda name:c.tie_key(t,"BTCUSDT","LONG",name)) for t in range(30)}
        self.assertGreater(len(chosen),5)
        self.assertEqual(c.tie_key(1,"BTCUSDT","LONG",ids[0]),c.tie_key(1,"BTCUSDT","LONG",ids[0]))

    def test_unconfirmed_swing_is_not_used(self):
        b=bars([90+i*.2 for i in range(60)])
        candle(b,-12,99.6,100,96,99.6)
        candle(b,-2,101.6,102,98,101.6)
        candle(b,-1,101.8,104,101,103)
        self.assertFalse(c.technical_conditions(b,"LONG",{})["CONFIRMED_SWING_CONTINUATION_V1"])


class CandidateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=feedback_fixtures.PaperFeedbackTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_history_query_excludes_future_and_rejects_gaps(self):
        with self.f.db.connection() as conn:
            event,symbol=conn.execute("SELECT event_open_ms,symbol FROM candles_5m ORDER BY event_open_ms DESC LIMIT 1").fetchone()
        before=c.load_histories(self.f.db,[symbol],event-300000)
        self.assertEqual(before[symbol][-1][0],event-300000)
        with self.f.db.connection() as conn:
            conn.execute("DELETE FROM candles_5m WHERE symbol=? AND event_open_ms=?",(symbol,event-600000))
        after=c.load_histories(self.f.db,[symbol],event)[symbol]
        self.assertEqual(len(after),2)
        self.assertEqual(c.technical_conditions(after,"LONG",{}),{})

    def test_selected_candidate_alone_receives_feedback(self):
        rule=c.BY_ID["DONCHIAN_BREAKOUT_V1"].tag()
        ctx=dict(self.f.proposal.experiment_context)
        ctx["paper_feedback"]=dict(ctx["paper_feedback"],candidate=rule,
                                  matched_candidates=[rule["id"],"VOLUME_BREAKOUT_V1"])
        self.f.proposal=replace(self.f.proposal,experiment_context=ctx)
        self.f.populate()
        model=self.f.feedback.snapshot(cutoff_ms=NOW)
        self.assertEqual(model["sample_count"],12)
        self.assertEqual(len(model["groups"]),2) # context + ALL, not two strategies
        self.assertTrue(all("DONCHIAN_BREAKOUT" in key for key in model["groups"]))
        self.assertTrue(all(group["trades"]==12 for group in model["groups"].values()))
        score,detail=PaperFeedback.adjust(model,{},"LONG",2.,candidate=rule)
        if self.f.proposal.side=="LONG":
            self.assertLess(score,2.)
        other,_=PaperFeedback.adjust(model,{},self.f.proposal.side,2.,candidate=c.BY_ID["VOLUME_BREAKOUT_V1"].tag())
        self.assertEqual(other,2.)
        report=paper_learning_report(self.f.db,release_sha=SHA,now_ms=NOW)
        self.assertIn("| DONCHIAN_BREAKOUT_V1 | BREAKOUT | 12 |",report)
        self.assertIn("| VOLUME_BREAKOUT_V1 | BREAKOUT | 0 |",report)

    def test_unknown_or_changed_candidate_contract_is_rejected(self):
        for rule in ({"id":"FAKE"},dict(c.BY_ID["EMA_CROSS_V1"].tag(),library="FUTURE")):
            with self.assertRaisesRegex(ValueError,"CANDIDATE_INVALID"):
                group_keys({"setup":"A","context":"B"},"LONG",rule)

    def test_overlapping_matches_produce_one_frozen_proposal(self):
        source=self.f.source
        with self.f.db.connection() as conn:
            conn.execute("DELETE FROM learned_live_paper_decisions")
        rules=[c.BY_ID["DONCHIAN_BREAKOUT_V1"].tag(),c.BY_ID["VOLUME_BREAKOUT_V1"].tag()]
        with patch("nbot.observation.learned_recommendation.matches",return_value=rules):
            first=source.refresh(now_ms=NOW,ttl_ms=30000)
            second=source.refresh(now_ms=NOW,ttl_ms=30000)
        self.assertIsNotNone(first.proposal)
        self.assertEqual(first,second)
        detail=first.proposal.experiment_context["paper_feedback"]
        self.assertEqual(len(detail["matched_candidates"]),2)
        self.assertIn(detail["candidate"],rules)
        with self.f.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learned_live_paper_decisions").fetchone()[0],1)


if __name__=="__main__":
    unittest.main()
