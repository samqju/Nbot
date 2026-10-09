"""Selective ML V3: high-resolution decision-outcome learning.

V3 never substitutes the old 5-minute bar-policy label for its target. It joins
causal decision-time feature vectors in permanent research memory to resolved,
funding-complete Binance aggTrade counterfactual outcomes.

Until enough V3 evidence exists, inference may use an eligible V2 artifact from
the same release. The active artifact always declares its target and Ridge blend.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict
import hashlib
import json
import math
import time
from typing import Any

from .decision_ledger import DecisionOutcomeLedger
from .decision_policy import GatePolicyCalibrator
from .research_memory import ResearchMemoryStore
from .selective_ml import (
    LOWER_QUANTILE, LOWER_SCORE_WEIGHT, MEAN_SCORE_WEIGHT, ML_FEATURE_NAMES,
    SelectiveMLConfig, SelectiveMLManager as V2Manager,
    SelectiveMLRuntime as V2Runtime, VERSION as V2_VERSION,
    augment_vector, _ml_imports, _train_booster,
)

VERSION = "SELECTIVE_ML_V3"
FEATURE_SCHEMA = "SELECTIVE_ML_FEATURES_V3_AGGTRADE_TARGET"
ARTIFACT_PREFIX = "selective-ml:v3:model:"
TARGET = "AGGTRADE_EXECUTION_ALIGNED_INTEGER_R_AFTER_COST_NET_R_COUNTERFACTUAL"
AUTHORITY = "RESEARCH_ONLY_MODEL_LIVE_PAPER_SELECTION_ONLY"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _groups(memory: ResearchMemoryStore, ledger: DecisionOutcomeLedger,
            cfg: SelectiveMLConfig) -> list[tuple[int, list[dict[str, Any]]]]:
    targets = ledger.training_targets()
    grouped: deque[tuple[int, list[dict[str, Any]]]] = deque()
    event = None
    rows: list[dict[str, Any]] = []
    total = 0

    def push(event_ms, values):
        nonlocal total
        if not values:
            return
        grouped.append((int(event_ms), values))
        total += len(values)
        while len(grouped) > cfg.max_events or total > cfg.max_rows:
            _, removed = grouped.popleft()
            total -= len(removed)

    for event_ms, row in memory.iter_training_rows():
        event_ms = int(event_ms)
        key = (event_ms, str(row.get("symbol")), str(row.get("side")))
        target = targets.get(key)
        if event is None:
            event = event_ms
        if event_ms != event:
            push(event, rows)
            event, rows = event_ms, []
        if target is None:
            continue
        try:
            vector_json = str(row["feature_vector_json"])
            vector = json.loads(vector_json)
            # The frozen decision vector must match permanent causal research
            # memory; mismatch is excluded instead of silently relabelled.
            frozen = target["feature_vector"]
            if _canonical(vector) != _canonical(frozen):
                continue
            value = float(target["target_net_r"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if not math.isfinite(value):
            continue
        rows.append({**row, "target_net_r": value})
    if event is not None:
        push(event, rows)
    return list(grouped)


def _matrix(groups, np):
    x, y, w, events = [], [], [], []
    for event_ms, rows in groups:
        usable = []
        for row in rows:
            try:
                vector = augment_vector(json.loads(str(row["feature_vector_json"])))
                target = max(-3.0, min(3.0, float(row["target_net_r"])))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if math.isfinite(target):
                usable.append((vector, target))
        if not usable:
            continue
        # One market timestamp has total weight one regardless of universe size.
        weight = 1.0 / len(usable)
        for vector, target in usable:
            x.append([vector[name] for name in ML_FEATURE_NAMES])
            y.append(target)
            w.append(weight)
            events.append(event_ms)
    return (np.asarray(x, dtype="float32"), np.asarray(y, dtype="float32"),
            np.asarray(w, dtype="float32"), events)


class SelectiveMLRuntime:
    """Runtime compatible with V3 and an explicitly-labelled V2 fallback."""
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.version = payload.get("version")
        self.legacy = None
        if self.version == V2_VERSION:
            self.legacy = V2Runtime(payload)
            return
        if self.version != VERSION or tuple(payload.get("feature_names", ())) != ML_FEATURE_NAMES:
            raise ValueError("SELECTIVE_ML_V3_ARTIFACT_CONTRACT_INVALID")
        lgb, np = _ml_imports()
        self._np = np
        self.mean = lgb.Booster(model_str=str(payload["mean_model"]))
        self.lower = lgb.Booster(model_str=str(payload["lower_model"]))

    def score(self, vector: dict[str, Any]) -> tuple[float, float]:
        if self.legacy is not None:
            return self.legacy.score(vector)
        values = augment_vector(vector)
        row = self._np.asarray([[values[name] for name in ML_FEATURE_NAMES]], dtype="float32")
        mean = float(self.mean.predict(row)[0])
        lower = float(self.lower.predict(row)[0])
        if not all(math.isfinite(v) for v in (mean, lower)):
            raise ValueError("SELECTIVE_ML_V3_PREDICTION_NONFINITE")
        return mean, lower


class SelectiveMLManager:
    def __init__(self, memory: ResearchMemoryStore, database=None, *, release_sha: str,
                 config: SelectiveMLConfig | None = None,
                 ledger: DecisionOutcomeLedger | None = None):
        self.memory = memory
        self.database = database
        self.release_sha = str(release_sha).strip()
        self.config = config or SelectiveMLConfig.from_environment()
        self.config.validate()
        path = (
            database.path.parent / "decision_outcomes.db"
            if database is not None else "data/observation/live/decision_outcomes.db"
        )
        self.ledger = ledger or DecisionOutcomeLedger(path)
        self.v2 = V2Manager(memory, database, release_sha=release_sha, config=self.config)
        if len(self.release_sha) != 40 or any(c not in "0123456789abcdef" for c in self.release_sha.lower()):
            raise ValueError("SELECTIVE_ML_RELEASE_SHA_INVALID")

    def _latest_v3(self):
        records = self.memory.list_artifacts(prefix=ARTIFACT_PREFIX)
        matches = [r for r in records if r["payload"].get("release_sha") == self.release_sha]
        return matches[-1] if matches else None

    def latest_for_event(self, event_ms: int):
        records = self.memory.list_artifacts(prefix=ARTIFACT_PREFIX)
        for record in reversed(records):
            payload = record["payload"]
            if payload.get("release_sha") != self.release_sha:
                continue
            if int(payload.get("trained_at_ms", 2**63-1)) >= int(event_ms):
                continue
            if int(payload.get("training_cutoff_event_ms", 2**63-1)) >= int(event_ms):
                continue
            if bool(payload.get("eligible")):
                return record
        return self.v2.latest_for_event(event_ms)

    def gate_for_record(self, record) -> tuple[float, float]:
        payload = record["payload"]
        if payload.get("version") == VERSION:
            policy = payload.get("gate_policy") or {}
            gate = policy.get("recommended_gate") if policy.get("qualified") else None
            if gate:
                return float(gate["min_confidence_r"]), float(gate["min_edge_gap_r"])
        gate = payload.get("selection_gate") or {}
        return (float(gate.get("min_lower_r", self.config.min_lower_r)),
                float(gate.get("min_edge_gap_r", self.config.min_edge_gap_r)))

    @staticmethod
    def ridge_blend_weight(record) -> float:
        payload = record["payload"]
        return float(payload.get("ridge_blend_weight", 0.25 if payload.get("version") == V2_VERSION else 0.0))

    @staticmethod
    def target_for_record(record) -> str:
        return str(record["payload"].get("target", TARGET))

    def status(self) -> dict[str, Any]:
        latest = self._latest_v3()
        fallback = self.v2.status()
        groups = _groups(self.memory, self.ledger, self.config)
        return {
            "version": VERSION, "authority": AUTHORITY, "release_sha": self.release_sha,
            "target": TARGET, "resolved_high_resolution_events": len(groups),
            "resolved_high_resolution_rows": sum(len(rows) for _, rows in groups),
            "decision_ledger": self.ledger.status(),
            "latest": None if latest is None else {
                "artifact_key": latest["artifact_key"],
                "artifact_digest": latest["artifact_digest"],
                **{k: latest["payload"].get(k) for k in (
                    "training_cutoff_event_ms","trained_at_ms","training_events","training_rows",
                    "validation_events","validation_rows","validation_mae_r","zero_baseline_mae_r",
                    "lower_quantile_coverage","eligible","entry_gate_mode","gate_policy",
                )},
            },
            "v2_same_release_fallback": fallback.get("latest"),
            "config": asdict(self.config),
        }

    def train_if_needed(self, *, force: bool = False) -> dict[str, Any]:
        groups = _groups(self.memory, self.ledger, self.config)
        if not groups:
            return {"status": "WAIT_FOR_HIGH_RESOLUTION_DECISION_OUTCOMES", "version": VERSION,
                    "decision_ledger": self.ledger.status()}
        cutoff = int(groups[-1][0])
        latest = self._latest_v3()
        if not force and latest is not None and int(latest["payload"].get("training_cutoff_event_ms", -1)) == cutoff:
            return {"status": "UP_TO_DATE", "version": VERSION,
                    "artifact_key": latest["artifact_key"], "artifact_digest": latest["artifact_digest"]}
        return self.train(groups=groups)

    def train(self, *, groups=None) -> dict[str, Any]:
        lgb, np = _ml_imports()
        groups = groups or _groups(self.memory, self.ledger, self.config)
        required = self.config.min_train_events + self.config.min_validation_events
        if len(groups) < required:
            return {"status": "WAIT_FOR_HIGH_RESOLUTION_ML_HISTORY", "version": VERSION,
                    "events": len(groups), "required": required,
                    "rows": sum(len(rows) for _, rows in groups)}
        split = max(self.config.min_train_events, int(len(groups) * self.config.train_fraction))
        split = min(split, len(groups)-self.config.min_validation_events)
        train_groups, valid_groups = groups[:split], groups[split:]
        train_x, train_y, train_w, _ = _matrix(train_groups, np)
        valid_x, valid_y, valid_w, _ = _matrix(valid_groups, np)
        if len(train_y) < self.config.min_data_in_leaf * 2 or len(valid_y) < 1:
            return {"status": "WAIT_FOR_HIGH_RESOLUTION_ML_ROWS", "version": VERSION,
                    "training_rows": int(len(train_y)), "validation_rows": int(len(valid_y))}
        mean = _train_booster(lgb, train_x, train_y, train_w, valid_x, valid_y, valid_w,
                              cfg=self.config, objective="regression_l1")
        lower = _train_booster(lgb, train_x, train_y, train_w, valid_x, valid_y, valid_w,
                               cfg=self.config, objective="quantile", alpha=LOWER_QUANTILE)
        mean_pred, lower_pred = mean.predict(valid_x), lower.predict(valid_x)
        validation_mae = float(np.average(np.abs(valid_y-mean_pred), weights=valid_w))
        zero_mae = float(np.average(np.abs(valid_y), weights=valid_w))
        coverage = float(np.average(valid_y >= lower_pred, weights=valid_w))
        eligible = bool(math.isfinite(validation_mae) and validation_mae < zero_mae)

        full_x, full_y, full_w, _ = _matrix(groups, np)
        full_ds = lgb.Dataset(full_x, label=full_y, weight=full_w,
                              feature_name=list(ML_FEATURE_NAMES), free_raw_data=False)
        common = {"learning_rate": self.config.learning_rate, "num_leaves": self.config.num_leaves,
                  "max_depth": self.config.max_depth, "min_data_in_leaf": self.config.min_data_in_leaf,
                  "feature_fraction": .85, "bagging_fraction": .80, "bagging_freq": 1,
                  "lambda_l1": .1, "lambda_l2": 1.0, "verbosity": -1,
                  "num_threads": self.config.threads, "seed": 391, "deterministic": True,
                  "force_col_wise": True}
        best_round = max(20, int(getattr(mean, "best_iteration", 0) or self.config.num_boost_round))
        lower_round = max(20, int(getattr(lower, "best_iteration", 0) or self.config.num_boost_round))
        mean_final = lgb.train({**common,"objective":"regression_l1","metric":"l1"},
                               full_ds, num_boost_round=best_round)
        lower_final = lgb.train({**common,"objective":"quantile","metric":"quantile",
                                 "alpha":LOWER_QUANTILE}, full_ds, num_boost_round=lower_round)
        importance = mean_final.feature_importance(importance_type="gain")
        top = sorted(zip(ML_FEATURE_NAMES,[float(v) for v in importance]),
                     key=lambda x:(-x[1],x[0]))[:20]
        cutoff, trained_at = int(groups[-1][0]), int(time.time()*1000)
        gate_policy = GatePolicyCalibrator(self.ledger).calibrate()
        payload = {
            "version":VERSION,"feature_schema":FEATURE_SCHEMA,"feature_names":list(ML_FEATURE_NAMES),
            "release_sha":self.release_sha,"authority":AUTHORITY,"target":TARGET,
            "target_evidence":"BINANCE_AGGTRADE_RESOLVED_FUNDING_COMPLETE_COUNTERFACTUAL",
            "counterfactual_not_execution_pnl":True,
            "training_cutoff_event_ms":cutoff,"trained_at_ms":trained_at,
            "training_events":len(train_groups),"training_rows":int(len(train_y)),
            "validation_events":len(valid_groups),"validation_rows":int(len(valid_y)),
            "all_events":len(groups),"all_rows":int(len(full_y)),
            "validation_mae_r":validation_mae,"zero_baseline_mae_r":zero_mae,
            "lower_quantile":LOWER_QUANTILE,"lower_quantile_coverage":coverage,
            "mean_score_weight":MEAN_SCORE_WEIGHT,"lower_score_weight":LOWER_SCORE_WEIGHT,
            "ridge_blend_weight":0.0,
            "eligible":eligible,
            "eligibility_rule":"CHRONOLOGICAL_VALIDATION_MAE_LT_ALWAYS_ZERO_MAE",
            "selection_gate":{"min_lower_r":self.config.min_lower_r,
                              "min_edge_gap_r":self.config.min_edge_gap_r},
            "gate_policy":gate_policy,
            "entry_gate_mode":"EXECUTION_REALTIME_WSS_ONLY",
            "mean_model":mean_final.model_to_string(),"lower_model":lower_final.model_to_string(),
            "feature_importance_gain_top20":top,"config":asdict(self.config),
            "note":"No 5m target fallback. Actual executed paper outcomes remain separate higher-quality execution evidence."
        }
        payload["model_digest"]=_digest({k:v for k,v in payload.items() if k!="model_digest"})
        key=f"{ARTIFACT_PREFIX}{cutoff}:{self.release_sha[:12]}:{payload['model_digest'][:12]}"
        record=self.memory.persist_artifact(key,payload,recorded_at_ms=trained_at)
        return {"status":"TRAINED","version":VERSION,"artifact_key":key,
                "artifact_digest":record["artifact_digest"],"model_digest":payload["model_digest"],
                "eligible":eligible,"training_events":len(train_groups),
                "validation_events":len(valid_groups),"training_rows":int(len(train_y)),
                "validation_rows":int(len(valid_y)),"validation_mae_r":validation_mae,
                "zero_baseline_mae_r":zero_mae,"lower_quantile_coverage":coverage,
                "gate_policy":gate_policy,"entry_gate_mode":"EXECUTION_REALTIME_WSS_ONLY"}
