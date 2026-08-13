"""Phase 4.1 traceable dataset builder and integrity report."""

from __future__ import annotations

import json
import math
import os
import sqlite3
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from strategy.experiment_contract import (
    EXPERIMENT_CONTRACT_VERSION,
    validate_experiment_context,
)
from utils.jsonl_history import iter_jsonl_lines, logical_jsonl_exists

from strategy.features import (
    CANDIDATE_FEATURE_NAMES,
    CANDIDATE_FEATURE_SCHEMA_VERSION,
)


TRAINING_DATASET_SCHEMA_VERSION = 3


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
        """Build a deterministic joined dataset with bounded Python memory.

        Raw observation and outcome histories can grow far beyond RAM.  Keep
        only one parsed record in Python at a time and use a temporary SQLite
        workspace for the observation index, duplicate detection, and the
        externally sorted joined rows.  The final JSONL/report contracts are
        unchanged.
        """
        issues = Counter()
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)

        observation_lines_read = 0
        outcome_lines_read = 0
        rows_written = 0
        patterns = Counter()
        outcome_types = Counter()
        directions = Counter()
        symbols = set()
        labels = Counter()
        experiment_contract_versions = Counter()
        strategy_versions = Counter()
        strategy_variants = Counter()
        outcome_variants = Counter()
        strategy_lab_catalogs = Counter()
        model_versions = Counter()
        market_context_completeness = Counter()

        workspace = Path(
            tempfile.mkdtemp(
                prefix=".dataset-build.",
                dir=str(self.dataset_path.parent),
            )
        )
        database_path = workspace / "join.sqlite3"
        connection = sqlite3.connect(str(database_path))
        try:
            self._configure_sqlite(connection)
            connection.executescript(
                """
                CREATE TABLE observations (
                    candidate_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    duplicate INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE seen_outcomes (
                    outcome_key TEXT PRIMARY KEY
                );
                CREATE TABLE joined_rows (
                    observed_at_ms INTEGER NOT NULL,
                    recorded_at_ms INTEGER NOT NULL,
                    candidate_id TEXT NOT NULL,
                    outcome_type TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

            for row in self._iter_jsonl(
                self.observations_path,
                source="observations",
                issues=issues,
            ):
                observation_lines_read += 1
                observation_id = self._text(
                    row.get("candidate_observation_id")
                )
                if not observation_id:
                    issues["observation_missing_id"] += 1
                    continue

                existing = connection.execute(
                    "SELECT 1 FROM observations WHERE candidate_id = ?",
                    (observation_id,),
                ).fetchone()
                if existing is not None:
                    # Match the historical fail-closed contract: once a
                    # previously accepted observation ID is repeated, every
                    # outcome linked to that ID becomes ambiguous.
                    issues["duplicate_observation_id"] += 1
                    connection.execute(
                        "UPDATE observations SET duplicate = 1 "
                        "WHERE candidate_id = ?",
                        (observation_id,),
                    )
                    continue

                validation_error = self._validate_observation(row)
                if validation_error:
                    issues[validation_error] += 1
                    continue
                connection.execute(
                    "INSERT INTO observations(candidate_id, payload, duplicate) "
                    "VALUES (?, ?, 0)",
                    (
                        observation_id,
                        json.dumps(row, sort_keys=True, default=str),
                    ),
                )

            connection.commit()

            for outcome in self._iter_jsonl(
                self.outcomes_path,
                source="outcomes",
                issues=issues,
            ):
                outcome_lines_read += 1
                observation_id = self._text(
                    outcome.get("candidate_observation_id")
                )
                if not observation_id:
                    issues["outcome_missing_candidate_id"] += 1
                    continue

                stored = connection.execute(
                    "SELECT payload FROM observations "
                    "WHERE candidate_id = ? AND duplicate = 0",
                    (observation_id,),
                ).fetchone()
                if stored is None:
                    issues["orphan_outcome"] += 1
                    continue
                observation = json.loads(stored[0])

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

                outcome_key = self._outcome_key_text(outcome)
                try:
                    connection.execute(
                        "INSERT INTO seen_outcomes(outcome_key) VALUES (?)",
                        (outcome_key,),
                    )
                except sqlite3.IntegrityError:
                    issues["duplicate_outcome"] += 1
                    continue

                row = self._join(observation, outcome)
                rows_written += 1
                patterns[row["pattern"]] += 1
                outcome_types[row["outcome_type"]] += 1
                directions[row["direction"]] += 1
                symbols.add(row["symbol"])
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
                outcome_variants[
                    row.get("outcome_variant_id") or "LEGACY_UNKNOWN"
                ] += 1
                strategy_lab_catalogs[
                    row.get("strategy_lab_catalog_version")
                    or "NOT_LAB_RECORD"
                ] += 1
                model_versions[
                    row.get("model_version") or "LEGACY_UNKNOWN"
                ] += 1
                context = row.get("market_context") or {}
                market_context_completeness[
                    context.get("completeness", "LEGACY_UNKNOWN")
                ] += 1
                connection.execute(
                    "INSERT INTO joined_rows("
                    "observed_at_ms, recorded_at_ms, candidate_id, "
                    "outcome_type, payload"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        int(row["observed_at_ms"]),
                        int(row["recorded_at_ms"]),
                        row["candidate_observation_id"],
                        row["outcome_type"],
                        json.dumps(row, sort_keys=True, default=str),
                    ),
                )

            connection.commit()
            self._write_jsonl_atomic(
                self.dataset_path,
                (
                    json.loads(payload)
                    for (payload,) in connection.execute(
                        "SELECT payload FROM joined_rows "
                        "ORDER BY observed_at_ms, recorded_at_ms, "
                        "candidate_id, outcome_type"
                    )
                ),
            )
            valid_unique_observations = int(
                connection.execute(
                    "SELECT COUNT(*) FROM observations WHERE duplicate = 0"
                ).fetchone()[0]
            )
        finally:
            connection.close()
            self._remove_workspace(workspace)

        status = "READY"
        if rows_written == 0:
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
                "observation_lines_read": observation_lines_read,
                "outcome_lines_read": outcome_lines_read,
                "valid_unique_observations": valid_unique_observations,
            },
            "output": {
                "dataset_path": str(self.dataset_path),
                "rows_written": rows_written,
                "dataset_schema_version": TRAINING_DATASET_SCHEMA_VERSION,
                "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
                "feature_names": list(CANDIDATE_FEATURE_NAMES),
                "build_mode": "DISK_BACKED_STREAMING_SQLITE",
            },
            "counts": {
                "patterns": dict(sorted(patterns.items())),
                "outcome_types": dict(sorted(outcome_types.items())),
                "directions": dict(sorted(directions.items())),
                "labels": dict(sorted(labels.items())),
                "experiment_contract_versions": dict(
                    sorted(experiment_contract_versions.items())
                ),
                "strategy_versions": dict(sorted(strategy_versions.items())),
                "strategy_variants": dict(sorted(strategy_variants.items())),
                "outcome_variants": dict(sorted(outcome_variants.items())),
                "strategy_lab_catalogs": dict(
                    sorted(strategy_lab_catalogs.items())
                ),
                "model_versions": dict(sorted(model_versions.items())),
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

    def _iter_jsonl(
        self,
        path: Path,
        *,
        source: str,
        issues: Counter,
    ) -> Iterator[dict]:
        if not logical_jsonl_exists(path):
            issues[f"{source}_file_missing"] += 1
            return
        try:
            for raw_line in iter_jsonl_lines(path):
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
                yield row
        except OSError as exc:
            raise DatasetBuildError(
                f"DATASET_INPUT_READ_FAILED | "
                f"source={source} | path={path} | error={exc}"
            ) from exc

    @staticmethod
    def _configure_sqlite(connection: sqlite3.Connection) -> None:
        # This database is disposable build workspace.  Keep SQLite caches
        # deliberately small and force sort/index spill to disk rather than RAM.
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("PRAGMA cache_size=-16384")

    @staticmethod
    def _remove_workspace(path: Path) -> None:
        if not path.exists():
            return
        for child in path.iterdir():
            try:
                child.unlink()
            except FileNotFoundError:
                pass
        try:
            path.rmdir()
        except FileNotFoundError:
            pass

    @staticmethod
    def _outcome_key_text(row: dict) -> str:
        key = TrainingDatasetBuilder._outcome_key(row)
        return json.dumps(key, sort_keys=True, default=str, separators=(",", ":"))

    # Phase 7.5C reuses the exact historical validation/join contract at
    # evidence-ingest time so qualification cannot drift from the dataset
    # builder semantics.
    def validate_observation_record(self, row: dict) -> str | None:
        return self._validate_observation(row)

    def validate_outcome_record(self, row: dict) -> str | None:
        return self._validate_outcome(row)

    def validate_contract_link(
        self, observation: dict, outcome: dict
    ) -> str | None:
        return self._validate_contract_link(observation, outcome)

    def join_records(self, observation: dict, outcome: dict) -> dict:
        return self._join(observation, outcome)

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
        outcome_context = outcome.get("experiment_context") or {}
        observation_context = observation.get("experiment_context") or {}
        effective_context = outcome_context or observation_context
        strategy_lab = effective_context.get("strategy_lab") or {}
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
            "market_context": (
                effective_context.get("market_context")
                or observation.get("market_context")
            ),
            "cost_model": (
                effective_context.get("cost_model")
                or observation.get("cost_model")
            ),
            "virtual_policy": (
                effective_context.get("virtual_policy")
                or observation.get("virtual_policy")
            ),
            "paper_policy": (
                effective_context.get("paper_policy")
                or observation.get("paper_policy")
            ),
            "strategy_lab": strategy_lab or None,
            "strategy_lab_catalog_version": (
                strategy_lab.get("catalog_version")
                or payload.get("strategy_lab_catalog_version")
            ),
            "experiment_context": effective_context or None,
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
        if isinstance(payload.get("net_profitable"), bool):
            return payload["net_profitable"]
        if isinstance(payload.get("profitable"), bool):
            return payload["profitable"]
        label = payload.get("label")
        if label in {0, 1, False, True}:
            return bool(label)
        for key in (
            "net_exit_r",
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
        for key in (
            "net_exit_r",
            "exit_r",
            "r_multiple",
            "target_r",
        ):
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
    def _write_jsonl_atomic(path: Path, rows) -> None:
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
