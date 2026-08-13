"""Unified read-only operator status for the autonomous learning loop.

Phase 5.13 consolidates existing atomic registry and governance reports into one
atomic JSON document.  It does not train, score, promote, route, roll back, or
submit orders.  Missing source files are represented explicitly rather than
silently replaced with invented values.
"""

from __future__ import annotations

import html
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from learning.training_orchestrator import TrainingInventory


AUTO_LEARNING_STATUS_SCHEMA_VERSION = 1


_REASON_TEXT = {
    "NO_CURRENT_SHADOW_MODEL": "No shadow challenger is currently registered.",
    "NO_CURRENT_PAPER_CANARY_MODEL": "No model is currently in a paper-canary stage.",
    "AUTOMATIC_PROMOTION_ENABLED_FALSE": "Automatic shadow promotion is disabled.",
    "PAPER_CANARY_CONTROLLER_ENABLED_FALSE": "Automatic paper-canary governance is disabled.",
    "COLLECTING_INDEPENDENT_STAGE_EVIDENCE": "The canary is collecting independent forward evidence for its next stage.",
    "INDEPENDENT_STAGE_EVIDENCE_GATES_PASSED": "The independent evidence gates for the next paper stage passed.",
    "PAPER_CANARY_SLOT_OCCUPIED": "Another model already occupies the paper-canary slot.",
    "MATERIAL_CHAMPION_UNDERPERFORMANCE": "The model materially underperformed its champion benchmark.",
    "MAXIMUM_DRAWDOWN_BREACH": "The model exceeded the allowed paper drawdown.",
    "LOSING_STREAK_BREACH": "The model exceeded the allowed losing streak.",
    "AVERAGE_EXPECTANCY_BREACH": "The model's after-cost paper expectancy fell below its safety limit.",
    "RECENT_EXPECTANCY_BREACH": "The model's recent after-cost expectancy fell below its safety limit.",
    "BRIER_SCORE_DETERIORATION": "Forward probability calibration deteriorated beyond the allowed Brier score.",
    "CALIBRATION_GAP_DETERIORATION": "Forward calibration gap exceeded its safety limit.",
    "FEATURE_DRIFT_PSI_BREACH": "Fresh feature drift exceeded the allowed PSI limit.",
    "MODEL_ARTIFACT_UNAVAILABLE": "The registered model artifact could not be loaded safely.",
    "REQUIRED_FEATURE_MISSING": "A required model feature was missing.",
    "FEATURE_SCHEMA_MISMATCH": "The runtime, registry, and artifact feature schemas did not match.",
    "PREDICTION_FAILURE_THRESHOLD_BREACH": "Runtime prediction failures exceeded the allowed threshold.",
    "WAITING_FOR_DATA": "The next training cycle is waiting for materially new completed outcomes and independent events.",
    "INSUFFICIENT_INDEPENDENT_FORWARD_EVIDENCE": "More independent forward comparisons are required before promotion can be considered.",
    "PROMISING_EARLY_FORWARD_EVIDENCE": "Early forward evidence is promising, but the minimum independent evidence is not complete.",
    "MINIMUM_INDEPENDENT_EVIDENCE_NOT_YET_COMPLETE": "The minimum independent forward-evidence gate has not yet completed.",
    "ALL_FORWARD_AND_MODEL_QUALITY_GATES_PASSED": "All forward-performance and model-quality gates passed.",
    "NEGATIVE_R_LIFT": "The challenger did not outperform the current champion.",
    "NON_POSITIVE_AFTER_COST_EXPECTANCY": "The challenger has non-positive after-cost expectancy.",
    "NON_POSITIVE_RECENT_EXPECTANCY": "The challenger's recent after-cost expectancy is non-positive.",
    "WIN_RATE_DETERIORATION_EXCEEDED": "The challenger win rate deteriorated beyond the allowed limit.",
    "NO_ACTIVE_CHALLENGER": "No eligible challenger exists yet; the rule system remains the paper champion.",
    "PHASE7_PAPER_PROMOTION_LOCKED": "The challenger passed the Phase-7 forward gates, but paper authority remains locked until Phase 8.",
    "CURRENT_SHADOW_NOT_PHASE7_VALIDATION_ELIGIBLE": "The current shadow model does not satisfy the strict Phase-7 validation contract.",
    "SUPPORTED_REGIME_R_LIFT_BELOW_MINIMUM": "The challenger did not beat the champion in every sufficiently represented market regime.",
    "SUPPORTED_REGIME_EXPECTANCY_NOT_POSITIVE": "The challenger was not profitable after costs in every sufficiently represented market regime.",
}


class AutoLearningStatusPublisher:
    """Build one operator-facing status from existing append-only evidence."""

    def __init__(
        self,
        *,
        environment: str,
        execution_mode: str,
        default_champion_model_id: str,
        status_path: str,
        registry_path: str,
        observations_path: str,
        outcomes_path: str,
        training_outcome_type: str,
        auto_training_status_path: str,
        promotion_status_path: str,
        promotion_evidence_path: str,
        paper_canary_status_path: str,
        strategy_policy_path: str,
        source_stale_seconds: int = 1800,
    ):
        self.environment = str(environment or "").strip().upper()
        self.execution_mode = str(execution_mode or "").strip().upper()
        self.default_champion_model_id = str(
            default_champion_model_id or "RULE_SYSTEM_V1"
        ).strip()
        self.status_path = Path(status_path)
        self.registry_path = Path(registry_path)
        self.observations_path = Path(observations_path)
        self.outcomes_path = Path(outcomes_path)
        self.training_outcome_type = str(
            training_outcome_type or "VIRTUAL_TRADE"
        ).strip().upper()
        self.auto_training_status_path = Path(auto_training_status_path)
        self.promotion_status_path = Path(promotion_status_path)
        self.promotion_evidence_path = Path(promotion_evidence_path)
        self.paper_canary_status_path = Path(paper_canary_status_path)
        self.strategy_policy_path = Path(strategy_policy_path)
        self.source_stale_seconds = int(source_stale_seconds)
        if not self.environment:
            raise ValueError("AUTO_LEARNING_STATUS_ENVIRONMENT_REQUIRED")
        if not self.default_champion_model_id:
            raise ValueError("AUTO_LEARNING_STATUS_CHAMPION_REQUIRED")
        if not str(self.status_path):
            raise ValueError("AUTO_LEARNING_STATUS_PATH_REQUIRED")
        if self.source_stale_seconds < 60:
            raise ValueError("AUTO_LEARNING_STATUS_STALE_SECONDS_INVALID")

    def refresh(self) -> dict:
        now_ms = int(time.time() * 1000)
        registry, registry_source = self._read_json_source(
            self.registry_path, "model_registry", now_ms
        )
        training, training_source = self._read_json_source(
            self.auto_training_status_path, "auto_training", now_ms
        )
        promotion, promotion_source = self._read_json_source(
            self.promotion_status_path, "promotion_controller", now_ms
        )
        promotion_evidence, promotion_evidence_source = self._read_json_source(
            self.promotion_evidence_path, "promotion_evidence", now_ms
        )
        canary, canary_source = self._read_json_source(
            self.paper_canary_status_path, "paper_governance", now_ms
        )
        strategy_policy, strategy_source = self._read_json_source(
            self.strategy_policy_path, "strategy_policy", now_ms
        )

        models = registry.get("models") if isinstance(registry, dict) else {}
        if not isinstance(models, dict):
            models = {}
        champion_id = str(
            registry.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        previous_champion_id = registry.get("previous_champion_model_id")
        canary_id = registry.get("current_paper_canary_model_id")
        shadow_id = registry.get("current_shadow_model_id")
        latest_id = registry.get("latest_model_id")
        challenger_id = self._challenger_id(
            champion_id=champion_id,
            canary_id=canary_id,
            shadow_id=shadow_id,
            latest_id=latest_id,
            models=models,
        )
        challenger_record = (
            models.get(str(challenger_id))
            if challenger_id is not None
            else None
        )
        if not isinstance(challenger_record, dict):
            challenger_record = {}
        stage = self._stage(
            challenger_id=challenger_id,
            canary_id=canary_id,
            shadow_id=shadow_id,
            record=challenger_record,
        )

        status_inventory = training.get("inventory")
        if not isinstance(status_inventory, dict):
            status_inventory = {}
        training_thresholds = training.get("thresholds")
        if not isinstance(training_thresholds, dict):
            training_thresholds = {}
        cohort_readiness = training.get("cohort_readiness")
        if not isinstance(cohort_readiness, dict):
            cohort_readiness = {}

        if (
            "new_completed_outcomes" in status_inventory
            and "new_independent_market_events" in status_inventory
        ):
            # Phase 7.5A: prefer the automatic trainer's own qualified
            # cohort/cutoff.  This is the exact gate the trainer will use and
            # avoids rescanning large history files for every /learning call.
            inventory = status_inventory
            completed_outcomes = int(
                inventory.get("new_completed_outcomes", 0) or 0
            )
            independent_events = int(
                inventory.get("new_independent_market_events", 0) or 0
            )
            training_count_basis = "AUTO_TRAINING_QUALIFIED_COHORT"
        else:
            inventory = TrainingInventory(
                observations_path=str(self.observations_path),
                outcomes_path=str(self.outcomes_path),
                outcome_type=self.training_outcome_type,
            ).scan(after_ms=0)
            training_rows = self._int_or_none(
                challenger_record.get("training_rows")
            )
            training_events = self._int_or_none(
                challenger_record.get("independent_event_count")
            )
            completed_outcomes = max(
                int(inventory.get("new_completed_outcomes", 0) or 0),
                training_rows or 0,
            )
            independent_events = max(
                int(inventory.get("new_independent_market_events", 0) or 0),
                training_events or 0,
            )
            training_count_basis = "FALLBACK_HISTORY_SCAN"

        required_outcomes = int(
            training_thresholds.get("min_new_outcomes", 0) or 0
        )
        required_events = int(
            training_thresholds.get("min_new_market_events", 0) or 0
        )

        evidence = self._select_evidence(
            challenger_id=challenger_id,
            promotion=promotion,
            promotion_evidence=promotion_evidence,
            canary=canary,
        )
        forward = self._forward_metrics(evidence, canary)
        promotion_thresholds = promotion.get("thresholds")
        if not isinstance(promotion_thresholds, dict):
            promotion_thresholds = {}
        gates = promotion.get("gates")
        checks = gates.get("checks") if isinstance(gates, dict) else {}
        if not isinstance(checks, dict):
            checks = {}

        def _required(check_name: str, threshold_name: str) -> int:
            check = checks.get(check_name)
            if isinstance(check, dict):
                value = self._int_or_none(check.get("required_min"))
                if value is not None:
                    return value
            return int(promotion_thresholds.get(threshold_name, 0) or 0)

        forward["status"] = promotion.get("status") or "NOT_AVAILABLE"
        forward["matched_required"] = _required(
            "matched_candidate_outcomes", "min_matched_outcomes"
        )
        forward["independent_required"] = _required(
            "independent_decision_events", "min_independent_events"
        )
        forward["disagreement_required"] = _required(
            "paired_disagreement_events", "min_disagreement_events"
        )
        regime = evidence.get("regime_robustness")
        market_regime = (
            regime.get("market_regime")
            if isinstance(regime, dict)
            else {}
        )
        if not isinstance(market_regime, dict):
            market_regime = {}
        forward["market_regimes_eligible"] = int(
            market_regime.get("eligible_group_count", 0) or 0
        )
        forward["market_regimes_required"] = _required(
            "market_regime_coverage", "min_distinct_market_regimes"
        )
        forward["minimum_events_per_regime"] = int(
            promotion_thresholds.get("min_regime_events", 0) or 0
        )
        forward["all_gates_passed"] = bool(
            gates.get("all_gates_passed", False)
        ) if isinstance(gates, dict) else False

        verdict, reason_codes = self._verdict(
            challenger_id=challenger_id,
            stage=stage,
            promotion=promotion,
            canary=canary,
            training=training,
            record=challenger_record,
        )
        reason = self._plain_reason(reason_codes, verdict)
        next_action = self._next_action(
            stage=stage,
            verdict=verdict,
            training=training,
            promotion=promotion,
            canary=canary,
            challenger_id=challenger_id,
        )

        authority = registry.get("authority")
        if not isinstance(authority, dict):
            authority = {}
        paper_activation = self._paper_activation(stage, champion_id)
        paper_routing = str(
            authority.get("paper_activation") or paper_activation
        )
        shadow_safe = self.execution_mode == "SHADOW"
        phase6_ready = self.environment == "LIVE" and shadow_safe
        sources = {
            item["name"]: item
            for item in (
                registry_source,
                training_source,
                promotion_source,
                promotion_evidence_source,
                canary_source,
                strategy_source,
            )
        }
        source_warnings = [
            name
            for name, source in sources.items()
            if source["status"] in {"MISSING", "INVALID", "STALE"}
        ]

        document = {
            "schema_version": AUTO_LEARNING_STATUS_SCHEMA_VERSION,
            "generated_at_ms": now_ms,
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "mission": "AUTONOMOUS_SELF_LEARNING_BINANCE_FUTURES_PAPER_SYSTEM",
            "current_paper_champion": champion_id,
            "previous_paper_champion": previous_champion_id,
            "current_challenger": challenger_id,
            "challenger_stage": stage,
            "training_data": {
                "phase": training.get("phase") or "UNKNOWN",
                "status": training.get("status") or "NOT_AVAILABLE",
                "completed_outcomes": completed_outcomes,
                "required_outcomes": required_outcomes,
                "remaining_outcomes": max(
                    0, required_outcomes - completed_outcomes
                ),
                "independent_market_events": independent_events,
                "required_independent_market_events": required_events,
                "remaining_independent_market_events": max(
                    0, required_events - independent_events
                ),
                "outcome_type": self.training_outcome_type,
                "count_basis": training_count_basis,
                "inventory_issue_count": int(
                    inventory.get("issue_count", 0) or 0
                ),
                "cohort_readiness": cohort_readiness,
            },
            "forward_comparison": forward,
            "governance": {
                "current_verdict": verdict,
                "reason_codes": reason_codes,
                "plain_english_reason": reason,
                "paper_activation": paper_activation,
                "paper_routing": paper_routing,
                "next_automatic_action": next_action,
            },
            "strategy_policy": self._strategy_policy_summary(strategy_policy),
            "safety": {
                "paper_position_limit": 1,
                "rules_benchmark": "PERMANENT",
                "paper_risk_multiplier": 1.0,
                "real_order_authority": "NONE",
                "real_order_execution": (
                    "IMPOSSIBLE" if shadow_safe else "NOT_SAFELY_BLOCKED"
                ),
                "phase6_startup_gate": (
                    "READY_FOR_LIVE_SHADOW"
                    if phase6_ready
                    else "BLOCKED_UNLESS_LIVE_SHADOW"
                ),
            },
            "source_health": {
                "warnings": source_warnings,
                "sources": sources,
            },
        }
        self._write_atomic(document)
        return document

    @staticmethod
    def render_console(document: dict) -> str:
        training = document.get("training_data") or {}
        forward = document.get("forward_comparison") or {}
        governance = document.get("governance") or {}
        safety = document.get("safety") or {}
        warnings = (document.get("source_health") or {}).get("warnings") or []

        def _progress(actual, required) -> str:
            actual = int(actual or 0)
            required = int(required or 0)
            if required <= 0:
                return f"{actual:,}"
            marker = "PASS" if actual >= required else "WAIT"
            return f"{actual:,} / {required:,} [{marker}]"

        lines = [
            "NBOT LEARNING STATUS",
            "================================================",
            f"Environment            : {document.get('environment', 'N/A')}+{document.get('execution_mode', 'N/A')}",
            f"Current champion       : {document.get('current_paper_champion') or 'NONE'}",
            f"Current challenger     : {document.get('current_challenger') or 'NONE'}",
            f"Challenger stage       : {document.get('challenger_stage') or 'NONE'}",
            "",
            f"TRAINING ({training.get('phase', 'UNKNOWN')})",
            f"Training status        : {training.get('status', 'NOT_AVAILABLE')}",
            "Qualified outcomes     : " + _progress(
                training.get("completed_outcomes"),
                training.get("required_outcomes"),
            ),
            "Independent events     : " + _progress(
                training.get("independent_market_events"),
                training.get("required_independent_market_events"),
            ),
        ]

        cohort = training.get("cohort_readiness") or {}
        cohort_checks = cohort.get("checks") or {}
        if cohort:
            split_events = cohort.get("split_market_events") or {}
            purging = cohort.get("purging") or {}
            embargo = cohort.get("embargo") or {}

            def _cohort_required(name):
                check = cohort_checks.get(name) or {}
                return int(check.get("required_min", 0) or 0)

            lines.extend([
                f"Cohort split status    : {cohort.get('split_status', 'UNKNOWN')}",
                f"Cohort build mode      : {cohort.get('snapshot_build_mode', 'UNKNOWN')}",
                "Cohort train events    : " + _progress(
                    split_events.get("train"),
                    _cohort_required("train_market_events"),
                ),
                "Cohort validation      : " + _progress(
                    split_events.get("validation"),
                    _cohort_required("validation_market_events"),
                ),
                "Cohort test events     : " + _progress(
                    split_events.get("test"),
                    _cohort_required("test_market_events"),
                ),
                f"Purged event groups    : {int(purging.get('candidate_groups_excluded', 0) or 0):,}",
                f"Embargoed event groups : {int(embargo.get('candidate_groups_excluded', 0) or 0):,}",
            ])

        lines.extend([
            "",
            "FORWARD CHALLENGE (7.5)",
            f"Comparison status      : {forward.get('status', 'NOT_AVAILABLE')}",
            "Matched outcomes       : " + _progress(
                forward.get("matched_candidate_outcomes"),
                forward.get("matched_required"),
            ),
            "Independent comparisons: " + _progress(
                forward.get("independent_decision_events"),
                forward.get("independent_required"),
            ),
            "Disagreement events    : " + _progress(
                forward.get("paired_disagreement_events"),
                forward.get("disagreement_required"),
            ),
            "Market regimes         : " + _progress(
                forward.get("market_regimes_eligible"),
                forward.get("market_regimes_required"),
            ),
            f"Champion average R     : {AutoLearningStatusPublisher._r(forward.get('champion_average_net_r'))}",
            f"Challenger average R   : {AutoLearningStatusPublisher._r(forward.get('challenger_average_net_r'))}",
            f"Lift                   : {AutoLearningStatusPublisher._r(forward.get('average_r_lift_over_champion'))}",
            "",
            f"Current verdict        : {governance.get('current_verdict', 'UNKNOWN')}",
            f"Reason                 : {governance.get('plain_english_reason', 'No reason available.')}",
            f"Paper activation       : {governance.get('paper_activation', 'UNKNOWN')}",
            f"Real-order execution   : {safety.get('real_order_execution', 'UNKNOWN')}",
            f"Next automatic action  : {governance.get('next_automatic_action', 'UNKNOWN')}",
        ])
        if warnings:
            lines.append(f"Source warnings        : {', '.join(warnings)}")
        return "\n".join(lines)

    @classmethod
    def render_telegram_body(cls, document: dict) -> str:
        console = cls.render_console(document)
        return f"<pre>{html.escape(console)}</pre>"

    def _challenger_id(
        self,
        *,
        champion_id: str,
        canary_id: Any,
        shadow_id: Any,
        latest_id: Any,
        models: dict,
    ) -> str | None:
        for value in (canary_id, shadow_id):
            if value:
                return str(value)
        if latest_id and str(latest_id) != champion_id:
            record = models.get(str(latest_id))
            if isinstance(record, dict) and record.get("status") not in {
                "INVALID", "REJECTED", "ROLLED_BACK", "ARCHIVED"
            }:
                return str(latest_id)
        return None

    @staticmethod
    def _stage(
        *,
        challenger_id: str | None,
        canary_id: Any,
        shadow_id: Any,
        record: dict,
    ) -> str:
        if challenger_id is None:
            return "NONE"
        if canary_id and str(canary_id) == challenger_id:
            return str(
                record.get("paper_canary_stage")
                or "PAPER_CANARY_10_PERCENT"
            )
        if shadow_id and str(shadow_id) == challenger_id:
            return "SHADOW"
        return str(record.get("status") or "REGISTERED")

    @staticmethod
    def _select_evidence(
        *,
        challenger_id: str | None,
        promotion: dict,
        promotion_evidence: dict,
        canary: dict,
    ) -> dict:
        if challenger_id and str(promotion.get("model_id") or "") == challenger_id:
            evidence = promotion.get("evidence")
            if isinstance(evidence, dict):
                return evidence
        if challenger_id and str(canary.get("model_id") or "") == challenger_id:
            rollback = canary.get("rollback_evidence")
            if isinstance(rollback, dict):
                return rollback
        if isinstance(promotion_evidence, dict):
            return promotion_evidence
        return {}

    def _forward_metrics(self, evidence: dict, canary: dict) -> dict:
        forward = evidence.get("forward_comparison")
        if not isinstance(forward, dict):
            forward = {}
        canary_metrics = canary.get("metrics")
        if not isinstance(canary_metrics, dict):
            canary_metrics = {}
        matched = self._first_int(
            evidence.get("matched_candidate_outcomes"),
            forward.get("paired_raw_comparisons"),
        )
        independent = self._first_int(
            evidence.get("independent_decision_events"),
            forward.get("paired_independent_events"),
        )
        disagreements = self._first_int(
            evidence.get("paired_disagreement_events"),
            forward.get("disagreement_events"),
        )
        challenger_average = self._first_number(
            evidence.get("after_cost_expectancy"),
            canary_metrics.get("average_net_r"),
        )
        lift = self._first_number(
            evidence.get("average_r_lift_over_champion"),
            forward.get("average_r_lift"),
        )
        champion_average = self._first_number(
            evidence.get("champion_average_net_r"),
        )
        if champion_average is None and challenger_average is not None and lift is not None:
            champion_average = challenger_average - lift
        return {
            "matched_candidate_outcomes": matched,
            "independent_decision_events": independent,
            "paired_disagreement_events": disagreements,
            "champion_average_net_r": champion_average,
            "challenger_average_net_r": challenger_average,
            "average_r_lift_over_champion": lift,
            "recent_challenger_expectancy": self._first_number(
                evidence.get("recent_period_expectancy"),
                canary_metrics.get("recent_average_net_r"),
            ),
            "return_basis": "NET_AFTER_COSTS",
            "independence_basis": "MARKET_EVENT_ID_PRIMARY",
        }

    @staticmethod
    def _verdict(
        *,
        challenger_id: str | None,
        stage: str,
        promotion: dict,
        canary: dict,
        training: dict,
        record: dict,
    ) -> tuple[str, list[str]]:
        if canary.get("status") in {
            "ROLLED_BACK", "PAPER_CHAMPION_ROLLED_BACK"
        }:
            return "ROLLED_BACK", list(canary.get("reason_codes") or [])
        if stage.startswith("PAPER_CANARY_"):
            return "EXTEND_PAPER_CANARY", list(
                canary.get("reason_codes")
                or ["COLLECTING_INDEPENDENT_STAGE_EVIDENCE"]
            )
        if stage == "PAPER_CHAMPION":
            return "PAPER_CHAMPION", ["PAPER_CHAMPION_ACTIVE"]
        if stage == "SHADOW":
            return str(promotion.get("promotion_outcome") or "HOLD"), list(
                promotion.get("reason_codes") or []
            )
        if challenger_id:
            return str(record.get("status") or "HOLD"), []
        if training.get("status") == "WAITING_FOR_DATA":
            return "COLLECT_MORE_DATA", ["WAITING_FOR_DATA"]
        return "HOLD", ["NO_ACTIVE_CHALLENGER"]

    def _next_action(
        self,
        *,
        stage: str,
        verdict: str,
        training: dict,
        promotion: dict,
        canary: dict,
        challenger_id: str | None,
    ) -> str:
        if verdict == "ROLLED_BACK":
            return "Keep the restored champion active and train a new challenger after enough materially new data."
        if stage.startswith("PAPER_CANARY_"):
            metrics = canary.get("metrics") if isinstance(canary.get("metrics"), dict) else {}
            gates = canary.get("next_stage_gates") if isinstance(canary.get("next_stage_gates"), dict) else {}
            remaining_events = max(
                0,
                int(gates.get("min_independent_events", 0) or 0)
                - int(metrics.get("independent_market_events", 0) or 0),
            )
            remaining_trades = max(
                0,
                int(gates.get("min_completed_trades", 0) or 0)
                - int(metrics.get("completed_trades", 0) or 0),
            )
            next_stage = canary.get("next_stage") or "the next paper stage"
            return (
                f"Re-evaluate automatically for {next_stage} after "
                f"{remaining_events} new independent events and "
                f"{remaining_trades} completed canary trades."
            )
        if stage == "SHADOW":
            gates = promotion.get("gates")
            checks = gates.get("checks") if isinstance(gates, dict) else {}
            if not isinstance(checks, dict):
                checks = {}
            parts = []
            for key, label in (
                ("independent_decision_events", "independent events"),
                ("paired_disagreement_events", "disagreement events"),
                ("matched_candidate_outcomes", "matched outcomes"),
            ):
                item = checks.get(key)
                if not isinstance(item, dict):
                    continue
                remaining = max(
                    0,
                    int(item.get("required_min", 0) or 0)
                    - int(item.get("actual", 0) or 0),
                )
                if remaining:
                    parts.append(f"{remaining} {label}")
            if parts:
                return "Re-evaluate automatically after " + ", ".join(parts) + "."
            return "Re-evaluate automatically when fresh completed shadow outcomes arrive."
        if stage == "PAPER_CHAMPION":
            return "Continue paper operation, rollback monitoring, and automatic challenger retraining."
        if challenger_id:
            return "Move the eligible challenger into shadow testing on the next valid decision cycle."
        if training.get("status") == "WAITING_FOR_DATA":
            inventory = training.get("inventory") if isinstance(training.get("inventory"), dict) else {}
            thresholds = training.get("thresholds") if isinstance(training.get("thresholds"), dict) else {}
            outcomes = max(
                0,
                int(thresholds.get("min_new_outcomes", 0) or 0)
                - int(inventory.get("new_completed_outcomes", 0) or 0),
            )
            events = max(
                0,
                int(thresholds.get("min_new_market_events", 0) or 0)
                - int(inventory.get("new_independent_market_events", 0) or 0),
            )
            return (
                f"Train automatically after {outcomes} new completed outcomes "
                f"and {events} new independent events."
            )
        return "Collect fresh virtual outcomes; all learning services will act automatically when their gates pass."

    @staticmethod
    def _paper_activation(stage: str, champion_id: str) -> str:
        if stage.startswith("PAPER_CANARY_"):
            return stage
        if stage == "SHADOW":
            return "BLOCKED_SHADOW_ONLY"
        if champion_id == "RULE_SYSTEM_V1":
            return "RULE_CHAMPION_ONLY"
        return "PAPER_CHAMPION_MODEL_SELECTION"

    @staticmethod
    def _strategy_policy_summary(document: dict) -> dict:
        recommendations = document.get("recommendations")
        if not isinstance(recommendations, dict):
            recommendations = {}
        return {
            "status": document.get("status") or "NOT_AVAILABLE",
            "recommended_pattern_count": len(recommendations),
            "catalog_version": document.get("catalog_version"),
            "activation": document.get("activation") or "RESEARCH_RECOMMENDATION_ONLY",
            "real_order_authority": "NONE",
        }

    def _plain_reason(self, reason_codes: list[str], verdict: str) -> str:
        if reason_codes:
            code = str(reason_codes[0]).split(":", 1)[0]
            if code in _REASON_TEXT:
                return _REASON_TEXT[code]
            return code.replace("_", " ").capitalize() + "."
        if verdict == "PAPER_CHAMPION":
            return "The current model completed staged paper-canary progression and remains under automatic rollback monitoring."
        if verdict == "OFFLINE_VALIDATED":
            return "The challenger passed offline validation and is waiting for fresh shadow evidence."
        return "No additional governance reason is currently available."

    def _read_json_source(
        self, path: Path, name: str, now_ms: int
    ) -> tuple[dict, dict]:
        source = {
            "name": name,
            "path": str(path),
            "status": "MISSING",
            "generated_at_ms": None,
            "age_seconds": None,
        }
        if not path.exists():
            return {}, source
        try:
            document = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            source["status"] = "INVALID"
            source["error"] = f"{type(exc).__name__}:{exc}"
            return {}, source
        if not isinstance(document, dict):
            source["status"] = "INVALID"
            source["error"] = "JSON_ROOT_NOT_OBJECT"
            return {}, source
        generated = self._first_int(
            document.get("generated_at_ms"),
            document.get("evaluated_at_ms"),
            document.get("updated_at_ms"),
        )
        if generated:
            age = max(0.0, (now_ms - generated) / 1000.0)
            source["generated_at_ms"] = generated
            source["age_seconds"] = round(age, 3)
            source["status"] = (
                "STALE" if age > self.source_stale_seconds else "OK"
            )
        else:
            source["status"] = "OK"
        return document, source

    def _write_atomic(self, document: dict) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.status_path.name}.",
            suffix=".tmp",
            dir=str(self.status_path.parent),
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.status_path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _r(value: Any) -> str:
        number = AutoLearningStatusPublisher._number(value)
        return "N/A" if number is None else f"{number:+.3f}R"

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _first_number(cls, *values: Any) -> float | None:
        for value in values:
            number = cls._number(value)
            if number is not None:
                return number
        return None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _first_int(cls, *values: Any) -> int:
        for value in values:
            number = cls._int_or_none(value)
            if number is not None:
                return number
        return 0


def build_configured_publisher() -> AutoLearningStatusPublisher:
    """Build the shared publisher lazily from the active environment config."""

    from config import (
        AUTO_LEARNING_STATUS_MAX_SOURCE_AGE_SECONDS,
        AUTO_LEARNING_STATUS_PATH,
        AUTO_TRAINING_OUTCOME_TYPE,
        AUTO_TRAINING_STATUS_PATH,
        AUTOMATIC_PROMOTION_EVIDENCE_REPORT_PATH,
        AUTOMATIC_PROMOTION_STATUS_PATH,
        CANDIDATE_OBSERVATIONS_PATH,
        CANDIDATE_OUTCOMES_PATH,
        EXECUTION_MODE,
        MODEL_REGISTRY_PATH,
        PAPER_CANARY_STATUS_PATH,
        RULE_MODEL_VERSION,
        STRATEGY_POLICY_RECOMMENDATION_PATH,
        TRADING_ENV,
    )

    return AutoLearningStatusPublisher(
        environment=TRADING_ENV,
        execution_mode=EXECUTION_MODE,
        default_champion_model_id=RULE_MODEL_VERSION,
        status_path=AUTO_LEARNING_STATUS_PATH,
        registry_path=MODEL_REGISTRY_PATH,
        observations_path=CANDIDATE_OBSERVATIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        training_outcome_type=AUTO_TRAINING_OUTCOME_TYPE,
        auto_training_status_path=AUTO_TRAINING_STATUS_PATH,
        promotion_status_path=AUTOMATIC_PROMOTION_STATUS_PATH,
        promotion_evidence_path=AUTOMATIC_PROMOTION_EVIDENCE_REPORT_PATH,
        paper_canary_status_path=PAPER_CANARY_STATUS_PATH,
        strategy_policy_path=STRATEGY_POLICY_RECOMMENDATION_PATH,
        source_stale_seconds=AUTO_LEARNING_STATUS_MAX_SOURCE_AGE_SECONDS,
    )
