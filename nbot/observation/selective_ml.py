"""Compact nonlinear selective-learning layer for LIVE paper recommendations.

This module has no order authority.  It trains immutable LightGBM artifacts from
causal compact research memory, keeps Ridge as a benchmark, and exposes only
bounded scoring helpers to the recommendation layer.

The primary target remains the existing research control-policy net R.  That
control policy mirrors Execution's integer-R stop progression, but it is still a
bar-based research simulation rather than actual execution PnL.  Actual paper
outcomes remain a separate calibration source.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
import time
from typing import Any

from .candidate_setups import BY_ID
from .context_learning import SETUPS, describe
from .research_memory import ResearchMemoryStore
from .selection import FEATURE_VECTOR_NAMES

VERSION = "SELECTIVE_ML_V1"
FEATURE_SCHEMA = "SELECTIVE_ML_FEATURES_V1"
ARTIFACT_PREFIX = "selective-ml:v1:model:"
TARGET = "CONTROL_POLICY_AFTER_COST_NET_R_NOT_EXECUTION_PNL"
LOWER_QUANTILE = 0.25
MEAN_SCORE_WEIGHT = 0.70
LOWER_SCORE_WEIGHT = 0.30
CONTEXTS = tuple(
    f"{alignment}:{volatility}"
    for alignment in ("ALIGNED", "MIXED", "OPPOSED")
    for volatility in ("LOW", "NORMAL", "HIGH")
)
ENGINEERED_FEATURE_NAMES = (
    "ret_5m_atr", "ret_15m_atr", "ret_30m_atr", "ret_1h_atr", "ret_2h_atr", "ret_4h_atr",
    "range_atr", "spread_atr", "btc_relative_5m", "btc_relative_1h", "btc_relative_4h",
    "momentum_curve_5m_1h", "momentum_curve_15m_4h", "pullback_15m_vs_4h",
    "vol_ratio_1h_4h", "breadth_gap", "relative_strength_centered",
    "trend_vol_interaction", "liquidity_vol_interaction", "signal_alignment_sum",
)
STRUCTURE_FEATURE_NAMES = (
    *tuple(f"setup::{name}" for name in SETUPS),
    *tuple(f"context::{name}" for name in CONTEXTS),
)
ML_FEATURE_NAMES = tuple(FEATURE_VECTOR_NAMES) + ENGINEERED_FEATURE_NAMES + STRUCTURE_FEATURE_NAMES
ENTRY_FEATURE_NAMES = (
    "score", "spread_pct", "side_sign", "seconds_to_next_bar",
    *tuple(f"context::{name}" for name in CONTEXTS),
    *tuple(f"candidate::{name}" for name in BY_ID),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def augment_vector(vector: dict[str, Any]) -> dict[str, float]:
    """Derive nonlinear-friendly, decision-time features from the causal vector."""
    base = {name: _finite(vector.get(name)) for name in FEATURE_VECTOR_NAMES}
    atr = max(abs(base.get("atr14_frac", 0.0)), 1e-8)
    vol4 = max(abs(base.get("realized_vol_4h", 0.0)), 1e-8)
    engineered = {
        "ret_5m_atr": base["ret_5m_side"] / atr,
        "ret_15m_atr": base["ret_15m_side"] / atr,
        "ret_30m_atr": base["ret_30m_side"] / atr,
        "ret_1h_atr": base["ret_1h_side"] / atr,
        "ret_2h_atr": base["ret_2h_side"] / atr,
        "ret_4h_atr": base["ret_4h_side"] / atr,
        "range_atr": base["range_frac"] / atr,
        "spread_atr": base["spread_pct"] / max(atr * 100.0, 1e-8),
        "btc_relative_5m": base["ret_5m_side"] - base["btc_ret_5m_side"],
        "btc_relative_1h": base["ret_1h_side"] - base["btc_ret_1h_side"],
        "btc_relative_4h": base["ret_4h_side"] - base["btc_ret_4h_side"],
        "momentum_curve_5m_1h": base["ret_5m_side"] - base["ret_1h_side"] / 12.0,
        "momentum_curve_15m_4h": base["ret_15m_side"] - base["ret_4h_side"] / 16.0,
        "pullback_15m_vs_4h": base["ret_4h_side"] - base["ret_15m_side"],
        "vol_ratio_1h_4h": base["realized_vol_1h"] / vol4,
        "breadth_gap": base["breadth_5m_side"] - base["breadth_1h_side"],
        "relative_strength_centered": base["ret_1h_percentile_side"] - 0.5,
        "trend_vol_interaction": (base["ret_4h_side"] / atr) * (base["volatility_percentile"] - 0.5),
        "liquidity_vol_interaction": base["liquidity_percentile"] * base["volatility_percentile"],
        "signal_alignment_sum": base["csm_alignment"] + base["tsmom_alignment"] + base["intraday_alignment"],
    }
    info = describe(base)
    structure = {
        **{f"setup::{name}": 1.0 if info["setup"] == name else 0.0 for name in SETUPS},
        **{f"context::{name}": 1.0 if info["context"] == name else 0.0 for name in CONTEXTS},
    }
    result = {**base, **engineered, **structure}
    if tuple(result) != ML_FEATURE_NAMES:
        raise ValueError("SELECTIVE_ML_FEATURE_SCHEMA_MISMATCH")
    if not all(math.isfinite(v) for v in result.values()):
        raise ValueError("SELECTIVE_ML_NONFINITE_FEATURE")
    return result


def entry_vector(*, score: float, bid: float, ask: float, side: str,
                 candidate_id: str | None, context: str | None, decision_ms: int) -> dict[str, float]:
    if side not in {"LONG", "SHORT"} or not 0 < bid <= ask:
        raise ValueError("SELECTIVE_ML_ENTRY_INPUT_INVALID")
    mid = (bid + ask) / 2.0
    spread_pct = (ask - bid) / mid * 100.0
    seconds_to_next = (((decision_ms // 300_000) + 1) * 300_000 - decision_ms) / 1000.0
    result = {
        "score": _finite(score),
        "spread_pct": spread_pct,
        "side_sign": 1.0 if side == "LONG" else -1.0,
        "seconds_to_next_bar": max(0.0, min(300.0, seconds_to_next)),
    }
    for name in CONTEXTS:
        result[f"context::{name}"] = 1.0 if context == name else 0.0
    for name in BY_ID:
        result[f"candidate::{name}"] = 1.0 if candidate_id == name else 0.0
    if tuple(result) != ENTRY_FEATURE_NAMES:
        raise ValueError("SELECTIVE_ML_ENTRY_SCHEMA_MISMATCH")
    return result


@dataclass(frozen=True)
class SelectiveMLConfig:
    max_events: int = 600
    max_rows: int = 60_000
    min_train_events: int = 40
    min_validation_events: int = 10
    train_fraction: float = 0.80
    num_boost_round: int = 160
    early_stopping_rounds: int = 20
    learning_rate: float = 0.04
    num_leaves: int = 15
    max_depth: int = 4
    min_data_in_leaf: int = 80
    threads: int = 1
    min_lower_r: float = 0.08
    min_edge_gap_r: float = 0.05
    min_fill_probability: float = 0.60
    entry_min_samples: int = 100
    entry_min_each_class: int = 20

    @classmethod
    def from_environment(cls) -> "SelectiveMLConfig":
        values: dict[str, Any] = {}
        integer = {
            "max_events": "NBOT_ML_MAX_EVENTS", "max_rows": "NBOT_ML_MAX_ROWS",
            "num_boost_round": "NBOT_ML_TREES", "min_data_in_leaf": "NBOT_ML_MIN_LEAF",
            "threads": "NBOT_ML_THREADS",
        }
        floating = {
            "min_lower_r": "NBOT_ML_MIN_LOWER_R", "min_edge_gap_r": "NBOT_ML_MIN_EDGE_GAP_R",
            "min_fill_probability": "NBOT_ML_MIN_FILL_PROB",
        }
        for field, env in integer.items():
            if env in os.environ:
                values[field] = int(os.environ[env])
        for field, env in floating.items():
            if env in os.environ:
                values[field] = float(os.environ[env])
        cfg = cls(**values)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not (50 <= self.max_events <= 5000 and 1000 <= self.max_rows <= 1_000_000):
            raise ValueError("SELECTIVE_ML_HISTORY_LIMIT_INVALID")
        if not (20 <= self.min_train_events < self.max_events and 5 <= self.min_validation_events < self.max_events):
            raise ValueError("SELECTIVE_ML_EVENT_MINIMUM_INVALID")
        if not 0.5 <= self.train_fraction <= 0.9:
            raise ValueError("SELECTIVE_ML_SPLIT_INVALID")
        if not (20 <= self.num_boost_round <= 1000 and 2 <= self.num_leaves <= 63 and 2 <= self.max_depth <= 8):
            raise ValueError("SELECTIVE_ML_COMPLEXITY_INVALID")
        if not (10 <= self.min_data_in_leaf <= 5000 and 1 <= self.threads <= 4):
            raise ValueError("SELECTIVE_ML_RESOURCE_LIMIT_INVALID")
        if not (0 <= self.min_lower_r <= 1 and 0 <= self.min_edge_gap_r <= 1 and 0.5 <= self.min_fill_probability <= 0.99):
            raise ValueError("SELECTIVE_ML_GATE_INVALID")


def _ml_imports():
    try:
        import lightgbm as lgb  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("SELECTIVE_ML_DEPENDENCY_MISSING:install requirements-ml.txt") from exc
    return lgb, np


def _recent_event_groups(memory: ResearchMemoryStore, cfg: SelectiveMLConfig) -> list[tuple[int, list[dict[str, Any]]]]:
    groups: deque[tuple[int, list[dict[str, Any]]]] = deque()
    current_event: int | None = None
    current_rows: list[dict[str, Any]] = []
    total_rows = 0
    for event_ms, row in memory.iter_training_rows():
        event_ms = int(event_ms)
        if current_event is None:
            current_event = event_ms
        if event_ms != current_event:
            groups.append((current_event, current_rows))
            total_rows += len(current_rows)
            current_event, current_rows = event_ms, []
            while len(groups) > cfg.max_events or total_rows > cfg.max_rows:
                _, removed = groups.popleft()
                total_rows -= len(removed)
        current_rows.append(row)
    if current_event is not None:
        groups.append((current_event, current_rows))
        total_rows += len(current_rows)
    while len(groups) > cfg.max_events or total_rows > cfg.max_rows:
        _, removed = groups.popleft()
        total_rows -= len(removed)
    return list(groups)


def _matrix(groups: list[tuple[int, list[dict[str, Any]]]], np):
    x: list[list[float]] = []
    y: list[float] = []
    w: list[float] = []
    events: list[int] = []
    for event_ms, rows in groups:
        usable = []
        for row in rows:
            try:
                vector = augment_vector(json.loads(str(row["feature_vector_json"])))
                target = max(-3.0, min(3.0, float(row["target_net_r"])))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if not math.isfinite(target):
                continue
            usable.append((vector, target))
        if not usable:
            continue
        weight = 1.0 / len(usable)
        for vector, target in usable:
            x.append([vector[name] for name in ML_FEATURE_NAMES])
            y.append(target)
            w.append(weight)
            events.append(event_ms)
    return np.asarray(x, dtype="float32"), np.asarray(y, dtype="float32"), np.asarray(w, dtype="float32"), events


def _train_booster(lgb, train_x, train_y, train_w, valid_x, valid_y, valid_w,
                   *, cfg: SelectiveMLConfig, objective: str, alpha: float | None = None):
    params: dict[str, Any] = {
        "objective": objective,
        "metric": ("quantile" if objective == "quantile" else
                   "binary_logloss" if objective == "binary" else "l1"),
        "learning_rate": cfg.learning_rate,
        "num_leaves": cfg.num_leaves,
        "max_depth": cfg.max_depth,
        "min_data_in_leaf": cfg.min_data_in_leaf,
        "feature_fraction": 0.85,
        "bagging_fraction": 0.80,
        "bagging_freq": 1,
        "lambda_l1": 0.1,
        "lambda_l2": 1.0,
        "verbosity": -1,
        "num_threads": cfg.threads,
        "seed": 391,
        "feature_fraction_seed": 391,
        "bagging_seed": 391,
        "deterministic": True,
        "force_col_wise": True,
    }
    if alpha is not None:
        params["alpha"] = alpha
    train = lgb.Dataset(train_x, label=train_y, weight=train_w, feature_name=list(ML_FEATURE_NAMES), free_raw_data=False)
    valid = lgb.Dataset(valid_x, label=valid_y, weight=valid_w, reference=train, feature_name=list(ML_FEATURE_NAMES), free_raw_data=False)
    return lgb.train(
        params, train, num_boost_round=cfg.num_boost_round, valid_sets=[valid], valid_names=["validation"],
        callbacks=[lgb.early_stopping(cfg.early_stopping_rounds, verbose=False)],
    )


def _entry_training_rows(database, cfg: SelectiveMLConfig):
    if database is None or not database.path.is_file():
        return []
    from .shadow import verified
    with database.connection() as conn:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_results'").fetchone() is None:
            return []
        rows = conn.execute(
            "SELECT result_json,digest FROM shadow_results WHERE profile='live-paper' "
            "ORDER BY closed_ms DESC LIMIT 5000"
        ).fetchall()
    result = []
    for raw, check in rows:
        try:
            value = verified(raw, check)
            reason = value.get("reason")
            if bool(value.get("eligible")):
                label = 1.0
            elif reason == "ENTRY_DRIFT_REJECTED":
                label = 0.0
            else:
                continue
            vec = entry_vector(
                score=float(value.get("score", 0.0)), bid=float(value["bid"]), ask=float(value["ask"]),
                side=value["side"], candidate_id=value.get("candidate_id"), context=value.get("decision_context"),
                decision_ms=int(value.get("decision_ms", value.get("event_ms", 0))),
            )
            result.append((vec, label))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return list(reversed(result))


class SelectiveMLRuntime:
    def __init__(self, payload: dict[str, Any]):
        lgb, np = _ml_imports()
        if payload.get("version") != VERSION or tuple(payload.get("feature_names", ())) != ML_FEATURE_NAMES:
            raise ValueError("SELECTIVE_ML_ARTIFACT_CONTRACT_INVALID")
        self.payload = payload
        self._np = np
        self.mean = lgb.Booster(model_str=str(payload["mean_model"]))
        self.lower = lgb.Booster(model_str=str(payload["lower_model"]))
        self.entry = lgb.Booster(model_str=str(payload["entry_model"])) if payload.get("entry_model") else None

    def score(self, vector: dict[str, Any]) -> tuple[float, float]:
        values = augment_vector(vector)
        row = self._np.asarray([[values[name] for name in ML_FEATURE_NAMES]], dtype="float32")
        mean = float(self.mean.predict(row)[0])
        lower = float(self.lower.predict(row)[0])
        if not all(math.isfinite(v) for v in (mean, lower)):
            raise ValueError("SELECTIVE_ML_PREDICTION_NONFINITE")
        return mean, lower

    def fill_probability(self, *, score: float, bid: float, ask: float, side: str,
                         candidate_id: str | None, context: str | None, decision_ms: int) -> float:
        if self.entry is None:
            return 1.0
        vector = entry_vector(
            score=score, bid=bid, ask=ask, side=side, candidate_id=candidate_id,
            context=context, decision_ms=decision_ms,
        )
        row = self._np.asarray([[vector[name] for name in ENTRY_FEATURE_NAMES]], dtype="float32")
        value = float(self.entry.predict(row)[0])
        if not math.isfinite(value):
            raise ValueError("SELECTIVE_ML_FILL_NONFINITE")
        return max(0.0, min(1.0, value))


class SelectiveMLManager:
    def __init__(self, memory: ResearchMemoryStore, database=None, *, release_sha: str,
                 config: SelectiveMLConfig | None = None):
        self.memory = memory
        self.database = database
        self.release_sha = str(release_sha).strip()
        self.config = config or SelectiveMLConfig.from_environment()
        self.config.validate()
        if len(self.release_sha) != 40 or any(c not in "0123456789abcdef" for c in self.release_sha.lower()):
            raise ValueError("SELECTIVE_ML_RELEASE_SHA_INVALID")

    def _latest_record(self) -> dict[str, Any] | None:
        records = self.memory.list_artifacts(prefix=ARTIFACT_PREFIX)
        matches = [r for r in records if r["payload"].get("release_sha") == self.release_sha]
        return matches[-1] if matches else None

    def latest_for_event(self, event_ms: int) -> dict[str, Any] | None:
        records = self.memory.list_artifacts(prefix=ARTIFACT_PREFIX)
        for record in reversed(records):
            payload = record["payload"]
            if payload.get("release_sha") != self.release_sha:
                continue
            if int(payload.get("trained_at_ms", 2**63-1)) >= int(event_ms):
                continue
            if int(payload.get("training_cutoff_event_ms", 2**63-1)) >= int(event_ms):
                continue
            if not bool(payload.get("eligible")):
                continue
            return record
        return None

    def status(self) -> dict[str, Any]:
        latest = self._latest_record()
        dependency = True
        dependency_error = None
        try:
            _ml_imports()
        except RuntimeError as exc:
            dependency = False
            dependency_error = str(exc)
        return {
            "version": VERSION,
            "authority": "RESEARCH_ONLY_MODEL_LIVE_PAPER_SELECTION_ONLY",
            "release_sha": self.release_sha,
            "dependency_ready": dependency,
            "dependency_error": dependency_error,
            "latest": None if latest is None else {
                "artifact_key": latest["artifact_key"],
                "artifact_digest": latest["artifact_digest"],
                **{k: latest["payload"].get(k) for k in (
                    "training_cutoff_event_ms", "trained_at_ms", "training_events", "training_rows",
                    "validation_events", "validation_rows", "validation_mae_r", "zero_baseline_mae_r",
                    "lower_quantile_coverage", "eligible", "entry_samples", "entry_positive", "entry_negative",
                )},
            },
            "config": asdict(self.config),
        }

    def train_if_needed(self, *, force: bool = False) -> dict[str, Any]:
        history = self.memory.history_base()
        cutoff = history.get("through_event_ms")
        if cutoff is None:
            return {"status": "WAIT_FOR_RESEARCH_MEMORY", "version": VERSION}
        latest = self._latest_record()
        if not force and latest is not None and int(latest["payload"].get("training_cutoff_event_ms", -1)) == int(cutoff):
            return {"status": "UP_TO_DATE", "version": VERSION, "artifact_key": latest["artifact_key"],
                    "artifact_digest": latest["artifact_digest"]}
        return self.train()

    def train(self) -> dict[str, Any]:
        lgb, np = _ml_imports()
        groups = _recent_event_groups(self.memory, self.config)
        if len(groups) < self.config.min_train_events + self.config.min_validation_events:
            return {"status": "WAIT_FOR_ML_HISTORY", "version": VERSION, "events": len(groups),
                    "required": self.config.min_train_events + self.config.min_validation_events}
        split = max(self.config.min_train_events, int(len(groups) * self.config.train_fraction))
        split = min(split, len(groups) - self.config.min_validation_events)
        train_groups, valid_groups = groups[:split], groups[split:]
        train_x, train_y, train_w, _ = _matrix(train_groups, np)
        valid_x, valid_y, valid_w, _ = _matrix(valid_groups, np)
        if len(train_y) < self.config.min_data_in_leaf * 2 or len(valid_y) < 1:
            return {"status": "WAIT_FOR_ML_ROWS", "version": VERSION,
                    "training_rows": int(len(train_y)), "validation_rows": int(len(valid_y))}
        mean = _train_booster(
            lgb, train_x, train_y, train_w, valid_x, valid_y, valid_w,
            cfg=self.config, objective="regression_l1",
        )
        lower = _train_booster(
            lgb, train_x, train_y, train_w, valid_x, valid_y, valid_w,
            cfg=self.config, objective="quantile", alpha=LOWER_QUANTILE,
        )
        mean_pred = mean.predict(valid_x)
        lower_pred = lower.predict(valid_x)
        validation_mae = float(np.average(np.abs(valid_y - mean_pred), weights=valid_w))
        zero_mae = float(np.average(np.abs(valid_y), weights=valid_w))
        coverage = float(np.average(valid_y >= lower_pred, weights=valid_w))
        eligible = bool(math.isfinite(validation_mae) and validation_mae < zero_mae)

        full_x, full_y, full_w, _ = _matrix(groups, np)
        full_ds = lgb.Dataset(
            full_x, label=full_y, weight=full_w, feature_name=list(ML_FEATURE_NAMES), free_raw_data=False
        )
        common = {
            "learning_rate": self.config.learning_rate, "num_leaves": self.config.num_leaves,
            "max_depth": self.config.max_depth, "min_data_in_leaf": self.config.min_data_in_leaf,
            "feature_fraction": 0.85, "bagging_fraction": 0.80, "bagging_freq": 1,
            "lambda_l1": 0.1, "lambda_l2": 1.0, "verbosity": -1,
            "num_threads": self.config.threads, "seed": 391, "deterministic": True,
            "force_col_wise": True,
        }
        best_round = max(20, int(getattr(mean, "best_iteration", 0) or self.config.num_boost_round))
        lower_round = max(20, int(getattr(lower, "best_iteration", 0) or self.config.num_boost_round))
        mean_final = lgb.train(
            {**common, "objective": "regression_l1", "metric": "l1"}, full_ds, num_boost_round=best_round
        )
        lower_final = lgb.train(
            {**common, "objective": "quantile", "metric": "quantile", "alpha": LOWER_QUANTILE},
            full_ds, num_boost_round=lower_round,
        )

        entry_model = None
        entry_rows = _entry_training_rows(self.database, self.config)
        positives = sum(label > 0.5 for _, label in entry_rows)
        negatives = len(entry_rows) - positives
        if (len(entry_rows) >= self.config.entry_min_samples
                and positives >= self.config.entry_min_each_class
                and negatives >= self.config.entry_min_each_class):
            entry_x = np.asarray(
                [[vec[name] for name in ENTRY_FEATURE_NAMES] for vec, _ in entry_rows], dtype="float32"
            )
            entry_y = np.asarray([label for _, label in entry_rows], dtype="float32")
            split_entry = max(1, int(len(entry_y) * 0.8))
            split_entry = min(split_entry, len(entry_y) - 1)
            train_e = lgb.Dataset(
                entry_x[:split_entry], label=entry_y[:split_entry],
                feature_name=list(ENTRY_FEATURE_NAMES), free_raw_data=False,
            )
            valid_e = lgb.Dataset(
                entry_x[split_entry:], label=entry_y[split_entry:], reference=train_e,
                feature_name=list(ENTRY_FEATURE_NAMES), free_raw_data=False,
            )
            entry_params = {
                **common, "objective": "binary", "metric": "binary_logloss",
                "min_data_in_leaf": max(10, min(self.config.min_data_in_leaf, 40)),
            }
            entry_booster = lgb.train(
                entry_params, train_e, num_boost_round=min(120, self.config.num_boost_round),
                valid_sets=[valid_e], callbacks=[lgb.early_stopping(15, verbose=False)],
            )
            rounds = max(20, int(getattr(entry_booster, "best_iteration", 0) or 80))
            full_entry = lgb.Dataset(
                entry_x, label=entry_y, feature_name=list(ENTRY_FEATURE_NAMES), free_raw_data=False
            )
            entry_final = lgb.train(entry_params, full_entry, num_boost_round=rounds)
            entry_model = entry_final.model_to_string()

        importance = mean_final.feature_importance(importance_type="gain")
        top = sorted(
            zip(ML_FEATURE_NAMES, [float(v) for v in importance]),
            key=lambda item: (-item[1], item[0]),
        )[:20]
        cutoff = int(groups[-1][0])
        trained_at = int(time.time() * 1000)
        payload = {
            "version": VERSION, "feature_schema": FEATURE_SCHEMA, "feature_names": list(ML_FEATURE_NAMES),
            "entry_feature_names": list(ENTRY_FEATURE_NAMES), "release_sha": self.release_sha,
            "authority": "RESEARCH_ONLY_MODEL_LIVE_PAPER_SELECTION_ONLY", "target": TARGET,
            "training_cutoff_event_ms": cutoff, "trained_at_ms": trained_at,
            "training_events": len(train_groups), "training_rows": int(len(train_y)),
            "validation_events": len(valid_groups), "validation_rows": int(len(valid_y)),
            "all_events": len(groups), "all_rows": int(len(full_y)),
            "validation_mae_r": validation_mae, "zero_baseline_mae_r": zero_mae,
            "lower_quantile": LOWER_QUANTILE, "lower_quantile_coverage": coverage,
            "mean_score_weight": MEAN_SCORE_WEIGHT, "lower_score_weight": LOWER_SCORE_WEIGHT,
            "eligible": eligible,
            "eligibility_rule": "CHRONOLOGICAL_VALIDATION_MAE_LT_ALWAYS_ZERO_MAE",
            "selection_gate": {
                "min_lower_r": self.config.min_lower_r,
                "min_edge_gap_r": self.config.min_edge_gap_r,
                "min_fill_probability": self.config.min_fill_probability,
            },
            "mean_model": mean_final.model_to_string(), "lower_model": lower_final.model_to_string(),
            "entry_model": entry_model, "entry_samples": len(entry_rows),
            "entry_positive": positives, "entry_negative": negatives,
            "feature_importance_gain_top20": top,
            "config": asdict(self.config),
            "note": "Internal holdout is diagnostic; no profitability claim. Future live-paper evidence remains required.",
        }
        payload["model_digest"] = _digest({k: v for k, v in payload.items() if k != "model_digest"})
        key = f"{ARTIFACT_PREFIX}{cutoff}:{self.release_sha[:12]}:{payload['model_digest'][:12]}"
        record = self.memory.persist_artifact(key, payload, recorded_at_ms=trained_at)
        return {
            "status": "TRAINED", "version": VERSION, "artifact_key": key,
            "artifact_digest": record["artifact_digest"], "model_digest": payload["model_digest"],
            "eligible": eligible, "training_events": len(train_groups), "validation_events": len(valid_groups),
            "training_rows": int(len(train_y)), "validation_rows": int(len(valid_y)),
            "validation_mae_r": validation_mae, "zero_baseline_mae_r": zero_mae,
            "lower_quantile_coverage": coverage, "entry_samples": len(entry_rows),
            "entry_positive": positives, "entry_negative": negatives,
        }
