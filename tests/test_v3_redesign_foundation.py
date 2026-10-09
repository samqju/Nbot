import tempfile
import unittest
from pathlib import Path

from nbot.observation.calibration import CalibrationRow, chronological_split, policy_metrics, score_bins
from nbot.observation.chronological_replay import TradeEvent
from nbot.observation.counterfactual import EvidenceQuality, ReplayCosts, TrailPolicy, classify_rejected_outcome, replay_policy
from nbot.observation.decision_ledger import DecisionLedger, FrozenDecision, MaturedOutcome
from nbot.observation.research_replay import ReplayHypothesis, ResearchReplayBook
from nbot.observation.v3_universe import UniverseCandidate, select_universes
from nbot.observation.wss_market import MarketDataUnavailable, WssMarketState, plan_combined_streams


class WssStateTests(unittest.TestCase):
    def test_fresh_quote_and_gap_fail_closed(self):
        state = WssMarketState(["BTCUSDT"])
        state.mark_connected()
        state.ingest_book_ticker({"s":"BTCUSDT","E":1000,"b":"100","a":"101","u":1}, receipt_time_ms=1000)
        self.assertEqual(state.executable_quote("BTCUSDT", now_ms=1100, max_age_ms=500).bid, 100)
        state.ingest_agg_trade({"s":"BTCUSDT","a":10,"E":1000,"T":1000,"p":"100.5","q":"1","m":False}, receipt_time_ms=1000)
        state.ingest_agg_trade({"s":"BTCUSDT","a":12,"E":1001,"T":1001,"p":"100.6","q":"1","m":False}, receipt_time_ms=1001)
        with self.assertRaises(MarketDataUnavailable):
            state.executable_quote("BTCUSDT", now_ms=1100, max_age_ms=500)
        state.mark_recovered("BTCUSDT", through_aggregate_id=12)
        self.assertEqual(state.executable_quote("BTCUSDT", now_ms=1100, max_age_ms=500).ask, 101)

    def test_shards_bound_stream_count(self):
        shards = plan_combined_streams([f"S{i}USDT" for i in range(200)], max_streams_per_connection=180)
        self.assertEqual(len(shards), 3)
        self.assertTrue(all(len(s.streams) <= 180 for s in shards))


class DecisionLedgerTests(unittest.TestCase):
    def decision(self):
        return FrozenDecision("d1","e1",1000,"BTCUSDT","LONG","setup","abc","model","fd",
                              .1,.11,.08,.08,1,.07,.01,False,"EDGE_GAP_FAIL",100,101,"WSS_BOOK",
                              "TICK_INTEGER_R_V1",.5,True)

    def test_append_only_and_actual_separate(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=DecisionLedger(Path(td)/"ledger.db")
            ledger.record_decision(self.decision())
            with self.assertRaises(ValueError):
                ledger.record_decision(FrozenDecision(**{**self.decision().__dict__,"reason":"OTHER"}))
            research=MaturedOutcome("d1","TICK_INTEGER_R_V1",2000,"AGGTRADE_RESOLVED","STOP",1,.0,-1,"src")
            actual=MaturedOutcome("d1","ACTUAL_PAPER",2100,"ACTUAL_EXECUTION","STOP",.5,1,-1,"actual",True,"paper-1")
            ledger.record_outcome(research)
            ledger.record_outcome(actual)
            counts=ledger.counts()
            self.assertEqual(counts["rejected"],1)
            self.assertEqual(counts["matured_research"],1)
            self.assertEqual(counts["actual_execution"],1)


class CounterfactualTests(unittest.TestCase):
    def ev(self, prices):
        return [TradeEvent("BTCUSDT", i, 1000+i*1000, p) for i,p in enumerate(prices)]

    def test_tick_and_bar_close_are_not_silently_equal(self):
        events=self.ev([100,102,100.5,99])
        tick=replay_policy(events,symbol="BTCUSDT",side="LONG",entry_price=100,one_r_price=1,
                           entry_time_ms=1000,policy=TrailPolicy.TICK_INTEGER_R,costs=ReplayCosts(taker_fee_rate=0))
        bar=replay_policy(events,symbol="BTCUSDT",side="LONG",entry_price=100,one_r_price=1,
                          entry_time_ms=1000,policy=TrailPolicy.BAR_CLOSE_INTEGER_R,costs=ReplayCosts(taker_fee_rate=0))
        self.assertEqual(tick.gross_r,.5)
        self.assertEqual(bar.gross_r,-1)

    def test_gap_unresolved(self):
        events=[TradeEvent("BTCUSDT",1,1000,100),TradeEvent("BTCUSDT",3,1001,99)]
        out=replay_policy(events,symbol="BTCUSDT",side="LONG",entry_price=100,one_r_price=1,
                          entry_time_ms=1000,policy=TrailPolicy.TICK_INTEGER_R)
        self.assertEqual(out.quality,EvidenceQuality.GAP_UNRESOLVED)
        self.assertEqual(classify_rejected_outcome(approved=False,net_r=None,quality=out.quality),"UNRESOLVED")

    def test_uncapped_overlapping_book(self):
        book=ResearchReplayBook()
        for i in range(25):
            book.add(ReplayHypothesis(f"d{i}","BTCUSDT","LONG" if i%2==0 else "SHORT",100,1,1000,TrailPolicy.TICK_INTEGER_R,horizon_ms=10))
        self.assertEqual(book.active_count,25)
        for e in self.ev([100,99,101]):
            book.ingest(e)
        self.assertEqual(len(book.mature_due(now_ms=2000)),25)


class UniverseCalibrationTests(unittest.TestCase):
    def test_execution_is_subset_of_research(self):
        rows=[UniverseCandidate("AUSDT",10_000_000,.1,history_bars=1000),
              UniverseCandidate("BUSDT",9_000_000,.1,history_bars=1000)]
        out=select_universes(rows,research_size=2,execution_allowlist=["BUSDT","XUSDT"])
        self.assertEqual(out.research_symbols,("AUSDT","BUSDT"))
        self.assertEqual(out.execution_symbols,("BUSDT",))

    def test_calibration_uses_chronology_and_event_weighting(self):
        rows=[CalibrationRow("e1",1,.10,1,True),CalibrationRow("e1",1,.11,-1,True),
              CalibrationRow("e2",2,.09,.5,True),CalibrationRow("e3",3,.01,-.2,False,.5)]
        train,test=chronological_split(rows,train_fraction=.5)
        self.assertLessEqual(max(r.decision_time_ms for r in train),min(r.decision_time_ms for r in test))
        self.assertTrue(score_bins(rows))
        m=policy_metrics(rows,threshold_r=.08)
        self.assertEqual(m["selected"],3)
        self.assertEqual(m["distinct_selected_events"],2)


if __name__ == "__main__":
    unittest.main()
