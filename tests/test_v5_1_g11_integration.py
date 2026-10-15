"""G11 actual contract-seam tests: all market, economic, and book data LAB only."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.research_book import VirtualResearchBook, SyntheticTick
from nbot_v5_1.research_intent import freeze_intent
from nbot_v5_1.research_journal import ResearchJournal, JournalHold
from nbot_v5_1.g11_integration import OfflineIntegratedPipeline, IntegrationHold
from nbot_v5_1.learning_contract import verified_learning_count, assemble_lab
from nbot_v5_1.training_lab import TrainingHold
from nbot_v5_1.paper_contract import PaperHold, authorize_real_paper_release
from nbot_v5_1.challenger_lab import (
    DualBookCompetition, CHAMPION, CHALLENGER, approve_model_promotion)

from test_v5_1_g2 import manifest, history, bar, END_OPEN, END_DECISION
from test_v5_1_g8_training import dataset as training_dataset, policy as training_policy
from test_v5_1_g10_challenger import cohort, protocol, market, KEY, K2

SHA = "a" * 64


class G11FullIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nbot-g11-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.universe = manifest()
        self.observation = ObservationBook(self.universe)
        self.research = VirtualResearchBook(ResearchJournal(self.root / "virtual.jsonl"))
        self.system = OfflineIntegratedPipeline(self.observation, self.research)
        self.event = FiveMinuteEvent(END_OPEN, END_DECISION)

    def ready(self):
        for s in self.universe.symbols:
            self.assertTrue(self.observation.bootstrap(
                s, history(s), as_of_ms=END_DECISION))

    def plan(self, symbol="BTCUSDT", side="LONG", **changes):
        # Supplier sees only the just-reviewed prospective frozen deep cohort.
        if not hasattr(self, "_cached_deep"):
            batch = explore_event(self.observation, self.event,
                                  capacity_slots=self.research.vacancies)
            from nbot_v5_1.deep_selection import choose_deep
            self._cached_deep = choose_deep(self.universe, batch)
        deep = self._cached_deep
        opts = dict(symbol=symbol, side=side,
                    event_open_ms=self.event.event_open_ms,
                    declared_at_ms=self.event.decision_at_ms,
                    activates_at_ms=self.event.decision_at_ms + 1,
                    entry_reference="100",
                    stop="95" if side == "LONG" else "105",
                    target="105" if side == "LONG" else "95",
                    horizon_ms=INTERVAL_MS,
                    cohort_sha=deep.manifest_sha,
                    observation_sha=SHA, source_epoch=1,
                    source_grade="SYNTHETIC_OFFLINE_TEST_ONLY")
        opts.update(changes)
        return freeze_intent(**opts)

    def tick(self, symbol="BTCUSDT", price="105", seq=1, *, at=None,
             complete=None, epoch=1):
        return SyntheticTick(
            symbol, at if at is not None else END_DECISION + 180000,
            price, epoch, seq,
            complete if complete is not None else END_DECISION)

    def admission(self, *plans):
        return self.system.on_five_minute(
            self.event, supplier=lambda: tuple(plans))

    def lab(self):
        p = __import__("nbot_v5_1.paper_contract",
                       fromlist=["PaperPolicy"]).PaperPolicy()
        self.system.competition = DualBookCompetition(
            champion_journal=ResearchJournal(self.root / "champion.jsonl"),
            challenger_journal=ResearchJournal(self.root / "challenger.jsonl"),
            review_journal=ResearchJournal(self.root / "shared.jsonl"),
            policy=p, cohort=cohort(), protocol=protocol(p, cohort()),
            champion_key=KEY, challenger_key=K2)

    def test_I01_full_100_200_20_without_any_trading(self):
        self.ready()
        p = self.admission()
        self.assertEqual((p.universe_count, p.direction_count,
                          p.deep_count), (100, 200, 20))
        self.assertEqual((p.capacity_before, p.admitted, p.capacity_after),
                         (40, 0, 0))
        self.assertEqual(p.financial_authority, "NONE")
        self.assertEqual(p.action, "NO_TRADE")
        self.assertEqual(self.research.status()["qualified_after_cost"], 0)

    def test_I02_admit_real_G5_40_pair_book_on_G3_G4_witness(self):
        self.ready()
        from nbot_v5_1.deep_selection import choose_deep
        b = explore_event(self.observation, self.event, capacity_slots=40)
        deep = choose_deep(self.universe, b)
        plans = [self.plan(s, side) for s in deep.symbols
                 for side in ("LONG", "SHORT")]
        result = self.admission(*plans)
        self.assertEqual(result.admitted, 40)
        self.assertEqual(self.research.occupied, 40)
        self.assertEqual(len(self.system._origins), 40)
        self.assertTrue(all(x.source_grade == "SYNTHETIC_OFFLINE_TEST_ONLY"
                            for x in self.research.active.values()
                            for x in (x.intent,)))

    def test_I03_one_shared_source_tick_updates_two_virtual_sides(self):
        self.ready()
        self.admission(self.plan("BTCUSDT", "LONG"),
                       self.plan("BTCUSDT", "SHORT"))
        terminal = self.system.on_synthetic_tick(self.tick())
        self.assertEqual({x.reason for x in terminal}, {"STOP", "TARGET"})
        self.assertEqual(self.research.occupied, 0)

    def test_I04_G5_terminal_goes_to_G7_as_cost_pending(self):
        self.ready()
        self.admission(self.plan())
        t = self.system.on_synthetic_tick(self.tick())[0]
        row = self.system.record_synthetic_outcome(t)
        self.assertEqual(row.economic_state, "COST_PENDING")
        self.assertIsNone(row.net_r)
        self.assertEqual(len(row.provenance), 8)
        science = self.system.review_science(cutoff_ms=t.at_ms)
        self.assertEqual((science.synthetic_rows, science.genuine_original_rows,
                          science.pending_rows, science.release_action),
                         (1, 0, 1, "HOLD"))

    def test_I05_explicit_modeled_net_R_still_not_original(self):
        self.ready()
        self.admission(self.plan())
        t = self.system.on_synthetic_tick(self.tick())[0]
        row = self.system.record_synthetic_outcome(t, modeled_net_r="0.7")
        self.assertEqual(row.economic_state, "SYNTHETIC_MODELED")
        self.assertEqual(row.source_grade, "SYNTHETIC_OFFLINE_TEST_ONLY")
        ds = assemble_lab((row,), cutoff_ms=t.at_ms)
        self.assertEqual(verified_learning_count(ds), 0)

    def test_I06_second_scoring_of_same_terminal_is_rejected(self):
        self.ready()
        self.admission(self.plan())
        t = self.system.on_synthetic_tick(self.tick())[0]
        self.system.record_synthetic_outcome(t)
        with self.assertRaises(IntegrationHold):
            self.system.record_synthetic_outcome(t, modeled_net_r="3")

    def test_I07_unknown_terminal_cannot_get_G7_lineage(self):
        self.ready()
        self.admission(self.plan())
        t = self.system.on_synthetic_tick(self.tick())[0]
        with self.assertRaises(IntegrationHold):
            self.system.record_synthetic_outcome(replace(t, at_ms=t.at_ms + 1))

    def test_I08_closed_five_minute_cannot_be_replayed(self):
        self.ready()
        self.admission()
        with self.assertRaises(IntegrationHold):
            self.system.on_five_minute(self.event)

    def test_I09_no_bootstrap_source_keeps_200_denominator_no_invented_deep(self):
        p = self.admission()
        self.assertEqual(p.source_held_directions, 200)
        self.assertEqual(p.evaluated_directions, 0)
        self.assertEqual(p.admitted, 0)
        self.assertEqual(self.research.status()["qualified_after_cost"], 0)

    def test_I10_full_40_book_skips_expensive_re_evaluation_next_boundary(self):
        self.ready()
        from nbot_v5_1.deep_selection import choose_deep
        b = explore_event(self.observation, self.event, capacity_slots=40)
        cohort20 = choose_deep(self.universe, b)
        self.admission(*(self.plan(s, side) for s in cohort20.symbols
                          for side in ("LONG", "SHORT")))
        newer_open = END_OPEN + INTERVAL_MS
        newer_decision = END_DECISION + INTERVAL_MS
        for s in self.universe.symbols:
            self.observation.ingest(bar(s, newer_open,
                                        received=newer_decision),
                                    decision_at_ms=newer_decision)
        never = []
        p = self.system.on_five_minute(
            FiveMinuteEvent(newer_open, newer_decision),
            supplier=lambda: (never.append(True), ())[1])
        self.assertEqual((p.evaluated_directions, p.admitted,
                          p.capacity_after), (0, 0, 40))
        self.assertEqual(never, [])

    def test_I11_gap_holds_active_and_preserves_slot(self):
        self.ready()
        self.admission(self.plan())
        self.system.on_synthetic_tick(self.tick(seq=1, price="100"))
        result = self.system.on_synthetic_tick(
            self.tick(seq=3, at=END_DECISION + 10000, price="101"))
        self.assertEqual(result, ())
        self.assertEqual(self.research.occupied, 1)
        self.assertEqual(self.research.status()["held"], 1)

    def test_I12_synthetic_tick_never_promotes_source_grade(self):
        self.ready()
        self.admission(self.plan())
        with self.assertRaises(IntegrationHold):
            self.system.on_synthetic_tick(replace(
                self.tick(), source_grade="ORIGINAL_VERIFIED"))
        self.assertEqual(self.research.occupied, 1)

    def test_I13_empty_source_event_no_new_RESEARCH_venue(self):
        with self.assertRaises(IntegrationHold):
            self.system.on_synthetic_tick(self.tick())

    def test_I14_99_coin_cohort_is_not_G11_acceptance(self):
        book = ObservationBook(manifest(99))
        sys = OfflineIntegratedPipeline(
            book, VirtualResearchBook(ResearchJournal(self.root / "other.jsonl")))
        with self.assertRaises(IntegrationHold):
            sys.on_five_minute(self.event)

    def test_I15_wrong_uncertified_component_rejected(self):
        with self.assertRaises(IntegrationHold):
            OfflineIntegratedPipeline(self.observation, object())

    def test_I16_stale_or_future_g3_source_grade_cannot_pass(self):
        self.ready()
        self.observation.mark_gap("BTCUSDT", reason="MISSING_SOURCE")
        p = self.admission()
        self.assertGreaterEqual(p.source_held_directions, 2)
        self.assertEqual(p.financial_authority, "NONE")

    def test_I17_G7_G8_lab_training_always_ends_with_HOLD(self):
        # Use the genuine G7/G8 model implementations and original G8 laboratory
        # fixture population, NOT a claim of 60 captured G5 settlements.
        d = training_dataset(n=60, net="1.1")
        self.system.learning_rows = list(d.rows)
        proof = self.system.review_science(
            cutoff_ms=d.cutoff_ms, protocol=training_policy())
        self.assertEqual(proof.synthetic_rows, 60)
        self.assertEqual(proof.genuine_original_rows, 0)
        self.assertEqual(proof.release_action, "HOLD")
        self.assertIsNotNone(proof.lab_model_sha)

    def test_I18_G8_insufficient_original_or_training_block_holds(self):
        self.ready()
        self.admission(self.plan())
        t = self.system.on_synthetic_tick(self.tick())[0]
        self.system.record_synthetic_outcome(t)
        with self.assertRaises(TrainingHold):
            self.system.review_science(
                cutoff_ms=t.at_ms, protocol=training_policy())

    def test_I19_shared_G9_G10_guardians_are_actual_unchanged_code(self):
        self.ready()
        self.admission()
        self.lab()
        x = self.system.on_lab_paper_event(market(0))
        self.assertTrue(x.champion_occupied and x.challenger_occupied)
        self.assertEqual(x.authority, "NONE")
        x2 = self.system.on_lab_paper_event(market(1))
        self.assertFalse(x2.champion_occupied or x2.challenger_occupied)
        review = self.system.review_competition()
        self.assertEqual(review.genuine_paper_settlements, 0)
        self.assertEqual(review.action, "HOLD")

    def test_I20_G10_duplicate_market_event_rejected(self):
        self.ready()
        self.admission()
        self.lab()
        x = market(0)
        self.system.on_lab_paper_event(x)
        with self.assertRaises(IntegrationHold):
            self.system.on_lab_paper_event(x)

    def test_I21_unselected_deep_market_rejected_for_books(self):
        self.ready()
        self.admission()
        self.lab()
        x = market(0)
        from nbot_v5_1.paper_contract import PaperQuote
        with self.assertRaises(IntegrationHold):
            self.system.on_lab_paper_event(
                replace(x, quote=replace(x.quote, symbol="NOTSELECTEDUSDT")))

    def test_I22_genuine_PAPER_and_promotion_still_raise_HOLD(self):
        with self.assertRaises(PaperHold):
            authorize_real_paper_release()
        with self.assertRaises(PaperHold):
            approve_model_promotion()

    def test_I23_G10_missing_comparison_cannot_admit_paper(self):
        self.ready()
        self.admission()
        with self.assertRaises(IntegrationHold):
            self.system.on_lab_paper_event(market(0))

    def test_I24_G5_crash_rebuild_retains_source_uncertainty(self):
        self.ready()
        self.admission(self.plan())
        newer = VirtualResearchBook(
            ResearchJournal(self.root / "virtual.jsonl"))
        self.assertEqual(newer.occupied, 1)
        self.assertEqual(newer.status()["held"], 1)
        self.assertEqual(newer.status()["qualified_after_cost"], 0)

    def test_I25_source_journal_tampering_never_autorepairs(self):
        self.ready()
        self.admission(self.plan())
        p = self.root / "virtual.jsonl"
        content = p.read_bytes()
        p.write_bytes(content[:-2] + b"\x00\n")
        with self.assertRaises(JournalHold):
            VirtualResearchBook(ResearchJournal(p))

    def test_I26_horizon_first_touch_is_event_time_not_boundary(self):
        self.ready()
        self.admission(self.plan())
        at = END_DECISION + 120000
        t = self.system.on_synthetic_tick(
            self.tick(price="105", at=at))[0]
        self.assertEqual(t.at_ms, at)
        self.assertLess(t.at_ms, END_DECISION + INTERVAL_MS)

    def test_I27_complete_40_research_all_journalled_with_replay(self):
        self.ready()
        from nbot_v5_1.deep_selection import choose_deep
        b = explore_event(self.observation, self.event, capacity_slots=40)
        dep = choose_deep(self.universe, b)
        self.admission(*(self.plan(s, side) for s in dep.symbols
                         for side in ("LONG", "SHORT")))
        rows, head = self.research.journal.replay()
        self.assertEqual(len([x for x in rows if x["action"] == "ADMIT"]), 40)
        self.assertEqual(len(head), 64)
        self.assertEqual(self.research.status()["qualified_after_cost"], 0)


if __name__ == "__main__":
    unittest.main()
