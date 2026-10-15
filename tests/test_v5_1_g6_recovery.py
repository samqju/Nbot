"""G6 fail-closed recovery, quoted modeled economics, sealed source copy.

All fixtures are SYNTHETIC. No test mints an exchange fill or scientifically
qualified original after-cost net return.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.core import INTERVAL_MS
from nbot_v5_1.recovery_contract import (
    completed_five_minute_bars,plan_public_aggtrade_gap,
    verify_aggtrade_gap,ambiguous_bar_first_touch,one_second_usdm_recovery,
    RecoveryHold)
from nbot_v5_1.research_intent import freeze_intent
from nbot_v5_1.research_book import VirtualTerminal
from nbot_v5_1.economic_audit import (QuoteWitness,CostWitness,
    assess_model_only,qualified_learning_label_count)
from nbot_v5_1.archive_custody import seal_archive,verify_archive,ArchiveHold
from nbot_v5_1.deep_segments import DeepSegmentRecorder
from test_v5_1_g2 import END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW,SYMBOLS

HASH="a"*64


def kline(t):
    return [t,"100","110","90","101","10",t+INTERVAL_MS-1,
            "0","0","0","0","0"]


def trade(a):
    return {"a":a,"f":a*2,"l":a*2+1,"T":END_DECISION+100+a,
            "p":"101","q":"0.2","m":False}


def plan(side="LONG"):
    return freeze_intent(symbol="BTCUSDT",side=side,
         event_open_ms=END_OPEN,declared_at_ms=END_DECISION,
         activates_at_ms=END_DECISION+10,entry_reference="100",
         stop="95" if side=="LONG" else "105",
         target="105" if side=="LONG" else "95",
         horizon_ms=INTERVAL_MS,cohort_sha=HASH,observation_sha=HASH,
         source_epoch=1,source_grade="SYNTHETIC_OFFLINE_TEST_ONLY")


def lab_case(side="LONG"):
    i=plan(side)
    terminal=VirtualTerminal(i.intent_id,"BTCUSDT",side,"TARGET",
                     END_DECISION+1000,"105" if side=="LONG" else "95")
    start=QuoteWitness("BTCUSDT",END_DECISION+9,"100","100.1",HASH)
    end=QuoteWitness("BTCUSDT",END_DECISION+999,"105","105.1",HASH)
    costs=CostWitness("0.0004","0.0005","0.01",END_DECISION+1000,
                       HASH,HASH,HASH)
    return i,terminal,start,end,costs


class RecoveryTests(unittest.TestCase):
    def test_G601_completed_recovery_only_context(self):
        data=json.dumps([kline(END_OPEN)]).encode()
        a=completed_five_minute_bars(symbol="BTCUSDT",raw=data,
              received_at_ms=END_DECISION,source_epoch=1,
              start_open_ms=END_OPEN,end_open_ms=END_OPEN)
        self.assertEqual(a.state,"CANDLE_CONTEXT_ONLY")
        self.assertFalse(a.qualifies_original_first_touch)
        self.assertFalse(a.qualifies_quote_or_funding)

    def test_G602_missing_second_finalized_candle_holds(self):
        data=json.dumps([kline(END_OPEN)]).encode()
        a=completed_five_minute_bars(symbol="BTCUSDT",raw=data,
              received_at_ms=END_DECISION+INTERVAL_MS,source_epoch=1,
              start_open_ms=END_OPEN,end_open_ms=END_OPEN+INTERVAL_MS)
        self.assertEqual(a.state,"HOLD")
        self.assertIn("G6_MISSING_DUPLICATE_OR_EXTRA_CANDLE",a.reasons)

    def test_G603_future_final_bar_rejected(self):
        raw=json.dumps([kline(END_OPEN)]).encode()
        with self.assertRaises(RecoveryHold):
            completed_five_minute_bars(symbol="BTCUSDT",raw=raw,
              received_at_ms=END_DECISION-1000,source_epoch=1,
              start_open_ms=END_OPEN,end_open_ms=END_OPEN)

    def test_G604_duplicate_mismatching_rest_fails(self):
        raw=json.dumps([kline(END_OPEN),kline(END_OPEN)]).encode()
        r=completed_five_minute_bars(symbol="BTCUSDT",raw=raw,
              received_at_ms=END_DECISION,source_epoch=1,
              start_open_ms=END_OPEN,end_open_ms=END_OPEN)
        self.assertEqual(r.state,"HOLD")

    def test_G605_public_usdm_1s_is_not_supported_assumption(self):
        with self.assertRaisesRegex(RecoveryHold,"NOT_VERIFIED"):
            one_second_usdm_recovery(interval="1s")

    def test_G606_both_first_touches_in_bar_are_unknown(self):
        self.assertIn("ORDER_UNKNOWABLE",str(ambiguous_bar_first_touch(
            side="LONG",stop="95",target="105",low="90",high="110",
            source_is_complete=True)))

    def test_G607_one_crossing_bar_still_not_exchange_fill(self):
        a=ambiguous_bar_first_touch(side="LONG",stop="95",target="105",
                      low="98",high="108",source_is_complete=True)
        self.assertIn("BAR_TOUCH_ONLY",str(a))

    def test_G608_uncovered_interval_cannot_be_reconstructed(self):
        a=ambiguous_bar_first_touch(side="SHORT",stop="105",target="95",
                      low="90",high="110",source_is_complete=False)
        self.assertIn("INCOMPLETE",str(a))

    def test_G609_aggtrade_gap_uri_respects_48_hours(self):
        p=plan_public_aggtrade_gap(symbol="BTCUSDT",
           first_missing_agg_id=11,until_at_ms=END_DECISION,
           now_ms=END_DECISION+1000,limit=3)
        self.assertEqual(p,"/fapi/v1/aggTrades?symbol=BTCUSDT&fromId=11&limit=3")
        with self.assertRaises(RecoveryHold):
            plan_public_aggtrade_gap(symbol="BTCUSDT",first_missing_agg_id=11,
                 until_at_ms=END_DECISION,now_ms=END_DECISION+49*3600*1000)

    def test_G610_complete_trade_id_numbered_recovery_still_not_quotes(self):
        raw=json.dumps([trade(10),trade(11),trade(12)]).encode()
        x=verify_aggtrade_gap(symbol="BTCUSDT",raw=raw,
                 from_agg_id=10,expected_last_agg_id=12,
                 known_at_ms=END_DECISION+500)
        self.assertEqual(x.state,"TRADE_CHRONOLOGY_ONLY")
        self.assertFalse(x.qualifies_quote_or_funding)
        self.assertFalse(x.qualifies_original_first_touch)

    def test_G611_missing_aggregate_id_cannot_pass(self):
        raw=json.dumps([trade(10),trade(12)]).encode()
        x=verify_aggtrade_gap(symbol="BTCUSDT",raw=raw,
                   from_agg_id=10,expected_last_agg_id=12,
                   known_at_ms=END_DECISION+500)
        self.assertEqual(x.state,"HOLD")

    def test_G612_underlying_trade_id_gap_fails(self):
        r=[trade(10),trade(11)]
        r[1]["f"]=100
        x=verify_aggtrade_gap(symbol="BTCUSDT",raw=json.dumps(r).encode(),
                    from_agg_id=10,expected_last_agg_id=11,
                    known_at_ms=END_DECISION+500)
        self.assertEqual(x.state,"HOLD")

    def test_G613_duplicate_json_key_rejected(self):
        with self.assertRaises(RecoveryHold):
            verify_aggtrade_gap(symbol="BTCUSDT",
                    raw=b'[{"a":1,"a":2}]',from_agg_id=1,
                    expected_last_agg_id=1,known_at_ms=END_DECISION)


class EconomicTests(unittest.TestCase):
    def test_G614_prospective_long_model_fee_slip_funding_all_included(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
              entry_quote=a[2],exit_quote=a[3],costs=a[4],
              audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"MODELED_SYNTHETIC_ONLY_NOT_QUALIFIED")
        self.assertGreater(float(r.modeled_gross_r),float(r.modeled_net_r))
        self.assertEqual(r.research_qualified_count,0)
        self.assertEqual(r.filled_exchange_orders,0)

    def test_G615_short_quote_sides_and_signed_financing(self):
        a=lab_case("SHORT")
        r=assess_model_only(intent=a[0],terminal=a[1],
              entry_quote=a[2],exit_quote=replace(a[3],bid="95",ask="95.1"),
              costs=replace(a[4],funding_cash_quote_per_unit="-0.01"),
              audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"MODELED_SYNTHETIC_ONLY_NOT_QUALIFIED")
        self.assertGreater(float(r.modeled_gross_r),0)
        self.assertGreater(float(r.modeled_net_r),0)

    def test_G616_missing_fee_source_holds_not_default_zero(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
             entry_quote=a[2],exit_quote=a[3],costs=None,
             audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"HOLD")
        self.assertIsNone(r.modeled_net_r)

    def test_G617_missing_independently_quoted_entry_holds(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
             entry_quote=None,exit_quote=a[3],costs=a[4],
             audit_at_ms=END_DECISION+1001)
        self.assertIn("ENTRY_QUOTE_MISSING",str(r.reasons))

    def test_G618_crossed_book_rejected(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
             entry_quote=replace(a[2],bid="102",ask="100"),
             exit_quote=a[3],costs=a[4],audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"HOLD")

    def test_G619_future_entry_quote_never_known_earlier(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
             entry_quote=replace(a[2],at_ms=END_DECISION+100),
             exit_quote=a[3],costs=a[4],audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"HOLD")

    def test_G620_funding_history_not_position_funding(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
             entry_quote=a[2],exit_quote=a[3],
             costs=replace(a[4],funding_interval_covered_through_ms=END_DECISION),
             audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"HOLD")

    def test_G621_synthetic_returns_never_become_learning_labels(self):
        a=lab_case()
        out=assess_model_only(intent=a[0],terminal=a[1],
               entry_quote=a[2],exit_quote=a[3],costs=a[4],
               audit_at_ms=END_DECISION+1001)
        self.assertEqual(qualified_learning_label_count((out,)*2000),0)

    def test_G622_impossible_qualified_grade_rejected(self):
        a=lab_case()
        r=assess_model_only(intent=a[0],terminal=a[1],
            entry_quote=replace(a[2],grade="INDEPENDENT_ORIGINAL"),
            exit_quote=a[3],costs=a[4],audit_at_ms=END_DECISION+1001)
        self.assertEqual(r.state,"HOLD")


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-g6-source-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/"source"
        self.dest=self.root/"sealed"
        self.source.mkdir(mode=0o700)
        self.dest.mkdir(mode=0o700)
        self.rec=DeepSegmentRecorder(self.source,symbols=SYMBOLS)
        self.rec.append(kind="TRADE",raw=frame(),received_at_ms=NOW,epoch=1)
        self.rec.append(kind="QUOTE",raw=frame("QUOTE"),received_at_ms=NOW,epoch=1)
        self.rec.flush()

    def test_G623_local_copy_seals_and_independent_full_replay(self):
        manifest=seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)
        self.assertEqual(manifest["frame_count"],2)
        r=verify_archive(root=self.dest,symbols=SYMBOLS)
        self.assertEqual(r["frames"],2)
        self.assertEqual(r["manifest_sha256"],manifest["manifest_sha256"])
        self.assertNotIn("OFFHOST_ATTESTED",r["status"])

    def test_G624_modification_of_stored_byte_rejected(self):
        seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)
        name=next(p for p in self.dest.iterdir() if p.suffix==".gz")
        name.write_bytes(b"altered"+name.read_bytes()[7:])
        with self.assertRaises(ArchiveHold):
            verify_archive(root=self.dest,symbols=SYMBOLS)

    def test_G625_partial_copy_not_overwritten(self):
        (self.dest/"extra").write_text("not pristine")
        with self.assertRaises(ArchiveHold):
            seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)
        self.assertTrue((self.dest/"extra").exists())

    def test_G626_private_directory_required(self):
        self.dest.chmod(0o777)
        try:
            with self.assertRaises(ArchiveHold):
                seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)
        finally:self.dest.chmod(0o700)

    def test_G627_disk_quota_fails_before_copy(self):
        with self.assertRaises(ArchiveHold):
            seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS,quota=1024)
        self.assertFalse(any(self.dest.iterdir()))

    def test_G628_extra_archive_file_triggers_hard_hold(self):
        seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)
        (self.dest/"strange.tmp").write_text("unexpected")
        with self.assertRaises(ArchiveHold):
            verify_archive(root=self.dest,symbols=SYMBOLS)

    def test_G629_missing_source_segment_pair_fails_closed(self):
        (self.source/"segment-00000001.gz").unlink()
        with self.assertRaises(ArchiveHold):
            seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)

    def test_G630_wrong_cohort_does_not_verify(self):
        seal_archive(source=self.source,destination=self.dest,symbols=SYMBOLS)
        with self.assertRaises(ArchiveHold):
            verify_archive(root=self.dest,symbols=("BTCUSDT",))

if __name__=="__main__":unittest.main()
