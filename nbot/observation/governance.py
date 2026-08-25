"""V3.9.2/V3.9.3 compact-memory model registry and rolling governance.

This module is Observation-only.  It materializes immutable model artifact files
from permanent compact research memory, builds immutable registry/report records,
and summarizes chronological challenger windows without rewriting any historical
final-test decision.

The first governance contract deliberately stops at *research-champion review
eligibility*.  It does not mutate the Champion pointer, does not create PAPER
CHAMPION authority, and has no Execution/order imports.  This keeps promotion
semantics frozen before the first *eligibility-counting* V3.9 challenger final window is judged.
Historical windows finalized before governance activation remain auditable but cannot count toward promotion eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from .challengers import (
    AUTHORITY,
    CHALLENGER_PREFIX,
    EVALUATION_PREFIX,
    FINAL_EVALUATION_STATUSES,
    MODEL_PREFIX,
)
from .research_memory import ResearchMemoryStore
from .selection import SELECTION_CONFIG


REGISTRY_VERSION = "V39_MODEL_REGISTRY_V1"
ROLLING_VERSION = "V39_ROLLING_REEVALUATION_V1"
ELIGIBILITY_VERSION = "V39_RESEARCH_CHAMPION_ELIGIBILITY_V1"
MODEL_REGISTRY_PREFIX = "v39:registry:model:"
CHALLENGER_REGISTRY_PREFIX = "v39:registry:challenger:"
ROLLING_REPORT_PREFIX = "v39:rolling:report:"
CONTRACT_KEY = f"v39:governance:contract:{ELIGIBILITY_VERSION}"
CHAMPION_POINTER_PREFIX = "v39:registry:champion-pointer:"
ROLLBACK_STATE_PREFIX = "v39:registry:rollback-state:"
CHAMPION_POINTER_GENESIS_KEY = CHAMPION_POINTER_PREFIX + "000000-genesis"
ROLLBACK_STATE_GENESIS_KEY = ROLLBACK_STATE_PREFIX + "000000-genesis"
ELIGIBILITY_EPOCH_KEY = f"v39:governance:eligibility-epoch:{ELIGIBILITY_VERSION}"


@dataclass(frozen=True)
class GovernanceConfig:
    registry_version: str = REGISTRY_VERSION
    rolling_version: str = ROLLING_VERSION
    eligibility_version: str = ELIGIBILITY_VERSION
    min_consecutive_pass_windows: int = 3
    min_total_test_events: int = 60
    min_total_trade_events: int = 15
    min_elapsed_hours: float = 48.0
    min_distinct_test_utc_dates: int = 3
    min_drift_transitions: int = 2
    confidence_level: float = 0.95
    bootstrap_samples: int = 2000

    def validate(self) -> None:
        if self.registry_version != REGISTRY_VERSION:
            raise ValueError("NBOT_V392_REGISTRY_VERSION_IMMUTABLE")
        if self.rolling_version != ROLLING_VERSION:
            raise ValueError("NBOT_V393_ROLLING_VERSION_IMMUTABLE")
        if self.eligibility_version != ELIGIBILITY_VERSION:
            raise ValueError("NBOT_V393_ELIGIBILITY_VERSION_IMMUTABLE")
        if self.min_consecutive_pass_windows != 3:
            raise ValueError("NBOT_V393_PASS_WINDOWS_IMMUTABLE")
        if self.min_total_test_events != 60:
            raise ValueError("NBOT_V393_TEST_EVENTS_IMMUTABLE")
        if self.min_total_trade_events != 15:
            raise ValueError("NBOT_V393_TRADE_EVENTS_IMMUTABLE")
        if self.min_elapsed_hours != 48.0:
            raise ValueError("NBOT_V393_ELAPSED_HOURS_IMMUTABLE")
        if self.min_distinct_test_utc_dates != 3:
            raise ValueError("NBOT_V393_DISTINCT_DATES_IMMUTABLE")
        if self.min_drift_transitions != 2:
            raise ValueError("NBOT_V393_DRIFT_TRANSITIONS_IMMUTABLE")
        if self.confidence_level != 0.95 or self.bootstrap_samples != 2000:
            raise ValueError("NBOT_V393_CONFIDENCE_CONTRACT_IMMUTABLE")


CONFIG = GovernanceConfig()
CONFIG.validate()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc_date(event_ms: int) -> str:
    return datetime.fromtimestamp(int(event_ms) / 1000.0, tz=timezone.utc).date().isoformat()


def _weighted_mean(items: list[tuple[float | None, int]]) -> float | None:
    valid = [(float(value), int(weight)) for value, weight in items if value is not None and int(weight) > 0]
    total = sum(weight for _, weight in valid)
    if total <= 0:
        return None
    return sum(value * weight for value, weight in valid) / total


class ModelGovernanceRegistry:
    """Observation-owned immutable registry and rolling reevaluation summary."""

    def __init__(
        self,
        memory: ResearchMemoryStore,
        artifact_root: Path,
        *,
        config: GovernanceConfig = CONFIG,
    ) -> None:
        self.memory = memory
        self.artifact_root = Path(artifact_root)
        self.config = config
        self.config.validate()

    def contract(self) -> dict[str, Any]:
        return {
            "registry_version": self.config.registry_version,
            "rolling_version": self.config.rolling_version,
            "eligibility_version": self.config.eligibility_version,
            "authority": AUTHORITY,
            "model_artifacts": "OBSERVATION_LOCAL_IMMUTABLE_CANONICAL_JSON",
            "historical_final_test_rule": "NEVER_REWRITE_OR_EXTEND_A_FINAL_WINDOW",
            "rolling_rule": "EACH_FINAL_CHALLENGER_WINDOW_IS_AN_IMMUTABLE_CHRONOLOGICAL_EVIDENCE_UNIT",
            "drift_metric": "TRAINING_STANDARDIZED_MEAN_SHIFT_RMS_V1",
            "calibration_brier": "NOT_APPLICABLE_TO_RIDGE_REGRESSION_WITHOUT_PROBABILITY_OUTPUT",
            "live_operational_degradation": "DEFERRED_UNTIL_RESEARCH_CHAMPION_HAS_LIVE_PAPER_AUTHORITY",
            "research_champion_review_gate": {
                "evidence_epoch_rule": "ONLY_WINDOWS_WITH_TRAINING_CUTOFF_AT_OR_AFTER_IMMUTABLE_GOVERNANCE_EPOCH",
                "pre_governance_windows": "AUDIT_ONLY_EXCLUDED_FROM_ELIGIBILITY",
                "consecutive_pass_windows": self.config.min_consecutive_pass_windows,
                "total_untouched_test_events": self.config.min_total_test_events,
                "total_trade_events": self.config.min_total_trade_events,
                "minimum_elapsed_hours": self.config.min_elapsed_hours,
                "distinct_test_utc_dates": self.config.min_distinct_test_utc_dates,
                "drift_transitions_monitored": self.config.min_drift_transitions,
                "all_individual_window_gates": "PASS_RESEARCH_GATE",
                "automatic_promotion": False,
            },
            "champion_pointer_mutation": "DISABLED_IN_V3_9_2_V3_9_3",
            "paper_champion_mutation": "FORBIDDEN",
            "execution_authority": "NONE",
        }

    @property
    def contract_hash(self) -> str:
        return _digest(self.contract())

    def _artifact_file(self, model_version: str) -> Path:
        name = str(model_version).strip()
        if not name or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for ch in name):
            raise ValueError("NBOT_V392_MODEL_FILE_NAME_INVALID")
        return self.artifact_root / f"{name}.json"

    def _materialize_model(self, model_record: dict[str, Any]) -> dict[str, Any]:
        payload = model_record["payload"]
        model_version = str(payload["model_version"])
        text = _canonical_json(payload)
        raw = text.encode("utf-8")
        expected = _sha256_bytes(raw)
        if expected != str(model_record["artifact_digest"]):
            raise RuntimeError("NBOT_V392_MEMORY_MODEL_DIGEST_MISMATCH")
        target = self._artifact_file(model_version)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_bytes()
            if existing != raw or _sha256_bytes(existing) != expected:
                raise RuntimeError(f"NBOT_V392_MODEL_FILE_IDENTITY_CONFLICT:{model_version}")
        else:
            temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            try:
                with temp.open("xb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
                directory_fd = os.open(str(target.parent), os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temp.exists():
                    temp.unlink()
        return {
            "artifact_file": target.name,
            "artifact_file_sha256": expected,
            "artifact_file_bytes": len(raw),
        }

    @staticmethod
    def _model_registry_payload(model_record: dict[str, Any], file_info: dict[str, Any]) -> dict[str, Any]:
        model = model_record["payload"]
        return {
            "registry_version": REGISTRY_VERSION,
            "record_type": "MODEL",
            "model_version": str(model["model_version"]),
            "model_family": str(model["model_family"]),
            "selector_version": str(model["selector_version"]),
            "feature_version": SELECTION_CONFIG.feature_version,
            "target_version": SELECTION_CONFIG.target_name,
            "target_policy_version": SELECTION_CONFIG.target_policy_version,
            "hyperparameters": {"ridge_alpha": float(model["model"]["alpha"])},
            "training_window": {
                "through_event_ms": int(model["training_cutoff_event_ms"]),
                "training_event_count": int(model["training_event_count"]),
                "training_row_count": int(model["training_row_count"]),
            },
            "training_source_digest": str(model["training_source_digest"]),
            "ridge_state_digest": str(model["ridge_state_digest"]),
            "model_digest": str(model["model_digest"]),
            "memory_artifact_digest": str(model_record["artifact_digest"]),
            "artifact_storage": "OBSERVATION_LOCAL_IMMUTABLE_FILE",
            **file_info,
            "release_sha": str(model["release_sha"]),
            "status": "CHALLENGER_MODEL",
            "authority": AUTHORITY,
        }

    @staticmethod
    def _challenger_registry_payload(challenger_record: dict[str, Any]) -> dict[str, Any]:
        challenger = challenger_record["payload"]
        return {
            "registry_version": REGISTRY_VERSION,
            "record_type": "CHALLENGER",
            "challenger_version": str(challenger["challenger_version"]),
            "challenger_family": str(challenger["challenger_family"]),
            "model_version": str(challenger["model_version"]),
            "model_artifact_digest": str(challenger["model_artifact_digest"]),
            "training_cutoff_event_ms": int(challenger["training_cutoff_event_ms"]),
            "definition_hash": str(challenger["definition_hash"]),
            "release_sha": str(challenger["release_sha"]),
            "registered_state": "CHALLENGER",
            "state_is_derived_from_immutable_evaluation": True,
            "authority": AUTHORITY,
        }

    def _model_records_by_version(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for record in self.memory.list_artifacts(prefix=MODEL_PREFIX):
            result[str(record["payload"]["model_version"])] = record
        return result

    @staticmethod
    def _drift(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
        if previous is None:
            return {
                "metric_version": "TRAINING_STANDARDIZED_MEAN_SHIFT_RMS_V1",
                "status": "BASELINE_NO_PREVIOUS_MODEL",
                "rms_standardized_mean_shift": None,
                "max_abs_standardized_mean_shift": None,
                "max_shift_feature": None,
            }
        current_model = current["payload"]["model"]
        previous_model = previous["payload"]["model"]
        shifts: dict[str, float] = {}
        for feature, current_mean in current_model["means"].items():
            previous_mean = float(previous_model["means"][feature])
            previous_scale = max(abs(float(previous_model["scales"][feature])), 1e-12)
            shifts[str(feature)] = (float(current_mean) - previous_mean) / previous_scale
        values = list(shifts.values())
        rms = math.sqrt(sum(value * value for value in values) / len(values)) if values else 0.0
        feature = None if not shifts else sorted(shifts, key=lambda key: (-abs(shifts[key]), key))[0]
        return {
            "metric_version": "TRAINING_STANDARDIZED_MEAN_SHIFT_RMS_V1",
            "status": "MONITORED",
            "rms_standardized_mean_shift": rms,
            "max_abs_standardized_mean_shift": None if feature is None else abs(shifts[feature]),
            "max_shift_feature": feature,
        }

    def _rolling_report_payload(
        self,
        evaluation_record: dict[str, Any],
        challenger_record: dict[str, Any],
        model_record: dict[str, Any],
        previous_model_record: dict[str, Any] | None,
    ) -> dict[str, Any]:
        evaluation = evaluation_record["payload"]
        final = evaluation["final_test"]
        test_events = [int(value) for value in evaluation["test_events"]]
        date_counts: dict[str, int] = {}
        for event in test_events:
            day = _utc_date(event)
            date_counts[day] = date_counts.get(day, 0) + 1
        max_date_concentration = (max(date_counts.values()) / len(test_events)) if test_events else None
        candidate = final["candidate"]
        paired = final["paired_lift"]
        stability = final["stability"]
        cost = final["cost_and_capture"]
        regret = final["selection_regret"]
        utilization = final["trade_utilization"]
        return {
            "rolling_version": self.config.rolling_version,
            "record_type": "ROLLING_CHALLENGER_WINDOW",
            "challenger_version": str(evaluation["challenger_version"]),
            "challenger_family": str(evaluation["challenger_family"]),
            "model_version": str(evaluation["model_version"]),
            "training_cutoff_event_ms": int(evaluation["training_cutoff_event_ms"]),
            "status": str(evaluation["status"]),
            "immutable_evaluation_digest": str(evaluation["evaluation_digest"]),
            "immutable_evaluation_artifact_digest": str(evaluation_record["artifact_digest"]),
            "challenger_artifact_digest": str(challenger_record["artifact_digest"]),
            "model_artifact_digest": str(model_record["artifact_digest"]),
            "validation_events": len(evaluation["validation_events"]),
            "test_events": len(test_events),
            "test_start_event_ms": None if not test_events else min(test_events),
            "test_end_event_ms": None if not test_events else max(test_events),
            "test_utc_dates": sorted(date_counts),
            "max_test_date_concentration": max_date_concentration,
            "after_cost_expectancy": {
                "mean_net_r": candidate.get("mean_net_r"),
                "median_net_r": candidate.get("median_net_r"),
                "mean_ci_low": candidate.get("mean_ci_low"),
                "mean_ci_high": candidate.get("mean_ci_high"),
                "profit_factor": candidate.get("profit_factor"),
                "max_drawdown_r": candidate.get("max_drawdown_r"),
            },
            "paired_lift": {
                "mean_lift_r": paired.get("mean_lift_r"),
                "median_lift_r": paired.get("median_lift_r"),
                "mean_lift_ci_low": paired.get("mean_lift_ci_low"),
                "mean_lift_ci_high": paired.get("mean_lift_ci_high"),
                "candidate_better_event_rate": paired.get("candidate_better_event_rate"),
            },
            "trade_utilization": utilization,
            "winner_capture": {
                "selected_winner_capture_mean": cost.get("selected_winner_capture_mean"),
                "control_winner_capture_median": cost.get("control_winner_capture_median"),
                "capture_comparison_ready": cost.get("capture_comparison_ready"),
            },
            "selection_regret": regret,
            "symbol_concentration": {
                "most_selected_symbol": stability.get("most_selected_symbol"),
                "max_selected_symbol_concentration": stability.get("max_selected_symbol_concentration"),
                "leave_most_selected_symbol_out_mean_net_r": stability.get("leave_most_selected_symbol_out_mean_net_r"),
            },
            "regimes": {
                "direction": stability.get("direction_regimes", {}),
                "volatility": stability.get("volatility_regimes", {}),
                "covered_regime_groups": stability.get("covered_regime_groups"),
                "no_catastrophic_covered_regime": stability.get("no_catastrophic_covered_regime"),
            },
            "cost_stress": cost.get("cost_stress", {}),
            "drift": self._drift(model_record, previous_model_record),
            "calibration_brier": {
                "status": "NOT_APPLICABLE",
                "reason": "RIDGE_EXPECTED_NET_R_IS_REGRESSION_NOT_A_PROBABILITY_MODEL",
            },
            "live_operational_degradation": {
                "status": "DEFERRED",
                "reason": "NO_RESEARCH_CHAMPION_PAPER_AUTHORITY_YET",
            },
            "promotion_gates": evaluation.get("promotion_gates", {}),
            "historical_final_test_mutable": False,
            "automatic_promotion": False,
            "authority": AUTHORITY,
        }

    def _expected_reports(self) -> list[dict[str, Any]]:
        models = self._model_records_by_version()
        challengers = {
            str(record["payload"]["challenger_version"]): record
            for record in self.memory.list_artifacts(prefix=CHALLENGER_PREFIX)
        }
        ordered_models = sorted(
            models.values(),
            key=lambda record: (
                int(record["payload"]["training_cutoff_event_ms"]),
                str(record["payload"]["model_version"]),
            ),
        )
        previous_by_model: dict[str, dict[str, Any] | None] = {}
        previous = None
        for record in ordered_models:
            version = str(record["payload"]["model_version"])
            previous_by_model[version] = previous
            previous = record

        reports: list[dict[str, Any]] = []
        for evaluation_record in self.memory.list_artifacts(prefix=EVALUATION_PREFIX):
            evaluation = evaluation_record["payload"]
            if str(evaluation.get("status")) not in FINAL_EVALUATION_STATUSES:
                continue
            challenger_version = str(evaluation["challenger_version"])
            model_version = str(evaluation["model_version"])
            challenger = challengers.get(challenger_version)
            model = models.get(model_version)
            if challenger is None or model is None:
                raise RuntimeError("NBOT_V393_ROLLING_ARTIFACT_REFERENCE_MISSING")
            reports.append(self._rolling_report_payload(
                evaluation_record, challenger, model, previous_by_model.get(model_version)
            ))
        reports.sort(key=lambda report: (
            int(report["test_end_event_ms"] or -1),
            str(report["challenger_version"]),
        ))
        return reports

    def _eligibility_epoch(self) -> dict[str, Any] | None:
        record = self.memory.artifact(ELIGIBILITY_EPOCH_KEY)
        return None if record is None else record["payload"]

    def _build_eligibility_epoch(self) -> dict[str, Any]:
        evaluations = {
            str(record["payload"]["challenger_version"])
            for record in self.memory.list_artifacts(prefix=EVALUATION_PREFIX)
            if str(record["payload"].get("status")) in FINAL_EVALUATION_STATUSES
        }
        active = []
        for record in self.memory.list_artifacts(prefix=CHALLENGER_PREFIX):
            payload = record["payload"]
            version = str(payload["challenger_version"])
            if version not in evaluations:
                active.append(payload)
        if len(active) != 1:
            raise RuntimeError(
                f"NBOT_V393_ELIGIBILITY_EPOCH_REQUIRES_ONE_ACTIVE_CHALLENGER:{len(active)}"
            )
        challenger = active[0]
        cutoff = int(challenger["training_cutoff_event_ms"])
        historical = 0
        for record in self.memory.list_artifacts(prefix=EVALUATION_PREFIX):
            payload = record["payload"]
            if str(payload.get("status")) not in FINAL_EVALUATION_STATUSES:
                continue
            linked = self.memory.artifact(CHALLENGER_PREFIX + str(payload["challenger_version"]))
            if linked is None:
                raise RuntimeError("NBOT_V393_ELIGIBILITY_EPOCH_CHALLENGER_MISSING")
            if int(linked["payload"]["training_cutoff_event_ms"]) < cutoff:
                historical += 1
        return {
            "eligibility_version": self.config.eligibility_version,
            "record_type": "RESEARCH_CHAMPION_ELIGIBILITY_EPOCH",
            "start_challenger_version": str(challenger["challenger_version"]),
            "minimum_training_cutoff_event_ms": cutoff,
            "pre_governance_final_windows": historical,
            "pre_governance_window_policy": "AUDIT_ONLY_EXCLUDED_FROM_ELIGIBILITY",
            "future_window_policy": "TRAINING_CUTOFF_GTE_EPOCH_COUNTS_IF_ALL_FROZEN_GATES_PASS",
            "automatic_promotion": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }

    def _ensure_eligibility_epoch(self) -> dict[str, Any]:
        existing = self.memory.artifact(ELIGIBILITY_EPOCH_KEY)
        if existing is not None:
            return existing["payload"]
        payload = self._build_eligibility_epoch()
        return self.memory.persist_artifact(ELIGIBILITY_EPOCH_KEY, payload)["payload"]

    def _eligibility(self, reports: list[dict[str, Any]], epoch: dict[str, Any] | None = None) -> dict[str, Any]:
        window_count = self.config.min_consecutive_pass_windows
        epoch = self._eligibility_epoch() if epoch is None else epoch
        if epoch is None:
            eligible_reports: list[dict[str, Any]] = []
            epoch_cutoff = None
        else:
            epoch_cutoff = int(epoch["minimum_training_cutoff_event_ms"])
            eligible_reports = [
                report for report in reports
                if int(report["training_cutoff_event_ms"]) >= epoch_cutoff
            ]
        latest = (
            eligible_reports[-window_count:]
            if len(eligible_reports) >= window_count
            else list(eligible_reports)
        )
        all_pass = len(latest) == window_count and all(
            report["status"] == "PASS_RESEARCH_GATE" for report in latest
        )
        test_events = sum(int(report["test_events"]) for report in latest)
        trade_events = sum(int(report["trade_utilization"]["trade_events"]) for report in latest)
        all_test_event_ids: list[int] = []
        # Reports store the frozen window bounds/date set rather than all IDs;
        # use the linked immutable evaluations for exact chronology/date counts.
        for report in latest:
            evaluation = self.memory.artifact(EVALUATION_PREFIX + str(report["challenger_version"]))
            if evaluation is None:
                raise RuntimeError("NBOT_V393_ELIGIBILITY_EVALUATION_MISSING")
            all_test_event_ids.extend(int(value) for value in evaluation["payload"]["test_events"])
        elapsed_hours = 0.0
        if all_test_event_ids:
            elapsed_hours = (max(all_test_event_ids) - min(all_test_event_ids)) / 3_600_000.0
        distinct_dates = len({_utc_date(value) for value in all_test_event_ids})
        drift_transitions = sum(
            report["drift"].get("status") == "MONITORED" for report in latest
        )
        candidate_weighted_mean = _weighted_mean([
            (report["after_cost_expectancy"].get("mean_net_r"), int(report["test_events"]))
            for report in latest
        ])
        paired_weighted_mean = _weighted_mean([
            (report["paired_lift"].get("mean_lift_r"), int(report["test_events"]))
            for report in latest
        ])
        gates = {
            "three_consecutive_pass_windows": all_pass,
            "minimum_untouched_test_events": test_events >= self.config.min_total_test_events,
            "minimum_trade_events": trade_events >= self.config.min_total_trade_events,
            "minimum_elapsed_hours": elapsed_hours >= self.config.min_elapsed_hours,
            "minimum_distinct_test_utc_dates": distinct_dates >= self.config.min_distinct_test_utc_dates,
            "minimum_drift_transitions_monitored": drift_transitions >= self.config.min_drift_transitions,
            "positive_weighted_after_cost_expectancy": candidate_weighted_mean is not None and candidate_weighted_mean > 0,
            "positive_weighted_paired_lift": paired_weighted_mean is not None and paired_weighted_mean > 0,
            "all_window_cost_stress_2x_positive": len(latest) == window_count and all(
                report["cost_stress"].get("2.0x", {}).get("mean_net_r") is not None
                and float(report["cost_stress"]["2.0x"]["mean_net_r"]) > 0
                for report in latest
            ),
            "historical_windows_immutable": all(
                report.get("historical_final_test_mutable") is False for report in latest
            ),
            "automatic_promotion_disabled": True,
        }
        eligible = bool(gates) and all(gates.values())
        return {
            "eligibility_version": self.config.eligibility_version,
            "window_basis": [str(report["challenger_version"]) for report in latest],
            "available_final_windows": len(eligible_reports),
            "all_historical_final_windows": len(reports),
            "excluded_pre_governance_windows": len(reports) - len(eligible_reports),
            "eligibility_epoch": epoch,
            "eligibility_epoch_training_cutoff_event_ms": epoch_cutoff,
            "considered_windows": len(latest),
            "total_test_events": test_events,
            "total_trade_events": trade_events,
            "elapsed_test_hours": elapsed_hours,
            "distinct_test_utc_dates": distinct_dates,
            "drift_transitions_monitored": drift_transitions,
            "weighted_after_cost_mean_r": candidate_weighted_mean,
            "weighted_paired_lift_mean_r": paired_weighted_mean,
            "gates": gates,
            "eligible_for_research_champion_review": eligible,
            "decision": "ELIGIBLE_FOR_RESEARCH_CHAMPION_REVIEW" if eligible else "NOT_YET_ELIGIBLE",
            "automatic_promotion": False,
            "champion_pointer_changed": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }

    def _latest_generation_payload(self, prefix: str, genesis_key: str) -> dict[str, Any] | None:
        records = self.memory.list_artifacts(prefix=prefix)
        if not records:
            record = self.memory.artifact(genesis_key)
            return None if record is None else record["payload"]
        records.sort(key=lambda row: (
            int(row["payload"].get("generation", -1)),
            int(row["recorded_at_ms"]),
            str(row["artifact_key"]),
        ))
        return records[-1]["payload"]

    def _genesis_records(self) -> tuple[dict[str, Any], dict[str, Any]]:
        pointer = {
            "registry_version": self.config.registry_version,
            "record_type": "CHAMPION_POINTER",
            "generation": 0,
            "current_research_champion": None,
            "previous_research_champion": None,
            "reason": "NO_V39_RESEARCH_CHAMPION_PROMOTION_AUTHORIZED",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }
        rollback = {
            "registry_version": self.config.registry_version,
            "record_type": "ROLLBACK_STATE",
            "generation": 0,
            "status": "DISABLED_NO_RESEARCH_CHAMPION",
            "from_model_version": None,
            "to_model_version": None,
            "automatic_rollback": False,
            "operator_required_if_later_enabled": True,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }
        return pointer, rollback

    def sync(self) -> dict[str, Any]:
        contract = self.memory.persist_artifact(CONTRACT_KEY, self.contract())
        eligibility_epoch = self._ensure_eligibility_epoch()
        pointer, rollback = self._genesis_records()
        self.memory.persist_artifact(CHAMPION_POINTER_GENESIS_KEY, pointer)
        self.memory.persist_artifact(ROLLBACK_STATE_GENESIS_KEY, rollback)

        model_count = 0
        for model_record in self.memory.list_artifacts(prefix=MODEL_PREFIX):
            file_info = self._materialize_model(model_record)
            registry = self._model_registry_payload(model_record, file_info)
            self.memory.persist_artifact(
                MODEL_REGISTRY_PREFIX + str(registry["model_version"]), registry
            )
            model_count += 1

        challenger_count = 0
        for challenger_record in self.memory.list_artifacts(prefix=CHALLENGER_PREFIX):
            registry = self._challenger_registry_payload(challenger_record)
            self.memory.persist_artifact(
                CHALLENGER_REGISTRY_PREFIX + str(registry["challenger_version"]), registry
            )
            challenger_count += 1

        reports = self._expected_reports()
        for report in reports:
            self.memory.persist_artifact(
                ROLLING_REPORT_PREFIX + str(report["challenger_version"]), report
            )

        return {
            "registry_version": self.config.registry_version,
            "rolling_version": self.config.rolling_version,
            "contract_hash": self.contract_hash,
            "contract_artifact_digest": contract["artifact_digest"],
            "models_synced": model_count,
            "challengers_synced": challenger_count,
            "rolling_reports_synced": len(reports),
            "eligibility_epoch": eligibility_epoch,
            "eligibility": self._eligibility(reports, eligibility_epoch),
            "authority": AUTHORITY,
            "automatic_promotion": False,
        }

    def status(self) -> dict[str, Any]:
        models = self.memory.list_artifacts(prefix=MODEL_REGISTRY_PREFIX)
        challengers = self.memory.list_artifacts(prefix=CHALLENGER_REGISTRY_PREFIX)
        reports = [record["payload"] for record in self.memory.list_artifacts(prefix=ROLLING_REPORT_PREFIX)]
        reports.sort(key=lambda report: (
            int(report.get("test_end_event_ms") or -1), str(report.get("challenger_version"))
        ))
        evaluations = {
            str(record["payload"].get("challenger_version")): record["payload"]
            for record in self.memory.list_artifacts(prefix=EVALUATION_PREFIX)
        }
        challenger_states = []
        for record in challengers:
            payload = record["payload"]
            version = str(payload["challenger_version"])
            evaluation = evaluations.get(version)
            challenger_states.append({
                "challenger_version": version,
                "model_version": payload["model_version"],
                "training_cutoff_event_ms": payload["training_cutoff_event_ms"],
                "state": "ACTIVE_WAITING_FUTURE_EVIDENCE" if evaluation is None else str(evaluation["status"]),
            })
        pointer = self._latest_generation_payload(CHAMPION_POINTER_PREFIX, CHAMPION_POINTER_GENESIS_KEY)
        rollback = self._latest_generation_payload(ROLLBACK_STATE_PREFIX, ROLLBACK_STATE_GENESIS_KEY)
        eligibility_epoch_record = self.memory.artifact(ELIGIBILITY_EPOCH_KEY)
        eligibility_epoch = None if eligibility_epoch_record is None else eligibility_epoch_record["payload"]
        return {
            "registry_version": self.config.registry_version,
            "rolling_version": self.config.rolling_version,
            "eligibility_version": self.config.eligibility_version,
            "authority": AUTHORITY,
            "artifact_root": str(self.artifact_root),
            "registered_models": len(models),
            "registered_challengers": len(challengers),
            "rolling_final_windows": len(reports),
            "challenger_states": challenger_states,
            "latest_rolling_window": None if not reports else reports[-1],
            "eligibility_epoch": eligibility_epoch,
            "research_champion_eligibility": self._eligibility(reports, eligibility_epoch),
            "champion_pointer": pointer,
            "rollback_state": rollback,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    def audit(self) -> dict[str, Any]:
        report = {
            "registry_version": self.config.registry_version,
            "rolling_version": self.config.rolling_version,
            "authority": AUTHORITY,
            "contract_missing_or_mismatch": 0,
            "model_registry_reference_mismatch": 0,
            "model_file_missing": 0,
            "model_file_digest_mismatch": 0,
            "challenger_registry_reference_mismatch": 0,
            "rolling_report_missing_or_mismatch": 0,
            "authority_mismatch": 0,
            "champion_pointer_violation": 0,
            "rollback_state_violation": 0,
            "automatic_promotion_violation": 0,
            "eligibility_epoch_violation": 0,
        }
        contract = self.memory.artifact(CONTRACT_KEY)
        if contract is None or contract["payload"] != self.contract():
            report["contract_missing_or_mismatch"] += 1

        epoch_record = self.memory.artifact(ELIGIBILITY_EPOCH_KEY)
        if epoch_record is None:
            report["eligibility_epoch_violation"] += 1
        else:
            epoch = epoch_record["payload"]
            start = self.memory.artifact(CHALLENGER_PREFIX + str(epoch.get("start_challenger_version") or ""))
            if (
                epoch.get("record_type") != "RESEARCH_CHAMPION_ELIGIBILITY_EPOCH"
                or epoch.get("authority") != AUTHORITY
                or epoch.get("automatic_promotion") is not False
                or epoch.get("execution_authority") != "NONE"
                or start is None
                or int(start["payload"]["training_cutoff_event_ms"])
                    != int(epoch.get("minimum_training_cutoff_event_ms", -1))
            ):
                report["eligibility_epoch_violation"] += 1

        models = self._model_records_by_version()
        for version, model_record in models.items():
            registry = self.memory.artifact(MODEL_REGISTRY_PREFIX + version)
            if registry is None:
                report["model_registry_reference_mismatch"] += 1
                continue
            file_info = {
                "artifact_file": self._artifact_file(version).name,
                "artifact_file_sha256": model_record["artifact_digest"],
                "artifact_file_bytes": len(_canonical_json(model_record["payload"]).encode("utf-8")),
            }
            expected = self._model_registry_payload(model_record, file_info)
            if registry["payload"] != expected:
                report["model_registry_reference_mismatch"] += 1
            if registry["payload"].get("authority") != AUTHORITY:
                report["authority_mismatch"] += 1
            path = self._artifact_file(version)
            if not path.exists():
                report["model_file_missing"] += 1
            else:
                raw = path.read_bytes()
                if _sha256_bytes(raw) != str(model_record["artifact_digest"]):
                    report["model_file_digest_mismatch"] += 1

        challengers = self.memory.list_artifacts(prefix=CHALLENGER_PREFIX)
        for challenger_record in challengers:
            expected = self._challenger_registry_payload(challenger_record)
            version = str(expected["challenger_version"])
            registry = self.memory.artifact(CHALLENGER_REGISTRY_PREFIX + version)
            if registry is None or registry["payload"] != expected:
                report["challenger_registry_reference_mismatch"] += 1
            elif registry["payload"].get("authority") != AUTHORITY:
                report["authority_mismatch"] += 1

        expected_reports = self._expected_reports()
        for expected in expected_reports:
            stored = self.memory.artifact(ROLLING_REPORT_PREFIX + str(expected["challenger_version"]))
            if stored is None or stored["payload"] != expected:
                report["rolling_report_missing_or_mismatch"] += 1
            elif stored["payload"].get("authority") != AUTHORITY:
                report["authority_mismatch"] += 1
            if stored is not None and stored["payload"].get("automatic_promotion") is not False:
                report["automatic_promotion_violation"] += 1

        genesis_pointer = self.memory.artifact(CHAMPION_POINTER_GENESIS_KEY)
        expected_pointer, expected_rollback = self._genesis_records()
        if genesis_pointer is None or genesis_pointer["payload"] != expected_pointer:
            report["champion_pointer_violation"] += 1
        genesis_rollback = self.memory.artifact(ROLLBACK_STATE_GENESIS_KEY)
        if genesis_rollback is None or genesis_rollback["payload"] != expected_rollback:
            report["rollback_state_violation"] += 1

        pointer = self._latest_generation_payload(CHAMPION_POINTER_PREFIX, CHAMPION_POINTER_GENESIS_KEY)
        if pointer is not None and int(pointer.get("generation", 0)) > 0:
            champion = str(pointer.get("current_research_champion") or "")
            if (
                not champion
                or self.memory.artifact(MODEL_REGISTRY_PREFIX + champion) is None
                or pointer.get("authority") != AUTHORITY
                or pointer.get("automatic_promotion") is not False
                or pointer.get("paper_champion_authority") is not False
                or pointer.get("execution_authority") != "NONE"
            ):
                report["champion_pointer_violation"] += 1

        rollback = self._latest_generation_payload(ROLLBACK_STATE_PREFIX, ROLLBACK_STATE_GENESIS_KEY)
        if rollback is not None and int(rollback.get("generation", 0)) > 0:
            if (
                rollback.get("authority") != AUTHORITY
                or rollback.get("automatic_rollback") is not False
                or rollback.get("execution_authority") != "NONE"
            ):
                report["rollback_state_violation"] += 1

        report["healthy"] = all(
            int(value) == 0
            for key, value in report.items()
            if key not in {"registry_version", "rolling_version", "authority", "healthy"}
        )
        return report
