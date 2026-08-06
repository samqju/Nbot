"""Chronological candidate-group split with leakage controls."""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections import Counter
from pathlib import Path


class TimeSplitError(RuntimeError):
    pass


class TimeAwareDatasetSplitter:
    """Split labeled rows chronologically while keeping candidates intact."""

    def __init__(
        self,
        *,
        dataset_path: str,
        train_path: str,
        validation_path: str,
        test_path: str,
        report_path: str,
        train_ratio: float,
        validation_ratio: float,
        test_ratio: float,
        embargo_seconds: int = 3600,
    ):
        self.dataset_path = Path(dataset_path)
        self.train_path = Path(train_path)
        self.validation_path = Path(validation_path)
        self.test_path = Path(test_path)
        self.report_path = Path(report_path)
        self.train_ratio = float(train_ratio)
        self.validation_ratio = float(validation_ratio)
        self.test_ratio = float(test_ratio)
        self.embargo_ms = int(embargo_seconds) * 1000

        ratios = (
            self.train_ratio,
            self.validation_ratio,
            self.test_ratio,
        )
        if any(ratio <= 0 or ratio >= 1 for ratio in ratios):
            raise ValueError("TIME_SPLIT_RATIO_RANGE_INVALID")
        if abs(sum(ratios) - 1.0) > 1e-9:
            raise ValueError("TIME_SPLIT_RATIO_SUM_INVALID")
        if self.embargo_ms < 0:
            raise ValueError("TIME_SPLIT_EMBARGO_INVALID")

    def split(self) -> dict:
        issues = Counter()
        rows = self._read_dataset(issues)

        grouped = {}
        unlabeled_rows = 0
        invalid_rows = 0

        for row in rows:
            error = self._validate_row(row)
            if error:
                issues[error] += 1
                invalid_rows += 1
                continue
            if row.get("label_profitable") is None:
                unlabeled_rows += 1
                continue

            candidate_id = row["candidate_observation_id"]
            grouped.setdefault(candidate_id, []).append(row)

        groups = []
        for candidate_id, candidate_rows in grouped.items():
            observed_times = {
                int(row["observed_at_ms"])
                for row in candidate_rows
            }
            if len(observed_times) != 1:
                issues["candidate_timestamp_inconsistent"] += 1
                continue

            directions = {row["direction"] for row in candidate_rows}
            symbols = {row["symbol"] for row in candidate_rows}
            patterns = {row["pattern"] for row in candidate_rows}
            if (
                len(directions) != 1
                or len(symbols) != 1
                or len(patterns) != 1
            ):
                issues["candidate_identity_inconsistent"] += 1
                continue

            groups.append({
                "candidate_id": candidate_id,
                "observed_at_ms": next(iter(observed_times)),
                "outcome_end_ms": max(
                    int(row["recorded_at_ms"])
                    for row in candidate_rows
                ),
                "rows": sorted(
                    candidate_rows,
                    key=lambda row: (
                        int(row["recorded_at_ms"]),
                        row["outcome_type"],
                    ),
                ),
            })

        groups.sort(
            key=lambda group: (
                group["observed_at_ms"],
                group["candidate_id"],
            )
        )

        status = "READY"
        split_groups = {
            "train": [],
            "validation": [],
            "test": [],
        }
        embargoed_groups = []
        purged_groups = []

        if len(groups) < 3:
            status = "INSUFFICIENT_DATA"
        else:
            train_count, validation_count = self._allocate_counts(
                len(groups)
            )
            test_start = train_count + validation_count

            raw_train = groups[:train_count]
            raw_validation = groups[train_count:test_start]
            raw_test = groups[test_start:]

            train_boundary = (
                raw_validation[0]["observed_at_ms"]
                if raw_validation else None
            )
            test_boundary = (
                raw_test[0]["observed_at_ms"]
                if raw_test else None
            )

            for group in raw_train:
                # Purge any training label whose observation window reaches
                # the validation boundary. This prevents future candles used
                # to label a training row from leaking into validation time.
                if (
                    train_boundary is not None
                    and group["outcome_end_ms"] >= train_boundary
                ):
                    purged_groups.append(group)
                elif (
                    train_boundary is not None
                    and group["observed_at_ms"]
                    >= train_boundary - self.embargo_ms
                ):
                    embargoed_groups.append(group)
                else:
                    split_groups["train"].append(group)

            for group in raw_validation:
                timestamp = group["observed_at_ms"]
                # Validation labels must finish before the untouched test
                # period begins. Rows crossing that boundary are purged.
                if (
                    test_boundary is not None
                    and group["outcome_end_ms"] >= test_boundary
                ):
                    purged_groups.append(group)
                    continue
                near_train_boundary = (
                    train_boundary is not None
                    and timestamp < train_boundary + self.embargo_ms
                )
                near_test_boundary = (
                    test_boundary is not None
                    and timestamp >= test_boundary - self.embargo_ms
                )
                if near_train_boundary or near_test_boundary:
                    embargoed_groups.append(group)
                else:
                    split_groups["validation"].append(group)

            for group in raw_test:
                if (
                    test_boundary is not None
                    and group["observed_at_ms"]
                    < test_boundary + self.embargo_ms
                ):
                    embargoed_groups.append(group)
                else:
                    split_groups["test"].append(group)

            if any(not split_groups[name] for name in split_groups):
                status = "INSUFFICIENT_AFTER_EMBARGO"

        split_rows = {
            name: [
                row
                for group in split_groups[name]
                for row in group["rows"]
            ]
            for name in split_groups
        }

        self._assert_no_candidate_leakage(split_groups)
        self._assert_chronological_order(split_groups)

        self._write_jsonl_atomic(
            self.train_path,
            split_rows["train"],
        )
        self._write_jsonl_atomic(
            self.validation_path,
            split_rows["validation"],
        )
        self._write_jsonl_atomic(
            self.test_path,
            split_rows["test"],
        )

        report = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "status": status,
            "configuration": {
                "train_ratio": self.train_ratio,
                "validation_ratio": self.validation_ratio,
                "test_ratio": self.test_ratio,
                "embargo_seconds": self.embargo_ms // 1000,
            },
            "input": {
                "dataset_path": str(self.dataset_path),
                "rows_read": len(rows),
                "valid_labeled_rows": sum(
                    len(group["rows"]) for group in groups
                ),
                "candidate_groups": len(groups),
                "unlabeled_rows_excluded": unlabeled_rows,
                "invalid_rows_excluded": invalid_rows,
            },
            "splits": {
                name: self._split_summary(
                    split_groups[name],
                    split_rows[name],
                    path,
                )
                for name, path in (
                    ("train", self.train_path),
                    ("validation", self.validation_path),
                    ("test", self.test_path),
                )
            },
            "purging": {
                "policy": "LABEL_WINDOW_MUST_END_BEFORE_NEXT_SPLIT",
                "candidate_groups_excluded": len(purged_groups),
                "rows_excluded": sum(
                    len(group["rows"])
                    for group in purged_groups
                ),
            },
            "embargo": {
                "candidate_groups_excluded": len(embargoed_groups),
                "rows_excluded": sum(
                    len(group["rows"])
                    for group in embargoed_groups
                ),
            },
            "leakage_checks": {
                "candidate_overlap": False,
                "label_window_overlap": False,
                "chronological_order": True,
            },
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
        }
        self._write_json_atomic(self.report_path, report)
        return report

    def _allocate_counts(self, group_count: int) -> tuple[int, int]:
        train_count = max(1, int(group_count * self.train_ratio))
        validation_count = max(
            1,
            int(group_count * self.validation_ratio),
        )

        if train_count + validation_count >= group_count:
            overflow = train_count + validation_count - group_count + 1
            if train_count > validation_count:
                train_count -= overflow
            else:
                validation_count -= overflow

        if train_count < 1 or validation_count < 1:
            raise TimeSplitError("TIME_SPLIT_ALLOCATION_INVALID")

        return train_count, validation_count

    def _read_dataset(self, issues: Counter) -> list[dict]:
        if not self.dataset_path.exists():
            issues["dataset_file_missing"] += 1
            return []

        rows = []
        try:
            with self.dataset_path.open("r") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        issues["dataset_malformed_json"] += 1
                        continue
                    if not isinstance(row, dict):
                        issues["dataset_row_not_object"] += 1
                        continue
                    rows.append(row)
        except OSError as exc:
            raise TimeSplitError(
                f"TIME_SPLIT_DATASET_READ_FAILED | {exc}"
            ) from exc
        return rows

    @staticmethod
    def _validate_row(row: dict) -> str | None:
        required = {
            "candidate_observation_id",
            "observed_at_ms",
            "recorded_at_ms",
            "symbol",
            "direction",
            "pattern",
            "outcome_type",
            "features",
            "label_profitable",
        }
        if not required.issubset(row):
            return "dataset_row_schema_invalid"
        if not str(row["candidate_observation_id"]).strip():
            return "dataset_candidate_id_invalid"
        if row["direction"] not in {"LONG", "SHORT"}:
            return "dataset_direction_invalid"
        if not isinstance(row["features"], dict):
            return "dataset_features_invalid"
        try:
            if int(row["observed_at_ms"]) < 0:
                return "dataset_observed_timestamp_invalid"
            if int(row["recorded_at_ms"]) < int(row["observed_at_ms"]):
                return "dataset_recorded_timestamp_invalid"
        except (TypeError, ValueError):
            return "dataset_timestamp_invalid"
        if row["label_profitable"] not in {True, False, None}:
            return "dataset_label_invalid"
        return None

    @staticmethod
    def _assert_no_candidate_leakage(split_groups: dict) -> None:
        ids = {
            name: {
                group["candidate_id"]
                for group in groups
            }
            for name, groups in split_groups.items()
        }
        if (
            ids["train"] & ids["validation"]
            or ids["train"] & ids["test"]
            or ids["validation"] & ids["test"]
        ):
            raise TimeSplitError("TIME_SPLIT_CANDIDATE_LEAKAGE")

    @staticmethod
    def _assert_chronological_order(split_groups: dict) -> None:
        def timestamps(name):
            return [
                group["observed_at_ms"]
                for group in split_groups[name]
            ]

        train = timestamps("train")
        validation = timestamps("validation")
        test = timestamps("test")

        if train and validation and max(train) >= min(validation):
            raise TimeSplitError("TIME_SPLIT_TRAIN_VALIDATION_ORDER")
        if validation and test and max(validation) >= min(test):
            raise TimeSplitError("TIME_SPLIT_VALIDATION_TEST_ORDER")
        if train and test and max(train) >= min(test):
            raise TimeSplitError("TIME_SPLIT_TRAIN_TEST_ORDER")

    @staticmethod
    def _split_summary(groups: list, rows: list, path: Path) -> dict:
        timestamps = [
            group["observed_at_ms"]
            for group in groups
        ]
        outcomes = Counter(row["outcome_type"] for row in rows)
        patterns = Counter(row["pattern"] for row in rows)
        labels = Counter(
            str(row["label_profitable"]).lower()
            for row in rows
        )
        return {
            "path": str(path),
            "candidate_groups": len(groups),
            "rows": len(rows),
            "first_observed_at_ms": min(timestamps) if timestamps else None,
            "last_observed_at_ms": max(timestamps) if timestamps else None,
            "outcome_types": dict(sorted(outcomes.items())),
            "patterns": dict(sorted(patterns.items())),
            "labels": dict(sorted(labels.items())),
        }

    @staticmethod
    def _write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                for row in rows:
                    handle.write(
                        json.dumps(row, sort_keys=True, default=str)
                        + "\n"
                    )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _write_json_atomic(path: Path, document: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(
                    document,
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
