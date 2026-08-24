"""V3.9 continuous challenger learning on permanent compact research memory.

The first V3.9 challenger deliberately stays simple and falsifiable.  It freezes
an immutable Ridge model artifact at the latest compact-memory cutoff and uses
one semantic capital-allocation rule: if the best predicted *after-cost* net R
is not positive, abstain.  The threshold is therefore exactly 0.0 and is not a
parameter tuned from validation/test evidence.

A challenger artifact has no execution authority.  Its first 20 mature events
after the training cutoff are validation; the next 20 are an untouched final
test.  Final window results are immutable and are evidence only -- this module
never creates a Research Champion or changes Execution permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import statistics
import time
from typing import Any

from .champion import (
    ChampionConfig,
    _bootstrap_mean_ci,
    _direction_regime,
    _mean,
    _median,
    _quantile,
    _series_metrics,
    _volatility_regime,
)
from .outcomes import FuturePathConfig
from .research_memory import RIDGE_COLUMNS, ResearchMemoryStore
from .selection import (
    BASELINE_SELECTORS,
    EntrySelectionLab,
    FEATURE_VECTOR_NAMES,
    RidgeSufficientStatistics,
    SELECTION_CONFIG,
    _digest as _selection_digest,
    _f,
    _ridge_score,
)


AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"
FRAMEWORK_VERSION = "V39_CONTINUOUS_CHALLENGER_V1"
CHALLENGER_FAMILY = "RIDGE_POSITIVE_EXPECTANCY_ABSTAIN_V1"
EVALUATOR_VERSION = "V39_FROZEN_FUTURE_20_20_V1"
MODEL_PREFIX = "v39:model:"
CHALLENGER_PREFIX = "v39:challenger:"
EVALUATION_PREFIX = "v39:evaluation:"
FINAL_EVALUATION_STATUSES = frozenset({"PASS_RESEARCH_GATE", "REJECT_RESEARCH_GATE"})


@dataclass(frozen=True)
class ChallengerConfig:
    framework_version: str = FRAMEWORK_VERSION
    challenger_family: str = CHALLENGER_FAMILY
    evaluator_version: str = EVALUATOR_VERSION
    underlying_selector_version: str = "RIDGE_EXPECTED_NET_R_V1"
    validation_events: int = 20
    test_events: int = 20
    prediction_threshold_net_r: float = 0.0
    min_test_trade_events: int = 5
    bootstrap_samples: int = 2000
    confidence_level: float = 0.95
    cost_stress_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    catastrophic_regime_mean_r: float = -1.0
    min_regime_events_for_gate: int = 3

    def validate(self) -> None:
        if self.framework_version != FRAMEWORK_VERSION:
            raise ValueError("NBOT_V391_FRAMEWORK_VERSION_IMMUTABLE")
        if self.challenger_family != CHALLENGER_FAMILY:
            raise ValueError("NBOT_V391_CHALLENGER_FAMILY_IMMUTABLE")
        if self.evaluator_version != EVALUATOR_VERSION:
            raise ValueError("NBOT_V391_EVALUATOR_VERSION_IMMUTABLE")
        if self.underlying_selector_version != "RIDGE_EXPECTED_NET_R_V1":
            raise ValueError("NBOT_V391_UNDERLYING_SELECTOR_IMMUTABLE")
        if self.validation_events != 20 or self.test_events != 20:
            raise ValueError("NBOT_V391_FUTURE_WINDOWS_IMMUTABLE")
        if self.prediction_threshold_net_r != 0.0:
            raise ValueError("NBOT_V391_POSITIVE_EXPECTANCY_THRESHOLD_IMMUTABLE")
        if self.min_test_trade_events != 5:
            raise ValueError("NBOT_V391_MIN_TEST_TRADES_IMMUTABLE")
        if self.bootstrap_samples != 2000 or self.confidence_level != 0.95:
            raise ValueError("NBOT_V391_CONFIDENCE_CONTRACT_IMMUTABLE")
        if self.cost_stress_multipliers != (1.0, 1.5, 2.0):
            raise ValueError("NBOT_V391_COST_STRESS_IMMUTABLE")
        if self.catastrophic_regime_mean_r != -1.0:
            raise ValueError("NBOT_V391_REGIME_FLOOR_IMMUTABLE")
        if self.min_regime_events_for_gate != 3:
            raise ValueError("NBOT_V391_REGIME_SAMPLE_IMMUTABLE")


CONFIG = ChallengerConfig()
CONFIG.validate()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index:index + size] for index in range(0, len(values), size)]


class ContinuousChallengerCycle:
    """Train one immutable challenger at a time and judge only future evidence."""

    def __init__(
        self,
        memory: ResearchMemoryStore,
        *,
        release_sha: str,
        config: ChallengerConfig = CONFIG,
    ) -> None:
        self.memory = memory
        self.release_sha = str(release_sha).strip()
        self.config = config
        self.config.validate()
        if len(self.release_sha) != 40 or any(ch not in "0123456789abcdef" for ch in self.release_sha.lower()):
            raise ValueError("NBOT_V391_RELEASE_SHA_INVALID")
        self.future_config = FuturePathConfig()
        self.future_config.validate()
        self.champion_config = ChampionConfig()
        self.champion_config.validate()

    def definition(self) -> dict[str, Any]:
        return {
            "framework_version": self.config.framework_version,
            "challenger_family": self.config.challenger_family,
            "evaluator_version": self.config.evaluator_version,
            "underlying_selector_version": self.config.underlying_selector_version,
            "training_source": "V3_8_4_PERMANENT_RESEARCH_MEMORY_RIDGE_STATE",
            "artifact_rule": "IMMUTABLE_MODEL_AND_CHALLENGER_ARTIFACTS",
            "selection_rule": {
                "rank": "HIGHEST_FROZEN_RIDGE_EXPECTED_AFTER_COST_NET_R",
                "trade_when": "TOP_PREDICTED_AFTER_COST_NET_R_GT_0",
                "abstain_when": "TOP_PREDICTED_AFTER_COST_NET_R_LE_0",
                "threshold": self.config.prediction_threshold_net_r,
                "threshold_tuning": False,
            },
            "validation_rule": f"FIRST_{self.config.validation_events}_MATURE_EVENTS_STRICTLY_AFTER_TRAINING_CUTOFF",
            "test_rule": f"NEXT_{self.config.test_events}_MATURE_EVENTS_FROZEN_FINAL_TEST",
            "benchmark_rule": "STRONGEST_TRANSPARENT_BASELINE_ON_VALIDATION_BY_MEAN_NET_R_TIE_LEXICAL",
            "abstention_accounting": "ZERO_R_FOR_EVENT_WHEN_NO_TRADE",
            "promotion": "NO_AUTOMATIC_CHAMPION_PROMOTION_WINDOW_EVIDENCE_ONLY",
            "bootstrap_samples": self.config.bootstrap_samples,
            "confidence_level": self.config.confidence_level,
            "cost_stress_multipliers": list(self.config.cost_stress_multipliers),
            "min_test_trade_events": self.config.min_test_trade_events,
            "authority": AUTHORITY,
        }

    @property
    def definition_hash(self) -> str:
        return _digest(self.definition())

    def _ridge_model_artifact(self) -> dict[str, Any]:
        history = self.memory.history_base()
        row = history.get("ridge_state_row")
        if row is None:
            raise RuntimeError("NBOT_V391_RIDGE_STATE_MISSING")
        mapped = dict(zip(RIDGE_COLUMNS, row))
        payload = json.loads(str(mapped["state_json"]))
        if _selection_digest(payload) != str(mapped["state_digest"]):
            raise RuntimeError("NBOT_V391_RIDGE_STATE_DIGEST_MISMATCH")
        state = RidgeSufficientStatistics.from_payload(payload)
        if (
            state.through_event_ms != mapped["through_event_ms"]
            or state.event_count != int(mapped["training_event_count"])
            or state.row_count != int(mapped["training_row_count"])
        ):
            raise RuntimeError("NBOT_V391_RIDGE_STATE_METADATA_MISMATCH")
        if (
            history["through_event_ms"] != state.through_event_ms
            or int(history["event_count"]) != state.event_count
            or int(history["row_count"]) != state.row_count
        ):
            raise RuntimeError("NBOT_V391_MEMORY_RIDGE_NOT_SYNCHRONIZED")
        if state.event_count < SELECTION_CONFIG.min_train_events:
            raise RuntimeError("NBOT_V391_INSUFFICIENT_TRAINING_EVENTS")
        model = state.fit(SELECTION_CONFIG.ridge_alpha)
        cutoff = int(state.through_event_ms)
        model_version = (
            f"V39_RIDGE_{cutoff}_{str(model['model_digest'])[:12]}"
        )
        artifact = {
            "artifact_type": "MODEL",
            "model_version": model_version,
            "model_family": "RIDGE_EXPECTED_NET_R_V1",
            "selector_version": self.config.underlying_selector_version,
            "training_cutoff_event_ms": cutoff,
            "training_event_count": state.event_count,
            "training_row_count": state.row_count,
            "training_source_digest": str(history["source_digest"]),
            "ridge_state_digest": str(mapped["state_digest"]),
            "model": model,
            "model_digest": str(model["model_digest"]),
            "feature_names": list(FEATURE_VECTOR_NAMES),
            "release_sha": self.release_sha,
            "authority": AUTHORITY,
        }
        return artifact

    def _train(self) -> dict[str, Any]:
        model_artifact = self._ridge_model_artifact()
        model_version = str(model_artifact["model_version"])
        cutoff = int(model_artifact["training_cutoff_event_ms"])
        model_record = self.memory.persist_artifact(
            f"{MODEL_PREFIX}{model_version}", model_artifact
        )
        challenger_version = (
            f"V39_ABSTAIN_{cutoff}_{model_record['artifact_digest'][:12]}"
        )
        challenger = {
            "artifact_type": "CHALLENGER",
            "challenger_version": challenger_version,
            "challenger_family": self.config.challenger_family,
            "framework_version": self.config.framework_version,
            "evaluator_version": self.config.evaluator_version,
            "model_version": model_version,
            "model_artifact_digest": model_record["artifact_digest"],
            "training_cutoff_event_ms": cutoff,
            "definition_hash": self.definition_hash,
            "definition": self.definition(),
            "release_sha": self.release_sha,
            "authority": AUTHORITY,
        }
        challenger_record = self.memory.persist_artifact(
            f"{CHALLENGER_PREFIX}{challenger_version}", challenger
        )
        return {
            "status": "TRAINED_WAIT_FOR_FUTURE_EVIDENCE",
            "authority": AUTHORITY,
            "challenger_version": challenger_version,
            "challenger_artifact_digest": challenger_record["artifact_digest"],
            "model_version": model_version,
            "model_artifact_digest": model_record["artifact_digest"],
            "training_cutoff_event_ms": cutoff,
            "training_event_count": model_artifact["training_event_count"],
            "training_row_count": model_artifact["training_row_count"],
            "required_validation_events": self.config.validation_events,
            "required_test_events": self.config.test_events,
            "automatic_promotion": False,
        }

    def _challenger_records(self) -> list[dict[str, Any]]:
        return self.memory.list_artifacts(prefix=CHALLENGER_PREFIX)

    def _evaluation_for(self, challenger_version: str) -> dict[str, Any] | None:
        return self.memory.artifact(f"{EVALUATION_PREFIX}{challenger_version}")

    def _active_challenger(self) -> dict[str, Any] | None:
        records = self._challenger_records()
        for record in reversed(records):
            payload = record["payload"]
            if self._evaluation_for(str(payload["challenger_version"])) is None:
                return record
        return None

    @staticmethod
    def _baseline_score(spec, example: dict[str, Any]) -> float:
        return EntrySelectionLab._baseline_score(spec, example)

    @staticmethod
    def _top_baseline(spec, examples: list[dict[str, Any]]) -> dict[str, Any]:
        scored = [(ContinuousChallengerCycle._baseline_score(spec, row), row) for row in examples]
        scored.sort(key=lambda item: (-item[0], str(item[1]["symbol"]), str(item[1]["side"])))
        score, row = scored[0]
        return {**row, "score": float(score)}

    def _top_candidate(self, model: dict[str, Any], examples: list[dict[str, Any]]) -> dict[str, Any]:
        scored = [(_ridge_score(model, str(row["feature_vector_json"])), row) for row in examples]
        scored.sort(key=lambda item: (-item[0], str(item[1]["symbol"]), str(item[1]["side"])))
        score, row = scored[0]
        traded = float(score) > self.config.prediction_threshold_net_r
        return {
            **row,
            "score": float(score),
            "traded": traded,
            "event_net_r": _f(row["target_net_r"]) if traded else 0.0,
        }

    @staticmethod
    def _bucket_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(rows, key=lambda row: (float(row["score"]), str(row["symbol"]), str(row["side"])))
        if len(ordered) < 3:
            return {
                "bottom_mean_net_r": None,
                "middle_mean_net_r": None,
                "top_mean_net_r": None,
                "ordered_top_middle_bottom": False,
            }
        third = max(1, len(ordered) // 3)
        bottom = ordered[:third]
        top = ordered[-third:]
        middle = ordered[third:-third]
        bottom_mean = _mean([_f(row["target_net_r"]) for row in bottom])
        middle_mean = _mean([_f(row["target_net_r"]) for row in middle])
        top_mean = _mean([_f(row["target_net_r"]) for row in top])
        return {
            "bottom_mean_net_r": bottom_mean,
            "middle_mean_net_r": middle_mean,
            "top_mean_net_r": top_mean,
            "ordered_top_middle_bottom": bool(
                bottom_mean is not None and middle_mean is not None and top_mean is not None
                and top_mean > middle_mean > bottom_mean
            ),
        }

    def _cost_stress(self, selected_by_event: dict[int, dict[str, Any]], test_events: list[int]) -> dict[str, Any]:
        rows: list[tuple[float, float, float | None]] = []
        for event in test_events:
            selected = selected_by_event[event]
            if not selected["traded"]:
                rows.append((0.0, 0.0, None))
                continue
            vector = json.loads(str(selected["feature_vector_json"]))
            risk_frac = _f(vector.get("atr14_frac"))
            if risk_frac <= 0:
                raise RuntimeError("NBOT_V391_SELECTED_RISK_UNIT_INVALID")
            spread_pct = _f(vector.get("spread_pct"))
            base_cost_frac = (
                2.0 * self.future_config.taker_fee_rate
                + (self.future_config.entry_slippage_bps + self.future_config.exit_slippage_bps) / 10_000.0
                + spread_pct / 100.0
            )
            net_r = _f(selected["target_net_r"])
            mfe_r = _f(selected["target_mfe_r"])
            capture = None if net_r <= 0 or mfe_r <= 0 else net_r / mfe_r
            rows.append((net_r, base_cost_frac / risk_frac, capture))
        stress: dict[str, Any] = {}
        for multiplier in self.config.cost_stress_multipliers:
            values = [net_r - (float(multiplier) - 1.0) * cost_r for net_r, cost_r, _ in rows]
            stress[f"{multiplier:.1f}x"] = {
                "mean_net_r": _mean(values),
                "median_net_r": _median(values),
            }
        selected_capture = [cap for net_r, _cost, cap in rows if net_r > 0 and cap is not None]
        return {
            "cost_stress": stress,
            "selected_winner_capture_mean": _mean(selected_capture),
            "trade_events": sum(1 for event in test_events if selected_by_event[event]["traded"]),
        }

    def _stability(
        self,
        selected_by_event: dict[int, dict[str, Any]],
        validation_selected: list[dict[str, Any]],
        test_events: list[int],
    ) -> dict[str, Any]:
        values = [float(selected_by_event[event]["event_net_r"]) for event in test_events]
        midpoint = len(values) // 2
        traded = [selected_by_event[event] for event in test_events if selected_by_event[event]["traded"]]
        symbols = [str(row["symbol"]) for row in traded]
        top_symbol = None
        concentration = 0.0
        leaveout_mean = None
        if symbols:
            counts = {symbol: symbols.count(symbol) for symbol in set(symbols)}
            top_symbol = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            concentration = counts[top_symbol] / len(symbols)
            leaveout_values = [
                float(selected_by_event[event]["event_net_r"])
                for event in test_events
                if not (
                    selected_by_event[event]["traded"]
                    and str(selected_by_event[event]["symbol"]) == top_symbol
                )
            ]
            leaveout_mean = _mean(leaveout_values)

        validation_vols = [
            _f(json.loads(str(row["feature_vector_json"])).get("realized_vol_1h"))
            for row in validation_selected
        ]
        low_cut = _quantile(validation_vols, 1.0 / 3.0)
        high_cut = _quantile(validation_vols, 2.0 / 3.0)
        direction: dict[str, list[float]] = {}
        volatility: dict[str, list[float]] = {}
        for event in test_events:
            row = selected_by_event[event]
            value = float(row["event_net_r"])
            direction.setdefault(_direction_regime(str(row["feature_vector_json"])), []).append(value)
            volatility.setdefault(
                _volatility_regime(str(row["feature_vector_json"]), low_cut, high_cut), []
            ).append(value)

        covered = [
            group for group in list(direction.values()) + list(volatility.values())
            if len(group) >= self.config.min_regime_events_for_gate
        ]
        no_catastrophe = all(
            statistics.fmean(group) > self.config.catastrophic_regime_mean_r for group in covered
        )
        summarize = lambda groups: {
            key: {"events": len(group), "mean_net_r": _mean(group)}
            for key, group in sorted(groups.items())
        }
        return {
            "first_half_mean_net_r": _mean(values[:midpoint]),
            "second_half_mean_net_r": _mean(values[midpoint:]),
            "most_selected_symbol": top_symbol,
            "max_selected_symbol_concentration": concentration,
            "leave_most_selected_symbol_out_mean_net_r": leaveout_mean,
            "validation_volatility_low_cut": low_cut,
            "validation_volatility_high_cut": high_cut,
            "direction_regimes": summarize(direction),
            "volatility_regimes": summarize(volatility),
            "covered_regime_groups": len(covered),
            "no_catastrophic_covered_regime": no_catastrophe,
        }

    def _evaluate(self, challenger_record: dict[str, Any]) -> dict[str, Any]:
        challenger = challenger_record["payload"]
        challenger_version = str(challenger["challenger_version"])
        model_record = self.memory.artifact(f"{MODEL_PREFIX}{challenger['model_version']}")
        if model_record is None:
            raise RuntimeError("NBOT_V391_MODEL_ARTIFACT_MISSING")
        if model_record["artifact_digest"] != challenger["model_artifact_digest"]:
            raise RuntimeError("NBOT_V391_MODEL_ARTIFACT_REFERENCE_MISMATCH")
        model_artifact = model_record["payload"]
        model = model_artifact["model"]
        cutoff = int(challenger["training_cutoff_event_ms"])
        records = list(self.memory.iter_event_records(after_event_ms=cutoff))
        required = self.config.validation_events + self.config.test_events
        if len(records) < required:
            return {
                "status": "WAIT_FOR_FUTURE_EVIDENCE",
                "authority": AUTHORITY,
                "challenger_version": challenger_version,
                "training_cutoff_event_ms": cutoff,
                "available_future_events": len(records),
                "required_future_events": required,
                "available_validation_events": min(len(records), self.config.validation_events),
                "available_test_events": max(0, min(len(records) - self.config.validation_events, self.config.test_events)),
                "automatic_promotion": False,
            }

        records = records[:required]
        validation_records = records[:self.config.validation_events]
        test_records = records[self.config.validation_events:]
        validation_events = [int(record["event_open_ms"]) for record in validation_records]
        test_events = [int(record["event_open_ms"]) for record in test_records]

        validation_candidate = [self._top_candidate(model, record["examples"]) for record in validation_records]
        baseline_reports: dict[str, Any] = {}
        candidates: list[tuple[float, str]] = []
        for spec in BASELINE_SELECTORS:
            rows = [self._top_baseline(spec, record["examples"]) for record in validation_records]
            values = [_f(row["target_net_r"]) for row in rows]
            metrics = _series_metrics(
                values,
                bootstrap_samples=self.config.bootstrap_samples,
                confidence_level=self.config.confidence_level,
                seed=f"{challenger_version}|validation|{spec.selector_version}",
            )
            baseline_reports[spec.selector_version] = metrics
            if metrics["events"] == self.config.validation_events and metrics["mean_net_r"] is not None:
                candidates.append((float(metrics["mean_net_r"]), spec.selector_version))
        if not candidates:
            raise RuntimeError("NBOT_V391_VALIDATION_BENCHMARK_UNAVAILABLE")
        candidates.sort(key=lambda item: (-item[0], item[1]))
        benchmark = candidates[0][1]
        benchmark_spec = next(spec for spec in BASELINE_SELECTORS if spec.selector_version == benchmark)

        selected_by_event: dict[int, dict[str, Any]] = {}
        benchmark_by_event: dict[int, dict[str, Any]] = {}
        all_scored_rows: list[dict[str, Any]] = []
        oracle_regret: list[float] = []
        for record in test_records:
            event = int(record["event_open_ms"])
            candidate = self._top_candidate(model, record["examples"])
            selected_by_event[event] = candidate
            benchmark_by_event[event] = self._top_baseline(benchmark_spec, record["examples"])
            scored_rows = []
            for row in record["examples"]:
                scored_rows.append({
                    **row,
                    "score": _ridge_score(model, str(row["feature_vector_json"])),
                })
            all_scored_rows.extend(scored_rows)
            oracle = max(_f(row["target_net_r"]) for row in record["examples"])
            oracle_regret.append(max(0.0, oracle - float(candidate["event_net_r"])))

        candidate_values = [float(selected_by_event[event]["event_net_r"]) for event in test_events]
        benchmark_values = [_f(benchmark_by_event[event]["target_net_r"]) for event in test_events]
        paired = [c - b for c, b in zip(candidate_values, benchmark_values)]
        candidate_metrics = _series_metrics(
            candidate_values,
            bootstrap_samples=self.config.bootstrap_samples,
            confidence_level=self.config.confidence_level,
            seed=f"{challenger_version}|test|candidate",
        )
        benchmark_metrics = _series_metrics(
            benchmark_values,
            bootstrap_samples=self.config.bootstrap_samples,
            confidence_level=self.config.confidence_level,
            seed=f"{challenger_version}|test|{benchmark}",
        )
        lift_low, lift_high = _bootstrap_mean_ci(
            paired,
            samples=self.config.bootstrap_samples,
            confidence=self.config.confidence_level,
            seed=f"{challenger_version}|test|paired|{benchmark}",
        )
        bucket = self._bucket_metrics(all_scored_rows)
        cost = self._cost_stress(selected_by_event, test_events)
        stability = self._stability(selected_by_event, validation_candidate, test_events)
        trade_events = int(cost["trade_events"])
        trade_captures = []
        all_winner_captures = []
        for record in test_records:
            for row in record["examples"]:
                net_r = _f(row["target_net_r"])
                mfe_r = _f(row["target_mfe_r"])
                if net_r > 0 and mfe_r > 0:
                    all_winner_captures.append(net_r / mfe_r)
        for event in test_events:
            row = selected_by_event[event]
            if not row["traded"]:
                continue
            net_r = _f(row["target_net_r"])
            mfe_r = _f(row["target_mfe_r"])
            if net_r > 0 and mfe_r > 0:
                trade_captures.append(net_r / mfe_r)
        selected_capture = _mean(trade_captures)
        control_capture = _median(all_winner_captures)
        cost["selected_winner_capture_mean"] = selected_capture
        cost["control_winner_capture_median"] = control_capture
        cost["capture_comparison_ready"] = bool(trade_captures and all_winner_captures)

        gates = {
            "minimum_trade_events": trade_events >= self.config.min_test_trade_events,
            "candidate_positive_expectancy_ci": bool(candidate_metrics["mean_ci_low"] is not None and candidate_metrics["mean_ci_low"] > 0),
            "meaningful_lift_vs_frozen_benchmark_ci": bool(lift_low is not None and lift_low > 0),
            "ordered_top_middle_bottom": bool(bucket["ordered_top_middle_bottom"]),
            "two_x_base_cost_stress_positive": bool(cost["cost_stress"]["2.0x"]["mean_net_r"] is not None and cost["cost_stress"]["2.0x"]["mean_net_r"] > 0),
            "drawdown_not_worse_than_benchmark": bool(candidate_metrics["max_drawdown_r"] <= benchmark_metrics["max_drawdown_r"]),
            "both_test_halves_positive": bool(
                stability["first_half_mean_net_r"] is not None and stability["first_half_mean_net_r"] > 0
                and stability["second_half_mean_net_r"] is not None and stability["second_half_mean_net_r"] > 0
            ),
            "not_dependent_on_most_selected_symbol": bool(
                stability["leave_most_selected_symbol_out_mean_net_r"] is not None
                and stability["leave_most_selected_symbol_out_mean_net_r"] > 0
            ),
            "no_catastrophic_covered_regime": bool(stability["no_catastrophic_covered_regime"]),
            "winner_capture_not_systematically_poor": bool(
                cost["capture_comparison_ready"] and selected_capture is not None
                and control_capture is not None and selected_capture >= control_capture
            ),
            "complete_final_test_pairing": len(candidate_values) == self.config.test_events == len(benchmark_values) == len(paired),
            "future_only_after_training_cutoff": min(validation_events + test_events) > cutoff,
            "authority_research_only": challenger.get("authority") == AUTHORITY == model_artifact.get("authority"),
            "no_automatic_promotion": True,
        }
        status = "PASS_RESEARCH_GATE" if all(gates.values()) else "REJECT_RESEARCH_GATE"
        source_digest = _digest({
            "challenger_artifact_digest": challenger_record["artifact_digest"],
            "model_artifact_digest": model_record["artifact_digest"],
            "events": [
                [int(record["event_open_ms"]), str(record["archive_digest"]), str(record["training_digest"])]
                for record in records
            ],
        })
        evaluation = {
            "artifact_type": "CHALLENGER_EVALUATION",
            "framework_version": self.config.framework_version,
            "evaluator_version": self.config.evaluator_version,
            "challenger_version": challenger_version,
            "challenger_family": self.config.challenger_family,
            "model_version": str(challenger["model_version"]),
            "training_cutoff_event_ms": cutoff,
            "validation_events": validation_events,
            "test_events": test_events,
            "benchmark_selector_version": benchmark,
            "status": status,
            "validation_candidate": _series_metrics(
                [float(row["event_net_r"]) for row in validation_candidate],
                bootstrap_samples=self.config.bootstrap_samples,
                confidence_level=self.config.confidence_level,
                seed=f"{challenger_version}|validation|candidate",
            ),
            "validation_baselines": baseline_reports,
            "final_test": {
                "candidate": candidate_metrics,
                "benchmark": benchmark_metrics,
                "paired_lift": {
                    "events": len(paired),
                    "mean_lift_r": _mean(paired),
                    "median_lift_r": _median(paired),
                    "mean_lift_ci_low": lift_low,
                    "mean_lift_ci_high": lift_high,
                    "candidate_better_event_rate": sum(value > 0 for value in paired) / len(paired),
                },
                "trade_utilization": {
                    "trade_events": trade_events,
                    "abstain_events": self.config.test_events - trade_events,
                    "utilization_rate": trade_events / self.config.test_events,
                },
                "selection_regret": {
                    "mean_oracle_regret_r": _mean(oracle_regret),
                    "median_oracle_regret_r": _median(oracle_regret),
                },
                "bucket_separation": bucket,
                "cost_and_capture": cost,
                "stability": stability,
                "walk_forward_blocks": [
                    {
                        "block": index,
                        "start_event_ms": block[0],
                        "end_event_ms": block[-1],
                        "events": len(block),
                        "candidate_mean_net_r": _mean([float(selected_by_event[event]["event_net_r"]) for event in block]),
                        "benchmark_mean_net_r": _mean([_f(benchmark_by_event[event]["target_net_r"]) for event in block]),
                    }
                    for index, block in enumerate(_chunks(test_events, 5), 1)
                ],
            },
            "promotion_gates": gates,
            "source_digest": source_digest,
            "release_sha": self.release_sha,
            "authority": AUTHORITY,
            "automatic_promotion": False,
        }
        evaluation_digest = _digest(evaluation)
        evaluation["evaluation_digest"] = evaluation_digest
        record = self.memory.persist_artifact(
            f"{EVALUATION_PREFIX}{challenger_version}", evaluation
        )
        return {
            "status": status,
            "authority": AUTHORITY,
            "challenger_version": challenger_version,
            "evaluation_artifact_digest": record["artifact_digest"],
            "evaluation_digest": evaluation_digest,
            "training_cutoff_event_ms": cutoff,
            "validation_events": self.config.validation_events,
            "test_events": self.config.test_events,
            "benchmark_selector_version": benchmark,
            "trade_events": trade_events,
            "automatic_promotion": False,
            "research_champion_created": False,
        }

    def cycle(self) -> dict[str, Any]:
        active = self._active_challenger()
        if active is None:
            return {
                "framework_version": self.config.framework_version,
                "action": "TRAIN",
                **self._train(),
            }
        evaluation = self._evaluate(active)
        if evaluation["status"] == "WAIT_FOR_FUTURE_EVIDENCE":
            return {
                "framework_version": self.config.framework_version,
                "action": "EVALUATE_WAIT",
                **evaluation,
            }
        # A final window is immutable.  Freeze the next daily artifact from the
        # latest available memory in the same cycle so rolling evidence can
        # continue without promoting anything automatically.
        next_training = self._train()
        return {
            "framework_version": self.config.framework_version,
            "action": "EVALUATE_FINAL_AND_TRAIN_NEXT",
            "evaluation": evaluation,
            "next_challenger": next_training,
            "authority": AUTHORITY,
            "automatic_promotion": False,
        }

    def status(self) -> dict[str, Any]:
        challengers = self._challenger_records()
        evaluations = self.memory.list_artifacts(prefix=EVALUATION_PREFIX)
        final_by_challenger = {
            str(record["payload"].get("challenger_version")): record for record in evaluations
        }
        active = self._active_challenger()
        latest = None if active is None else active["payload"]
        future = None
        if latest is not None:
            cutoff = int(latest["training_cutoff_event_ms"])
            count = sum(1 for _ in self.memory.iter_event_records(after_event_ms=cutoff))
            future = {
                "training_cutoff_event_ms": cutoff,
                "available_future_events": count,
                "required_future_events": self.config.validation_events + self.config.test_events,
                "available_validation_events": min(count, self.config.validation_events),
                "available_test_events": max(0, min(count - self.config.validation_events, self.config.test_events)),
            }
        statuses = [str(record["payload"].get("status")) for record in evaluations]
        return {
            "framework_version": self.config.framework_version,
            "challenger_family": self.config.challenger_family,
            "evaluator_version": self.config.evaluator_version,
            "authority": AUTHORITY,
            "challenger_artifacts": len(challengers),
            "evaluation_artifacts": len(evaluations),
            "passed_windows": statuses.count("PASS_RESEARCH_GATE"),
            "rejected_windows": statuses.count("REJECT_RESEARCH_GATE"),
            "active_challenger": latest,
            "active_future_evidence": future,
            "final_evaluations_by_challenger": sorted(final_by_challenger),
            "automatic_promotion": False,
        }

    def audit(self) -> dict[str, Any]:
        report = {
            "framework_version": self.config.framework_version,
            "authority": AUTHORITY,
            "artifact_reference_mismatch": 0,
            "authority_mismatch": 0,
            "definition_mismatch": 0,
            "future_window_violation": 0,
            "final_window_count_mismatch": 0,
            "automatic_promotion_violation": 0,
            "duplicate_active_challengers": 0,
        }
        challengers = self._challenger_records()
        unresolved = 0
        for record in challengers:
            payload = record["payload"]
            if payload.get("authority") != AUTHORITY:
                report["authority_mismatch"] += 1
            if payload.get("definition_hash") != self.definition_hash:
                report["definition_mismatch"] += 1
            model = self.memory.artifact(f"{MODEL_PREFIX}{payload.get('model_version')}")
            if model is None or model["artifact_digest"] != payload.get("model_artifact_digest"):
                report["artifact_reference_mismatch"] += 1
            evaluation = self._evaluation_for(str(payload.get("challenger_version")))
            if evaluation is None:
                unresolved += 1
                continue
            detail = evaluation["payload"]
            if detail.get("authority") != AUTHORITY:
                report["authority_mismatch"] += 1
            if detail.get("automatic_promotion") is not False:
                report["automatic_promotion_violation"] += 1
            validation = [int(v) for v in detail.get("validation_events", [])]
            test = [int(v) for v in detail.get("test_events", [])]
            cutoff = int(payload["training_cutoff_event_ms"])
            if validation + test and min(validation + test) <= cutoff:
                report["future_window_violation"] += 1
            if len(validation) != self.config.validation_events or len(test) != self.config.test_events:
                report["final_window_count_mismatch"] += 1
        report["duplicate_active_challengers"] = max(0, unresolved - 1)
        report["healthy"] = all(
            int(value) == 0
            for key, value in report.items()
            if key not in {"framework_version", "authority", "healthy"}
        )
        return report
