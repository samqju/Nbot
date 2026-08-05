import json
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from learning.shadow_scorer import ShadowModelScorer, ShadowModelError
from strategy.candidate import StrategyCandidate
from strategy.features import CandidateFeatures


FEATURE_NAMES = (
    "short_range",
    "long_range",
    "trend_score",
    "wick_ratio_recent",
    "body_ratio_recent",
    "range_acceleration",
    "dist_high",
    "dist_low",
    "directional_consistency",
)


class Breakdown:
    def __init__(self, rule_score):
        self.rule_score = rule_score


class Phase46ShadowScoringTests(unittest.TestCase):
    def _candidate(self, symbol, score, pattern="RANGE_BREAKOUT"):
        features = CandidateFeatures(
            short_range=0.01,
            long_range=0.02,
            trend_score=5.0,
            wick_ratio_recent=0.2,
            body_ratio_recent=0.8,
            range_acceleration=1.1,
            dist_high=0.01,
            dist_low=0.02,
            directional_consistency=0.7,
        )
        return StrategyCandidate(
            symbol=symbol,
            direction="LONG",
            score=score,
            pattern=pattern,
            bucket=1,
            features=features,
            score_breakdown=Breakdown(score - 0.1),
            reference_price=100.0,
        )

    def _artifact(self, candidates):
        patterns = ("RANGE_BREAKOUT",)
        rows = []
        labels = []
        for index in range(20):
            candidate = candidates[index % len(candidates)]
            vector = (
                [
                    float(candidate.features.as_dict()[name])
                    for name in FEATURE_NAMES
                ]
                + [
                    float(candidate.score_breakdown.rule_score),
                    float(candidate.score),
                    1.0,
                ]
                + [1.0]
            )
            vector[0] += index * 0.01
            rows.append(vector)
            labels.append(index % 2)

        X = np.asarray(rows, dtype=float)
        y = np.asarray(labels, dtype=int)
        scaler = StandardScaler().fit(X)
        model = LogisticRegression(max_iter=1000).fit(
            scaler.transform(X),
            y,
        )
        return {
            "artifact_schema_version": 1,
            "artifact_kind": "OFFLINE_ENSEMBLE_EXPERIMENT",
            "base_feature_names": FEATURE_NAMES,
            "pattern_categories": patterns,
            "vector_columns": tuple(range(X.shape[1])),
            "scaler": scaler,
            "models": {"LOGISTIC_REGRESSION": model},
            "winner": {
                "kind": "MODEL",
                "name": "LOGISTIC_REGRESSION",
            },
            "runtime_activation": "DISABLED",
        }

    def test_shadow_scores_without_mutating_rule_order(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            first = self._candidate("BTCUSDT", 0.9)
            second = self._candidate("ETHUSDT", 0.8)
            candidates = [first, second]

            artifact_path = root / "artifact.pkl"
            artifact_path.write_bytes(
                pickle.dumps(self._artifact(candidates))
            )
            predictions_path = root / "predictions.jsonl"

            result = ShadowModelScorer(
                enabled=True,
                artifact_path=artifact_path,
                predictions_path=predictions_path,
                refresh_seconds=300,
            ).score_candidates(
                candidates,
                rule_selected_candidate=first,
            )

            self.assertEqual(candidates, [first, second])
            self.assertEqual(len(result), 2)
            self.assertTrue(
                any(row["rule_selected"] for row in result)
            )
            self.assertTrue(
                all(row["runtime_effect"] == "NONE" for row in result)
            )
            written = [
                json.loads(line)
                for line in predictions_path.read_text().splitlines()
            ]
            self.assertEqual(len(written), 2)

    def test_disabled_scorer_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "predictions.jsonl"
            result = ShadowModelScorer(
                enabled=False,
                artifact_path=Path(root) / "missing.pkl",
                predictions_path=path,
            ).score_candidates(
                [self._candidate("BTCUSDT", 0.9)]
            )
            self.assertEqual(result, [])
            self.assertFalse(path.exists())

    def test_missing_artifact_fails_open_for_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            result = ShadowModelScorer(
                enabled=True,
                artifact_path=Path(root) / "missing.pkl",
                predictions_path=Path(root) / "predictions.jsonl",
            ).score_candidates(
                [self._candidate("BTCUSDT", 0.9)]
            )
            self.assertEqual(result, [])

    def test_runtime_enabled_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            candidate = self._candidate("BTCUSDT", 0.9)
            artifact = self._artifact([candidate])
            artifact["runtime_activation"] = "ENABLED"
            artifact_path = root / "artifact.pkl"
            artifact_path.write_bytes(pickle.dumps(artifact))

            scorer = ShadowModelScorer(
                enabled=True,
                artifact_path=artifact_path,
                predictions_path=root / "predictions.jsonl",
            )
            self.assertIsNone(scorer._get_artifact())


if __name__ == "__main__":
    unittest.main()
