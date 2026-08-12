"""Phase 5.8 automatic, isolated challenger-training orchestration."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pickle
import shutil
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learning.baseline_trainer import BaselineModelTrainer
from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_FEATURE_SCHEMA_VERSION,
    is_complete_market_context,
    market_context_from_row,
)
from learning.cost_evidence import has_complete_cost_evidence
from learning.challenger_evaluator import ChallengerArtifactEvaluator
from learning.dataset_builder import TrainingDatasetBuilder
from learning.ensemble_experiment import OfflineEnsembleExperiment
from learning.model_registry import ModelRegistry
from learning.time_split import TimeAwareDatasetSplitter
from strategy.experiment_contract import EXPERIMENT_CONTRACT_VERSION
from strategy.features import CANDIDATE_FEATURE_SCHEMA_VERSION
from utils.jsonl_history import (
    iter_jsonl_lines,
    logical_jsonl_exists,
    rotate_jsonl_to_history,
)


AUTO_TRAINING_SCHEMA_VERSION = 3


class AutoTrainingError(RuntimeError):
    pass


class AutoTrainingAlreadyRunning(AutoTrainingError):
    pass


class AutoTrainingProcessLock:
    """Separate process lock; unrelated to the trading-engine instance lock."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise AutoTrainingAlreadyRunning(
                f"AUTO_TRAINING_ALREADY_RUNNING | path={self.path}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "acquired_at_ms": int(time.time() * 1000),
                },
                sort_keys=True,
            )
        )
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()
        return False


class TrainingInventory:
    """Count material completed outcomes and independent market events."""

    def __init__(
        self,
        *,
        observations_path: str,
        outcomes_path: str,
        outcome_type: str,
        require_complete_market_context: bool = False,
        require_complete_cost_evidence: bool = False,
    ):
        self.observations_path = Path(observations_path)
        self.outcomes_path = Path(outcomes_path)
        self.outcome_type = str(outcome_type).strip().upper()
        self.require_complete_market_context = bool(
            require_complete_market_context
        )
        self.require_complete_cost_evidence = bool(
            require_complete_cost_evidence
        )

    def scan(self, *, after_ms: int = 0) -> dict:
        observations = {}
        issues = Counter()
        for row in self._read_jsonl(self.observations_path, issues, "observation"):
            candidate_id = str(
                row.get("candidate_observation_id") or ""
            ).strip()
            if not candidate_id:
                issues["observation_missing_id"] += 1
                continue
            if candidate_id in observations:
                issues["duplicate_observation_id"] += 1
                continue
            observations[candidate_id] = row

        material = []
        seen = set()
        for outcome in self._read_jsonl(self.outcomes_path, issues, "outcome"):
            if str(outcome.get("outcome_type") or "").upper() != self.outcome_type:
                continue
            candidate_id = str(
                outcome.get("candidate_observation_id") or ""
            ).strip()
            observation = observations.get(candidate_id)
            if observation is None:
                issues["orphan_outcome"] += 1
                continue
            recorded_at_ms = self._int(outcome.get("recorded_at_ms"))
            if recorded_at_ms <= int(after_ms):
                continue
            contract_version = self._int(
                observation.get("experiment_contract_version")
            )
            if contract_version != EXPERIMENT_CONTRACT_VERSION:
                issues["non_current_contract_excluded"] += 1
                continue
            if (
                self.require_complete_market_context
                and not is_complete_market_context(
                    market_context_from_row(observation)
                )
            ):
                issues["market_context_incomplete_excluded"] += 1
                continue
            if (
                self.require_complete_cost_evidence
                and not has_complete_cost_evidence(outcome)
            ):
                issues["cost_evidence_incomplete_excluded"] += 1
                continue
            market_event_id = str(
                observation.get("market_event_id") or ""
            ).strip()
            if not market_event_id:
                issues["market_event_id_missing"] += 1
                continue
            outcome_variant_id = str(
                outcome.get("outcome_variant_id") or ""
            ).strip()
            key = (
                candidate_id,
                self.outcome_type,
                outcome_variant_id,
            )
            if key in seen:
                issues["duplicate_material_outcome"] += 1
                continue
            seen.add(key)
            material.append(
                {
                    "candidate_observation_id": candidate_id,
                    "market_event_id": market_event_id,
                    "recorded_at_ms": recorded_at_ms,
                    "outcome_variant_id": outcome_variant_id,
                }
            )

        return {
            "outcome_type": self.outcome_type,
            "after_ms": int(after_ms),
            "new_completed_outcomes": len(material),
            "new_independent_market_events": len(
                {row["market_event_id"] for row in material}
            ),
            "latest_recorded_at_ms": max(
                (row["recorded_at_ms"] for row in material),
                default=int(after_ms),
            ),
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
        }

    @staticmethod
    def _read_jsonl(path: Path, issues: Counter, prefix: str) -> list[dict]:
        if not logical_jsonl_exists(path):
            issues[f"{prefix}_file_missing"] += 1
            return []
        rows = []
        for line in iter_jsonl_lines(path):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                issues[f"{prefix}_malformed_json"] += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                issues[f"{prefix}_row_not_object"] += 1
        return rows

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


class AutomaticTrainingOrchestrator:
    """Create reproducible challenger models without touching trade authority."""

    def __init__(
        self,
        *,
        enabled: bool,
        environment: str,
        observations_path: str,
        outcomes_path: str,
        snapshot_root: str,
        model_root: str,
        registry_path: str,
        status_path: str,
        lock_path: str,
        outcome_type: str,
        default_parent_model_id: str,
        min_new_outcomes: int,
        min_new_market_events: int,
        train_ratio: float,
        validation_ratio: float,
        test_ratio: float,
        embargo_seconds: int,
        baseline_min_train_rows: int,
        baseline_min_eval_rows: int,
        ensemble_min_train_rows: int,
        ensemble_min_eval_rows: int,
        random_state: int,
        calibration_bins: int,
        drift_bins: int,
        min_roc_auc: float,
        max_brier_score: float,
        max_calibration_gap: float,
        max_feature_psi: float,
        virtual_trades_path: str | None = None,
        history_rotation_enabled: bool = True,
        history_rotate_min_bytes: int = 64 * 1024 * 1024,
        prune_rejected_storage: bool = True,
        min_train_market_events: int = 1,
        min_validation_market_events: int = 1,
        min_test_market_events: int = 1,
    ):
        self.enabled = bool(enabled)
        self.environment = str(environment).strip().upper()
        self.observations_path = Path(observations_path)
        self.outcomes_path = Path(outcomes_path)
        self.snapshot_root = Path(snapshot_root)
        self.model_root = Path(model_root)
        self.status_path = Path(status_path)
        self.lock = AutoTrainingProcessLock(lock_path)
        self.outcome_type = str(outcome_type).strip().upper()
        self.min_new_outcomes = int(min_new_outcomes)
        self.min_new_market_events = int(min_new_market_events)
        self.train_ratio = float(train_ratio)
        self.validation_ratio = float(validation_ratio)
        self.test_ratio = float(test_ratio)
        self.embargo_seconds = int(embargo_seconds)
        self.baseline_min_train_rows = int(baseline_min_train_rows)
        self.baseline_min_eval_rows = int(baseline_min_eval_rows)
        self.ensemble_min_train_rows = int(ensemble_min_train_rows)
        self.ensemble_min_eval_rows = int(ensemble_min_eval_rows)
        self.random_state = int(random_state)
        self.calibration_bins = int(calibration_bins)
        self.drift_bins = int(drift_bins)
        self.min_roc_auc = float(min_roc_auc)
        self.max_brier_score = float(max_brier_score)
        self.max_calibration_gap = float(max_calibration_gap)
        self.max_feature_psi = float(max_feature_psi)
        self.virtual_trades_path = (
            Path(virtual_trades_path) if virtual_trades_path else None
        )
        self.history_rotation_enabled = bool(history_rotation_enabled)
        self.history_rotate_min_bytes = max(
            0, int(history_rotate_min_bytes)
        )
        self.prune_rejected_storage = bool(prune_rejected_storage)
        self.min_train_market_events = max(1, int(min_train_market_events))
        self.min_validation_market_events = max(
            1, int(min_validation_market_events)
        )
        self.min_test_market_events = max(1, int(min_test_market_events))
        self.registry = ModelRegistry(
            path=registry_path,
            environment=self.environment,
            default_champion_model_id=default_parent_model_id,
        )

    def run_once(self) -> dict:
        if not self.enabled:
            return self._status(
                "DISABLED",
                reason="AUTO_TRAINING_ENABLED_FALSE",
            )
        try:
            with self.lock:
                return self._run_locked()
        except AutoTrainingAlreadyRunning as exc:
            return self._status(
                "SKIPPED_ALREADY_RUNNING",
                reason=str(exc),
            )

    def _run_locked(self) -> dict:
        self.registry.initialize()
        cutoff_ms = self.registry.latest_completed_cutoff_ms()
        storage_maintenance = self._storage_maintenance(
            cutoff_ms=cutoff_ms
        )
        inventory = TrainingInventory(
            observations_path=str(self.observations_path),
            outcomes_path=str(self.outcomes_path),
            outcome_type=self.outcome_type,
            require_complete_market_context=True,
            require_complete_cost_evidence=True,
        ).scan(after_ms=cutoff_ms)
        if (
            inventory["new_completed_outcomes"] < self.min_new_outcomes
            or inventory["new_independent_market_events"]
            < self.min_new_market_events
        ):
            return self._status(
                "WAITING_FOR_DATA",
                inventory=inventory,
                thresholds={
                    "min_new_outcomes": self.min_new_outcomes,
                    "min_new_market_events": self.min_new_market_events,
                },
                current_champion_model_id=(
                    self.registry.current_champion_model_id()
                ),
                storage_maintenance=storage_maintenance,
            )

        started_at_ms = int(time.time() * 1000)
        snapshot = self._create_snapshot()
        cohort = self._cohort_readiness(snapshot)
        if not cohort["ready"]:
            self._remove_tree(Path(snapshot["snapshot_path"]))
            return self._status(
                "WAITING_FOR_COHORT",
                inventory=inventory,
                cohort_readiness=cohort,
                thresholds={
                    "min_new_outcomes": self.min_new_outcomes,
                    "min_new_market_events": self.min_new_market_events,
                    "min_train_market_events": self.min_train_market_events,
                    "min_validation_market_events": (
                        self.min_validation_market_events
                    ),
                    "min_test_market_events": self.min_test_market_events,
                },
                current_champion_model_id=(
                    self.registry.current_champion_model_id()
                ),
                storage_maintenance=storage_maintenance,
            )
        model_id = self._model_id(
            started_at_ms, snapshot["dataset_fingerprint"]
        )
        parent_model_id = self.registry.current_champion_model_id()
        model_dir = self.model_root / model_id
        model_dir.mkdir(parents=True, exist_ok=False)
        registry_record = {
            "model_id": model_id,
            "parent_model_id": parent_model_id,
            "dataset_fingerprint": snapshot["dataset_fingerprint"],
            "dataset_snapshot_path": snapshot["snapshot_path"],
            "training_started_at_ms": started_at_ms,
            "training_completed_at_ms": None,
            "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
            "context_feature_schema_version": CONTEXT_FEATURE_SCHEMA_VERSION,
            "context_feature_names": list(CONTEXT_FEATURE_NAMES),
            "requires_complete_market_context": True,
            "requires_complete_cost_evidence": True,
            "strategy_schema": snapshot["strategy_schema"],
            "training_rows": 0,
            "independent_event_count": snapshot[
                "independent_event_count"
            ],
            "validation_metrics": None,
            "test_metrics": None,
            "artifact_checksum_sha256": None,
            "artifact_path": None,
            "data_cutoff_ms": snapshot["data_cutoff_ms"],
            "outcome_type": self.outcome_type,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
            "phase": "7.4",
            "paper_promotion_allowed": False,
        }
        self.registry.register_training(registry_record)
        try:
            result = self._train_model(
                model_id=model_id,
                model_dir=model_dir,
                snapshot=snapshot,
                parent_model_id=parent_model_id,
                started_at_ms=started_at_ms,
            )
            final_status = result.pop("status")
            record = self.registry.update_model(
                model_id,
                status=final_status,
                updates=result,
            )
            storage_maintenance = self._storage_maintenance(
                cutoff_ms=int(record.get("data_cutoff_ms", 0) or 0)
            )
            record = self.registry.get_model(model_id) or record
            return self._status(
                "TRAINING_COMPLETE",
                model_id=model_id,
                model_status=record["status"],
                current_champion_model_id=(
                    self.registry.current_champion_model_id()
                ),
                champion_changed=False,
                registry_path=str(self.registry.path),
                model_path=record.get("artifact_path"),
                snapshot_path=record.get("dataset_snapshot_path"),
                storage_maintenance=storage_maintenance,
            )
        except Exception as exc:
            completed_at_ms = int(time.time() * 1000)
            self.registry.update_model(
                model_id,
                status="INVALID",
                updates={
                    "training_completed_at_ms": completed_at_ms,
                    "failure_reason": f"{type(exc).__name__}:{exc}",
                },
            )
            self._status(
                "TRAINING_FAILED",
                model_id=model_id,
                reason=f"{type(exc).__name__}:{exc}",
                current_champion_model_id=(
                    self.registry.current_champion_model_id()
                ),
                champion_changed=False,
            )
            raise

    def _create_snapshot(self) -> dict:
        """Freeze the exact eligible training dataset without raw-data copies."""
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=".snapshot.", dir=str(self.snapshot_root)
            )
        )

        full_dataset_path = staging / ".training_dataset_all.tmp.jsonl"
        integrity_path = staging / "dataset_integrity_report.json"
        integrity = TrainingDatasetBuilder(
            observations_path=str(self.observations_path),
            outcomes_path=str(self.outcomes_path),
            dataset_path=str(full_dataset_path),
            report_path=str(integrity_path),
        ).build()
        if integrity["status"] == "EMPTY":
            raise AutoTrainingError("AUTO_TRAINING_DATASET_EMPTY")

        eligible_rows = []
        for line in full_dataset_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("outcome_type") != self.outcome_type:
                continue
            if (
                int(row.get("experiment_contract_version", 0) or 0)
                != EXPERIMENT_CONTRACT_VERSION
            ):
                continue
            if not str(row.get("market_event_id") or "").strip():
                continue
            if row.get("label_profitable") not in {True, False}:
                continue
            if not is_complete_market_context(
                market_context_from_row(row)
            ):
                continue
            if not has_complete_cost_evidence(row):
                continue
            eligible_rows.append(row)
        eligible_rows.sort(
            key=lambda row: (
                int(row["observed_at_ms"]),
                int(row["recorded_at_ms"]),
                row["candidate_observation_id"],
            )
        )
        if len(eligible_rows) < self.min_new_outcomes:
            raise AutoTrainingError(
                "AUTO_TRAINING_ELIGIBLE_DATA_BELOW_TRIGGER"
            )
        market_events = {
            row["market_event_id"] for row in eligible_rows
        }
        if len(market_events) < self.min_new_market_events:
            raise AutoTrainingError(
                "AUTO_TRAINING_ELIGIBLE_EVENTS_BELOW_TRIGGER"
            )

        eligible_path = staging / "training_dataset.jsonl"
        self._write_jsonl(eligible_path, eligible_rows)
        metadata = {
            "schema_version": AUTO_TRAINING_SCHEMA_VERSION,
            "environment": self.environment,
            "outcome_type": self.outcome_type,
            "experiment_contract_version": EXPERIMENT_CONTRACT_VERSION,
            "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
            "context_feature_schema_version": CONTEXT_FEATURE_SCHEMA_VERSION,
            "context_feature_names": list(CONTEXT_FEATURE_NAMES),
            "requires_complete_market_context": True,
            "requires_complete_cost_evidence": True,
            "rows": len(eligible_rows),
            "independent_market_events": len(market_events),
            "data_cutoff_ms": max(
                int(row["recorded_at_ms"]) for row in eligible_rows
            ),
            "source_mode": "LOGICAL_HISTORY_PLUS_LIVE",
            "observations_path": str(self.observations_path),
            "outcomes_path": str(self.outcomes_path),
        }
        fingerprint = self._fingerprint(
            eligible_path.read_bytes(), metadata
        )
        metadata["dataset_fingerprint"] = fingerprint
        metadata["strategy_schema"] = self._strategy_schema(eligible_rows)
        self._write_json(staging / "snapshot_manifest.json", metadata)

        # The all-outcomes join is only a build workspace. Keeping it beside the
        # filtered training dataset duplicated hundreds of MB per challenger.
        full_dataset_path.unlink(missing_ok=True)
        integrity["output"]["dataset_path"] = None
        integrity["output"]["full_dataset_persisted"] = False
        integrity["output"]["eligible_dataset_path"] = "training_dataset.jsonl"
        self._write_json(integrity_path, integrity)

        snapshot_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "_"
            + fingerprint[:12]
        )
        final_path = self.snapshot_root / snapshot_id
        if final_path.exists():
            shutil.rmtree(staging)
        else:
            os.replace(staging, final_path)
        self._make_read_only(final_path)
        return {
            "snapshot_path": str(final_path),
            "dataset_path": str(final_path / "training_dataset.jsonl"),
            "dataset_fingerprint": fingerprint,
            "rows": len(eligible_rows),
            "independent_event_count": len(market_events),
            "data_cutoff_ms": metadata["data_cutoff_ms"],
            "strategy_schema": metadata["strategy_schema"],
        }

    def _cohort_readiness(self, snapshot: dict) -> dict:
        """Prove independent-event split readiness before registering a model."""
        self.model_root.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".cohort.", dir=str(self.model_root))
        )
        try:
            report = TimeAwareDatasetSplitter(
                dataset_path=snapshot["dataset_path"],
                train_path=str(staging / "train.jsonl"),
                validation_path=str(staging / "validation.jsonl"),
                test_path=str(staging / "test.jsonl"),
                report_path=str(staging / "time_split_report.json"),
                train_ratio=self.train_ratio,
                validation_ratio=self.validation_ratio,
                test_ratio=self.test_ratio,
                embargo_seconds=self.embargo_seconds,
                group_by_market_event=True,
            ).split()
            counts = {
                name: int(report["splits"][name].get("market_event_groups", 0))
                for name in ("train", "validation", "test")
            }
            checks = {
                "split_ready": {
                    "actual": report["status"],
                    "required": "READY",
                    "passed": report["status"] == "READY",
                },
                "train_market_events": {
                    "actual": counts["train"],
                    "required_min": self.min_train_market_events,
                    "passed": counts["train"] >= self.min_train_market_events,
                },
                "validation_market_events": {
                    "actual": counts["validation"],
                    "required_min": self.min_validation_market_events,
                    "passed": (
                        counts["validation"]
                        >= self.min_validation_market_events
                    ),
                },
                "test_market_events": {
                    "actual": counts["test"],
                    "required_min": self.min_test_market_events,
                    "passed": counts["test"] >= self.min_test_market_events,
                },
                "market_event_isolation": {
                    "actual": report["leakage_checks"].get(
                        "market_event_overlap"
                    ),
                    "required": False,
                    "passed": report["leakage_checks"].get(
                        "market_event_overlap"
                    ) is False,
                },
            }
            return {
                "ready": all(item["passed"] for item in checks.values()),
                "checks": checks,
                "split_status": report["status"],
                "split_market_events": counts,
                "grouping_policy": report["configuration"][
                    "grouping_policy"
                ],
            }
        finally:
            self._remove_tree(staging)

    def _train_model(
        self,
        *,
        model_id: str,
        model_dir: Path,
        snapshot: dict,
        parent_model_id: str,
        started_at_ms: int,
    ) -> dict:
        split_dir = model_dir / "splits"
        split_dir.mkdir()
        train_path = split_dir / "train.jsonl"
        validation_path = split_dir / "validation.jsonl"
        test_path = split_dir / "test.jsonl"
        split_report_path = model_dir / "time_split_report.json"
        split_report = TimeAwareDatasetSplitter(
            dataset_path=snapshot["dataset_path"],
            train_path=str(train_path),
            validation_path=str(validation_path),
            test_path=str(test_path),
            report_path=str(split_report_path),
            train_ratio=self.train_ratio,
            validation_ratio=self.validation_ratio,
            test_ratio=self.test_ratio,
            embargo_seconds=self.embargo_seconds,
            group_by_market_event=True,
        ).split()
        if split_report["status"] != "READY":
            raise AutoTrainingError(
                "AUTO_TRAINING_SPLIT_NOT_READY | "
                f"status={split_report['status']}"
            )
        event_counts = {
            name: int(split_report["splits"][name].get("market_event_groups", 0))
            for name in ("train", "validation", "test")
        }
        event_thresholds = {
            "train": self.min_train_market_events,
            "validation": self.min_validation_market_events,
            "test": self.min_test_market_events,
        }
        if any(event_counts[name] < event_thresholds[name] for name in event_counts):
            raise AutoTrainingError(
                "AUTO_TRAINING_COHORT_NOT_READY | "
                f"events={event_counts} | required={event_thresholds}"
            )

        test_sha256_before = hashlib.sha256(test_path.read_bytes()).hexdigest()

        baseline_artifact = model_dir / "baseline.pkl"
        baseline_report_path = model_dir / "baseline_report.json"
        baseline_report = BaselineModelTrainer(
            train_path=str(train_path),
            validation_path=str(validation_path),
            test_path=None,
            artifact_path=str(baseline_artifact),
            report_path=str(baseline_report_path),
            outcome_type=self.outcome_type,
            min_train_rows=self.baseline_min_train_rows,
            min_eval_rows=self.baseline_min_eval_rows,
            random_state=self.random_state,
            context_aware=True,
            evaluate_test=False,
        ).train()

        ensemble_artifact = model_dir / "ensemble.pkl"
        ensemble_report_path = model_dir / "ensemble_report.json"
        ensemble_report = OfflineEnsembleExperiment(
            train_path=str(train_path),
            validation_path=str(validation_path),
            test_path=None,
            artifact_path=str(ensemble_artifact),
            report_path=str(ensemble_report_path),
            outcome_type=self.outcome_type,
            min_train_rows=self.ensemble_min_train_rows,
            min_eval_rows=self.ensemble_min_eval_rows,
            random_state=self.random_state,
            context_aware=True,
            evaluate_test=False,
        ).run()

        candidates = []
        if baseline_report.get("status") == "TRAINED":
            metrics = (baseline_report.get("metrics") or {}).get("validation")
            if isinstance(metrics, dict):
                candidates.append({
                    "name": "BASELINE",
                    "artifact_path": baseline_artifact,
                    "validation_metrics": metrics,
                })
        if ensemble_report.get("status") == "EXPERIMENT_COMPLETE":
            winner_report = ensemble_report.get("winner") or {}
            metrics = winner_report.get("validation_metrics")
            if isinstance(metrics, dict):
                candidates.append({
                    "name": "ENSEMBLE",
                    "artifact_path": ensemble_artifact,
                    "validation_metrics": metrics,
                })
        if not candidates:
            raise AutoTrainingError("AUTO_TRAINING_NO_VALID_MODEL")

        winner = min(candidates, key=self._candidate_selection_key)
        selected_at_ms = int(time.time() * 1000)
        pretest_selection = {
            "schema_version": 1,
            "model_id": model_id,
            "selected_at_ms": selected_at_ms,
            "selected_candidate": winner["name"],
            "selection_basis": "VALIDATION_LOG_LOSS_THEN_BRIER_THEN_ROC_AUC",
            "selected_using_test_data": False,
            "test_set_policy": "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED",
            "test_sha256": test_sha256_before,
            "candidates": {
                candidate["name"]: {
                    "validation_metrics": candidate["validation_metrics"],
                    "test_metrics": None,
                    "test_evaluated": False,
                }
                for candidate in candidates
            },
        }
        self._write_json(model_dir / "pretest_selection_report.json", pretest_selection)

        evaluation = ChallengerArtifactEvaluator(
            artifact_path=str(winner["artifact_path"]),
            validation_path=str(validation_path),
            test_path=str(test_path),
            calibration_bins=self.calibration_bins,
            drift_bins=self.drift_bins,
        ).evaluate()
        self._write_json(model_dir / "selected_challenger_evaluation.json", evaluation)
        if evaluation.get("status") != "EVALUATED":
            raise AutoTrainingError("AUTO_TRAINING_SELECTED_MODEL_EVALUATION_FAILED")

        test_sha256_after = hashlib.sha256(test_path.read_bytes()).hexdigest()
        if test_sha256_after != test_sha256_before:
            raise AutoTrainingError("AUTO_TRAINING_TEST_SET_MUTATED")

        gates = self._offline_gates(evaluation)
        final_status = "OFFLINE_VALIDATED" if gates["passed"] else "REJECTED"
        completed_at_ms = int(time.time() * 1000)
        selected_artifact = pickle.loads(winner["artifact_path"].read_bytes())
        selected_artifact.update({
            "phase": "7.4",
            "model_id": model_id,
            "parent_model_id": parent_model_id,
            "dataset_fingerprint": snapshot["dataset_fingerprint"],
            "dataset_snapshot_path": snapshot["snapshot_path"],
            "data_cutoff_ms": snapshot["data_cutoff_ms"],
            "training_started_at_ms": started_at_ms,
            "training_completed_at_ms": completed_at_ms,
            "strategy_schema": snapshot["strategy_schema"],
            "registry_status": final_status,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
            "paper_promotion_allowed": False,
            "test_set_policy": "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED",
            "selected_using_test_data": False,
            "test_sha256": test_sha256_after,
        })
        challenger_path = model_dir / "challenger.pkl"
        self._write_pickle(challenger_path, selected_artifact)
        checksum = hashlib.sha256(challenger_path.read_bytes()).hexdigest()
        selection_report = {
            "schema_version": 2,
            "model_id": model_id,
            "selected_candidate": winner["name"],
            "selection_basis": "VALIDATION_LOG_LOSS_THEN_BRIER_THEN_ROC_AUC",
            "selected_using_test_data": False,
            "test_set_policy": "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED",
            "test_sha256_before": test_sha256_before,
            "test_sha256_after": test_sha256_after,
            "test_unchanged": test_sha256_before == test_sha256_after,
            "pretest_selected_at_ms": selected_at_ms,
            "offline_gates": gates,
            "final_status": final_status,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
            "split_market_events": event_counts,
            "candidates": {
                candidate["name"]: {
                    "validation_metrics": candidate["validation_metrics"],
                    "test_evaluated": candidate["name"] == winner["name"],
                    "test_metrics": (
                        evaluation["metrics"]["test"]
                        if candidate["name"] == winner["name"]
                        else None
                    ),
                }
                for candidate in candidates
            },
        }
        self._write_json(model_dir / "challenger_selection_report.json", selection_report)
        train_rows = int(split_report["splits"]["train"]["rows"])
        return {
            "status": final_status,
            "training_completed_at_ms": completed_at_ms,
            "training_rows": train_rows,
            "split_market_events": event_counts,
            "validation_metrics": evaluation["metrics"]["validation"],
            "test_metrics": evaluation["metrics"]["test"],
            "calibration_metrics": {
                "validation_max_abs_gap": evaluation["calibration"]["validation_max_abs_gap"],
                "test_max_abs_gap": evaluation["calibration"]["test_max_abs_gap"],
            },
            "drift_metrics": {
                "max_feature_psi": evaluation["drift"]["max_feature_psi"]
            },
            "offline_gate_results": gates,
            "selected_candidate": winner["name"],
            "selected_using_test_data": False,
            "test_set_policy": "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED",
            "test_unchanged": True,
            "artifact_checksum_sha256": checksum,
            "artifact_path": str(challenger_path),
            "model_directory": str(model_dir),
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
        }

    @staticmethod
    def _candidate_selection_key(candidate: dict) -> tuple:
        metrics = candidate.get("validation_metrics")
        if not isinstance(metrics, dict):
            metrics = candidate["evaluation"]["metrics"]["validation"]
        roc_auc = metrics.get("roc_auc")
        return (
            float(metrics["log_loss"]),
            float(metrics["brier_score"]),
            -(float(roc_auc) if roc_auc is not None else -1.0),
            candidate["name"],
        )

    def _offline_gates(self, evaluation: dict) -> dict:
        test = evaluation["metrics"]["test"]
        roc_auc = test.get("roc_auc")
        checks = {
            "test_roc_auc": {
                "actual": roc_auc,
                "required_min": self.min_roc_auc,
                "passed": (
                    roc_auc is not None
                    and float(roc_auc) >= self.min_roc_auc
                ),
            },
            "test_brier_score": {
                "actual": test.get("brier_score"),
                "required_max": self.max_brier_score,
                "passed": float(test["brier_score"])
                <= self.max_brier_score,
            },
            "test_calibration_gap": {
                "actual": evaluation["calibration"][
                    "test_max_abs_gap"
                ],
                "required_max": self.max_calibration_gap,
                "passed": evaluation["calibration"][
                    "test_max_abs_gap"
                ]
                <= self.max_calibration_gap,
            },
            "feature_drift_psi": {
                "actual": evaluation["drift"]["max_feature_psi"],
                "required_max": self.max_feature_psi,
                "passed": evaluation["drift"]["max_feature_psi"]
                <= self.max_feature_psi,
            },
        }
        return {
            "passed": all(item["passed"] for item in checks.values()),
            "checks": checks,
        }

    def _storage_maintenance(self, *, cutoff_ms: int) -> dict:
        result = {
            "cutoff_ms": int(cutoff_ms),
            "rejected_models_pruned": [],
            "history_rotations": {},
        }
        if self.prune_rejected_storage:
            result["rejected_models_pruned"] = (
                self._prune_rejected_storage()
            )
        if self.history_rotation_enabled and int(cutoff_ms) > 0:
            tag = f"cutoff-{int(cutoff_ms)}"
            for name, path in (
                ("candidate_observations", self.observations_path),
                ("candidate_outcomes", self.outcomes_path),
                ("virtual_trades", self.virtual_trades_path),
            ):
                if path is None:
                    continue
                try:
                    result["history_rotations"][name] = (
                        rotate_jsonl_to_history(
                            path,
                            segment_tag=tag,
                            min_bytes=self.history_rotate_min_bytes,
                        )
                    )
                except Exception as exc:
                    result["history_rotations"][name] = {
                        "rotated": False,
                        "reason": f"{type(exc).__name__}:{exc}",
                    }
        return result

    def _prune_rejected_storage(self) -> list[dict]:
        document = self.registry.load()
        pruned = []
        for model_id, record in sorted(document.get("models", {}).items()):
            if record.get("status") != "REJECTED":
                continue
            if record.get("storage_pruned_at_ms"):
                continue

            original_snapshot = record.get("dataset_snapshot_path")
            original_model_dir = record.get("model_directory")
            reclaimed = 0
            removed = []
            for kind, raw_path, root in (
                ("snapshot", original_snapshot, self.snapshot_root),
                ("model", original_model_dir, self.model_root),
            ):
                if not raw_path:
                    continue
                target = Path(raw_path)
                if not self._is_within(target, root):
                    continue
                reclaimed += self._tree_size(target)
                if target.exists():
                    self._remove_tree(target)
                    removed.append(kind)

            now_ms = int(time.time() * 1000)
            updates = {
                "storage_pruned_at_ms": now_ms,
                "storage_prune_reason": "REJECTED_CHALLENGER",
                "storage_reclaimed_bytes": reclaimed,
                "pruned_dataset_snapshot_path": original_snapshot,
                "pruned_model_directory": original_model_dir,
                "artifact_path": None,
                "model_directory": None,
                "dataset_snapshot_path": None,
            }
            self.registry.update_model(model_id, updates=updates)
            pruned.append(
                {
                    "model_id": model_id,
                    "removed": removed,
                    "bytes_reclaimed": reclaimed,
                }
            )
        return pruned

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            return False

    @staticmethod
    def _tree_size(path: Path) -> int:
        if not path.exists():
            return 0
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    pass
        return total

    @staticmethod
    def _remove_tree(path: Path) -> None:
        if not path.exists():
            return
        if path.is_file():
            path.chmod(0o600)
            path.unlink()
            return
        for child in path.rglob("*"):
            try:
                child.chmod(0o700 if child.is_dir() else 0o600)
            except FileNotFoundError:
                pass
        path.chmod(0o700)
        shutil.rmtree(path)

    def _status(self, status: str, **details) -> dict:
        document = {
            "schema_version": AUTO_TRAINING_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "phase": "7.4",
            "status": status,
            "environment": self.environment,
            "process_id": os.getpid(),
            "runtime_process": "SEPARATE_FROM_TRADING_ENGINE",
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
            **details,
        }
        self._write_json(self.status_path, document)
        return document

    @staticmethod
    def _model_id(started_at_ms: int, fingerprint: str) -> str:
        timestamp = datetime.fromtimestamp(
            started_at_ms / 1000.0, tz=timezone.utc
        )
        stamp = timestamp.strftime("%Y%m%dT%H%M%S")
        milliseconds = f"{started_at_ms % 1000:03d}"
        return (
            f"CHALLENGER_{stamp}{milliseconds}Z_"
            f"{fingerprint[:8].upper()}"
        )

    @staticmethod
    def _fingerprint(dataset_bytes: bytes, metadata: dict) -> str:
        digest = hashlib.sha256()
        digest.update(dataset_bytes)
        digest.update(b"\n--PHASE5.8-METADATA--\n")
        digest.update(
            json.dumps(
                metadata, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        return digest.hexdigest()

    @staticmethod
    def _strategy_schema(rows: list[dict]) -> dict:
        return {
            "experiment_contract_versions": sorted(
                {
                    int(row["experiment_contract_version"])
                    for row in rows
                }
            ),
            "strategy_versions": sorted(
                {str(row.get("strategy_version") or "UNKNOWN") for row in rows}
            ),
            "strategy_variant_ids": sorted(
                {
                    str(row.get("strategy_variant_id") or "UNKNOWN")
                    for row in rows
                }
            ),
            "outcome_variant_ids": sorted(
                {
                    str(row.get("outcome_variant_id") or "UNKNOWN")
                    for row in rows
                }
            ),
            "strategy_lab_catalog_versions": sorted(
                {
                    str(
                        row.get("strategy_lab_catalog_version")
                        or "NOT_LAB_RECORD"
                    )
                    for row in rows
                }
            ),
        }

    @staticmethod
    def _make_read_only(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.chmod(0o444)
            elif path.is_dir():
                path.chmod(0o555)
        root.chmod(0o555)

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _write_json(path: Path, document: dict) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
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

    @staticmethod
    def _write_pickle(path: Path, document: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                pickle.dump(document, handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
