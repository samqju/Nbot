import json
import tempfile
import unittest
from pathlib import Path

from learning.time_split import TimeAwareDatasetSplitter


class Phase42TimeSplitTests(unittest.TestCase):
    def _row(
        self,
        candidate_id,
        observed_at_ms,
        *,
        outcome_type="VIRTUAL_TRADE",
        recorded_offset=100,
        label=True,
    ):
        return {
            "candidate_observation_id": candidate_id,
            "observed_at_ms": observed_at_ms,
            "recorded_at_ms": observed_at_ms + recorded_offset,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "outcome_type": outcome_type,
            "features": {"short_range": 0.01},
            "label_profitable": label,
        }

    @staticmethod
    def _write_jsonl(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )

    def _split(self, root, rows, embargo_seconds=0):
        root = Path(root)
        dataset = root / "dataset.jsonl"
        train = root / "train.jsonl"
        validation = root / "validation.jsonl"
        test = root / "test.jsonl"
        report = root / "report.json"
        self._write_jsonl(dataset, rows)

        document = TimeAwareDatasetSplitter(
            dataset_path=str(dataset),
            train_path=str(train),
            validation_path=str(validation),
            test_path=str(test),
            report_path=str(report),
            train_ratio=0.60,
            validation_ratio=0.20,
            test_ratio=0.20,
            embargo_seconds=embargo_seconds,
        ).split()
        return document, train, validation, test

    @staticmethod
    def _ids(path):
        return {
            json.loads(line)["candidate_observation_id"]
            for line in path.read_text().splitlines()
        }

    def test_candidate_outcomes_never_cross_splits(self):
        with tempfile.TemporaryDirectory() as root:
            rows = []
            for index in range(10):
                candidate_id = f"candidate-{index}"
                timestamp = 1000 + index * 1000
                rows.append(
                    self._row(candidate_id, timestamp)
                )
                rows.append(
                    self._row(
                        candidate_id,
                        timestamp,
                        outcome_type="FORWARD_5_CANDLE",
                        recorded_offset=200,
                    )
                )

            report, train, validation, test = self._split(root, rows)

            train_ids = self._ids(train)
            validation_ids = self._ids(validation)
            test_ids = self._ids(test)

            self.assertFalse(train_ids & validation_ids)
            self.assertFalse(train_ids & test_ids)
            self.assertFalse(validation_ids & test_ids)
            self.assertEqual(report["status"], "READY")
            self.assertEqual(
                report["splits"]["train"]["candidate_groups"],
                6,
            )
            self.assertEqual(
                report["splits"]["validation"]["candidate_groups"],
                2,
            )
            self.assertEqual(
                report["splits"]["test"]["candidate_groups"],
                2,
            )

    def test_splits_are_chronological(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._row(f"candidate-{index}", 1000 + index * 1000)
                for index in range(10)
            ]
            report, _, _, _ = self._split(root, rows)

            train = report["splits"]["train"]
            validation = report["splits"]["validation"]
            test = report["splits"]["test"]

            self.assertLess(
                train["last_observed_at_ms"],
                validation["first_observed_at_ms"],
            )
            self.assertLess(
                validation["last_observed_at_ms"],
                test["first_observed_at_ms"],
            )

    def test_embargo_excludes_boundary_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._row(
                    f"candidate-{index}",
                    index * 3_600_000,
                )
                for index in range(10)
            ]
            report, _, _, _ = self._split(
                root,
                rows,
                embargo_seconds=1800,
            )
            self.assertGreater(
                report["embargo"]["candidate_groups_excluded"],
                0,
            )

    def test_unlabeled_rows_are_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._row(f"candidate-{index}", index * 1000)
                for index in range(6)
            ]
            rows.append(
                self._row(
                    "unlabeled",
                    9999,
                    label=None,
                )
            )
            report, _, _, _ = self._split(root, rows)
            self.assertEqual(
                report["input"]["unlabeled_rows_excluded"],
                1,
            )

    def test_fewer_than_three_candidate_groups_is_insufficient(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._row("candidate-1", 1000),
                self._row("candidate-2", 2000),
            ]
            report, train, validation, test = self._split(root, rows)
            self.assertEqual(report["status"], "INSUFFICIENT_DATA")
            self.assertEqual(train.read_text(), "")
            self.assertEqual(validation.read_text(), "")
            self.assertEqual(test.read_text(), "")


if __name__ == "__main__":
    unittest.main()
