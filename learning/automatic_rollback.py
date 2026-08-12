"""Phase 5.12 runtime health evidence for automatic model rollback.

The evaluator is read-only.  It joins append-only paper trades, paper-routing
snapshots, virtual candidate outcomes, candidate observations, and the immutable
training snapshot referenced by the registry.  It never changes model authority;
the atomic registry owns rollback transitions.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from utils.jsonl_history import iter_jsonl_lines, logical_jsonl_exists
from typing import Any

from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    context_feature_mapping,
    market_context_from_row,
)
from learning.model_artifact_scorer import (
    RegisteredModelArtifactScorer,
    RegisteredModelScoringError,
)
from learning.paper_execution_evidence import (
    iter_paper_execution_evidence,
)


ROLLBACK_EVIDENCE_SCHEMA_VERSION = 1


class RuntimeRollbackEvidenceEvaluator:
    def __init__(
        self,
        *,
        trades_path: str,
        decisions_path: str,
        outcomes_path: str,
        observations_path: str,
        recent_trade_window: int,
        max_drawdown_r: float,
        max_losing_streak: int,
        min_completed_trades: int,
        min_average_net_r: float,
        min_recent_average_net_r: float,
        min_paired_events: int,
        min_average_r_lift: float,
        min_runtime_decisions: int,
        max_prediction_failures: int,
        max_prediction_failure_rate: float,
        min_calibration_outcomes: int,
        max_brier_score: float,
        max_calibration_gap: float,
        min_drift_observations: int,
        max_feature_psi: float,
        drift_bins: int = 10,
        calibration_bins: int = 10,
    ):
        self.trades_path = Path(trades_path)
        self.decisions_path = Path(decisions_path)
        self.outcomes_path = Path(outcomes_path)
        self.observations_path = Path(observations_path)
        self.recent_trade_window = int(recent_trade_window)
        self.max_drawdown_r = float(max_drawdown_r)
        self.max_losing_streak = int(max_losing_streak)
        self.min_completed_trades = int(min_completed_trades)
        self.min_average_net_r = float(min_average_net_r)
        self.min_recent_average_net_r = float(min_recent_average_net_r)
        self.min_paired_events = int(min_paired_events)
        self.min_average_r_lift = float(min_average_r_lift)
        self.min_runtime_decisions = int(min_runtime_decisions)
        self.max_prediction_failures = int(max_prediction_failures)
        self.max_prediction_failure_rate = float(max_prediction_failure_rate)
        self.min_calibration_outcomes = int(min_calibration_outcomes)
        self.max_brier_score = float(max_brier_score)
        self.max_calibration_gap = float(max_calibration_gap)
        self.min_drift_observations = int(min_drift_observations)
        self.max_feature_psi = float(max_feature_psi)
        self.drift_bins = int(drift_bins)
        self.calibration_bins = int(calibration_bins)

    def evaluate(
        self,
        *,
        model_id: str,
        role: str,
        record: dict,
        started_at_ms: int,
        benchmark_model_id: str,
    ) -> dict:
        model_id = str(model_id or "").strip()
        role = str(role or "").strip().upper()
        reasons: list[str] = []
        artifact_health, scorer = self._artifact_health(model_id, record)
        if artifact_health["status"] != "HEALTHY":
            reasons.append(artifact_health["reason_code"])

        decisions = [
            row for row in self._read_jsonl(self.decisions_path)
            if int(row.get("observed_at_ms", 0) or 0) >= int(started_at_ms)
            and str(row.get("evaluated_model_id") or "") == model_id
        ]
        runtime_health = self._runtime_health(decisions)
        if runtime_health["required_feature_failures"]:
            reasons.append("REQUIRED_FEATURE_MISSING")
        if runtime_health["schema_mismatch_failures"]:
            reasons.append("FEATURE_SCHEMA_MISMATCH")
        if (
            runtime_health["model_evaluations"] >= self.min_runtime_decisions
            and (
                runtime_health["prediction_failures"]
                >= self.max_prediction_failures
                or runtime_health["prediction_failure_rate"]
                > self.max_prediction_failure_rate
            )
        ):
            reasons.append("PREDICTION_FAILURE_THRESHOLD_BREACH")

        paper = self._paper_metrics(model_id, role, started_at_ms)
        if paper["maximum_drawdown_r"] >= self.max_drawdown_r:
            reasons.append("MAXIMUM_DRAWDOWN_BREACH")
        if paper["maximum_losing_streak"] >= self.max_losing_streak:
            reasons.append("LOSING_STREAK_BREACH")
        if paper["completed_trades"] >= self.min_completed_trades:
            if (
                paper["average_net_r"] is None
                or paper["average_net_r"] <= self.min_average_net_r
            ):
                reasons.append("AVERAGE_EXPECTANCY_BREACH")
            if (
                paper["recent_average_net_r"] is None
                or paper["recent_average_net_r"]
                <= self.min_recent_average_net_r
            ):
                reasons.append("RECENT_EXPECTANCY_BREACH")

        outcomes = self._baseline_outcomes()
        forward = self._forward_metrics(decisions, outcomes)
        if (
            forward["paired_independent_events"] >= self.min_paired_events
            and forward["average_r_lift"] is not None
            and forward["average_r_lift"] <= self.min_average_r_lift
        ):
            reasons.append("MATERIAL_CHAMPION_UNDERPERFORMANCE")
        if (
            forward["calibration_outcomes"] >= self.min_calibration_outcomes
            and forward["brier_score"] is not None
            and forward["brier_score"] > self.max_brier_score
        ):
            reasons.append("BRIER_SCORE_DETERIORATION")
        if (
            forward["calibration_outcomes"] >= self.min_calibration_outcomes
            and forward["maximum_calibration_gap"] is not None
            and forward["maximum_calibration_gap"]
            > self.max_calibration_gap
        ):
            reasons.append("CALIBRATION_GAP_DETERIORATION")

        drift = self._drift_metrics(decisions, scorer, record)
        if (
            drift["observations"] >= self.min_drift_observations
            and drift["maximum_feature_psi"] is not None
            and drift["maximum_feature_psi"] > self.max_feature_psi
        ):
            reasons.append("FEATURE_DRIFT_PSI_BREACH")

        reasons = list(dict.fromkeys(reasons))
        return {
            "schema_version": ROLLBACK_EVIDENCE_SCHEMA_VERSION,
            "model_id": model_id,
            "role": role,
            "benchmark_model_id": str(benchmark_model_id or ""),
            "started_at_ms": int(started_at_ms),
            "artifact_health": artifact_health,
            "runtime_health": runtime_health,
            "paper_performance": paper,
            "forward_comparison": forward,
            "feature_drift": drift,
            "rollback_required": bool(reasons),
            "reason_codes": reasons,
            "real_order_authority": "NONE",
        }

    def _artifact_health(self, model_id: str, record: dict):
        try:
            expected_schema = record.get("feature_schema_version")
            scorer = RegisteredModelArtifactScorer(
                model_id=model_id,
                artifact_path=str(record.get("artifact_path") or ""),
                expected_checksum_sha256=str(
                    record.get("artifact_checksum_sha256") or ""
                ) or None,
                expected_feature_schema_version=(
                    int(expected_schema) if expected_schema is not None else None
                ),
            )
            return ({
                "status": "HEALTHY",
                "reason_code": None,
                "feature_schema_version": scorer.feature_schema_version,
            }, scorer)
        except (RegisteredModelScoringError, ValueError, OSError) as exc:
            message = str(exc)
            if "SCHEMA" in message:
                reason = "FEATURE_SCHEMA_MISMATCH"
            elif "FEATURE_MISSING" in message:
                reason = "REQUIRED_FEATURE_MISSING"
            else:
                reason = "MODEL_ARTIFACT_UNAVAILABLE"
            return ({
                "status": "UNSAFE",
                "reason_code": reason,
                "error": f"{type(exc).__name__}:{message}",
            }, None)

    def _runtime_health(self, decisions: list[dict]) -> dict:
        failures = [row for row in decisions if row.get("health_failure_code")]
        prediction = [
            row for row in failures
            if row.get("health_failure_code") == "PREDICTION_FAILURE"
        ]
        required = [
            row for row in failures
            if row.get("health_failure_code") == "REQUIRED_FEATURE_MISSING"
        ]
        schema = [
            row for row in failures
            if row.get("health_failure_code") == "FEATURE_SCHEMA_MISMATCH"
        ]
        total = len(decisions)
        return {
            "model_evaluations": total,
            "successful_evaluations": total - len(failures),
            "prediction_failures": len(prediction),
            "prediction_failure_rate": len(prediction) / total if total else 0.0,
            "required_feature_failures": len(required),
            "schema_mismatch_failures": len(schema),
            "all_health_failures": len(failures),
        }

    def _paper_metrics(self, model_id: str, role: str, started_at_ms: int):
        authority = "PAPER_CANARY" if role == "PAPER_CANARY" else "PAPER_CHAMPION"
        rows = []
        for row in iter_paper_execution_evidence(self.trades_path):
            closed = int(row["closed_at_ms"])
            value = float(row["net_r"])
            if (
                closed < int(started_at_ms)
                or row.get("selection_authority") != authority
                or str(row.get("paper_canary_model_id") or "") != model_id
                or not math.isfinite(value)
            ):
                continue
            event = str(
                row.get("market_event_id")
                or row.get("decision_batch_id")
                or row.get("trade_id")
                or "UNKNOWN"
            )
            rows.append((closed, value, event))
        rows.sort(key=lambda item: (item[0], item[2]))
        values = [item[1] for item in rows]
        cumulative = peak = drawdown = 0.0
        losing = max_losing = 0
        for value in values:
            cumulative += value
            peak = max(peak, cumulative)
            drawdown = max(drawdown, peak - cumulative)
            if value < 0:
                losing += 1
                max_losing = max(max_losing, losing)
            else:
                losing = 0
        recent = values[-self.recent_trade_window:]
        return {
            "completed_trades": len(values),
            "independent_market_events": len({item[2] for item in rows}),
            "average_net_r": sum(values) / len(values) if values else None,
            "recent_trade_count": len(recent),
            "recent_average_net_r": sum(recent) / len(recent) if recent else None,
            "win_rate": (
                sum(1 for value in values if value > 0) / len(values)
                if values else None
            ),
            "maximum_drawdown_r": drawdown,
            "maximum_losing_streak": max_losing,
            "return_basis": "PAPER_NET_R_AFTER_FEES_AND_SLIPPAGE",
        }

    def _forward_metrics(self, decisions: list[dict], outcomes: dict[str, float]):
        paired_by_event: dict[str, list[float]] = defaultdict(list)
        calibration = []
        matched_raw = 0
        for row in decisions:
            model_candidate = str(
                row.get("evaluated_model_candidate_observation_id") or ""
            )
            benchmark_candidate = str(
                row.get("benchmark_candidate_observation_id") or ""
            )
            probability = row.get("evaluated_model_probability")
            model_r = outcomes.get(model_candidate)
            benchmark_r = outcomes.get(benchmark_candidate)
            if model_r is not None and benchmark_r is not None:
                event = str(
                    row.get("market_event_id")
                    or row.get("decision_batch_id")
                    or "UNKNOWN"
                )
                paired_by_event[event].append(model_r - benchmark_r)
                matched_raw += 1
            if model_r is not None and probability is not None:
                try:
                    p = float(probability)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(p) and 0.0 <= p <= 1.0:
                    calibration.append((p, 1.0 if model_r > 0 else 0.0))
        event_lifts = [sum(values) / len(values) for values in paired_by_event.values()]
        brier = (
            sum((p - label) ** 2 for p, label in calibration) / len(calibration)
            if calibration else None
        )
        gap = self._calibration_gap(calibration)
        return {
            "paired_raw_comparisons": matched_raw,
            "paired_independent_events": len(event_lifts),
            "average_r_lift": (
                sum(event_lifts) / len(event_lifts) if event_lifts else None
            ),
            "calibration_outcomes": len(calibration),
            "brier_score": brier,
            "maximum_calibration_gap": gap,
            "comparison_basis": "INDEPENDENT_MARKET_EVENT_VIRTUAL_NET_R",
        }

    def _drift_metrics(self, decisions: list[dict], scorer, record: dict):
        if scorer is None:
            return {
                "status": "UNAVAILABLE_ARTIFACT",
                "observations": 0,
                "maximum_feature_psi": None,
                "features": {},
            }
        snapshot_value = str(
            record.get("dataset_snapshot_path") or ""
        ).strip()
        if not snapshot_value:
            return {
                "status": "UNAVAILABLE_TRAINING_SNAPSHOT",
                "observations": 0,
                "maximum_feature_psi": None,
                "features": {},
            }
        snapshot = Path(snapshot_value)
        training_path = snapshot / "training_dataset.jsonl"
        if not training_path.is_file():
            return {
                "status": "UNAVAILABLE_TRAINING_SNAPSHOT",
                "observations": 0,
                "maximum_feature_psi": None,
                "features": {},
            }
        wanted = {
            str(row.get("evaluated_model_candidate_observation_id") or "")
            for row in decisions
        }
        observations = {
            str(row.get("candidate_observation_id") or ""): row
            for row in self._read_jsonl(self.observations_path)
            if str(row.get("candidate_observation_id") or "") in wanted
        }
        live_rows = list(observations.values())
        train_rows = self._read_jsonl(training_path)
        names = list(scorer.artifact["base_feature_names"]) + [
            "rule_score", "final_score"
        ]
        if scorer.artifact.get("requires_complete_market_context"):
            names.extend(
                scorer.artifact.get("context_feature_names")
                or CONTEXT_FEATURE_NAMES
            )
        report = {}
        for name in names:
            expected = self._column(train_rows, name)
            actual = self._column(live_rows, name)
            if len(expected) < 2 or len(actual) < 2:
                continue
            report[name] = self._psi(expected, actual)
        return {
            "status": "EVALUATED" if report else "INSUFFICIENT_DATA",
            "observations": len(live_rows),
            "training_rows": len(train_rows),
            "maximum_feature_psi": max(report.values()) if report else None,
            "features": {
                name: {"psi": value} for name, value in sorted(report.items())
            },
        }

    def _baseline_outcomes(self) -> dict[str, float]:
        result = {}
        for row in self._read_jsonl(self.outcomes_path):
            if row.get("outcome_type") != "VIRTUAL_TRADE":
                continue
            candidate_id = str(row.get("candidate_observation_id") or "")
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
            value = payload.get("net_exit_r", payload.get("exit_r"))
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if candidate_id and math.isfinite(value):
                result[candidate_id] = value
        return result

    def _calibration_gap(self, rows: list[tuple[float, float]]):
        if not rows:
            return None
        bins: list[list[tuple[float, float]]] = [
            [] for _ in range(self.calibration_bins)
        ]
        for probability, label in rows:
            index = min(self.calibration_bins - 1, int(probability * self.calibration_bins))
            bins[index].append((probability, label))
        gaps = []
        for bucket in bins:
            if bucket:
                mean_p = sum(item[0] for item in bucket) / len(bucket)
                mean_y = sum(item[1] for item in bucket) / len(bucket)
                gaps.append(abs(mean_p - mean_y))
        return max(gaps, default=0.0)

    @staticmethod
    def _column(rows: list[dict], name: str) -> list[float]:
        values = []
        for row in rows:
            if name in CONTEXT_FEATURE_NAMES:
                try:
                    value = float(
                        context_feature_mapping(
                            market_context_from_row(row)
                        )[name]
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            else:
                source = (
                    row
                    if name in {"rule_score", "final_score"}
                    else row.get("features")
                )
                if not isinstance(source, dict):
                    continue
                try:
                    value = float(source[name])
                except (KeyError, TypeError, ValueError):
                    continue
            if math.isfinite(value):
                values.append(value)
        return values

    def _psi(self, expected: list[float], actual: list[float]) -> float:
        ordered = sorted(expected)
        edges = []
        for index in range(1, self.drift_bins):
            position = int(index * len(ordered) / self.drift_bins)
            position = min(len(ordered) - 1, max(0, position))
            edges.append(ordered[position])
        edges = sorted(set(edges))
        expected_counts = [0] * (len(edges) + 1)
        actual_counts = [0] * (len(edges) + 1)
        for value in expected:
            expected_counts[self._bin_index(value, edges)] += 1
        for value in actual:
            actual_counts[self._bin_index(value, edges)] += 1
        result = 0.0
        for exp_count, act_count in zip(expected_counts, actual_counts):
            exp_pct = max(exp_count / len(expected), 1e-6)
            act_pct = max(act_count / len(actual), 1e-6)
            result += (act_pct - exp_pct) * math.log(act_pct / exp_pct)
        return float(result)

    @staticmethod
    def _bin_index(value: float, edges: list[float]) -> int:
        for index, edge in enumerate(edges):
            if value < edge:
                return index
        return len(edges)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        if not logical_jsonl_exists(path):
            return []
        rows = []
        for line in iter_jsonl_lines(path):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows
