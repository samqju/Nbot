import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.baseline_trainer import BaselineModelTrainer
from learning.challenger_evaluator import ChallengerArtifactEvaluator
from learning.ensemble_experiment import OfflineEnsembleExperiment
from learning.time_split import (
    TIME_SPLIT_BUILD_MODE,
    TimeAwareDatasetSplitter,
)
from tests import test_phase4_3_baseline_trainer as phase43
from tests import test_phase4_5_ensemble_experiment as phase45


class Phase75B1EndToEndMemorySafeTrainingTests(unittest.TestCase):
    def test_time_split_does_not_bulk_read_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            rows = []
            for index in range(20):
                rows.append({
                    "candidate_observation_id": f"candidate-{index}",
                    "market_event_id": f"event-{index}",
                    "observed_at_ms": index * 10_000,
                    "recorded_at_ms": index * 10_000 + 100,
                    "symbol": "BTCUSDT",
                    "direction": "LONG",
                    "pattern": "RANGE_BREAKOUT",
                    "outcome_type": "VIRTUAL_TRADE",
                    "features": {"short_range": 0.01},
                    "label_profitable": index % 2 == 0,
                })
            with dataset.open("w") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")

            with patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("bulk read_text forbidden"),
            ):
                report = TimeAwareDatasetSplitter(
                    dataset_path=str(dataset),
                    train_path=str(root / "train.jsonl"),
                    validation_path=str(root / "validation.jsonl"),
                    test_path=str(root / "test.jsonl"),
                    report_path=str(root / "report.json"),
                    train_ratio=0.60,
                    validation_ratio=0.20,
                    test_ratio=0.20,
                    embargo_seconds=0,
                    group_by_market_event=True,
                ).split()

            self.assertEqual(
                report["configuration"]["build_mode"],
                TIME_SPLIT_BUILD_MODE,
            )
            self.assertEqual(list(root.glob(".time-split.*")), [])

    def test_baseline_and_ensemble_train_without_read_text(self):
        baseline = phase43.T()
        ensemble = phase45.Phase45EnsembleExperimentTests()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b_train = root / "b-train.jsonl"
            b_validation = root / "b-validation.jsonl"
            baseline.write(
                b_train,
                [baseline.row(i, i % 2 == 0) for i in range(40)],
            )
            baseline.write(
                b_validation,
                [baseline.row(100 + i, i % 2 == 0) for i in range(12)],
            )

            e_train = root / "e-train.jsonl"
            e_validation = root / "e-validation.jsonl"
            ensemble._write(
                e_train,
                [ensemble._row(i, i % 2 == 0) for i in range(80)],
            )
            ensemble._write(
                e_validation,
                [ensemble._row(100 + i, i % 2 == 0) for i in range(30)],
            )

            with patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("bulk read_text forbidden"),
            ):
                baseline_report = BaselineModelTrainer(
                    train_path=b_train,
                    validation_path=b_validation,
                    test_path=None,
                    artifact_path=root / "baseline.pkl",
                    report_path=root / "baseline.json",
                    min_train_rows=20,
                    min_eval_rows=5,
                    evaluate_test=False,
                ).train()
                ensemble_report = OfflineEnsembleExperiment(
                    train_path=e_train,
                    validation_path=e_validation,
                    test_path=None,
                    artifact_path=root / "ensemble.pkl",
                    report_path=root / "ensemble.json",
                    min_train_rows=50,
                    min_eval_rows=20,
                    evaluate_test=False,
                ).run()

            self.assertEqual(baseline_report["status"], "TRAINED")
            self.assertEqual(
                baseline_report["matrix_build_mode"],
                "STREAMING_COMPACT_NUMPY",
            )
            self.assertEqual(
                ensemble_report["status"], "EXPERIMENT_COMPLETE"
            )
            self.assertEqual(
                ensemble_report["matrix_build_mode"],
                "STREAMING_COMPACT_NUMPY",
            )

    def test_challenger_evaluator_uses_compact_matrix_loader(self):
        helper = phase43.T()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train = root / "train.jsonl"
            validation = root / "validation.jsonl"
            test = root / "test.jsonl"
            helper.write(
                train,
                [helper.row(i, i % 2 == 0) for i in range(50)],
            )
            helper.write(
                validation,
                [helper.row(100 + i, i % 2 == 0) for i in range(20)],
            )
            helper.write(
                test,
                [helper.row(200 + i, i % 2 == 0) for i in range(20)],
            )
            artifact = root / "baseline.pkl"
            BaselineModelTrainer(
                train_path=train,
                validation_path=validation,
                test_path=None,
                artifact_path=artifact,
                report_path=root / "baseline.json",
                min_train_rows=20,
                min_eval_rows=5,
                evaluate_test=False,
            ).train()

            with patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("bulk read_text forbidden"),
            ):
                report = ChallengerArtifactEvaluator(
                    artifact_path=str(artifact),
                    validation_path=str(validation),
                    test_path=str(test),
                ).evaluate()

            self.assertEqual(report["status"], "EVALUATED")
            self.assertEqual(
                report["matrix_build_mode"],
                "STREAMING_COMPACT_NUMPY",
            )


if __name__ == "__main__":
    unittest.main()
