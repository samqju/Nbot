"""Paper-only learning from verified forward tick-policy decision outcomes.

V2 bar labels are never mixed into this target. Candidate fitting and future
evaluation run under the existing research command lock, not the quote thread.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import math
import os
import platform
import sqlite3
import time

from .selection import FEATURE_VECTOR_NAMES
from .features import CANONICAL_FEATURE_VERSION
from .selective_ml import (SelectiveMLManager, SelectiveMLRuntime, VERSION as V2,
    _matrix, _train_booster, _ml_imports, ML_FEATURE_NAMES, FEATURE_SCHEMA,
    LOWER_QUANTILE, MEAN_SCORE_WEIGHT, LOWER_SCORE_WEIGHT)

VERSION = "SELECTIVE_ML_V3_TICK_PAPER"
CONTRACT = "FORWARD_TICK_ATR_COSTS_V1"
TARGET = "TICK_INTEGER_R_AFTER_COST_COUNTERFACTUAL_NOT_EXECUTION_PNL"
MODEL_PREFIX = "cf-learning:v1:model:"
REVIEW_PREFIX = "cf-learning:v1:review:"
ACTIVATION_PREFIX = "cf-learning:v1:activation:"
HORIZON_MS = 4 * 60 * 60 * 1000
SPACING_MS = HORIZON_MS + 300_000
MIN_TRAIN_EVENTS = 80
MIN_HOLDOUT_EVENTS = 10
FUTURE_EVENTS = 20  # ten diagnostic validation events + ten untouched test events
MAX_ROWS = 60_000
MAX_EVENTS = 3000
MAX_BOUNDARY_DELAY_MS = 10_000


def enabled():
    value = os.environ.get("NBOT_COUNTERFACTUAL_LEARNING", "1")
    if value not in {"0", "1"}:
        raise ValueError("COUNTERFACTUAL_LEARNING_SETTING_INVALID")
    return value == "1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def runtime_from_payload(payload):
    if payload.get("version") == VERSION:
        if (payload.get("target") != TARGET or payload.get("evidence_contract") != CONTRACT
                or payload.get("authority") != "PAPER_MODEL_ONLY_NO_ORDER_AUTHORITY"
                or payload.get("model_digest") != digest({k: v for k, v in payload.items() if k != "model_digest"})):
            raise ValueError("COUNTERFACTUAL_MODEL_CONTRACT_INVALID")
        # The serialized boosting schema is shared, the label/promotion contracts are not.
        return SelectiveMLRuntime({**payload, "version": V2})
    return SelectiveMLRuntime(payload)


def load_samples(path, *, now_ms, limit=MAX_ROWS):
    """Read a bounded consistent snapshot. Old records without inputs stay excluded."""
    if not Path(path).is_file():
        return [], {"ledger": "NOT_CREATED"}
    rows, exclusions = [], defaultdict(int)
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
        conn.execute("BEGIN")
        # Limit by newest decision, not exit time: avoids preferring fast stopouts.
        records = conn.execute("""SELECT d.payload_json,d.digest,o.payload_json,o.digest
            FROM frozen_decisions d JOIN matured_outcomes o USING(decision_id,policy_id)
            WHERE o.actual_execution=0 AND o.matured_at_ms<? AND d.decision_time_ms<?
              AND NOT EXISTS (SELECT 1 FROM unresolved_outcomes u WHERE u.decision_id=d.decision_id AND u.policy_id=d.policy_id)
            ORDER BY d.decision_time_ms DESC,d.decision_id DESC LIMIT ?""",
            (now_ms, now_ms-HORIZON_MS-130_000, limit)).fetchall()
    if len(records) == limit:
        boundary = json.loads(records[-1][0])["decision_time_ms"]
        records = [r for r in records if json.loads(r[0])["decision_time_ms"] != boundary]
    for dj, dd, oj, od in records:
        try:
            d, o = json.loads(dj), json.loads(oj)
            x, evidence = d.get("extras", {}), o.get("evidence", {})
            if digest(d) != dd or digest(o) != od:
                raise ValueError("DIGEST")
            if (x.get("training_contract") != CONTRACT or x.get("feature_schema") != FEATURE_SCHEMA
                    or x.get("canonical_feature_version") != CANONICAL_FEATURE_VERSION
                    or o.get("quality") != "AGGTRADE_RESOLVED" or o.get("actual_execution")
                    or d.get("policy_id") != "TICK_INTEGER_R_V1"
                    or o.get("policy_id") != d.get("policy_id")
                    or d.get("authority") != "RESEARCH_ONLY_NO_EXECUTION"
                    or o.get("authority") != "RESEARCH_ONLY_NO_EXECUTION"):
                raise ValueError("CONTRACT_OR_QUALITY")
            vector = x["feature_vector"]
            if (set(vector) != set(FEATURE_VECTOR_NAMES) or digest(vector) != d["feature_digest"]
                    or not all(math.isfinite(float(v)) for v in vector.values())):
                raise ValueError("FEATURES")
            entry, end, available = int(x["entry_time_ms"]), int(evidence["exit_time_ms"]), int(o["matured_at_ms"])
            if not d["decision_time_ms"] <= entry <= end <= available < now_ms:
                raise ValueError("TIME")
            if x.get("horizon_ms") != HORIZON_MS or end > entry + HORIZON_MS:
                raise ValueError("HORIZON")
            if (evidence.get("events_seen", 0) < 2 or not evidence.get("continuous")
                    or evidence.get("first_trade_ms", entry + MAX_BOUNDARY_DELAY_MS + 1) - entry > MAX_BOUNDARY_DELAY_MS
                    or not evidence.get("source_digest") or evidence["source_digest"] != o["source_digest"]):
                raise ValueError("COVERAGE")
            if o["exit_reason"] == "HORIZON" and entry + HORIZON_MS - end > MAX_BOUNDARY_DELAY_MS:
                raise ValueError("STALE_HORIZON")
            costs = x["costs"]
            if costs != {"taker_fee_rate": .0005, "entry_slippage_bps": 1.0,
                         "exit_slippage_bps": 1.0, "funding_r": 0.0}:
                raise ValueError("COSTS")
            rr = float(o["net_r"])
            if not math.isfinite(rr) or not 0 < float(x["one_r_price"]) < float(x["entry_price"]):
                raise ValueError("NUMERIC")
            if not math.isclose(x["one_r_price"] / x["entry_price"],
                                float(vector["atr14_frac"]), rel_tol=1e-8):
                raise ValueError("RISK_GEOMETRY")
            direction = 1 if d["side"] == "LONG" else -1
            gross = direction * (float(evidence["exit_price"]) - x["entry_price"]) / x["one_r_price"]
            expected = gross - (.001 + .0002) * x["entry_price"] / x["one_r_price"]
            if not math.isclose(expected, rr, rel_tol=1e-8, abs_tol=1e-8):
                raise ValueError("NET_COST_MISMATCH")
            if o["exit_reason"] not in {"STOP", "HORIZON"}:
                raise ValueError("EXIT_REASON")
            rows.append({"id": d["decision_id"], "event_ms": int(d["decision_time_ms"]),
                "entry_ms": entry, "end_ms": end, "available_ms": available,
                "symbol": d["symbol"], "side": d["side"], "approved": d["approved"],
                "feature_vector_json": json.dumps(vector), "target_net_r": rr,
                "ridge_score": d.get("ridge_score_r"), "source_digest": digest([dd, od]),
                "sampling": "CONDITIONAL_ON_HIGH_RES_POOL_NOT_MARKET_WIDE"})
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            exclusions[str(exc)[:80]] += 1
    return sorted(rows, key=lambda r: (r["event_ms"], r["id"])), dict(exclusions)


def groups_for(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["event_ms"]].append(row)
    return sorted(groups.items())


def purged_split(rows):
    groups = groups_for(rows)[-MAX_EVENTS:]
    split = int(len(groups) * .8)
    if not split or split == len(groups):
        return [], []
    boundary = groups[split][0]
    # A row cap must not make ten non-overlapping diagnostic events impossible
    # in a dense 100/20 stream. Reserve their time span before fitting.
    reserve, previous = [], float("inf")
    for event, rs in reversed(groups):
        if previous - event >= SPACING_MS:
            reserve.append(event)
            previous = event
        if len(reserve) == MIN_HOLDOUT_EVENTS:
            boundary = min(boundary, reserve[-1])
            split = next(i for i, (event, _) in enumerate(groups) if event >= boundary)
            break
    # Purge labels AND receipt availability, not just the row's decision time.
    train = [(t, rs) for t, rs in groups[:split]
             if max(max(r["end_ms"], r["available_ms"]) for r in rs) + 300_000 < boundary]
    valid, last = [], -SPACING_MS
    for event, rs in groups[split:]:
        if event - last >= SPACING_MS:
            valid.append((event, rs))
            last = event
    return train, valid


def portfolio_metrics(groups, predictions, *, threshold=.08, edge=.05, extra_cost=.0):
    """One-position executable-capacity diagnostic on identical observed samples.

    Missing high-res candidates are missing, not zero-return trades. Does not
    represent the full market portfolio or exchange fills.
    """
    available_at, equity, peak, drawdown, count = -1, 0., 0., 0., 0
    selected = []
    for event, rows in groups:
        if event <= available_at:
            continue
        ranked = sorted(((predictions[r["id"]], r) for r in rows),
                        key=lambda p: (-p[0], p[1]["symbol"], p[1]["side"]))
        score, row = ranked[0]
        if score < threshold or (len(ranked) > 1 and score - ranked[1][0] < edge):
            continue
        equity += row["target_net_r"] - extra_cost
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
        available_at = row["end_ms"]
        count += 1
        selected.append(row["id"])
    return {"trades": count, "net_r": equity, "drawdown_r": drawdown,
            "selected_ids": selected, "capacity": 1,
            "scope": "OBSERVED_HIGH_RES_POOL_COUNTERFACTUAL_NOT_ACTUAL_PNL"}


class CounterfactualLearner:
    def __init__(self, memory, *, release_sha, ledger_path=None):
        self.memory, self.release_sha = memory, release_sha
        self.ledger_path = Path(ledger_path or memory.path.parent / "decision_outcomes.db")

    def _ridge_record(self, event_ms):
        from .learned_recommendation import LearnedTestnetSource
        return LearnedTestnetSource.ridge_record_for_memory(
            self.memory, release_sha=self.release_sha, event_ms=event_ms)

    def paper_incumbent(self, event_ms):
        """Freeze the same V3/V2/Ridge hierarchy and V2 blend used by paper inference."""
        from .selective_ml import SelectiveMLConfig
        ml_setting = os.environ.get("NBOT_SELECTIVE_ML", "1")
        if ml_setting not in {"0", "1"}:
            raise ValueError("NBOT_SELECTIVE_ML_INVALID")
        if ml_setting == "0":
            return None  # no nonlinear replacement while nonlinear inference is disabled
        active = self.active(event_ms=event_ms) if ml_setting == "1" else None
        if active:
            return {"kind": VERSION, "key": active["artifact_key"],
                    "digest": active["artifact_digest"], "threshold": .08, "edge": .05}
        cfg = SelectiveMLConfig.from_environment()
        v2 = (SelectiveMLManager(self.memory, release_sha=self.release_sha, config=cfg)
              .latest_for_event(event_ms)) if ml_setting == "1" else None
        ridge = self._ridge_record(event_ms)
        if ridge is None:
            return None  # inference cannot recommend without a compatible Ridge base
        result = {"kind": V2 if v2 else "RIDGE", "key": v2["artifact_key"] if v2 else ridge["artifact_key"],
            "digest": v2["artifact_digest"] if v2 else ridge["artifact_digest"],
            "ridge_key": ridge["artifact_key"], "ridge_digest": ridge["artifact_digest"],
            "threshold": cfg.min_lower_r if v2 else .08, "edge": cfg.min_edge_gap_r if v2 else .05}
        return result

    def _incumbent_matches(self, payload, now):
        frozen = payload.get("incumbent")
        return frozen is not None and self.paper_incumbent(now) == frozen

    def _verified_record(self, key, expected_digest):
        record = self.memory.artifact(key)
        if record is None or record["artifact_digest"] != expected_digest:
            raise ValueError("PAPER_INCUMBENT_ARTIFACT_CHANGED")
        return record

    def _records(self, prefix):
        if not self.memory.path.is_file():
            return []
        with closing(sqlite3.connect(self.memory.path.resolve().as_uri()+"?mode=ro", uri=True, timeout=2)) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='research_memory_artifacts'").fetchone() is None:
                return []
            keys = conn.execute("""SELECT artifact_key FROM research_memory_artifacts
                WHERE artifact_key LIKE ? AND json_extract(artifact_json,'$.release_sha')=?
                ORDER BY recorded_at_ms DESC,artifact_key DESC LIMIT 64""",
                (prefix+'%', self.release_sha)).fetchall()
        return [self.memory.artifact(key) for (key,) in reversed(keys)]

    def active(self, *, event_ms):
        activations = [r for r in self._records(ACTIVATION_PREFIX)
                       if r["payload"].get("release_sha") == self.release_sha
                       and r["payload"]["activated_at_ms"] < event_ms]
        if not activations:
            return None
        p = activations[-1]["payload"]
        if not p.get("model_key"):
            return None  # explicit rollback to V2
        record = self.memory.artifact(p["model_key"])
        if record is None or record["artifact_digest"] != p["model_artifact_digest"]:
            raise ValueError("COUNTERFACTUAL_ACTIVE_MODEL_LINK_INVALID")
        model = record["payload"]
        if model["trained_at_ms"] >= event_ms or model["training_available_ms"] >= event_ms:
            return None
        if model.get("version") != VERSION or model.get("release_sha") != self.release_sha:
            raise ValueError("COUNTERFACTUAL_ACTIVE_MODEL_RELEASE_INVALID")
        return record

    def status(self):
        now = int(time.time() * 1000)
        rows, excluded = load_samples(self.ledger_path, now_ms=now)
        candidates = [r for r in self._records(MODEL_PREFIX) if r["payload"]["release_sha"] == self.release_sha]
        active = self.active(event_ms=now)
        latest = candidates[-1] if candidates else None
        review = self.memory.artifact(REVIEW_PREFIX + latest["artifact_digest"]) if latest else None
        train, valid = purged_split(rows)
        future = len(future_groups(rows, latest["payload"]["trained_at_ms"])) if latest else 0
        return {"version": VERSION, "target": TARGET, "eligible_rows": len(rows),
            "accepted_opportunities": sum(bool(r["approved"]) for r in rows),
            "rejected_opportunities": sum(not r["approved"] for r in rows),
            "exclusions": excluded, "active_model": active["artifact_key"] if active else None,
            "candidate": latest["artifact_key"] if latest else None,
            "review": review["payload"] if review else None,
            "train_events_ready": len(train), "diagnostic_events_ready": len(valid),
            "future_events_collected": future,
            "future_events_required": FUTURE_EVENTS, "order_authority": "NONE"}

    def _save(self, prefix, payload):
        return self.memory.persist_artifact(prefix + digest(payload), payload,
                                            recorded_at_ms=payload.get("recorded_at_ms"))

    def rollback(self):
        now = int(time.time() * 1000)
        current = self.active(event_ms=now)
        if not current:
            return {"status": "NO_V3_MODEL_ACTIVE"}
        activations = [r["payload"] for r in self._records(ACTIVATION_PREFIX)
                       if r["payload"].get("release_sha") == self.release_sha]
        previous = activations[-1].get("previous_model_key")
        record = self.memory.artifact(previous) if previous else None
        self._save(ACTIVATION_PREFIX, {"release_sha": self.release_sha, "activated_at_ms": now,
            "model_key": previous, "model_artifact_digest": record["artifact_digest"] if record else None,
            "previous_model_key": current["artifact_key"], "reason": "OPERATOR_PAPER_ROLLBACK",
            "recorded_at_ms": now, "authority": "PAPER_ONLY"})
        return {"status": "ROLLED_BACK", "model": previous or "V2_FALLBACK"}

    def train_if_needed(self):
        if not enabled():
            return {"status": "DISABLED_KEEP_V2_FALLBACK"}
        now = int(time.time() * 1000)
        rows, excluded = load_samples(self.ledger_path, now_ms=now)
        candidates = [r for r in self._records(MODEL_PREFIX) if r["payload"]["release_sha"] == self.release_sha]
        if candidates:
            candidate = candidates[-1]
            if self.memory.artifact(REVIEW_PREFIX + candidate["artifact_digest"]) is None:
                return self._evaluate(candidate, rows, now)
            # Never repeatedly tune on a finalized test window. Need fresh training evidence.
            review = self.memory.artifact(REVIEW_PREFIX + candidate["artifact_digest"])["payload"]
            if review["status"] == "PASS_PAPER_GATE" and not any(
                    r["payload"].get("review_digest") == digest(review)
                    for r in self._records(ACTIVATION_PREFIX)):
                if self._activate(candidate, review, now):
                    return {"status": "RECOVERED_PAPER_ACTIVATION"}
                # Stale passed evidence cannot activate; allow a new candidate
                # only once genuinely newer training evidence is available.
            if not rows or rows[-1]["event_ms"] <= review["through_event_ms"] + SPACING_MS:
                return {"status": "WAIT_FOR_NEW_TRAINING_EVIDENCE"}
        train, valid = purged_split(rows)
        if len(train) < MIN_TRAIN_EVENTS or len(valid) < MIN_HOLDOUT_EVENTS:
            return {"status": "WAIT_FOR_HIGH_RES_HISTORY", "train_events": len(train),
                    "holdout_events": len(valid), "exclusions": excluded}
        lgb, np = _ml_imports()
        from .selective_ml import SelectiveMLConfig
        cfg = SelectiveMLConfig.from_environment()
        tx, ty, tw, _ = _matrix(train, np)
        vx, vy, vw, _ = _matrix(valid, np)
        if len(ty) < 2 * cfg.min_data_in_leaf:
            return {"status": "WAIT_FOR_HIGH_RES_ROWS"}
        mean = _train_booster(lgb, tx, ty, tw, vx, vy, vw, cfg=cfg, objective="regression")
        lower = _train_booster(lgb, tx, ty, tw, vx, vy, vw, cfg=cfg, objective="quantile", alpha=LOWER_QUANTILE)
        now = int(time.time() * 1000)  # actual completion time, not fitting start
        incumbent = self.paper_incumbent(now)
        if incumbent is None:
            return {"status": "WAIT_FOR_PAPER_INCUMBENT"}
        used = [r for _, rs in train + valid for r in rs]
        payload = {"version": VERSION, "target": TARGET, "evidence_contract": CONTRACT,
            "feature_names": list(ML_FEATURE_NAMES), "feature_schema": FEATURE_SCHEMA,
            "release_sha": self.release_sha, "authority": "PAPER_MODEL_ONLY_NO_ORDER_AUTHORITY",
            "trained_at_ms": now, "training_cutoff_event_ms": max(r["event_ms"] for r in used),
            "training_available_ms": max(r["available_ms"] for r in used),
            "training_events": len(train), "holdout_events": len(valid),
            "training_rows": len(ty), "data_digest": digest([(r["id"], r["source_digest"]) for r in used]),
            "mean_model": mean.model_to_string(), "lower_model": lower.model_to_string(),
            "config": asdict(cfg), "incumbent": incumbent,
            "incumbent_key": incumbent["key"],
            "libraries": {"python": platform.python_version(), "lightgbm": lgb.__version__,
                          "numpy": np.__version__},
            "selection_gate": {"min_lower_r": .08, "min_edge_gap_r": .05},
            "mean_score_weight": MEAN_SCORE_WEIGHT, "lower_score_weight": LOWER_SCORE_WEIGHT,
            "entry_gate_mode": "EXECUTION_REALTIME_ONLY", "recorded_at_ms": now,
            "validation_mae_r": float(np.average(np.abs(vy - mean.predict(vx)), weights=vw)),
            "sampling_scope": "CONDITIONAL_HIGH_RES_POOL", "automatic_real_money_promotion": False}
        payload["model_digest"] = digest(payload)
        record = self._save(MODEL_PREFIX, payload)
        return {"status": "CANDIDATE_FROZEN_WAIT_FUTURE", "candidate": record["artifact_key"]}

    def _evaluate(self, candidate, rows, now):
        p = candidate["payload"]
        if not self._incumbent_matches(p, now):
            review = {"status": "REJECT_PAPER_GATE", "reason": "INCUMBENT_CHANGED_OR_UNFROZEN",
                "incumbent_changed_during_evaluation": True, "candidate_key": candidate["artifact_key"],
                "candidate_digest": candidate["artifact_digest"], "through_event_ms": now,
                "release_sha": self.release_sha, "recorded_at_ms": now, "order_authority": "NONE"}
            self.memory.persist_artifact(REVIEW_PREFIX + candidate["artifact_digest"], review, recorded_at_ms=now)
            return review
        groups = future_groups(rows, p["trained_at_ms"])
        if len(groups) < FUTURE_EVENTS:
            return {"status": "WAIT_FOR_FUTURE_EVALUATION", "events": len(groups), "required": FUTURE_EVENTS}
        candidate_runtime = runtime_from_payload(p)
        frozen = p["incumbent"]
        incumbent = self._verified_record(frozen["key"], frozen["digest"])
        incumbent_runtime = runtime_from_payload(incumbent["payload"]) if frozen["kind"] != "RIDGE" else None
        ridge = (self._verified_record(frozen["ridge_key"], frozen["ridge_digest"])
                 if frozen["kind"] != VERSION else None)
        from .selection import _ridge_score
        means, scores, old_means, old_scores = {}, {}, {}, {}
        for _, rs in groups:
            for r in rs:
                vector = json.loads(r["feature_vector_json"])
                mean, lower = candidate_runtime.score(vector)
                means[r["id"]], scores[r["id"]] = mean, .7 * mean + .3 * lower
                if incumbent_runtime:
                    om, ol = incumbent_runtime.score(vector)
                    if frozen["kind"] == V2:
                        om = .25 * _ridge_score(ridge["payload"]["model"], r["feature_vector_json"]) + .75 * om
                else:
                    om = ol = _ridge_score(ridge["payload"]["model"], r["feature_vector_json"])
                old_means[r["id"]], old_scores[r["id"]] = om, .7 * om + .3 * ol
        reports = [evaluate_window(window, means, scores, old_means, old_scores,
                                   incumbent_gate=frozen)
                   for window in (groups[:10], groups[10:])]
        passed = all(r["passed"] for r in reports)
        incumbent_changed = not self._incumbent_matches(p, int(time.time() * 1000))
        passed = passed and not incumbent_changed
        review = {"status": "PASS_PAPER_GATE" if passed else "REJECT_PAPER_GATE",
            "candidate_key": candidate["artifact_key"], "candidate_digest": candidate["artifact_digest"],
            "validation": reports[0], "final_test": reports[1], "recorded_at_ms": now,
            "through_event_ms": groups[-1][0], "release_sha": self.release_sha,
            "evaluation_ids_digest": digest([[r["id"] for r in rs] for _, rs in groups]),
            "incumbent_changed_during_evaluation": incumbent_changed,
            "incumbent": frozen,
            "economic_proof": False, "order_authority": "NONE"}
        self.memory.persist_artifact(REVIEW_PREFIX + candidate["artifact_digest"], review, recorded_at_ms=now)
        if passed:
            self._activate(candidate, review, now)
        return review

    def _activate(self, candidate, review, now):
        if not enabled() or review.get("status") != "PASS_PAPER_GATE" or not self._incumbent_matches(candidate["payload"], now):
            return False
        active = self.active(event_ms=now)
        self._save(ACTIVATION_PREFIX, {"model_key": candidate["artifact_key"],
            "model_artifact_digest": candidate["artifact_digest"], "release_sha": self.release_sha,
            "previous_model_key": active["artifact_key"] if active else None,
            "activated_at_ms": now, "reason": "PASS_PAPER_GATE", "review_digest": digest(review),
            "incumbent": candidate["payload"]["incumbent"],
            "recorded_at_ms": now, "authority": "PAPER_ONLY"})
        return True


def evaluate_window(groups, means, scores, old_means, old_scores, *, incumbent_gate=None):
    errors, old_errors, zeros = [], [], []
    for _, rs in groups:
        errors.append(sum(abs(max(-3., min(3., r["target_net_r"])) - means[r["id"]]) for r in rs) / len(rs))
        old_errors.append(sum(abs(max(-3., min(3., r["target_net_r"])) - old_means[r["id"]]) for r in rs) / len(rs))
        zeros.append(sum(abs(max(-3., min(3., r["target_net_r"]))) for r in rs) / len(rs))
    avg = lambda values: sum(values) / len(values)
    new = portfolio_metrics(groups, scores)
    gate = incumbent_gate or {"threshold": .08, "edge": .05}
    old = portfolio_metrics(groups, old_scores, threshold=gate["threshold"], edge=gate["edge"])
    stressed = portfolio_metrics(groups, scores, extra_cost=.10)
    selected = set(new["selected_ids"])
    regime_results = defaultdict(list)
    avoided_losses = missed_winners = 0
    for _, rs in groups:
        for row in rs:
            if not row["approved"]:
                avoided_losses += row["target_net_r"] < 0
                missed_winners += row["target_net_r"] > 0
            if row["id"] in selected:
                volatility = json.loads(row["feature_vector_json"])["volatility_percentile"]
                bucket = "LOW" if volatility < 1/3 else "HIGH" if volatility > 2/3 else "NORMAL"
                regime_results[bucket].append(row["target_net_r"])
    regimes = {name: {"trades": len(values), "mean_net_r": avg(values)}
               for name, values in regime_results.items()}
    checks = {"prediction_beats_zero": avg(errors) < avg(zeros),
        "prediction_not_worse_than_incumbent": avg(errors) <= avg(old_errors),
        "enough_trades": new["trades"] >= 5, "positive_after_cost": new["net_r"] > 0,
        "cost_stress_positive": stressed["net_r"] > 0,
        "net_not_worse": new["net_r"] >= old["net_r"],
        "net_improvement_at_least_0_1r": new["net_r"] >= old["net_r"] + .1,
        "drawdown_not_worse": new["drawdown_r"] <= old["drawdown_r"],
        "no_supported_regime_catastrophe": all(r["trades"] < 3 or r["mean_net_r"] > -1
                                               for r in regimes.values())}
    return {"passed": all(checks.values()), "checks": checks, "events": len(groups),
        "mae_r": avg(errors), "zero_mae_r": avg(zeros), "incumbent_mae_r": avg(old_errors),
        "candidate": new, "incumbent": old, "extra_0_1r_cost": stressed,
        "volatility_regimes": regimes, "rejected_avoided_losses": avoided_losses,
        "rejected_missed_winners": missed_winners}


def future_groups(rows, trained_at_ms):
    groups, last = [], trained_at_ms
    for event, rs in groups_for(rows):
        if event > trained_at_ms and event - last >= SPACING_MS:
            groups.append((event, rs))
            last = event
        if len(groups) == FUTURE_EVENTS:
            break
    return groups


class PaperLearningManager(SelectiveMLManager):
    """V3 active model first; V2 is an explicit fallback. Paper callers only."""
    def latest_for_event(self, event_ms):
        if enabled() and self.memory.path.is_file():
            active = CounterfactualLearner(self.memory, release_sha=self.release_sha).active(event_ms=event_ms)
            if active:
                return active
        return super().latest_for_event(event_ms)
