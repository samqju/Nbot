"""G4 100->20 BTC, fair sampling and prospective source-grade safety."""
import unittest
from dataclasses import replace
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep,DeepSelectionHold
from test_v5_1_g2 import manifest,history,END_OPEN,END_DECISION


class DeepSelectionTests(unittest.TestCase):
    def setUp(self):
        self.universe=manifest()
        book=ObservationBook(self.universe)
        for s in self.universe.symbols:
            self.assertTrue(book.bootstrap(s,history(s),as_of_ms=END_DECISION))
        self.g3=explore_event(book,FiveMinuteEvent(END_OPEN,END_DECISION),
                              capacity_slots=1,evaluation_limit=15)

    def test_S01_frozen_20_btc_and_all_100_denominator(self):
        out=choose_deep(self.universe,self.g3)
        self.assertEqual(len(out.entries),20)
        self.assertEqual(len(out.excluded),80)
        self.assertIn("BTCUSDT",out.symbols)
        self.assertEqual(len(set(out.symbols)),20)
        self.assertTrue(all(x.source_grade=="WARMUP_HOLD_NOT_ORIGINAL_VERIFIED"
                            for x in out.entries))
        self.assertTrue(all(x.state=="SELECTED_WARMUP_HOLD" for x in out.entries))
        self.assertTrue(out.no_trade)

    def test_S02_reproducible_ignores_pattern_count_and_outcomes(self):
        a=choose_deep(self.universe,self.g3)
        b=choose_deep(self.universe,self.g3)
        self.assertEqual(a,b)
        self.assertEqual(len(a.manifest_sha),64)
        self.assertNotIn("realized_net",repr(a))
        self.assertNotIn("profit",repr(a))

    def test_S03_all_strata_have_prospective_propensity(self):
        a=choose_deep(self.universe,self.g3)
        for x in (*a.entries,*a.excluded):
            self.assertTrue(0<=float(x.inclusion_probability)<=1)
            self.assertEqual(x.inclusion_probability,"1"
                      if x.symbol=="BTCUSDT" else x.inclusion_probability)
            self.assertTrue(x.groups)
        self.assertTrue(any(float(x.inclusion_probability)<1 for x in a.excluded))

    def test_S04_no_future_or_mismatched_exploration(self):
        with self.assertRaises(DeepSelectionHold):
            choose_deep(self.universe,replace(self.g3,universe_sha="bad"))
        with self.assertRaises(DeepSelectionHold):
            choose_deep(self.universe,replace(self.g3,decision_at_ms=0))

    def test_S05_capacity_zero_does_not_fabricate_patterns(self):
        book=ObservationBook(self.universe)
        g3=explore_event(book,FiveMinuteEvent(END_OPEN,END_DECISION),capacity_slots=0)
        result=choose_deep(self.universe,g3)
        self.assertEqual(len(result.entries),20)
        self.assertTrue(all(x.state=="SELECTED_WARMUP_HOLD" for x in result.entries))

    def test_S06_invalid_counts_hard_reject(self):
        for n in (0,21,-1,True,2.5):
            with self.subTest(n=n),self.assertRaises(DeepSelectionHold):
                choose_deep(self.universe,self.g3,count=n)

    def test_S07_smaller_eligible_cohort_honest_count(self):
        m=manifest(8)
        b=ObservationBook(m)
        g3=explore_event(b,FiveMinuteEvent(END_OPEN,END_DECISION),capacity_slots=0)
        r=choose_deep(m,g3,count=8)
        self.assertEqual(len(r.entries),8)
        self.assertEqual(len(r.excluded),0)
        with self.assertRaises(DeepSelectionHold):
            choose_deep(m,g3,count=20)

    def test_S08_different_precommitted_sampling_seed_rotates_nonbtc(self):
        a=choose_deep(self.universe,self.g3,seed="NBOT_V5_1_FIRST_COHORT")
        b=choose_deep(self.universe,self.g3,seed="NBOT_V5_1_NEXT_COHORT")
        self.assertEqual(len(a.entries),len(b.entries))
        self.assertEqual(set(a.symbols)&set(b.symbols)>={"BTCUSDT"},True)
        self.assertNotEqual(a.manifest_sha,b.manifest_sha)

if __name__=="__main__":unittest.main()
