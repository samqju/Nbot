"""Staged paper routing and complete automatic rollback for Phase 5.12."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from learning.model_artifact_scorer import (
    RegisteredModelArtifactScorer,
    RegisteredModelScoringError,
)
from learning.automatic_rollback import RuntimeRollbackEvidenceEvaluator
from learning.model_registry import (
    ModelRegistry,
    ModelRegistryError,
    PAPER_CANARY_STAGE_ALLOCATION,
    PAPER_CANARY_STAGE_TRANSITIONS,
)


PAPER_CANARY_DECISION_SCHEMA_VERSION = 2
PAPER_CANARY_STATUS_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class PaperCanaryRoute:
    candidate: Any
    selection_authority: str
    model_id: str | None
    risk_multiplier: float
    allocation_id: str | None
    allocation_sample: float | None
    model_probability: float | None
    reason: str
    canary_model_id: str | None = None
    canary_stage: str | None = None
    champion_model_id: str | None = None
    evaluated_model_id: str | None = None
    evaluated_model_candidate_observation_id: str | None = None
    evaluated_model_probability: float | None = None
    benchmark_candidate_observation_id: str | None = None
    health_failure_code: str | None = None

    @property
    def is_canary(self) -> bool:
        return self.selection_authority == "PAPER_CANARY"

    @property
    def is_model_selected(self) -> bool:
        return self.selection_authority in {
            "PAPER_CANARY",
            "PAPER_CHAMPION",
        }


class PaperCanaryRouter:
    """Deterministic staged paper routing with rule fallback.

    Rules remain the permanent benchmark. A registered paper champion controls
    non-canary paper batches; a canary controls only its deterministic stage
    share. Every model-selected route uses the unchanged paper risk budget.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        execution_mode: str,
        environment: str,
        registry_path: str,
        default_champion_model_id: str,
        decisions_path: str,
        trades_path: str,
        allocation_fraction: float,
        risk_multiplier: float,
        max_trades_per_utc_day: int,
        minimum_model_probability: float,
        system_log=None,
    ):
        self.enabled = bool(enabled)
        self.execution_mode = str(execution_mode or "").strip().upper()
        self.environment = str(environment or "").strip().upper()
        self.default_champion_model_id = str(
            default_champion_model_id or ""
        ).strip()
        self.decisions_path = Path(decisions_path)
        self.trades_path = Path(trades_path)
        # Retained only as a migration fallback for a legacy registry record.
        self.legacy_allocation_fraction = float(allocation_fraction)
        self.risk_multiplier = float(risk_multiplier)
        self.max_trades_per_utc_day = int(max_trades_per_utc_day)
        self.minimum_model_probability = float(minimum_model_probability)
        self.system_log = system_log
        if not self.environment:
            raise ValueError("PAPER_CANARY_ENVIRONMENT_REQUIRED")
        if not self.default_champion_model_id:
            raise ValueError("PAPER_CANARY_CHAMPION_REQUIRED")
        if not (0.0 < self.legacy_allocation_fraction <= 1.0):
            raise ValueError("PAPER_CANARY_ALLOCATION_FRACTION_INVALID")
        if abs(self.risk_multiplier - 1.0) > 1e-12:
            raise ValueError("PAPER_CANARY_RISK_MULTIPLIER_MUST_EQUAL_ONE")
        if self.max_trades_per_utc_day < 1:
            raise ValueError("PAPER_CANARY_MAX_DAILY_TRADES_INVALID")
        if not (0.0 <= self.minimum_model_probability <= 1.0):
            raise ValueError("PAPER_CANARY_MINIMUM_PROBABILITY_INVALID")
        self.registry = ModelRegistry(
            path=registry_path,
            environment=self.environment,
            default_champion_model_id=self.default_champion_model_id,
        )
        self._scorers: dict[
            tuple[str, str, str], RegisteredModelArtifactScorer
        ] = {}
        self._write_lock = threading.Lock()

    def route(
        self,
        *,
        candidates: Iterable,
        rule_candidate,
        decision_batch_id: str,
        market_event_id: str,
        candle_bucket: int,
    ) -> PaperCanaryRoute:
        candidates = list(candidates)
        batch_id = str(decision_batch_id or "").strip()
        event_id = str(market_event_id or "").strip()
        if not batch_id or not event_id:
            raise ValueError("PAPER_CANARY_DECISION_IDENTITY_INVALID")
        if rule_candidate is None:
            route = self._rule_route(None, "NO_RULE_CANDIDATE")
            self._record(route, batch_id, event_id, candle_bucket, None)
            return route
        if not self.enabled:
            route = self._rule_route(rule_candidate, "PAPER_MODEL_ROUTING_DISABLED")
            self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
            return route
        if self.execution_mode != "SHADOW":
            route = self._rule_route(
                rule_candidate,
                "PAPER_MODEL_ROUTING_BLOCKED_NON_SHADOW_EXECUTION",
            )
            self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
            return route

        attempted_model_id = None
        attempted_stage = None
        benchmark_candidate_id = str(
            getattr(rule_candidate, "observation_id", "") or ""
        ) or None
        try:
            self.registry.initialize()
            document = self.registry.load()
            champion_id = str(
                document.get("current_champion_model_id")
                or self.default_champion_model_id
            )
            if champion_id != self.default_champion_model_id:
                attempted_model_id = champion_id
            champion_route = self._champion_route(
                candidates=candidates,
                rule_candidate=rule_candidate,
                document=document,
            )
            canary_id = document.get("current_paper_canary_model_id")
            if not canary_id:
                self._record(
                    champion_route,
                    batch_id,
                    event_id,
                    candle_bucket,
                    rule_candidate,
                )
                return champion_route

            canary_id = str(canary_id)
            record = document.get("models", {}).get(canary_id)
            if not isinstance(record, dict) or record.get("status") != "PAPER_CANARY":
                raise ModelRegistryError(
                    "PAPER_CANARY_REGISTRY_STATE_INVALID | "
                    f"model_id={canary_id}"
                )
            stage = self.registry.paper_canary_stage(record)
            allocation_fraction = PAPER_CANARY_STAGE_ALLOCATION[stage]
            if self._completed_today(canary_id) >= self.max_trades_per_utc_day:
                route = self._with_allocation(
                    champion_route,
                    canary_model_id=canary_id,
                    canary_stage=stage,
                    reason="PAPER_CANARY_DAILY_TRADE_LIMIT",
                )
                self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
                return route

            allocation_id, allocation_sample = self._allocation(
                model_id=canary_id,
                decision_batch_id=batch_id,
            )
            if allocation_sample >= allocation_fraction:
                route = self._with_allocation(
                    champion_route,
                    canary_model_id=canary_id,
                    canary_stage=stage,
                    allocation_id=allocation_id,
                    allocation_sample=allocation_sample,
                    reason="CHAMPION_TRAFFIC_BUCKET",
                )
                self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
                return route

            attempted_model_id = canary_id
            attempted_stage = stage
            benchmark_candidate_id = str(
                getattr(champion_route.candidate, "observation_id", "") or ""
            ) or benchmark_candidate_id
            scorer = self._scorer(record)
            probabilities = scorer.score_candidates(candidates)
            canary_candidate = min(
                candidates,
                key=lambda candidate: (
                    -float(probabilities[str(candidate.observation_id)]),
                    candidate.symbol,
                    candidate.direction,
                    str(candidate.observation_id),
                ),
            )
            probability = float(
                probabilities[str(canary_candidate.observation_id)]
            )
            if probability < self.minimum_model_probability:
                route = self._with_allocation(
                    champion_route,
                    canary_model_id=canary_id,
                    canary_stage=stage,
                    allocation_id=allocation_id,
                    allocation_sample=allocation_sample,
                    model_probability=probability,
                    evaluated_model_id=canary_id,
                    evaluated_model_candidate_observation_id=str(
                        canary_candidate.observation_id
                    ),
                    evaluated_model_probability=probability,
                    benchmark_candidate_observation_id=benchmark_candidate_id,
                    reason="CANARY_MODEL_CONFIDENCE_BELOW_FLOOR",
                )
                self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
                return route

            self.registry.enable_paper_canary_routing(
                canary_id,
                allocation_fraction=allocation_fraction,
                risk_multiplier=1.0,
                execution_mode=self.execution_mode,
            )
            route = PaperCanaryRoute(
                candidate=canary_candidate,
                selection_authority="PAPER_CANARY",
                model_id=canary_id,
                risk_multiplier=1.0,
                allocation_id=allocation_id,
                allocation_sample=allocation_sample,
                model_probability=probability,
                reason="PAPER_CANARY_TRAFFIC_ALLOCATED",
                canary_model_id=canary_id,
                canary_stage=stage,
                champion_model_id=str(
                    document.get("current_champion_model_id")
                    or self.default_champion_model_id
                ),
                evaluated_model_id=canary_id,
                evaluated_model_candidate_observation_id=str(
                    canary_candidate.observation_id
                ),
                evaluated_model_probability=probability,
                benchmark_candidate_observation_id=benchmark_candidate_id,
            )
            self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
            if self.system_log:
                self.system_log.warning(
                    "PAPER_CANARY_CANDIDATE_SELECTED | "
                    f"model_id={canary_id} | stage={stage} | "
                    f"batch={batch_id} | symbol={canary_candidate.symbol} | "
                    f"direction={canary_candidate.direction} | "
                    f"probability={probability:.6f} | risk_multiplier=1.0000 | "
                    "execution=LOCAL_PAPER_ONLY | real_orders=IMPOSSIBLE"
                )
            return route
        except Exception as exc:
            if self.system_log:
                self.system_log.error(
                    "PAPER_MODEL_ROUTE_FAILED_CLOSED | "
                    f"batch={batch_id} | error={type(exc).__name__}:{exc} | "
                    "fallback=RULES | real_order_authority=NONE"
                )
            failure_code = self._health_failure_code(exc)
            route = PaperCanaryRoute(
                candidate=rule_candidate,
                selection_authority="RULES",
                model_id=None,
                risk_multiplier=1.0,
                allocation_id=None,
                allocation_sample=None,
                model_probability=None,
                reason=f"MODEL_ROUTING_FAILURE_FALLBACK:{type(exc).__name__}",
                canary_model_id=(
                    attempted_model_id if attempted_stage else None
                ),
                canary_stage=attempted_stage,
                champion_model_id=(
                    attempted_model_id
                    if attempted_model_id and not attempted_stage
                    else self.default_champion_model_id
                ),
                evaluated_model_id=attempted_model_id,
                benchmark_candidate_observation_id=benchmark_candidate_id,
                health_failure_code=failure_code,
            )
            self._record(route, batch_id, event_id, candle_bucket, rule_candidate)
            return route

    def _champion_route(self, *, candidates, rule_candidate, document: dict):
        champion_id = str(
            document.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        if champion_id == self.default_champion_model_id:
            return PaperCanaryRoute(
                candidate=rule_candidate,
                selection_authority="RULES",
                model_id=None,
                risk_multiplier=1.0,
                allocation_id=None,
                allocation_sample=None,
                model_probability=None,
                reason="RULE_CHAMPION_SELECTED",
                champion_model_id=champion_id,
            )
        record = document.get("models", {}).get(champion_id)
        if not isinstance(record, dict) or record.get("status") != "PAPER_CHAMPION":
            raise ModelRegistryError(
                "PAPER_CHAMPION_REGISTRY_STATE_INVALID | "
                f"model_id={champion_id}"
            )
        probabilities = self._scorer(record).score_candidates(candidates)
        candidate = min(
            candidates,
            key=lambda item: (
                -float(probabilities[str(item.observation_id)]),
                item.symbol,
                item.direction,
                str(item.observation_id),
            ),
        )
        probability = float(probabilities[str(candidate.observation_id)])
        return PaperCanaryRoute(
            candidate=candidate,
            selection_authority="PAPER_CHAMPION",
            model_id=champion_id,
            risk_multiplier=1.0,
            allocation_id=None,
            allocation_sample=None,
            model_probability=probability,
            reason="PAPER_CHAMPION_SELECTED",
            champion_model_id=champion_id,
            evaluated_model_id=champion_id,
            evaluated_model_candidate_observation_id=str(
                candidate.observation_id
            ),
            evaluated_model_probability=probability,
            benchmark_candidate_observation_id=str(
                getattr(rule_candidate, "observation_id", "") or ""
            ) or None,
        )

    def _scorer(self, record: dict) -> RegisteredModelArtifactScorer:
        model_id = str(record.get("model_id") or "").strip()
        artifact_path = str(record.get("artifact_path") or "").strip()
        checksum = str(
            record.get("artifact_checksum_sha256") or ""
        ).strip().lower()
        key = (model_id, artifact_path, checksum)
        scorer = self._scorers.get(key)
        if scorer is None:
            scorer = RegisteredModelArtifactScorer(
                model_id=model_id,
                artifact_path=artifact_path,
                expected_checksum_sha256=checksum or None,
                expected_feature_schema_version=(
                    int(record["feature_schema_version"])
                    if record.get("feature_schema_version") is not None
                    else None
                ),
            )
            self._scorers[key] = scorer
        return scorer

    def _completed_today(self, model_id: str) -> int:
        if not self.trades_path.exists():
            return 0
        today = datetime.now(timezone.utc).date()
        count = 0
        with self.trades_path.open() as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    closed_at_ms = int(row.get("closed_at_ms", 0) or 0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if (
                    row.get("selection_authority") != "PAPER_CANARY"
                    or row.get("paper_canary_model_id") != model_id
                    or closed_at_ms <= 0
                ):
                    continue
                closed_date = datetime.fromtimestamp(
                    closed_at_ms / 1000.0,
                    tz=timezone.utc,
                ).date()
                if closed_date == today:
                    count += 1
        return count

    def _allocation(self, *, model_id: str, decision_batch_id: str):
        seed = (
            f"{self.environment}|{model_id}|{decision_batch_id}|MISSION_ALIGNMENT_V1"
        ).encode("utf-8")
        digest = hashlib.sha256(seed).hexdigest()
        sample = int(digest[:16], 16) / float(16**16)
        return f"CANARY_{digest[:20].upper()}", sample

    def _rule_route(self, candidate, reason: str) -> PaperCanaryRoute:
        return PaperCanaryRoute(
            candidate=candidate,
            selection_authority="RULES",
            model_id=None,
            risk_multiplier=1.0,
            allocation_id=None,
            allocation_sample=None,
            model_probability=None,
            reason=reason,
            champion_model_id=self.default_champion_model_id,
        )

    @staticmethod
    def _with_allocation(
        route: PaperCanaryRoute,
        *,
        canary_model_id: str,
        canary_stage: str,
        reason: str,
        allocation_id: str | None = None,
        allocation_sample: float | None = None,
        model_probability: float | None = None,
        evaluated_model_id: str | None = None,
        evaluated_model_candidate_observation_id: str | None = None,
        evaluated_model_probability: float | None = None,
        benchmark_candidate_observation_id: str | None = None,
    ) -> PaperCanaryRoute:
        return PaperCanaryRoute(
            candidate=route.candidate,
            selection_authority=route.selection_authority,
            model_id=route.model_id,
            risk_multiplier=1.0,
            allocation_id=allocation_id,
            allocation_sample=allocation_sample,
            model_probability=(
                route.model_probability
                if model_probability is None
                else model_probability
            ),
            reason=reason,
            canary_model_id=canary_model_id,
            canary_stage=canary_stage,
            champion_model_id=route.champion_model_id,
            evaluated_model_id=(
                route.evaluated_model_id
                if evaluated_model_id is None else evaluated_model_id
            ),
            evaluated_model_candidate_observation_id=(
                route.evaluated_model_candidate_observation_id
                if evaluated_model_candidate_observation_id is None
                else evaluated_model_candidate_observation_id
            ),
            evaluated_model_probability=(
                route.evaluated_model_probability
                if evaluated_model_probability is None
                else evaluated_model_probability
            ),
            benchmark_candidate_observation_id=(
                route.benchmark_candidate_observation_id
                if benchmark_candidate_observation_id is None
                else benchmark_candidate_observation_id
            ),
            health_failure_code=route.health_failure_code,
        )

    @staticmethod
    def _health_failure_code(exc: Exception) -> str:
        message = str(exc).upper()
        if "REQUIRED_FEATURE_MISSING" in message or "FEATURE_MISSING" in message:
            return "REQUIRED_FEATURE_MISSING"
        if "SCHEMA" in message:
            return "FEATURE_SCHEMA_MISMATCH"
        if "ARTIFACT" in message or "CHECKSUM" in message or "UNPICKLE" in message:
            return "ARTIFACT_FAILURE"
        return "PREDICTION_FAILURE"

    def _record(
        self,
        route: PaperCanaryRoute,
        batch_id: str,
        event_id: str,
        candle_bucket: int,
        rule_candidate,
    ) -> None:
        stage_fraction = (
            PAPER_CANARY_STAGE_ALLOCATION.get(route.canary_stage)
            if route.canary_stage
            else None
        )
        document = {
            "schema_version": PAPER_CANARY_DECISION_SCHEMA_VERSION + 1,
            "observation_type": "PAPER_CANARY_ROUTING_DECISION",
            "observed_at_ms": int(time.time() * 1000),
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "decision_batch_id": batch_id,
            "market_event_id": event_id,
            "candle_bucket": int(candle_bucket),
            "selection_authority": route.selection_authority,
            "selected_model_id": route.model_id,
            "current_champion_model_id": route.champion_model_id,
            "current_paper_canary_model_id": route.canary_model_id,
            "paper_canary_stage": route.canary_stage,
            "selected_candidate_observation_id": (
                getattr(route.candidate, "observation_id", None)
            ),
            "rule_candidate_observation_id": (
                getattr(rule_candidate, "observation_id", None)
            ),
            "allocation_id": route.allocation_id,
            "allocation_sample": route.allocation_sample,
            "allocation_fraction": stage_fraction,
            "risk_multiplier": 1.0,
            "model_probability": route.model_probability,
            "evaluated_model_id": route.evaluated_model_id,
            "evaluated_model_candidate_observation_id": (
                route.evaluated_model_candidate_observation_id
            ),
            "evaluated_model_probability": route.evaluated_model_probability,
            "benchmark_candidate_observation_id": (
                route.benchmark_candidate_observation_id
            ),
            "health_failure_code": route.health_failure_code,
            "reason": route.reason,
            "rules_benchmark": "PERMANENT",
            "paper_execution": "LOCAL_SHADOW_ONLY",
            "real_order_authority": "NONE",
        }
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(document, sort_keys=True, default=str)
        with self._write_lock:
            descriptor = os.open(
                self.decisions_path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(descriptor, (line + "\n").encode("utf-8"))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)


class PaperCanaryControllerAlreadyRunning(RuntimeError):
    pass


class PaperCanaryControllerProcessLock:
    def __init__(self, path: str):
        self.path = Path(path)
        self._handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise PaperCanaryControllerAlreadyRunning(
                f"PAPER_CANARY_CONTROLLER_ALREADY_RUNNING | path={self.path}"
            ) from exc
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
        return False


class AutomaticPaperCanaryController:
    """Advance healthy paper canaries and roll back unsafe ones atomically."""

    def __init__(
        self,
        *,
        enabled: bool,
        execution_mode: str,
        environment: str,
        registry_path: str,
        trades_path: str,
        status_path: str,
        lock_path: str,
        default_champion_model_id: str,
        min_completed_trades: int,
        max_drawdown_r: float,
        max_losing_streak: int,
        min_average_net_r: float,
        recent_trade_window: int,
        min_recent_average_net_r: float,
        stage_10_min_completed_trades: int = 25,
        stage_10_min_independent_events: int = 20,
        stage_25_min_completed_trades: int = 75,
        stage_25_min_independent_events: int = 50,
        stage_50_min_completed_trades: int = 150,
        stage_50_min_independent_events: int = 100,
        advance_min_average_net_r: float = 0.0,
        advance_min_recent_average_net_r: float = 0.0,
        strategy_policy_refresher=None,
        decisions_path: str | None = None,
        outcomes_path: str | None = None,
        observations_path: str | None = None,
        rollback_min_paired_events: int = 20,
        rollback_min_average_r_lift: float = -0.15,
        rollback_min_runtime_decisions: int = 20,
        rollback_max_prediction_failures: int = 3,
        rollback_max_prediction_failure_rate: float = 0.05,
        rollback_min_calibration_outcomes: int = 20,
        rollback_max_brier_score: float = 0.25,
        rollback_max_calibration_gap: float = 0.10,
        rollback_min_drift_observations: int = 20,
        rollback_max_feature_psi: float = 0.25,
    ):
        self.enabled = bool(enabled)
        self.execution_mode = str(execution_mode or "").strip().upper()
        self.environment = str(environment or "").strip().upper()
        self.trades_path = Path(trades_path)
        self.status_path = Path(status_path)
        self.min_completed_trades = int(min_completed_trades)
        self.max_drawdown_r = float(max_drawdown_r)
        self.max_losing_streak = int(max_losing_streak)
        self.min_average_net_r = float(min_average_net_r)
        self.recent_trade_window = int(recent_trade_window)
        self.min_recent_average_net_r = float(min_recent_average_net_r)
        self.advance_min_average_net_r = float(advance_min_average_net_r)
        self.advance_min_recent_average_net_r = float(
            advance_min_recent_average_net_r
        )
        self.stage_gates = {
            "PAPER_CANARY_10_PERCENT": {
                "min_completed_trades": int(stage_10_min_completed_trades),
                "min_independent_events": int(stage_10_min_independent_events),
            },
            "PAPER_CANARY_25_PERCENT": {
                "min_completed_trades": int(stage_25_min_completed_trades),
                "min_independent_events": int(stage_25_min_independent_events),
            },
            "PAPER_CANARY_50_PERCENT": {
                "min_completed_trades": int(stage_50_min_completed_trades),
                "min_independent_events": int(stage_50_min_independent_events),
            },
        }
        self.strategy_policy_refresher = strategy_policy_refresher
        self.rollback_evaluator = None
        if decisions_path and outcomes_path and observations_path:
            self.rollback_evaluator = RuntimeRollbackEvidenceEvaluator(
                trades_path=trades_path,
                decisions_path=decisions_path,
                outcomes_path=outcomes_path,
                observations_path=observations_path,
                recent_trade_window=recent_trade_window,
                max_drawdown_r=max_drawdown_r,
                max_losing_streak=max_losing_streak,
                min_completed_trades=min_completed_trades,
                min_average_net_r=min_average_net_r,
                min_recent_average_net_r=min_recent_average_net_r,
                min_paired_events=rollback_min_paired_events,
                min_average_r_lift=rollback_min_average_r_lift,
                min_runtime_decisions=rollback_min_runtime_decisions,
                max_prediction_failures=rollback_max_prediction_failures,
                max_prediction_failure_rate=(
                    rollback_max_prediction_failure_rate
                ),
                min_calibration_outcomes=(
                    rollback_min_calibration_outcomes
                ),
                max_brier_score=rollback_max_brier_score,
                max_calibration_gap=rollback_max_calibration_gap,
                min_drift_observations=(
                    rollback_min_drift_observations
                ),
                max_feature_psi=rollback_max_feature_psi,
            )
        if not self.environment:
            raise ValueError("PAPER_CANARY_CONTROLLER_ENVIRONMENT_REQUIRED")
        if self.min_completed_trades < 1:
            raise ValueError("PAPER_CANARY_MIN_COMPLETED_TRADES_INVALID")
        if self.max_drawdown_r <= 0:
            raise ValueError("PAPER_CANARY_MAX_DRAWDOWN_INVALID")
        if self.max_losing_streak < 1:
            raise ValueError("PAPER_CANARY_MAX_LOSING_STREAK_INVALID")
        if self.recent_trade_window < 1:
            raise ValueError("PAPER_CANARY_RECENT_WINDOW_INVALID")
        if any(
            gate["min_completed_trades"] < 1
            or gate["min_independent_events"] < 1
            for gate in self.stage_gates.values()
        ):
            raise ValueError("PAPER_CANARY_STAGE_GATE_INVALID")
        self.registry = ModelRegistry(
            path=registry_path,
            environment=self.environment,
            default_champion_model_id=default_champion_model_id,
        )
        self.lock = PaperCanaryControllerProcessLock(lock_path)

    def run_once(self) -> dict:
        if not self.enabled:
            return self._status(
                "DISABLED",
                reason_codes=["PAPER_CANARY_CONTROLLER_ENABLED_FALSE"],
            )
        if self.execution_mode != "SHADOW":
            return self._status(
                "BLOCKED_NON_SHADOW_EXECUTION",
                reason_codes=["PAPER_CANARY_REQUIRES_SHADOW_EXECUTION"],
            )
        try:
            with self.lock:
                return self._run_locked()
        except PaperCanaryControllerAlreadyRunning as exc:
            return self._status(
                "SKIPPED_ALREADY_RUNNING",
                reason_codes=[str(exc)],
            )

    def _run_locked(self) -> dict:
        policy_status = self._refresh_strategy_policy()
        self.registry.initialize()
        document = self.registry.load()
        champion_rollback = self._maybe_rollback_champion(
            document, policy_status
        )
        if champion_rollback is not None:
            return champion_rollback
        document = self.registry.load()
        model_id = document.get("current_paper_canary_model_id")
        if not model_id:
            return self._status(
                "WAITING_FOR_PAPER_CANARY",
                reason_codes=["NO_CURRENT_PAPER_CANARY_MODEL"],
                current_champion_model_id=document.get(
                    "current_champion_model_id"
                ),
                previous_champion_model_id=document.get(
                    "previous_champion_model_id"
                ),
                strategy_policy=policy_status,
            )
        model_id = str(model_id)
        record = document.get("models", {}).get(model_id)
        if not isinstance(record, dict) or record.get("status") != "PAPER_CANARY":
            raise ModelRegistryError(
                "PAPER_CANARY_CONTROLLER_REGISTRY_STATE_INVALID | "
                f"model_id={model_id}"
            )
        stage = self.registry.paper_canary_stage(record)

        metrics = self._metrics(model_id)
        metrics["paper_canary_stage"] = stage
        rollback_report = None
        if self.rollback_evaluator is not None:
            rollback_report = self.rollback_evaluator.evaluate(
                model_id=model_id,
                role="PAPER_CANARY",
                record=record,
                started_at_ms=int(
                    record.get("paper_canary_started_at_ms", 0) or 0
                ),
                benchmark_model_id=str(
                    document.get("current_champion_model_id")
                    or self.registry.default_champion_model_id
                ),
            )
            reason_codes = list(rollback_report["reason_codes"])
        else:
            reason_codes = []
            try:
                RegisteredModelArtifactScorer(
                    model_id=model_id,
                    artifact_path=str(record.get("artifact_path") or ""),
                    expected_checksum_sha256=str(
                        record.get("artifact_checksum_sha256") or ""
                    ) or None,
                )
            except (RegisteredModelScoringError, ValueError) as exc:
                reason_codes.append(
                    f"CANARY_ARTIFACT_INVALID:{type(exc).__name__}"
                )
            if metrics["maximum_drawdown_r"] >= self.max_drawdown_r:
                reason_codes.append("CANARY_MAX_DRAWDOWN_BREACH")
            if metrics["maximum_losing_streak"] >= self.max_losing_streak:
                reason_codes.append("CANARY_MAX_LOSING_STREAK_BREACH")
            if metrics["completed_trades"] >= self.min_completed_trades:
                average = metrics["average_net_r"]
                recent = metrics["recent_average_net_r"]
                if average is None or average <= self.min_average_net_r:
                    reason_codes.append("CANARY_AVERAGE_EXPECTANCY_BREACH")
                if recent is None or recent <= self.min_recent_average_net_r:
                    reason_codes.append("CANARY_RECENT_EXPECTANCY_BREACH")

        if reason_codes:
            updated = self.registry.rollback_paper_canary(
                model_id,
                evidence=(rollback_report or metrics),
                reason_codes=reason_codes,
            )
            return self._status(
                "ROLLED_BACK",
                model_id=model_id,
                paper_canary_stage=stage,
                reason_codes=reason_codes,
                metrics=metrics,
                rollback_evidence=rollback_report,
                registry_model_status=updated.get("status"),
                registry_changed=True,
                strategy_policy=policy_status,
            )

        previous = record.get("paper_canary_last_evidence") or {}
        no_new = previous.get("completed_trades") == metrics["completed_trades"]
        target_stage = self._advancement_target(stage, metrics)
        if target_stage and not no_new:
            advance_reasons = [
                "INDEPENDENT_STAGE_EVIDENCE_GATES_PASSED",
                "UNCHANGED_PAPER_RISK_CONFIRMED",
            ]
            if target_stage == "PAPER_CHAMPION":
                updated = self.registry.promote_paper_canary_to_champion(
                    model_id,
                    evidence=metrics,
                    reason_codes=advance_reasons,
                )
                return self._status(
                    "PAPER_CHAMPION_PROMOTED",
                    model_id=model_id,
                    paper_canary_stage="PAPER_CHAMPION",
                    reason_codes=advance_reasons,
                    metrics=metrics,
                    registry_model_status=updated.get("status"),
                    registry_changed=True,
                    champion_changed=True,
                    current_champion_model_id=model_id,
                    previous_champion_model_id=(
                        updated.get("previous_champion_model_id")
                    ),
                    strategy_policy=policy_status,
                )
            updated = self.registry.advance_paper_canary_stage(
                model_id,
                target_stage=target_stage,
                evidence=metrics,
                reason_codes=advance_reasons,
            )
            return self._status(
                "PAPER_CANARY_STAGE_ADVANCED",
                model_id=model_id,
                paper_canary_stage=target_stage,
                reason_codes=advance_reasons,
                metrics=metrics,
                registry_model_status=updated.get("status"),
                registry_changed=True,
                strategy_policy=policy_status,
            )

        if not no_new:
            self.registry.update_paper_canary_evidence(
                model_id,
                evidence=metrics,
            )
        gate = self.stage_gates[stage]
        return self._status(
            "NO_NEW_COMPLETED_TRADES" if no_new else "PAPER_CANARY_ACTIVE",
            model_id=model_id,
            paper_canary_stage=stage,
            allocation_fraction=PAPER_CANARY_STAGE_ALLOCATION[stage],
            reason_codes=[
                "COLLECTING_INDEPENDENT_STAGE_EVIDENCE"
                if target_stage is None
                else "STAGE_EVIDENCE_READY"
            ],
            metrics=metrics,
            next_stage=PAPER_CANARY_STAGE_TRANSITIONS[stage],
            next_stage_gates=gate,
            registry_changed=not no_new,
            strategy_policy=policy_status,
        )

    def _maybe_rollback_champion(
        self, document: dict, policy_status: dict
    ) -> dict | None:
        if self.rollback_evaluator is None:
            return None
        champion_id = str(
            document.get("current_champion_model_id")
            or self.registry.default_champion_model_id
        )
        if champion_id == self.registry.default_champion_model_id:
            return None
        record = document.get("models", {}).get(champion_id)
        if not isinstance(record, dict) or record.get("status") != "PAPER_CHAMPION":
            raise ModelRegistryError(
                "PAPER_CHAMPION_CONTROLLER_REGISTRY_STATE_INVALID"
            )
        previous_id = str(
            record.get("previous_champion_model_id")
            or document.get("previous_champion_model_id")
            or self.registry.default_champion_model_id
        )
        report = self.rollback_evaluator.evaluate(
            model_id=champion_id,
            role="PAPER_CHAMPION",
            record=record,
            started_at_ms=int(
                record.get("paper_champion_started_at_ms", 0) or 0
            ),
            benchmark_model_id=previous_id,
        )
        if not report["rollback_required"]:
            return None
        restore_id = self._safe_restore_champion(previous_id, document)
        updated = self.registry.rollback_paper_champion(
            champion_id,
            restore_model_id=restore_id,
            evidence=report,
            reason_codes=report["reason_codes"],
        )
        return self._status(
            "PAPER_CHAMPION_ROLLED_BACK",
            model_id=champion_id,
            reason_codes=report["reason_codes"],
            rollback_evidence=report,
            restored_champion_model_id=(
                updated["restored_champion_model_id"]
            ),
            registry_changed=True,
            champion_changed=True,
            strategy_policy=policy_status,
        )

    def _safe_restore_champion(self, previous_id: str, document: dict) -> str:
        previous_id = str(previous_id or "").strip()
        if previous_id == self.registry.default_champion_model_id:
            return previous_id
        record = document.get("models", {}).get(previous_id)
        if not isinstance(record, dict) or record.get("status") != "PAPER_CHAMPION":
            return self.registry.default_champion_model_id
        try:
            RegisteredModelArtifactScorer(
                model_id=previous_id,
                artifact_path=str(record.get("artifact_path") or ""),
                expected_checksum_sha256=str(
                    record.get("artifact_checksum_sha256") or ""
                ) or None,
                expected_feature_schema_version=(
                    int(record["feature_schema_version"])
                    if record.get("feature_schema_version") is not None
                    else None
                ),
            )
        except (RegisteredModelScoringError, ValueError, OSError):
            return self.registry.default_champion_model_id
        return previous_id

    def _advancement_target(self, stage: str, metrics: dict) -> str | None:
        gate = self.stage_gates[stage]
        average = metrics.get("average_net_r")
        recent = metrics.get("recent_average_net_r")
        passed = (
            metrics["completed_trades"] >= gate["min_completed_trades"]
            and metrics["independent_market_events"]
            >= gate["min_independent_events"]
            and average is not None
            and average > self.advance_min_average_net_r
            and recent is not None
            and recent > self.advance_min_recent_average_net_r
        )
        return PAPER_CANARY_STAGE_TRANSITIONS[stage] if passed else None

    def _refresh_strategy_policy(self) -> dict:
        if self.strategy_policy_refresher is None:
            return {"status": "NOT_CONFIGURED"}
        try:
            result = self.strategy_policy_refresher.refresh()
            return {
                "status": result.get("status", "READY"),
                "recommendation_path": result.get("recommendation_path"),
                "recommended_pattern_count": len(
                    result.get("recommendations", {})
                ),
                "real_order_authority": "NONE",
            }
        except Exception as exc:
            return {
                "status": "REFRESH_FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "runtime_effect": "NONE",
                "real_order_authority": "NONE",
            }

    def _metrics(self, model_id: str) -> dict:
        rows = []
        if self.trades_path.exists():
            with self.trades_path.open() as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                        net_r = float(row.get("net_r"))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue
                    if (
                        row.get("selection_authority") != "PAPER_CANARY"
                        or row.get("paper_canary_model_id") != model_id
                        or not math.isfinite(net_r)
                    ):
                        continue
                    event_id = str(
                        row.get("market_event_id")
                        or row.get("decision_batch_id")
                        or row.get("trade_id")
                        or "UNKNOWN"
                    )
                    rows.append((
                        int(row.get("closed_at_ms", 0) or 0),
                        net_r,
                        event_id,
                    ))
        rows.sort(key=lambda item: (item[0], item[2]))
        values = [value for _, value, _ in rows]
        cumulative = 0.0
        peak = 0.0
        maximum_drawdown = 0.0
        current_losing = 0
        maximum_losing = 0
        for value in values:
            cumulative += value
            peak = max(peak, cumulative)
            maximum_drawdown = max(maximum_drawdown, peak - cumulative)
            if value < 0:
                current_losing += 1
                maximum_losing = max(maximum_losing, current_losing)
            else:
                current_losing = 0
        recent = values[-self.recent_trade_window :]
        return {
            "model_id": model_id,
            "completed_trades": len(values),
            "independent_market_events": len({event for _, _, event in rows}),
            "average_net_r": (
                sum(values) / len(values) if values else None
            ),
            "win_rate": (
                sum(1 for value in values if value > 0) / len(values)
                if values
                else None
            ),
            "maximum_drawdown_r": maximum_drawdown,
            "maximum_losing_streak": maximum_losing,
            "recent_trade_count": len(recent),
            "recent_average_net_r": (
                sum(recent) / len(recent) if recent else None
            ),
            "return_basis": "PAPER_NET_R_AFTER_FEES_AND_SLIPPAGE",
            "independence_basis": "MARKET_EVENT_ID_PRIMARY",
        }

    def _status(self, status: str, **extra) -> dict:
        champion_changed = bool(extra.pop("champion_changed", False))
        document = {
            "schema_version": PAPER_CANARY_STATUS_SCHEMA_VERSION + 1,
            "status": status,
            "evaluated_at_ms": int(time.time() * 1000),
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "champion_changed": champion_changed,
            "paper_risk_multiplier": 1.0,
            "rules_benchmark": "PERMANENT",
            "real_order_authority": "NONE",
            **extra,
        }
        self._atomic_json_write(self.status_path, document)
        return document

    @staticmethod
    def _atomic_json_write(path: Path, document: dict) -> None:
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

