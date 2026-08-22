from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import dataclass
from typing import Any, Iterable

from .database import EvidenceDatabase
from .features import (
    CANONICAL_FEATURE_FIELDS,
    CANONICAL_FEATURE_VERSION,
    CanonicalFeatureStore,
    _rows_digest as _canonical_feature_rows_digest,
)
from .policies import (
    CONTROL_POLICY_VERSION,
    LAB_VERSION as POLICY_LAB_VERSION,
    RESULT_COLUMNS as POLICY_RESULT_COLUMNS,
    ExitPolicyLab,
    _result_digest as _policy_result_digest,
)
from .signals import (
    SIGNAL_ANNOTATION_FIELDS,
    SIGNAL_VERSIONS,
    ResearchSignalStore,
    _signal_rows_digest,
)


@dataclass(frozen=True)
class SelectionConfig:
    """Frozen V2-equivalent V3.4.5 entry-selection research definition."""

    lab_version: str = "ENTRY_SELECTION_LAB_V1"
    feature_version: str = CANONICAL_FEATURE_VERSION
    policy_lab_version: str = POLICY_LAB_VERSION
    target_policy_version: str = CONTROL_POLICY_VERSION
    target_policy_status: str = "CONTROL_BENCHMARK_NOT_PROMOTED"
    target_name: str = "AFTER_COST_NET_R"
    learned_selector_version: str = "RIDGE_EXPECTED_NET_R_V1"
    min_train_events: int = 20
    ridge_alpha: float = 10.0
    max_events_per_build: int = 100

    def validate(self) -> None:
        if self.lab_version != "ENTRY_SELECTION_LAB_V1":
            raise ValueError("NBOT_V345_LAB_VERSION_IMMUTABLE")
        if self.feature_version != CANONICAL_FEATURE_VERSION:
            raise ValueError("NBOT_V345_FEATURE_VERSION_IMMUTABLE")
        if self.policy_lab_version != POLICY_LAB_VERSION:
            raise ValueError("NBOT_V345_POLICY_LAB_VERSION_IMMUTABLE")
        if self.target_policy_version != CONTROL_POLICY_VERSION:
            raise ValueError("NBOT_V345_TARGET_POLICY_IMMUTABLE")
        if self.target_name != "AFTER_COST_NET_R":
            raise ValueError("NBOT_V345_TARGET_IMMUTABLE")
        if self.learned_selector_version != "RIDGE_EXPECTED_NET_R_V1":
            raise ValueError("NBOT_V345_LEARNED_SELECTOR_IMMUTABLE")
        if self.min_train_events != 20:
            raise ValueError("NBOT_V345_MIN_TRAIN_EVENTS_IMMUTABLE")
        if self.ridge_alpha != 10.0:
            raise ValueError("NBOT_V345_RIDGE_ALPHA_IMMUTABLE")
        if self.max_events_per_build <= 0:
            raise ValueError("NBOT_V345_BUILD_LIMIT_INVALID")


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
            "candidate_universe": "ALL_V344_TARGET_POLICY_SYMBOL_SIDE_RESULTS_NO_SIGNAL_GATING",
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
        "Ranks candidates by side-aligned V3.4.2 intraday conditional score.",
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
    "event_open_ms", "symbol", "side", "lab_version", "feature_version", "policy_lab_version", "target_policy_version",
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

SELECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS entry_selection_labs (
    lab_version TEXT PRIMARY KEY,
    feature_version TEXT NOT NULL,
    policy_lab_version TEXT NOT NULL,
    target_policy_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version),
    FOREIGN KEY (policy_lab_version) REFERENCES exit_policy_labs(lab_version),
    FOREIGN KEY (target_policy_version) REFERENCES exit_policy_sets(policy_version)
);
CREATE TABLE IF NOT EXISTS entry_selector_sets (
    selector_version TEXT PRIMARY KEY,
    lab_version TEXT NOT NULL,
    family TEXT NOT NULL,
    is_learned INTEGER NOT NULL CHECK (is_learned IN (0,1)),
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version)
);
CREATE TABLE IF NOT EXISTS entry_selection_examples (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG','SHORT')),
    lab_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    policy_lab_version TEXT NOT NULL,
    target_policy_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    target_net_r REAL NOT NULL,
    target_net_return_frac REAL NOT NULL,
    target_mfe_r REAL NOT NULL,
    target_mae_r REAL NOT NULL,
    source_policy_result_digest TEXT NOT NULL,
    source_feature_digest TEXT NOT NULL,
    source_signal_digest TEXT NOT NULL,
    feature_vector_json TEXT NOT NULL,
    example_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, side, lab_version),
    FOREIGN KEY (event_open_ms, symbol, side, target_policy_version, policy_lab_version)
        REFERENCES exit_policy_results(event_open_ms, symbol, side, policy_version, lab_version)
        ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version)
);
CREATE TABLE IF NOT EXISTS entry_selection_builds (
    event_open_ms INTEGER NOT NULL,
    lab_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    example_row_count INTEGER NOT NULL CHECK (example_row_count >= 0),
    source_digest TEXT NOT NULL,
    example_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, lab_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version)
);
CREATE TABLE IF NOT EXISTS entry_selection_predictions (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG','SHORT')),
    lab_version TEXT NOT NULL,
    selector_version TEXT NOT NULL,
    scored_at_ms INTEGER NOT NULL,
    score REAL NOT NULL,
    rank_in_event INTEGER NOT NULL CHECK (rank_in_event > 0),
    trained_through_event_ms INTEGER,
    training_event_count INTEGER NOT NULL CHECK (training_event_count >= 0),
    training_row_count INTEGER NOT NULL CHECK (training_row_count >= 0),
    model_digest TEXT,
    source_example_digest TEXT NOT NULL,
    prediction_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, side, selector_version),
    FOREIGN KEY (event_open_ms, symbol, side, lab_version)
        REFERENCES entry_selection_examples(event_open_ms, symbol, side, lab_version)
        ON DELETE CASCADE,
    FOREIGN KEY (selector_version) REFERENCES entry_selector_sets(selector_version)
);
CREATE TABLE IF NOT EXISTS entry_selection_prediction_builds (
    event_open_ms INTEGER NOT NULL,
    lab_version TEXT NOT NULL,
    selector_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    prediction_row_count INTEGER NOT NULL CHECK (prediction_row_count >= 0),
    training_event_count INTEGER NOT NULL CHECK (training_event_count >= 0),
    training_row_count INTEGER NOT NULL CHECK (training_row_count >= 0),
    trained_through_event_ms INTEGER,
    model_digest TEXT,
    source_digest TEXT NOT NULL,
    prediction_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, lab_version, selector_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version),
    FOREIGN KEY (selector_version) REFERENCES entry_selector_sets(selector_version)
);
CREATE INDEX IF NOT EXISTS idx_entry_selection_examples_event
    ON entry_selection_examples(event_open_ms, lab_version);
CREATE INDEX IF NOT EXISTS idx_entry_selection_predictions_event
    ON entry_selection_predictions(event_open_ms, lab_version, selector_version, rank_in_event);
CREATE INDEX IF NOT EXISTS idx_entry_selection_predictions_selector_time
    ON entry_selection_predictions(selector_version, event_open_ms, rank_in_event);
CREATE TABLE IF NOT EXISTS entry_selection_ridge_state (
    lab_version TEXT PRIMARY KEY,
    selector_version TEXT NOT NULL,
    through_event_ms INTEGER,
    training_event_count INTEGER NOT NULL CHECK (training_event_count >= 0),
    training_row_count INTEGER NOT NULL CHECK (training_row_count >= 0),
    state_json TEXT NOT NULL,
    state_digest TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version),
    FOREIGN KEY (selector_version) REFERENCES entry_selector_sets(selector_version)
);
"""

RESEARCH_SELECTION_TABLES = (
    "entry_selection_labs",
    "entry_selector_sets",
    "entry_selection_examples",
    "entry_selection_builds",
    "entry_selection_predictions",
    "entry_selection_prediction_builds",
    "entry_selection_ridge_state",
)


class EntrySelectionError(RuntimeError):
    """Selection definition, chronology, lineage, or persistence is inconsistent."""


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
        raise EntrySelectionError("NBOT_V345_FEATURE_VECTOR_ORDER_CHANGED")
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



@dataclass
class RidgeSufficientStatistics:
    """Cumulative raw moments for exact forward-only Ridge chronology.

    This state contains only decision-time feature vectors and targets from
    completed prior events.  It never contains the event currently being
    scored, so the V3.4.5 no-lookahead contract is preserved.
    """

    event_count: int
    row_count: int
    through_event_ms: int | None
    sum_y: float
    sum_x: list[float]
    sum_x2: list[float]
    sum_xy: list[float]
    sum_xx: list[list[float]]

    @classmethod
    def empty(cls) -> "RidgeSufficientStatistics":
        d = len(FEATURE_VECTOR_NAMES)
        return cls(
            event_count=0,
            row_count=0,
            through_event_ms=None,
            sum_y=0.0,
            sum_x=[0.0] * d,
            sum_x2=[0.0] * d,
            sum_xy=[0.0] * d,
            sum_xx=[[0.0] * d for _ in range(d)],
        )

    def add_event(self, event_open_ms: int, rows: list[dict[str, Any]]) -> None:
        event_open_ms = int(event_open_ms)
        if self.through_event_ms is not None and event_open_ms <= self.through_event_ms:
            raise EntrySelectionError("NBOT_V381R_RIDGE_STATE_CHRONOLOGY_INVALID")
        if not rows:
            raise EntrySelectionError("NBOT_V381R_RIDGE_STATE_EMPTY_EVENT")
        d = len(FEATURE_VECTOR_NAMES)
        for row in rows:
            vector = json.loads(str(row["feature_vector_json"]))
            x = [_f(vector[name]) for name in FEATURE_VECTOR_NAMES]
            y = _f(row["target_net_r"])
            self.sum_y = math.fsum((self.sum_y, y))
            for i in range(d):
                xi = x[i]
                self.sum_x[i] = math.fsum((self.sum_x[i], xi))
                self.sum_x2[i] = math.fsum((self.sum_x2[i], xi * xi))
                self.sum_xy[i] = math.fsum((self.sum_xy[i], xi * y))
                for j in range(i, d):
                    self.sum_xx[i][j] = math.fsum((self.sum_xx[i][j], xi * x[j]))
        for i in range(d):
            for j in range(i):
                self.sum_xx[i][j] = self.sum_xx[j][i]
        self.row_count += len(rows)
        self.event_count += 1
        self.through_event_ms = event_open_ms

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "row_count": self.row_count,
            "through_event_ms": self.through_event_ms,
            "sum_y": self.sum_y,
            "sum_x": self.sum_x,
            "sum_x2": self.sum_x2,
            "sum_xy": self.sum_xy,
            "sum_xx": self.sum_xx,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RidgeSufficientStatistics":
        d = len(FEATURE_VECTOR_NAMES)
        state = cls(
            event_count=int(payload["event_count"]),
            row_count=int(payload["row_count"]),
            through_event_ms=(
                None if payload.get("through_event_ms") is None
                else int(payload["through_event_ms"])
            ),
            sum_y=float(payload["sum_y"]),
            sum_x=[float(v) for v in payload["sum_x"]],
            sum_x2=[float(v) for v in payload["sum_x2"]],
            sum_xy=[float(v) for v in payload["sum_xy"]],
            sum_xx=[[float(v) for v in row] for row in payload["sum_xx"]],
        )
        if not (
            len(state.sum_x) == len(state.sum_x2) == len(state.sum_xy) == d
            and len(state.sum_xx) == d
            and all(len(row) == d for row in state.sum_xx)
        ):
            raise EntrySelectionError("NBOT_V381R_RIDGE_STATE_DIMENSION_INVALID")
        return state

    def fit(self, alpha: float) -> dict[str, Any]:
        if self.row_count <= 0:
            raise ValueError("cannot fit ridge without rows")
        n = float(self.row_count)
        d = len(FEATURE_VECTOR_NAMES)
        means: dict[str, float] = {}
        scales: dict[str, float] = {}
        means_list: list[float] = []
        scales_list: list[float] = []
        for i, name in enumerate(FEATURE_VECTOR_NAMES):
            mean = self.sum_x[i] / n
            variance = max(0.0, (self.sum_x2[i] / n) - mean * mean)
            scale = math.sqrt(variance)
            mean = 0.0 if mean == 0.0 else mean
            scale = scale if scale > 1e-12 else 1.0
            means[name] = mean
            scales[name] = scale
            means_list.append(mean)
            scales_list.append(scale)

        # With training-window z-scoring each feature is centered by
        # construction.  Solve only the penalized slope block and keep the
        # unpenalized intercept at mean(y).  This is algebraically the same
        # Ridge objective as _fit_ridge(), but avoids coupling the intercept
        # to tiny floating-point residuals in sum(z) that can create a large
        # common score offset in an otherwise rank-identical model.
        xtx = [[0.0 for _ in range(d)] for _ in range(d)]
        xty = [0.0 for _ in range(d)]
        for i in range(d):
            mean_i = means_list[i]
            scale_i = scales_list[i]
            xty[i] = (self.sum_xy[i] - mean_i * self.sum_y) / scale_i
            for j in range(i, d):
                mean_j = means_list[j]
                scale_j = scales_list[j]
                centered = (
                    self.sum_xx[i][j]
                    - mean_i * self.sum_x[j]
                    - mean_j * self.sum_x[i]
                    + n * mean_i * mean_j
                )
                value = centered / (scale_i * scale_j)
                xtx[i][j] = value
                xtx[j][i] = value
        for index in range(d):
            xtx[index][index] += alpha
        coefficients = _solve_linear_system(xtx, xty)
        model = {
            "selector_version": "RIDGE_EXPECTED_NET_R_V1",
            "feature_names": list(FEATURE_VECTOR_NAMES),
            "alpha": float(alpha),
            "means": means,
            "scales": scales,
            "intercept": self.sum_y / n,
            "coefficients": dict(zip(FEATURE_VECTOR_NAMES, coefficients)),
        }
        model["model_digest"] = _digest(model)
        return model

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
    """V3.4.5 research-only ranking over V3 features and V3.4.4 control labels."""

    def __init__(self, db: EvidenceDatabase, config: SelectionConfig | None = None):
        self.db = db
        self.config = config or SelectionConfig()
        self.config.validate()
        self.feature_store = CanonicalFeatureStore(db)
        self.signal_store = ResearchSignalStore(db)
        self.policy_lab = ExitPolicyLab(db)

    def definition(self) -> dict[str, Any]:
        return {
            "lab_version": self.config.lab_version,
            "feature_version": self.config.feature_version,
            "policy_lab_version": self.config.policy_lab_version,
            "target_policy_version": self.config.target_policy_version,
            "target_policy_status": self.config.target_policy_status,
            "target_name": self.config.target_name,
            "candidate_universe": "ALL_V344_TARGET_POLICY_RESULTS_BOTH_SIDES_NO_SIGNAL_GATING",
            "feature_vector_names": list(FEATURE_VECTOR_NAMES),
            "learned_selector_version": self.config.learned_selector_version,
            "min_train_events": self.config.min_train_events,
            "ridge_alpha": self.config.ridge_alpha,
            "chronology_rule": "FOR_EVENT_T_LEARNED_MODEL_USES_ONLY_EXAMPLES_WITH_EVENT_LT_T",
            "evaluation_independence": "MARKET_EVENT_IS_PRIMARY_INDEPENDENT_UNIT_NOT_SYMBOL_ROW",
            "probability_calibration": "NOT_APPLICABLE_TO_EXPECTED_NET_R_REGRESSION",
            "authority": "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION",
        }

    @property
    def definition_hash(self) -> str:
        return _digest(self.definition())

    @property
    def selector_definition_hashes(self) -> dict[str, str]:
        result: dict[str, str] = {}
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
            result[spec.selector_version] = _digest(definition)
        return result

    def initialize(self) -> None:
        self.signal_store.initialize()
        self.policy_lab.initialize()
        now_ms = int(time.time() * 1000)
        definition = self.definition()
        definition_hash = _digest(definition)
        with self.db.connection() as conn:
            conn.executescript(SELECTION_SCHEMA)
            target = conn.execute(
                "SELECT lab_version FROM exit_policy_sets WHERE policy_version=?",
                (self.config.target_policy_version,),
            ).fetchone()
            if target is None or target[0] != self.config.policy_lab_version:
                raise EntrySelectionError("NBOT_V345_TARGET_POLICY_REGISTRATION_MISMATCH")
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
                raise EntrySelectionError(f"NBOT_V345_LAB_DEFINITION_MISMATCH:{self.config.lab_version}")
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
                    raise EntrySelectionError(f"NBOT_V345_SELECTOR_DEFINITION_MISMATCH:{spec.selector_version}")

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

    def _feature_event_digest(self, conn, event_open_ms: int) -> str:
        rows = conn.execute(
            f"SELECT {','.join(CANONICAL_FEATURE_FIELDS)} FROM canonical_features "
            "WHERE event_open_ms=? AND feature_version=? ORDER BY symbol",
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        payload = tuple(dict(zip(CANONICAL_FEATURE_FIELDS, row)) for row in rows)
        return _canonical_feature_rows_digest(payload)

    def _signal_event_digest(self, conn, event_open_ms: int) -> str:
        rows = conn.execute(
            f"SELECT {','.join(SIGNAL_ANNOTATION_FIELDS)} FROM signal_annotations "
            "WHERE event_open_ms=? AND feature_version=? ORDER BY symbol, signal_version",
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        payload = tuple(dict(zip(SIGNAL_ANNOTATION_FIELDS, row)) for row in rows)
        return _signal_rows_digest(payload)

    def _source_rows(self, conn, event_open_ms: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            f"SELECT {','.join(POLICY_RESULT_COLUMNS)} FROM exit_policy_results "
            "WHERE event_open_ms=? AND lab_version=? AND policy_version=? ORDER BY symbol, side",
            (event_open_ms, self.config.policy_lab_version, self.config.target_policy_version),
        ).fetchall()
        return [dict(zip(POLICY_RESULT_COLUMNS, row)) for row in rows]

    def _build_examples_for_event(self, conn, event_open_ms: int, rebuild: bool) -> int:
        source_rows = self._source_rows(conn, event_open_ms)
        features = self._feature_rows(conn, event_open_ms)
        signals = self._signal_rows(conn, event_open_ms)

        feature_build = conn.execute(
            "SELECT feature_digest FROM feature_builds WHERE event_open_ms=? AND feature_version=?",
            (event_open_ms, self.config.feature_version),
        ).fetchone()
        signal_build = conn.execute(
            "SELECT signal_digest FROM signal_builds WHERE event_open_ms=? AND feature_version=?",
            (event_open_ms, self.config.feature_version),
        ).fetchone()
        if feature_build is None or signal_build is None:
            raise EntrySelectionError(
                f"NBOT_V345_FEATURE_SIGNAL_BUILD_MISSING:{event_open_ms}"
            )
        source_feature_digest = str(feature_build[0])
        source_signal_digest = str(signal_build[0])
        if self._feature_event_digest(conn, event_open_ms) != source_feature_digest:
            raise EntrySelectionError(
                f"NBOT_V345_FEATURE_SOURCE_DIGEST_MISMATCH:{event_open_ms}"
            )
        if self._signal_event_digest(conn, event_open_ms) != source_signal_digest:
            raise EntrySelectionError(
                f"NBOT_V345_SIGNAL_SOURCE_DIGEST_MISMATCH:{event_open_ms}"
            )

        built_at_ms = int(time.time() * 1000)
        examples: list[dict[str, Any]] = []
        for source in source_rows:
            if str(source["feature_version"]) != self.config.feature_version:
                raise EntrySelectionError(
                    f"NBOT_V345_POLICY_FEATURE_VERSION_MISMATCH:{event_open_ms}"
                )
            if _policy_result_digest(source) != str(source["result_digest"]):
                raise EntrySelectionError(
                    f"NBOT_V345_POLICY_RESULT_DIGEST_MISMATCH:{event_open_ms}:"
                    f"{source['symbol']}:{source['side']}"
                )
            symbol = str(source["symbol"])
            feature = features.get(symbol)
            if feature is None:
                raise EntrySelectionError(
                    f"NBOT_V345_FEATURE_ROW_MISSING:{event_open_ms}:{symbol}"
                )
            if int(feature["source_max_event_open_ms"]) > event_open_ms:
                raise EntrySelectionError(
                    f"NBOT_V345_FUTURE_FEATURE_SOURCE:{event_open_ms}:{symbol}"
                )
            symbol_signals = signals.get(symbol, {})
            if set(symbol_signals) != set(SIGNAL_VERSIONS):
                raise EntrySelectionError(
                    f"NBOT_V345_SIGNAL_ANNOTATIONS_INCOMPLETE:{event_open_ms}:{symbol}"
                )
            side = str(source["side"])
            vector = _feature_vector(feature, symbol_signals, side)
            row: dict[str, Any] = {
                "event_open_ms": event_open_ms,
                "symbol": symbol,
                "side": side,
                "lab_version": self.config.lab_version,
                "feature_version": self.config.feature_version,
                "policy_lab_version": self.config.policy_lab_version,
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
            [
                row["symbol"], row["side"], row["result_digest"],
                source_feature_digest, source_signal_digest,
            ]
            for row in source_rows
        ])
        example_digest = _rows_digest(
            examples,
            EXAMPLE_DIGEST_FIELDS,
            key_fields=("event_open_ms", "symbol", "side"),
        )
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
            (
                event_open_ms,
                self.config.lab_version,
                built_at_ms,
                len(examples),
                source_digest,
                example_digest,
            ),
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


    def _compacted_history_exists(self, conn) -> bool:
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_event_ledger'"
        ).fetchone()
        if present is None:
            return False
        return conn.execute(
            "SELECT 1 FROM research_event_ledger WHERE state='COMPACTED' LIMIT 1"
        ).fetchone() is not None

    def _selection_history_meta(
        self, conn, *, before_event_ms: int | None = None, through_event_ms: int | None = None
    ) -> tuple[int, int, int | None]:
        counts: dict[int, int] = {}
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_event_ledger'"
        ).fetchone()
        if present is not None:
            for event_open_ms, row_count in conn.execute(
                "SELECT event_open_ms,example_row_count FROM research_event_ledger"
            ):
                counts[int(event_open_ms)] = int(row_count)
        for event_open_ms, row_count in conn.execute(
            "SELECT event_open_ms,example_row_count FROM entry_selection_builds WHERE lab_version=?",
            (self.config.lab_version,),
        ):
            event = int(event_open_ms)
            count = int(row_count)
            if event in counts and counts[event] != count:
                raise EntrySelectionError(
                    f"NBOT_V382_ARCHIVE_SELECTION_ROW_COUNT_MISMATCH:{event}"
                )
            counts[event] = count
        events = sorted(
            event for event in counts
            if (before_event_ms is None or event < before_event_ms)
            and (through_event_ms is None or event <= through_event_ms)
        )
        return (
            len(events),
            sum(counts[event] for event in events),
            events[-1] if events else None,
        )

    def _selection_history_event_count(self, conn, through_event_ms: int) -> int:
        return self._selection_history_meta(
            conn, through_event_ms=through_event_ms
        )[0]


    def _load_ridge_state(self, conn) -> RidgeSufficientStatistics:
        row = conn.execute(
            "SELECT through_event_ms, training_event_count, training_row_count, state_json, state_digest "
            "FROM entry_selection_ridge_state WHERE lab_version=? AND selector_version=?",
            (self.config.lab_version, self.config.learned_selector_version),
        ).fetchone()
        if row is None:
            if self._compacted_history_exists(conn):
                raise EntrySelectionError(
                    "NBOT_V382_RIDGE_STATE_MISSING_WITH_COMPACTED_HISTORY"
                )
            existing_learned = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_prediction_builds WHERE lab_version=? AND selector_version=?",
                (self.config.lab_version, self.config.learned_selector_version),
            ).fetchone()[0])
            if existing_learned:
                raise EntrySelectionError(
                    "NBOT_V381R_RIDGE_STATE_MIGRATION_REQUIRED_RESET_DERIVED_FIRST"
                )
            return RidgeSufficientStatistics.empty()
        payload = json.loads(str(row[3]))
        if _digest(payload) != str(row[4]):
            raise EntrySelectionError("NBOT_V381R_RIDGE_STATE_DIGEST_MISMATCH")
        state = RidgeSufficientStatistics.from_payload(payload)
        if (
            state.through_event_ms != row[0]
            or state.event_count != int(row[1])
            or state.row_count != int(row[2])
        ):
            raise EntrySelectionError("NBOT_V381R_RIDGE_STATE_METADATA_MISMATCH")
        if state.through_event_ms is not None:
            actual_events = self._selection_history_event_count(
                conn, int(state.through_event_ms)
            )
            if actual_events != state.event_count:
                raise EntrySelectionError(
                    "NBOT_V381R_RIDGE_STATE_CHRONOLOGY_CHANGED_REBUILD_REQUIRED"
                )
        return state

    def _save_ridge_state(self, conn, state: RidgeSufficientStatistics) -> None:
        payload = state.to_payload()
        state_json = _canonical_json(payload)
        state_digest = _digest(payload)
        conn.execute(
            """
            INSERT INTO entry_selection_ridge_state(
                lab_version, selector_version, through_event_ms,
                training_event_count, training_row_count, state_json,
                state_digest, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lab_version) DO UPDATE SET
                selector_version=excluded.selector_version,
                through_event_ms=excluded.through_event_ms,
                training_event_count=excluded.training_event_count,
                training_row_count=excluded.training_row_count,
                state_json=excluded.state_json,
                state_digest=excluded.state_digest,
                updated_at_ms=excluded.updated_at_ms
            """,
            (
                self.config.lab_version,
                self.config.learned_selector_version,
                state.through_event_ms,
                state.event_count,
                state.row_count,
                state_json,
                state_digest,
                int(time.time() * 1000),
            ),
        )

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

    def _score_event(
        self, conn, event_open_ms: int, spec: SelectorSpec, rebuild: bool,
        *, ridge_state: RidgeSufficientStatistics | None = None,
    ) -> int:
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
            if ridge_state is None:
                training_rows, training_event_count, trained_through = self._training_rows(conn, event_open_ms)
                training_row_count = len(training_rows)
                if training_event_count < self.config.min_train_events:
                    return 0
                model = _fit_ridge(training_rows, self.config.ridge_alpha)
            else:
                training_event_count = ridge_state.event_count
                training_row_count = ridge_state.row_count
                trained_through = ridge_state.through_event_ms
                if training_event_count < self.config.min_train_events:
                    return 0
                if trained_through is None or trained_through >= event_open_ms:
                    raise EntrySelectionError("NBOT_V381R_RIDGE_STATE_LEAKAGE")
                model = ridge_state.fit(self.config.ridge_alpha)
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
            raise ValueError("NBOT_V345_MAX_EVENTS_INVALID")
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

            if rebuild:
                if self._compacted_history_exists(conn):
                    raise EntrySelectionError(
                        "NBOT_V382_SELECTION_REBUILD_BLOCKED_BY_COMPACTED_HISTORY"
                    )
                conn.execute(
                    "DELETE FROM entry_selection_prediction_builds WHERE lab_version=?",
                    (self.config.lab_version,),
                )
                conn.execute(
                    "DELETE FROM entry_selection_predictions WHERE lab_version=?",
                    (self.config.lab_version,),
                )
                conn.execute(
                    "DELETE FROM entry_selection_ridge_state WHERE lab_version=?",
                    (self.config.lab_version,),
                )
                conn.commit()

            all_events = [int(row[0]) for row in conn.execute(
                "SELECT event_open_ms FROM entry_selection_builds WHERE lab_version=? ORDER BY event_open_ms",
                (self.config.lab_version,),
            ).fetchall()]
            baseline_rows = 0
            learned_rows = 0
            learned_ready_events = 0
            ridge_state = self._load_ridge_state(conn)
            for event_open_ms in all_events:
                for spec in BASELINE_SELECTORS:
                    baseline_rows += self._score_event(conn, event_open_ms, spec, rebuild)

                if (
                    ridge_state.through_event_ms is None
                    or event_open_ms > ridge_state.through_event_ms
                ):
                    if ridge_state.event_count >= self.config.min_train_events:
                        learned_ready_events += 1
                        learned_rows += self._score_event(
                            conn, event_open_ms,
                            SELECTOR_BY_VERSION[self.config.learned_selector_version],
                            rebuild, ridge_state=ridge_state,
                        )
                    event_examples = self._examples_for_event(conn, event_open_ms)
                    ridge_state.add_event(event_open_ms, event_examples)
                    self._save_ridge_state(conn, ridge_state)
                elif ridge_state.event_count >= self.config.min_train_events:
                    learned_ready_events += 1
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

    def audit(self, *, event_open_ms: Iterable[int] | None = None) -> dict[str, Any]:
        """Read-only deterministic lineage/chronology audit for V3.4.5.

        When ``event_open_ms`` is supplied, the same deep checks are restricted
        to that immutable evaluation window.  Champion evaluation uses this
        scoped mode so routine promotion cannot accidentally rescan hundreds of
        unrelated historical events.  The standalone selection audit remains
        full-history by default.
        """
        audit_events = None if event_open_ms is None else tuple(sorted({int(v) for v in event_open_ms}))

        required_tables = set(RESEARCH_SELECTION_TABLES)
        expected_lab_hash = self.definition_hash
        expected_selector_hashes = self.selector_definition_hashes
        counter_keys = (
            "lab_definition_mismatch",
            "selector_definition_mismatches",
            "target_policy_mismatches",
            "examples_without_policy_result",
            "policy_result_integrity_mismatches",
            "policy_result_digest_mismatches",
            "feature_build_integrity_mismatches",
            "signal_build_integrity_mismatches",
            "feature_source_digest_mismatches",
            "signal_source_digest_mismatches",
            "future_feature_source_rows",
            "signal_annotation_set_mismatches",
            "feature_vector_mismatches",
            "example_digest_mismatches",
            "example_build_row_mismatches",
            "example_build_digest_mismatches",
            "example_build_source_digest_mismatches",
            "predictions_without_example",
            "prediction_source_digest_mismatches",
            "prediction_digest_mismatches",
            "prediction_value_mismatches",
            "prediction_rank_mismatches",
            "baseline_prediction_count_mismatches",
            "learned_prediction_count_mismatches",
            "learned_training_leakage",
            "learned_before_min_train_events",
            "learned_model_digest_mismatches",
            "prediction_build_metadata_mismatches",
            "prediction_build_row_mismatches",
            "prediction_build_digest_mismatches",
            "prediction_build_source_digest_mismatches",
            "ridge_state_mismatches",
        )
        report: dict[str, Any] = {
            "lab_version": self.config.lab_version,
            "definition_hash": expected_lab_hash,
            "target_policy_version": self.config.target_policy_version,
            "selector_count": len(SELECTORS),
            "source_events": 0,
            "source_rows": 0,
            "example_events": 0,
            "example_rows": 0,
            "pending_example_events": 0,
            "prediction_rows": 0,
            "learned_scored_events": 0,
            "audit_scope": "FULL_HISTORY" if audit_events is None else "SCOPED_EVENTS",
            "audit_event_count": 0 if audit_events is None else len(audit_events),
            "missing_tables": (),
            **{key: 0 for key in counter_keys},
        }

        with self.db.connection() as conn:
            present = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing_tables = tuple(sorted(required_tables - present))
            report["missing_tables"] = missing_tables
            if missing_tables:
                report["healthy"] = False
                return report

            stored_lab = conn.execute(
                "SELECT feature_version, policy_lab_version, target_policy_version, "
                "definition_hash, definition_json FROM entry_selection_labs WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            expected_lab = (
                self.config.feature_version,
                self.config.policy_lab_version,
                self.config.target_policy_version,
                expected_lab_hash,
                _canonical_json(self.definition()),
            )
            if stored_lab != expected_lab:
                report["lab_definition_mismatch"] += 1

            for version, expected_hash in expected_selector_hashes.items():
                spec = SELECTOR_BY_VERSION[version]
                definition = spec.definition()
                if version == self.config.learned_selector_version:
                    definition = dict(definition)
                    definition["parameters"] = dict(definition["parameters"])
                    definition["parameters"].update({
                        "min_train_events": self.config.min_train_events,
                        "ridge_alpha": self.config.ridge_alpha,
                        "feature_names": list(FEATURE_VECTOR_NAMES),
                    })
                row = conn.execute(
                    "SELECT lab_version, family, is_learned, definition_hash, definition_json "
                    "FROM entry_selector_sets WHERE selector_version=?",
                    (version,),
                ).fetchone()
                expected = (
                    self.config.lab_version,
                    spec.family,
                    int(spec.is_learned),
                    expected_hash,
                    _canonical_json(definition),
                )
                if row != expected:
                    report["selector_definition_mismatches"] += 1

            source_events, source_rows = self._source_counts(conn)
            report["source_events"] = source_events
            report["source_rows"] = source_rows
            example_events, example_rows = conn.execute(
                "SELECT COUNT(DISTINCT event_open_ms), COUNT(*) "
                "FROM entry_selection_examples WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()
            report["example_events"] = int(example_events)
            report["example_rows"] = int(example_rows)
            report["pending_example_events"] = max(0, source_events - int(example_events))
            report["prediction_rows"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=?",
                (self.config.lab_version,),
            ).fetchone()[0])
            report["learned_scored_events"] = int(conn.execute(
                "SELECT COUNT(DISTINCT event_open_ms) FROM entry_selection_predictions "
                "WHERE lab_version=? AND selector_version=?",
                (self.config.lab_version, self.config.learned_selector_version),
            ).fetchone()[0])

            report["target_policy_mismatches"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=? "
                "AND (policy_lab_version<>? OR target_policy_version<>? OR feature_version<>?)",
                (
                    self.config.lab_version,
                    self.config.policy_lab_version,
                    self.config.target_policy_version,
                    self.config.feature_version,
                ),
            ).fetchone()[0])
            report["examples_without_policy_result"] = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM entry_selection_examples e
                LEFT JOIN exit_policy_results r
                  ON r.event_open_ms=e.event_open_ms
                 AND r.symbol=e.symbol
                 AND r.side=e.side
                 AND r.policy_version=e.target_policy_version
                 AND r.lab_version=e.policy_lab_version
                WHERE e.lab_version=? AND r.event_open_ms IS NULL
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["predictions_without_example"] = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM entry_selection_predictions p
                LEFT JOIN entry_selection_examples e
                  ON e.event_open_ms=p.event_open_ms
                 AND e.symbol=p.symbol
                 AND e.side=p.side
                 AND e.lab_version=p.lab_version
                WHERE p.lab_version=? AND e.event_open_ms IS NULL
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["prediction_source_digest_mismatches"] = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM entry_selection_predictions p
                JOIN entry_selection_examples e
                  ON e.event_open_ms=p.event_open_ms
                 AND e.symbol=p.symbol
                 AND e.side=p.side
                 AND e.lab_version=p.lab_version
                WHERE p.lab_version=? AND p.source_example_digest<>e.example_digest
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["future_feature_source_rows"] = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM entry_selection_examples e
                JOIN canonical_features f
                  ON f.event_open_ms=e.event_open_ms
                 AND f.symbol=e.symbol
                 AND f.feature_version=e.feature_version
                WHERE e.lab_version=? AND f.source_max_event_open_ms>e.event_open_ms
                """,
                (self.config.lab_version,),
            ).fetchone()[0])
            report["learned_training_leakage"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? "
                "AND selector_version=? AND (trained_through_event_ms IS NULL "
                "OR trained_through_event_ms>=event_open_ms)",
                (self.config.lab_version, self.config.learned_selector_version),
            ).fetchone()[0])
            report["learned_before_min_train_events"] = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_predictions WHERE lab_version=? "
                "AND selector_version=? AND training_event_count<?",
                (
                    self.config.lab_version,
                    self.config.learned_selector_version,
                    self.config.min_train_events,
                ),
            ).fetchone()[0])

            if audit_events is None:
                event_ids = [
                    int(row[0])
                    for row in conn.execute(
                        "SELECT event_open_ms FROM entry_selection_builds "
                        "WHERE lab_version=? ORDER BY event_open_ms",
                        (self.config.lab_version,),
                    ).fetchall()
                ]
            else:
                event_ids = list(audit_events)

            for event_open_ms in event_ids:
                stored_examples = self._stored_example_rows(conn, event_open_ms)
                current_policy_rows = self._source_rows(conn, event_open_ms)
                current_policy = {
                    (str(row["symbol"]), str(row["side"])): row
                    for row in current_policy_rows
                }
                features = self._feature_rows(conn, event_open_ms)
                signals = self._signal_rows(conn, event_open_ms)

                feature_build = conn.execute(
                    "SELECT feature_digest FROM feature_builds "
                    "WHERE event_open_ms=? AND feature_version=?",
                    (event_open_ms, self.config.feature_version),
                ).fetchone()
                signal_build = conn.execute(
                    "SELECT signal_digest FROM signal_builds "
                    "WHERE event_open_ms=? AND feature_version=?",
                    (event_open_ms, self.config.feature_version),
                ).fetchone()
                current_feature_digest = (
                    self._feature_event_digest(conn, event_open_ms)
                    if feature_build is not None else None
                )
                current_signal_digest = (
                    self._signal_event_digest(conn, event_open_ms)
                    if signal_build is not None else None
                )
                if feature_build is None or current_feature_digest != str(feature_build[0]):
                    report["feature_build_integrity_mismatches"] += 1
                if signal_build is None or current_signal_digest != str(signal_build[0]):
                    report["signal_build_integrity_mismatches"] += 1

                feature_digest = str(feature_build[0]) if feature_build is not None else ""
                signal_digest = str(signal_build[0]) if signal_build is not None else ""
                current_source_rows: list[list[Any]] = []

                if len(stored_examples) != len(current_policy_rows):
                    report["example_build_row_mismatches"] += 1

                for row in stored_examples:
                    key = (str(row["symbol"]), str(row["side"]))
                    policy = current_policy.get(key)
                    if policy is None:
                        continue
                    actual_policy_digest = _policy_result_digest(policy)
                    if actual_policy_digest != str(policy["result_digest"]):
                        report["policy_result_integrity_mismatches"] += 1
                    if str(row["source_policy_result_digest"]) != str(policy["result_digest"]):
                        report["policy_result_digest_mismatches"] += 1
                    if str(row["source_feature_digest"]) != feature_digest:
                        report["feature_source_digest_mismatches"] += 1
                    if str(row["source_signal_digest"]) != signal_digest:
                        report["signal_source_digest_mismatches"] += 1

                    symbol = str(row["symbol"])
                    feature = features.get(symbol)
                    symbol_signals = signals.get(symbol, {})
                    if feature is None:
                        report["feature_vector_mismatches"] += 1
                    else:
                        if set(symbol_signals) != set(SIGNAL_VERSIONS):
                            report["signal_annotation_set_mismatches"] += 1
                        vector = _feature_vector(feature, symbol_signals, str(row["side"]))
                        if _canonical_json(vector) != str(row["feature_vector_json"]):
                            report["feature_vector_mismatches"] += 1
                    if _row_digest(row, EXAMPLE_DIGEST_FIELDS) != str(row["example_digest"]):
                        report["example_digest_mismatches"] += 1
                    current_source_rows.append([
                        row["symbol"],
                        row["side"],
                        policy["result_digest"],
                        feature_digest,
                        signal_digest,
                    ])

                build_row = conn.execute(
                    "SELECT example_row_count, source_digest, example_digest "
                    "FROM entry_selection_builds WHERE event_open_ms=? AND lab_version=?",
                    (event_open_ms, self.config.lab_version),
                ).fetchone()
                if build_row is None:
                    report["example_build_row_mismatches"] += 1
                else:
                    if int(build_row[0]) != len(stored_examples):
                        report["example_build_row_mismatches"] += 1
                    current_example_digest = _rows_digest(
                        stored_examples,
                        EXAMPLE_DIGEST_FIELDS,
                        key_fields=("event_open_ms", "symbol", "side"),
                    )
                    if str(build_row[2]) != current_example_digest:
                        report["example_build_digest_mismatches"] += 1
                    if str(build_row[1]) != _digest(current_source_rows):
                        report["example_build_source_digest_mismatches"] += 1

            # The persisted cumulative Ridge state is the normal-operation
            # chronology proof.  Full-history audits validate its durable
            # metadata/digest without replaying every model.  Scoped Champion
            # audits replay only the small frozen evaluation prefix.
            try:
                persisted_ridge_state = self._load_ridge_state(conn)
                (
                    expected_state_events,
                    expected_state_rows,
                    expected_state_through,
                ) = self._selection_history_meta(conn)
                if (
                    persisted_ridge_state.event_count != expected_state_events
                    or persisted_ridge_state.row_count != expected_state_rows
                    or persisted_ridge_state.through_event_ms != expected_state_through
                ):
                    report["ridge_state_mismatches"] += 1
            except (EntrySelectionError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                report["ridge_state_mismatches"] += 1

            scoped_ridge_models: dict[int, tuple[dict[str, Any], int, int, int | None, str]] = {}
            if audit_events is not None and audit_events:
                target_set = set(audit_events)
                max_target = max(audit_events)
                replay_state = RidgeSufficientStatistics.empty()
                replay_events = [
                    int(row[0])
                    for row in conn.execute(
                        "SELECT event_open_ms FROM entry_selection_builds "
                        "WHERE lab_version=? AND event_open_ms<=? ORDER BY event_open_ms",
                        (self.config.lab_version, max_target),
                    )
                ]
                for replay_event in replay_events:
                    if (
                        replay_event in target_set
                        and replay_state.event_count >= self.config.min_train_events
                    ):
                        replay_model = replay_state.fit(self.config.ridge_alpha)
                        replay_model.update({
                            "trained_through_event_ms": replay_state.through_event_ms,
                            "training_event_count": replay_state.event_count,
                            "training_row_count": replay_state.row_count,
                        })
                        replay_digest = _digest({
                            key: value
                            for key, value in replay_model.items()
                            if key != "model_digest"
                        })
                        scoped_ridge_models[replay_event] = (
                            replay_model,
                            replay_state.event_count,
                            replay_state.row_count,
                            replay_state.through_event_ms,
                            replay_digest,
                        )
                    replay_state.add_event(
                        replay_event, self._examples_for_event(conn, replay_event)
                    )

            prediction_sql = (
                "SELECT event_open_ms, selector_version, prediction_row_count, "
                "training_event_count, training_row_count, trained_through_event_ms, "
                "model_digest, source_digest, prediction_digest "
                "FROM entry_selection_prediction_builds WHERE lab_version=?"
            )
            prediction_params: list[Any] = [self.config.lab_version]
            if audit_events is not None:
                if audit_events:
                    prediction_sql += " AND event_open_ms IN (" + ",".join("?" for _ in audit_events) + ")"
                    prediction_params.extend(audit_events)
                else:
                    prediction_sql += " AND 1=0"
            prediction_sql += " ORDER BY event_open_ms, selector_version"
            prediction_builds = conn.execute(
                prediction_sql, tuple(prediction_params)
            ).fetchall()

            for build_row in prediction_builds:
                event_open_ms = int(build_row[0])
                selector_version = str(build_row[1])
                spec = SELECTOR_BY_VERSION.get(selector_version)
                if spec is None:
                    report["prediction_build_metadata_mismatches"] += 1
                    continue
                predictions = self._stored_prediction_rows(
                    conn, event_open_ms, selector_version
                )
                examples = self._examples_for_event(conn, event_open_ms)
                if int(build_row[2]) != len(predictions):
                    report["prediction_build_row_mismatches"] += 1

                ranks = [int(row["rank_in_event"]) for row in predictions]
                if ranks != list(range(1, len(predictions) + 1)):
                    report["prediction_rank_mismatches"] += 1
                for row in predictions:
                    if _row_digest(row, PREDICTION_DIGEST_FIELDS) != str(row["prediction_digest"]):
                        report["prediction_digest_mismatches"] += 1

                expected_training_events = 0
                expected_training_rows = 0
                expected_trained_through: int | None = None
                expected_model: dict[str, Any] | None = None
                expected_model_digest: str | None = None
                if spec.is_learned:
                    (
                        expected_training_events,
                        expected_training_rows,
                        expected_trained_through,
                    ) = self._selection_history_meta(
                        conn, before_event_ms=event_open_ms
                    )
                    if expected_training_events < self.config.min_train_events:
                        report["learned_before_min_train_events"] += 1
                    if audit_events is not None:
                        scoped = scoped_ridge_models.get(event_open_ms)
                        if scoped is None:
                            report["learned_model_digest_mismatches"] += 1
                        else:
                            (
                                expected_model,
                                expected_training_events,
                                expected_training_rows,
                                expected_trained_through,
                                expected_model_digest,
                            ) = scoped
                            if str(build_row[6]) != expected_model_digest:
                                report["learned_model_digest_mismatches"] += 1
                    else:
                        # Normal full-history audit avoids a second complete
                        # training replay.  The model digest is already sealed
                        # into every prediction row and the build source digest.
                        expected_model_digest = None if build_row[6] is None else str(build_row[6])
                else:
                    if build_row[5] is not None or build_row[6] is not None:
                        report["prediction_build_metadata_mismatches"] += 1

                if (
                    int(build_row[3]) != expected_training_events
                    or int(build_row[4]) != expected_training_rows
                    or build_row[5] != expected_trained_through
                ):
                    report["prediction_build_metadata_mismatches"] += 1

                if spec.is_learned and audit_events is None:
                    for stored in predictions:
                        if stored["model_digest"] != expected_model_digest:
                            report["prediction_value_mismatches"] += 1
                else:
                    scored: list[tuple[float, dict[str, Any]]] = []
                    for example in examples:
                        if expected_model is not None:
                            score = _ridge_score(expected_model, str(example["feature_vector_json"]))
                        else:
                            score = self._baseline_score(spec, example)
                        scored.append((score, example))
                    scored.sort(
                        key=lambda item: (
                            -item[0], str(item[1]["symbol"]), str(item[1]["side"])
                        )
                    )
                    if len(scored) != len(predictions):
                        report["prediction_value_mismatches"] += 1
                    else:
                        for rank, ((expected_score, expected_example), stored) in enumerate(
                            zip(scored, predictions), 1
                        ):
                            if (
                                int(stored["rank_in_event"]) != rank
                                or str(stored["symbol"]) != str(expected_example["symbol"])
                                or str(stored["side"]) != str(expected_example["side"])
                                or not math.isclose(
                                    float(stored["score"]),
                                    float(expected_score),
                                    rel_tol=1e-10,
                                    abs_tol=1e-10,
                                )
                                or stored["model_digest"] != expected_model_digest
                            ):
                                report["prediction_value_mismatches"] += 1

                current_prediction_digest = _rows_digest(
                    predictions,
                    PREDICTION_DIGEST_FIELDS,
                    key_fields=(
                        "event_open_ms", "selector_version", "rank_in_event", "symbol", "side"
                    ),
                )
                if str(build_row[8]) != current_prediction_digest:
                    report["prediction_build_digest_mismatches"] += 1
                expected_source = _digest({
                    "event_examples": [
                        [row["symbol"], row["side"], row["example_digest"]]
                        for row in examples
                    ],
                    "model_digest": expected_model_digest,
                })
                if str(build_row[7]) != expected_source:
                    report["prediction_build_source_digest_mismatches"] += 1

            for event_open_ms in event_ids:
                example_count = int(conn.execute(
                    "SELECT COUNT(*) FROM entry_selection_examples "
                    "WHERE event_open_ms=? AND lab_version=?",
                    (event_open_ms, self.config.lab_version),
                ).fetchone()[0])
                for spec in BASELINE_SELECTORS:
                    count = int(conn.execute(
                        "SELECT COUNT(*) FROM entry_selection_predictions "
                        "WHERE event_open_ms=? AND lab_version=? AND selector_version=?",
                        (event_open_ms, self.config.lab_version, spec.selector_version),
                    ).fetchone()[0])
                    if count != example_count:
                        report["baseline_prediction_count_mismatches"] += 1

                prior_events = self._selection_history_meta(
                    conn, before_event_ms=event_open_ms
                )[0]
                learned_count = int(conn.execute(
                    "SELECT COUNT(*) FROM entry_selection_predictions "
                    "WHERE event_open_ms=? AND lab_version=? AND selector_version=?",
                    (
                        event_open_ms,
                        self.config.lab_version,
                        self.config.learned_selector_version,
                    ),
                ).fetchone()[0])
                expected_learned = example_count if prior_events >= self.config.min_train_events else 0
                if learned_count != expected_learned:
                    report["learned_prediction_count_mismatches"] += 1

        report["healthy"] = (
            not report["missing_tables"]
            and all(int(report[key]) == 0 for key in counter_keys)
        )
        return report
