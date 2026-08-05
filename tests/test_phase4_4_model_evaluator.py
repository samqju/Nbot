import json
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from learning.model_evaluator import (
    BaselineModelEvaluator,
    ModelEvaluationError,
)


FEATURES = (
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


class Phase44ModelEvaluatorTests(unittest.TestCase):
    def _row(self, index, label):
        return {
            "candidate_observation_id": f"candidate-{index}",
            "outcome_type": "VIRTUAL_TRADE",
            "label_profitable": label,
            "direction": "LONG" if index % 2 else "SHORT",
            "pattern": (
                "RANGE_BREAKOUT"
                if index % 3 else "MEAN_REVERSION"
            ),
            "rule_score": 0.4 + (index % 5) * 0.1,
            "final_score": 0.5 + (index % 4) * 0.1,
            "features": {
                name: float(index + offset + 1) / 100.0
                for offset, name in enumerate(FEATURES)
            },
        }

    @staticmethod
    def _vector(row, patterns):
        return (
            [float(row["features"][name]) for name in FEATURES]
            + [
                float(row["rule_score"]),
                float(row["final_score"]),
                1.0 if row["direction"] == "LONG" else 0.0,
            ]
            + [
                1.0 if row["pattern"] == pattern else 0.0
                for pattern in patterns
            ]
        )

    def _artifact(self, rows):
        patterns = tuple(sorted({row["pattern"] for row in rows}))
        X = np.asarray(
            [self._vector(row, patterns) for row in rows],
            dtype=float,
        )
        y = np.asarray(
            [int(row["label_profitable"]) for row in rows],
            dtype=int,
        )
        scaler = StandardScaler()
        transformed = scaler.fit_transform(X)
        model = LogisticRegression(max_iter=1000)
        model.fit(transformed, y)
        return {
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "created_at_ms": 123,
            "outcome_type": "VIRTUAL_TRADE",
            "feature_schema_version": 3,
            "base_feature_names": FEATURES,
            "pattern_categories": patterns,
            "vector_columns": tuple(range(X.shape[1])),
            "scaler": scaler,
            "model": model,
            "training_rows": len(rows),
            "runtime_activation": "DISABLED",
        }

    @staticmethod
    def _write_rows(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )

    def test_evaluation_and_calibration_reports_are_written(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            training = [
                self._row(index, index % 2 == 0)
                for index in range(40)
            ]
            validation = [
                self._row(100 + index, index % 2 == 0)
                for index in range(20)
            ]
            test = [
                self._row(200 + index, index % 2 == 0)
                for index in range(20)
            ]
            artifact_path = root / "model.pkl"
            artifact_path.write_bytes(
                pickle.dumps(self._artifact(training))
            )
            validation_path = root / "validation.jsonl"
            test_path = root / "test.jsonl"
            self._write_rows(validation_path, validation)
            self._write_rows(test_path, test)

            evaluation_path = root / "evaluation.json"
            calibration_path = root / "calibration.json"
            report = BaselineModelEvaluator(
                artifact_path=artifact_path,
                validation_path=validation_path,
                test_path=test_path,
                evaluation_report_path=evaluation_path,
                calibration_report_path=calibration_path,
                min_subgroup_rows=5,
                calibration_bins=10,
                drift_bins=5,
            ).evaluate()

            self.assertEqual(report["status"], "EVALUATED")
            self.assertEqual(
                report["runtime_activation"],
                "DISABLED",
            )
            self.assertIn("f1", report["metrics"]["test"])
            self.assertIn(
                "confusion_matrix",
                report["metrics"]["validation"],
            )
            self.assertEqual(
                len(
                    json.loads(
                        calibration_path.read_text()
                    )["test"]
                ),
                10,
            )
            self.assertTrue(evaluation_path.exists())
            self.assertIsNotNone(
                report["recommended_threshold"]
            )

    def test_runtime_enabled_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            rows = [
                self._row(index, index % 2 == 0)
                for index in range(20)
            ]
            artifact = self._artifact(rows)
            artifact["runtime_activation"] = "ENABLED"
            artifact_path = root / "model.pkl"
            artifact_path.write_bytes(pickle.dumps(artifact))

            with self.assertRaisesRegex(
                ModelEvaluationError,
                "MODEL_EVALUATION_RUNTIME_FLAG_INVALID",
            ):
                BaselineModelEvaluator(
                    artifact_path=artifact_path,
                    validation_path=root / "validation",
                    test_path=root / "test",
                    evaluation_report_path=root / "evaluation",
                    calibration_report_path=root / "calibration",
                ).evaluate()

    def test_missing_rows_produce_insufficient_status(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            rows = [
                self._row(index, index % 2 == 0)
                for index in range(20)
            ]
            artifact_path = root / "model.pkl"
            artifact_path.write_bytes(
                pickle.dumps(self._artifact(rows))
            )
            report = BaselineModelEvaluator(
                artifact_path=artifact_path,
                validation_path=root / "missing-validation",
                test_path=root / "missing-test",
                evaluation_report_path=root / "evaluation.json",
                calibration_report_path=root / "calibration.json",
            ).evaluate()
            self.assertEqual(
                report["status"],
                "INSUFFICIENT_DATA",
            )


if __name__ == "__main__":
    unittest.main()
