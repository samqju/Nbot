"""CS-00 source recovery and exclusion contract: synthetic input, NO NETWORK.

Tests verify trade-ID pagination/recovery and prevent an unrecoverable G5
experiment from returning to any scored/training dataset.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.cs00_history_recovery import (
    HistoricalAggTradeRecovery, SourceRecoveryHold, RECOVERED_STATE,
    eligible_learning_ids)
from nbot_v5_1.research_book import VirtualResearchBook
from nbot_v5_1.research_journal import ResearchJournal, JournalHold
from nbot_v5_1.research_intent import freeze_intent, ResearchHold
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS
from nbot_v5_1.learning_contract import lab_row, assemble_lab, verified_learning_count
from test_v5_1_g2 import manifest, END_OPEN, END_DECISION
from test_v5_1_g7_learning import fixture

SHA="a"*64
T=1792000000000


def trade(ident:int, at:int, price:str="100", *, first=None, last=None):
    return {"a":ident,"f":ident if first is None else first,
            "l":ident if last is None else last,"T":at,
            "p":price,"q":"1.000","m":True}


def body(rows):
    return json.dumps(rows,sort_keys=True,separators=(",",":")).encode("ascii")


def session(*,count:int=3,first:int=100,old:bool=False):
    start=T
    end=start+10000
    now=end+(49 if old else 1)*3600*1000
    return HistoricalAggTradeRecovery(experiment_id=SHA,symbol="BTCUSDT",
        first_agg_id=first,last_agg_id=first+count-1,
        gap_start_ms=start,gap_end_ms=end,now_ms=now)


class RecoveryContractCS00(unittest.TestCase):
    def test_CSREC01_default_no_network_and_public_id_request(self):
        x=session()
        self.assertEqual(x.state,"RECOVERY_PENDING")
        self.assertEqual(x.next_rest_request(),
                         "/fapi/v1/aggTrades?symbol=BTCUSDT&fromId=100&limit=3")
        self.assertFalse(hasattr(x,"fetch"))
        self.assertFalse(hasattr(x,"start_service"))

    def test_CSREC02_complete_historical_trade_stop_before_target(self):
        x=session()
        self.assertEqual(x.ingest_page(body([
            trade(100,T+1000,"100"),
            trade(101,T+2000,"98"),
            trade(102,T+3000,"103")]),received_at_ms=T+20000),
            RECOVERED_STATE)
        p=x.proof()
        self.assertEqual(p.trade_count,3)
        self.assertEqual(p.state,RECOVERED_STATE)
        self.assertFalse(p.qualifies_scientific_training)
        self.assertFalse(p.exact_historical_quote_verified)
        self.assertFalse(p.original_live_decision_verified)
        touch=x.traded_price_first_touch(side="LONG",stop="99",target="102")
        self.assertEqual((touch.barrier,touch.trade_agg_id),("STOP",101))
        self.assertEqual(touch.state,"TRADED_PRICE_FIRST_TOUCH_ONLY")

    def test_CSREC03_target_first_when_real_history_proves_it(self):
        x=session()
        x.ingest_page(body([
            trade(100,T+1000,"100"),trade(101,T+2000,"103"),
            trade(102,T+3000,"98")]),received_at_ms=T+20000)
        self.assertEqual(x.traded_price_first_touch(
            side="LONG",stop="99",target="102").barrier,"TARGET")

    def test_CSREC04_multi_page_strict_cursor_and_deterministic_sha(self):
        x=session()
        self.assertEqual(x.ingest_page(body([
            trade(100,T+1000),trade(101,T+2000)]),
            received_at_ms=T+20000),"RECOVERY_PENDING")
        self.assertIn("fromId=102",x.next_rest_request())
        self.assertIn("limit=1",x.next_rest_request())
        x.ingest_page(body([trade(102,T+3000)]),received_at_ms=T+20000)
        self.assertEqual(x.state,RECOVERED_STATE)
        self.assertEqual(x.proof().trade_count,3)
        self.assertEqual(len(x.proof().page_sha256),2)
        self.assertEqual(len(x.proof().chain_sha256),64)

    def test_CSREC05_missing_aggregate_id_cannot_pass(self):
        x=session()
        with self.assertRaisesRegex(SourceRecoveryHold,"TRADE_ID_TIME"):
            x.ingest_page(body([trade(100,T+1000),trade(102,T+2000)]),
                          received_at_ms=T+20000)
        self.assertEqual(x.state,"RECOVERY_PENDING")
        self.assertEqual(x.proof().trade_count,0)

    def test_CSREC06_duplicate_page_does_not_rewind(self):
        x=session()
        raw=body([trade(100,T+1000)])
        x.ingest_page(raw,received_at_ms=T+20000)
        with self.assertRaises(SourceRecoveryHold):
            x.ingest_page(raw,received_at_ms=T+20000)
        self.assertEqual(x.proof().trade_count,1)

    def test_CSREC07_future_or_out_of_window_history_denied(self):
        x=session()
        for at in (T-1000,T+11000):
            with self.subTest(at=at),self.assertRaises(SourceRecoveryHold):
                x.ingest_page(body([trade(100,at)]),received_at_ms=T+20000)
        self.assertEqual(x.proof().trade_count,0)

    def test_CSREC08_underlying_id_gap_is_review_not_forged_profit(self):
        x=session()
        p=body([trade(100,T+1000,first=500,last=501),
                trade(101,T+2000,first=504,last=504)])
        self.assertEqual(x.ingest_page(p,received_at_ms=T+20000),
                         "RECOVERY_HOLD")
        self.assertIn("CS00_UNDERLYING_TRADE_ID_DISCONTINUITY_REVIEW",
                      x.proof().reasons)
        self.assertEqual(x.proof().trade_count,0)

    def test_CSREC09_old_rest_gap_demands_archive_verification(self):
        x=session(old=True)
        self.assertEqual(x.state,"ARCHIVE_PENDING")
        self.assertIsNone(x.next_rest_request())
        with self.assertRaisesRegex(SourceRecoveryHold,"OVER_48H"):
            x.ingest_page(body([trade(100,T+1000)]),
                          received_at_ms=T+20000)
        self.assertEqual(x.proof().trade_count,0)

    def test_CSREC10_historical_archive_claim_alone_no_qualified_cost(self):
        x=session(old=True)
        x.ingest_page(body([trade(100,T+1000),trade(101,T+2000),
                            trade(102,T+3000)]),received_at_ms=T+20000,
                      source="OFFICIAL_ARCHIVE_CHECKSUM_VERIFIED")
        self.assertEqual(x.state,RECOVERED_STATE)
        self.assertFalse(x.proof().qualifies_scientific_training)
        self.assertFalse(x.proof().mark_trigger_verified)
        self.assertFalse(x.proof().cost_verified)

    def test_CSREC11_wrong_archive_format_and_duplicate_key_denied(self):
        x=session()
        with self.assertRaises(SourceRecoveryHold):
            x.ingest_page(b'[{"a":100,"a":100}]',received_at_ms=T+20000)
        with self.assertRaises(SourceRecoveryHold):
            x.ingest_page(b'[]',received_at_ms=T+20000)
        with self.assertRaises(SourceRecoveryHold):
            x.ingest_page(body([trade(100,T+1000)])[0:12],
                          received_at_ms=T+20000)

    def test_CSREC12_oversize_20_market_retry_never_network(self):
        with self.assertRaises(SourceRecoveryHold):
            session(count=500001)
        x=session(count=1001)
        self.assertIn("limit=1000",x.next_rest_request())
        self.assertEqual(x.state,"RECOVERY_PENDING")

    def test_CSREC13_incomplete_trade_path_not_labelled_as_win(self):
        x=session()
        x.ingest_page(body([trade(100,T+1000)]),received_at_ms=T+20000)
        self.assertEqual(x.traded_price_first_touch(
            side="LONG",stop="99",target="102").state,
            "UNQUALIFIED_SOURCE_HOLD")

    def test_CSREC14_invalid_symbol_and_clock_denied(self):
        with self.assertRaises(SourceRecoveryHold):
            HistoricalAggTradeRecovery(
                experiment_id=SHA,symbol="BTC/USDT",first_agg_id=100,
                last_agg_id=102,gap_start_ms=T,gap_end_ms=T+1000,now_ms=T+2000)
        with self.assertRaises(SourceRecoveryHold):
            HistoricalAggTradeRecovery(
                experiment_id=SHA,symbol="BTCUSDT",first_agg_id=100,
                last_agg_id=99,gap_start_ms=T,gap_end_ms=T+1000,now_ms=T+2000)

    def test_CSREC15_label_filter_excludes_unrecoverable_and_pending(self):
        x=eligible_learning_ids(labeled_records=(
            ("1"*64,"UNRECOVERABLE_EXCLUDED","EXCLUDED"),
            ("2"*64,"RECOVERY_PENDING","COST_PENDING"),
            ("3"*64,"TRADE_PATH_ONLY","COST_UNQUALIFIED"),
            ("4"*64,"PATH_AND_COST_COMPLETE","INDEPENDENTLY_QUALIFIED")))
        self.assertEqual(x,("4"*64,))
        with self.assertRaises(SourceRecoveryHold):
            eligible_learning_ids(labeled_records=(
                ("1"*64,"UNRECOVERABLE_EXCLUDED","EXCLUDED"),
                ("1"*64,"PATH_AND_COST_COMPLETE","INDEPENDENTLY_QUALIFIED")))

    def test_CSREC16_g7_unrecoverable_is_denominator_not_score(self):
        row=fixture(state="UNRECOVERABLE_EXCLUDED",net=None)
        d=assemble_lab((row,),cutoff_ms=row.matured_ms+10)
        self.assertEqual(len(d.rows),1)
        self.assertEqual(len(d.economic_lab_rows),0)
        self.assertEqual(verified_learning_count(d),0)
        with self.assertRaises(Exception):
            assemble_lab((fixture(state="UNRECOVERABLE_EXCLUDED",net="5"),),
                         cutoff_ms=row.matured_ms+10)


class ExplicitExclusionCS00(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="cs00-censor-offline-")
        self.addCleanup(self.temp.cleanup)
        self.journal=ResearchJournal(Path(self.temp.name)/"research.jsonl")
        self.book=VirtualResearchBook(self.journal)
        cohort=manifest(20)
        b=ObservationBook(cohort)
        event=FiveMinuteEvent(END_OPEN,END_DECISION)
        g3=explore_event(b,event,capacity_slots=0)
        deep=choose_deep(cohort,g3,count=20)
        self.plan=freeze_intent(
            symbol="BTCUSDT",side="LONG",event_open_ms=END_OPEN,
            declared_at_ms=END_DECISION,activates_at_ms=END_DECISION+1,
            entry_reference="100",stop="95",target="105",
            horizon_ms=INTERVAL_MS,cohort_sha=deep.manifest_sha,
            observation_sha=SHA,source_epoch=1,
            source_grade="SYNTHETIC_OFFLINE_TEST_ONLY",
            trail_activation_r="0.5",trail_distance_r="0.5")
        self.event=event
        self.deep=deep
        self.book.review(event,deep,lambda:(self.plan,))

    def test_CSEXC01_healthy_trade_cannot_be_secretly_erased(self):
        with self.assertRaisesRegex(ResearchHold,"CENSOR_NOT_HELD"):
            self.book.exclude_unrecoverable(
                self.plan.intent_id,at_ms=END_DECISION+100,
                reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=SHA)
        self.assertEqual(self.book.occupied,1)
        self.assertFalse(self.book.excluded)

    def test_CSEXC02_held_trade_explicitly_excluded_not_winner(self):
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+100,
                             reason="WSS_GAP")
        self.assertEqual(self.book.occupied,1)
        out=self.book.exclude_unrecoverable(
            self.plan.intent_id,at_ms=END_DECISION+200,
            reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=SHA)
        self.assertFalse(out["learning_eligible"])
        self.assertEqual(self.book.occupied,0)
        self.assertEqual(self.book.status()["unrecoverable_excluded"],1)
        self.assertNotIn(self.plan.intent_id,self.book.closed)
        self.assertIn(self.plan.intent_id,self.book.excluded)

    def test_CSEXC03_restart_replays_censor_and_retains_tombstone(self):
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+100)
        self.book.exclude_unrecoverable(
            self.plan.intent_id,at_ms=END_DECISION+200,
            reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=SHA)
        reloaded=VirtualResearchBook(self.journal)
        self.assertEqual(reloaded.occupied,0)
        self.assertEqual(reloaded.status()["unrecoverable_excluded"],1)
        self.assertFalse(reloaded.closed)
        self.assertIn(self.plan.intent_id,reloaded.seen_ids)

    def test_CSEXC04_bad_or_missing_recovery_proof_never_frees_slot(self):
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+100)
        for digest in ("","not-sha","A"*64):
            with self.subTest(digest=digest),self.assertRaises(ResearchHold):
                self.book.exclude_unrecoverable(
                    self.plan.intent_id,at_ms=END_DECISION+200,
                    reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=digest)
        self.assertEqual(self.book.occupied,1)

    def test_CSEXC05_invalid_exclusion_reason_rejected(self):
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+100)
        with self.assertRaises(ResearchHold):
            self.book.exclude_unrecoverable(
                self.plan.intent_id,at_ms=END_DECISION+200,
                reason="WIN_AND_FORGET",recovery_proof_sha256=SHA)
        self.assertEqual(self.book.occupied,1)

    def test_CSEXC06_second_exclusion_cannot_reuse_same_id(self):
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+100)
        self.book.exclude_unrecoverable(
            self.plan.intent_id,at_ms=END_DECISION+200,
            reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=SHA)
        with self.assertRaises(ResearchHold):
            self.book.exclude_unrecoverable(
                self.plan.intent_id,at_ms=END_DECISION+300,
                reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=SHA)
        self.assertEqual(len(self.book.excluded),1)

    def test_CSEXC07_journal_censor_without_hold_refuses_replay(self):
        self.book._log("CENSOR",END_DECISION+100,{
            "intent_id":self.plan.intent_id,
            "reason":"SOURCE_UNRECOVERABLE","recovery_proof_sha256":SHA})
        with self.assertRaisesRegex(JournalHold,"CENSOR_REQUIRES_HELD"):
            VirtualResearchBook(self.journal)

    def test_CSEXC08_tampered_journal_never_silently_discards_audit(self):
        self.book.invalidate("BTCUSDT",at_ms=END_DECISION+100)
        self.book.exclude_unrecoverable(
            self.plan.intent_id,at_ms=END_DECISION+200,
            reason="SOURCE_UNRECOVERABLE",recovery_proof_sha256=SHA)
        path=Path(self.temp.name)/"research.jsonl"
        content=path.read_bytes().replace(b"SOURCE_UNRECOVERABLE",
                                          b"SOURCE_UNRECOVERABLE_FAKE",1)
        path.write_bytes(content)
        with self.assertRaises(JournalHold):
            VirtualResearchBook(ResearchJournal(path))


if __name__=="__main__":
    unittest.main()
