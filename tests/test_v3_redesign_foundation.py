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
        self.assertEqual(len(shards), 4)
        self.assertTrue(all(len(s.streams) <= 180 for s in shards))

    def test_binance_2026_stream_categories_use_separate_endpoints(self):
        shards = plan_combined_streams(["BTCUSDT", "ETHUSDT"])
        self.assertEqual(len(shards), 2)
        public_shard = next(s for s in shards if "/public/stream?streams=" in s.combined_url)
        market_shard = next(s for s in shards if "/market/stream?streams=" in s.combined_url)
        self.assertEqual(
            public_shard.streams,
            ("btcusdt@bookTicker", "ethusdt@bookTicker"),
        )
        self.assertEqual(
            market_shard.streams,
            ("btcusdt@aggTrade", "ethusdt@aggTrade"),
        )
        self.assertTrue(all("@aggTrade" not in s for s in public_shard.streams))
        self.assertTrue(all("@bookTicker" not in s for s in market_shard.streams))
        self.assertTrue(all("fstream.binance.com/stream?streams=" not in s.combined_url for s in shards))


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

    def test_no_stop_path_resolves_at_horizon(self):
        events=self.ev([100,100.2,100.4])
        out=replay_policy(events,symbol="BTCUSDT",side="LONG",entry_price=100,one_r_price=1,
                          entry_time_ms=1000,policy=TrailPolicy.TICK_INTEGER_R,
                          costs=ReplayCosts(taker_fee_rate=0),horizon_ms=10_000)
        self.assertEqual(out.exit_reason,"HORIZON")
        self.assertAlmostEqual(out.gross_r,.4)
        self.assertAlmostEqual(out.net_r,.4)

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
        self.assertEqual(book.buffered_event_count(),0)
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


from nbot.observation.sampling import SamplingCandidate, stratified_sample
from nbot.observation.redesign_runtime import V3ResearchRuntime
from nbot.observation.wss_transport import decode_combined_message


class SamplingRuntimeTests(unittest.TestCase):
    def test_stratified_sampling_includes_disagreement(self):
        rows=[SamplingCandidate(f"d{i}","e",f"S{i}USDT","LONG","a" if i%2 else "b",.09,.08,
                                ridge_score_r=.09 if i else .01,ml_score_r=.09,
                                volatility_bucket="H" if i%3 else "L")
              for i in range(12)]
        selected=stratified_sample(rows,capacity=4,seed="x")
        self.assertIn("d0",selected)
        self.assertEqual(len(selected),4)
        self.assertTrue(all(0<p<=1 for p in selected.values()))

    def test_integrated_runtime_keeps_actual_separate(self):
        with tempfile.TemporaryDirectory() as td:
            rt=V3ResearchRuntime(Path(td)/"research_memory.db")
            d=DecisionLedgerTests().decision()
            h=ReplayHypothesis("d1","BTCUSDT","LONG",100,1,1000,TrailPolicy.TICK_INTEGER_R,
                               horizon_ms=10,costs=ReplayCosts(taker_fee_rate=0))
            rt.submit(d,h)
            for e in [TradeEvent("BTCUSDT",0,1000,100),TradeEvent("BTCUSDT",1,1001,99)]:
                rt.ingest_trade(e)
            matured=rt.mature_due(now_ms=2000)
            self.assertIn("d1",matured)
            rt.record_actual_execution(MaturedOutcome(
                "d1","ACTUAL_PAPER",2001,"ACTUAL_EXECUTION","STOP",-.8,0,-1,"x",True,"p1"))
            self.assertEqual(rt.ledger.counts()["actual_execution"],1)
            with self.assertRaises(RuntimeError):
                rt.submit_order()

    def test_combined_stream_decoder(self):
        data=decode_combined_message('{"stream":"btcusdt@bookTicker","data":{"e":"bookTicker","s":"BTCUSDT"}}')
        self.assertEqual(data["s"],"BTCUSDT")


from nbot.observation.aggtrade_recovery import recover_agg_trades
from nbot.observation.coarse_replay import OhlcBar, replay_coarse_bars


class RecoveryFallbackTests(unittest.TestCase):
    def test_bounded_aggtrade_recovery(self):
        class Resp:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return b'[{"a":5,"T":1000,"p":"100"},{"a":6,"T":1001,"p":"101"}]'
        rows=recover_agg_trades("BTCUSDT",first_id=5,last_id=6,urlopen_fn=lambda *args,**kwargs:Resp())
        self.assertEqual([row.trade_id for row in rows],[5,6])

    def test_five_minute_tick_path_is_ambiguous_when_order_unknown(self):
        bar=OhlcBar(0,300_000,100,102,99,101)
        outcome=replay_coarse_bars([bar],side="LONG",entry_price=100,one_r_price=1,
                                   policy=TrailPolicy.TICK_INTEGER_R)
        self.assertEqual(outcome.quality,EvidenceQuality.FIVE_MINUTE_AMBIGUOUS)
        self.assertIsNone(outcome.net_r)

    def test_bar_close_policy_can_resolve_same_ohlc(self):
        bar=OhlcBar(0,300_000,100,102,99,101)
        outcome=replay_coarse_bars([bar],side="LONG",entry_price=100,one_r_price=1,
                                   policy=TrailPolicy.BAR_CLOSE_INTEGER_R)
        self.assertEqual(outcome.gross_r,-1)
        self.assertFalse(outcome.ambiguous)


from nbot.observation.decision_analysis import DecisionEvaluationRow, compare_thresholds, disagreement_report


class DecisionAnalysisTests(unittest.TestCase):
    def test_disagreement_and_threshold_reports_are_research_only(self):
        rows=[DecisionEvaluationRow("e1",1,.10,.01,.01,-1,False),
              DecisionEvaluationRow("e2",2,.01,.10,.10,.5,True),
              DecisionEvaluationRow("e3",3,.12,.11,.11,.8,True)]
        report=disagreement_report(rows)
        self.assertEqual(report["disagreements"],2)
        grid=compare_thresholds(rows)
        self.assertTrue(grid)
        self.assertTrue(all(row["authority"]=="RESEARCH_EVALUATION_ONLY_NO_AUTO_DEPLOY" for row in grid))


from nbot.observation.watch_planner import WatchCandidate, plan_two_tier_watch
from nbot.observation.two_tier_runtime import TwoTierV3ResearchRuntime


class TwoTierWatchTests(unittest.TestCase):
    def candidates(self, count=40):
        rows=[]
        for i in range(count):
            rows.append(WatchCandidate(
                symbol=f"S{i:03d}USDT",
                conservative_score_r=.12 if i < 20 else (.08 if i < 30 else .02),
                threshold_r=.08,
                setup_id=f"setup{i%4}",
                volatility_bucket=("HIGH","MID","LOW")[i%3],
                ridge_score_r=.10 if i%7 else .02,
                ml_score_r=.10,
                approved=i < 8,
            ))
        return rows

    def test_broad_100_and_high_res_20(self):
        broad=[f"S{i:03d}USDT" for i in range(140)]
        plan=plan_two_tier_watch(broad_symbols=broad,candidates=self.candidates(140))
        self.assertEqual(len(plan.broad_symbols),100)
        self.assertEqual(len(plan.high_res_symbols),20)

    def test_active_symbols_are_sticky_and_share_stream(self):
        broad=[f"S{i:03d}USDT" for i in range(100)]
        active=["S090USDT","S091USDT"]
        plan=plan_two_tier_watch(broad_symbols=broad,candidates=self.candidates(100),
                                 active_high_res_symbols=active)
        self.assertEqual(plan.high_res_symbols[:2],tuple(sorted(active)))
        self.assertEqual(plan.reasons["S090USDT"],"ACTIVE_HYPOTHESIS_STICKY")

    def test_active_symbol_survives_broad_pool_rotation(self):
        broad=[f"S{i:03d}USDT" for i in range(100)]
        candidates=self.candidates(100)
        plan=plan_two_tier_watch(
            broad_symbols=broad,
            candidates=candidates,
            active_high_res_symbols=["LEGACYUSDT"],
        )
        self.assertIn("LEGACYUSDT",plan.high_res_symbols)
        self.assertEqual(plan.reasons["LEGACYUSDT"],"ACTIVE_HYPOTHESIS_STICKY")
        self.assertLessEqual(len(plan.high_res_symbols),20)

    def test_selection_preserves_learning_mix(self):
        broad=[f"S{i:03d}USDT" for i in range(100)]
        candidates=[]
        for i in range(10):
            candidates.append(WatchCandidate(f"S{i:03d}USDT",.20,.08,"strong","MID",.20,.20,True))
        for i in range(10,14):
            candidates.append(WatchCandidate(f"S{i:03d}USDT",.04,.08,"disagree","HIGH",.12,.02,False))
        for i in range(14,18):
            candidates.append(WatchCandidate(f"S{i:03d}USDT",.075,.08,"edge","LOW",.07,.07,False))
        for i in range(18,30):
            candidates.append(WatchCandidate(f"S{i:03d}USDT",.01,.08,f"setup{i%3}",("HIGH","LOW")[i%2],.01,.01,False))
        plan=plan_two_tier_watch(broad_symbols=broad,candidates=candidates)
        reasons=set(plan.reasons.values())
        self.assertIn("STRONG_OR_APPROVED",reasons)
        self.assertIn("RIDGE_ML_DISAGREEMENT",reasons)
        self.assertIn("NEAR_THRESHOLD",reasons)
        self.assertTrue("SETUP_DIVERSITY" in reasons or "VOLATILITY_DIVERSITY" in reasons)

    def test_does_not_force_twenty_when_only_twelve_candidates_exist(self):
        broad=[f"S{i:03d}USDT" for i in range(100)]
        plan=plan_two_tier_watch(broad_symbols=broad,candidates=self.candidates(12))
        self.assertEqual(len(plan.high_res_symbols),12)

    def test_two_tier_runtime_refuses_precise_replay_outside_watch(self):
        with tempfile.TemporaryDirectory() as td:
            rt=TwoTierV3ResearchRuntime(Path(td)/"research.db",broad_target=100,high_res_cap=2)
            broad=["BTCUSDT","ETHUSDT","SOLUSDT"]
            candidates=[
                WatchCandidate("BTCUSDT",.2,.08,"a",approved=True),
                WatchCandidate("ETHUSDT",.1,.08,"b",approved=True),
                WatchCandidate("SOLUSDT",.01,.08,"c"),
            ]
            plan=rt.refresh_watch_plan(broad_symbols=broad,candidates=candidates)
            excluded=next(symbol for symbol in broad if symbol not in plan.high_res_symbols)
            setup={"BTCUSDT":"a","ETHUSDT":"b","SOLUSDT":"c"}[excluded]
            score={"BTCUSDT":.2,"ETHUSDT":.1,"SOLUSDT":.01}[excluded]
            d=FrozenDecision("excluded-d","e2",1000,excluded,"LONG",setup,"abc","model","fd",
                             score,score,score,score,3,.02,-.01,False,"CAPACITY_TEST",100,101,
                             "WSS_BOOK","TICK_INTEGER_R_V1",1.0,True)
            h=ReplayHypothesis("excluded-d",excluded,"LONG",100,1,1000,TrailPolicy.TICK_INTEGER_R)
            rt.submit(d,h)
            self.assertEqual(rt.replays.active_count,0)
            self.assertEqual(rt.ledger.counts()["unresolved"],1)

    def test_high_res_streams_only_cover_admitted_symbols(self):
        with tempfile.TemporaryDirectory() as td:
            rt=TwoTierV3ResearchRuntime(Path(td)/"research.db",broad_target=100,high_res_cap=20)
            broad=[f"S{i:03d}USDT" for i in range(100)]
            rt.refresh_watch_plan(broad_symbols=broad,candidates=self.candidates(100))
            shards=rt.high_res_stream_shards()
            self.assertTrue(shards)
            subscribed={symbol for shard in shards for symbol in shard.symbols}
            self.assertEqual(subscribed,set(rt.watch_plan.high_res_symbols))
            self.assertEqual(sum(len(shard.streams) for shard in shards),40)

    def test_multiple_decisions_same_symbol_use_one_active_symbol(self):
        book=ResearchReplayBook()
        for i in range(7):
            book.add(ReplayHypothesis(f"btc-{i}","BTCUSDT","LONG",100,1,1000,
                                      TrailPolicy.TICK_INTEGER_R,horizon_ms=100))
        self.assertEqual(book.active_count,7)
        self.assertEqual(book.active_symbols,("BTCUSDT",))
        self.assertEqual(book.active_decisions_for_symbol("BTCUSDT"),7)


class LiveIntegrationSurfaceTests(unittest.TestCase):
    def test_live_observation_entrypoint_starts_two_tier_supervisor(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/"run_observation.py").read_text(encoding="utf-8")
        self.assertIn("LiveTwoTierResearchSupervisor",text)
        self.assertIn("NBOT_TWO_TIER_RESEARCH",text)
        self.assertNotIn("nbot.execution",text)
        self.assertNotIn("nbot.exchange",text)

    def test_websocket_is_normal_runtime_dependency(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/"requirements.txt").read_text(encoding="utf-8")
        self.assertIn("websockets==17.2",text.splitlines())


class TwoTierCurrentReleaseModelTests(unittest.TestCase):
    def test_live_scanner_has_separate_current_release_snapshot_path(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/"nbot/observation/live_two_tier.py").read_text(encoding="utf-8")
        self.assertIn('TWO_TIER_MODEL_PREFIX = "two_tier:ridge_snapshot:"',text)
        self.assertIn('"BROAD_COUNTERFACTUAL_RESEARCH_ONLY"',text)
        self.assertIn('"automatic_promotion": False',text)
        self.assertIn('"execution_authority": "NONE"',text)
        self.assertIn('"MODEL_FROZEN_WAIT_NEXT_EVENT"',text)

    def test_challenger_exposes_freeze_without_forcing_cycle(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/"nbot/observation/challengers.py").read_text(encoding="utf-8")
        self.assertIn("def ridge_model_artifact(self)",text)
        self.assertIn("model_artifact = self.ridge_model_artifact()",text)
