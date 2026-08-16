from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .binance import Candle
from .config import ObserverConfig, PolicyConfig
from .db import EvidenceDB


RESULT_COLUMNS = (
    "event_open_ms",
    "symbol",
    "side",
    "feature_version",
    "outcome_version",
    "lab_version",
    "policy_version",
    "built_at_ms",
    "entry_price",
    "initial_risk_frac",
    "source_path_digest",
    "source_candle_digest",
    "exit_bar",
    "exit_time_ms",
    "exit_price",
    "exit_reason",
    "gross_return_frac",
    "gross_r",
    "funding_cost_frac",
    "roundtrip_base_cost_frac",
    "net_return_frac",
    "net_r",
    "mfe_r",
    "mae_r",
    "capture_ratio",
    "peak_favorable_r",
    "peak_giveback_r",
    "time_to_mfe_min",
    "holding_minutes",
    "post_exit_mfe_r",
    "missed_extension_r",
    "stop_updates",
    "stop_trace_json",
    "ambiguous_stop_bar",
    "result_digest",
)

RESULT_DIGEST_FIELDS = tuple(
    field for field in RESULT_COLUMNS if field not in {"built_at_ms", "result_digest"}
)


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
            "initial_risk": "EXACTLY_1X_V2_3_RISK_UNIT_NO_POLICY_MAY_WIDEN_IT",
            "decision_clock": "STOP_FOR_BAR_N_IS_FIXED_USING_INFORMATION_THROUGH_BAR_N_MINUS_1",
            "intrabar_stop_rule": "ACTIVE_STOP_HIT_USES_ADVERSE_GAP_FILL_ELSE_STOP_PRICE",
            "same_bar_path_rule": "FAVORABLE_EXTREME_ON_A_STOP_BAR_IS_NOT_ASSUMED_TO_PRECEDE_THE_STOP",
            "stop_exit_time_resolution": "5M_BAR_ONLY_HOLDING_USES_BAR_COUNT_AND_FUNDING_COUNTS_ONLY_EVENTS_AT_OR_BEFORE_STOP_BAR_OPEN",
            "horizon": "48_COMPLETED_5M_BARS",
        }


POLICIES: tuple[ExitPolicySpec, ...] = (
    ExitPolicySpec(
        "INTEGER_R_STEP_CONTROL",
        "INTEGER_R_STAIRCASE_CONTROL",
        True,
        "Integer-R staircase retained only as the V2.4 control.",
        {"activation_r": 1.0, "rule": "stop_r=floor(peak_r)-1 for peak_r>=1"},
    ),
    ExitPolicySpec(
        "CONTINUOUS_R_GIVEBACK_V1",
        "CONTINUOUS_R_GIVEBACK",
        False,
        "Continuous one-R giveback from the favorable extreme after +1R.",
        {"activation_r": 1.0, "giveback_r": 1.0},
    ),
    ExitPolicySpec(
        "ATR_VOLATILITY_TRAIL_V1",
        "ATR_VOLATILITY_TRAIL",
        False,
        "Completed-bar volatility adjusts trailing distance without widening initial risk.",
        {"activation_r": 1.0, "tr_window_bars": 14, "tr_multiplier": 2.0, "min_distance_r": 0.75, "max_distance_r": 2.0},
    ),
    ExitPolicySpec(
        "CHANDELIER_TRAIL_V1",
        "CHANDELIER_TRAIL",
        False,
        "Chandelier-like 1.5R distance from the favorable extreme after +1R.",
        {"activation_r": 1.0, "distance_r": 1.5},
    ),
    ExitPolicySpec(
        "STRUCTURE_TRAIL_V1",
        "STRUCTURE_TRAIL",
        False,
        "Trail behind the last three completed bars with a 0.10R buffer.",
        {"activation_r": 1.0, "lookback_bars": 3, "buffer_r": 0.10},
    ),
    ExitPolicySpec(
        "RUNNER_POLICY_V1",
        "RUNNER_POLICY",
        False,
        "Give strong paths room: no trailing until +2R, then allow 2R giveback.",
        {"activation_r": 2.0, "giveback_r": 2.0},
    ),
    ExitPolicySpec(
        "STAGNATION_TIME_EXIT_V1",
        "STAGNATION_TIME_EXIT",
        False,
        "Continuous one-R trail plus a 60-minute exit when peak progress stays below +0.5R.",
        {"activation_r": 1.0, "giveback_r": 1.0, "stagnation_bar": 12, "minimum_peak_r": 0.5},
    ),
    ExitPolicySpec(
        "EXHAUSTION_TIGHTENING_V1",
        "EXHAUSTION_TIGHTENING",
        False,
        "1.5R base giveback, tightened to 0.75R after a >=2R path closes >=0.5R off its peak.",
        {"activation_r": 1.0, "base_giveback_r": 1.5, "exhaustion_peak_r": 2.0, "close_giveback_trigger_r": 0.5, "tight_giveback_r": 0.75},
    ),
)

POLICY_BY_VERSION = {policy.policy_version: policy for policy in POLICIES}


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
    payload = [
        [row.get(field) for field in fields]
        for row in sorted(
            rows,
            key=lambda item: (
                int(item["event_open_ms"]),
                str(item["symbol"]),
                str(item["side"]),
                str(item["policy_version"]),
            ),
        )
    ]
    return _digest(payload)


_RESULT_INT_FIELDS = {
    "event_open_ms", "exit_bar", "exit_time_ms", "time_to_mfe_min",
    "holding_minutes", "stop_updates", "ambiguous_stop_bar",
}
_RESULT_FLOAT_FIELDS = {
    "entry_price", "initial_risk_frac", "exit_price", "gross_return_frac", "gross_r",
    "funding_cost_frac", "roundtrip_base_cost_frac", "net_return_frac", "net_r",
    "mfe_r", "mae_r", "capture_ratio", "peak_favorable_r", "peak_giveback_r",
    "post_exit_mfe_r", "missed_extension_r",
}


def _result_digest(row: dict[str, Any]) -> str:
    values: list[Any] = []
    for field in RESULT_DIGEST_FIELDS:
        value = row[field]
        if field in _RESULT_INT_FIELDS:
            value = int(value)
        elif field in _RESULT_FLOAT_FIELDS:
            if value is None:
                value = None
            else:
                value = float(value)
                # SQLite REAL normalizes -0.0 to +0.0. Canonicalize signed
                # zero before hashing so pre-insert and post-read digests match.
                if value == 0.0:
                    value = 0.0
        elif value is not None:
            value = str(value)
        values.append(value)
    return _digest(values)


def _signed_r(side: str, price: float, entry_price: float, risk_frac: float) -> float:
    if side == "LONG":
        return (price / entry_price - 1.0) / risk_frac
    return (1.0 - price / entry_price) / risk_frac


def _price_for_r(side: str, r_value: float, entry_price: float, risk_frac: float) -> float:
    if side == "LONG":
        return entry_price * (1.0 + r_value * risk_frac)
    return entry_price * (1.0 - r_value * risk_frac)


def _favorable_r(side: str, candle: Candle, entry_price: float, risk_frac: float) -> float:
    price = candle.high_price if side == "LONG" else candle.low_price
    return _signed_r(side, price, entry_price, risk_frac)


def _adverse_r(side: str, candle: Candle, entry_price: float, risk_frac: float) -> float:
    price = candle.low_price if side == "LONG" else candle.high_price
    return _signed_r(side, price, entry_price, risk_frac)


def _stop_hit(side: str, candle: Candle, stop_price: float) -> bool:
    return candle.low_price <= stop_price if side == "LONG" else candle.high_price >= stop_price


def _stop_fill(side: str, candle: Candle, stop_price: float) -> float:
    if side == "LONG":
        return candle.open_price if candle.open_price <= stop_price else stop_price
    return candle.open_price if candle.open_price >= stop_price else stop_price


def _true_range_frac(candle: Candle, previous_close: float, entry_price: float) -> float:
    return max(
        candle.high_price - candle.low_price,
        abs(candle.high_price - previous_close),
        abs(candle.low_price - previous_close),
    ) / entry_price


def _policy_stop_after_close(
    spec: ExitPolicySpec,
    *,
    side: str,
    bar_index: int,
    current_stop_r: float,
    peak_r: float,
    close_r: float,
    history: list[Candle],
    tr_r_history: list[float],
    entry_price: float,
    risk_frac: float,
) -> tuple[float, str | None]:
    p = spec.parameters
    proposed = current_stop_r
    reason: str | None = None

    if spec.policy_version == "INTEGER_R_STEP_CONTROL":
        if peak_r >= float(p["activation_r"]):
            proposed = math.floor(peak_r + 1e-12) - 1.0
            reason = "INTEGER_R_STEP"

    elif spec.policy_version == "CONTINUOUS_R_GIVEBACK_V1":
        if peak_r >= float(p["activation_r"]):
            proposed = peak_r - float(p["giveback_r"])
            reason = "CONTINUOUS_GIVEBACK"

    elif spec.policy_version == "ATR_VOLATILITY_TRAIL_V1":
        if peak_r >= float(p["activation_r"]) and tr_r_history:
            window = tr_r_history[-int(p["tr_window_bars"]):]
            distance = float(p["tr_multiplier"]) * statistics.fmean(window)
            distance = max(float(p["min_distance_r"]), min(float(p["max_distance_r"]), distance))
            proposed = peak_r - distance
            reason = "VOLATILITY_TRAIL"

    elif spec.policy_version == "CHANDELIER_TRAIL_V1":
        if peak_r >= float(p["activation_r"]):
            proposed = peak_r - float(p["distance_r"])
            reason = "CHANDELIER_TRAIL"

    elif spec.policy_version == "STRUCTURE_TRAIL_V1":
        if peak_r >= float(p["activation_r"]):
            lookback = history[-int(p["lookback_bars"]):]
            if lookback:
                if side == "LONG":
                    structure_price = min(candle.low_price for candle in lookback)
                else:
                    structure_price = max(candle.high_price for candle in lookback)
                proposed = _signed_r(side, structure_price, entry_price, risk_frac) - float(p["buffer_r"])
                reason = "STRUCTURE_TRAIL"

    elif spec.policy_version == "RUNNER_POLICY_V1":
        if peak_r >= float(p["activation_r"]):
            proposed = peak_r - float(p["giveback_r"])
            reason = "RUNNER_GIVEBACK"

    elif spec.policy_version == "STAGNATION_TIME_EXIT_V1":
        if peak_r >= float(p["activation_r"]):
            proposed = peak_r - float(p["giveback_r"])
            reason = "CONTINUOUS_GIVEBACK"

    elif spec.policy_version == "EXHAUSTION_TIGHTENING_V1":
        if peak_r >= float(p["activation_r"]):
            giveback = float(p["base_giveback_r"])
            if (
                peak_r >= float(p["exhaustion_peak_r"])
                and peak_r - close_r >= float(p["close_giveback_trigger_r"])
            ):
                giveback = float(p["tight_giveback_r"])
                reason = "EXHAUSTION_TIGHTEN"
            else:
                reason = "BASE_CHANDELIER"
            proposed = peak_r - giveback

    return max(current_stop_r, proposed), reason


def simulate_policy(
    *,
    spec: ExitPolicySpec,
    side: str,
    event_open_ms: int,
    entry_price: float,
    risk_frac: float,
    path: list[Candle],
    funding_events: list[dict[str, Any]],
    roundtrip_base_cost_frac: float,
    full_mfe_frac: float,
    full_mae_frac: float,
    time_to_mfe_min: int,
    interval_minutes: int,
) -> dict[str, Any]:
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    if risk_frac <= 0 or not math.isfinite(risk_frac):
        raise ValueError("risk_frac must be positive and finite")
    if not path:
        raise ValueError("path must not be empty")

    stop_r = -1.0
    peak_r = 0.0
    peak_before_exit_r = 0.0
    stop_trace: list[list[Any]] = [[0, -1.0, "INITIAL_RISK"]]
    stop_updates = 0
    tr_r_history: list[float] = []
    completed_history: list[Candle] = []
    previous_close = entry_price
    ambiguous_stop_bar = 0

    exit_bar = len(path)
    exit_price = path[-1].close_price
    exit_reason = "HORIZON_4H"
    funding_cutoff_ms = path[-1].close_time_ms

    for bar_index, candle in enumerate(path, start=1):
        stop_price = _price_for_r(side, stop_r, entry_price, risk_frac)
        if _stop_hit(side, candle, stop_price):
            # With OHLC only, if this same bar also extends the favorable peak,
            # ordering is unknowable. Do not pretend the favorable move happened first.
            if _favorable_r(side, candle, entry_price, risk_frac) > peak_r + 1e-12:
                ambiguous_stop_bar = 1
            exit_bar = bar_index
            exit_price = _stop_fill(side, candle, stop_price)
            exit_reason = "STOP"
            funding_cutoff_ms = candle.open_time_ms
            peak_before_exit_r = peak_r
            break

        favorable = _favorable_r(side, candle, entry_price, risk_frac)
        peak_r = max(peak_r, favorable)
        peak_before_exit_r = peak_r
        tr_frac = _true_range_frac(candle, previous_close, entry_price)
        tr_r_history.append(tr_frac / risk_frac)
        completed_history.append(candle)
        previous_close = candle.close_price
        close_r = _signed_r(side, candle.close_price, entry_price, risk_frac)

        if spec.policy_version == "STAGNATION_TIME_EXIT_V1":
            p = spec.parameters
            if bar_index == int(p["stagnation_bar"]) and peak_r < float(p["minimum_peak_r"]):
                exit_bar = bar_index
                exit_price = candle.close_price
                exit_reason = "STAGNATION_60M"
                funding_cutoff_ms = candle.close_time_ms
                break

        new_stop_r, update_reason = _policy_stop_after_close(
            spec,
            side=side,
            bar_index=bar_index,
            current_stop_r=stop_r,
            peak_r=peak_r,
            close_r=close_r,
            history=completed_history,
            tr_r_history=tr_r_history,
            entry_price=entry_price,
            risk_frac=risk_frac,
        )
        if new_stop_r > stop_r + 1e-12:
            # If a completed-bar rule tightens beyond the closing price, a real
            # stop could not be placed there for the next bar. Exit at this close.
            if new_stop_r >= close_r - 1e-12:
                exit_bar = bar_index
                exit_price = candle.close_price
                exit_reason = "POLICY_CLOSE_TIGHTEN"
                funding_cutoff_ms = candle.close_time_ms
                stop_trace.append([bar_index, new_stop_r, update_reason or "TIGHTEN"])
                stop_updates += 1
                break
            stop_r = new_stop_r
            stop_trace.append([bar_index, stop_r, update_reason or "TIGHTEN"])
            stop_updates += 1

        if bar_index == len(path):
            exit_bar = bar_index
            exit_price = candle.close_price
            exit_reason = "HORIZON_4H"
            funding_cutoff_ms = candle.close_time_ms

    gross_return_frac = (
        exit_price / entry_price - 1.0
        if side == "LONG"
        else 1.0 - exit_price / entry_price
    )
    funding_sum = sum(
        float(row["funding_rate"])
        for row in funding_events
        if int(row["funding_time_ms"]) <= int(funding_cutoff_ms)
    )
    funding_cost_frac = funding_sum if side == "LONG" else -funding_sum
    net_return_frac = gross_return_frac - roundtrip_base_cost_frac - funding_cost_frac
    gross_r = gross_return_frac / risk_frac
    net_r = net_return_frac / risk_frac

    mfe_r = max(0.0, full_mfe_frac / risk_frac)
    mae_r = max(0.0, full_mae_frac / risk_frac)
    capture_ratio = None if net_r <= 0 or mfe_r <= 0 else net_r / mfe_r
    peak_giveback_r = max(0.0, peak_before_exit_r - gross_r)

    remaining = path[exit_bar:]
    if remaining:
        post_exit_mfe_r = max(
            0.0,
            max(_favorable_r(side, candle, entry_price, risk_frac) for candle in remaining),
        )
    else:
        post_exit_mfe_r = 0.0
    missed_extension_r = max(0.0, mfe_r - max(gross_r, 0.0))

    return {
        "exit_bar": exit_bar,
        "exit_time_ms": int(path[exit_bar - 1].close_time_ms),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "gross_return_frac": gross_return_frac,
        "gross_r": gross_r,
        "funding_cost_frac": funding_cost_frac,
        "roundtrip_base_cost_frac": roundtrip_base_cost_frac,
        "net_return_frac": net_return_frac,
        "net_r": net_r,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "capture_ratio": capture_ratio,
        "peak_favorable_r": peak_before_exit_r,
        "peak_giveback_r": peak_giveback_r,
        "time_to_mfe_min": int(time_to_mfe_min),
        "holding_minutes": int(exit_bar * interval_minutes),
        "post_exit_mfe_r": post_exit_mfe_r,
        "missed_extension_r": missed_extension_r,
        "stop_updates": stop_updates,
        "stop_trace_json": _canonical_json(stop_trace),
        "ambiguous_stop_bar": ambiguous_stop_bar,
    }


class ExitPolicyLab:
    """V2.4 policy-only research. It has no entry, recommendation, or order authority."""

    def __init__(self, observer_config: ObserverConfig, policy_config: PolicyConfig, db: EvidenceDB):
        self.observer_config = observer_config
        self.config = policy_config
        self.db = db
        self.interval_ms = observer_config.candle_interval_ms
        self.interval_minutes = self.interval_ms // 60_000

    def definition(self) -> dict[str, Any]:
        return {
            "lab_version": self.config.lab_version,
            "feature_version": self.config.feature_version,
            "outcome_version": self.config.outcome_version,
            "risk_unit_version": self.config.risk_unit_version,
            "policy_versions": [policy.policy_version for policy in POLICIES],
            "policy_definition_hashes": {
                policy.policy_version: _digest(policy.definition()) for policy in POLICIES
            },
            "sides": ["LONG", "SHORT"],
            "initial_risk_rule": "ALL_POLICIES_START_AT_MINUS_1R_AND_CANNOT_LOOSEN_BELOW_MINUS_1R",
            "evaluation_target": "AFTER_COST_NET_R_AND_PROFIT_CAPTURE_NOT_CAPTURE_RATIO_ALONE",
            "authority": "RESEARCH_ONLY_NO_PROMOTION_NO_EXECUTION",
        }

    def initialize(self) -> None:
        self.db.initialize()
        now_ms = int(time.time() * 1000)
        definition = self.definition()
        catalog_hash = _digest(definition)
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO exit_policy_labs(
                    lab_version, outcome_version, catalog_hash, definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (self.config.lab_version, self.config.outcome_version, catalog_hash, _canonical_json(definition), now_ms),
            )
            row = conn.execute(
                "SELECT outcome_version, catalog_hash FROM exit_policy_labs WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            if row is None or row[0] != self.config.outcome_version or row[1] != catalog_hash:
                raise RuntimeError(f"policy lab version {self.config.lab_version} has a different definition")

            for policy in POLICIES:
                policy_definition = policy.definition()
                policy_hash = _digest(policy_definition)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO exit_policy_sets(
                        policy_version, lab_version, family, is_control,
                        definition_hash, definition_json, registered_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        policy.policy_version,
                        self.config.lab_version,
                        policy.family,
                        1 if policy.is_control else 0,
                        policy_hash,
                        _canonical_json(policy_definition),
                        now_ms,
                    ),
                )
                row = conn.execute(
                    "SELECT lab_version, definition_hash FROM exit_policy_sets WHERE policy_version=?",
                    (policy.policy_version,),
                ).fetchone()
                if row is None or row[0] != self.config.lab_version or row[1] != policy_hash:
                    raise RuntimeError(f"policy version {policy.policy_version} has a different definition")

    def _counts(self, conn) -> dict[str, int]:
        source_paths = int(conn.execute(
            "SELECT COUNT(*) FROM future_paths WHERE outcome_version=?",
            (self.config.outcome_version,),
        ).fetchone()[0])
        source_events = int(conn.execute(
            "SELECT COUNT(DISTINCT event_open_ms) FROM future_paths WHERE outcome_version=?",
            (self.config.outcome_version,),
        ).fetchone()[0])
        eligible_paths = int(conn.execute(
            "SELECT COUNT(*) FROM future_paths WHERE outcome_version=? AND risk_unit_version=? "
            "AND risk_unit_frac IS NOT NULL AND risk_unit_frac>0 AND funding_complete=1",
            (self.config.outcome_version, self.config.risk_unit_version),
        ).fetchone()[0])
        ineligible_paths = source_paths - eligible_paths
        eligible_events = int(conn.execute(
            "SELECT COUNT(DISTINCT event_open_ms) FROM future_paths WHERE outcome_version=? AND risk_unit_version=? "
            "AND risk_unit_frac IS NOT NULL AND risk_unit_frac>0 AND funding_complete=1",
            (self.config.outcome_version, self.config.risk_unit_version),
        ).fetchone()[0])
        built_events = int(conn.execute(
            "SELECT COUNT(*) FROM exit_policy_builds WHERE lab_version=?",
            (self.config.lab_version,),
        ).fetchone()[0])
        result_rows = int(conn.execute(
            "SELECT COUNT(*) FROM exit_policy_results WHERE lab_version=?",
            (self.config.lab_version,),
        ).fetchone()[0])
        return {
            "source_paths": source_paths,
            "source_events": source_events,
            "risk_eligible_paths": eligible_paths,
            "risk_ineligible_paths": ineligible_paths,
            "eligible_events": eligible_events,
            "built_events": built_events,
            "result_rows": result_rows,
            "pending_build_events": max(0, eligible_events - built_events),
        }

    def _target_events(self, conn, limit: int, rebuild: bool) -> list[int]:
        params: list[Any] = [self.config.outcome_version, self.config.risk_unit_version]
        sql = (
            "SELECT DISTINCT p.event_open_ms FROM future_paths p "
            "WHERE p.outcome_version=? AND p.risk_unit_version=? AND p.risk_unit_frac IS NOT NULL "
            "AND p.risk_unit_frac>0 AND p.funding_complete=1 "
        )
        if not rebuild:
            sql += "AND NOT EXISTS (SELECT 1 FROM exit_policy_builds b WHERE b.event_open_ms=p.event_open_ms AND b.lab_version=?) "
            params.append(self.config.lab_version)
        sql += "ORDER BY p.event_open_ms"
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        return [int(row[0]) for row in conn.execute(sql, params).fetchall()]

    def _load_event_paths(self, conn, event_open_ms: int) -> list[dict[str, Any]]:
        columns = (
            "event_open_ms", "symbol", "feature_version", "outcome_version", "entry_price",
            "risk_unit_version", "risk_unit_frac", "funding_complete", "funding_events_json",
            "roundtrip_base_cost_frac", "long_mfe_frac", "long_mae_frac", "short_mfe_frac",
            "short_mae_frac", "time_to_long_mfe_min", "time_to_short_mfe_min",
            "source_candle_digest", "path_digest",
        )
        rows = conn.execute(
            f"SELECT {','.join(columns)} FROM future_paths "
            "WHERE event_open_ms=? AND outcome_version=? AND risk_unit_version=? AND risk_unit_frac IS NOT NULL "
            "AND risk_unit_frac>0 AND funding_complete=1 ORDER BY symbol",
            (event_open_ms, self.config.outcome_version, self.config.risk_unit_version),
        ).fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def _load_path_candles(self, conn, symbol: str, event_open_ms: int) -> list[Candle]:
        start_open = event_open_ms + self.interval_ms
        end_open = event_open_ms + self.config.max_horizon_bars * self.interval_ms
        columns = (
            "event_open_ms", "open_time_ms", "close_time_ms", "open_price", "high_price", "low_price",
            "close_price", "base_volume", "quote_volume", "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume",
        )
        canonical = conn.execute(
            f"SELECT {','.join(columns)} FROM candles_5m WHERE symbol=? AND event_open_ms BETWEEN ? AND ?",
            (symbol, start_open, end_open),
        ).fetchall()
        cached = conn.execute(
            f"SELECT {','.join(columns)} FROM future_candle_cache WHERE symbol=? AND event_open_ms BETWEEN ? AND ?",
            (symbol, start_open, end_open),
        ).fetchall()
        by_open: dict[int, tuple[Any, ...]] = {}
        for row in cached:
            by_open[int(row[0])] = row
        for row in canonical:
            by_open[int(row[0])] = row
        required = [event_open_ms + offset * self.interval_ms for offset in range(1, self.config.max_horizon_bars + 1)]
        if any(open_ms not in by_open for open_ms in required):
            return []
        result: list[Candle] = []
        for open_ms in required:
            row = by_open[open_ms]
            result.append(Candle(
                symbol=symbol,
                open_time_ms=int(row[1]),
                close_time_ms=int(row[2]),
                open_price=float(row[3]),
                high_price=float(row[4]),
                low_price=float(row[5]),
                close_price=float(row[6]),
                base_volume=float(row[7]),
                quote_volume=float(row[8]),
                trade_count=int(row[9]),
                taker_buy_base_volume=float(row[10]),
                taker_buy_quote_volume=float(row[11]),
            ))
        return result

    def _simulate_row(self, source: dict[str, Any], path: list[Candle], side: str, policy: ExitPolicySpec, built_at_ms: int) -> dict[str, Any]:
        funding_events = json.loads(str(source["funding_events_json"]))
        if not isinstance(funding_events, list):
            raise RuntimeError("funding_events_json must contain a list")
        if side == "LONG":
            full_mfe = float(source["long_mfe_frac"])
            full_mae = float(source["long_mae_frac"])
            time_to_mfe = int(source["time_to_long_mfe_min"])
        else:
            full_mfe = float(source["short_mfe_frac"])
            full_mae = float(source["short_mae_frac"])
            time_to_mfe = int(source["time_to_short_mfe_min"])

        sim = simulate_policy(
            spec=policy,
            side=side,
            event_open_ms=int(source["event_open_ms"]),
            entry_price=float(source["entry_price"]),
            risk_frac=float(source["risk_unit_frac"]),
            path=path,
            funding_events=funding_events,
            roundtrip_base_cost_frac=float(source["roundtrip_base_cost_frac"]),
            full_mfe_frac=full_mfe,
            full_mae_frac=full_mae,
            time_to_mfe_min=time_to_mfe,
            interval_minutes=self.interval_minutes,
        )
        row: dict[str, Any] = {
            "event_open_ms": int(source["event_open_ms"]),
            "symbol": str(source["symbol"]),
            "side": side,
            "feature_version": str(source["feature_version"]),
            "outcome_version": str(source["outcome_version"]),
            "lab_version": self.config.lab_version,
            "policy_version": policy.policy_version,
            "built_at_ms": built_at_ms,
            "entry_price": float(source["entry_price"]),
            "initial_risk_frac": float(source["risk_unit_frac"]),
            "source_path_digest": str(source["path_digest"]),
            "source_candle_digest": str(source["source_candle_digest"]),
            **sim,
        }
        row["result_digest"] = _result_digest(row)
        return row

    def build(self, *, max_events: int | None = None, rebuild: bool = False) -> PolicyBuildResult:
        self.initialize()
        limit = self.config.max_events_per_build if max_events is None else int(max_events)
        if limit < 0:
            raise ValueError("max_events must be >= 0")
        with self.db.connection() as conn:
            counts = self._counts(conn)
            targets = self._target_events(conn, limit, rebuild)

        attempted = 0
        built = 0
        result_count = 0
        for event_open_ms in targets:
            attempted += 1
            with self.db.connection() as conn:
                sources = self._load_event_paths(conn, event_open_ms)
            rows: list[dict[str, Any]] = []
            built_at_ms = int(time.time() * 1000)
            for source in sources:
                with self.db.connection() as conn:
                    path = self._load_path_candles(conn, str(source["symbol"]), event_open_ms)
                if len(path) != self.config.max_horizon_bars:
                    raise RuntimeError(f"V2.4 source path missing for {event_open_ms}/{source['symbol']}")
                for side in ("LONG", "SHORT"):
                    for policy in POLICIES:
                        rows.append(self._simulate_row(source, path, side, policy, built_at_ms))

            source_digest = _digest([
                [source["symbol"], source["path_digest"], source["risk_unit_frac"]]
                for source in sources
            ])
            result_digest = _rows_digest(rows, ("event_open_ms", "symbol", "side", "policy_version", "result_digest"))
            with self.db.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if rebuild:
                    conn.execute("DELETE FROM exit_policy_builds WHERE event_open_ms=? AND lab_version=?", (event_open_ms, self.config.lab_version))
                    conn.execute("DELETE FROM exit_policy_results WHERE event_open_ms=? AND lab_version=?", (event_open_ms, self.config.lab_version))
                placeholders = ",".join("?" for _ in RESULT_COLUMNS)
                conn.executemany(
                    f"INSERT INTO exit_policy_results({','.join(RESULT_COLUMNS)}) VALUES ({placeholders})",
                    [[row[column] for column in RESULT_COLUMNS] for row in rows],
                )
                conn.execute(
                    """
                    INSERT INTO exit_policy_builds(
                        event_open_ms, lab_version, built_at_ms, eligible_path_count,
                        result_row_count, source_digest, result_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_open_ms, self.config.lab_version, built_at_ms, len(sources), len(rows), source_digest, result_digest),
                )
            built += 1
            result_count += len(rows)

        with self.db.connection() as conn:
            after = self._counts(conn)
        return PolicyBuildResult(
            lab_version=self.config.lab_version,
            source_events=after["source_events"],
            source_paths=after["source_paths"],
            risk_eligible_paths=after["risk_eligible_paths"],
            risk_ineligible_paths=after["risk_ineligible_paths"],
            pending_build_events=after["pending_build_events"],
            attempted_events=attempted,
            built_events=built,
            result_rows=result_count,
        )

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            counts = self._counts(conn)
            policy_counts = {
                str(policy_version): int(count)
                for policy_version, count in conn.execute(
                    "SELECT policy_version, COUNT(*) FROM exit_policy_results WHERE lab_version=? GROUP BY policy_version ORDER BY policy_version",
                    (self.config.lab_version,),
                ).fetchall()
            }
            latest = conn.execute(
                "SELECT event_open_ms, eligible_path_count, result_row_count, source_digest, result_digest "
                "FROM exit_policy_builds WHERE lab_version=? ORDER BY event_open_ms DESC LIMIT 1",
                (self.config.lab_version,),
            ).fetchone()
        return {
            "lab_version": self.config.lab_version,
            "outcome_version": self.config.outcome_version,
            "policy_count": len(POLICIES),
            "control_policy": next(policy.policy_version for policy in POLICIES if policy.is_control),
            **counts,
            "policy_result_counts": policy_counts,
            "latest_build": latest,
        }

    def report(self) -> dict[str, Any]:
        self.initialize()
        report: dict[str, Any] = {
            "lab_version": self.config.lab_version,
            "authority": "RESEARCH_ONLY_NO_POLICY_PROMOTION",
            "comparison_note": "All policies use identical entries, sides, initial 1R, source paths and cost contract.",
            "policies": {},
        }
        with self.db.connection() as conn:
            raw = conn.execute(
                """
                SELECT event_open_ms, symbol, side, policy_version, net_r, gross_r, capture_ratio,
                       peak_giveback_r, holding_minutes, missed_extension_r
                FROM exit_policy_results
                WHERE lab_version=?
                ORDER BY event_open_ms, symbol, side, policy_version
                """,
                (self.config.lab_version,),
            ).fetchall()

        control_map = {
            (int(event), str(symbol), str(side)): float(net_r)
            for event, symbol, side, policy, net_r, *_rest in raw
            if str(policy) == "INTEGER_R_STEP_CONTROL"
        }
        grouped: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
        for row in raw:
            grouped.setdefault((str(row[3]), str(row[2])), []).append(row)

        for policy in POLICIES:
            for side in ("LONG", "SHORT"):
                rows = grouped.get((policy.policy_version, side), [])
                key = f"{policy.policy_version}:{side}"
                if not rows:
                    report["policies"][key] = {"rows": 0}
                    continue
                net = [float(row[4]) for row in rows]
                gross = [float(row[5]) for row in rows]
                captures = [float(row[6]) for row in rows if row[6] is not None]
                positives = sum(value for value in net if value > 0)
                negatives = -sum(value for value in net if value < 0)
                paired_lifts = [
                    float(row[4]) - control_map[(int(row[0]), str(row[1]), str(row[2]))]
                    for row in rows
                    if (int(row[0]), str(row[1]), str(row[2])) in control_map
                ]
                event_values: dict[int, list[float]] = {}
                event_lifts: dict[int, list[float]] = {}
                for row in rows:
                    event = int(row[0])
                    event_values.setdefault(event, []).append(float(row[4]))
                    ckey = (event, str(row[1]), str(row[2]))
                    if ckey in control_map:
                        event_lifts.setdefault(event, []).append(float(row[4]) - control_map[ckey])
                event_means = [statistics.fmean(values) for _event, values in sorted(event_values.items())]
                event_mean_lifts = [statistics.fmean(values) for _event, values in sorted(event_lifts.items())]

                report["policies"][key] = {
                    "rows": len(rows),
                    "independent_market_events": len(event_values),
                    "mean_net_r": statistics.fmean(net),
                    "median_net_r": statistics.median(net),
                    "p05_net_r": sorted(net)[max(0, math.ceil(0.05 * len(net)) - 1)],
                    "win_rate": sum(1 for value in net if value > 0) / len(net),
                    "profit_factor": None if negatives == 0 else positives / negatives,
                    "mean_capture_ratio_winners": None if not captures else statistics.fmean(captures),
                    "mean_peak_giveback_r": statistics.fmean(float(row[7]) for row in rows),
                    "mean_holding_minutes": statistics.fmean(float(row[8]) for row in rows),
                    "mean_missed_extension_r": statistics.fmean(float(row[9]) for row in rows),
                    "mean_gross_r": statistics.fmean(gross),
                    "mean_net_r_lift_vs_control": None if not paired_lifts else statistics.fmean(paired_lifts),
                    "median_net_r_lift_vs_control": None if not paired_lifts else statistics.median(paired_lifts),
                    "paired_better_than_control_rate": None if not paired_lifts else sum(1 for value in paired_lifts if value > 0) / len(paired_lifts),
                    "mean_event_net_r": statistics.fmean(event_means),
                    "mean_event_lift_vs_control": None if not event_mean_lifts else statistics.fmean(event_mean_lifts),
                    "positive_event_lift_rate": None if not event_mean_lifts else sum(1 for value in event_mean_lifts if value > 0) / len(event_mean_lifts),
                }
        return report

    def audit(self) -> dict[str, Any]:
        self.initialize()
        definition = self.definition()
        expected_lab_hash = _digest(definition)
        expected_policy_hash = {policy.policy_version: _digest(policy.definition()) for policy in POLICIES}
        with self.db.connection() as conn:
            lab_row = conn.execute(
                "SELECT catalog_hash FROM exit_policy_labs WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            lab_definition_mismatch = 1 if lab_row is None or str(lab_row[0]) != expected_lab_hash else 0
            policy_rows = conn.execute(
                "SELECT policy_version, definition_hash FROM exit_policy_sets WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchall()
            actual_policy_hash = {str(version): str(digest) for version, digest in policy_rows}
            policy_definition_mismatches = sum(
                1 for version, digest in expected_policy_hash.items() if actual_policy_hash.get(version) != digest
            ) + sum(1 for version in actual_policy_hash if version not in expected_policy_hash)

            results = conn.execute(
                f"SELECT {','.join(RESULT_COLUMNS)} FROM exit_policy_results WHERE lab_version=? ORDER BY event_open_ms, symbol, side, policy_version",
                (self.config.lab_version,),
            ).fetchall()
            builds = conn.execute(
                "SELECT event_open_ms, eligible_path_count, result_row_count, source_digest, result_digest "
                "FROM exit_policy_builds WHERE lab_version=? ORDER BY event_open_ms",
                (self.config.lab_version,),
            ).fetchall()
            source_rows = conn.execute(
                "SELECT event_open_ms, symbol, path_digest, source_candle_digest, risk_unit_frac, risk_unit_version, funding_complete "
                "FROM future_paths WHERE outcome_version=?",
                (self.config.outcome_version,),
            ).fetchall()

        result_digest_mismatches = 0
        invalid_results = 0
        invalid_initial_risk = 0
        source_path_mismatches = 0
        policy_result_counts: dict[tuple[int, str], int] = {}
        event_results: dict[int, list[dict[str, Any]]] = {}
        source_map = {
            (int(event_open_ms), str(symbol)): (str(path_digest), str(candle_digest), risk, str(risk_version), int(funding_complete))
            for event_open_ms, symbol, path_digest, candle_digest, risk, risk_version, funding_complete in source_rows
        }
        risk_unit_version_mismatches = sum(
            1 for _key, source in source_map.items()
            if source[2] is not None and float(source[2]) > 0 and source[3] != self.config.risk_unit_version
        )
        for raw in results:
            row = dict(zip(RESULT_COLUMNS, raw))
            expected = _result_digest(row)
            if expected != row["result_digest"]:
                result_digest_mismatches += 1
            values = [
                row["entry_price"], row["initial_risk_frac"], row["exit_price"], row["gross_return_frac"],
                row["gross_r"], row["funding_cost_frac"], row["roundtrip_base_cost_frac"], row["net_return_frac"],
                row["net_r"], row["mfe_r"], row["mae_r"], row["peak_favorable_r"], row["peak_giveback_r"],
                row["post_exit_mfe_r"], row["missed_extension_r"],
            ]
            if any(not math.isfinite(float(value)) for value in values):
                invalid_results += 1
            if float(row["initial_risk_frac"]) <= 0 or int(row["exit_bar"]) < 1 or int(row["exit_bar"]) > self.config.max_horizon_bars:
                invalid_results += 1
            try:
                trace = json.loads(str(row["stop_trace_json"]))
                if not isinstance(trace, list) or not trace or float(trace[0][1]) != -1.0:
                    invalid_initial_risk += 1
                if any(float(item[1]) < -1.0 - 1e-12 for item in trace):
                    invalid_initial_risk += 1
                if any(float(trace[index][1]) < float(trace[index - 1][1]) - 1e-12 for index in range(1, len(trace))):
                    invalid_initial_risk += 1
            except Exception:
                invalid_initial_risk += 1
            source = source_map.get((int(row["event_open_ms"]), str(row["symbol"])))
            if source is None or source[0] != row["source_path_digest"] or source[1] != row["source_candle_digest"] or source[3] != self.config.risk_unit_version or source[4] != 1:
                source_path_mismatches += 1
            key = (int(row["event_open_ms"]), str(row["symbol"]))
            policy_result_counts[key] = policy_result_counts.get(key, 0) + 1
            event_results.setdefault(int(row["event_open_ms"]), []).append(row)

        expected_per_source = len(POLICIES) * 2
        annotation_count_mismatches = sum(1 for count in policy_result_counts.values() if count != expected_per_source)

        build_row_mismatches = 0
        build_digest_mismatches = 0
        build_source_digest_mismatches = 0
        for event_open_ms, eligible_count, result_count, source_digest, result_digest in builds:
            event_open_ms = int(event_open_ms)
            event_rows = event_results.get(event_open_ms, [])
            if int(result_count) != len(event_rows) or int(result_count) != int(eligible_count) * expected_per_source:
                build_row_mismatches += 1
            expected_result_digest = _rows_digest(
                event_rows,
                ("event_open_ms", "symbol", "side", "policy_version", "result_digest"),
            )
            if str(result_digest) != expected_result_digest:
                build_digest_mismatches += 1
            sources = sorted(
                [
                    [symbol, path_digest, risk]
                    for (evt, symbol), (path_digest, _candle, risk, risk_version, funding_complete) in source_map.items()
                    if evt == event_open_ms and risk is not None and float(risk) > 0
                    and risk_version == self.config.risk_unit_version and funding_complete == 1
                ],
                key=lambda item: item[0],
            )
            if str(source_digest) != _digest(sources):
                build_source_digest_mismatches += 1

        return {
            "lab_version": self.config.lab_version,
            "policy_count": len(POLICIES),
            "lab_definition_mismatch": lab_definition_mismatch,
            "policy_definition_mismatches": policy_definition_mismatches,
            "result_rows": len(results),
            "result_digest_mismatches": result_digest_mismatches,
            "invalid_results": invalid_results,
            "invalid_initial_risk": invalid_initial_risk,
            "source_path_mismatches": source_path_mismatches,
            "risk_unit_version_mismatches": risk_unit_version_mismatches,
            "annotation_count_mismatches": annotation_count_mismatches,
            "build_row_mismatches": build_row_mismatches,
            "build_digest_mismatches": build_digest_mismatches,
            "build_source_digest_mismatches": build_source_digest_mismatches,
        }
