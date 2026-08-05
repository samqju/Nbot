import json
import tempfile
import unittest
from pathlib import Path

from strategy.candidate import StrategyCandidate
from strategy.candidate_observer import CandidateObservationWriter
from strategy.features import (
    CANDIDATE_FEATURE_NAMES,
    CANDIDATE_FEATURE_SCHEMA_VERSION,
    CandidateFeatureExtractor,
    CandidateFeatures,
)


class FakeStrategy:
    SHORT_WINDOW = 2
    LONG_WINDOW = 4

    @staticmethod
    def _avg_range(candles, window):
        rows = list(candles)[-window:]
        return sum(h - l for _, h, l, _ in rows) / len(rows)

    @staticmethod
    def _trend_score(candles):
        closes = [row[3] for row in candles]
        return sum(
            1 if closes[idx] > closes[idx - 1] else -1
            for idx in range(1, len(closes))
        )


class Phase32FeatureObservationTests(unittest.TestCase):
    def _candles(self):
        rows = []
        price = 100.0
        for _ in range(25):
            rows.append((price, price + 1.0, price - 1.0, price + 0.5))
            price += 0.5
        return rows

    def test_feature_schema_is_stable(self):
        self.assertEqual(CANDIDATE_FEATURE_SCHEMA_VERSION, 3)
        self.assertEqual(len(CANDIDATE_FEATURE_NAMES), 9)

    def test_feature_extractor_returns_ordered_vector(self):
        features = CandidateFeatureExtractor(FakeStrategy()).extract(
            self._candles()
        )
        self.assertEqual(features.as_numpy().shape, (1, 9))
        self.assertEqual(
            tuple(features.as_dict()),
            CANDIDATE_FEATURE_NAMES,
        )

    def test_insufficient_history_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "FEATURE_HISTORY_INSUFFICIENT",
        ):
            CandidateFeatureExtractor(FakeStrategy()).extract(
                self._candles()[:10]
            )

    def test_observation_writer_records_selected_and_rejected_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidates.jsonl"
            features = CandidateFeatures(
                0.01, 0.02, 5, 0.4, 0.6, 0.5, -0.01, 0.03, 4
            )
            candidate = StrategyCandidate(
                "BTCUSDT",
                "LONG",
                0.8,
                "STRUCTURE_5M",
                123,
                features,
                {"trend": "UP"},
            )
            writer = CandidateObservationWriter(str(path))
            writer.append(candidate, rank=1, selected=True)
            writer.append(candidate, rank=2, selected=False)

            rows = [
                json.loads(line)
                for line in path.read_text().splitlines()
            ]
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                rows[0]["candidate_observation_id"],
                candidate.observation_id,
            )
            self.assertTrue(rows[0]["selected"])
            self.assertFalse(rows[1]["selected"])
            self.assertTrue(rows[0]["eligible_for_training"])
            self.assertEqual(rows[0]["rule_score"], 0.8)
            self.assertEqual(rows[0]["final_score"], 0.8)
            self.assertIsNone(rows[0]["score_breakdown"])
            self.assertEqual(
                tuple(rows[0]["features"]),
                CANDIDATE_FEATURE_NAMES,
            )


if __name__ == "__main__":
    unittest.main()
