"""Deterministic exit-policy research laboratory for NBOT V3.4.4.

The lab compares one V2-equivalent control and seven challenger exit policies
on exactly the same mature V3.4.3 symbol/side paths.  It is research-only: it
has no entry selection, recommendation, communication, or order authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import statistics
import time
from typing import Any, Iterable

from .database import EvidenceDatabase
from .features import CANONICAL_FEATURE_VERSION
from .models import Candle
from .outcomes import OUTCOME_VERSION, RISK_UNIT_VERSION

LAB_VERSION = "EXIT_POLICY_LAB_V1"
CONTROL_POLICY_VERSION = "INTEGER_R_STEP_CONTROL"

RESULT_COLUMNS = (
    "event_open_ms", "symbol", "side", "feature_version", "outcome_version", "lab_version",
    "policy_version", "built_at_ms", "entry_price", "initial_risk_frac",
    "source_path_digest", "source_candle_digest", "exit_bar", "exit_time_ms",
    "exit_price", "exit_reason", "gross_return_frac", "gross_r",
    "funding_cost_frac", "roundtrip_base_cost_frac", "net_return_frac", "net_r",
    "mfe_r", "mae_r", "capture_ratio", "peak_favorable_r", "peak_giveback_r",
    "time_to_mfe_min", "holding_minutes", "post_exit_mfe_r", "missed_extension_r",
    "stop_updates", "stop_trace_json", "ambiguous_stop_bar", "result_digest",
)
RESULT_DIGEST_FIELDS = tuple(
    field for field in RESULT_COLUMNS if field not in {"built_at_ms", "result_digest"}
)

POLICY_SCHEMA = """
CREATE TABLE IF NOT EXISTS exit_policy_labs (
    lab_version TEXT PRIMARY KEY,
    outcome_version TEXT NOT NULL,
    catalog_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);
CREATE TABLE IF NOT EXISTS exit_policy_sets (
    policy_version TEXT PRIMARY KEY,
    lab_version TEXT NOT NULL,
    family TEXT NOT NULL,
    is_control INTEGER NOT NULL CHECK (is_control IN (0,1)),
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (lab_version) REFERENCES exit_policy_labs(lab_version)
);
CREATE TABLE IF NOT EXISTS exit_policy_results (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG','SHORT')),
    feature_version TEXT NOT NULL,
    outcome_version TEXT NOT NULL,
    lab_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    initial_risk_frac REAL NOT NULL,
    source_path_digest TEXT NOT NULL,
    source_candle_digest TEXT NOT NULL,
    exit_bar INTEGER NOT NULL,
    exit_time_ms INTEGER NOT NULL,
    exit_price REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    gross_return_frac REAL NOT NULL,
    gross_r REAL NOT NULL,
    funding_cost_frac REAL NOT NULL,
    roundtrip_base_cost_frac REAL NOT NULL,
    net_return_frac REAL NOT NULL,
    net_r REAL NOT NULL,
    mfe_r REAL NOT NULL,
    mae_r REAL NOT NULL,
    capture_ratio REAL,
    peak_favorable_r REAL NOT NULL,
    peak_giveback_r REAL NOT NULL,
    time_to_mfe_min INTEGER NOT NULL,
    holding_minutes INTEGER NOT NULL,
    post_exit_mfe_r REAL NOT NULL,
    missed_extension_r REAL NOT NULL,
    stop_updates INTEGER NOT NULL,
    stop_trace_json TEXT NOT NULL,
    ambiguous_stop_bar INTEGER NOT NULL CHECK (ambiguous_stop_bar IN (0,1)),
    result_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, side, policy_version, lab_version),
    FOREIGN KEY (event_open_ms, symbol, outcome_version)
        REFERENCES future_paths(event_open_ms, symbol, outcome_version) ON DELETE CASCADE,
    FOREIGN KEY (policy_version) REFERENCES exit_policy_sets(policy_version),
    FOREIGN KEY (lab_version) REFERENCES exit_policy_labs(lab_version)
);
CREATE TABLE IF NOT EXISTS exit_policy_builds (
    event_open_ms INTEGER NOT NULL,
    lab_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    eligible_path_count INTEGER NOT NULL,
    result_row_count INTEGER NOT NULL,
    source_digest TEXT NOT NULL,
    result_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, lab_version),
    FOREIGN KEY (lab_version) REFERENCES exit_policy_labs(lab_version)
);
CREATE INDEX IF NOT EXISTS idx_exit_policy_results_event
    ON exit_policy_results(event_open_ms, lab_version, policy_version);
"""


class ExitPolicyError(RuntimeError):
    """Policy definition, source lineage, or persistence is inconsistent."""


@dataclass(frozen=True)
class ExitPolicySpec:
    policy_version: str
    family: str
    is_control: bool
    description: str
    parameters: dict[str, Any]

    def definition(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "family": self.family,
            "is_control": self.is_control,
            "description": self.description,
            "parameters": self.parameters,
            "initial_risk": "EXACTLY_1X_V343_RISK_UNIT_NO_POLICY_MAY_WIDEN_IT",
            "decision_clock": "STOP_FOR_BAR_N_USES_INFORMATION_THROUGH_BAR_N_MINUS_1",
            "intrabar_stop_rule": "ACTIVE_STOP_HIT_USES_ADVERSE_GAP_FILL_ELSE_STOP_PRICE",
            "same_bar_path_rule": "FAVORABLE_EXTREME_ON_STOP_BAR_IS_NOT_ASSUMED_BEFORE_STOP",
            "horizon": "48_COMPLETED_5M_BARS",
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        }


POLICIES: tuple[ExitPolicySpec, ...] = (
    ExitPolicySpec(CONTROL_POLICY_VERSION, "INTEGER_R_STAIRCASE_CONTROL", True,
                   "Integer-R staircase retained only as the V3.4.4 control.",
                   {"activation_r": 1.0, "rule": "stop_r=floor(peak_r)-1 for peak_r>=1"}),
    ExitPolicySpec("CONTINUOUS_R_GIVEBACK_V1", "CONTINUOUS_R_GIVEBACK", False,
                   "Continuous one-R giveback from the favorable extreme after +1R.",
                   {"activation_r": 1.0, "giveback_r": 1.0}),
    ExitPolicySpec("ATR_VOLATILITY_TRAIL_V1", "ATR_VOLATILITY_TRAIL", False,
                   "Completed-bar volatility adjusts trail distance without widening initial risk.",
                   {"activation_r": 1.0, "tr_window_bars": 14, "tr_multiplier": 2.0,
                    "min_distance_r": 0.75, "max_distance_r": 2.0}),
    ExitPolicySpec("CHANDELIER_TRAIL_V1", "CHANDELIER_TRAIL", False,
                   "Chandelier-like 1.5R distance from the favorable extreme after +1R.",
                   {"activation_r": 1.0, "distance_r": 1.5}),
    ExitPolicySpec("STRUCTURE_TRAIL_V1", "STRUCTURE_TRAIL", False,
                   "Trail behind the last three completed bars with a 0.10R buffer.",
                   {"activation_r": 1.0, "lookback_bars": 3, "buffer_r": 0.10}),
    ExitPolicySpec("RUNNER_POLICY_V1", "RUNNER_POLICY", False,
                   "No trail until +2R, then allow 2R giveback.",
                   {"activation_r": 2.0, "giveback_r": 2.0}),
    ExitPolicySpec("STAGNATION_TIME_EXIT_V1", "STAGNATION_TIME_EXIT", False,
                   "One-R trail plus 60-minute exit when peak progress stays below +0.5R.",
                   {"activation_r": 1.0, "giveback_r": 1.0,
                    "stagnation_bar": 12, "minimum_peak_r": 0.5}),
    ExitPolicySpec("EXHAUSTION_TIGHTENING_V1", "EXHAUSTION_TIGHTENING", False,
                   "1.5R giveback tightened to 0.75R after a >=2R path closes >=0.5R off peak.",
                   {"activation_r": 1.0, "base_giveback_r": 1.5,
                    "exhaustion_peak_r": 2.0, "close_giveback_trigger_r": 0.5,
                    "tight_giveback_r": 0.75}),
)
POLICY_BY_VERSION = {policy.policy_version: policy for policy in POLICIES}


@dataclass(frozen=True)
class ExitPolicyConfig:
    lab_version: str = LAB_VERSION
    feature_version: str = CANONICAL_FEATURE_VERSION
    outcome_version: str = OUTCOME_VERSION
    risk_unit_version: str = RISK_UNIT_VERSION
    max_horizon_bars: int = 48

    def validate(self) -> None:
        if self.lab_version != LAB_VERSION:
            raise ValueError("NBOT_V344_LAB_VERSION_IMMUTABLE")
        if self.feature_version != CANONICAL_FEATURE_VERSION:
            raise ValueError("NBOT_V344_FEATURE_VERSION_IMMUTABLE")
        if self.outcome_version != OUTCOME_VERSION:
            raise ValueError("NBOT_V344_OUTCOME_VERSION_IMMUTABLE")
        if self.risk_unit_version != RISK_UNIT_VERSION:
            raise ValueError("NBOT_V344_RISK_UNIT_VERSION_IMMUTABLE")
        if self.max_horizon_bars != 48:
            raise ValueError("NBOT_V344_HORIZON_IMMUTABLE")


@dataclass(frozen=True)
class PolicyBuildResult:
    lab_version: str
    source_events: int
    source_paths: int
    risk_eligible_paths: int
    risk_ineligible_paths: int
    pending_build_events: int
    attempted_events: int
    built_events: int
    result_rows: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _rows_digest(rows: Iterable[dict[str, Any]], fields: tuple[str, ...]) -> str:
    payload = [[row.get(field) for field in fields] for row in sorted(
        rows, key=lambda item: (int(item["event_open_ms"]), str(item["symbol"]),
                                str(item["side"]), str(item["policy_version"]))) ]
    return _digest(payload)


_RESULT_INT_FIELDS = {"event_open_ms", "exit_bar", "exit_time_ms", "time_to_mfe_min",
                      "holding_minutes", "stop_updates", "ambiguous_stop_bar"}
_RESULT_FLOAT_FIELDS = {"entry_price", "initial_risk_frac", "exit_price", "gross_return_frac",
                        "gross_r", "funding_cost_frac", "roundtrip_base_cost_frac",
                        "net_return_frac", "net_r", "mfe_r", "mae_r", "capture_ratio",
                        "peak_favorable_r", "peak_giveback_r", "post_exit_mfe_r",
                        "missed_extension_r"}


def _result_digest(row: dict[str, Any]) -> str:
    values: list[Any] = []
    for field in RESULT_DIGEST_FIELDS:
        value = row[field]
        if field in _RESULT_INT_FIELDS:
            value = int(value)
        elif field in _RESULT_FLOAT_FIELDS:
            value = None if value is None else float(value)
            if value == 0.0:
                value = 0.0
        elif value is not None:
            value = str(value)
        values.append(value)
    return _digest(values)


def _signed_r(side: str, price: float, entry_price: float, risk_frac: float) -> float:
    return ((price / entry_price - 1.0) if side == "LONG" else
            (1.0 - price / entry_price)) / risk_frac


def _price_for_r(side: str, r_value: float, entry_price: float, risk_frac: float) -> float:
    return entry_price * (1.0 + r_value * risk_frac) if side == "LONG" else entry_price * (1.0 - r_value * risk_frac)


def _favorable_r(side: str, candle: Candle, entry_price: float, risk_frac: float) -> float:
    return _signed_r(side, candle.high_price if side == "LONG" else candle.low_price, entry_price, risk_frac)


def _stop_hit(side: str, candle: Candle, stop_price: float) -> bool:
    return candle.low_price <= stop_price if side == "LONG" else candle.high_price >= stop_price


def _stop_fill(side: str, candle: Candle, stop_price: float) -> float:
    if side == "LONG":
        return candle.open_price if candle.open_price <= stop_price else stop_price
    return candle.open_price if candle.open_price >= stop_price else stop_price


def _true_range_frac(candle: Candle, previous_close: float, entry_price: float) -> float:
    return max(candle.high_price - candle.low_price,
               abs(candle.high_price - previous_close),
               abs(candle.low_price - previous_close)) / entry_price


def _policy_stop_after_close(spec: ExitPolicySpec, *, side: str, current_stop_r: float,
                             peak_r: float, close_r: float, history: list[Candle],
                             tr_r_history: list[float], entry_price: float,
                             risk_frac: float) -> tuple[float, str | None]:
    p = spec.parameters
    proposed = current_stop_r
    reason: str | None = None
    if spec.policy_version == CONTROL_POLICY_VERSION:
        if peak_r >= float(p["activation_r"]):
            proposed, reason = math.floor(peak_r + 1e-12) - 1.0, "INTEGER_R_STEP"
    elif spec.policy_version == "CONTINUOUS_R_GIVEBACK_V1":
        if peak_r >= float(p["activation_r"]):
            proposed, reason = peak_r - float(p["giveback_r"]), "CONTINUOUS_GIVEBACK"
    elif spec.policy_version == "ATR_VOLATILITY_TRAIL_V1":
        if peak_r >= float(p["activation_r"]) and tr_r_history:
            window = tr_r_history[-int(p["tr_window_bars"]):]
            distance = float(p["tr_multiplier"]) * statistics.fmean(window)
            distance = max(float(p["min_distance_r"]), min(float(p["max_distance_r"]), distance))
            proposed, reason = peak_r - distance, "VOLATILITY_TRAIL"
    elif spec.policy_version == "CHANDELIER_TRAIL_V1":
        if peak_r >= float(p["activation_r"]):
            proposed, reason = peak_r - float(p["distance_r"]), "CHANDELIER_TRAIL"
    elif spec.policy_version == "STRUCTURE_TRAIL_V1":
        if peak_r >= float(p["activation_r"]):
            lookback = history[-int(p["lookback_bars"]):]
            if lookback:
                structure_price = (min(c.low_price for c in lookback) if side == "LONG"
                                   else max(c.high_price for c in lookback))
                proposed = _signed_r(side, structure_price, entry_price, risk_frac) - float(p["buffer_r"])
                reason = "STRUCTURE_TRAIL"
    elif spec.policy_version == "RUNNER_POLICY_V1":
        if peak_r >= float(p["activation_r"]):
            proposed, reason = peak_r - float(p["giveback_r"]), "RUNNER_GIVEBACK"
    elif spec.policy_version == "STAGNATION_TIME_EXIT_V1":
        if peak_r >= float(p["activation_r"]):
            proposed, reason = peak_r - float(p["giveback_r"]), "CONTINUOUS_GIVEBACK"
    elif spec.policy_version == "EXHAUSTION_TIGHTENING_V1":
        if peak_r >= float(p["activation_r"]):
            giveback = float(p["base_giveback_r"])
            if peak_r >= float(p["exhaustion_peak_r"]) and peak_r - close_r >= float(p["close_giveback_trigger_r"]):
                giveback, reason = float(p["tight_giveback_r"]), "EXHAUSTION_TIGHTEN"
            else:
                reason = "BASE_CHANDELIER"
            proposed = peak_r - giveback
    return max(current_stop_r, proposed), reason


def simulate_policy(*, spec: ExitPolicySpec, side: str, entry_price: float, risk_frac: float,
                    path: list[Candle], funding_events: list[dict[str, Any]],
                    roundtrip_base_cost_frac: float, full_mfe_frac: float,
                    full_mae_frac: float, time_to_mfe_min: int,
                    interval_minutes: int) -> dict[str, Any]:
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    if risk_frac <= 0 or not math.isfinite(risk_frac):
        raise ValueError("risk_frac must be positive and finite")
    if not path:
        raise ValueError("path must not be empty")
    stop_r, peak_r = -1.0, 0.0
    peak_before_exit_r = 0.0
    stop_trace: list[list[Any]] = [[0, -1.0, "INITIAL_RISK"]]
    stop_updates = 0
    tr_r_history: list[float] = []
    completed_history: list[Candle] = []
    previous_close = entry_price
    ambiguous_stop_bar = 0
    exit_bar, exit_price, exit_reason = len(path), path[-1].close_price, "HORIZON_4H"
    funding_cutoff_ms = path[-1].close_time_ms

    for bar_index, candle in enumerate(path, start=1):
        stop_price = _price_for_r(side, stop_r, entry_price, risk_frac)
        if _stop_hit(side, candle, stop_price):
            if _favorable_r(side, candle, entry_price, risk_frac) > peak_r + 1e-12:
                ambiguous_stop_bar = 1
            exit_bar, exit_price, exit_reason = bar_index, _stop_fill(side, candle, stop_price), "STOP"
            funding_cutoff_ms = candle.open_time_ms
            peak_before_exit_r = peak_r
            break
        favorable = _favorable_r(side, candle, entry_price, risk_frac)
        peak_r = max(peak_r, favorable)
        peak_before_exit_r = peak_r
        tr_r_history.append(_true_range_frac(candle, previous_close, entry_price) / risk_frac)
        completed_history.append(candle)
        previous_close = candle.close_price
        close_r = _signed_r(side, candle.close_price, entry_price, risk_frac)
        if spec.policy_version == "STAGNATION_TIME_EXIT_V1":
            p = spec.parameters
            if bar_index == int(p["stagnation_bar"]) and peak_r < float(p["minimum_peak_r"]):
                exit_bar, exit_price, exit_reason = bar_index, candle.close_price, "STAGNATION_60M"
                funding_cutoff_ms = candle.close_time_ms
                break
        new_stop_r, reason = _policy_stop_after_close(
            spec, side=side, current_stop_r=stop_r, peak_r=peak_r, close_r=close_r,
            history=completed_history, tr_r_history=tr_r_history,
            entry_price=entry_price, risk_frac=risk_frac)
        if new_stop_r > stop_r + 1e-12:
            if new_stop_r >= close_r - 1e-12:
                exit_bar, exit_price, exit_reason = bar_index, candle.close_price, "POLICY_CLOSE_TIGHTEN"
                funding_cutoff_ms = candle.close_time_ms
                stop_trace.append([bar_index, new_stop_r, reason or "TIGHTEN"])
                stop_updates += 1
                break
            stop_r = new_stop_r
            stop_trace.append([bar_index, stop_r, reason or "TIGHTEN"])
            stop_updates += 1

    gross_return_frac = (exit_price / entry_price - 1.0 if side == "LONG" else 1.0 - exit_price / entry_price)
    funding_sum = sum(float(row["funding_rate"]) for row in funding_events
                      if int(row["funding_time_ms"]) <= int(funding_cutoff_ms))
    funding_cost_frac = funding_sum if side == "LONG" else -funding_sum
    net_return_frac = gross_return_frac - roundtrip_base_cost_frac - funding_cost_frac
    gross_r, net_r = gross_return_frac / risk_frac, net_return_frac / risk_frac
    mfe_r, mae_r = max(0.0, full_mfe_frac / risk_frac), max(0.0, full_mae_frac / risk_frac)
    capture_ratio = None if net_r <= 0 or mfe_r <= 0 else net_r / mfe_r
    peak_giveback_r = max(0.0, peak_before_exit_r - gross_r)
    remaining = path[exit_bar:]
    post_exit_mfe_r = (max(0.0, max(_favorable_r(side, c, entry_price, risk_frac) for c in remaining))
                       if remaining else 0.0)
    return {
        "exit_bar": exit_bar, "exit_time_ms": int(path[exit_bar - 1].close_time_ms),
        "exit_price": exit_price, "exit_reason": exit_reason,
        "gross_return_frac": gross_return_frac, "gross_r": gross_r,
        "funding_cost_frac": funding_cost_frac,
        "roundtrip_base_cost_frac": roundtrip_base_cost_frac,
        "net_return_frac": net_return_frac, "net_r": net_r,
        "mfe_r": mfe_r, "mae_r": mae_r, "capture_ratio": capture_ratio,
        "peak_favorable_r": peak_before_exit_r, "peak_giveback_r": peak_giveback_r,
        "time_to_mfe_min": int(time_to_mfe_min), "holding_minutes": int(exit_bar * interval_minutes),
        "post_exit_mfe_r": post_exit_mfe_r,
        "missed_extension_r": max(0.0, mfe_r - max(gross_r, 0.0)),
        "stop_updates": stop_updates, "stop_trace_json": _canonical_json(stop_trace),
        "ambiguous_stop_bar": ambiguous_stop_bar,
    }


class ExitPolicyLab:
    """V3.4.4 policy-only research with no execution/recommendation authority."""
    def __init__(self, db: EvidenceDatabase, config: ExitPolicyConfig | None = None):
        self.db = db
        self.config = config or ExitPolicyConfig()
        self.config.validate()
        self.interval_ms = db.config.candle_interval_ms
        self.interval_minutes = self.interval_ms // 60_000

    def definition(self) -> dict[str, Any]:
        return {
            "lab_version": self.config.lab_version,
            "feature_version": self.config.feature_version,
            "outcome_version": self.config.outcome_version,
            "risk_unit_version": self.config.risk_unit_version,
            "policy_versions": [p.policy_version for p in POLICIES],
            "policy_definition_hashes": {p.policy_version: _digest(p.definition()) for p in POLICIES},
            "sides": ["LONG", "SHORT"],
            "initial_risk_rule": "ALL_POLICIES_START_MINUS_1R_AND_NEVER_WIDEN",
            "evaluation_target": "AFTER_COST_NET_R_AND_PROFIT_CAPTURE",
            "source_contract": "ONLY_V343_FUNDING_COMPLETE_PATHS_WITH_POSITIVE_RISK_UNIT",
            "authority": "RESEARCH_ONLY_NO_POLICY_PROMOTION_NO_EXECUTION",
        }

    @property
    def definition_hash(self) -> str:
        return _digest(self.definition())

    @property
    def policy_definition_hashes(self) -> dict[str, str]:
        return {p.policy_version: _digest(p.definition()) for p in POLICIES}

    def initialize(self) -> None:
        self.db.initialize()
        now_ms = int(time.time() * 1000)
        definition_json = _canonical_json(self.definition())
        with self.db.connection() as conn:
            # V3.4.3 must exist first.
            source = conn.execute("SELECT definition_hash FROM future_path_sets WHERE outcome_version=?",
                                  (self.config.outcome_version,)).fetchone()
            if source is None:
                raise ExitPolicyError("NBOT_V344_OUTCOME_DEFINITION_MISSING")
            conn.executescript(POLICY_SCHEMA)
            conn.execute("INSERT OR IGNORE INTO exit_policy_labs(lab_version,outcome_version,catalog_hash,definition_json,registered_at_ms) VALUES(?,?,?,?,?)",
                         (self.config.lab_version, self.config.outcome_version, self.definition_hash, definition_json, now_ms))
            stored = conn.execute("SELECT outcome_version,catalog_hash,definition_json FROM exit_policy_labs WHERE lab_version=?",
                                  (self.config.lab_version,)).fetchone()
            if stored != (self.config.outcome_version, self.definition_hash, definition_json):
                raise ExitPolicyError("NBOT_V344_LAB_DEFINITION_HASH_MISMATCH")
            for policy in POLICIES:
                pjson, phash = _canonical_json(policy.definition()), _digest(policy.definition())
                conn.execute("INSERT OR IGNORE INTO exit_policy_sets(policy_version,lab_version,family,is_control,definition_hash,definition_json,registered_at_ms) VALUES(?,?,?,?,?,?,?)",
                             (policy.policy_version, self.config.lab_version, policy.family, int(policy.is_control), phash, pjson, now_ms))
                row = conn.execute("SELECT lab_version,definition_hash,definition_json FROM exit_policy_sets WHERE policy_version=?",
                                   (policy.policy_version,)).fetchone()
                if row != (self.config.lab_version, phash, pjson):
                    raise ExitPolicyError(f"NBOT_V344_POLICY_DEFINITION_HASH_MISMATCH:{policy.policy_version}")

    def _eligible_clause(self) -> tuple[str, tuple[Any, ...]]:
        return ("feature_version=? AND outcome_version=? AND risk_unit_version=? "
                "AND risk_unit_frac IS NOT NULL AND risk_unit_frac>0 AND funding_complete=1",
                (self.config.feature_version, self.config.outcome_version, self.config.risk_unit_version))

    def _counts(self, conn) -> dict[str, int]:
        clause, params = self._eligible_clause()
        source_paths = int(conn.execute("SELECT COUNT(*) FROM future_paths WHERE outcome_version=?", (self.config.outcome_version,)).fetchone()[0])
        source_events = int(conn.execute("SELECT COUNT(DISTINCT event_open_ms) FROM future_paths WHERE outcome_version=?", (self.config.outcome_version,)).fetchone()[0])
        eligible_paths = int(conn.execute(f"SELECT COUNT(*) FROM future_paths WHERE {clause}", params).fetchone()[0])
        eligible_events = int(conn.execute(f"SELECT COUNT(DISTINCT event_open_ms) FROM future_paths WHERE {clause}", params).fetchone()[0])
        built_events = int(conn.execute("SELECT COUNT(*) FROM exit_policy_builds WHERE lab_version=?", (self.config.lab_version,)).fetchone()[0])
        result_rows = int(conn.execute("SELECT COUNT(*) FROM exit_policy_results WHERE lab_version=?", (self.config.lab_version,)).fetchone()[0])
        return {"source_paths": source_paths, "source_events": source_events,
                "risk_eligible_paths": eligible_paths, "risk_ineligible_paths": source_paths-eligible_paths,
                "eligible_events": eligible_events, "built_events": built_events,
                "result_rows": result_rows, "pending_build_events": max(0, eligible_events-built_events)}

    def _target_events(self, conn, limit: int, rebuild: bool) -> list[int]:
        clause, params = self._eligible_clause()
        sql = f"SELECT DISTINCT p.event_open_ms FROM future_paths p WHERE {clause} "
        values: list[Any] = list(params)
        if not rebuild:
            sql += "AND NOT EXISTS(SELECT 1 FROM exit_policy_builds b WHERE b.event_open_ms=p.event_open_ms AND b.lab_version=?) "
            values.append(self.config.lab_version)
        sql += "ORDER BY p.event_open_ms"
        if limit > 0:
            sql += " LIMIT ?"
            values.append(limit)
        return [int(r[0]) for r in conn.execute(sql, values)]

    def _load_sources(self, conn, event_open_ms: int) -> list[dict[str, Any]]:
        columns = ("event_open_ms", "symbol", "feature_version", "outcome_version", "entry_price", "risk_unit_version",
                   "risk_unit_frac", "funding_complete", "funding_events_json", "funding_source_digest",
                   "roundtrip_base_cost_frac", "long_mfe_frac", "long_mae_frac", "short_mfe_frac",
                   "short_mae_frac", "time_to_long_mfe_min", "time_to_short_mfe_min",
                   "source_candle_digest", "path_digest")
        clause, params = self._eligible_clause()
        rows = conn.execute(f"SELECT {','.join(columns)} FROM future_paths WHERE event_open_ms=? AND {clause} ORDER BY symbol",
                            (event_open_ms, *params)).fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def _load_path(self, conn, symbol: str, event_open_ms: int) -> list[Candle]:
        start_open = event_open_ms + self.interval_ms
        end_open = event_open_ms + self.config.max_horizon_bars * self.interval_ms
        cols = ("event_open_ms", "open_time_ms", "close_time_ms", "open_price", "high_price", "low_price",
                "close_price", "base_volume", "quote_volume", "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume")
        cached = conn.execute(f"SELECT {','.join(cols)} FROM future_candle_cache WHERE symbol=? AND event_open_ms BETWEEN ? AND ?",
                              (symbol, start_open, end_open)).fetchall()
        canonical = conn.execute(f"SELECT {','.join(cols)} FROM candles_5m WHERE symbol=? AND event_open_ms BETWEEN ? AND ?",
                                 (symbol, start_open, end_open)).fetchall()
        by_open: dict[int, tuple[Any, ...]] = {int(r[0]): r for r in cached}
        by_open.update({int(r[0]): r for r in canonical})
        required = [event_open_ms + i*self.interval_ms for i in range(1, self.config.max_horizon_bars+1)]
        if any(o not in by_open for o in required):
            return []
        return [Candle(symbol=symbol, open_time_ms=int(by_open[o][1]), close_time_ms=int(by_open[o][2]),
                       open_price=float(by_open[o][3]), high_price=float(by_open[o][4]), low_price=float(by_open[o][5]),
                       close_price=float(by_open[o][6]), base_volume=float(by_open[o][7]), quote_volume=float(by_open[o][8]),
                       trade_count=int(by_open[o][9]), taker_buy_base_volume=float(by_open[o][10]),
                       taker_buy_quote_volume=float(by_open[o][11])) for o in required]

    @staticmethod
    def _candle_digest(path: list[Candle]) -> str:
        return _digest([[c.open_time_ms,c.close_time_ms,c.open_price,c.high_price,c.low_price,c.close_price,
                         c.base_volume,c.quote_volume,c.trade_count,c.taker_buy_base_volume,c.taker_buy_quote_volume]
                        for c in path])

    def _event_source_digest_from_sources(self, sources: list[dict[str, Any]]) -> str:
        return _digest([[s["symbol"], s["feature_version"], s["path_digest"], s["source_candle_digest"], s["funding_source_digest"],
                         s["risk_unit_version"], s["risk_unit_frac"], s["roundtrip_base_cost_frac"]]
                        for s in sources])

    def _simulate_row(self, source: dict[str, Any], path: list[Candle], side: str,
                      policy: ExitPolicySpec, built_at_ms: int) -> dict[str, Any]:
        funding_events = json.loads(str(source["funding_events_json"]))
        if not isinstance(funding_events, list):
            raise ExitPolicyError("NBOT_V344_FUNDING_EVENTS_JSON_INVALID")
        full_mfe = float(source["long_mfe_frac"] if side == "LONG" else source["short_mfe_frac"])
        full_mae = float(source["long_mae_frac"] if side == "LONG" else source["short_mae_frac"])
        time_to_mfe = int(source["time_to_long_mfe_min"] if side == "LONG" else source["time_to_short_mfe_min"])
        sim = simulate_policy(spec=policy, side=side, entry_price=float(source["entry_price"]),
                              risk_frac=float(source["risk_unit_frac"]), path=path,
                              funding_events=funding_events,
                              roundtrip_base_cost_frac=float(source["roundtrip_base_cost_frac"]),
                              full_mfe_frac=full_mfe, full_mae_frac=full_mae,
                              time_to_mfe_min=time_to_mfe, interval_minutes=self.interval_minutes)
        row = {"event_open_ms": int(source["event_open_ms"]), "symbol": str(source["symbol"]), "side": side,
               "feature_version": str(source["feature_version"]),
               "outcome_version": str(source["outcome_version"]), "lab_version": self.config.lab_version,
               "policy_version": policy.policy_version, "built_at_ms": built_at_ms,
               "entry_price": float(source["entry_price"]), "initial_risk_frac": float(source["risk_unit_frac"]),
               "source_path_digest": str(source["path_digest"]),
               "source_candle_digest": str(source["source_candle_digest"]), **sim}
        row["result_digest"] = _result_digest(row)
        return row

    def build(self, *, max_events: int = 1, rebuild: bool = False) -> PolicyBuildResult:
        self.initialize()
        limit = int(max_events)
        if limit < 0:
            raise ValueError("NBOT_V344_MAX_EVENTS_INVALID")
        with self.db.connection() as conn:
            targets = self._target_events(conn, limit, rebuild)
        attempted = built = result_count = 0
        for event_open_ms in targets:
            attempted += 1
            with self.db.connection() as conn:
                sources = self._load_sources(conn, event_open_ms)
                source_digest = self._event_source_digest_from_sources(sources)
                paths = {str(s["symbol"]): self._load_path(conn, str(s["symbol"]), event_open_ms) for s in sources}
            rows: list[dict[str, Any]] = []
            built_at_ms = int(time.time() * 1000)
            for source in sources:
                path = paths[str(source["symbol"])]
                if len(path) != self.config.max_horizon_bars:
                    raise ExitPolicyError(f"NBOT_V344_SOURCE_PATH_MISSING:{event_open_ms}:{source['symbol']}")
                if self._candle_digest(path) != str(source["source_candle_digest"]):
                    raise ExitPolicyError(f"NBOT_V344_SOURCE_CANDLE_DIGEST_MISMATCH:{event_open_ms}:{source['symbol']}")
                for side in ("LONG", "SHORT"):
                    for policy in POLICIES:
                        rows.append(self._simulate_row(source, path, side, policy, built_at_ms))
            result_digest = _rows_digest(rows, ("event_open_ms","symbol","side","policy_version","result_digest"))
            with self.db.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                current_sources = self._load_sources(conn, event_open_ms)
                if self._event_source_digest_from_sources(current_sources) != source_digest:
                    raise ExitPolicyError(f"NBOT_V344_SOURCE_CHANGED_DURING_BUILD:{event_open_ms}")
                if not rebuild and conn.execute("SELECT 1 FROM exit_policy_builds WHERE event_open_ms=? AND lab_version=?",
                                                (event_open_ms,self.config.lab_version)).fetchone():
                    continue
                if rebuild:
                    conn.execute("DELETE FROM exit_policy_builds WHERE event_open_ms=? AND lab_version=?", (event_open_ms,self.config.lab_version))
                    conn.execute("DELETE FROM exit_policy_results WHERE event_open_ms=? AND lab_version=?", (event_open_ms,self.config.lab_version))
                placeholders = ",".join("?" for _ in RESULT_COLUMNS)
                conn.executemany(f"INSERT INTO exit_policy_results({','.join(RESULT_COLUMNS)}) VALUES({placeholders})",
                                 [[r[c] for c in RESULT_COLUMNS] for r in rows])
                conn.execute("INSERT INTO exit_policy_builds(event_open_ms,lab_version,built_at_ms,eligible_path_count,result_row_count,source_digest,result_digest) VALUES(?,?,?,?,?,?,?)",
                             (event_open_ms,self.config.lab_version,built_at_ms,len(sources),len(rows),source_digest,result_digest))
            built += 1
            result_count += len(rows)
        with self.db.connection() as conn:
            counts = self._counts(conn)
        return PolicyBuildResult(self.config.lab_version, counts["source_events"], counts["source_paths"],
                                 counts["risk_eligible_paths"], counts["risk_ineligible_paths"],
                                 counts["pending_build_events"], attempted, built, result_count)

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            counts = self._counts(conn)
            policy_counts = {str(v): int(n) for v,n in conn.execute(
                "SELECT policy_version,COUNT(*) FROM exit_policy_results WHERE lab_version=? GROUP BY policy_version ORDER BY policy_version",
                (self.config.lab_version,))}
        return {"lab_version": self.config.lab_version, "outcome_version": self.config.outcome_version,
                "policy_count": len(POLICIES), "control_policy": CONTROL_POLICY_VERSION,
                **counts, "policy_result_counts": policy_counts}

    def report(self) -> dict[str, Any]:
        self.initialize()
        report: dict[str, Any] = {"lab_version": self.config.lab_version,
            "authority": "RESEARCH_ONLY_NO_POLICY_PROMOTION_NO_EXECUTION",
            "comparison_note": "All policies use identical entries, sides, initial 1R, source paths and cost contract.",
            "policies": {}}
        with self.db.connection() as conn:
            raw = conn.execute("SELECT event_open_ms,symbol,side,policy_version,net_r,gross_r,capture_ratio,peak_giveback_r,holding_minutes,missed_extension_r FROM exit_policy_results WHERE lab_version=? ORDER BY event_open_ms,symbol,side,policy_version",
                               (self.config.lab_version,)).fetchall()
        control = {(int(e),str(s),str(side)): float(net) for e,s,side,p,net,*_ in raw if str(p)==CONTROL_POLICY_VERSION}
        grouped: dict[tuple[str,str], list[tuple[Any,...]]] = {}
        for row in raw:
            grouped.setdefault((str(row[3]),str(row[2])), []).append(row)
        for policy in POLICIES:
            for side in ("LONG","SHORT"):
                rows = grouped.get((policy.policy_version,side), [])
                key=f"{policy.policy_version}:{side}"
                if not rows:
                    report["policies"][key]={"rows":0}; continue
                net=[float(r[4]) for r in rows]; gross=[float(r[5]) for r in rows]
                captures=[float(r[6]) for r in rows if r[6] is not None]
                lifts=[float(r[4])-control[(int(r[0]),str(r[1]),str(r[2]))] for r in rows]
                by_event: dict[int,list[float]]={}
                lift_event: dict[int,list[float]]={}
                for r,lift in zip(rows,lifts):
                    by_event.setdefault(int(r[0]),[]).append(float(r[4])); lift_event.setdefault(int(r[0]),[]).append(lift)
                positives=sum(v for v in net if v>0); negatives=-sum(v for v in net if v<0)
                report["policies"][key]={"rows":len(rows), "independent_market_events":len(by_event),
                    "mean_net_r":statistics.fmean(net), "median_net_r":statistics.median(net),
                    "p05_net_r":sorted(net)[max(0,math.ceil(.05*len(net))-1)],
                    "win_rate":sum(v>0 for v in net)/len(net),
                    "profit_factor":None if negatives==0 else positives/negatives,
                    "mean_capture_ratio_winners":None if not captures else statistics.fmean(captures),
                    "mean_peak_giveback_r":statistics.fmean(float(r[7]) for r in rows),
                    "mean_holding_minutes":statistics.fmean(float(r[8]) for r in rows),
                    "mean_missed_extension_r":statistics.fmean(float(r[9]) for r in rows),
                    "mean_gross_r":statistics.fmean(gross),
                    "mean_net_r_lift_vs_control":statistics.fmean(lifts),
                    "median_net_r_lift_vs_control":statistics.median(lifts),
                    "paired_better_than_control_rate":sum(v>0 for v in lifts)/len(lifts),
                    "mean_event_net_r":statistics.fmean(statistics.fmean(v) for _,v in sorted(by_event.items())),
                    "mean_event_lift_vs_control":statistics.fmean(statistics.fmean(v) for _,v in sorted(lift_event.items())),
                    "positive_event_lift_rate":sum(statistics.fmean(v)>0 for v in lift_event.values())/len(lift_event)}
        return report

    def audit(self, *, event_open_ms: Iterable[int] | None = None) -> dict[str, Any]:
        audit_events = None if event_open_ms is None else tuple(sorted({int(v) for v in event_open_ms}))
        expected_policy_hashes = self.policy_definition_hashes
        required_tables = {
            "exit_policy_labs", "exit_policy_sets",
            "exit_policy_results", "exit_policy_builds",
        }
        with self.db.connection() as conn:
            present = {str(row[0]) for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            missing_tables = tuple(sorted(required_tables - present))
            if missing_tables:
                return {
                    "healthy": False,
                    "lab_version": self.config.lab_version,
                    "definition_hash": self.definition_hash,
                    "policy_count": len(POLICIES),
                    "missing_tables": missing_tables,
                }
            lab=conn.execute("SELECT catalog_hash,definition_json FROM exit_policy_labs WHERE lab_version=?",(self.config.lab_version,)).fetchone()
            lab_definition_mismatch=int(lab is None or lab!=(self.definition_hash,_canonical_json(self.definition())))
            actual={str(v):(str(h),str(j)) for v,h,j in conn.execute("SELECT policy_version,definition_hash,definition_json FROM exit_policy_sets WHERE lab_version=?",(self.config.lab_version,))}
            policy_definition_mismatches=sum(1 for p in POLICIES if actual.get(p.policy_version)!=(expected_policy_hashes[p.policy_version],_canonical_json(p.definition()))) + sum(1 for v in actual if v not in expected_policy_hashes)
            result_sql=f"SELECT {','.join(RESULT_COLUMNS)} FROM exit_policy_results WHERE lab_version=?"
            build_sql="SELECT event_open_ms,eligible_path_count,result_row_count,source_digest,result_digest FROM exit_policy_builds WHERE lab_version=?"
            result_params: list[Any] = [self.config.lab_version]
            build_params: list[Any] = [self.config.lab_version]
            if audit_events is not None:
                if audit_events:
                    placeholders = ",".join("?" for _ in audit_events)
                    result_sql += f" AND event_open_ms IN ({placeholders})"
                    build_sql += f" AND event_open_ms IN ({placeholders})"
                    result_params.extend(audit_events)
                    build_params.extend(audit_events)
                else:
                    result_sql += " AND 1=0"
                    build_sql += " AND 1=0"
            result_sql += " ORDER BY event_open_ms,symbol,side,policy_version"
            build_sql += " ORDER BY event_open_ms"
            result_rows=[dict(zip(RESULT_COLUMNS,row)) for row in conn.execute(result_sql, tuple(result_params))]
            builds=conn.execute(build_sql, tuple(build_params)).fetchall()
            result_events={int(r["event_open_ms"]) for r in result_rows}
            build_events={int(r[0]) for r in builds}
            results_without_build=sum(1 for r in result_rows if int(r["event_open_ms"]) not in build_events)
            source_path_mismatches = source_candle_digest_mismatches = 0
            initial_risk_mismatches = result_digest_mismatches = invalid_stop_traces = 0
            source_candle_checked: set[tuple[int, str]] = set()
            for r in result_rows:
                src=conn.execute("SELECT path_digest,source_candle_digest,risk_unit_frac FROM future_paths WHERE event_open_ms=? AND symbol=? AND outcome_version=?",
                                 (r["event_open_ms"],r["symbol"],self.config.outcome_version)).fetchone()
                if src is None or str(src[0])!=str(r["source_path_digest"]): source_path_mismatches+=1
                if src is None or str(src[1]) != str(r["source_candle_digest"]):
                    source_candle_digest_mismatches += 1
                source_key = (int(r["event_open_ms"]), str(r["symbol"]))
                if src is not None and source_key not in source_candle_checked:
                    current_path = self._load_path(
                        conn, str(r["symbol"]), int(r["event_open_ms"])
                    )
                    if (
                        len(current_path) != self.config.max_horizon_bars
                        or self._candle_digest(current_path) != str(src[1])
                    ):
                        source_candle_digest_mismatches += 1
                    source_candle_checked.add(source_key)
                if src is None or src[2] is None or abs(float(src[2])-float(r["initial_risk_frac"]))>1e-15: initial_risk_mismatches+=1
                if _result_digest(r)!=str(r["result_digest"]): result_digest_mismatches+=1
                try:
                    trace=json.loads(str(r["stop_trace_json"])); values=[float(item[1]) for item in trace]
                    if not values or abs(values[0]+1.0)>1e-12 or any(v < -1.0-1e-12 for v in values) or any(values[i] < values[i-1]-1e-12 for i in range(1,len(values))): invalid_stop_traces+=1
                except Exception: invalid_stop_traces+=1
            build_row_mismatches=build_source_digest_mismatches=build_result_digest_mismatches=policy_set_mismatches=0
            for event,eligible_count,row_count,source_digest,result_digest in builds:
                sources=self._load_sources(conn,int(event))
                rows=[r for r in result_rows if int(r["event_open_ms"])==int(event)]
                if int(eligible_count)!=len(sources) or int(row_count)!=len(rows): build_row_mismatches+=1
                if str(source_digest)!=self._event_source_digest_from_sources(sources): build_source_digest_mismatches+=1
                recomputed_rows = []
                for row in rows:
                    clone = dict(row)
                    clone["result_digest"] = _result_digest(row)
                    recomputed_rows.append(clone)
                if str(result_digest) != _rows_digest(
                    recomputed_rows,
                    ("event_open_ms", "symbol", "side", "policy_version", "result_digest"),
                ):
                    build_result_digest_mismatches += 1
                expected_keys={(str(s["symbol"]),side,p.policy_version) for s in sources for side in ("LONG","SHORT") for p in POLICIES}
                actual_keys={(str(r["symbol"]),str(r["side"]),str(r["policy_version"])) for r in rows}
                if expected_keys!=actual_keys: policy_set_mismatches+=1
            orphan_builds=sum(1 for event in build_events if not self._load_sources(conn,event))
            rows_without_source=sum(1 for r in result_rows if conn.execute("SELECT 1 FROM future_paths WHERE event_open_ms=? AND symbol=? AND outcome_version=?",(r["event_open_ms"],r["symbol"],self.config.outcome_version)).fetchone() is None)
            counts=self._counts(conn)
        counters={"lab_definition_mismatch":lab_definition_mismatch,
                  "policy_definition_mismatches":policy_definition_mismatches,
                  "results_without_build":results_without_build,
                  "rows_without_source":rows_without_source,
                  "orphan_builds":orphan_builds,
                  "source_path_mismatches":source_path_mismatches,
                  "source_candle_digest_mismatches":source_candle_digest_mismatches,
                  "initial_risk_mismatches":initial_risk_mismatches,
                  "result_digest_mismatches":result_digest_mismatches,
                  "invalid_stop_traces":invalid_stop_traces,
                  "build_row_mismatches":build_row_mismatches,
                  "build_source_digest_mismatches":build_source_digest_mismatches,
                  "build_result_digest_mismatches":build_result_digest_mismatches,
                  "policy_set_mismatches":policy_set_mismatches}
        return {
            "healthy": all(v == 0 for v in counters.values()),
            "audit_scope": "FULL_HISTORY" if audit_events is None else "SCOPED_EVENTS",
            "audit_event_count": 0 if audit_events is None else len(audit_events),
            "lab_version": self.config.lab_version,
            "definition_hash": self.definition_hash,
            "policy_count": len(POLICIES),
            "missing_tables": (),
            **counts,
            **counters,
        }
