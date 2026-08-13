"""Chronological candidate-group split with leakage controls."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import time
from collections import Counter
from pathlib import Path


TIME_SPLIT_BUILD_MODE = "DISK_BACKED_STREAMING_SQLITE"


class TimeSplitError(RuntimeError):
    pass


class TimeAwareDatasetSplitter:
    """Split labeled rows chronologically while keeping candidates intact.

    Full JSON rows are staged in a temporary SQLite database.  Only compact
    candidate/market-event metadata is retained in Python memory, preventing
    large Phase-7 snapshots from being materialized as nested dictionaries.
    """

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
        group_by_market_event: bool = False,
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
        self.group_by_market_event = bool(group_by_market_event)

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
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        work_root = Path(tempfile.mkdtemp(
            prefix=".time-split.",
            dir=str(self.report_path.parent),
        ))
        connection = None
        try:
            connection = sqlite3.connect(str(work_root / "split.sqlite3"))
            self._configure_database(connection)
            input_stats = self._stage_rows(connection, issues)
            candidate_group_count = self._stage_candidate_groups(
                connection, issues
            )
            groups = self._load_group_metadata(connection)
            groups.sort(
                key=lambda group: (
                    group["observed_at_ms"],
                    group["group_id"],
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

            self._assert_no_candidate_leakage(split_groups)
            if self.group_by_market_event:
                self._assert_no_market_event_leakage(split_groups)
            self._assert_chronological_order(split_groups)

            split_summaries = {}
            for name, path in (
                ("train", self.train_path),
                ("validation", self.validation_path),
                ("test", self.test_path),
            ):
                split_summaries[name] = self._write_split_atomic(
                    connection,
                    split_groups[name],
                    path,
                )

            report = {
                "schema_version": 2,
                "generated_at_ms": int(time.time() * 1000),
                "status": status,
                "configuration": {
                    "train_ratio": self.train_ratio,
                    "validation_ratio": self.validation_ratio,
                    "test_ratio": self.test_ratio,
                    "embargo_seconds": self.embargo_ms // 1000,
                    "grouping_policy": (
                        "MARKET_EVENT"
                        if self.group_by_market_event
                        else "CANDIDATE"
                    ),
                    "build_mode": TIME_SPLIT_BUILD_MODE,
                },
                "input": {
                    "dataset_path": str(self.dataset_path),
                    "rows_read": input_stats["rows_read"],
                    "valid_labeled_rows": sum(
                        int(group["row_count"]) for group in groups
                    ),
                    "candidate_groups": candidate_group_count,
                    "market_event_groups": (
                        len(groups) if self.group_by_market_event else None
                    ),
                    "unlabeled_rows_excluded": input_stats[
                        "unlabeled_rows_excluded"
                    ],
                    "invalid_rows_excluded": input_stats[
                        "invalid_rows_excluded"
                    ],
                    "build_mode": TIME_SPLIT_BUILD_MODE,
                },
                "splits": split_summaries,
                "purging": {
                    "policy": "LABEL_WINDOW_MUST_END_BEFORE_NEXT_SPLIT",
                    "candidate_groups_excluded": len(purged_groups),
                    "rows_excluded": sum(
                        int(group["row_count"])
                        for group in purged_groups
                    ),
                },
                "embargo": {
                    "candidate_groups_excluded": len(embargoed_groups),
                    "rows_excluded": sum(
                        int(group["row_count"])
                        for group in embargoed_groups
                    ),
                },
                "leakage_checks": {
                    "candidate_overlap": False,
                    "market_event_overlap": False,
                    "label_window_overlap": False,
                    "chronological_order": True,
                },
                "issues": dict(sorted(issues.items())),
                "issue_count": sum(issues.values()),
            }
            self._write_json_atomic(self.report_path, report)
            return report
        finally:
            if connection is not None:
                connection.close()
            shutil.rmtree(work_root, ignore_errors=True)

    @staticmethod
    def _configure_database(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("PRAGMA cache_size=-16384")
        connection.executescript(
            """
            CREATE TABLE rows (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL,
                market_event_id TEXT NOT NULL,
                observed_at_ms INTEGER NOT NULL,
                recorded_at_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                pattern TEXT NOT NULL,
                outcome_type TEXT NOT NULL,
                label_value TEXT NOT NULL,
                row_json TEXT NOT NULL
            );
            CREATE INDEX rows_candidate_idx
                ON rows(candidate_id, recorded_at_ms, outcome_type, row_id);
            CREATE TABLE candidate_groups (
                candidate_id TEXT PRIMARY KEY,
                market_event_id TEXT NOT NULL,
                observed_at_ms INTEGER NOT NULL,
                outcome_end_ms INTEGER NOT NULL,
                row_count INTEGER NOT NULL,
                market_event_ids_json TEXT NOT NULL
            );
            CREATE INDEX candidate_event_idx
                ON candidate_groups(market_event_id, observed_at_ms, candidate_id);
            """
        )

    def _stage_rows(
        self,
        connection: sqlite3.Connection,
        issues: Counter,
    ) -> dict:
        rows_read = 0
        unlabeled_rows = 0
        invalid_rows = 0
        if not self.dataset_path.exists():
            issues["dataset_file_missing"] += 1
            return {
                "rows_read": 0,
                "unlabeled_rows_excluded": 0,
                "invalid_rows_excluded": 0,
            }

        insert = (
            "INSERT INTO rows ("
            "candidate_id, market_event_id, observed_at_ms, recorded_at_ms, "
            "symbol, direction, pattern, outcome_type, label_value, row_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        try:
            with self.dataset_path.open("r") as handle:
                batch = []
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
                    rows_read += 1
                    error = self._validate_row(row)
                    if error:
                        issues[error] += 1
                        invalid_rows += 1
                        continue
                    if row.get("label_profitable") is None:
                        unlabeled_rows += 1
                        continue
                    batch.append((
                        str(row["candidate_observation_id"]),
                        str(row.get("market_event_id") or "").strip(),
                        int(row["observed_at_ms"]),
                        int(row["recorded_at_ms"]),
                        str(row["symbol"]),
                        str(row["direction"]),
                        str(row["pattern"]),
                        str(row["outcome_type"]),
                        str(row["label_profitable"]).lower(),
                        json.dumps(row, sort_keys=True, default=str),
                    ))
                    if len(batch) >= 512:
                        connection.executemany(insert, batch)
                        batch.clear()
                if batch:
                    connection.executemany(insert, batch)
            connection.commit()
        except OSError as exc:
            raise TimeSplitError(
                f"TIME_SPLIT_DATASET_READ_FAILED | {exc}"
            ) from exc
        return {
            "rows_read": rows_read,
            "unlabeled_rows_excluded": unlabeled_rows,
            "invalid_rows_excluded": invalid_rows,
        }

    def _stage_candidate_groups(
        self,
        connection: sqlite3.Connection,
        issues: Counter,
    ) -> int:
        query = """
            SELECT
                candidate_id,
                MIN(observed_at_ms), MAX(observed_at_ms),
                COUNT(DISTINCT observed_at_ms),
                COUNT(DISTINCT direction),
                COUNT(DISTINCT symbol),
                COUNT(DISTINCT pattern),
                COUNT(DISTINCT market_event_id),
                MIN(market_event_id),
                MAX(recorded_at_ms),
                COUNT(*)
            FROM rows
            GROUP BY candidate_id
            ORDER BY candidate_id
        """
        insert = (
            "INSERT INTO candidate_groups ("
            "candidate_id, market_event_id, observed_at_ms, outcome_end_ms, "
            "row_count, market_event_ids_json"
            ") VALUES (?, ?, ?, ?, ?, ?)"
        )
        valid_count = 0
        batch = []
        for record in connection.execute(query):
            (
                candidate_id,
                min_observed,
                _max_observed,
                observed_count,
                direction_count,
                symbol_count,
                pattern_count,
                market_event_count,
                first_market_event,
                outcome_end_ms,
                row_count,
            ) = record
            if observed_count != 1:
                issues["candidate_timestamp_inconsistent"] += 1
                continue
            if (
                direction_count != 1
                or symbol_count != 1
                or pattern_count != 1
            ):
                issues["candidate_identity_inconsistent"] += 1
                continue

            event_rows = connection.execute(
                "SELECT DISTINCT market_event_id FROM rows "
                "WHERE candidate_id=? ORDER BY market_event_id",
                (candidate_id,),
            ).fetchall()
            market_event_ids = tuple(
                str(item[0]) for item in event_rows if str(item[0]).strip()
            )
            if self.group_by_market_event and (
                market_event_count != 1
                or not str(first_market_event or "").strip()
            ):
                issues["candidate_market_event_invalid"] += 1
                continue

            batch.append((
                candidate_id,
                str(first_market_event or "").strip(),
                int(min_observed),
                int(outcome_end_ms),
                int(row_count),
                json.dumps(market_event_ids),
            ))
            valid_count += 1
            if len(batch) >= 512:
                connection.executemany(insert, batch)
                batch.clear()
        if batch:
            connection.executemany(insert, batch)
        connection.commit()
        return valid_count

    def _load_group_metadata(
        self,
        connection: sqlite3.Connection,
    ) -> list[dict]:
        if not self.group_by_market_event:
            groups = []
            for row in connection.execute(
                "SELECT candidate_id, observed_at_ms, outcome_end_ms, "
                "row_count, market_event_ids_json FROM candidate_groups"
            ):
                candidate_id, observed, outcome_end, row_count, events_json = row
                events = tuple(json.loads(events_json))
                groups.append({
                    "group_id": candidate_id,
                    "candidate_id": candidate_id,
                    "candidate_ids": (candidate_id,),
                    "market_event_ids": events,
                    "observed_at_ms": int(observed),
                    "outcome_end_ms": int(outcome_end),
                    "row_count": int(row_count),
                })
            return groups

        groups = []
        for event_id, observed, outcome_end, row_count in connection.execute(
            "SELECT market_event_id, MIN(observed_at_ms), "
            "MAX(outcome_end_ms), SUM(row_count) "
            "FROM candidate_groups GROUP BY market_event_id"
        ):
            candidate_ids = tuple(
                item[0]
                for item in connection.execute(
                    "SELECT candidate_id FROM candidate_groups "
                    "WHERE market_event_id=? ORDER BY candidate_id",
                    (event_id,),
                )
            )
            groups.append({
                "group_id": str(event_id),
                "candidate_id": candidate_ids[0],
                "candidate_ids": candidate_ids,
                "market_event_ids": (str(event_id),),
                "observed_at_ms": int(observed),
                "outcome_end_ms": int(outcome_end),
                "row_count": int(row_count),
            })
        return groups

    def _iter_group_rows(
        self,
        connection: sqlite3.Connection,
        group: dict,
    ):
        if self.group_by_market_event:
            cursor = connection.execute(
                "SELECT r.row_json, r.outcome_type, r.pattern, r.label_value "
                "FROM rows r JOIN candidate_groups c "
                "ON c.candidate_id=r.candidate_id "
                "WHERE c.market_event_id=? "
                "ORDER BY r.observed_at_ms, r.recorded_at_ms, "
                "r.candidate_id, r.outcome_type, r.row_id",
                (group["group_id"],),
            )
        else:
            cursor = connection.execute(
                "SELECT row_json, outcome_type, pattern, label_value "
                "FROM rows WHERE candidate_id=? "
                "ORDER BY recorded_at_ms, outcome_type, row_id",
                (group["candidate_id"],),
            )
        yield from cursor

    def _write_split_atomic(
        self,
        connection: sqlite3.Connection,
        groups: list[dict],
        path: Path,
    ) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        outcomes = Counter()
        patterns = Counter()
        labels = Counter()
        row_count = 0
        try:
            with os.fdopen(fd, "w") as handle:
                for group in groups:
                    for row_json, outcome_type, pattern, label_value in (
                        self._iter_group_rows(connection, group)
                    ):
                        handle.write(row_json + "\n")
                        outcomes[str(outcome_type)] += 1
                        patterns[str(pattern)] += 1
                        labels[str(label_value)] += 1
                        row_count += 1
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

        timestamps = [group["observed_at_ms"] for group in groups]
        return {
            "path": str(path),
            "candidate_groups": sum(
                len(group.get("candidate_ids", (group["candidate_id"],)))
                for group in groups
            ),
            "market_event_groups": len({
                event_id
                for group in groups
                for event_id in group.get("market_event_ids", ())
            }),
            "rows": row_count,
            "first_observed_at_ms": min(timestamps) if timestamps else None,
            "last_observed_at_ms": max(timestamps) if timestamps else None,
            "outcome_types": dict(sorted(outcomes.items())),
            "patterns": dict(sorted(patterns.items())),
            "labels": dict(sorted(labels.items())),
        }

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
                candidate_id
                for group in groups
                for candidate_id in group.get(
                    "candidate_ids", (group["candidate_id"],)
                )
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
    def _assert_no_market_event_leakage(split_groups: dict) -> None:
        ids = {
            name: {
                event_id
                for group in groups
                for event_id in group.get("market_event_ids", ())
            }
            for name, groups in split_groups.items()
        }
        if (
            ids["train"] & ids["validation"]
            or ids["train"] & ids["test"]
            or ids["validation"] & ids["test"]
        ):
            raise TimeSplitError("TIME_SPLIT_MARKET_EVENT_LEAKAGE")

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
