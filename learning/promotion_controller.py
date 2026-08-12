"""Automatic, fail-closed shadow promotion governance for Phase 5.10."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from learning.model_artifact_scorer import (
    RegisteredModelArtifactScorer,
    RegisteredModelScoringError,
)
from learning.model_registry import ModelRegistry, ModelRegistryError
from learning.shadow_decision_testing import ShadowDecisionEvaluator


PROMOTION_CONTROLLER_SCHEMA_VERSION = 2

class PromotionControllerError(RuntimeError):
    pass


class PromotionControllerAlreadyRunning(PromotionControllerError):
    pass


class PromotionControllerProcessLock:
    """Non-blocking process lock independent of the trading engine."""

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
            raise PromotionControllerAlreadyRunning(
                f"PROMOTION_CONTROLLER_ALREADY_RUNNING | path={self.path}"
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


class AutomaticPromotionController:
    """Evaluate one registered shadow challenger and apply one atomic verdict.

    The controller owns registry lifecycle transitions only. It does not route
    candidates, place paper orders, replace the champion, or create any real
    exchange authority.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        environment: str,
        decisions_path: str,
        outcomes_path: str,
        evidence_report_path: str,
        registry_path: str,
        status_path: str,
        lock_path: str,
        default_champion_model_id: str,
        outcome_type: str,
        min_matched_outcomes: int,
        min_independent_events: int,
        min_disagreement_events: int,
        min_average_r_lift: float,
        min_after_cost_expectancy: float,
        max_win_rate_deterioration: float,
        max_brier_score: float,
        max_calibration_gap: float,
        max_feature_psi: float,
        min_recent_expectancy: float,
        recent_event_window: int,
        extend_evidence_ratio: float,
        phase7_strict_evidence: bool = False,
        min_regime_events: int = 1,
        min_distinct_market_regimes: int = 1,
        min_regime_average_r_lift: float = -5.0,
        min_regime_after_cost_expectancy: float = -5.0,
    ):
        self.enabled = bool(enabled)
        self.environment = str(environment or "").strip().upper()
        self.decisions_path = Path(decisions_path)
        self.outcomes_path = Path(outcomes_path)
        self.evidence_report_path = Path(evidence_report_path)
        self.status_path = Path(status_path)
        self.outcome_type = str(outcome_type or "").strip().upper()
        self.default_champion_model_id = str(
            default_champion_model_id or ""
        ).strip()
        self.min_matched_outcomes = int(min_matched_outcomes)
        self.min_independent_events = int(min_independent_events)
        self.min_disagreement_events = int(min_disagreement_events)
        self.min_average_r_lift = float(min_average_r_lift)
        self.min_after_cost_expectancy = float(
            min_after_cost_expectancy
        )
        self.max_win_rate_deterioration = float(
            max_win_rate_deterioration
        )
        self.max_brier_score = float(max_brier_score)
        self.max_calibration_gap = float(max_calibration_gap)
        self.max_feature_psi = float(max_feature_psi)
        self.min_recent_expectancy = float(min_recent_expectancy)
        self.recent_event_window = int(recent_event_window)
        self.extend_evidence_ratio = float(extend_evidence_ratio)
        self.phase7_strict_evidence = bool(phase7_strict_evidence)
        self.min_regime_events = max(1, int(min_regime_events))
        self.min_distinct_market_regimes = max(
            1, int(min_distinct_market_regimes)
        )
        self.min_regime_average_r_lift = float(
            min_regime_average_r_lift
        )
        self.min_regime_after_cost_expectancy = float(
            min_regime_after_cost_expectancy
        )
        if self.phase7_strict_evidence:
            if self.min_regime_events > self.min_independent_events:
                raise ValueError(
                    "PROMOTION_CONTROLLER_REGIME_EVENTS_INVALID"
                )
            if not (1 <= self.min_distinct_market_regimes <= 3):
                raise ValueError(
                    "PROMOTION_CONTROLLER_DISTINCT_REGIMES_INVALID"
                )
        if not self.environment:
            raise ValueError("PROMOTION_CONTROLLER_ENVIRONMENT_REQUIRED")
        if not self.default_champion_model_id:
            raise ValueError("PROMOTION_CONTROLLER_CHAMPION_REQUIRED")
        self.registry = ModelRegistry(
            path=registry_path,
            environment=self.environment,
            default_champion_model_id=self.default_champion_model_id,
        )
        self.lock = PromotionControllerProcessLock(lock_path)

    def run_once(self) -> dict:
        if not self.enabled:
            return self._status(
                "DISABLED",
                promotion_outcome="HOLD",
                reason_codes=["AUTOMATIC_PROMOTION_ENABLED_FALSE"],
            )
        try:
            with self.lock:
                return self._run_locked()
        except PromotionControllerAlreadyRunning as exc:
            return self._status(
                "SKIPPED_ALREADY_RUNNING",
                promotion_outcome="HOLD",
                reason_codes=[str(exc)],
            )

    def _run_locked(self) -> dict:
        self.registry.initialize()
        registry_document = self.registry.load()
        challenger_model_id = registry_document.get(
            "current_shadow_model_id"
        )
        if not challenger_model_id:
            return self._status(
                "WAITING_FOR_SHADOW_CHALLENGER",
                promotion_outcome="HOLD",
                reason_codes=["NO_CURRENT_SHADOW_MODEL"],
                current_champion_model_id=registry_document.get(
                    "current_champion_model_id"
                ),
            )

        challenger_model_id = str(challenger_model_id)
        record = registry_document.get("models", {}).get(
            challenger_model_id
        )
        if not isinstance(record, dict) or record.get("status") != "SHADOW":
            raise PromotionControllerError(
                "PROMOTION_SHADOW_REGISTRY_STATE_INVALID | "
                f"model_id={challenger_model_id}"
            )
        champion_model_id = str(
            registry_document.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        if (
            self.phase7_strict_evidence
            and not self.registry.phase7_shadow_eligible(record)
        ):
            return self._status(
                "WAITING_FOR_PHASE7_CHALLENGER",
                model_id=challenger_model_id,
                champion_model_id=champion_model_id,
                promotion_outcome="HOLD",
                reason_codes=[
                    "CURRENT_SHADOW_NOT_PHASE7_VALIDATION_ELIGIBLE"
                ],
                registry_changed=False,
            )

        evidence_report = ShadowDecisionEvaluator(
            decisions_path=str(self.decisions_path),
            outcomes_path=str(self.outcomes_path),
            report_path=str(self.evidence_report_path),
            outcome_type=self.outcome_type,
            challenger_model_id=challenger_model_id,
            champion_model_id=champion_model_id,
            recent_event_window=self.recent_event_window,
            require_complete_market_context=self.phase7_strict_evidence,
            require_complete_cost_evidence=self.phase7_strict_evidence,
        ).evaluate()
        evidence = self._evidence(evidence_report, record)
        gate_report = self._gates(evidence)
        promotion_outcome, reason_codes = self._decide(gate_report)
        if (
            promotion_outcome == "PROMOTE_TO_PAPER_CANARY"
            and record.get("paper_promotion_allowed") is False
        ):
            promotion_outcome = "EXTEND_SHADOW"
            reason_codes = ["PHASE7_PAPER_PROMOTION_LOCKED"]

        previous_evaluation = record.get("promotion_evaluation") or {}
        no_new_evidence = (
            promotion_outcome in {"HOLD", "EXTEND_SHADOW"}
            and previous_evaluation.get("matched_candidate_outcomes")
            == evidence["matched_candidate_outcomes"]
            and previous_evaluation.get("independent_decision_events")
            == evidence["independent_decision_events"]
            and previous_evaluation.get("paired_disagreement_events")
            == evidence["paired_disagreement_events"]
        )
        if no_new_evidence:
            return self._status(
                "NO_NEW_COMPLETED_EVIDENCE",
                model_id=challenger_model_id,
                champion_model_id=champion_model_id,
                promotion_outcome=promotion_outcome,
                reason_codes=reason_codes,
                evidence=evidence,
                gates=gate_report,
                registry_changed=False,
            )

        canary_id = registry_document.get("current_paper_canary_model_id")
        if (
            promotion_outcome == "PROMOTE_TO_PAPER_CANARY"
            and canary_id
            and str(canary_id) != challenger_model_id
        ):
            promotion_outcome = "HOLD"
            reason_codes = ["PAPER_CANARY_SLOT_OCCUPIED"]

        updated = self.registry.apply_promotion_decision(
            challenger_model_id,
            decision=promotion_outcome,
            evidence=evidence,
            gate_report=gate_report,
            reason_codes=reason_codes,
        )
        return self._status(
            "EVALUATED",
            model_id=challenger_model_id,
            champion_model_id=champion_model_id,
            promotion_outcome=promotion_outcome,
            reason_codes=reason_codes,
            evidence=evidence,
            gates=gate_report,
            registry_model_status=updated["status"],
            registry_changed=True,
            paper_canary_slot=(
                self.registry.current_paper_canary_model_id()
            ),
        )

    def _evidence(self, report: dict, record: dict) -> dict:
        challenger = report["policies"]["CHALLENGER"]["TOP_ONE"][
            "summary"
        ]
        comparison = report["pairwise"][
            "CHALLENGER_VS_CHAMPION"
        ]["TOP_ONE"]
        brier_score = self._number(
            (record.get("test_metrics") or {}).get("brier_score")
        )
        calibration_gap = self._number(
            (record.get("calibration_metrics") or {}).get(
                "test_max_abs_gap"
            )
        )
        feature_psi = self._number(
            (record.get("drift_metrics") or {}).get(
                "max_feature_psi"
            )
        )
        artifact_validation = self._validate_artifact(record)
        regime_robustness = self._regime_robustness(
            comparison,
            report["policies"]["CHALLENGER"]["TOP_ONE"].get(
                "regimes"
            )
            or {},
        )
        challenger_win_rate = self._number(
            comparison.get("left_win_rate")
        )
        champion_win_rate = self._number(
            comparison.get("right_win_rate")
        )
        win_rate_deterioration = (
            None
            if challenger_win_rate is None or champion_win_rate is None
            else champion_win_rate - challenger_win_rate
        )
        return {
            "model_id": record.get("model_id"),
            "parent_model_id": record.get("parent_model_id"),
            "dataset_fingerprint": record.get("dataset_fingerprint"),
            "matched_candidate_outcomes": int(
                comparison.get("raw_completed_pairs", 0) or 0
            ),
            "independent_decision_events": int(
                comparison.get("independent_market_event_pairs", 0) or 0
            ),
            "paired_disagreement_events": int(
                comparison.get("disagreement_events", 0) or 0
            ),
            "average_r_lift_over_champion": self._number(
                comparison.get("left_minus_right_average_net_r")
            ),
            "after_cost_expectancy": self._number(
                challenger.get("average_net_r")
            ),
            "challenger_win_rate": challenger_win_rate,
            "champion_win_rate": champion_win_rate,
            "win_rate_deterioration": win_rate_deterioration,
            "brier_score": brier_score,
            "calibration_gap": calibration_gap,
            "maximum_feature_psi": feature_psi,
            "recent_period_expectancy": self._number(
                challenger.get("recent_average_net_r")
            ),
            "recent_event_count": int(
                challenger.get("recent_event_count", 0) or 0
            ),
            "recent_event_window": self.recent_event_window,
            "artifact_validation": artifact_validation,
            "regime_robustness": regime_robustness,
            "evidence_basis": "INDEPENDENT_MARKET_EVENTS_PRIMARY",
            "return_basis": (
                "NET_AFTER_COMPLETE_PHASE7_3_COSTS"
                if self.phase7_strict_evidence
                else "NET_AFTER_ESTIMATED_COSTS"
            ),
            "market_context_basis": (
                "COMPLETE_PHASE7_1_REQUIRED"
                if self.phase7_strict_evidence
                else "LEGACY_COMPATIBLE"
            ),
        }

    def _regime_robustness(
        self, comparison: dict, challenger_regimes: dict
    ) -> dict:
        report = {}
        all_regimes = comparison.get("regimes") or {}
        for dimension in (
            "market_regime",
            "volatility_regime",
            "btc_regime",
        ):
            groups = all_regimes.get(dimension) or {}
            normalized = {}
            eligible = []
            for name, metrics in sorted(groups.items()):
                if not isinstance(metrics, dict):
                    continue
                event_count = int(
                    metrics.get("independent_market_event_pairs", 0) or 0
                )
                challenger_group = (
                    (challenger_regimes.get(dimension) or {}).get(name)
                    or {}
                )
                item = {
                    "independent_market_events": event_count,
                    "challenger_average_net_r": self._number(
                        challenger_group.get("average_net_r")
                    ),
                    "champion_average_net_r": self._number(
                        metrics.get("right_average_net_r")
                    ),
                    "average_r_lift_over_champion": self._number(
                        metrics.get("left_minus_right_average_net_r")
                    ),
                    "challenger_win_rate": self._number(
                        metrics.get("left_win_rate")
                    ),
                    "champion_win_rate": self._number(
                        metrics.get("right_win_rate")
                    ),
                    "disagreement_events": int(
                        metrics.get("disagreement_events", 0) or 0
                    ),
                    "comparison_basis": metrics.get("comparison_basis"),
                    "eligible": (
                        name not in {"MIXED", "NOT_AVAILABLE"}
                        and event_count >= self.min_regime_events
                    ),
                }
                normalized[str(name)] = item
                if item["eligible"]:
                    eligible.append(item)
            lifts = [
                item["average_r_lift_over_champion"]
                for item in eligible
                if item["average_r_lift_over_champion"] is not None
            ]
            expectancies = [
                item["challenger_average_net_r"]
                for item in eligible
                if item["challenger_average_net_r"] is not None
            ]
            report[dimension] = {
                "minimum_events_per_group": self.min_regime_events,
                "observed_group_count": len(normalized),
                "eligible_group_count": len(eligible),
                "minimum_r_lift": min(lifts) if lifts else None,
                "minimum_challenger_expectancy": (
                    min(expectancies) if expectancies else None
                ),
                "groups": normalized,
            }
        return report

    def _gates(self, evidence: dict) -> dict:
        checks = {
            "matched_candidate_outcomes": self._minimum_gate(
                evidence["matched_candidate_outcomes"],
                self.min_matched_outcomes,
            ),
            "independent_decision_events": self._minimum_gate(
                evidence["independent_decision_events"],
                self.min_independent_events,
            ),
            "paired_disagreement_events": self._minimum_gate(
                evidence["paired_disagreement_events"],
                self.min_disagreement_events,
            ),
            "average_r_lift_over_champion": self._minimum_gate(
                evidence["average_r_lift_over_champion"],
                self.min_average_r_lift,
            ),
            "after_cost_expectancy": self._strict_minimum_gate(
                evidence["after_cost_expectancy"],
                self.min_after_cost_expectancy,
            ),
            "win_rate_deterioration": self._maximum_gate(
                evidence["win_rate_deterioration"],
                self.max_win_rate_deterioration,
            ),
            "brier_score": self._maximum_gate(
                evidence["brier_score"],
                self.max_brier_score,
            ),
            "calibration_gap": self._maximum_gate(
                evidence["calibration_gap"],
                self.max_calibration_gap,
            ),
            "maximum_feature_psi": self._maximum_gate(
                evidence["maximum_feature_psi"],
                self.max_feature_psi,
            ),
            "recent_period_expectancy": self._strict_minimum_gate(
                evidence["recent_period_expectancy"],
                self.min_recent_expectancy,
            ),
            "artifact_integrity": {
                "actual": evidence["artifact_validation"]["status"],
                "required": "VALID",
                "passed": evidence["artifact_validation"]["valid"],
            },
        }
        if self.phase7_strict_evidence:
            market_regime = evidence["regime_robustness"][
                "market_regime"
            ]
            checks.update({
                "market_regime_coverage": self._minimum_gate(
                    market_regime["eligible_group_count"],
                    self.min_distinct_market_regimes,
                ),
                "market_regime_min_r_lift": self._minimum_gate(
                    market_regime["minimum_r_lift"],
                    self.min_regime_average_r_lift,
                ),
                "market_regime_min_after_cost_expectancy": (
                    self._strict_minimum_gate(
                        market_regime["minimum_challenger_expectancy"],
                        self.min_regime_after_cost_expectancy,
                    )
                ),
            })
        count_names = (
            "matched_candidate_outcomes",
            "independent_decision_events",
            "paired_disagreement_events",
            *(
                ("market_regime_coverage",)
                if self.phase7_strict_evidence
                else ()
            ),
        )
        performance_names = (
            "average_r_lift_over_champion",
            "after_cost_expectancy",
            "win_rate_deterioration",
            "recent_period_expectancy",
            *(
                (
                    "market_regime_min_r_lift",
                    "market_regime_min_after_cost_expectancy",
                )
                if self.phase7_strict_evidence
                else ()
            ),
        )
        hard_safety_names = (
            "brier_score",
            "calibration_gap",
            "maximum_feature_psi",
            "artifact_integrity",
        )
        return {
            "checks": checks,
            "count_gates_passed": all(
                checks[name]["passed"] for name in count_names
            ),
            "performance_gates_passed": all(
                checks[name]["passed"] for name in performance_names
            ),
            "hard_safety_gates_passed": all(
                checks[name]["passed"] for name in hard_safety_names
            ),
            "all_gates_passed": all(
                item["passed"] for item in checks.values()
            ),
            "promotion_basis": (
                "INDEPENDENT_MARKET_EVENTS_AND_REGIME_ROBUSTNESS"
                if self.phase7_strict_evidence
                else "INDEPENDENT_MARKET_EVENTS_PRIMARY"
            ),
        }

    def _decide(self, gate_report: dict) -> tuple[str, list[str]]:
        checks = gate_report["checks"]
        failed = [
            name for name, item in checks.items() if not item["passed"]
        ]
        if not gate_report["hard_safety_gates_passed"]:
            return "REJECT", [
                "HARD_SAFETY_GATE_FAILED:" + name
                for name in failed
                if name in {
                    "brier_score",
                    "calibration_gap",
                    "maximum_feature_psi",
                    "artifact_integrity",
                }
            ]

        if gate_report["count_gates_passed"]:
            if gate_report["all_gates_passed"]:
                return "PROMOTE_TO_PAPER_CANARY", [
                    "ALL_FORWARD_AND_MODEL_QUALITY_GATES_PASSED"
                ]
            clearly_worse = []
            lift = checks["average_r_lift_over_champion"]["actual"]
            expectancy = checks["after_cost_expectancy"]["actual"]
            recent = checks["recent_period_expectancy"]["actual"]
            win_drop = checks["win_rate_deterioration"]["actual"]
            if lift is None or lift < 0:
                clearly_worse.append("NEGATIVE_R_LIFT")
            if expectancy is None or expectancy <= self.min_after_cost_expectancy:
                clearly_worse.append("NON_POSITIVE_AFTER_COST_EXPECTANCY")
            if recent is None or recent <= self.min_recent_expectancy:
                clearly_worse.append("NON_POSITIVE_RECENT_EXPECTANCY")
            if (
                win_drop is None
                or win_drop > self.max_win_rate_deterioration
            ):
                clearly_worse.append("WIN_RATE_DETERIORATION_EXCEEDED")
            if self.phase7_strict_evidence:
                regime_lift = checks["market_regime_min_r_lift"][
                    "actual"
                ]
                regime_expectancy = checks[
                    "market_regime_min_after_cost_expectancy"
                ]["actual"]
                if (
                    regime_lift is None
                    or regime_lift < self.min_regime_average_r_lift
                ):
                    clearly_worse.append(
                        "SUPPORTED_REGIME_R_LIFT_BELOW_MINIMUM"
                    )
                if (
                    regime_expectancy is None
                    or regime_expectancy
                    <= self.min_regime_after_cost_expectancy
                ):
                    clearly_worse.append(
                        "SUPPORTED_REGIME_EXPECTANCY_NOT_POSITIVE"
                    )
            if clearly_worse:
                return "REJECT", clearly_worse
            return "EXTEND_SHADOW", [
                "POSITIVE_BUT_PROMOTION_THRESHOLD_NOT_YET_PASSED:" + name
                for name in failed
            ]

        progress = self._count_progress(checks)
        early_promising = self._early_performance_promising(checks)
        if progress >= self.extend_evidence_ratio and early_promising:
            return "EXTEND_SHADOW", [
                "PROMISING_EARLY_FORWARD_EVIDENCE",
                "MINIMUM_INDEPENDENT_EVIDENCE_NOT_YET_COMPLETE",
            ]
        return "HOLD", [
            "INSUFFICIENT_INDEPENDENT_FORWARD_EVIDENCE"
        ]

    def _validate_artifact(self, record: dict) -> dict:
        model_id = str(record.get("model_id") or "").strip()
        artifact_path = str(record.get("artifact_path") or "").strip()
        checksum = str(
            record.get("artifact_checksum_sha256") or ""
        ).strip().lower()
        try:
            RegisteredModelArtifactScorer(
                model_id=model_id,
                artifact_path=artifact_path,
                expected_checksum_sha256=checksum or None,
            )
            return {
                "valid": True,
                "status": "VALID",
                "artifact_path": artifact_path,
                "checksum_sha256": checksum,
            }
        except (RegisteredModelScoringError, ValueError) as exc:
            return {
                "valid": False,
                "status": f"{type(exc).__name__}:{exc}",
                "artifact_path": artifact_path,
                "checksum_sha256": checksum,
            }

    @staticmethod
    def _minimum_gate(actual: Any, required: float) -> dict:
        number = AutomaticPromotionController._number(actual)
        return {
            "actual": number,
            "required_min": required,
            "passed": number is not None and number >= required,
        }

    @staticmethod
    def _strict_minimum_gate(actual: Any, required: float) -> dict:
        number = AutomaticPromotionController._number(actual)
        return {
            "actual": number,
            "required_strictly_greater_than": required,
            "passed": number is not None and number > required,
        }

    @staticmethod
    def _maximum_gate(actual: Any, required: float) -> dict:
        number = AutomaticPromotionController._number(actual)
        return {
            "actual": number,
            "required_max": required,
            "passed": number is not None and number <= required,
        }

    def _count_progress(self, checks: dict) -> float:
        values = []
        names = [
            "matched_candidate_outcomes",
            "independent_decision_events",
            "paired_disagreement_events",
        ]
        if self.phase7_strict_evidence:
            names.append("market_regime_coverage")
        for name in names:
            actual = float(checks[name]["actual"] or 0.0)
            required = float(checks[name]["required_min"])
            values.append(min(1.0, actual / required))
        return min(values, default=0.0)

    def _early_performance_promising(self, checks: dict) -> bool:
        lift = checks["average_r_lift_over_champion"]["actual"]
        expectancy = checks["after_cost_expectancy"]["actual"]
        recent = checks["recent_period_expectancy"]["actual"]
        win_drop = checks["win_rate_deterioration"]["actual"]
        promising = (
            lift is not None
            and lift >= 0
            and expectancy is not None
            and expectancy > self.min_after_cost_expectancy
            and recent is not None
            and recent > self.min_recent_expectancy
            and win_drop is not None
            and win_drop <= self.max_win_rate_deterioration
        )
        if not promising or not self.phase7_strict_evidence:
            return promising
        regime_coverage = checks.get("market_regime_coverage", {}).get(
            "actual"
        )
        regime_lift = checks.get("market_regime_min_r_lift", {}).get(
            "actual"
        )
        regime_expectancy = checks.get(
            "market_regime_min_after_cost_expectancy", {}
        ).get("actual")
        return (
            regime_coverage is None
            or regime_coverage < self.min_distinct_market_regimes
            or (
                regime_lift is not None
                and regime_lift >= self.min_regime_average_r_lift
                and regime_expectancy is not None
                and regime_expectancy
                > self.min_regime_after_cost_expectancy
            )
        )

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number or number in {float("inf"), float("-inf")}:
            return None
        return number

    def _status(self, status: str, **details) -> dict:
        document = {
            "schema_version": PROMOTION_CONTROLLER_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "phase": (
                "7.5" if self.phase7_strict_evidence else "5.10"
            ),
            "status": status,
            "environment": self.environment,
            "process_id": os.getpid(),
            "runtime_process": "SEPARATE_FROM_TRADING_ENGINE",
            "champion_changed": False,
            "paper_order_routing_changed": False,
            "real_order_authority": "NONE",
            **details,
        }
        self._write_json_atomic(self.status_path, document)
        return document

    @staticmethod
    def _write_json_atomic(path: Path, document: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
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
