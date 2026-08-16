from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .config import ObserverConfig
from .db import EvidenceDB
from .research import SIGNAL_VERSIONS


@dataclass(frozen=True)
class SelectionConfig:
    """Version-controlled V2.5 entry-selection research definition."""

    lab_version: str = "ENTRY_SELECTION_LAB_V1"
    feature_version: str = "CANONICAL_FEATURES_V1"
    policy_lab_version: str = "EXIT_POLICY_LAB_V1"
    target_policy_version: str = "INTEGER_R_STEP_CONTROL"
    target_policy_status: str = "CONTROL_BENCHMARK_NOT_PROMOTED"
    target_name: str = "AFTER_COST_NET_R"
    learned_selector_version: str = "RIDGE_EXPECTED_NET_R_V1"
    min_train_events: int = 20
    ridge_alpha: float = 10.0
    max_events_per_build: int = 100

    def validate(self) -> None:
        if self.lab_version != "ENTRY_SELECTION_LAB_V1":
            raise ValueError("V2.5 initial selection lab is frozen as ENTRY_SELECTION_LAB_V1")
        if self.feature_version != "CANONICAL_FEATURES_V1":
            raise ValueError("V2.5 is tied to CANONICAL_FEATURES_V1")
        if self.policy_lab_version != "EXIT_POLICY_LAB_V1":
            raise ValueError("V2.5 is tied to EXIT_POLICY_LAB_V1")
        if self.target_policy_version != "INTEGER_R_STEP_CONTROL":
            raise ValueError("V2.5 V1 target policy is the unpromoted integer-R control benchmark")
        if self.target_name != "AFTER_COST_NET_R":
            raise ValueError("V2.5 V1 target is frozen as after-cost net R")
        if self.learned_selector_version != "RIDGE_EXPECTED_NET_R_V1":
            raise ValueError("V2.5 V1 learned selector is frozen")
        if self.min_train_events < 2:
            raise ValueError("min_train_events must be at least two independent events")
        if self.ridge_alpha <= 0:
            raise ValueError("ridge_alpha must be positive")
        if self.max_events_per_build <= 0:
            raise ValueError("max_events_per_build must be positive")


SELECTION_CONFIG = SelectionConfig()
SELECTION_CONFIG.validate()


@dataclass(frozen=True)
class SelectorSpec:
    selector_version: str
    family: str
    is_learned: bool
    description: str
    parameters: dict[str, Any]

    def definition(self) -> dict[str, Any]:
        return {
            "selector_version": self.selector_version,
            "family": self.family,
            "is_learned": self.is_learned,
            "description": self.description,
            "parameters": self.parameters,
            "candidate_universe": "ALL_V2_4_TARGET_POLICY_SYMBOL_SIDE_RESULTS_NO_SIGNAL_GATING",
            "score_clock": "DECISION_TIME_FEATURES_ONLY",
            "authority": "RESEARCH_ONLY_NO_CHAMPION_NO_EXECUTION",
        }


SELECTORS: tuple[SelectorSpec, ...] = (
    SelectorSpec(
        "RANDOM_HASH_BASELINE_V1",
        "RANDOM_ELIGIBLE_SELECTION",
        False,
        "Deterministic hash ranking used as a reproducible random-selection baseline.",
        {"hash": "SHA256(event_open_ms|symbol|side|selector_version)"},
    ),
    SelectorSpec(
        "LIQUIDITY_BASELINE_V1",
        "HIGHEST_LIQUIDITY",
        False,
        "Ranks candidates by decision-time liquidity percentile only.",
        {"score": "liquidity_percentile"},
    ),
    SelectorSpec(
        "CSM_BASELINE_V1",
        "CROSS_SECTIONAL_MOMENTUM",
        False,
        "Ranks candidates by side-aligned CSM score; missing CSM is neutral.",
        {"score": "csm_side_score"},
    ),
    SelectorSpec(
        "TSMOM_BASELINE_V1",
        "TIME_SERIES_MOMENTUM",
        False,
        "Ranks candidates by side-aligned time-series momentum score; missing score is neutral.",
        {"score": "tsmom_side_score"},
    ),
    SelectorSpec(
        "INTRADAY_BASELINE_V1",
        "INTRADAY_CONDITIONAL",
        False,
        "Ranks candidates by side-aligned V2.2 intraday conditional score.",
        {"score": "intraday_side_score"},
    ),
    SelectorSpec(
        "RIDGE_EXPECTED_NET_R_V1",
        "EXPECTED_NET_R_REGRESSION",
        True,
        "Forward-chained ridge regression predicting after-cost net R from decision-time features.",
        {
            "objective": "EXPECTED_AFTER_COST_NET_R",
            "training_rule": "ONLY_EVENTS_STRICTLY_BEFORE_SCORED_EVENT",
            "standardization": "TRAIN_WINDOW_ONLY_ZSCORE",
            "probability_output": False,
        },
    ),
)
SELECTOR_BY_VERSION = {spec.selector_version: spec for spec in SELECTORS}
BASELINE_SELECTORS = tuple(spec for spec in SELECTORS if not spec.is_learned)


FEATURE_VECTOR_NAMES: tuple[str, ...] = (
    "side_sign",
    "ret_5m_side", "ret_15m_side", "ret_30m_side", "ret_1h_side", "ret_2h_side", "ret_4h_side",
    "realized_vol_1h", "realized_vol_4h", "atr14_frac", "range_frac",
    "log_quote_volume_24h", "spread_pct", "funding_rate_side",
    "liquidity_percentile", "ret_1h_percentile_side", "ret_4h_percentile_side", "volatility_percentile",
    "btc_ret_5m_side", "btc_ret_1h_side", "btc_ret_4h_side",
    "breadth_5m_side", "breadth_1h_side", "median_ret_5m_side", "median_ret_1h_side",
    "utc_hour_sin", "utc_hour_cos", "utc_day_sin", "utc_day_cos",
    "csm_side_score", "tsmom_side_score", "intraday_side_score",
    "csm_alignment", "tsmom_alignment", "intraday_alignment",
    "missing_ret_4h", "missing_vol_4h", "missing_csm", "missing_tsmom",
)

FEATURE_QUERY_COLUMNS: tuple[str, ...] = (
    "event_open_ms", "symbol", "feature_version", "source_max_event_open_ms",
    "ret_5m", "ret_15m", "ret_30m", "ret_1h", "ret_2h", "ret_4h",
    "realized_vol_1h", "realized_vol_4h", "atr14_frac", "range_frac",
    "quote_volume_24h_usd", "spread_pct", "funding_rate", "liquidity_percentile",
    "ret_1h_percentile", "ret_4h_percentile", "volatility_percentile",
    "btc_ret_5m", "btc_ret_1h", "btc_ret_4h", "breadth_positive_5m", "breadth_positive_1h",
    "median_ret_5m", "median_ret_1h", "utc_hour", "utc_day_of_week",
)

EXAMPLE_COLUMNS: tuple[str, ...] = (
    "event_open_ms", "symbol", "side", "lab_version", "feature_version", "target_policy_version",
    "built_at_ms", "target_net_r", "target_net_return_frac", "target_mfe_r", "target_mae_r",
    "source_policy_result_digest", "source_feature_digest", "source_signal_digest",
    "feature_vector_json", "example_digest",
)
EXAMPLE_DIGEST_FIELDS = tuple(field for field in EXAMPLE_COLUMNS if field not in {"built_at_ms", "example_digest"})

PREDICTION_COLUMNS: tuple[str, ...] = (
    "event_open_ms", "symbol", "side", "lab_version", "selector_version", "scored_at_ms",
    "score", "rank_in_event", "trained_through_event_ms", "training_event_count", "training_row_count",
    "model_digest", "source_example_digest", "prediction_digest",
)
PREDICTION_DIGEST_FIELDS = tuple(field for field in PREDICTION_COLUMNS if field not in {"scored_at_ms", "prediction_digest"})


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and value == 0.0:
        return 0.0
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(_normalize(value)).encode("utf-8")).hexdigest()


def _rows_digest(rows: Iterable[dict[str, Any]], fields: tuple[str, ...], *, key_fields: tuple[str, ...]) -> str:
    ordered = sorted(rows, key=lambda row: tuple(row[field] for field in key_fields))
    return _digest([[row.get(field) for field in fields] for row in ordered])


def _row_digest(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    return _digest([row.get(field) for field in fields])


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    result = float(value)
    return 0.0 if result == 0.0 else result


def _alignment(direction: str | None, side: str, active: int | bool | None) -> float:
    if not active or direction not in {"LONG", "SHORT"}:
        return 0.0
    return 1.0 if direction == side else -1.0


def _side_score(score: Any, side: str) -> float:
    if score is None:
        return 0.0
    sign = 1.0 if side == "LONG" else -1.0
    return _f(score) * sign


def _percentile_side(value: Any, side: str) -> float:
    if value is None:
        return 0.0
    sign = 1.0 if side == "LONG" else -1.0
    return (2.0 * _f(value) - 1.0) * sign


def _breadth_side(value: Any, side: str) -> float:
    if value is None:
        return 0.0
    sign = 1.0 if side == "LONG" else -1.0
    return (2.0 * _f(value) - 1.0) * sign


def _feature_vector(feature: dict[str, Any], signals: dict[str, dict[str, Any]], side: str) -> dict[str, float]:
    sign = 1.0 if side == "LONG" else -1.0
    csm = signals.get(SIGNAL_VERSIONS[0], {})
    tsmom = signals.get(SIGNAL_VERSIONS[1], {})
    intraday = signals.get(SIGNAL_VERSIONS[2], {})
    hour = int(feature["utc_hour"])
    day = int(feature["utc_day_of_week"])
    ret_4h = feature.get("ret_4h")
    vol_4h = feature.get("realized_vol_4h")
    volume = max(0.0, _f(feature.get("quote_volume_24h_usd")))
    values = {
        "side_sign": sign,
        "ret_5m_side": _f(feature.get("ret_5m")) * sign,
        "ret_15m_side": _f(feature.get("ret_15m")) * sign,
        "ret_30m_side": _f(feature.get("ret_30m")) * sign,
        "ret_1h_side": _f(feature.get("ret_1h")) * sign,
        "ret_2h_side": _f(feature.get("ret_2h")) * sign,
        "ret_4h_side": _f(ret_4h) * sign,
        "realized_vol_1h": _f(feature.get("realized_vol_1h")),
        "realized_vol_4h": _f(vol_4h),
        "atr14_frac": _f(feature.get("atr14_frac")),
        "range_frac": _f(feature.get("range_frac")),
        "log_quote_volume_24h": math.log1p(volume),
        "spread_pct": _f(feature.get("spread_pct")),
        "funding_rate_side": _f(feature.get("funding_rate")) * sign,
        "liquidity_percentile": _f(feature.get("liquidity_percentile"), 0.5),
        "ret_1h_percentile_side": _percentile_side(feature.get("ret_1h_percentile"), side),
        "ret_4h_percentile_side": _percentile_side(feature.get("ret_4h_percentile"), side),
        "volatility_percentile": _f(feature.get("volatility_percentile"), 0.5),
        "btc_ret_5m_side": _f(feature.get("btc_ret_5m")) * sign,
        "btc_ret_1h_side": _f(feature.get("btc_ret_1h")) * sign,
        "btc_ret_4h_side": _f(feature.get("btc_ret_4h")) * sign,
        "breadth_5m_side": _breadth_side(feature.get("breadth_positive_5m"), side),
        "breadth_1h_side": _breadth_side(feature.get("breadth_positive_1h"), side),
        "median_ret_5m_side": _f(feature.get("median_ret_5m")) * sign,
        "median_ret_1h_side": _f(feature.get("median_ret_1h")) * sign,
        "utc_hour_sin": math.sin(2.0 * math.pi * hour / 24.0),
        "utc_hour_cos": math.cos(2.0 * math.pi * hour / 24.0),
        "utc_day_sin": math.sin(2.0 * math.pi * day / 7.0),
        "utc_day_cos": math.cos(2.0 * math.pi * day / 7.0),
        "csm_side_score": _side_score(csm.get("score"), side),
        "tsmom_side_score": _side_score(tsmom.get("score"), side),
        "intraday_side_score": _side_score(intraday.get("score"), side),
        "csm_alignment": _alignment(csm.get("direction"), side, csm.get("active")),
        "tsmom_alignment": _alignment(tsmom.get("direction"), side, tsmom.get("active")),
        "intraday_alignment": _alignment(intraday.get("direction"), side, intraday.get("active")),
        "missing_ret_4h": 1.0 if ret_4h is None else 0.0,
        "missing_vol_4h": 1.0 if vol_4h is None else 0.0,
        "missing_csm": 1.0 if csm.get("score") is None else 0.0,
        "missing_tsmom": 1.0 if tsmom.get("score") is None else 0.0,
    }
    if tuple(values) != FEATURE_VECTOR_NAMES:
        raise RuntimeError("V2.5 feature vector order changed")
    return {key: (0.0 if value == 0.0 else float(value)) for key, value in values.items()}


def _random_score(event_open_ms: int, symbol: str, side: str, selector_version: str) -> float:
    raw = f"{event_open_ms}|{symbol}|{side}|{selector_version}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    return integer / float((1 << 64) - 1)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [list(matrix[i]) + [float(vector[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            raise RuntimeError("ridge normal equation is singular")
        if pivot != col:
            augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            if factor == 0.0:
                continue
            augmented[row] = [
                augmented[row][j] - factor * augmented[col][j]
                for j in range(n + 1)
            ]
    return [augmented[i][-1] for i in range(n)]


def _fit_ridge(rows: list[dict[str, Any]], alpha: float) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot fit ridge without rows")
    vectors = [json.loads(str(row["feature_vector_json"])) for row in rows]
    y = [_f(row["target_net_r"]) for row in rows]
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    for name in FEATURE_VECTOR_NAMES:
        values = [_f(vector[name]) for vector in vectors]
        mean = statistics.fmean(values)
        variance = statistics.fmean((value - mean) ** 2 for value in values)
        scale = math.sqrt(variance)
        means[name] = 0.0 if mean == 0.0 else mean
        scales[name] = scale if scale > 1e-12 else 1.0

    dimension = len(FEATURE_VECTOR_NAMES) + 1
    xtx = [[0.0 for _ in range(dimension)] for _ in range(dimension)]
    xty = [0.0 for _ in range(dimension)]
    for vector, target in zip(vectors, y):
        x = [1.0] + [(_f(vector[name]) - means[name]) / scales[name] for name in FEATURE_VECTOR_NAMES]
        for i in range(dimension):
            xty[i] += x[i] * target
            for j in range(i, dimension):
                xtx[i][j] += x[i] * x[j]
    for i in range(dimension):
        for j in range(i):
            xtx[i][j] = xtx[j][i]
    for index in range(1, dimension):
        xtx[index][index] += alpha
    coefficients = _solve_linear_system(xtx, xty)
    model = {
        "selector_version": "RIDGE_EXPECTED_NET_R_V1",
        "feature_names": list(FEATURE_VECTOR_NAMES),
        "alpha": float(alpha),
        "means": means,
        "scales": scales,
        "intercept": coefficients[0],
        "coefficients": dict(zip(FEATURE_VECTOR_NAMES, coefficients[1:])),
    }
    model["model_digest"] = _digest(model)
    return model


def _ridge_score(model: dict[str, Any], feature_vector_json: str) -> float:
    vector = json.loads(feature_vector_json)
    score = _f(model["intercept"])
    for name in FEATURE_VECTOR_NAMES:
        standardized = (_f(vector[name]) - _f(model["means"][name])) / _f(model["scales"][name], 1.0)
        score += _f(model["coefficients"][name]) * standardized
    return 0.0 if score == 0.0 else score


@dataclass(frozen=True)
class SelectionBuildResult:
    lab_version: str
    target_policy_version: str
    source_events: int
    source_rows: int
    pending_example_events: int
    attempted_example_events: int
    built_example_events: int
    example_rows: int
    baseline_prediction_rows: int
    learned_prediction_rows: int
    learned_ready_events: int


class EntrySelectionLab:
    """V2.5 research-only entry ranking over V2.2 features and V2.4 net-R labels."""

    def __init__(self, observer_config: ObserverConfig, config: SelectionConfig, db: EvidenceDB):
        self.observer_config = observer_config
        self.config = config
        self.db = db

    def definition(self) -> dict[str, Any]:
        return {
            "lab_version": self.config.lab_version,
            "feature_version": self.config.feature_version,
            "policy_lab_version": self.config.policy_lab_version,
            "target_policy_version": self.config.target_policy_version,
            "target_policy_status": self.config.target_policy_status,
            "target_name": self.config.target_name,
            "candidate_universe": "ALL_TARGET_POLICY_RESULTS_BOTH_SIDES_NO_SIGNAL_GATING",
            "feature_vector_names": list(FEATURE_VECTOR_NAMES),
            "learned_selector_version": self.config.learned_selector_version,
            "min_train_events": self.config.min_train_events,
            "ridge_alpha": self.config.ridge_alpha,
            "chronology_rule": "FOR_EVENT_T_LEARNED_MODEL_USES_ONLY_EXAMPLES_WITH_EVENT_LT_T",
            "evaluation_independence": "MARKET_EVENT_IS_PRIMARY_INDEPENDENT_UNIT_NOT_SYMBOL_ROW",
            "probability_calibration": "NOT_APPLICABLE_TO_EXPECTED_NET_R_REGRESSION",
            "authority": "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION",
        }

    def initialize(self) -> None:
        self.db.initialize()
        now_ms = int(time.time() * 1000)
        definition = self.definition()
        definition_hash = _digest(definition)
        with self.db.connection() as conn:
            target = conn.execute(
                "SELECT lab_version FROM exit_policy_sets WHERE policy_version=?",
                (self.config.target_policy_version,),
            ).fetchone()
            if target is None or target[0] != self.config.policy_lab_version:
                raise RuntimeError("V2.5 target policy is not registered in the expected V2.4 lab")
            conn.execute(
                """
                INSERT OR IGNORE INTO entry_selection_labs(
                    lab_version, feature_version, policy_lab_version, target_policy_version,
                    definition_hash, definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.config.lab_version, self.config.feature_version, self.config.policy_lab_version,
                    self.config.target_policy_version, definition_hash, _canonical_json(definition), now_ms,
                ),
            )
            stored = conn.execute(
                "SELECT feature_version, policy_lab_version, target_policy_version, definition_hash "
                "FROM entry_selection_labs WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            if stored != (
                self.config.feature_version, self.config.policy_lab_version,
                self.config.target_policy_version, definition_hash,
            ):
                raise RuntimeError(f"selection lab {self.config.lab_version} already has a different definition")
            for spec in SELECTORS:
                definition = spec.definition()
                if spec.selector_version == self.config.learned_selector_version:
                    definition = dict(definition)
                    definition["parameters"] = dict(definition["parameters"])
                    definition["parameters"].update({
                        "min_train_events": self.config.min_train_events,
                        "ridge_alpha": self.config.ridge_alpha,
                        "feature_names": list(FEATURE_VECTOR_NAMES),
                    })
                definition_hash = _digest(definition)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO entry_selector_sets(
                        selector_version, lab_version, family, is_learned,
                        definition_hash, definition_json, registered_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        spec.selector_version, self.config.lab_version, spec.family, int(spec.is_learned),
                        definition_hash, _canonical_json(definition), now_ms,
                    ),
                )
                stored_selector = conn.execute(
                    "SELECT lab_version, definition_hash FROM entry_selector_sets WHERE selector_version=?",
                    (spec.selector_version,),
                ).fetchone()
                if stored_selector != (self.config.lab_version, definition_hash):
                    raise RuntimeError(f"selector {spec.selector_version} already has a different definition")

    def _source_counts(self, conn) -> tuple[int, int]:
        row = conn.execute(
            "SELECT COUNT(DISTINCT event_open_ms), COUNT(*) FROM exit_policy_results "
            "WHERE lab_version=? AND policy_version=?",
            (self.config.policy_lab_version, self.config.target_policy_version),
        ).fetchone()
        return int(row[0]), int(row[1])

    def _target_events(self, conn, limit: int, rebuild: bool) -> list[int]:
        params: list[Any] = [self.config.policy_lab_version, self.config.target_policy_version]
        sql = (
            "SELECT DISTINCT r.event_open_ms FROM exit_policy_results r "
            "WHERE r.lab_version=? AND r.policy_version=? "
        )
        if not rebuild:
            sql += "AND NOT EXISTS (SELECT 1 FROM entry_selection_builds b WHERE b.event_open_ms=r.event_open_ms AND b.lab_version=?) "
            params.append(self.config.lab_version)
        sql += "ORDER BY r.event_open_ms"
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        return [int(row[0]) for row in conn.execute(sql, params).fetchall()]

    def _feature_rows(self, conn, event_open_ms: int) -> dict[str, dict[str, Any]]:
        rows = conn.execute(
            f"SELECT {','.join(FEATURE_QUERY_COLUMNS)} FROM canonical_features "
            "WHERE event_open_ms=? AND feature_version=? ORDER BY symbol",
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        return {str(row[1]): dict(zip(FEATURE_QUERY_COLUMNS, row)) for row in rows}

    def _signal_rows(self, conn, event_open_ms: int) -> dict[str, dict[str, dict[str, Any]]]:
        rows = conn.execute(
            "SELECT symbol, signal_version, score, active, direction FROM signal_annotations "
            "WHERE event_open_ms=? AND feature_version=? ORDER BY symbol, signal_version",
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for symbol, version, score, active, direction in rows:
            result.setdefault(str(symbol), {})[str(version)] = {
                "score": score, "active": int(active), "direction": str(direction),
            }
        return result

    def _source_rows(self, conn, event_open_ms: int) -> list[dict[str, Any]]:
        fields = (
            "event_open_ms", "symbol", "side", "feature_version", "net_r", "net_return_frac",
            "mfe_r", "mae_r", "result_digest",
        )
        rows = conn.execute(
            f"SELECT {','.join(fields)} FROM exit_policy_results "
            "WHERE event_open_ms=? AND lab_version=? AND policy_version=? ORDER BY symbol, side",
            (event_open_ms, self.config.policy_lab_version, self.config.target_policy_version),
        ).fetchall()
        return [dict(zip(fields, row)) for row in rows]

    def _build_examples_for_event(self, conn, event_open_ms: int, rebuild: bool) -> int:
        source_rows = self._source_rows(conn, event_open_ms)
        features = self._feature_rows(conn, event_open_ms)
        signals = self._signal_rows(conn, event_open_ms)
        build = conn.execute(
            "SELECT feature_digest, signal_digest FROM feature_builds WHERE event_open_ms=? AND feature_version=?",
            (event_open_ms, self.config.feature_version),
        ).fetchone()
        if build is None:
            raise RuntimeError(f"missing V2.2 feature build for event {event_open_ms}")
        source_feature_digest, source_signal_digest = str(build[0]), str(build[1])
        built_at_ms = int(time.time() * 1000)
        examples: list[dict[str, Any]] = []
        for source in source_rows:
            symbol = str(source["symbol"])
            feature = features.get(symbol)
            if feature is None:
                raise RuntimeError(f"target policy row {symbol} has no V2.2 feature")
            if int(feature["source_max_event_open_ms"]) > event_open_ms:
                raise RuntimeError("future decision-time feature source detected")
            side = str(source["side"])
            vector = _feature_vector(feature, signals.get(symbol, {}), side)
            row: dict[str, Any] = {
                "event_open_ms": event_open_ms,
                "symbol": symbol,
                "side": side,
                "lab_version": self.config.lab_version,
                "feature_version": self.config.feature_version,
                "target_policy_version": self.config.target_policy_version,
                "built_at_ms": built_at_ms,
                "target_net_r": _f(source["net_r"]),
                "target_net_return_frac": _f(source["net_return_frac"]),
                "target_mfe_r": _f(source["mfe_r"]),
                "target_mae_r": _f(source["mae_r"]),
                "source_policy_result_digest": str(source["result_digest"]),
                "source_feature_digest": source_feature_digest,
                "source_signal_digest": source_signal_digest,
                "feature_vector_json": _canonical_json(vector),
                "example_digest": "",
            }
            row["example_digest"] = _row_digest(row, EXAMPLE_DIGEST_FIELDS)
            examples.append(row)
        source_digest = _digest([
            [row["symbol"], row["side"], row["result_digest"], source_feature_digest, source_signal_digest]
            for row in source_rows
        ])
        example_digest = _rows_digest(examples, EXAMPLE_DIGEST_FIELDS, key_fields=("event_open_ms", "symbol", "side"))
        if rebuild:
            conn.execute(
                "DELETE FROM entry_selection_prediction_builds WHERE event_open_ms=? AND lab_version=?",
                (event_open_ms, self.config.lab_version),
            )
            conn.execute(
                "DELETE FROM entry_selection_predictions WHERE event_open_ms=? AND lab_version=?",
                (event_open_ms, self.config.lab_version),
            )
            conn.execute(
                "DELETE FROM entry_selection_builds WHERE event_open_ms=? AND lab_version=?",
                (event_open_ms, self.config.lab_version),
            )
            conn.execute(
                "DELETE FROM entry_selection_examples WHERE event_open_ms=? AND lab_version=?",
                (event_open_ms, self.config.lab_version),
            )
        placeholders = ",".join("?" for _ in EXAMPLE_COLUMNS)
        conn.executemany(
            f"INSERT INTO entry_selection_examples({','.join(EXAMPLE_COLUMNS)}) VALUES ({placeholders})",
            [[row[field] for field in EXAMPLE_COLUMNS] for row in examples],
        )
        conn.execute(
            """
            INSERT INTO entry_selection_builds(
                event_open_ms, lab_version, built_at_ms, example_row_count, source_digest, example_digest
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_open_ms, self.config.lab_version, built_at_ms, len(examples), source_digest, example_digest),
        )
        return len(examples)

    def _examples_for_event(self, conn, event_open_ms: int) -> list[dict[str, Any]]:
        fields = ("event_open_ms", "symbol", "side", "target_net_r", "feature_vector_json", "example_digest")
        rows = conn.execute(
            f"SELECT {','.join(fields)} FROM entry_selection_examples WHERE event_open_ms=? AND lab_version=? ORDER BY symbol, side",
            (event_open_ms, self.config.lab_version),
        ).fetchall()
        return [dict(zip(fields, row)) for row in rows]

    def _training_rows(self, conn, event_open_ms: int) -> tuple[list[dict[str, Any]], int, int | None]:
        fields = ("event_open_ms", "symbol", "side", "target_net_r", "feature_vector_json", "example_digest")
        rows = conn.execute(
            f"SELECT {','.join(fields)} FROM entry_selection_examples WHERE lab_version=? AND event_open_ms<? "
            "ORDER BY event_open_ms, symbol, side",
            (self.config.lab_version, event_open_ms),
        ).fetchall()
        result = [dict(zip(fields, row)) for row in rows]
        events = sorted({int(row["event_open_ms"]) for row in result})
        return result, len(events), (events[-1] if events else None)

    @staticmethod
    def _baseline_score(spec: SelectorSpec, example: dict[str, Any]) -> float:
        vector = json.loads(str(example["feature_vector_json"]))
        if spec.selector_version == "RANDOM_HASH_BASELINE_V1":
            return _random_score(int(example["event_open_ms"]), str(example["symbol"]), str(example["side"]), spec.selector_version)
        mapping = {
            "LIQUIDITY_BASELINE_V1": "liquidity_percentile",
            "CSM_BASELINE_V1": "csm_side_score",
            "TSMOM_BASELINE_V1": "tsmom_side_score",
            "INTRADAY_BASELINE_V1": "intraday_side_score",
        }
        return _f(vector[mapping[spec.selector_version]])

    def _score_event(self, conn, event_open_ms: int, spec: SelectorSpec, rebuild: bool) -> int:
        examples = self._examples_for_event(conn, event_open_ms)
        if not examples:
            return 0
        existing = conn.execute(
            "SELECT 1 FROM entry_selection_prediction_builds WHERE event_open_ms=? AND lab_version=? AND selector_version=?",
            (event_open_ms, self.config.lab_version, spec.selector_version),
        ).fetchone()
        if existing is not None and not rebuild:
            return 0

        model: dict[str, Any] | None = None
        training_event_count = 0
        training_row_count = 0
        trained_through: int | None = None
        model_digest: str | None = None
        if spec.is_learned:
            training_rows, training_event_count, trained_through = self._training_rows(conn, event_open_ms)
            training_row_count = len(training_rows)
            if training_event_count < self.config.min_train_events:
                return 0
            model = _fit_ridge(training_rows, self.config.ridge_alpha)
            model.update({
                "trained_through_event_ms": trained_through,
                "training_event_count": training_event_count,
                "training_row_count": training_row_count,
            })
            model_digest = _digest({key: value for key, value in model.items() if key != "model_digest"})
        scored: list[tuple[float, dict[str, Any]]] = []
        for example in examples:
            score = _ridge_score(model, str(example["feature_vector_json"])) if model is not None else self._baseline_score(spec, example)
            scored.append((score, example))
        scored.sort(key=lambda item: (-item[0], str(item[1]["symbol"]), str(item[1]["side"])))
        scored_at_ms = int(time.time() * 1000)
        predictions: list[dict[str, Any]] = []
        for rank, (score, example) in enumerate(scored, 1):
            row: dict[str, Any] = {
                "event_open_ms": event_open_ms,
                "symbol": str(example["symbol"]),
                "side": str(example["side"]),
                "lab_version": self.config.lab_version,
                "selector_version": spec.selector_version,
                "scored_at_ms": scored_at_ms,
                "score": 0.0 if score == 0.0 else float(score),
                "rank_in_event": rank,
                "trained_through_event_ms": trained_through,
                "training_event_count": training_event_count,
                "training_row_count": training_row_count,
                "model_digest": model_digest,
                "source_example_digest": str(example["example_digest"]),
                "prediction_digest": "",
            }
            row["prediction_digest"] = _row_digest(row, PREDICTION_DIGEST_FIELDS)
            predictions.append(row)
        source_digest = _digest({
            "event_examples": [[row["symbol"], row["side"], row["example_digest"]] for row in examples],
            "model_digest": model_digest,
        })
        prediction_digest = _rows_digest(
            predictions, PREDICTION_DIGEST_FIELDS,
            key_fields=("event_open_ms", "selector_version", "rank_in_event", "symbol", "side"),
        )
        if rebuild:
            conn.execute(
                "DELETE FROM entry_selection_prediction_builds WHERE event_open_ms=? AND lab_version=? AND selector_version=?",
                (event_open_ms, self.config.lab_version, spec.selector_version),
            )
            conn.execute(
                "DELETE FROM entry_selection_predictions WHERE event_open_ms=? AND selector_version=?",
                (event_open_ms, spec.selector_version),
            )
        placeholders = ",".join("?" for _ in PREDICTION_COLUMNS)
        conn.executemany(
            f"INSERT INTO entry_selection_predictions({','.join(PREDICTION_COLUMNS)}) VALUES ({placeholders})",
            [[row[field] for field in PREDICTION_COLUMNS] for row in predictions],
        )
        conn.execute(
            """
            INSERT INTO entry_selection_prediction_builds(
                event_open_ms, lab_version, selector_version, built_at_ms, prediction_row_count,
                training_event_count, training_row_count, trained_through_event_ms, model_digest,
                source_digest, prediction_digest
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_open_ms, self.config.lab_version, spec.selector_version, scored_at_ms, len(predictions),
                training_event_count, training_row_count, trained_through, model_digest, source_digest, prediction_digest,
            ),
        )
        return len(predictions)

    def build(self, *, max_events: int | None = None, rebuild: bool = False) -> SelectionBuildResult:
        self.initialize()
        limit = self.config.max_events_per_build if max_events is None else max_events
        if limit < 0:
            raise ValueError("max_events must be non-negative")
        with self.db.connection() as conn:
            source_events, source_rows = self._source_counts(conn)
            targets = self._target_events(conn, limit, rebuild)
            pending_before = int(conn.execute(
                "SELECT COUNT(DISTINCT r.event_open_ms) FROM exit_policy_results r "
                "WHERE r.lab_version=? AND r.policy_version=? AND NOT EXISTS ("
                "SELECT 1 FROM entry_selection_builds b WHERE b.event_open_ms=r.event_open_ms AND b.lab_version=?)",
                (self.config.policy_lab_version, self.config.target_policy_version, self.config.lab_version),
            ).fetchone()[0])
            built_example_events = 0
            for event_open_ms in targets:
                self._build_examples_for_event(conn, event_open_ms, rebuild)
                conn.commit()
                built_example_events += 1

            all_events = [int(row[0]) for row in conn.execute(
                "SELECT event_open_ms FROM entry_selection_builds WHERE lab_version=? ORDER BY event_open_ms",
                (self.config.lab_version,),
            ).fetchall()]
            baseline_rows = 0
            learned_rows = 0
            learned_ready_events = 0
            for event_open_ms in all_events:
                for spec in BASELINE_SELECTORS:
                    baseline_rows += self._score_event(conn, event_open_ms, spec, rebuild)
                    conn.commit()
                prior_events = int(conn.execute(
                    "SELECT COUNT(DISTINCT event_open_ms) FROM entry_selection_examples WHERE lab_version=? AND event_open_ms<?",
                    (self.config.lab_version, event_open_ms),
                ).fetchone()[0])
                if prior_events >= self.config.min_train_events:
                    learned_ready_events += 1
                    learned_rows += self._score_event(conn, event_open_ms, SELECTOR_BY_VERSION[self.config.learned_selector_version], rebuild)
                    conn.commit()

            example_rows = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=?", (self.config.lab_version,)
            ).fetchone()[0])
        return SelectionBuildResult(
            self.config.lab_version, self.config.target_policy_version, source_events, source_rows,
            pending_before, len(targets), built_example_events, example_rows,
            baseline_rows, learned_rows, learned_ready_events,
        )

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            source_events, source_rows = self._source_counts(conn)
            example_events, example_rows = conn.execute(
                "SELECT COUNT(DISTINCT event_open_ms), COUNT(*) FROM entry_selection_examples WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            predictions = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=?", (self.config.lab_version,)
            ).fetchone()[0])
            learned_predictions = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? AND selector_version=?",
                (self.config.lab_version, self.config.learned_selector_version),
            ).fetchone()[0])
            learned_scored_events = int(conn.execute(
                "SELECT COUNT(DISTINCT event_open_ms) FROM entry_selection_predictions WHERE lab_version=? AND selector_version=?",
                (self.config.lab_version, self.config.learned_selector_version),
            ).fetchone()[0])
            counts = {
                str(selector): int(count)
                for selector, count in conn.execute(
                    "SELECT selector_version, COUNT(*) FROM entry_selection_predictions WHERE lab_version=? GROUP BY selector_version ORDER BY selector_version",
                    (self.config.lab_version,),
                ).fetchall()
            }
            latest = conn.execute(
                "SELECT event_open_ms, example_row_count, example_digest FROM entry_selection_builds "
                "WHERE lab_version=? ORDER BY event_open_ms DESC LIMIT 1",
                (self.config.lab_version,),
            ).fetchone()
        return {
            "lab_version": self.config.lab_version,
            "target_policy_version": self.config.target_policy_version,
            "target_policy_status": self.config.target_policy_status,
            "source_events": source_events,
            "source_rows": source_rows,
            "example_events": int(example_events),
            "example_rows": int(example_rows),
            "pending_example_events": max(0, source_events - int(example_events)),
            "selector_count": len(SELECTORS),
            "prediction_rows": predictions,
            "prediction_counts": counts,
            "min_train_events": self.config.min_train_events,
            "learned_scored_events": learned_scored_events,
            "learned_prediction_rows": learned_predictions,
            "latest_example_build": latest,
            "authority": "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION",
        }

    @staticmethod
    def _profit_factor(values: list[float]) -> float | None:
        gains = sum(value for value in values if value > 0)
        losses = -sum(value for value in values if value < 0)
        if losses <= 0:
            return None
        return gains / losses

    @staticmethod
    def _max_drawdown(values: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        return max_dd

    def report(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            examples = {
                (int(event), str(symbol), str(side)): float(target)
                for event, symbol, side, target in conn.execute(
                    "SELECT event_open_ms, symbol, side, target_net_r FROM entry_selection_examples WHERE lab_version=?",
                    (self.config.lab_version,),
                ).fetchall()
            }
            prediction_rows = conn.execute(
                "SELECT event_open_ms, symbol, side, selector_version, score, rank_in_event "
                "FROM entry_selection_predictions WHERE lab_version=? ORDER BY selector_version, event_open_ms, rank_in_event",
                (self.config.lab_version,),
            ).fetchall()
        random_selected_mean: float | None = None
        policy_reports: dict[str, Any] = {}
        for spec in SELECTORS:
            rows = [row for row in prediction_rows if row[3] == spec.selector_version]
            by_event: dict[int, list[tuple[Any, ...]]] = {}
            for row in rows:
                by_event.setdefault(int(row[0]), []).append(row)
            selected_values: list[float] = []
            regrets: list[float] = []
            selected_symbols: list[str] = []
            bucket_top: list[float] = []
            bucket_middle: list[float] = []
            bucket_bottom: list[float] = []
            for event in sorted(by_event):
                event_rows = sorted(by_event[event], key=lambda row: int(row[5]))
                if not event_rows:
                    continue
                selected = event_rows[0]
                selected_target = examples[(event, str(selected[1]), str(selected[2]))]
                selected_values.append(selected_target)
                selected_symbols.append(str(selected[1]))
                event_targets = [examples[(event, str(row[1]), str(row[2]))] for row in event_rows]
                regrets.append(max(event_targets) - selected_target)
                n = len(event_rows)
                for index, row in enumerate(event_rows):
                    target = examples[(event, str(row[1]), str(row[2]))]
                    bucket = min(2, (index * 3) // n)
                    (bucket_top if bucket == 0 else bucket_middle if bucket == 1 else bucket_bottom).append(target)
            if not rows:
                policy_reports[spec.selector_version] = {"rows": 0, "independent_market_events": 0}
                continue
            concentration = 0.0
            if selected_symbols:
                concentration = max(selected_symbols.count(symbol) for symbol in set(selected_symbols)) / len(selected_symbols)
            report = {
                "family": spec.family,
                "is_learned": spec.is_learned,
                "rows": len(rows),
                "independent_market_events": len(by_event),
                "selected_mean_net_r": statistics.fmean(selected_values) if selected_values else None,
                "selected_median_net_r": statistics.median(selected_values) if selected_values else None,
                "selected_win_rate": (sum(value > 0 for value in selected_values) / len(selected_values)) if selected_values else None,
                "selected_profit_factor": self._profit_factor(selected_values) if selected_values else None,
                "mean_event_selection_regret_r": statistics.fmean(regrets) if regrets else None,
                "sequential_max_drawdown_r": self._max_drawdown(selected_values),
                "max_selected_symbol_concentration": concentration,
                "top_bucket_mean_net_r": statistics.fmean(bucket_top) if bucket_top else None,
                "middle_bucket_mean_net_r": statistics.fmean(bucket_middle) if bucket_middle else None,
                "bottom_bucket_mean_net_r": statistics.fmean(bucket_bottom) if bucket_bottom else None,
                "top_minus_bottom_net_r": (statistics.fmean(bucket_top) - statistics.fmean(bucket_bottom)) if bucket_top and bucket_bottom else None,
            }
            if spec.selector_version == "RANDOM_HASH_BASELINE_V1":
                random_selected_mean = report["selected_mean_net_r"]
            policy_reports[spec.selector_version] = report
        if random_selected_mean is not None:
            for report in policy_reports.values():
                if report.get("selected_mean_net_r") is not None:
                    report["selected_mean_net_r_lift_vs_random"] = report["selected_mean_net_r"] - random_selected_mean
        return {
            "lab_version": self.config.lab_version,
            "target_policy_version": self.config.target_policy_version,
            "target_policy_status": self.config.target_policy_status,
            "target": self.config.target_name,
            "authority": "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION",
            "calibration_note": "RIDGE_EXPECTED_NET_R_V1_IS_REGRESSION_NOT_A_PROBABILITY_MODEL_CALIBRATION_NOT_APPLICABLE",
            "independence_note": "MARKET_EVENTS_NOT_SYMBOL_ROWS_ARE_THE_PRIMARY_INDEPENDENT_PROOF_UNIT",
            "selectors": policy_reports,
        }

    def _stored_example_rows(self, conn, event_open_ms: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"SELECT {','.join(EXAMPLE_COLUMNS)} FROM entry_selection_examples WHERE event_open_ms=? AND lab_version=? ORDER BY symbol, side",
            (event_open_ms, self.config.lab_version),
        ).fetchall()
        return [dict(zip(EXAMPLE_COLUMNS, row)) for row in rows]

    def _stored_prediction_rows(self, conn, event_open_ms: int, selector_version: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"SELECT {','.join(PREDICTION_COLUMNS)} FROM entry_selection_predictions "
            "WHERE event_open_ms=? AND selector_version=? ORDER BY rank_in_event, symbol, side",
            (event_open_ms, selector_version),
        ).fetchall()
        return [dict(zip(PREDICTION_COLUMNS, row)) for row in rows]

    def audit(self) -> dict[str, Any]:
        self.initialize()
        expected_lab_hash = _digest(self.definition())
        expected_selector_hashes: dict[str, str] = {}
        for spec in SELECTORS:
            definition = spec.definition()
            if spec.selector_version == self.config.learned_selector_version:
                definition = dict(definition)
                definition["parameters"] = dict(definition["parameters"])
                definition["parameters"].update({
                    "min_train_events": self.config.min_train_events,
                    "ridge_alpha": self.config.ridge_alpha,
                    "feature_names": list(FEATURE_VECTOR_NAMES),
                })
            expected_selector_hashes[spec.selector_version] = _digest(definition)

        report = {
            "lab_version": self.config.lab_version,
            "target_policy_version": self.config.target_policy_version,
            "example_rows": 0,
            "prediction_rows": 0,
            "lab_definition_mismatch": 0,
            "selector_definition_mismatches": 0,
            "target_policy_mismatches": 0,
            "examples_without_policy_result": 0,
            "policy_result_digest_mismatches": 0,
            "feature_source_digest_mismatches": 0,
            "signal_source_digest_mismatches": 0,
            "future_feature_source_rows": 0,
            "feature_vector_mismatches": 0,
            "example_digest_mismatches": 0,
            "example_build_row_mismatches": 0,
            "example_build_digest_mismatches": 0,
            "example_build_source_digest_mismatches": 0,
            "predictions_without_example": 0,
            "prediction_source_digest_mismatches": 0,
            "prediction_digest_mismatches": 0,
            "prediction_rank_mismatches": 0,
            "baseline_prediction_count_mismatches": 0,
            "learned_training_leakage": 0,
            "learned_before_min_train_events": 0,
            "learned_model_digest_mismatches": 0,
            "prediction_build_row_mismatches": 0,
            "prediction_build_digest_mismatches": 0,
            "prediction_build_source_digest_mismatches": 0,
        }
        with self.db.connection() as conn:
            stored_lab = conn.execute(
                "SELECT feature_version, policy_lab_version, target_policy_version, definition_hash FROM entry_selection_labs WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            if stored_lab != (
                self.config.feature_version, self.config.policy_lab_version,
                self.config.target_policy_version, expected_lab_hash,
            ):
                report["lab_definition_mismatch"] += 1
            for version, expected_hash in expected_selector_hashes.items():
                row = conn.execute(
                    "SELECT lab_version, definition_hash FROM entry_selector_sets WHERE selector_version=?", (version,)
                ).fetchone()
                if row != (self.config.lab_version, expected_hash):
                    report["selector_definition_mismatches"] += 1

            report["example_rows"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=?", (self.config.lab_version,)
            ).fetchone()[0])
            report["prediction_rows"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=?", (self.config.lab_version,)
            ).fetchone()[0])
            report["target_policy_mismatches"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=? AND target_policy_version<>?",
                (self.config.lab_version, self.config.target_policy_version),
            ).fetchone()[0])
            report["examples_without_policy_result"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_examples e
                LEFT JOIN exit_policy_results r
                  ON r.event_open_ms=e.event_open_ms AND r.symbol=e.symbol AND r.side=e.side
                 AND r.policy_version=e.target_policy_version
                WHERE e.lab_version=? AND r.event_open_ms IS NULL
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["policy_result_digest_mismatches"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_examples e
                JOIN exit_policy_results r
                  ON r.event_open_ms=e.event_open_ms AND r.symbol=e.symbol AND r.side=e.side
                 AND r.policy_version=e.target_policy_version
                WHERE e.lab_version=? AND e.source_policy_result_digest<>r.result_digest
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["feature_source_digest_mismatches"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_examples e
                JOIN feature_builds b ON b.event_open_ms=e.event_open_ms AND b.feature_version=e.feature_version
                WHERE e.lab_version=? AND e.source_feature_digest<>b.feature_digest
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["signal_source_digest_mismatches"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_examples e
                JOIN feature_builds b ON b.event_open_ms=e.event_open_ms AND b.feature_version=e.feature_version
                WHERE e.lab_version=? AND e.source_signal_digest<>b.signal_digest
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["future_feature_source_rows"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_examples e
                JOIN canonical_features f ON f.event_open_ms=e.event_open_ms AND f.symbol=e.symbol AND f.feature_version=e.feature_version
                WHERE e.lab_version=? AND f.source_max_event_open_ms>e.event_open_ms
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["predictions_without_example"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_predictions p
                LEFT JOIN entry_selection_examples e
                  ON e.event_open_ms=p.event_open_ms AND e.symbol=p.symbol AND e.side=p.side AND e.lab_version=p.lab_version
                WHERE p.lab_version=? AND e.event_open_ms IS NULL
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["prediction_source_digest_mismatches"] = int(conn.execute(
                """
                SELECT COUNT(*) FROM entry_selection_predictions p
                JOIN entry_selection_examples e
                  ON e.event_open_ms=p.event_open_ms AND e.symbol=p.symbol AND e.side=p.side AND e.lab_version=p.lab_version
                WHERE p.lab_version=? AND p.source_example_digest<>e.example_digest
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["learned_training_leakage"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? AND selector_version=? "
                "AND (trained_through_event_ms IS NULL OR trained_through_event_ms>=event_open_ms)",
                (self.config.lab_version, self.config.learned_selector_version),
            ).fetchone()[0])
            report["learned_before_min_train_events"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? AND selector_version=? AND training_event_count<?",
                (self.config.lab_version, self.config.learned_selector_version, self.config.min_train_events),
            ).fetchone()[0])

            event_ids = [int(row[0]) for row in conn.execute(
                "SELECT event_open_ms FROM entry_selection_builds WHERE lab_version=? ORDER BY event_open_ms",
                (self.config.lab_version,),
            ).fetchall()]
            for event_open_ms in event_ids:
                stored_examples = self._stored_example_rows(conn, event_open_ms)
                features = self._feature_rows(conn, event_open_ms)
                signals = self._signal_rows(conn, event_open_ms)
                current_policy = {
                    (str(symbol), str(side)): str(digest)
                    for symbol, side, digest in conn.execute(
                        "SELECT symbol, side, result_digest FROM exit_policy_results WHERE event_open_ms=? AND lab_version=? AND policy_version=?",
                        (event_open_ms, self.config.policy_lab_version, self.config.target_policy_version),
                    ).fetchall()
                }
                build = conn.execute(
                    "SELECT feature_digest, signal_digest FROM feature_builds WHERE event_open_ms=? AND feature_version=?",
                    (event_open_ms, self.config.feature_version),
                ).fetchone()
                if build is None:
                    continue
                current_source_rows = []
                for row in stored_examples:
                    feature = features.get(str(row["symbol"]))
                    if feature is None:
                        report["feature_vector_mismatches"] += 1
                        continue
                    vector = _feature_vector(feature, signals.get(str(row["symbol"]), {}), str(row["side"]))
                    if _canonical_json(vector) != str(row["feature_vector_json"]):
                        report["feature_vector_mismatches"] += 1
                    if _row_digest(row, EXAMPLE_DIGEST_FIELDS) != row["example_digest"]:
                        report["example_digest_mismatches"] += 1
                    current_source_rows.append([
                        row["symbol"], row["side"], current_policy.get((str(row["symbol"]), str(row["side"]))), str(build[0]), str(build[1])
                    ])
                build_row = conn.execute(
                    "SELECT example_row_count, source_digest, example_digest FROM entry_selection_builds WHERE event_open_ms=? AND lab_version=?",
                    (event_open_ms, self.config.lab_version),
                ).fetchone()
                if build_row is not None:
                    if int(build_row[0]) != len(stored_examples):
                        report["example_build_row_mismatches"] += 1
                    current_example_digest = _rows_digest(stored_examples, EXAMPLE_DIGEST_FIELDS, key_fields=("event_open_ms", "symbol", "side"))
                    if str(build_row[2]) != current_example_digest:
                        report["example_build_digest_mismatches"] += 1
                    if str(build_row[1]) != _digest(current_source_rows):
                        report["example_build_source_digest_mismatches"] += 1

            prediction_builds = conn.execute(
                "SELECT event_open_ms, selector_version, prediction_row_count, training_event_count, training_row_count, "
                "trained_through_event_ms, model_digest, source_digest, prediction_digest "
                "FROM entry_selection_prediction_builds WHERE lab_version=? ORDER BY event_open_ms, selector_version",
                (self.config.lab_version,),
            ).fetchall()
            for build_row in prediction_builds:
                event_open_ms = int(build_row[0])
                selector_version = str(build_row[1])
                predictions = self._stored_prediction_rows(conn, event_open_ms, selector_version)
                examples = self._examples_for_event(conn, event_open_ms)
                if int(build_row[2]) != len(predictions):
                    report["prediction_build_row_mismatches"] += 1
                ranks = [int(row["rank_in_event"]) for row in predictions]
                if ranks != list(range(1, len(predictions) + 1)):
                    report["prediction_rank_mismatches"] += 1
                for row in predictions:
                    if _row_digest(row, PREDICTION_DIGEST_FIELDS) != row["prediction_digest"]:
                        report["prediction_digest_mismatches"] += 1
                current_prediction_digest = _rows_digest(
                    predictions, PREDICTION_DIGEST_FIELDS,
                    key_fields=("event_open_ms", "selector_version", "rank_in_event", "symbol", "side"),
                )
                if str(build_row[8]) != current_prediction_digest:
                    report["prediction_build_digest_mismatches"] += 1
                model_digest = build_row[6]
                if selector_version == self.config.learned_selector_version:
                    training_rows, event_count, trained_through = self._training_rows(conn, event_open_ms)
                    if event_count >= self.config.min_train_events:
                        model = _fit_ridge(training_rows, self.config.ridge_alpha)
                        model.update({
                            "trained_through_event_ms": trained_through,
                            "training_event_count": event_count,
                            "training_row_count": len(training_rows),
                        })
                        expected_model_digest = _digest({key: value for key, value in model.items() if key != "model_digest"})
                        if str(model_digest) != expected_model_digest:
                            report["learned_model_digest_mismatches"] += 1
                expected_source = _digest({
                    "event_examples": [[row["symbol"], row["side"], row["example_digest"]] for row in examples],
                    "model_digest": model_digest,
                })
                if str(build_row[7]) != expected_source:
                    report["prediction_build_source_digest_mismatches"] += 1

            for event_open_ms in event_ids:
                example_count = int(conn.execute(
                    "SELECT COUNT(*) FROM entry_selection_examples WHERE event_open_ms=? AND lab_version=?",
                    (event_open_ms, self.config.lab_version),
                ).fetchone()[0])
                for spec in BASELINE_SELECTORS:
                    count = int(conn.execute(
                        "SELECT COUNT(*) FROM entry_selection_predictions WHERE event_open_ms=? AND selector_version=?",
                        (event_open_ms, spec.selector_version),
                    ).fetchone()[0])
                    if count != example_count:
                        report["baseline_prediction_count_mismatches"] += 1
        return report
