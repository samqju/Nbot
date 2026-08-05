"""Phase 4.1 traceable dataset builder and integrity report."""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any


TRAINING_DATASET_SCHEMA_VERSION = 1
CANDIDATE_FEATURE_SCHEMA_VERSION = 3
CANDIDATE_FEATURE_NAMES = (
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


class DatasetBuildError(RuntimeError):
    pass


class TrainingDatasetBuilder:
    """Join candidate observations to linked outcomes without inventing rows."""

    def __init__(
        self,
        *,
        observations_path: str,
        outcomes_path: str,
        dataset_path: str,
        report_path: str,
    ):
        self.observations_path = Path(observations_path)
        self.outcomes_path = Path(outcomes_path)
        self.dataset_path = Path(dataset_path)
        self.report_path = Path(report_path)

    def build(self) -> dict:
        issues = Counter()
        observation_rows = self._read_jsonl(
            self.observations_path,
            source="observations",
            issues=issues,
        )
        outcome_rows = self._read_jsonl(
            self.outcomes_path,
            source="outcomes",
            issues=issues,
        )

        observations = {}
        duplicate_ids = set()

        for row in observation_rows:
            observation_id = self._text(
                row.get("candidate_observation_id")
            )
            if not observation_id:
                issues["observation_missing_id"] += 1
                continue
            if observation_id in observations:
                issues["duplicate_observation_id"] += 1
                duplicate_ids.add(observation_id)
                continue
            validation_error = self._validate_observation(row)
            if validation_error:
                issues[validation_error] += 1
                continue
            observations[observation_id] = row

        # Duplicate IDs are ambiguous and excluded completely.
        for observation_id in duplicate_ids:
            observations.pop(observation_id, None)

        dataset_rows = []
        seen_outcomes = set()
        patterns = Counter()
        outcome_types = Counter()
        directions = Counter()
        symbols = Counter()
        labels = Counter()

        for outcome in outcome_rows:
            observation_id = self._text(
                outcome.get("candidate_observation_id")
            )
            if not observation_id:
                issues["outcome_missing_candidate_id"] += 1
                continue

            observation = observations.get(observation_id)
            if observation is None:
                issues["orphan_outcome"] += 1
                continue

            validation_error = self._validate_outcome(outcome)
            if validation_error:
                issues[validation_error] += 1
                continue

            if self._text(outcome.get("symbol")).upper() != self._text(
                observation.get("symbol")
            ).upper():
                issues["symbol_mismatch"] += 1
                continue

            if self._text(outcome.get("direction")).upper() != self._text(
                observation.get("direction")
            ).upper():
                issues["direction_mismatch"] += 1
                continue

            outcome_key = self._outcome_key(outcome)
            if outcome_key in seen_outcomes:
                issues["duplicate_outcome"] += 1
                continue
            seen_outcomes.add(outcome_key)

            row = self._join(observation, outcome)
            dataset_rows.append(row)
            patterns[row["pattern"]] += 1
            outcome_types[row["outcome_type"]] += 1
            directions[row["direction"]] += 1
            symbols[row["symbol"]] += 1
            label = row["label_profitable"]
            labels[
                str(label).lower() if label is not None else "unknown"
            ] += 1

        dataset_rows.sort(
            key=lambda row: (
                row["observed_at_ms"],
                row["recorded_at_ms"],
                row["candidate_observation_id"],
                row["outcome_type"],
            )
        )
        self._write_jsonl_atomic(self.dataset_path, dataset_rows)

        status = "READY"
        if not dataset_rows:
            status = "EMPTY"
        elif sum(issues.values()):
            status = "READY_WITH_WARNINGS"

        report = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "status": status,
            "inputs": {
                "observations_path": str(self.observations_path),
                "outcomes_path": str(self.outcomes_path),
                "observation_lines_read": len(observation_rows),
                "outcome_lines_read": len(outcome_rows),
                "valid_unique_observations": len(observations),
            },
            "output": {
                "dataset_path": str(self.dataset_path),
                "rows_written": len(dataset_rows),
                "dataset_schema_version": (
                    TRAINING_DATASET_SCHEMA_VERSION
                ),
                "feature_schema_version": (
                    CANDIDATE_FEATURE_SCHEMA_VERSION
                ),
                "feature_names": list(CANDIDATE_FEATURE_NAMES),
            },
            "counts": {
                "patterns": dict(sorted(patterns.items())),
                "outcome_types": dict(sorted(outcome_types.items())),
                "directions": dict(sorted(directions.items())),
                "labels": dict(sorted(labels.items())),
                "unique_symbols": len(symbols),
            },
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
        }
        self._write_json_atomic(self.report_path, report)
        return report

    def _read_jsonl(
        self,
        path: Path,
        *,
        source: str,
        issues: Counter,
    ) -> list[dict]:
        if not path.exists():
            issues[f"{source}_file_missing"] += 1
            return []

        rows = []
        try:
            with path.open("r") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        issues[f"{source}_malformed_json"] += 1
                        continue
                    if not isinstance(row, dict):
                        issues[f"{source}_row_not_object"] += 1
                        continue
                    rows.append(row)
        except OSError as exc:
            raise DatasetBuildError(
                f"DATASET_INPUT_READ_FAILED | "
                f"source={source} | path={path} | error={exc}"
            ) from exc
        return rows

    def _validate_observation(self, row: dict) -> str | None:
        if row.get("observation_type") != "STRATEGY_CANDIDATE":
            return "observation_type_invalid"
        if row.get("schema_version") != CANDIDATE_FEATURE_SCHEMA_VERSION:
            return "observation_schema_invalid"
        if not row.get("eligible_for_training", False):
            return "observation_not_training_eligible"
        if self._text(row.get("direction")).upper() not in {
            "LONG",
            "SHORT",
        }:
            return "observation_direction_invalid"
        if not self._text(row.get("symbol")):
            return "observation_symbol_invalid"
        if not self._text(row.get("pattern")):
            return "observation_pattern_invalid"
        features = row.get("features")
        if not isinstance(features, dict):
            return "observation_features_missing"
        if tuple(features.keys()) != CANDIDATE_FEATURE_NAMES:
            return "observation_feature_schema_mismatch"
        if not all(
            self._finite(features[name])
            for name in CANDIDATE_FEATURE_NAMES
        ):
            return "observation_feature_value_invalid"
        if not self._integer(row.get("observed_at_ms")):
            return "observation_timestamp_invalid"
        return None

    def _validate_outcome(self, row: dict) -> str | None:
        if row.get("observation_type") != "CANDIDATE_OUTCOME":
            return "outcome_type_record_invalid"
        if not self._text(row.get("outcome_type")):
            return "outcome_type_missing"
        if self._text(row.get("direction")).upper() not in {
            "LONG",
            "SHORT",
        }:
            return "outcome_direction_invalid"
        if not self._text(row.get("symbol")):
            return "outcome_symbol_invalid"
        if not isinstance(row.get("payload"), dict):
            return "outcome_payload_invalid"
        if not self._integer(row.get("recorded_at_ms")):
            return "outcome_timestamp_invalid"
        return None

    def _join(self, observation: dict, outcome: dict) -> dict:
        payload = dict(outcome["payload"])
        return {
            "dataset_schema_version": TRAINING_DATASET_SCHEMA_VERSION,
            "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
            "candidate_observation_id": observation[
                "candidate_observation_id"
            ],
            "observed_at_ms": int(observation["observed_at_ms"]),
            "recorded_at_ms": int(outcome["recorded_at_ms"]),
            "symbol": self._text(observation["symbol"]).upper(),
            "direction": self._text(
                observation["direction"]
            ).upper(),
            "pattern": self._text(observation["pattern"]).upper(),
            "bucket": observation.get("bucket"),
            "rank": observation.get("rank"),
            "selected": bool(observation.get("selected", False)),
            "rule_score": self._optional_float(
                observation.get("rule_score")
            ),
            "final_score": self._optional_float(
                observation.get("final_score")
            ),
            "reference_price": self._optional_float(
                observation.get("reference_price")
            ),
            "features": {
                name: float(observation["features"][name])
                for name in CANDIDATE_FEATURE_NAMES
            },
            "score_breakdown": observation.get("score_breakdown"),
            "risk_plan": observation.get("risk_plan"),
            "structure_fingerprint": observation.get(
                "structure_fingerprint"
            ),
            "outcome_type": self._text(
                outcome["outcome_type"]
            ).upper(),
            "outcome": payload,
            "label_profitable": self._derive_label(payload),
            "target_r": self._derive_target_r(payload),
        }

    @staticmethod
    def _derive_label(payload: dict) -> bool | None:
        if isinstance(payload.get("profitable"), bool):
            return payload["profitable"]
        label = payload.get("label")
        if label in {0, 1, False, True}:
            return bool(label)
        for key in (
            "exit_r",
            "r_multiple",
            "target_r",
            "realized_pnl_usd",
        ):
            value = payload.get(key)
            if TrainingDatasetBuilder._finite(value):
                return float(value) > 0
        return None

    @staticmethod
    def _derive_target_r(payload: dict) -> float | None:
        for key in ("exit_r", "r_multiple", "target_r"):
            value = payload.get(key)
            if TrainingDatasetBuilder._finite(value):
                return float(value)
        return None

    @staticmethod
    def _outcome_key(row: dict) -> tuple:
        return (
            TrainingDatasetBuilder._text(
                row.get("candidate_observation_id")
            ),
            TrainingDatasetBuilder._text(
                row.get("outcome_type")
            ).upper(),
            int(row.get("recorded_at_ms", 0)),
            json.dumps(
                row.get("payload", {}),
                sort_keys=True,
                default=str,
            ),
        )

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _integer(value: Any) -> bool:
        try:
            return int(value) >= 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if TrainingDatasetBuilder._finite(value):
            return float(value)
        return None

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
