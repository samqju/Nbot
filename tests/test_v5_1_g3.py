"""G3 up-to-100 coin x 2-side accounting; capacity, source, BTC, as-of and safety."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from nbot_v5_1.core import FiveMinuteEvent, ObservationAuthority, ObservationDisposition, INTERVAL_MS
from nbot_v5_1.observation import ObservationBook, ClosedBar
from nbot_v5_1.exploration import (
    G3_SCHEMA, PATTERN_IDS, TECH_IDS, DETECTOR_VERSION, ExplorationBatch,
    explore_event,
)
from test_v5_1_g2 import manifest, history, END_OPEN, END_DECISION


class ExplorationTests(unittest.TestCase):
    def setUp(self):
        self.universe = manifest()
        self.book = ObservationBook(self.universe)
        self.event = FiveMinuteEvent(END_OPEN, END_DECISION)

    def bootstrap(self):
        for sym in self.universe.symbols:
            self.assertTrue(self.book.bootstrap(sym,history(sym),as_of_ms=END_DECISION))

    def test_E01_catalog_has_exact_original_24_and_version_sha(self):
        self.assertEqual(len(PATTERN_IDS),24)
        self.assertEqual(len(TECH_IDS),19)
        self.assertEqual(len(set(PATTERN_IDS)),24)
        self.assertTrue(DETECTOR_VERSION.startswith("NBOT_V5_1_G3_ADAPTER_V1:"))
        self.assertEqual(G3_SCHEMA,"NBOT_V5_1_EXPLORATION_V1")

    def test_E02_missing_all_source_full_200_not_silently_removed(self):
        batch = explore_event(self.book,self.event,capacity_slots=20)
        self.assertEqual(len(batch.rows),200)
        self.assertEqual(batch.source_skipped_pairs,200)
        self.assertEqual(batch.evaluated_pairs,0)
        self.assertEqual(batch.capacity_skipped_pairs,0)
        self.assertTrue(all(r.status=="NOT_EVALUATED_SOURCE" for r in batch.rows))
        self.assertTrue(all(set(r.states().values()) == {"NOT_EVALUATED_SOURCE"} for r in batch.rows))
        self.assertEqual(len({r.decision_id for r in batch.rows}),200)

    def test_E03_no_vacancy_skips_200_even_healthy(self):
        self.bootstrap()
        batch=explore_event(self.book,self.event,capacity_slots=0)
        self.assertEqual((batch.eligible_pairs,batch.capacity_skipped_pairs,
                          batch.evaluated_pairs), (200,200,0))
        self.assertTrue(all(r.status=="NOT_EVALUATED_CAPACITY" for r in batch.rows))
        self.assertTrue(all(all(s=="NOT_EVALUATED_CAPACITY" for s in r.states().values())
                            for r in batch.rows))

    def test_E04_full_evaluation_200_and_24_per_side(self):
        self.bootstrap()
        batch=explore_event(self.book,self.event,capacity_slots=1,evaluation_limit=200)
        self.assertEqual(len(batch.rows),200)
        self.assertEqual(batch.evaluated_pairs,200)
        self.assertEqual(batch.source_skipped_pairs,0)
        self.assertEqual(batch.capacity_skipped_pairs,0)
        self.assertEqual(len({r.decision_id for r in batch.rows}),200)
        self.assertEqual(set(r.side for r in batch.rows),{"LONG","SHORT"})
        self.assertTrue(all(tuple(r.states())==PATTERN_IDS for r in batch.rows))
        self.assertTrue(all(r.authority == ObservationAuthority.NONE
                            and r.disposition==ObservationDisposition.NO_TRADE
                            for r in batch.rows))

    def test_E05_partial_policy_deterministic_sample_and_probability(self):
        self.bootstrap()
        a=explore_event(self.book,self.event,capacity_slots=4,evaluation_limit=17)
        b=explore_event(self.book,self.event,capacity_slots=4,evaluation_limit=17)
        self.assertEqual(a,b)
        self.assertEqual((a.evaluated_pairs,a.capacity_skipped_pairs), (17,183))
        self.assertEqual(len(a.rows),200)
        self.assertEqual({r.inclusion_probability for r in a.rows if r.status=="OBSERVED"},
                         {17/200})
        self.assertTrue(all(r.inclusion_probability==0 for r in a.rows if r.status!="OBSERVED"))

    def test_E06_source_and_capacity_missingness_are_distinct(self):
        self.bootstrap()
        blocked=self.universe.symbols[1:11]
        for s in blocked:
            self.book.mark_gap(s,reason="DISCONNECTED")
        result=explore_event(self.book,self.event,capacity_slots=1,evaluation_limit=20)
        self.assertEqual(len(result.rows),200)
        self.assertEqual(result.source_skipped_pairs,20)
        self.assertEqual(result.evaluated_pairs,20)
        self.assertEqual(result.capacity_skipped_pairs,160)
        for r in result.rows:
            if r.symbol in blocked:
                self.assertEqual(r.status,"NOT_EVALUATED_SOURCE")
                self.assertEqual(set(r.states().values()),{"NOT_EVALUATED_SOURCE"})

    def test_E07_missing_BTC_does_not_turn_relative_rule_into_no_match(self):
        self.bootstrap()
        self.book.mark_gap("BTCUSDT", reason="BTC_GAP")
        rows=explore_event(self.book,self.event,capacity_slots=1)
        self.assertEqual(rows.source_skipped_pairs,2)
        self.assertEqual(rows.evaluated_pairs,198)
        self.assertTrue(all(r.btc_regime=="UNAVAILABLE" for r in rows.rows))
        self.assertTrue(all(r.states()["BTC_RELATIVE_MOMENTUM_V1"]=="UNAVAILABLE"
             for r in rows.rows if r.symbol!="BTCUSDT"))
        self.assertTrue(all(r.disposition==ObservationDisposition.NO_TRADE for r in rows.rows))

    def test_E08_cross_section_insufficient_5_context_unavailable(self):
        self.bootstrap()
        for s in self.universe.symbols[1:31]:
            self.book.mark_gap(s,reason="MISSING_MARKET")
        batch=explore_event(self.book,self.event,capacity_slots=1)
        self.assertEqual(batch.source_skipped_pairs,60)
        self.assertEqual(batch.evaluated_pairs,140)
        self.assertTrue(all(r.market_regime=="UNAVAILABLE" for r in batch.rows))
        for r in batch.rows:
            if r.status=="OBSERVED":
                self.assertTrue(all(r.states()[name]=="UNAVAILABLE" for name in PATTERN_IDS[:5]))

    def test_E09_future_or_stale_candle_can_never_be_reused(self):
        self.bootstrap()
        previous=FiveMinuteEvent(END_OPEN-INTERVAL_MS, END_OPEN)
        batch=explore_event(self.book,previous,capacity_slots=1)
        self.assertEqual(batch.evaluated_pairs,0)
        self.assertEqual(batch.source_skipped_pairs,200)
        self.assertTrue(all(r.status=="NOT_EVALUATED_SOURCE" for r in batch.rows))

    def test_E10_one_breakout_matches_without_creating_order(self):
        self.bootstrap()
        b=history(self.universe.symbols[1])
        old=b[-1]
        b[-1]=ClosedBar(old.symbol,old.open_ms,old.close_ms,
                  "101","106","99","105","10",END_DECISION,0,"public_rest")
        self.assertTrue(self.book.bootstrap(old.symbol,b,as_of_ms=END_DECISION))
        batch=explore_event(self.book,self.event,capacity_slots=1)
        row=next(r for r in batch.rows if r.symbol==old.symbol and r.side=="LONG")
        self.assertEqual(row.states()["DONCHIAN_BREAKOUT_V1"],"MATCH")
        self.assertEqual(row.authority,ObservationAuthority.NONE)
        self.assertEqual(row.disposition,ObservationDisposition.NO_TRADE)
        self.assertFalse(hasattr(batch,"orders"))
        self.assertFalse(hasattr(row,"net_return"))

    def test_E11_reject_invalid_capacity_budget_and_types(self):
        for slots,limit in ((-1,100),(41,100),(True,100),(1,201),(1,-1),(1,True)):
            with self.subTest(slots=slots,limit=limit),self.assertRaises(ValueError):
                explore_event(self.book,self.event,capacity_slots=slots,evaluation_limit=limit)

    def test_E12_records_are_frozen_and_deterministic(self):
        self.bootstrap()
        a=explore_event(self.book,self.event,capacity_slots=1,evaluation_limit=3)
        b=explore_event(self.book,self.event,capacity_slots=1,evaluation_limit=3)
        self.assertEqual(a.batch_id,b.batch_id)
        self.assertEqual(a.as_record(),b.as_record())
        with self.assertRaises(FrozenInstanceError):a.capacity_slots=40
        with self.assertRaises(FrozenInstanceError):a.rows[0].side="BUY"

    def test_E13_under_100_cohort_gives_two_per_market(self):
        m=manifest(7)
        b=ObservationBook(m)
        e=FiveMinuteEvent(END_OPEN,END_DECISION)
        for sym in m.symbols:
            self.assertTrue(b.bootstrap(sym,history(sym),as_of_ms=END_DECISION))
        out=explore_event(b,e,capacity_slots=1)
        self.assertEqual(len(out.rows),14)
        self.assertEqual(out.evaluated_pairs,14)
        # Context families require at least ten valid symbols.
        self.assertTrue(all(r.market_regime=="UNAVAILABLE" for r in out.rows))

    def test_E14_reconnect_does_not_inherit_old_source(self):
        self.bootstrap()
        coin=self.universe.symbols[2]
        self.book.reconnect(coin,next_epoch=1,route="public_rest")
        result=explore_event(self.book,self.event,capacity_slots=1)
        self.assertEqual(result.source_skipped_pairs,2)
        self.assertEqual(result.evaluated_pairs,198)

    def test_E15_no_order_network_or_legacy_imports(self):
        from nbot_v5_1 import exploration, detector_rules
        self.assertFalse(hasattr(exploration,"submit_order"))
        self.assertFalse(hasattr(detector_rules,"load_histories"))
        self.assertFalse(hasattr(exploration,"open_position"))
        self.assertFalse(hasattr(exploration,"connect_binance"))


if __name__=="__main__": unittest.main()
