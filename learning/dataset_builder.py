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

from strategy.experiment_contract import (
    EXPERIMENT_CONTRACT_VERSION,
    validate_experiment_context,
)
from strategy.features import (
    CANDIDATE_FEATURE_NAMES,
    CANDIDATE_FEATURE_SCHEMA_VERSION,
)


TRAINING_DATASET_SCHEMA_VERSION = 2


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
        experiment_contract_versions = Counter()
        strategy_versions = Counter()
        strategy_variants = Counter()
        model_versions = Counter()
        market_context_completeness = Counter()

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

            contract_error = self._validate_contract_link(
                observation,
                outcome,
            )
            if contract_error:
                issues[contract_error] += 1
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
            experiment_contract_versions[str(
                row["experiment_contract_version"]
            )] += 1
            strategy_versions[
                row.get("strategy_version") or "LEGACY_UNKNOWN"
            ] += 1
            strategy_variants[
                row.get("strategy_variant_id") or "LEGACY_UNKNOWN"
            ] += 1
            model_versions[
                row.get("model_version") or "LEGACY_UNKNOWN"
            ] += 1
            context = row.get("market_context") or {}
            market_context_completeness[
                context.get("completeness", "LEGACY_UNKNOWN")
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
                "experiment_contract_versions": dict(
                    sorted(experiment_contract_versions.items())
                ),
                "strategy_versions": dict(
                    sorted(strategy_versions.items())
                ),
                "strategy_variants": dict(
                    sorted(strategy_variants.items())
                ),
                "model_versions": dict(
                    sorted(model_versions.items())
                ),
                "market_context_completeness": dict(
                    sorted(market_context_completeness.items())
                ),
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
        contract_version = int(
            row.get("experiment_contract_version", 0) or 0
        )
        if contract_version not in {0, EXPERIMENT_CONTRACT_VERSION}:
            return "observation_experiment_contract_unsupported"
        if contract_version == EXPERIMENT_CONTRACT_VERSION:
            context = row.get("experiment_context")
            try:
                validate_experiment_context(context)
            except (TypeError, ValueError):
                return "observation_experiment_context_invalid"
            if not self._projection_matches_context(row, context):
                return "observation_experiment_projection_mismatch"
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
        schema_version = int(row.get("schema_version", 1) or 1)
        if schema_version not in {1, 2}:
            return "outcome_schema_invalid"
        contract_version = int(
            row.get("experiment_contract_version", 0) or 0
        )
        if contract_version not in {0, EXPERIMENT_CONTRACT_VERSION}:
            return "outcome_experiment_contract_unsupported"
        if contract_version == EXPERIMENT_CONTRACT_VERSION:
            context = row.get("experiment_context")
            try:
                validate_experiment_context(context)
            except (TypeError, ValueError):
                return "outcome_experiment_context_invalid"
            if not self._projection_matches_context(row, context):
                return "outcome_experiment_projection_mismatch"
        return None

    @staticmethod
    def _projection_matches_context(row: dict, context: dict) -> bool:
        expected = {
            "decision_batch_id": context["decision_batch_id"],
            "market_event_id": context["market_event_id"],
            "strategy_version": context["strategy_version"],
            "strategy_variant_id": context["strategy_variant_id"],
            "model_version": context["selection_model_version"],
            "feature_schema_version": context[
                "feature_schema_version"
            ],
        }
        return all(row.get(key) == value for key, value in expected.items())

    def _validate_contract_link(
        self,
        observation: dict,
        outcome: dict,
    ) -> str | None:
        observation_version = int(
            observation.get("experiment_contract_version", 0) or 0
        )
        outcome_version = int(
            outcome.get("experiment_contract_version", 0) or 0
        )
        if observation_version != outcome_version:
            return "experiment_contract_version_mismatch"
        if observation_version == 0:
            return None
        observation_context = observation["experiment_context"]
        outcome_context = outcome["experiment_context"]
        for key in (
            "decision_batch_id",
            "market_event_id",
            "strategy_version",
            "strategy_variant_id",
            "selection_model_version",
            "feature_schema_version",
            "environment",
            "execution_mode",
            "candle_interval",
            "candle_bucket",
        ):
            if observation_context.get(key) != outcome_context.get(key):
                return f"experiment_context_{key}_mismatch"
        return None

    def _join(self, observation: dict, outcome: dict) -> dict:
        payload = dict(outcome["payload"])
        return {
            "dataset_schema_version": TRAINING_DATASET_SCHEMA_VERSION,
            "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
            "experiment_contract_version": int(
                observation.get("experiment_contract_version", 0) or 0
            ),
            "decision_batch_id": observation.get("decision_batch_id"),
            "market_event_id": observation.get("market_event_id"),
            "strategy_version": observation.get("strategy_version"),
            "strategy_variant_id": observation.get(
                "strategy_variant_id"
            ),
            "model_version": observation.get("model_version"),
            "outcome_variant_id": outcome.get("outcome_variant_id"),
            "legacy_record": bool(observation.get("legacy_record", True)),
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
            "market_context": observation.get("market_context"),
            "cost_model": observation.get("cost_model"),
            "virtual_policy": observation.get("virtual_policy"),
            "paper_policy": observation.get("paper_policy"),
            "experiment_context": observation.get(
                "experiment_context"
            ),
            "selection_status": observation.get(
                "selection_status"
            ),
            "rejection_reason": observation.get(
                "rejection_reason"
            ),
            "execution_eligible": observation.get(
                "execution_eligible"
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
