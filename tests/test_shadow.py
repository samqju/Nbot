import ast
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nbot.observation.shadow import (ShadowBook, ShadowConfig, advance_bar, shadow_report,
                                    VERSION, AUTHORITY, verified, encode, digest)
from nbot.observation.candidate_setups import BY_ID
from tests.communication.test_v35_control_target import database, seed_event, NOW, SHA
from tests import test_learned_testnet as fixtures


def position(side="LONG"):
    return dict(status="PENDING",side=side,next_bar_ms=300000,bid=100.,ask=100.,
                config=asdict(ShadowConfig(slippage_pct=0,taker_fee_rate=0)),spread_half_frac=0)


class ShadowMathTests(unittest.TestCase):
    def test_long_staircase_and_fees(self):
        p,_=advance_bar(position(),(300000,100,102.2,99.5,102))
        self.assertEqual(p["stop"],101)
        p,reason=advance_bar(p,(600000,102,102.5,100,101))
        self.assertEqual(reason,"STOP")
        self.assertAlmostEqual(p["net_usd"],10)
        p=position();p["config"]=asdict(ShadowConfig())
        p,_=advance_bar(p,(300000,100,100.2,98,99))
        self.assertLess(p["net_usd"],-10)

    def test_short_staircase(self):
        p,_=advance_bar(position("SHORT"),(300000,100,100.5,97.8,98))
        self.assertEqual(p["stop"],99)
        p,reason=advance_bar(p,(600000,98,100,97.5,99))
        self.assertEqual(reason,"STOP")
        self.assertAlmostEqual(p["net_usd"],10)

    def test_stop_first_when_both_extremes_cross(self):
        p,reason=advance_bar(position(),(300000,100,110,98,109))
        self.assertEqual(reason,"STOP")
        self.assertEqual(p["net_usd"],-10)

    def test_new_stop_only_applies_next_bar_and_ambiguity_is_recorded(self):
        p,reason=advance_bar(position(),(300000,100,103.2,99.5,101))
        self.assertIsNone(reason)
        self.assertEqual(p["stop"],102)
        self.assertEqual(p["ambiguous_bars"],1)
        p,reason=advance_bar(p,(600000,101,102,100,101))
        self.assertEqual(reason,"STOP")
        self.assertEqual(p["exit_price"],101) # adverse gap, not ideal stop fill

    def test_delayed_entry_with_excessive_price_drift_is_not_filled(self):
        p,reason=advance_bar(position(),(300000,105,106,104,105))
        self.assertEqual(reason,"ENTRY_DRIFT_REJECTED")
        self.assertNotIn("net_usd",p)

    def test_invalid_candles_fail_closed(self):
        for bar in ((300001,100,101,99,100),(300000,100,99,98,100),(300000,100,101,99,float("nan"))):
            with self.assertRaises(ValueError):
                advance_bar(position(),bar)

    def test_config_validation(self):
        for settings in ({"risk_usd":0},{"risk_usd":1000},{"taker_fee_rate":1},{"notional_usd":float("inf")}):
            with self.assertRaises(ValueError):
                ShadowConfig(**settings)

    def test_no_order_transport_imports(self):
        path=Path(__file__).parents[1]/"nbot/observation/shadow.py"
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0],{"requests","urllib","socket"})
                self.assertFalse((node.module or "").startswith(("nbot.execution","nbot.exchange")))
            if isinstance(node,ast.Import):
                self.assertFalse(any(n.name.startswith(("requests","urllib","socket","nbot.exchange","nbot.execution")) for n in node.names))


class ShadowBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=database(Path(self.tmp.name),"live-paper")
        self.event=seed_event(self.db)
        self.book=ShadowBook(self.db,release_sha=SHA,profile="live-paper")
        self.names=list(BY_ID)
        self.opps=[dict(candidate_id=name,symbol="BTCUSDT",side="LONG",score=2.,bid=100.,ask=100.1) for name in self.names]

    def offer(self,opps=None,excluded=(),book=None,now=NOW):
        (book or self.book).offer(event_ms=self.event+(now-NOW),now_ms=now,
                                 opportunities=self.opps if opps is None else opps,excluded=excluded)

    def active(self):
        with self.db.connection() as conn:
            return [verified(*r) for r in conn.execute("SELECT state_json,digest FROM shadow_positions")]

    def results(self):
        with self.db.connection() as conn:
            return [verified(*r) for r in conn.execute("SELECT result_json,digest FROM shadow_results")]

    def candle(self,t,o=100.,h=100.5,l=98.,c=99.):
        # Collector fixture creates complete events and valid public evidence.
        seed_event(self.db,captured_at_ms=t+300000+500)
        with self.db.connection() as conn:
            conn.execute("UPDATE candles_5m SET open_price=?,high_price=?,low_price=?,close_price=? WHERE event_open_ms=? AND symbol='BTCUSDT'",
                         (o,h,l,c,t))

    def test_global_ten_slots_and_one_per_candidate_across_profiles(self):
        self.offer(excluded=[self.names[0]])
        self.assertEqual(len(self.active()),10)
        self.assertNotIn(self.names[0],{p["candidate_id"] for p in self.active()})
        other=ShadowBook(self.db,release_sha=SHA,profile="live-trade")
        self.offer(book=other)
        self.assertEqual(len(self.active()),10)
        self.assertEqual(len({p["candidate_id"] for p in self.active()}),10)

    def test_concurrent_profiles_share_one_slot_budget(self):
        from concurrent.futures import ThreadPoolExecutor
        other=ShadowBook(self.db,release_sha=SHA,profile="live-trade")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.offer,book=book) for book in (self.book,other)]
            for future in futures: future.result()
        self.assertEqual(len(self.active()),10)

    def test_unresolved_main_candidate_is_reserved_until_veto(self):
        from nbot.observation.recommendation import ObservationControlTarget
        from nbot.config.profiles import get_profile
        ObservationControlTarget(self.db,get_profile("live-paper"),release_sha=SHA)
        name=self.names[0]
        value={"experiment_context":{"shadow_main_candidate":name}}
        with self.db.connection() as conn:
            conn.execute("INSERT INTO served_execution_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("P","live-paper","LIVE","LIVE",encode(value),digest(value),NOW,NOW,1,None,None,None))
        self.offer(opps=[self.opps[0]])
        self.assertEqual(self.active(),[])
        with self.db.connection() as conn:
            conn.execute("INSERT INTO execution_veto_feedback VALUES(?,?,?,?,?)",("P","E","R","VETO",NOW))
        self.offer(opps=[self.opps[0]],now=NOW+300000)
        self.assertEqual(len(self.active()),1)

    def test_under_tested_candidates_get_slots_before_completed_ones(self):
        self.offer()
        first={p["candidate_id"] for p in self.active()}
        t=self.active()[0]["next_bar_ms"]; self.candle(t)
        self.book.advance(now_ms=t+301000)
        self.offer(now=NOW+900000)
        self.assertTrue(first.isdisjoint({p["candidate_id"] for p in self.active()}))

    def test_event_replay_restart_and_no_predecision_entry(self):
        self.offer()
        before=self.active()
        self.offer(book=ShadowBook(self.db,release_sha=SHA,profile="live-paper"))
        self.assertEqual(before,self.active())
        self.assertTrue(all(p["next_bar_ms"]>NOW for p in before))
        self.book.advance(now_ms=NOW)
        self.assertTrue(all(p["status"]=="PENDING" for p in self.active()))

    def test_future_candle_not_consumed_then_stop_results_once(self):
        self.offer()
        t=self.active()[0]["next_bar_ms"]
        self.candle(t)
        self.book.advance(now_ms=t+1000)
        self.assertEqual(len(self.active()),10)
        self.assertEqual(self.results(),[])
        self.book.advance(now_ms=t+300001)
        self.assertEqual(self.results(),[]) # capture not available yet
        self.book.advance(now_ms=t+301000)
        self.assertEqual(len(self.active()),0)
        self.assertEqual(len(self.results()),10)
        self.assertTrue(all(p["eligible"] and p["net_usd"]<0 for p in self.results()))
        self.book.advance(now_ms=t+302000)
        self.assertEqual(len(self.results()),10)

    def test_gap_is_unscorable_not_fabricated_profit(self):
        self.offer()
        t=self.active()[0]["next_bar_ms"]
        self.candle(t+300000)
        self.book.advance(now_ms=t+601000)
        self.assertEqual(len(self.results()),10)
        self.assertTrue(all(not p["eligible"] and "net_usd" not in p for p in self.results()))

    def test_config_changes_cannot_silently_mix_one_experiment(self):
        with self.assertRaisesRegex(ValueError,"CONFIG_CHANGED"):
            ShadowBook(self.db,release_sha=SHA,profile="live-paper",config=ShadowConfig(risk_usd=5))
        ShadowBook(self.db,release_sha="b"*40,profile="live-paper",config=ShadowConfig(risk_usd=5))

    def test_corrupt_state_fails_closed_without_reset(self):
        self.offer()
        with self.db.connection() as conn:
            conn.execute("UPDATE shadow_positions SET digest='bad'")
        with self.assertRaisesRegex(ValueError,"DIGEST"):
            self.book.advance(now_ms=NOW)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM shadow_positions").fetchone()[0],10)

    def test_daily_floor_sticky_restart_independent_and_utc_reset(self):
        cfg=asdict(ShadowConfig(daily_trigger_r=2,normal_giveback_r=3,profit_giveback_r=1))
        with self.db.connection() as conn:
            a=self.book._daily(conn,self.names[0],NOW,config=cfg,pnl=30)
            self.assertEqual(a["floor_usd"],20)
            a=self.book._daily(conn,self.names[0],NOW,config=cfg,pnl=-11)
            self.assertTrue(a["halted"])
            self.assertFalse(self.book._daily(conn,self.names[1],NOW,config=cfg)["halted"])
        new=ShadowBook(self.db,release_sha=SHA,profile="live-paper")
        with self.db.connection() as conn:
            self.assertTrue(new._daily(conn,self.names[0],NOW,config=cfg)["halted"])
            self.assertFalse(new._daily(conn,self.names[0],NOW+86400000,config=cfg)["halted"])

    def test_blocked_daily_candidate_does_not_open(self):
        with self.db.connection() as conn:
            self.book._daily(conn,self.names[0],NOW,pnl=-1000)
        self.offer()
        self.assertNotIn(self.names[0],{p["candidate_id"] for p in self.active()})

    def test_no_negative_or_stale_or_wide_spread_entries(self):
        self.offer(opps=[dict(self.opps[0],score=-1),dict(self.opps[1],ask=120)])
        self.assertEqual(self.active(),[])
        self.book.offer(event_ms=self.event,now_ms=NOW+60000,opportunities=self.opps)
        self.assertEqual(self.active(),[])

    def test_main_reservation_cancels_shadow_without_inventing_outcome(self):
        self.offer()
        name=self.active()[0]["candidate_id"]
        self.offer(excluded=[name],now=NOW+300000)
        cancelled=[p for p in self.results() if p["candidate_id"]==name]
        self.assertEqual(len(cancelled),1)
        self.assertFalse(cancelled[0]["eligible"])
        self.assertEqual(cancelled[0]["reason"],"MAIN_CANDIDATE_RESERVED")
        self.assertNotIn(name,{p["candidate_id"] for p in self.active()})

    def test_results_report_is_separate_readonly_and_capped(self):
        self.offer()
        t=self.active()[0]["next_bar_ms"]; self.candle(t)
        self.book.advance(now_ms=t+301000)
        text=shadow_report(self.db,release_sha=SHA)
        self.assertIn("adjust paper ranking at reduced weight",text)
        self.assertIn("Alongside live-trade",text)
        self.assertIn("Global reserved slots: 0 / 10",text)
        self.assertEqual(len(self.results()),10)
        with self.db.connection() as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM sqlite_master WHERE name='paper_feedback_samples'").fetchone())


class ShadowSourceTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.LearnedTestnetTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_both_mainnet_modes_have_shadows_but_testnet_does_not(self):
        from nbot.observation.learned_recommendation import LearnedTestnetSource
        self.assertIsNone(self.f.source.shadow)
        for mode in ("live-paper","live-trade"):
            source=LearnedTestnetSource(self.f.live,release_sha=SHA,profile_name=mode,
                                       memory_path=self.f.training.memory.path)
            self.assertIsNotNone(source.shadow)
            rules=[BY_ID[name].tag() for name in list(BY_ID)[:12]]
            with patch("nbot.observation.learned_recommendation.matches",return_value=rules):
                snapshot=source.refresh(now_ms=NOW,ttl_ms=30000)
            self.assertIsNotNone(snapshot.proposal)
            self.assertIn(snapshot.proposal.experiment_context["shadow_main_candidate"],BY_ID)
        with self.f.live.connection() as conn:
            self.assertLessEqual(conn.execute("SELECT COUNT(*) FROM shadow_positions").fetchone()[0],10)

    def test_shadow_failure_does_not_block_main_recommendation(self):
        from nbot.observation.learned_recommendation import LearnedTestnetSource
        source=LearnedTestnetSource(self.f.live,release_sha=SHA,profile_name="live-trade",
                                   memory_path=self.f.training.memory.path)
        with patch.object(source.shadow,"advance",side_effect=ValueError("corrupt")),self.assertLogs(level="ERROR"):
            result=source.refresh(now_ms=NOW,ttl_ms=30000)
        self.assertIsNotNone(result.proposal)

    def test_shadow_history_failure_does_not_block_live_recommendation(self):
        from nbot.observation.learned_recommendation import LearnedTestnetSource
        source=LearnedTestnetSource(self.f.live,release_sha=SHA,profile_name="live-trade",
                                   memory_path=self.f.training.memory.path)
        with patch("nbot.observation.learned_recommendation.load_histories",side_effect=ValueError("bad candle")),self.assertLogs(level="ERROR"):
            result=source.refresh(now_ms=NOW,ttl_ms=30000)
        self.assertIsNotNone(result.proposal)
        self.assertIn("bad candle",source.shadow_error)

    def test_disable_switch(self):
        from nbot.observation.learned_recommendation import LearnedTestnetSource
        with patch.dict("os.environ",{"NBOT_SHADOW_ENABLED":"0"}):
            source=LearnedTestnetSource(self.f.live,release_sha=SHA,profile_name="live-paper",
                                       memory_path=self.f.training.memory.path)
        self.assertIsNone(source.shadow)


if __name__=="__main__": unittest.main()
