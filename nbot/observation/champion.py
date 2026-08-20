from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .database import EvidenceDatabase
from .policies import CONTROL_POLICY_VERSION, ExitPolicyLab
from .selection import (
    BASELINE_SELECTORS,
    EntrySelectionLab,
    SELECTION_CONFIG,
    SELECTOR_BY_VERSION,
    SelectionConfig,
)


@dataclass(frozen=True)
class ChampionConfig:
    """Frozen V3.4.6 walk-forward Research Champion evaluation contract."""

    evaluation_version: str = "WALK_FORWARD_CHAMPION_V1"
    champion_version: str = "RESEARCH_CHAMPION_V1"
    selection_lab_version: str = "ENTRY_SELECTION_LAB_V1"
    candidate_selector_version: str = "RIDGE_EXPECTED_NET_R_V1"
    exit_policy_version: str = CONTROL_POLICY_VERSION
    candidate_min_train_events: int = 20
    min_validation_events: int = 20
    min_test_events: int = 20
    bootstrap_samples: int = 2000
    confidence_level: float = 0.95
    cost_stress_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    catastrophic_regime_mean_r: float = -1.0
    min_regime_events_for_gate: int = 3

    def validate(self) -> None:
        if self.evaluation_version != "WALK_FORWARD_CHAMPION_V1":
            raise ValueError("V3.4.6 initial evaluation is frozen as WALK_FORWARD_CHAMPION_V1")
        if self.champion_version != "RESEARCH_CHAMPION_V1":
            raise ValueError("V3.4.6 first champion ID is frozen as RESEARCH_CHAMPION_V1")
        if self.selection_lab_version != "ENTRY_SELECTION_LAB_V1":
            raise ValueError("V3.4.6 is tied to ENTRY_SELECTION_LAB_V1")
        if self.candidate_selector_version != "RIDGE_EXPECTED_NET_R_V1":
            raise ValueError("V3.4.6 V1 evaluates the frozen V3.4.5 ridge challenger")
        if self.exit_policy_version != "INTEGER_R_STEP_CONTROL":
            raise ValueError("V3.4.6 V1 pairs selection with the frozen V3.4.4 control reference")
        if self.candidate_min_train_events != 20:
            raise ValueError("V3.4.6 V1 is tied to the V3.4.5 20-event learned-selector warmup")
        if self.min_validation_events != 20 or self.min_test_events != 20:
            raise ValueError("V3.4.6 V1 freezes validation and final-test windows at 20 independent events each")
        if self.bootstrap_samples < 100:
            raise ValueError("bootstrap_samples must be at least 100")
        if not 0.5 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0.5 and 1.0")
        if self.cost_stress_multipliers != (1.0, 1.5, 2.0):
            raise ValueError("V3.4.6 initial cost stress multipliers are frozen")
        if self.catastrophic_regime_mean_r != -1.0:
            raise ValueError("V3.4.6 catastrophic regime floor is frozen at -1R mean")
        if self.min_regime_events_for_gate < 2:
            raise ValueError("min_regime_events_for_gate must be at least two")


CHAMPION_CONFIG = ChampionConfig()
CHAMPION_CONFIG.validate()

AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"
FINAL_STATUSES = {"PASS_RESEARCH_CHAMPION", "REJECT_RESEARCH_CHAMPION"}

CHAMPION_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_champion_sets (
    evaluation_version TEXT PRIMARY KEY,
    champion_version TEXT NOT NULL,
    selection_lab_version TEXT NOT NULL,
    candidate_selector_version TEXT NOT NULL,
    exit_policy_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (selection_lab_version) REFERENCES entry_selection_labs(lab_version),
    FOREIGN KEY (candidate_selector_version) REFERENCES entry_selector_sets(selector_version),
    FOREIGN KEY (exit_policy_version) REFERENCES exit_policy_sets(policy_version)
);

CREATE TABLE IF NOT EXISTS research_champion_evaluations (
    evaluation_version TEXT PRIMARY KEY,
    evaluated_at_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    candidate_scored_events INTEGER NOT NULL CHECK (candidate_scored_events >= 0),
    validation_event_count INTEGER NOT NULL CHECK (validation_event_count >= 0),
    test_event_count INTEGER NOT NULL CHECK (test_event_count >= 0),
    post_test_event_count INTEGER NOT NULL CHECK (post_test_event_count >= 0),
    benchmark_selector_version TEXT,
    source_digest TEXT NOT NULL,
    evaluation_json TEXT NOT NULL,
    evaluation_digest TEXT NOT NULL,
    FOREIGN KEY (evaluation_version) REFERENCES research_champion_sets(evaluation_version),
    FOREIGN KEY (benchmark_selector_version) REFERENCES entry_selector_sets(selector_version)
);

CREATE TABLE IF NOT EXISTS research_champions (
    champion_version TEXT PRIMARY KEY,
    evaluation_version TEXT NOT NULL UNIQUE,
    selector_version TEXT NOT NULL,
    exit_policy_version TEXT NOT NULL,
    promoted_at_ms INTEGER NOT NULL,
    authority TEXT NOT NULL CHECK (authority = 'RESEARCH_ONLY_NO_EXECUTION'),
    source_evaluation_digest TEXT NOT NULL,
    FOREIGN KEY (evaluation_version) REFERENCES research_champion_sets(evaluation_version),
    FOREIGN KEY (selector_version) REFERENCES entry_selector_sets(selector_version),
    FOREIGN KEY (exit_policy_version) REFERENCES exit_policy_sets(policy_version)
);
"""

RESEARCH_CHAMPION_TABLES = (
    "research_champion_sets",
    "research_champion_evaluations",
    "research_champions",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and value == 0.0:
        return 0.0
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(_normalize(value)).encode("utf-8")).hexdigest()


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    result = float(value)
    return 0.0 if result == 0.0 else result


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return None if losses <= 0 else gains / losses


def _max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _quantile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = quantile * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _bootstrap_mean_ci(
    values: list[float], *, samples: int, confidence: float, seed: str,
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    means: list[float] = []
    n = len(values)
    for sample_index in range(samples):
        total = 0.0
        for draw_index in range(n):
            raw = hashlib.sha256(f"{seed}|{sample_index}|{draw_index}".encode("utf-8")).digest()
            index = int.from_bytes(raw[:8], "big") % n
            total += values[index]
        means.append(total / n)
    alpha = (1.0 - confidence) / 2.0
    return _quantile(means, alpha), _quantile(means, 1.0 - alpha)


def _series_metrics(values: list[float], *, bootstrap_samples: int, confidence_level: float, seed: str) -> dict[str, Any]:
    low, high = _bootstrap_mean_ci(
        values, samples=bootstrap_samples, confidence=confidence_level, seed=seed,
    )
    return {
        "events": len(values),
        "mean_net_r": _mean(values),
        "median_net_r": _median(values),
        "win_rate": (sum(value > 0 for value in values) / len(values)) if values else None,
        "profit_factor": _profit_factor(values),
        "max_drawdown_r": _max_drawdown(values),
        "mean_ci_low": low,
        "mean_ci_high": high,
    }


def _direction_regime(feature_vector_json: str) -> str:
    vector = json.loads(feature_vector_json)
    side_sign = _f(vector.get("side_sign"), 1.0)
    btc_ret_1h = _f(vector.get("btc_ret_1h_side")) * side_sign
    breadth = (_f(vector.get("breadth_1h_side")) * side_sign + 1.0) / 2.0
    if btc_ret_1h > 0 and breadth >= 0.5:
        return "BULLISH"
    if btc_ret_1h < 0 and breadth < 0.5:
        return "BEARISH"
    return "MIXED"


def _volatility_regime(feature_vector_json: str, low_cut: float | None, high_cut: float | None) -> str:
    vector = json.loads(feature_vector_json)
    value = _f(vector.get("realized_vol_1h"))
    if low_cut is None or high_cut is None:
        return "UNKNOWN"
    if value <= low_cut:
        return "LOW"
    if value >= high_cut:
        return "HIGH"
    return "NORMAL"


def _chunks(values: list[int], parts: int) -> list[list[int]]:
    if not values:
        return []
    parts = min(parts, len(values))
    result: list[list[int]] = []
    for index in range(parts):
        start = index * len(values) // parts
        end = (index + 1) * len(values) // parts
        result.append(values[start:end])
    return [chunk for chunk in result if chunk]


@dataclass(frozen=True)
class ChampionEvaluationResult:
    evaluation_version: str
    status: str
    candidate_selector_version: str
    exit_policy_version: str
    candidate_scored_events: int
    validation_events: int
    test_events: int
    post_test_events: int
    benchmark_selector_version: str | None
    champion_version: str | None


class WalkForwardChampionEvaluator:
    """V3.4.6 research-only walk-forward champion gate over frozen V3.4.5 predictions."""

    def __init__(
        self,
        db: EvidenceDatabase,
        config: ChampionConfig | None = None,
        selection_config: SelectionConfig = SELECTION_CONFIG,
    ):
        self.db = db
        self.config = config or ChampionConfig()
        self.selection_config = selection_config
        self.config.validate()
        self.selection_config.validate()

    def definition(self) -> dict[str, Any]:
        return {
            "evaluation_version": self.config.evaluation_version,
            "champion_version": self.config.champion_version,
            "selection_lab_version": self.config.selection_lab_version,
            "candidate_selector_version": self.config.candidate_selector_version,
            "exit_policy_version": self.config.exit_policy_version,
            "validation_rule": f"FIRST_{self.config.min_validation_events}_FORWARD_SCORED_EVENTS",
            "final_test_rule": f"NEXT_{self.config.min_test_events}_FORWARD_SCORED_EVENTS_FROZEN_ONCE_AVAILABLE",
            "post_test_rule": "LATER_EVENTS_EXCLUDED_FROM_INITIAL_PROMOTION_GATE",
            "benchmark_rule": "STRONGEST_TRANSPARENT_BASELINE_BY_VALIDATION_SELECTED_MEAN_NET_R_TIE_LEXICAL",
            "candidate_parameters": "FROZEN_IN_V3_4_5_NO_FINAL_TEST_TUNING",
            "candidate_min_train_events": self.config.candidate_min_train_events,
            "independence_unit": "MARKET_EVENT_NOT_SYMBOL_ROW",
            "bootstrap": {
                "samples": self.config.bootstrap_samples,
                "confidence_level": self.config.confidence_level,
                "resample_unit": "MARKET_EVENT",
                "deterministic": True,
            },
            "cost_stress": {
                "multipliers": list(self.config.cost_stress_multipliers),
                "stress_component": "ROUNDTRIP_BASE_COST_ONLY_FUNDING_REMAINS_EXACT_HISTORY",
            },
            "promotion_gates": {
                "candidate_positive_expectancy": "FINAL_TEST_EVENT_BOOTSTRAP_MEAN_CI_LOW_GT_0",
                "lift_vs_benchmark": "FINAL_TEST_PAIRED_EVENT_LIFT_BOOTSTRAP_CI_LOW_GT_0",
                "selected_beats_rejected": "FINAL_TEST_SELECTED_MEAN_GT_REJECTED_MEAN",
                "ordered_buckets": "FINAL_TEST_TOP_GT_MIDDLE_GT_BOTTOM",
                "cost_stress": "FINAL_TEST_2X_BASE_COST_MEAN_NET_R_GT_0",
                "drawdown": "FINAL_TEST_CANDIDATE_MAX_DD_LE_BENCHMARK_MAX_DD",
                "date_stability": "BOTH_FINAL_TEST_HALVES_MEAN_NET_R_GT_0",
                "symbol_dependency": "LEAVE_MOST_SELECTED_SYMBOL_OUT_MEAN_NET_R_GT_0",
                "regime_catastrophe": (
                    f"NO_DIRECTION_OR_VOL_REGIME_WITH_AT_LEAST_{self.config.min_regime_events_for_gate}_EVENTS_"
                    f"HAS_MEAN_NET_R_LE_{self.config.catastrophic_regime_mean_r}"
                ),
                "winner_capture": "SELECTED_WINNER_MEAN_CAPTURE_GE_FINAL_TEST_CONTROL_WINNER_MEDIAN_CAPTURE",
                "initial_risk": "V3_4_4_CONTROL_REFERENCE_ONLY_NO_INITIAL_RISK_INCREASE",
                "data_integrity": "V3_4_5_SELECTION_AUDIT_CLEAN_AND_NO_TRAINING_LEAKAGE",
            },
            "authority": AUTHORITY,
        }

    def initialize(self) -> None:
        EntrySelectionLab(self.db, self.selection_config).initialize()
        self.config.validate()
        now_ms = int(time.time() * 1000)
        definition = self.definition()
        definition_hash = _digest(definition)
        with self.db.connection() as conn:
            conn.executescript(CHAMPION_SCHEMA)
            lab = conn.execute(
                "SELECT target_policy_version FROM entry_selection_labs WHERE lab_version=?",
                (self.config.selection_lab_version,),
            ).fetchone()
            if lab is None:
                raise RuntimeError("NBOT_V346_SELECTION_LAB_REQUIRED")
            if str(lab[0]) != self.config.exit_policy_version:
                raise RuntimeError("NBOT_V346_EXIT_POLICY_MISMATCH")
            selector = conn.execute(
                "SELECT lab_version, is_learned, definition_json FROM entry_selector_sets WHERE selector_version=?",
                (self.config.candidate_selector_version,),
            ).fetchone()
            if selector is None or selector[0] != self.config.selection_lab_version or int(selector[1]) != 1:
                raise RuntimeError("NBOT_V346_CANDIDATE_SELECTOR_MISMATCH")
            selector_definition = json.loads(str(selector[2]))
            selector_min_train = int(selector_definition.get("parameters", {}).get("min_train_events", -1))
            if selector_min_train != self.config.candidate_min_train_events:
                raise RuntimeError("NBOT_V346_TRAINING_WARMUP_MISMATCH")
            conn.execute(
                """
                INSERT OR IGNORE INTO research_champion_sets(
                    evaluation_version, champion_version, selection_lab_version,
                    candidate_selector_version, exit_policy_version,
                    definition_hash, definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.config.evaluation_version, self.config.champion_version,
                    self.config.selection_lab_version, self.config.candidate_selector_version,
                    self.config.exit_policy_version, definition_hash, _canonical_json(definition), now_ms,
                ),
            )
            stored = conn.execute(
                "SELECT champion_version, selection_lab_version, candidate_selector_version, exit_policy_version, definition_hash "
                "FROM research_champion_sets WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
            expected = (
                self.config.champion_version, self.config.selection_lab_version,
                self.config.candidate_selector_version, self.config.exit_policy_version, definition_hash,
            )
            if stored != expected:
                raise RuntimeError("NBOT_V346_EVALUATION_DEFINITION_MISMATCH")

    def _candidate_events(self, conn) -> list[int]:
        return [
            int(row[0]) for row in conn.execute(
                "SELECT DISTINCT event_open_ms FROM entry_selection_predictions "
                "WHERE lab_version=? AND selector_version=? ORDER BY event_open_ms",
                (self.config.selection_lab_version, self.config.candidate_selector_version),
            ).fetchall()
        ]

    def _windows(self, candidate_events: list[int]) -> tuple[list[int], list[int], list[int]]:
        v_end = self.config.min_validation_events
        t_end = v_end + self.config.min_test_events
        return candidate_events[:v_end], candidate_events[v_end:t_end], candidate_events[t_end:]

    def _selected_rows(self, conn, selector_version: str, events: list[int]) -> list[dict[str, Any]]:
        if not events:
            return []
        placeholders = ",".join("?" for _ in events)
        rows = conn.execute(
            f"""
            SELECT p.event_open_ms, p.symbol, p.side, p.score, p.prediction_digest,
                   p.trained_through_event_ms, p.training_event_count, p.model_digest,
                   e.target_net_r, e.target_net_return_frac, e.target_mfe_r, e.target_mae_r,
                   e.feature_vector_json, e.example_digest, e.source_policy_result_digest
            FROM entry_selection_predictions p
            JOIN entry_selection_examples e
              ON e.event_open_ms=p.event_open_ms AND e.symbol=p.symbol AND e.side=p.side AND e.lab_version=p.lab_version
            WHERE p.lab_version=? AND p.selector_version=? AND p.rank_in_event=1
              AND p.event_open_ms IN ({placeholders})
            ORDER BY p.event_open_ms
            """,
            (self.config.selection_lab_version, selector_version, *events),
        ).fetchall()
        names = (
            "event_open_ms", "symbol", "side", "score", "prediction_digest",
            "trained_through_event_ms", "training_event_count", "model_digest",
            "target_net_r", "target_net_return_frac", "target_mfe_r", "target_mae_r",
            "feature_vector_json", "example_digest", "source_policy_result_digest",
        )
        return [dict(zip(names, row)) for row in rows]

    def _all_prediction_rows(self, conn, selector_version: str, events: list[int]) -> list[dict[str, Any]]:
        if not events:
            return []
        placeholders = ",".join("?" for _ in events)
        rows = conn.execute(
            f"""
            SELECT p.event_open_ms, p.symbol, p.side, p.rank_in_event, p.score, p.prediction_digest,
                   e.target_net_r, e.example_digest
            FROM entry_selection_predictions p
            JOIN entry_selection_examples e
              ON e.event_open_ms=p.event_open_ms AND e.symbol=p.symbol AND e.side=p.side AND e.lab_version=p.lab_version
            WHERE p.lab_version=? AND p.selector_version=? AND p.event_open_ms IN ({placeholders})
            ORDER BY p.event_open_ms, p.rank_in_event
            """,
            (self.config.selection_lab_version, selector_version, *events),
        ).fetchall()
        names = ("event_open_ms", "symbol", "side", "rank_in_event", "score", "prediction_digest", "target_net_r", "example_digest")
        return [dict(zip(names, row)) for row in rows]

    def _baseline_validation(self, conn, validation_events: list[int]) -> tuple[dict[str, Any], str | None]:
        reports: dict[str, Any] = {}
        candidates: list[tuple[float, str]] = []
        for spec in BASELINE_SELECTORS:
            rows = self._selected_rows(conn, spec.selector_version, validation_events)
            values = [_f(row["target_net_r"]) for row in rows]
            reports[spec.selector_version] = _series_metrics(
                values,
                bootstrap_samples=self.config.bootstrap_samples,
                confidence_level=self.config.confidence_level,
                seed=f"{self.config.evaluation_version}|validation|{spec.selector_version}",
            )
            if len(rows) == len(validation_events) and values:
                candidates.append((statistics.fmean(values), spec.selector_version))
        strongest = None
        if len(validation_events) == self.config.min_validation_events and candidates:
            strongest = sorted(candidates, key=lambda item: (-item[0], item[1]))[0][1]
        return reports, strongest

    def _bucket_metrics(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_event: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            by_event.setdefault(int(row["event_open_ms"]), []).append(row)
        top: list[float] = []
        middle: list[float] = []
        bottom: list[float] = []
        rejected: list[float] = []
        for event in sorted(by_event):
            event_rows = sorted(by_event[event], key=lambda row: int(row["rank_in_event"]))
            n = len(event_rows)
            for index, row in enumerate(event_rows):
                target = _f(row["target_net_r"])
                if index > 0:
                    rejected.append(target)
                bucket = min(2, (index * 3) // n)
                (top if bucket == 0 else middle if bucket == 1 else bottom).append(target)
        top_mean, middle_mean, bottom_mean = _mean(top), _mean(middle), _mean(bottom)
        return {
            "top_mean_net_r": top_mean,
            "middle_mean_net_r": middle_mean,
            "bottom_mean_net_r": bottom_mean,
            "rejected_mean_net_r": _mean(rejected),
            "ordered_top_middle_bottom": bool(
                top_mean is not None and middle_mean is not None and bottom_mean is not None
                and top_mean > middle_mean > bottom_mean
            ),
        }

    def _cost_and_capture(self, conn, selected_rows: list[dict[str, Any]], test_events: list[int]) -> dict[str, Any]:
        selected_costs: list[tuple[float, float, float | None]] = []
        for row in selected_rows:
            source = conn.execute(
                "SELECT initial_risk_frac, roundtrip_base_cost_frac, net_r, capture_ratio, result_digest "
                "FROM exit_policy_results WHERE event_open_ms=? AND symbol=? AND side=? AND policy_version=?",
                (int(row["event_open_ms"]), str(row["symbol"]), str(row["side"]), self.config.exit_policy_version),
            ).fetchone()
            if source is None:
                continue
            initial_risk, base_cost, net_r, capture_ratio, result_digest = source
            if str(result_digest) != str(row["source_policy_result_digest"]):
                continue
            base_cost_r = _f(base_cost) / _f(initial_risk, 1.0)
            selected_costs.append((_f(net_r), base_cost_r, None if capture_ratio is None else _f(capture_ratio)))

        stress: dict[str, Any] = {}
        for multiplier in self.config.cost_stress_multipliers:
            values = [net_r - (float(multiplier) - 1.0) * base_cost_r for net_r, base_cost_r, _capture in selected_costs]
            stress[f"{multiplier:.1f}x"] = {
                "mean_net_r": _mean(values),
                "median_net_r": _median(values),
            }

        all_winner_capture: list[float] = []
        if test_events:
            placeholders = ",".join("?" for _ in test_events)
            all_winner_capture = [
                _f(row[0]) for row in conn.execute(
                    f"SELECT capture_ratio FROM exit_policy_results WHERE policy_version=? "
                    f"AND event_open_ms IN ({placeholders}) AND net_r>0 AND capture_ratio IS NOT NULL",
                    (self.config.exit_policy_version, *test_events),
                ).fetchall()
            ]
        selected_winner_capture = [capture for net_r, _cost, capture in selected_costs if net_r > 0 and capture is not None]
        return {
            "cost_stress": stress,
            "selected_source_rows": len(selected_costs),
            "selected_winner_capture_mean": _mean(selected_winner_capture),
            "control_winner_capture_median": _median(all_winner_capture),
            "capture_comparison_ready": bool(selected_winner_capture and all_winner_capture),
        }

    def _stability(self, selected_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> dict[str, Any]:
        values = [_f(row["target_net_r"]) for row in selected_rows]
        symbols = [str(row["symbol"]) for row in selected_rows]
        top_symbol = None
        concentration = 0.0
        leave_top_symbol_out_mean = None
        if symbols:
            counts = {symbol: symbols.count(symbol) for symbol in set(symbols)}
            top_symbol = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            concentration = counts[top_symbol] / len(symbols)
            leaveout = [_f(row["target_net_r"]) for row in selected_rows if str(row["symbol"]) != top_symbol]
            leave_top_symbol_out_mean = _mean(leaveout)

        midpoint = len(values) // 2
        first_half = values[:midpoint]
        second_half = values[midpoint:]

        validation_vols = [_f(json.loads(str(row["feature_vector_json"])).get("realized_vol_1h")) for row in validation_rows]
        low_cut = _quantile(validation_vols, 1.0 / 3.0)
        high_cut = _quantile(validation_vols, 2.0 / 3.0)

        direction: dict[str, list[float]] = {}
        volatility: dict[str, list[float]] = {}
        for row in selected_rows:
            value = _f(row["target_net_r"])
            direction.setdefault(_direction_regime(str(row["feature_vector_json"])), []).append(value)
            volatility.setdefault(_volatility_regime(str(row["feature_vector_json"]), low_cut, high_cut), []).append(value)

        def summarize(groups: dict[str, list[float]]) -> dict[str, Any]:
            return {
                key: {"events": len(group), "mean_net_r": _mean(group)}
                for key, group in sorted(groups.items())
            }

        covered = [
            group for group in list(direction.values()) + list(volatility.values())
            if len(group) >= self.config.min_regime_events_for_gate
        ]
        no_catastrophe = all(statistics.fmean(group) > self.config.catastrophic_regime_mean_r for group in covered)

        return {
            "max_selected_symbol_concentration": concentration,
            "most_selected_symbol": top_symbol,
            "leave_most_selected_symbol_out_mean_net_r": leave_top_symbol_out_mean,
            "first_half_mean_net_r": _mean(first_half),
            "second_half_mean_net_r": _mean(second_half),
            "validation_volatility_low_cut": low_cut,
            "validation_volatility_high_cut": high_cut,
            "direction_regimes": summarize(direction),
            "volatility_regimes": summarize(volatility),
            "covered_regime_groups": len(covered),
            "no_catastrophic_covered_regime": no_catastrophe,
        }

    def _walk_forward_blocks(
        self, candidate_by_event: dict[int, float], benchmark_by_event: dict[int, float], test_events: list[int],
    ) -> list[dict[str, Any]]:
        blocks = []
        for index, events in enumerate(_chunks(test_events, 4), 1):
            candidate = [candidate_by_event[event] for event in events if event in candidate_by_event]
            benchmark = [benchmark_by_event[event] for event in events if event in benchmark_by_event]
            paired = [candidate_by_event[event] - benchmark_by_event[event] for event in events if event in candidate_by_event and event in benchmark_by_event]
            blocks.append({
                "block": index,
                "start_event_ms": events[0],
                "end_event_ms": events[-1],
                "events": len(events),
                "candidate_mean_net_r": _mean(candidate),
                "benchmark_mean_net_r": _mean(benchmark),
                "mean_lift_r": _mean(paired),
            })
        return blocks

    def _source_digest(self, conn, validation_events: list[int], test_events: list[int]) -> str:
        events = validation_events + test_events
        if not events:
            return _digest({"events": []})
        placeholders = ",".join("?" for _ in events)
        selection_registration = conn.execute(
            "SELECT definition_hash FROM entry_selection_labs WHERE lab_version=?",
            (self.config.selection_lab_version,),
        ).fetchone()
        selector_registration = conn.execute(
            "SELECT definition_hash FROM entry_selector_sets WHERE selector_version=?",
            (self.config.candidate_selector_version,),
        ).fetchone()
        selector_versions = [self.config.candidate_selector_version] + [spec.selector_version for spec in BASELINE_SELECTORS]
        selector_placeholders = ",".join("?" for _ in selector_versions)
        prediction_builds = conn.execute(
            f"SELECT event_open_ms, selector_version, source_digest, prediction_digest, model_digest, trained_through_event_ms "
            f"FROM entry_selection_prediction_builds WHERE lab_version=? AND event_open_ms IN ({placeholders}) "
            f"AND selector_version IN ({selector_placeholders}) ORDER BY event_open_ms, selector_version",
            (self.config.selection_lab_version, *events, *selector_versions),
        ).fetchall()
        example_builds = conn.execute(
            f"SELECT event_open_ms, source_digest, example_digest FROM entry_selection_builds "
            f"WHERE lab_version=? AND event_open_ms IN ({placeholders}) ORDER BY event_open_ms",
            (self.config.selection_lab_version, *events),
        ).fetchall()
        selected_policy = []
        candidate_selected = self._selected_rows(conn, self.config.candidate_selector_version, events)
        for row in candidate_selected:
            source = conn.execute(
                "SELECT result_digest FROM exit_policy_results WHERE event_open_ms=? AND symbol=? AND side=? AND policy_version=?",
                (int(row["event_open_ms"]), str(row["symbol"]), str(row["side"]), self.config.exit_policy_version),
            ).fetchone()
            selected_policy.append([
                int(row["event_open_ms"]), str(row["symbol"]), str(row["side"]), None if source is None else str(source[0]),
            ])
        return _digest({
            "events": events,
            "selection_lab_definition_hash": None if selection_registration is None else str(selection_registration[0]),
            "candidate_selector_definition_hash": None if selector_registration is None else str(selector_registration[0]),
            "prediction_builds": [list(row) for row in prediction_builds],
            "example_builds": [list(row) for row in example_builds],
            "candidate_selected_policy": selected_policy,
        })

    def _compute(self, conn) -> dict[str, Any]:
        candidate_events = self._candidate_events(conn)
        validation_events, test_events, post_test_events = self._windows(candidate_events)
        final_window_complete = len(test_events) >= self.config.min_test_events
        evaluation_candidate_event_count = (
            self.config.min_validation_events + self.config.min_test_events
            if final_window_complete else len(candidate_events)
        )
        evaluation_post_test_count = 0 if final_window_complete else len(post_test_events)
        validation_candidate = self._selected_rows(conn, self.config.candidate_selector_version, validation_events)
        validation_values = [_f(row["target_net_r"]) for row in validation_candidate]
        baseline_validation, benchmark = self._baseline_validation(conn, validation_events)

        status = "WAIT_FOR_VALIDATION_EVIDENCE"
        if len(validation_events) >= self.config.min_validation_events:
            status = "WAIT_FOR_UNTOUCHED_TEST_EVIDENCE"

        evaluation: dict[str, Any] = {
            "evaluation_version": self.config.evaluation_version,
            "candidate_selector_version": self.config.candidate_selector_version,
            "exit_policy_version": self.config.exit_policy_version,
            "authority": AUTHORITY,
            "status": status,
            "candidate_scored_events": evaluation_candidate_event_count,
            "required_validation_events": self.config.min_validation_events,
            "required_test_events": self.config.min_test_events,
            "validation_events": validation_events,
            "test_events": test_events,
            "post_test_event_count": evaluation_post_test_count,
            "post_test_events_used_for_initial_gate": 0,
            "validation_candidate": _series_metrics(
                validation_values,
                bootstrap_samples=self.config.bootstrap_samples,
                confidence_level=self.config.confidence_level,
                seed=f"{self.config.evaluation_version}|validation|candidate",
            ),
            "validation_baselines": baseline_validation,
            "benchmark_selector_version": benchmark,
            "final_test": None,
            "promotion_gates": {},
            "champion_version": None,
            "notes": [
                "Independent proof unit is the market event, not symbol rows.",
                "Candidate and hyperparameters were frozen in V3.4.5 before the final V3.4.6 test window.",
                "The initial V3.4.6 final-test window is fixed to the next untouched events; later events do not change this first promotion decision.",
                "The V3.4.4 integer-R control is a reference exit policy, not an adaptive exit promotion.",
            ],
        }

        if len(validation_events) < self.config.min_validation_events or benchmark is None:
            evaluation["source_digest"] = self._source_digest(conn, validation_events, [])
            return evaluation

        test_candidate = self._selected_rows(conn, self.config.candidate_selector_version, test_events)
        test_benchmark = self._selected_rows(conn, benchmark, test_events)
        if len(test_events) < self.config.min_test_events:
            evaluation["source_digest"] = self._source_digest(conn, validation_events, test_events)
            evaluation["partial_test_events"] = len(test_events)
            return evaluation

        candidate_by_event = {int(row["event_open_ms"]): _f(row["target_net_r"]) for row in test_candidate}
        benchmark_by_event = {int(row["event_open_ms"]): _f(row["target_net_r"]) for row in test_benchmark}
        candidate_values = [candidate_by_event[event] for event in test_events if event in candidate_by_event]
        benchmark_values = [benchmark_by_event[event] for event in test_events if event in benchmark_by_event]
        paired_lifts = [candidate_by_event[event] - benchmark_by_event[event] for event in test_events if event in candidate_by_event and event in benchmark_by_event]

        candidate_metrics = _series_metrics(
            candidate_values,
            bootstrap_samples=self.config.bootstrap_samples,
            confidence_level=self.config.confidence_level,
            seed=f"{self.config.evaluation_version}|test|candidate",
        )
        benchmark_metrics = _series_metrics(
            benchmark_values,
            bootstrap_samples=self.config.bootstrap_samples,
            confidence_level=self.config.confidence_level,
            seed=f"{self.config.evaluation_version}|test|{benchmark}",
        )
        lift_low, lift_high = _bootstrap_mean_ci(
            paired_lifts,
            samples=self.config.bootstrap_samples,
            confidence=self.config.confidence_level,
            seed=f"{self.config.evaluation_version}|test|paired_lift|{benchmark}",
        )
        lift_metrics = {
            "events": len(paired_lifts),
            "mean_lift_r": _mean(paired_lifts),
            "median_lift_r": _median(paired_lifts),
            "mean_lift_ci_low": lift_low,
            "mean_lift_ci_high": lift_high,
            "candidate_better_event_rate": (sum(value > 0 for value in paired_lifts) / len(paired_lifts)) if paired_lifts else None,
        }
        bucket_metrics = self._bucket_metrics(self._all_prediction_rows(conn, self.config.candidate_selector_version, test_events))
        cost_capture = self._cost_and_capture(conn, test_candidate, test_events)
        stability = self._stability(test_candidate, validation_candidate)
        walk_forward = self._walk_forward_blocks(candidate_by_event, benchmark_by_event, test_events)

        training_leakage = sum(
            row["trained_through_event_ms"] is None or int(row["trained_through_event_ms"]) >= int(row["event_open_ms"])
            for row in validation_candidate + test_candidate
        )
        selection_audit = EntrySelectionLab(self.db, self.selection_config).audit()
        selection_audit_failures = 0 if bool(selection_audit.get("healthy")) else 1

        selected_mean = candidate_metrics["mean_net_r"]
        rejected_mean = bucket_metrics["rejected_mean_net_r"]
        stress_2x = cost_capture["cost_stress"].get("2.0x", {}).get("mean_net_r")
        capture_selected = cost_capture["selected_winner_capture_mean"]
        capture_control = cost_capture["control_winner_capture_median"]
        gates = {
            "candidate_positive_expectancy_ci": bool(candidate_metrics["mean_ci_low"] is not None and candidate_metrics["mean_ci_low"] > 0),
            "meaningful_lift_vs_frozen_benchmark_ci": bool(lift_low is not None and lift_low > 0),
            "selected_beats_rejected": bool(selected_mean is not None and rejected_mean is not None and selected_mean > rejected_mean),
            "ordered_top_middle_bottom": bool(bucket_metrics["ordered_top_middle_bottom"]),
            "two_x_base_cost_stress_positive": bool(stress_2x is not None and stress_2x > 0),
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
                cost_capture["capture_comparison_ready"]
                and capture_selected is not None and capture_control is not None and capture_selected >= capture_control
            ),
            "control_exit_reference_no_initial_risk_increase": True,
            "no_training_leakage": training_leakage == 0,
            "selection_data_integrity_clean": selection_audit_failures == 0,
            "complete_final_test_pairing": len(candidate_values) == self.config.min_test_events == len(benchmark_values) == len(paired_lifts),
        }
        passed = all(gates.values())
        status = "PASS_RESEARCH_CHAMPION" if passed else "REJECT_RESEARCH_CHAMPION"
        evaluation["status"] = status
        evaluation["promotion_gates"] = gates
        evaluation["champion_version"] = self.config.champion_version if passed else None
        evaluation["final_test"] = {
            "candidate": candidate_metrics,
            "benchmark": benchmark_metrics,
            "paired_lift": lift_metrics,
            "bucket_separation": bucket_metrics,
            "cost_and_capture": cost_capture,
            "stability": stability,
            "walk_forward_blocks": walk_forward,
            "training_leakage_rows": training_leakage,
            "selection_audit_failures": selection_audit_failures,
        }
        evaluation["source_digest"] = self._source_digest(conn, validation_events, test_events)
        return evaluation

    def evaluate(self, *, rebuild: bool = False) -> ChampionEvaluationResult:
        self.initialize()
        now_ms = int(time.time() * 1000)
        with self.db.connection() as conn:
            existing = conn.execute(
                "SELECT status, evaluation_json FROM research_champion_evaluations WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
            if existing is not None and str(existing[0]) in FINAL_STATUSES and not rebuild:
                evaluation = json.loads(str(existing[1]))
            else:
                evaluation = self._compute(conn)
                definition_hash = _digest(self.definition())
                source_digest = str(evaluation["source_digest"])
                payload = {key: value for key, value in evaluation.items() if key != "source_digest"}
                evaluation_json = _canonical_json(payload)
                evaluation_digest = _digest({
                    "definition_hash": definition_hash,
                    "source_digest": source_digest,
                    "evaluation": payload,
                })
                conn.execute(
                    """
                    INSERT INTO research_champion_evaluations(
                        evaluation_version, evaluated_at_ms, status, candidate_scored_events,
                        validation_event_count, test_event_count, post_test_event_count,
                        benchmark_selector_version, source_digest, evaluation_json, evaluation_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(evaluation_version) DO UPDATE SET
                        evaluated_at_ms=excluded.evaluated_at_ms,
                        status=excluded.status,
                        candidate_scored_events=excluded.candidate_scored_events,
                        validation_event_count=excluded.validation_event_count,
                        test_event_count=excluded.test_event_count,
                        post_test_event_count=excluded.post_test_event_count,
                        benchmark_selector_version=excluded.benchmark_selector_version,
                        source_digest=excluded.source_digest,
                        evaluation_json=excluded.evaluation_json,
                        evaluation_digest=excluded.evaluation_digest
                    """,
                    (
                        self.config.evaluation_version, now_ms, str(evaluation["status"]),
                        int(evaluation["candidate_scored_events"]), len(evaluation["validation_events"]),
                        len(evaluation["test_events"]), int(evaluation["post_test_event_count"]),
                        evaluation.get("benchmark_selector_version"), source_digest, evaluation_json, evaluation_digest,
                    ),
                )
                if rebuild:
                    conn.execute(
                        "DELETE FROM research_champions WHERE evaluation_version=?",
                        (self.config.evaluation_version,),
                    )
                if evaluation["status"] == "PASS_RESEARCH_CHAMPION":
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO research_champions(
                            champion_version, evaluation_version, selector_version, exit_policy_version,
                            promoted_at_ms, authority, source_evaluation_digest
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            self.config.champion_version, self.config.evaluation_version,
                            self.config.candidate_selector_version, self.config.exit_policy_version,
                            now_ms, AUTHORITY, evaluation_digest,
                        ),
                    )
                conn.commit()

        return ChampionEvaluationResult(
            self.config.evaluation_version,
            str(evaluation["status"]),
            self.config.candidate_selector_version,
            self.config.exit_policy_version,
            int(evaluation["candidate_scored_events"]),
            len(evaluation["validation_events"]),
            len(evaluation["test_events"]),
            int(evaluation["post_test_event_count"]),
            evaluation.get("benchmark_selector_version"),
            evaluation.get("champion_version"),
        )

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            candidate_events = self._candidate_events(conn)
            validation, test, post = self._windows(candidate_events)
            row = conn.execute(
                "SELECT status, candidate_scored_events, validation_event_count, test_event_count, post_test_event_count, "
                "benchmark_selector_version, evaluation_digest FROM research_champion_evaluations WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
            champion = conn.execute(
                "SELECT champion_version, selector_version, exit_policy_version, authority FROM research_champions WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
        return {
            "evaluation_version": self.config.evaluation_version,
            "candidate_selector_version": self.config.candidate_selector_version,
            "exit_policy_version": self.config.exit_policy_version,
            "candidate_scored_events": len(candidate_events),
            "required_validation_events": self.config.min_validation_events,
            "available_validation_events": len(validation),
            "required_test_events": self.config.min_test_events,
            "available_test_events": len(test),
            "post_test_events": len(post),
            "evaluation": row,
            "champion": champion,
            "authority": AUTHORITY,
        }

    def report(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT status, source_digest, evaluation_json, evaluation_digest FROM research_champion_evaluations WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
        if row is None:
            with self.db.connection() as conn:
                return self._compute(conn)
        payload = json.loads(str(row[2]))
        payload["source_digest"] = str(row[1])
        payload["evaluation_digest"] = str(row[3])
        return payload

    def audit(self) -> dict[str, Any]:
        """Read-only V3.4.6 evaluator/lineage audit."""

        definition_hash = _digest(self.definition())
        selection_audit = EntrySelectionLab(self.db, self.selection_config).audit()
        selection_failures = 0 if bool(selection_audit.get("healthy")) else 1
        policy_audit = ExitPolicyLab(self.db).audit()
        policy_failures = 0 if bool(policy_audit.get("healthy")) else 1
        counter_keys = (
            "selection_integrity_failures",
            "policy_integrity_failures",
            "definition_mismatch",
            "selection_lab_mismatch",
            "candidate_selector_mismatch",
            "exit_policy_mismatch",
            "evaluation_missing",
            "source_digest_mismatch",
            "evaluation_digest_mismatch",
            "window_mismatch",
            "benchmark_mismatch",
            "training_leakage",
            "missing_source_predictions",
            "selected_policy_digest_mismatches",
            "champion_without_pass",
            "champion_authority_mismatch",
            "champion_source_digest_mismatch",
            "unexpected_champion_rows",
        )
        report: dict[str, Any] = {
            "evaluation_version": self.config.evaluation_version,
            "authority": AUTHORITY,
            "missing_tables": (),
            **{key: 0 for key in counter_keys},
        }
        report["selection_integrity_failures"] = selection_failures
        report["policy_integrity_failures"] = policy_failures

        with self.db.connection() as conn:
            present = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing_tables = tuple(sorted(set(RESEARCH_CHAMPION_TABLES) - present))
            report["missing_tables"] = missing_tables
            if missing_tables:
                report["healthy"] = False
                return report

            set_row = conn.execute(
                "SELECT selection_lab_version, candidate_selector_version, exit_policy_version, definition_hash "
                "FROM research_champion_sets WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
            report["definition_mismatch"] = int(set_row is None or str(set_row[3]) != definition_hash)
            report["selection_lab_mismatch"] = int(
                set_row is None or str(set_row[0]) != self.config.selection_lab_version
            )
            report["candidate_selector_mismatch"] = int(
                set_row is None or str(set_row[1]) != self.config.candidate_selector_version
            )
            report["exit_policy_mismatch"] = int(
                set_row is None or str(set_row[2]) != self.config.exit_policy_version
            )

            row = conn.execute(
                "SELECT status, source_digest, evaluation_json, evaluation_digest, benchmark_selector_version "
                "FROM research_champion_evaluations WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
            if row is None:
                report["evaluation_missing"] = 1
                report["healthy"] = False
                return report

            stored_payload = json.loads(str(row[2]))
            computed = self._compute(conn)
            computed_source = str(computed["source_digest"])
            computed_payload = {key: value for key, value in computed.items() if key != "source_digest"}
            computed_digest = _digest({
                "definition_hash": definition_hash,
                "source_digest": computed_source,
                "evaluation": computed_payload,
            })
            report["source_digest_mismatch"] = int(str(row[1]) != computed_source)
            report["evaluation_digest_mismatch"] = int(
                str(row[3]) != computed_digest or stored_payload != computed_payload
            )
            report["window_mismatch"] = int(
                stored_payload.get("validation_events") != computed_payload.get("validation_events")
                or stored_payload.get("test_events") != computed_payload.get("test_events")
                or int(stored_payload.get("post_test_events_used_for_initial_gate", -1)) != 0
            )
            report["benchmark_mismatch"] = int(
                stored_payload.get("benchmark_selector_version")
                != computed_payload.get("benchmark_selector_version")
            )

            used_events = list(stored_payload.get("validation_events", [])) + list(
                stored_payload.get("test_events", [])
            )
            if used_events:
                placeholders = ",".join("?" for _ in used_events)
                report["training_leakage"] = int(conn.execute(
                    f"SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? AND selector_version=? "
                    f"AND event_open_ms IN ({placeholders}) AND "
                    "(trained_through_event_ms IS NULL OR trained_through_event_ms>=event_open_ms)",
                    (
                        self.config.selection_lab_version,
                        self.config.candidate_selector_version,
                        *used_events,
                    ),
                ).fetchone()[0])
                expected_prediction_rows = sum(
                    int(row_[0])
                    for row_ in conn.execute(
                        f"SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=? "
                        f"AND event_open_ms IN ({placeholders}) GROUP BY event_open_ms",
                        (self.config.selection_lab_version, *used_events),
                    ).fetchall()
                )
                actual_prediction_rows = int(conn.execute(
                    f"SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? "
                    f"AND selector_version=? AND event_open_ms IN ({placeholders})",
                    (
                        self.config.selection_lab_version,
                        self.config.candidate_selector_version,
                        *used_events,
                    ),
                ).fetchone()[0])
                report["missing_source_predictions"] = max(
                    0, expected_prediction_rows - actual_prediction_rows
                )

                selected = self._selected_rows(
                    conn, self.config.candidate_selector_version, used_events
                )
                mismatches = 0
                for selected_row in selected:
                    result = conn.execute(
                        "SELECT result_digest FROM exit_policy_results WHERE event_open_ms=? "
                        "AND symbol=? AND side=? AND policy_version=?",
                        (
                            int(selected_row["event_open_ms"]),
                            str(selected_row["symbol"]),
                            str(selected_row["side"]),
                            self.config.exit_policy_version,
                        ),
                    ).fetchone()
                    if result is None or str(result[0]) != str(
                        selected_row["source_policy_result_digest"]
                    ):
                        mismatches += 1
                report["selected_policy_digest_mismatches"] = mismatches

            champions = conn.execute(
                "SELECT champion_version, authority, source_evaluation_digest "
                "FROM research_champions WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchall()
            report["unexpected_champion_rows"] = max(0, len(champions) - 1)
            if champions:
                report["champion_without_pass"] = int(
                    str(row[0]) != "PASS_RESEARCH_CHAMPION"
                )
                report["champion_authority_mismatch"] = int(
                    str(champions[0][1]) != AUTHORITY
                )
                report["champion_source_digest_mismatch"] = int(
                    str(champions[0][2]) != str(row[3])
                )

        report["healthy"] = (
            not report["missing_tables"]
            and all(int(report[key]) == 0 for key in counter_keys)
        )
        return report
