"""V4 paper-only event ranking challenger built on verified V3 tick outcomes.

V4 deliberately separates three concepts:
1. event-relative ranking (LightGBM LambdaRank);
2. calibration of the selected candidate from causal out-of-fold predictions;
3. execution authority (always NONE in this module).

This module never replaces V2/V3 inference by itself.  It persists immutable
challenger artifacts that can be evaluated on future events before any paper
activation is considered.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import bisect
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any

from .counterfactual_learning import (
    CONTRACT,
    HORIZON_MS,
    MAX_ROWS,
    digest,
    load_samples,
    purged_split,
)
from .selective_ml import (
    FEATURE_SCHEMA,
    ML_FEATURE_NAMES,
    SelectiveMLConfig,
    _ml_imports,
    augment_vector,
)

VERSION = "SELECTIVE_ML_V4_RANK_CAL_PAPER"
TARGET = "EVENT_RELATIVE_RANK_FROM_TICK_INTEGER_R_AFTER_COST"
ARTIFACT_PREFIX = "ranking-v4:model:"
AUTHORITY = "RESEARCH_CHALLENGER_ONLY_NO_ORDER_AUTHORITY"
MIN_TRAIN_EVENTS = 80
MIN_HOLDOUT_EVENTS = 10
MIN_OOF_EVENTS = 30
OOF_FOLDS = 4
CALIBRATION_BINS = 4
EMBARGO_MS = HORIZON_MS + 300_000


@dataclass(frozen=True)
class V4Config:
    num_boost_round: int = 180
    early_stopping_rounds: int = 20
    learning_rate: float = 0.035
    num_leaves: int = 15
    max_depth: int = 4
    min_data_in_leaf: int = 40
    threads: int = 1

    def validate(self) -> None:
        if not 20 <= self.num_boost_round <= 1000:
            raise ValueError("V4_TREES_INVALID")
        if not 2 <= self.num_leaves <= 63 or not 2 <= self.max_depth <= 8:
            raise ValueError("V4_COMPLEXITY_INVALID")
        if not 10 <= self.min_data_in_leaf <= 5000:
            raise ValueError("V4_MIN_LEAF_INVALID")
        if not 1 <= self.threads <= 4:
            raise ValueError("V4_THREADS_INVALID")


def enabled() -> bool:
    value = os.environ.get("NBOT_RANKING_V4", "0")
    if value not in {"0", "1"}:
        raise ValueError("NBOT_RANKING_V4_SETTING_INVALID")
    return value == "1"


def relevance(target_r: float) -> int:
    """Ordinal event relevance. Numeric R is never treated as a rank score."""
    value = float(target_r)
    if not math.isfinite(value):
        raise ValueError("V4_TARGET_NONFINITE")
    if value >= 1.0:
        return 4
    if value >= 0.5:
        return 3
    if value > 0.0:
        return 2
    if value > -0.5:
        return 1
    return 0


def _ranking_matrix(groups, np):
    x: list[list[float]] = []
    y: list[int] = []
    weights: list[float] = []
    sizes: list[int] = []
    row_ids: list[str] = []
    event_ids: list[int] = []
    actual: list[float] = []

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
            usable.append((row, vector, target))
        if len(usable) < 2:
            continue
        event_weight = 1.0 / len(usable)
        sizes.append(len(usable))
        for row, vector, target in usable:
            x.append([vector[name] for name in ML_FEATURE_NAMES])
            y.append(relevance(target))
            weights.append(event_weight)
            row_ids.append(str(row["id"]))
            event_ids.append(int(event_ms))
            actual.append(target)

    return (
        np.asarray(x, dtype="float32"),
        np.asarray(y, dtype="int32"),
        np.asarray(weights, dtype="float32"),
        sizes,
        row_ids,
        event_ids,
        actual,
    )


def _train_ranker(lgb, train, valid, *, cfg: V4Config):
    tx, ty, tw, tg, *_ = train
    vx, vy, vw, vg, *_ = valid
    if len(tx) == 0 or len(vx) == 0 or not tg or not vg:
        raise ValueError("V4_EMPTY_RANK_DATASET")
    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [1, 3, 5],
        "label_gain": [0, 1, 3, 7, 15],
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
        "seed": 417,
        "feature_fraction_seed": 417,
        "bagging_seed": 417,
        "deterministic": True,
        "force_col_wise": True,
    }
    train_set = lgb.Dataset(
        tx, label=ty, weight=tw, group=tg,
        feature_name=list(ML_FEATURE_NAMES), free_raw_data=False,
    )
    valid_set = lgb.Dataset(
        vx, label=vy, weight=vw, group=vg, reference=train_set,
        feature_name=list(ML_FEATURE_NAMES), free_raw_data=False,
    )
    return lgb.train(
        params,
        train_set,
        num_boost_round=cfg.num_boost_round,
        valid_sets=[valid_set],
        valid_names=["validation"],
        callbacks=[lgb.early_stopping(cfg.early_stopping_rounds, verbose=False)],
    )


def _selected_from_predictions(matrix, predictions):
    _, _, _, sizes, row_ids, event_ids, actual = matrix
    selected = []
    offset = 0
    for size in sizes:
        stop = offset + size
        block = [
            (float(predictions[i]), row_ids[i], actual[i], event_ids[i])
            for i in range(offset, stop)
        ]
        block.sort(key=lambda item: (-item[0], item[1]))
        winner = block[0]
        runner = block[1]
        selected.append({
            "event_ms": winner[3],
            "row_id": winner[1],
            "score": winner[0],
            "margin": winner[0] - runner[0],
            "target_net_r": winner[2],
            "positive": winner[2] > 0.0,
        })
        offset = stop
    return selected


def _pav(values: list[float], weights: list[int]) -> list[float]:
    """Pool-adjacent-violators monotone nondecreasing fit."""
    blocks = [[float(v), int(w), 1] for v, w in zip(values, weights)]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] <= blocks[i + 1][0]:
            i += 1
            continue
        total_w = blocks[i][1] + blocks[i + 1][1]
        mean = (
            blocks[i][0] * blocks[i][1]
            + blocks[i + 1][0] * blocks[i + 1][1]
        ) / total_w
        count = blocks[i][2] + blocks[i + 1][2]
        blocks[i:i + 2] = [[mean, total_w, count]]
        i = max(0, i - 1)
    out = []
    for value, _weight, count in blocks:
        out.extend([value] * count)
    return out


def build_calibration(selected: list[dict[str, Any]], *, bins: int = CALIBRATION_BINS) -> dict[str, Any]:
    if len(selected) < MIN_OOF_EVENTS:
        raise ValueError("V4_INSUFFICIENT_OOF_CALIBRATION")
    ordered = sorted(selected, key=lambda row: (row["margin"], row["event_ms"], row["row_id"]))
    bins = max(2, min(int(bins), len(ordered) // 5))
    chunks = []
    for index in range(bins):
        lo = index * len(ordered) // bins
        hi = (index + 1) * len(ordered) // bins
        chunk = ordered[lo:hi]
        if not chunk:
            continue
        chunks.append({
            "upper_margin": float(chunk[-1]["margin"]),
            "count": len(chunk),
            "mean_net_r": sum(float(r["target_net_r"]) for r in chunk) / len(chunk),
            "positive_rate": sum(bool(r["positive"]) for r in chunk) / len(chunk),
        })
    counts = [int(row["count"]) for row in chunks]
    mean_fit = _pav([float(row["mean_net_r"]) for row in chunks], counts)
    prob_fit = _pav([float(row["positive_rate"]) for row in chunks], counts)
    for row, mean_r, prob in zip(chunks, mean_fit, prob_fit):
        row["calibrated_mean_net_r"] = float(mean_r)
        row["calibrated_positive_rate"] = min(1.0, max(0.0, float(prob)))
    return {
        "method": "CAUSAL_OOF_MARGIN_QUANTILES_PAV_V1",
        "events": len(selected),
        "bins": chunks,
        "diagnostic_only_until_future_gate": True,
    }


def calibration_lookup(calibration: dict[str, Any], margin: float) -> dict[str, float | int]:
    bins = list(calibration.get("bins") or [])
    if not bins:
        raise ValueError("V4_CALIBRATION_EMPTY")
    uppers = [float(row["upper_margin"]) for row in bins]
    index = min(bisect.bisect_left(uppers, float(margin)), len(bins) - 1)
    row = bins[index]
    return {
        "expected_net_r": float(row["calibrated_mean_net_r"]),
        "positive_probability": float(row["calibrated_positive_rate"]),
        "support": int(row["count"]),
    }


def _causal_oof(train_groups, *, lgb, np, cfg: V4Config):
    n = len(train_groups)
    if n < MIN_TRAIN_EVENTS:
        return []
    starts = sorted(set(max(20, int(n * ratio)) for ratio in (0.40, 0.55, 0.70, 0.85)))
    selected = []
    for fold, start in enumerate(starts):
        stop = starts[fold + 1] if fold + 1 < len(starts) else n
        valid_groups = train_groups[start:stop]
        if not valid_groups:
            continue
        boundary = valid_groups[0][0]
        fit_groups = [
            (event, rows) for event, rows in train_groups[:start]
            if max(max(r["end_ms"], r["available_ms"]) for r in rows) + 300_000 < boundary
        ]
        if len(fit_groups) < 20:
            continue
        fit_matrix = _ranking_matrix(fit_groups, np)
        valid_matrix = _ranking_matrix(valid_groups, np)
        if not fit_matrix[3] or not valid_matrix[3]:
            continue
        ranker = _train_ranker(lgb, fit_matrix, valid_matrix, cfg=cfg)
        predictions = ranker.predict(valid_matrix[0])
        selected.extend(_selected_from_predictions(valid_matrix, predictions))
    return selected


class V4Runtime:
    def __init__(self, payload: dict[str, Any]):
        lgb, np = _ml_imports()
        if (
            payload.get("version") != VERSION
            or payload.get("target") != TARGET
            or payload.get("evidence_contract") != CONTRACT
            or payload.get("authority") != AUTHORITY
            or tuple(payload.get("feature_names", ())) != ML_FEATURE_NAMES
        ):
            raise ValueError("V4_ARTIFACT_CONTRACT_INVALID")
        expected = digest({k: v for k, v in payload.items() if k != "model_digest"})
        if payload.get("model_digest") != expected:
            raise ValueError("V4_ARTIFACT_DIGEST_INVALID")
        self.payload = payload
        self._np = np
        self.ranker = lgb.Booster(model_str=str(payload["ranking_model"]))

    def rank(self, candidates: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        if len(candidates) < 2:
            raise ValueError("V4_EVENT_REQUIRES_MULTIPLE_CANDIDATES")
        x = []
        for _candidate_id, vector in candidates:
            values = augment_vector(vector)
            x.append([values[name] for name in ML_FEATURE_NAMES])
        scores = self.ranker.predict(self._np.asarray(x, dtype="float32"))
        order = sorted(
            range(len(candidates)),
            key=lambda i: (-float(scores[i]), str(candidates[i][0])),
        )
        winner, runner = order[0], order[1]
        margin = float(scores[winner]) - float(scores[runner])
        calibrated = calibration_lookup(self.payload["calibration"], margin)
        return [
            {
                "candidate_id": str(candidates[i][0]),
                "rank": rank + 1,
                "rank_score": float(scores[i]),
                **(calibrated if i == winner else {}),
            }
            for rank, i in enumerate(order)
        ]


class V4RankingChallenger:
    """Persist V4 challenger artifacts. Never activates recommendation/order paths."""

    def __init__(self, memory, *, release_sha: str, ledger_path=None, config: V4Config | None = None):
        self.memory = memory
        self.release_sha = str(release_sha).strip()
        self.ledger_path = Path(ledger_path or memory.path.parent / "decision_outcomes.db")
        self.config = config or V4Config()
        self.config.validate()
        if len(self.release_sha) != 40 or any(c not in "0123456789abcdef" for c in self.release_sha.lower()):
            raise ValueError("V4_RELEASE_SHA_INVALID")

    def _records(self):
        return [
            record for record in self.memory.list_artifacts(prefix=ARTIFACT_PREFIX)
            if record["payload"].get("release_sha") == self.release_sha
        ]

    def status(self) -> dict[str, Any]:
        now = int(time.time() * 1000)
        rows, exclusions = load_samples(self.ledger_path, now_ms=now, limit=MAX_ROWS)
        train, valid = purged_split(rows)
        records = self._records()
        return {
            "version": VERSION,
            "enabled": enabled(),
            "authority": AUTHORITY,
            "order_authority": "NONE",
            "release_sha": self.release_sha,
            "eligible_rows": len(rows),
            "train_events_ready": len(train),
            "holdout_events_ready": len(valid),
            "candidate": records[-1]["artifact_key"] if records else None,
            "exclusions": exclusions,
        }

    def train_if_needed(self, *, force: bool = False) -> dict[str, Any]:
        if not enabled():
            return {"status": "DISABLED", "version": VERSION, "order_authority": "NONE"}
        now = int(time.time() * 1000)
        rows, exclusions = load_samples(self.ledger_path, now_ms=now, limit=MAX_ROWS)
        train, valid = purged_split(rows)
        if len(train) < MIN_TRAIN_EVENTS or len(valid) < MIN_HOLDOUT_EVENTS:
            return {
                "status": "WAIT_FOR_HIGH_RES_HISTORY",
                "train_events": len(train),
                "holdout_events": len(valid),
                "exclusions": exclusions,
            }
        cutoff = max(r["event_ms"] for _, rs in train + valid for r in rs)
        records = self._records()
        if not force and records and int(records[-1]["payload"]["training_cutoff_event_ms"]) == int(cutoff):
            return {"status": "UP_TO_DATE", "candidate": records[-1]["artifact_key"]}

        lgb, np = _ml_imports()
        train_matrix = _ranking_matrix(train, np)
        valid_matrix = _ranking_matrix(valid, np)
        if not train_matrix[3] or not valid_matrix[3]:
            return {"status": "WAIT_FOR_RANKABLE_EVENTS"}

        oof = _causal_oof(train, lgb=lgb, np=np, cfg=self.config)
        if len(oof) < MIN_OOF_EVENTS:
            return {"status": "WAIT_FOR_OOF_CALIBRATION", "oof_events": len(oof), "required": MIN_OOF_EVENTS}
        calibration = build_calibration(oof)

        ranker = _train_ranker(lgb, train_matrix, valid_matrix, cfg=self.config)
        validation_selected = _selected_from_predictions(valid_matrix, ranker.predict(valid_matrix[0]))
        validation_mean = sum(r["target_net_r"] for r in validation_selected) / len(validation_selected)
        validation_positive = sum(r["positive"] for r in validation_selected) / len(validation_selected)

        now = int(time.time() * 1000)
        used = [r for _, rs in train + valid for r in rs]
        payload = {
            "version": VERSION,
            "target": TARGET,
            "evidence_contract": CONTRACT,
            "feature_names": list(ML_FEATURE_NAMES),
            "feature_schema": FEATURE_SCHEMA,
            "release_sha": self.release_sha,
            "authority": AUTHORITY,
            "order_authority": "NONE",
            "trained_at_ms": now,
            "training_cutoff_event_ms": max(r["event_ms"] for r in used),
            "training_available_ms": max(r["available_ms"] for r in used),
            "training_events": len(train),
            "holdout_events": len(valid),
            "training_rows": len(train_matrix[1]),
            "holdout_rows": len(valid_matrix[1]),
            "data_digest": digest([(r["id"], r["source_digest"]) for r in used]),
            "ranking_model": ranker.model_to_string(),
            "ranking_objective": "lambdarank",
            "relevance_contract": "R>=1:4,R>=0.5:3,R>0:2,R>-0.5:1,ELSE:0",
            "calibration": calibration,
            "validation_top1_mean_net_r": float(validation_mean),
            "validation_top1_positive_rate": float(validation_positive),
            "config": asdict(self.config),
            "libraries": {
                "python": platform.python_version(),
                "lightgbm": lgb.__version__,
                "numpy": np.__version__,
            },
            "activation": "NONE_CHALLENGER_ONLY",
            "automatic_real_money_promotion": False,
            "recorded_at_ms": now,
        }
        payload["model_digest"] = digest(payload)
        record = self.memory.persist_artifact(
            ARTIFACT_PREFIX + payload["model_digest"],
            payload,
            recorded_at_ms=now,
        )
        return {
            "status": "V4_CANDIDATE_FROZEN",
            "candidate": record["artifact_key"],
            "artifact_digest": record["artifact_digest"],
            "validation_top1_mean_net_r": validation_mean,
            "validation_top1_positive_rate": validation_positive,
            "order_authority": "NONE",
        }
