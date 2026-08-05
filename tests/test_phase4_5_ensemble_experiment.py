import json
import pickle
import tempfile
import unittest
from pathlib import Path

from learning.ensemble_experiment import OfflineEnsembleExperiment


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


class Phase45EnsembleExperimentTests(unittest.TestCase):
    def _row(self, index, label):
        signal = 1.0 if label else -1.0
        return {
            "candidate_observation_id": f"candidate-{index}",
            "outcome_type": "VIRTUAL_TRADE",
            "label_profitable": bool(label),
            "direction": "LONG" if index % 2 else "SHORT",
            "pattern": (
                "RANGE_BREAKOUT"
                if index % 3 else "MEAN_REVERSION"
            ),
            "rule_score": 0.5 + signal * 0.15,
            "final_score": 0.5 + signal * 0.20,
            "features": {
                name: (
                    signal * (offset + 1)
                    + (index % 7) * 0.03
                )
                for offset, name in enumerate(FEATURES)
            },
        }

    @staticmethod
    def _write(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )

    def test_experiment_selects_validation_winner(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            train = root / "train.jsonl"
            validation = root / "validation.jsonl"
            test = root / "test.jsonl"
            artifact = root / "ensemble.pkl"
            report = root / "report.json"

            self._write(
                train,
                [
                    self._row(index, index % 2 == 0)
                    for index in range(80)
                ],
            )
            self._write(
                validation,
                [
                    self._row(100 + index, index % 2 == 0)
                    for index in range(30)
                ],
            )
            self._write(
                test,
                [
                    self._row(200 + index, index % 2 == 0)
                    for index in range(30)
                ],
            )

            result = OfflineEnsembleExperiment(
                train_path=train,
                validation_path=validation,
                test_path=test,
                artifact_path=artifact,
                report_path=report,
                min_train_rows=50,
                min_eval_rows=20,
                random_state=7,
            ).run()

            self.assertEqual(
                result["status"],
                "EXPERIMENT_COMPLETE",
            )
            self.assertTrue(artifact.exists())
            document = pickle.loads(artifact.read_bytes())
            self.assertEqual(
                document["runtime_activation"],
                "DISABLED",
            )
            self.assertFalse(
                result["winner"]["selected_using_test_data"]
            )
            self.assertIn(
                result["winner"]["kind"],
                {"MODEL", "BLEND"},
            )
            self.assertIn(
                "LOGISTIC_REGRESSION",
                result["individual_metrics"]["validation"],
            )
            self.assertTrue(
                result["blend_validation_metrics"]
            )

    def test_insufficient_data_does_not_write_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            train = root / "train.jsonl"
            validation = root / "validation.jsonl"
            test = root / "test.jsonl"
            artifact = root / "ensemble.pkl"
            report = root / "report.json"
            rows = [
                self._row(index, index % 2 == 0)
                for index in range(10)
            ]
            self._write(train, rows)
            self._write(validation, rows)
            self._write(test, rows)

            result = OfflineEnsembleExperiment(
                train_path=train,
                validation_path=validation,
                test_path=test,
                artifact_path=artifact,
                report_path=report,
                min_train_rows=50,
                min_eval_rows=20,
            ).run()

            self.assertEqual(
                result["status"],
                "INSUFFICIENT_DATA",
            )
            self.assertFalse(artifact.exists())
            self.assertTrue(report.exists())

    def test_duplicate_candidates_are_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            train = root / "train.jsonl"
            validation = root / "validation.jsonl"
            test = root / "test.jsonl"
            artifact = root / "ensemble.pkl"
            report = root / "report.json"

            train_rows = [
                self._row(index, index % 2 == 0)
                for index in range(60)
            ]
            train_rows.append(dict(train_rows[0]))
            self._write(train, train_rows)
            self._write(
                validation,
                [
                    self._row(100 + index, index % 2 == 0)
                    for index in range(20)
                ],
            )
            self._write(
                test,
                [
                    self._row(200 + index, index % 2 == 0)
                    for index in range(20)
                ],
            )

            result = OfflineEnsembleExperiment(
                train_path=train,
                validation_path=validation,
                test_path=test,
                artifact_path=artifact,
                report_path=report,
                min_train_rows=50,
                min_eval_rows=20,
            ).run()

            self.assertEqual(
                result["issues"]["train_candidate_duplicate"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
