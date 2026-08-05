import unittest

from strategy.candidate import StrategyCandidate, rank_candidates
from strategy.features import CandidateFeatures

FEATURES = CandidateFeatures(0, 0, 0, 0, 0, 0, 0, 0, 0)


class Phase31CandidateArchitectureTests(unittest.TestCase):
    def test_candidate_normalizes_and_validates_fields(self):
        candidate = StrategyCandidate(
            symbol="btcusdt",
            direction="long",
            score=0.75,
            pattern="STRUCTURE_5M",
            bucket=123,
            features=FEATURES,
        )
        self.assertEqual(candidate.symbol, "BTCUSDT")
        self.assertEqual(candidate.direction, "LONG")
        self.assertEqual(candidate.score, 0.75)

    def test_invalid_direction_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "CANDIDATE_DIRECTION_INVALID",
        ):
            StrategyCandidate(
                symbol="BTCUSDT",
                direction="SIDEWAYS",
                score=1.0,
                pattern="STRUCTURE_5M",
                bucket=1,
                features=FEATURES,
            )

    def test_ranking_is_score_descending(self):
        candidates = [
            StrategyCandidate("ETHUSDT", "LONG", 0.5, "A", 1, FEATURES),
            StrategyCandidate("BTCUSDT", "SHORT", 0.9, "A", 1, FEATURES),
            StrategyCandidate("SOLUSDT", "LONG", 0.7, "A", 1, FEATURES),
        ]
        ranked = rank_candidates(candidates)
        self.assertEqual(
            [item.symbol for item in ranked],
            ["BTCUSDT", "SOLUSDT", "ETHUSDT"],
        )

    def test_ranking_ties_are_deterministic(self):
        candidates = [
            StrategyCandidate("ETHUSDT", "LONG", 0.5, "A", 1, FEATURES),
            StrategyCandidate("BTCUSDT", "SHORT", 0.5, "A", 1, FEATURES),
            StrategyCandidate("BTCUSDT", "LONG", 0.5, "A", 1, FEATURES),
        ]
        ranked = rank_candidates(candidates)
        self.assertEqual(
            [(item.symbol, item.direction) for item in ranked],
            [
                ("BTCUSDT", "LONG"),
                ("BTCUSDT", "SHORT"),
                ("ETHUSDT", "LONG"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
