"""G5 virtual Research state machine, 40-occupancy, actual event-time first touch.

All prices, quotes, sequence numbers and permits in these tests are SYNTHETIC.
No qualified G4 original source or scientifically scored G6 outcome is implied.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from nbot_v5_1.core import FiveMinuteEvent,INTERVAL_MS
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.research_intent import freeze_intent,from_record,ResearchHold
from nbot_v5_1.research_book import VirtualResearchBook,SyntheticTick
from nbot_v5_1.research_journal import ResearchJournal,JournalHold
from test_v5_1_g2 import manifest,END_OPEN,END_DECISION

SHA="a"*64
BASE=100


class G5ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="nbot-g5-test-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.journal=ResearchJournal(self.root/"research.jsonl")
        self.book=VirtualResearchBook(self.journal)
        self.universe=manifest(20)
        b=ObservationBook(self.universe)
        g3=explore_event(b,FiveMinuteEvent(END_OPEN,END_DECISION),capacity_slots=0)
        self.deep=choose_deep(self.universe,g3,count=20)
        self.event=FiveMinuteEvent(END_OPEN,END_DECISION)

    def plan(self,symbol="BTCUSDT",side="LONG",event=None,**changes):
        event=event or self.event
        default={"symbol":symbol,"side":side,"event_open_ms":event.event_open_ms,
          "declared_at_ms":event.decision_at_ms,"activates_at_ms":event.decision_at_ms+1,
          "entry_reference":"100","stop":"95" if side=="LONG" else "105",
          "target":"105" if side=="LONG" else "95","horizon_ms":INTERVAL_MS,
          "cohort_sha":self.deep.manifest_sha,"observation_sha":SHA,
          "source_epoch":1,"source_grade":"SYNTHETIC_OFFLINE_TEST_ONLY",
          "trail_activation_r":"0.5","trail_distance_r":"0.5"}
        default.update(changes)
        return freeze_intent(**default)

    def tick(self,price,*,symbol="BTCUSDT",id=1,t=None,epoch=1,complete=None):
        t=t if t is not None else END_DECISION+2
        complete=END_DECISION if complete is None else complete
        return SyntheticTick(symbol,t,str(price),epoch,id,complete)

    def admit(self,*plans):
        return self.book.review(self.event,self.deep,lambda:tuple(plans))

    def test_R01_one_active_each_coin_side_full_40(self):
        plans=[self.plan(s,side) for s in self.deep.symbols for side in ("LONG","SHORT")]
        result=self.admit(*plans)
        self.assertEqual(result.openings,40)
        self.assertEqual(self.book.occupied,40)
        self.assertEqual(self.book.vacancies,0)
        self.assertFalse(self.book.should_explore())
        self.assertEqual(len(self.book.by_pair),40)
        self.assertEqual(self.book.status()["qualified_after_cost"],0)

    def test_R02_full_book_never_runs_new_expensive_supplier(self):
        plans=[self.plan(s,x) for s in self.deep.symbols for x in ("LONG","SHORT")]
        self.admit(*plans)
        next_event=FiveMinuteEvent(END_OPEN+INTERVAL_MS,END_DECISION+INTERVAL_MS)
        calls=[]
        def expensive():
            calls.append(1)
            return ()
        r=self.book.review(next_event,self.deep,expensive)
        self.assertFalse(r.supplier_called)
        self.assertFalse(calls)
        self.assertEqual(r.openings,0)
        self.assertEqual(self.book.occupied,40)

    def test_R03_target_at_precise_10_03_before_refill_boundary(self):
        p=self.plan()
        self.admit(p)
        terminal=self.book.ingest(self.tick("105",id=1,t=END_DECISION+180000))
        self.assertEqual(len(terminal),1)
        self.assertEqual(terminal[0].reason,"TARGET")
        self.assertEqual(terminal[0].at_ms,END_DECISION+180000)
        self.assertEqual(terminal[0].economic_state,"COST_PENDING_UNQUALIFIED")
        self.assertIsNone(terminal[0].qualified_net_return)
        self.assertEqual(self.book.occupied,0)
        # Capacity is free, but NO new proposal may be admitted without
        # a NEW five-minute boundary review.
        self.assertEqual(self.book.last_review_ms,END_OPEN)

    def test_R04_stop_on_short_and_opposite_pair_same_market(self):
        self.admit(self.plan("BTCUSDT","LONG"),self.plan("BTCUSDT","SHORT"))
        hit=self.book.ingest(self.tick("105",id=1,t=END_DECISION+1000))
        self.assertEqual(len(hit),2)
        self.assertEqual({r.reason for r in hit},{"STOP","TARGET"})
        self.assertEqual({r.side for r in hit},{"LONG","SHORT"})
        self.assertEqual(self.book.occupied,0)

    def test_R05_trailing_long_only_tightens_and_then_stops(self):
        p=self.plan()
        self.admit(p)
        self.book.ingest(self.tick("103",id=1))
        stop=self.book.active[p.intent_id].stop
        self.assertGreater(stop,95)
        self.book.ingest(self.tick("102",id=2,t=END_DECISION+3000))
        self.assertEqual(self.book.active[p.intent_id].stop,stop)
        hits=self.book.ingest(self.tick("100",id=3,t=END_DECISION+4000))
        self.assertEqual(len(hits),1)
        self.assertEqual(hits[0].reason,"TRAILING_STOP")

    def test_R06_trailing_short_tightens_only_down(self):
        p=self.plan(side="SHORT")
        self.admit(p)
        self.book.ingest(self.tick("97",id=1))
        before=self.book.active[p.intent_id].stop
        self.assertLess(before,105)
        self.book.ingest(self.tick("98",id=2,t=END_DECISION+3000))
        self.assertEqual(self.book.active[p.intent_id].stop,before)
        hit=self.book.ingest(self.tick("100",id=3,t=END_DECISION+4000))
        self.assertEqual(len(hit),1)
        self.assertEqual(hit[0].reason,"TRAILING_STOP")

    def test_R07_source_aggregate_gap_holds_and_retains_slot(self):
        p=self.plan()
        self.admit(p)
        self.book.ingest(self.tick("100",id=1))
        hit=self.book.ingest(self.tick("106",id=3,t=END_DECISION+5000))
        self.assertEqual(hit,())
        self.assertEqual(self.book.active[p.intent_id].state,"SOURCE_HOLD")
        self.assertEqual(self.book.occupied,1)
        self.assertNotIn(p.intent_id,self.book.closed)

    def test_R08_epoch_restart_holds_both_directions_and_no_score(self):
        a=self.plan(side="LONG");b=self.plan(side="SHORT")
        self.admit(a,b)
        self.book.ingest(self.tick("100",id=1))
        self.book.ingest(self.tick("105",id=2,epoch=2,t=END_DECISION+1000))
        self.assertEqual(self.book.status()["held"],2)
        self.assertEqual(self.book.occupied,2)
        self.assertFalse(self.book.closed)

    def test_R09_recovery_never_assumes_unsynced_trailing_or_lost_path(self):
        p=self.plan()
        self.admit(p)
        self.book.ingest(self.tick("103",id=1))
        self.assertGreater(self.book.active[p.intent_id].stop,95)
        recovered=VirtualResearchBook(self.journal)
        self.assertEqual(recovered.occupied,1)
        self.assertEqual(recovered.active[p.intent_id].state,"RESTART_HOLD")
        self.assertEqual(recovered.status()["qualified_after_cost"],0)
        self.assertEqual(recovered.closed,{})
        again=VirtualResearchBook(self.journal)
        self.assertEqual(again.occupied,1)
        self.assertEqual(again.status()["held"],1)

    def test_R10_horizon_maturity_requires_consecutive_coverage(self):
        p=self.plan()
        self.admit(p)
        self.book.ingest(self.tick("100",id=1))
        result=self.book.ingest(self.tick("101",id=2,t=p.expires_at_ms+1))
        self.assertEqual(result[0].reason,"HORIZON")
        self.assertEqual(result[0].at_ms,p.expires_at_ms)
        self.assertEqual(result[0].reference_price,"100")
        self.assertEqual(result[0].economic_state,"COST_PENDING_UNQUALIFIED")

    def test_R11_horizon_without_any_verified_prior_path_holds(self):
        p=self.plan()
        self.admit(p)
        self.book.ingest(self.tick("106",id=1,t=p.expires_at_ms+1))
        self.assertEqual(self.book.occupied,1)
        self.assertEqual(self.book.active[p.intent_id].state,"SOURCE_HOLD")

    def test_R12_no_forced_replacement_without_valid_proposals(self):
        self.assertEqual(self.admit().openings,0)
        next_event=FiveMinuteEvent(END_OPEN+INTERVAL_MS,END_DECISION+INTERVAL_MS)
        out=self.book.review(next_event,self.deep,lambda:())
        self.assertEqual(out.openings,0)
        self.assertEqual(self.book.vacancies,40)

    def test_R13_refill_exactly_next_completed_5m_event(self):
        self.admit(self.plan("BTCUSDT","LONG"))
        self.book.ingest(self.tick("105",id=1))
        next_event=FiveMinuteEvent(END_OPEN+INTERVAL_MS,END_DECISION+INTERVAL_MS)
        p=self.plan("BTCUSDT","LONG",next_event)
        out=self.book.review(next_event,self.deep,lambda:(p,))
        self.assertEqual(out.openings,1)
        self.assertEqual(self.book.occupied,1)
        self.assertNotEqual(p.intent_id,next(iter(self.book.closed)))

    def test_R14_duplicate_same_boundary_is_idempotent_and_no_supplier(self):
        p=self.plan();self.admit(p)
        calls=[]
        def proposed():
            calls.append(1);return (p,)
        result=self.book.review(self.event,self.deep,proposed)
        self.assertEqual(result.openings,0)
        self.assertFalse(result.supplier_called)
        self.assertEqual(calls,[])
        self.assertEqual(self.book.occupied,1)

    def test_R15_no_pattern_tags_duplicate_existing_coin_side(self):
        p=self.plan()
        with self.assertRaises(ResearchHold):
            self.admit(p,p)
        self.assertEqual(self.book.occupied,0)

    def test_R16_stale_or_outside_deep_cohort_is_rejected(self):
        outside=next(s for s in self.universe.symbols if s not in self.deep.symbols) if len(self.universe.symbols)>20 else "NONEXISTENTUSDT"
        out=self.admit(self.plan(outside))
        self.assertEqual(out.openings,0)
        self.assertEqual(out.skipped_ineligible,1)

    def test_R17_frozen_source_not_backdated_and_no_zero_cost_defaults(self):
        with self.assertRaises(ResearchHold):
            self.plan(activates_at_ms=END_DECISION)
        with self.assertRaises(ResearchHold):
            self.plan(fee_policy="ZERO_FEES")
        with self.assertRaises(ResearchHold):
            self.plan(source_grade="ORIGINAL_VERIFIED")
        with self.assertRaises(ResearchHold):
            self.plan(side="BUY")

    def test_R18_forged_geometry_and_id_cannot_pass_record_replay(self):
        p=self.plan()
        bad=p.to_dict()
        bad["stop"]="80"
        with self.assertRaises(ResearchHold):
            from_record(bad)
        with self.assertRaises(ResearchHold):
            from_record({**p.to_dict(),"intent_id":"0"*64})

    def test_R19_journal_duplicate_fail_closed_and_hash_corruption(self):
        p=self.plan()
        self.admit(p)
        file=self.journal.path
        data=file.read_bytes()
        file.write_bytes(data.replace(b"ACTIVE",b"LIVE",1) if b"ACTIVE" in data
                   else data[:-2]+b"0\n")
        with self.assertRaises(JournalHold):
            VirtualResearchBook(self.journal)

    def test_R20_journal_torn_record_fails_closed(self):
        self.admit(self.plan())
        with self.journal.path.open("ab") as f:f.write(b'{"part')
        with self.assertRaises(JournalHold):
            VirtualResearchBook(self.journal)

    def test_R21_parent_folder_permissions_fail_closed(self):
        self.root.chmod(0o777)
        try:
            with self.assertRaises(JournalHold):
                VirtualResearchBook(self.journal)
        finally:self.root.chmod(0o700)

    def test_R22_sync_failure_does_not_release_active_slot(self):
        p=self.plan();self.admit(p)
        def fail(*args,**kw):
            raise OSError("simulated fsync failure")
        with patch.object(self.journal,"append",side_effect=fail):
            with self.assertRaises(OSError):
                self.book.ingest(self.tick("106",id=1))
        self.assertEqual(self.book.occupied,1)
        self.assertFalse(self.book.closed)

    def test_R23_unsafe_future_or_incomplete_tick_never_exits(self):
        p=self.plan()
        self.admit(p)
        self.book.ingest(self.tick("106",id=1,
                         complete=END_DECISION+1000))
        self.assertEqual(self.book.active[p.intent_id].state,"SOURCE_HOLD")
        self.assertNotIn(p.intent_id,self.book.closed)

    def test_R24_unqualified_real_tick_grade_rejected(self):
        self.admit(self.plan())
        good=self.tick("105",id=1)
        with self.assertRaises(ResearchHold):
            self.book.ingest(replace(good,source_grade="PUBLIC_TLS_WSS_LOCAL_RAW_NOT_EXCHANGE_SIGNED"))
        self.assertEqual(self.book.occupied,1)
        self.assertFalse(self.book.closed)

    def test_R25_checkpoint_trail_and_restart_quarantine(self):
        p=self.plan();self.admit(p)
        self.book.ingest(self.tick("103",id=1))
        self.assertEqual(self.book.checkpoint(END_DECISION+1000),1)
        self.assertEqual(self.book.checkpoint(END_DECISION+1001),0)
        r=VirtualResearchBook(self.journal)
        self.assertEqual(r.active[p.intent_id].state,"RESTART_HOLD")
        self.assertEqual(r.status()["held"],1)

    def test_R26_no_unauthorized_virtual_order_api_exists(self):
        self.assertFalse(hasattr(self.book,"submit_order"))
        self.assertFalse(hasattr(self.book,"open_real_position"))
        self.assertFalse(hasattr(self.book,"qualified_net_return"))
        self.assertEqual(self.book.status()["financial_authority"],"NONE")

    def test_R27_all_source_hold_occupancy_survives_repeated_review(self):
        p=self.plan();self.admit(p)
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+1000)
        next_event=FiveMinuteEvent(END_OPEN+INTERVAL_MS,END_DECISION+INTERVAL_MS)
        out=self.book.review(next_event,self.deep,
                             lambda:(self.plan(event=next_event),))
        self.assertEqual(out.openings,0)
        self.assertEqual(out.skipped_ineligible,1)
        self.assertEqual(self.book.occupied,1)

    def test_R28_journal_head_prevents_concurrent_conflicting_writer(self):
        head=self.book.head
        self.admit(self.plan())
        with self.assertRaisesRegex(JournalHold,"CONCURRENT_HEAD"):
            self.journal.append("REVIEW",END_DECISION,
                {"event_open_ms":END_OPEN},expected_head=head)

    def test_R29_source_for_two_sides_is_one_shared_stream_event(self):
        a=self.plan(side="LONG");b=self.plan(side="SHORT")
        self.admit(a,b)
        self.book.ingest(self.tick("100",id=5))
        self.assertEqual(self.book.active[a.intent_id].seen,1)
        self.assertEqual(self.book.active[b.intent_id].seen,1)
        self.book.ingest(self.tick("101",id=6,t=END_DECISION+3000))
        self.assertEqual(self.book.active[a.intent_id].seen,2)
        self.assertEqual(self.book.active[b.intent_id].seen,2)

if __name__=="__main__":
    unittest.main()
