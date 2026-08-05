import json
import tempfile
import unittest
from pathlib import Path

from learning.dataset_builder import (
    CANDIDATE_FEATURE_NAMES,
    TrainingDatasetBuilder,
)


class Phase41DatasetBuilderTests(unittest.TestCase):
    def _features(self):
        return {
            name: float(index + 1)
            for index, name in enumerate(CANDIDATE_FEATURE_NAMES)
        }

    def _observation(self, observation_id="candidate-1"):
        return {
            "schema_version": 3,
            "observation_type": "STRATEGY_CANDIDATE",
            "observed_at_ms": 1000,
            "candidate_observation_id": observation_id,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "bucket": 10,
            "rule_score": 0.7,
            "final_score": 0.8,
            "score_breakdown": {"final_score": 0.8},
            "reference_price": 100.0,
            "risk_plan": {"advisory_only": True},
            "rank": 1,
            "selected": True,
            "eligible_for_training": True,
            "features": self._features(),
            "structure_fingerprint": {"regime": "UP"},
        }

    def _make_outcome(
        self,
        observation_id="candidate-1",
        *,
        outcome_type="VIRTUAL_TRADE",
        recorded_at_ms=2000,
    ):
        return {
            "schema_version": 1,
            "observation_type": "CANDIDATE_OUTCOME",
            "recorded_at_ms": recorded_at_ms,
            "candidate_observation_id": observation_id,
            "outcome_type": outcome_type,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "payload": {"exit_r": 2.0, "profitable": True},
        }

    @staticmethod
    def _write_jsonl(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )

    def _build(self, root, observations, outcomes):
        root = Path(root)
        observations_path = root / "observations.jsonl"
        outcomes_path = root / "outcomes.jsonl"
        dataset_path = root / "dataset.jsonl"
        report_path = root / "report.json"
        self._write_jsonl(observations_path, observations)
        self._write_jsonl(outcomes_path, outcomes)
        report = TrainingDatasetBuilder(
            observations_path=str(observations_path),
            outcomes_path=str(outcomes_path),
            dataset_path=str(dataset_path),
            report_path=str(report_path),
        ).build()
        return report, dataset_path, report_path

    def test_linked_outcome_creates_training_row(self):
        with tempfile.TemporaryDirectory() as root:
            report, dataset_path, report_path = self._build(
                root,
                [self._observation()],
                [self._make_outcome()],
            )
            rows = [
                json.loads(line)
                for line in dataset_path.read_text().splitlines()
            ]
            self.assertEqual(report["status"], "READY")
            self.assertEqual(report["output"]["rows_written"], 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                rows[0]["candidate_observation_id"],
                "candidate-1",
            )
            self.assertTrue(rows[0]["label_profitable"])
            self.assertEqual(rows[0]["target_r"], 2.0)
            self.assertTrue(report_path.exists())

    def test_multiple_outcome_types_create_separate_rows(self):
        with tempfile.TemporaryDirectory() as root:
            report, dataset_path, _ = self._build(
                root,
                [self._observation()],
                [
                    self._make_outcome(
                        outcome_type="FORWARD_5_CANDLE",
                        recorded_at_ms=2000,
                    ),
                    self._make_outcome(
                        outcome_type="VIRTUAL_TRADE",
                        recorded_at_ms=3000,
                    ),
                ],
            )
            self.assertEqual(report["output"]["rows_written"], 2)
            rows = [
                json.loads(line)
                for line in dataset_path.read_text().splitlines()
            ]
            self.assertEqual(
                {row["outcome_type"] for row in rows},
                {"FORWARD_5_CANDLE", "VIRTUAL_TRADE"},
            )

    def test_orphan_outcome_is_reported_and_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            report, dataset_path, _ = self._build(
                root,
                [self._observation()],
                [self._make_outcome("unknown-candidate")],
            )
            self.assertEqual(report["status"], "EMPTY")
            self.assertEqual(report["issues"]["orphan_outcome"], 1)
            self.assertEqual(dataset_path.read_text(), "")

    def test_duplicate_observation_id_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            report, _, _ = self._build(
                root,
                [self._observation(), self._observation()],
                [self._make_outcome()],
            )
            self.assertEqual(
                report["issues"]["duplicate_observation_id"],
                1,
            )
            self.assertEqual(report["output"]["rows_written"], 0)

    def test_feature_schema_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            observation = self._observation()
            observation["features"] = dict(
                reversed(list(observation["features"].items()))
            )
            report, _, _ = self._build(
                root,
                [observation],
                [self._make_outcome()],
            )
            self.assertEqual(
                report["issues"][
                    "observation_feature_schema_mismatch"
                ],
                1,
            )

    def test_missing_inputs_produce_empty_integrity_report(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            report = TrainingDatasetBuilder(
                observations_path=str(root / "missing-observations"),
                outcomes_path=str(root / "missing-outcomes"),
                dataset_path=str(root / "dataset.jsonl"),
                report_path=str(root / "report.json"),
            ).build()
            self.assertEqual(report["status"], "EMPTY")
            self.assertEqual(
                report["issues"]["observations_file_missing"],
                1,
            )
            self.assertEqual(
                report["issues"]["outcomes_file_missing"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
