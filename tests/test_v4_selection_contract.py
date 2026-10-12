"""V4 cross-path ranking and time-purged validation regression tests."""
import unittest
from types import SimpleNamespace

from nbot.observation.v4_generation import ResearchRow, _purge_training_groups
from nbot.observation.v4_research import HORIZON_MS, INTERVAL_MS
from nbot.observation.v4_selection import rank_candidates


class V4RankSelectionParityTests(unittest.TestCase):
    def test_negative_ranker_scores_are_valid_relative_ranks(self):
        low = SimpleNamespace(symbol="BTCUSDT", side="LONG", raw=-7.0)
        high = SimpleNamespace(symbol="ETHUSDT", side="SHORT", raw=-3.0)
        self.assertEqual(
            rank_candidates(lambda candidate: candidate.raw, [low, high]),
            [(-3.0, high), (-7.0, low)],
        )

    def test_invalid_scores_abstain_and_ties_are_deterministic(self):
        bad = SimpleNamespace(symbol="BADUSDT", side="LONG", raw=float("nan"))
        invalid = SimpleNamespace(symbol="ERRUSDT", side="LONG", raw=None)
        a = SimpleNamespace(symbol="BTCUSDT", side="SHORT", raw=0.0)
        b = SimpleNamespace(symbol="BTCUSDT", side="LONG", raw=0.0)
        ranked = rank_candidates(lambda c: c.raw, [bad, a, invalid, b])
        self.assertEqual([c.side for _, c in ranked], ["LONG", "SHORT"])
        self.assertEqual(rank_candidates(lambda c: c.raw, [bad, invalid]), [])

    def test_no_profit_threshold_is_inferred_from_rank_score(self):
        candidate = SimpleNamespace(symbol="BTCUSDT", side="LONG", raw=-.25)
        self.assertEqual(rank_candidates(lambda c: c.raw, [candidate])[0][0], -.25)


def row(event_ms, matured_at_ms, decision_id):
    return ResearchRow(decision_id, event_ms, "BTCUSDT", "LONG", {}, 0.5, matured_at_ms)


class V4PurgedValidationTests(unittest.TestCase):
    def test_exact_four_hour_horizon_boundary_is_safe(self):
        validation_event = 10 * HORIZON_MS
        validation_entry = validation_event + INTERVAL_MS
        safe_event = validation_event - HORIZON_MS
        train = [(safe_event, [row(safe_event, validation_entry, "a"),
                               row(safe_event, validation_entry, "b")])]
        self.assertEqual(_purge_training_groups(train, [(validation_event, [])]), train)

    def test_overlapping_four_hour_cohort_is_purged(self):
        validation_event = 10 * HORIZON_MS
        overlapping_event = validation_event - HORIZON_MS + INTERVAL_MS
        train = [(overlapping_event, [row(overlapping_event, validation_event, "a"),
                                     row(overlapping_event, validation_event, "b")])]
        self.assertEqual(_purge_training_groups(train, [(validation_event, [])]), [])

    def test_late_matured_evidence_is_purged_independently(self):
        validation_event = 10 * HORIZON_MS
        early = validation_event - 2 * HORIZON_MS
        first_entry = validation_event + INTERVAL_MS
        train = [(early, [row(early, first_entry - 1, "a"),
                          row(early, first_entry, "b"),
                          row(early, first_entry + 1, "late")])]
        result = _purge_training_groups(train, [(validation_event, [])])
        self.assertEqual([r.decision_id for r in result[0][1]], ["a", "b"])

    def test_no_validation_means_no_training_split(self):
        self.assertEqual(_purge_training_groups([(0, [row(0, 1, "a")])], []), [])


if __name__ == "__main__":
    unittest.main()
