"""Bounded G5 evaluation and G6 learning primitives; no automatic release.

All datasets are chronological, content-addressed, and grouped by overlapping
decision-to-exit intervals. Synthetic fixtures are never release evidence.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import random
import statistics
from nbot.v5.observation_contract import PATTERN_IDS

VERSION = "NBOT_V5_SCIENCE_V1"
STRUCTURES = ("BREAKOUT_UP", "BREAKOUT_DOWN", "COMPRESSION", "TREND_UP", "TREND_DOWN", "RANGE", "TRANSITION")
FEATURES = ("btc_confidence", "btc_return_1h", "coin_return_1h",
            "atr14_fraction", "relative_strength", "breadth", "source_quality", "side_long") + tuple(
            "pattern:"+k for k in PATTERN_IDS) + tuple("structure:"+k for k in STRUCTURES)
MAX_ROWS = 20000


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def sha(x):
    return isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdef" for c in x)


def causal_features(candidate, g3):
    f = g3["feature_evidence"]
    coin, btc = f["coins"][candidate["symbol"]], f["btc"]
    if (f["valid_from_ms"] > candidate["decision_at_ms"] or not btc["valid"]
            or coin["state"] != "AVAILABLE" or not f["breadth_available"]
            or coin["structure"] not in STRUCTURES or any(v == "UNAVAILABLE" for v in candidate["patterns"].values())):
        raise ValueError("G6_FEATURE_SOURCE_NOT_CAUSAL_OR_COMPLETE")
    result = {"btc_confidence": btc["confidence_score"], "btc_return_1h": btc["features"]["return_1h"],
              "coin_return_1h": coin["features"]["return_1h"], "atr14_fraction": coin["features"]["atr14_fraction"],
              "relative_strength": coin["relative_momentum_1h"], "breadth": f["breadth_1h"],
              "source_quality": 1.0, "side_long": float(candidate["side"] == "LONG")}
    result.update({"pattern:"+k: float(candidate["patterns"][k] == "MATCH") for k in PATTERN_IDS})
    result.update({"structure:"+k: float(coin["structure"] == k) for k in STRUCTURES})
    if not all(finite(v) for v in result.values()):
        raise ValueError("G6_FEATURE_SOURCE_NOT_FINITE")
    return result


@dataclass(frozen=True)
class Protocol:
    declared_ms: int
    evaluation_start_ms: int
    evaluation_end_ms: int
    min_outcomes: int = 2000
    min_blocks: int = 30
    min_symbols: int = 10
    min_regimes: int = 3
    min_per_side: int = 200
    min_span_ms: int = 7 * 86400000
    embargo_ms: int = 14400000
    bootstrap_replicates: int = 500
    max_drawdown_r: float = 10.0
    seed: int = 519

    def validate(self):
        if not (type(self.declared_ms) is int and type(self.evaluation_start_ms) is int
                and type(self.evaluation_end_ms) is int
                and 0 <= self.declared_ms < self.evaluation_start_ms < self.evaluation_end_ms
                and self.min_outcomes >= 2000 and self.min_blocks >= 30
                and self.min_symbols >= 10 and self.min_regimes >= 3
                and self.min_per_side >= 200 and self.min_span_ms >= 86400000
                and self.embargo_ms >= 14400000
                and 100 <= self.bootstrap_replicates <= 2000
                and finite(self.max_drawdown_r) and self.max_drawdown_r > 0):
            raise ValueError("G5_PROTOCOL_NOT_PROSPECTIVE_OR_THRESHOLDS_WEAKENED")


def dataset(rows, *, cutoff_ms, grade="ORIGINAL"):
    """Verify schema and immutable lineage, NOT exchange authenticity.

    Independent source audit must additionally verify hashes against originals.
    This function cannot grant scientific acceptance from caller assertions.
    """
    if type(cutoff_ms) is not int or not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("G5_DATASET_BOUNDS")
    if grade not in ("ORIGINAL", "SYNTHETIC"):
        raise ValueError("G5_DATASET_GRADE")
    ids = set()
    clean = []
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError("G5_ROW_SHAPE")
        if not sha(r.get("label_id")) or r["label_id"] in ids:
            raise ValueError("G5_DUPLICATED_OR_INVALID_LABEL")
        ids.add(r["label_id"])
        if (r.get("grade") != grade or r.get("status") != "SCORED"
                or r.get("source_grade") != "QUOTE_CONSTRAINED_SIMULATION"
                or not finite(r.get("net_r")) or not finite(r.get("gross_r"))
                or r.get("side") not in ("LONG", "SHORT")
                or not isinstance(r.get("symbol"), str)
                or not isinstance(r.get("regime"), str)
                or not isinstance(r.get("patterns"), list)):
            raise ValueError("G5_NOT_QUALIFIED_OUTCOME")
        clocks = [r.get(k) for k in ("event_ms", "feature_known_ms", "decision_ms", "exit_ms", "settled_ms")]
        if (any(type(t) is not int or t < 0 for t in clocks)
                or not clocks[0] <= clocks[1] <= clocks[2] < clocks[3] <= clocks[4] <= cutoff_ms):
            raise ValueError("G5_LEAKAGE_OR_UNMATURED")
        lineage = r.get("lineage", {})
        if set(lineage) != {"candidate", "g2", "g3", "policy", "path", "cost", "audit"} or not all(sha(v) for v in lineage.values()):
            raise ValueError("G5_SOURCE_LINEAGE_INCOMPLETE")
        if set(r.get("features", {})) != set(FEATURES) or not all(finite(v) for v in r["features"].values()):
            raise ValueError("G6_CAUSAL_FEATURE_SCHEMA")
        body = {k: v for k, v in r.items() if k != "row_sha256"}
        if r.get("row_sha256") != digest(body):
            raise ValueError("G5_ROW_TAMPER")
        clean.append(json.loads(canonical(r)))
    clean.sort(key=lambda r: (r["decision_ms"], r["label_id"]))
    return {"version": VERSION, "grade": grade, "cutoff_ms": cutoff_ms,
            "rows": clean, "dataset_sha256": digest(clean)}


def dependence_blocks(rows):
    """Conservative connected components of overlapping market windows.

    LONG/SHORT, symbols and pattern tags never multiply independent N.
    Dense continuous horizons may yield only ONE block: honest HOLD.
    """
    blocks, end = [], -1
    for r in sorted(rows, key=lambda x: (x["decision_ms"], x["label_id"])):
        if r["decision_ms"] > end:
            blocks.append([])
        blocks[-1].append(r)
        end = max(end, r["exit_ms"])
    return blocks


def selector(rows):
    """Frozen simple causal selector, at most one side/coin per event."""
    events = {}
    for r in rows:
        events.setdefault(r["event_ms"], []).append(r)
    selected = []
    for event in sorted(events):
        pool = [r for r in events[event] if r["features"]["source_quality"] >= 0.99
                and r["features"]["btc_confidence"] >= 0.7
                and (1 if r["side"] == "LONG" else -1) * r["features"]["relative_strength"] > 0]
        if pool:
            selected.append(sorted(pool, key=lambda r: (-abs(r["features"]["relative_strength"]), r["symbol"], r["side"]))[0])
    return selected


def portfolio_path(rows):
    """Single sequential equal-risk portfolio; overlapping entries abstain."""
    chosen, end = [], -1
    for r in sorted(rows, key=lambda x: (x["decision_ms"], x["label_id"])):
        if r["decision_ms"] > end:
            chosen.append(r)
            end = r["exit_ms"]
    equity = peak = drawdown = 0.0
    for r in chosen:
        equity += r["net_r"]
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    returns = sorted(r["net_r"] for r in chosen)
    tail = returns[:max(1, math.ceil(len(returns)*0.05))]
    return {"entries": len(chosen), "net_r": equity, "max_drawdown_r": drawdown,
            "tail_mean_r": statistics.mean(tail) if tail else None}


def evaluate(data, protocol):
    protocol.validate()
    checked = dataset(data["rows"], cutoff_ms=data["cutoff_ms"], grade=data["grade"])
    if checked["dataset_sha256"] != data["dataset_sha256"]:
        raise ValueError("G5_DATASET_TAMPER")
    rows = [r for r in checked["rows"] if protocol.evaluation_start_ms <= r["decision_ms"]
            and r["settled_ms"] <= protocol.evaluation_end_ms]
    blocks = dependence_blocks(rows)
    reasons = []
    counts = Counter(r["side"] for r in rows)
    span = max((r["exit_ms"] for r in rows), default=0) - min((r["decision_ms"] for r in rows), default=0)
    for name, bad in (("OUTCOMES_BELOW_2000", len(rows) < protocol.min_outcomes),
                      ("DEPENDENT_SAMPLE", len(blocks) < protocol.min_blocks),
                      ("COIN_DIVERSITY", len({r["symbol"] for r in rows}) < protocol.min_symbols),
                      ("REGIME_DIVERSITY", len({r["regime"] for r in rows}) < protocol.min_regimes),
                      ("SIDE_COVERAGE", any(counts[s] < protocol.min_per_side for s in ("LONG", "SHORT"))),
                      ("TIME_SPAN", span < protocol.min_span_ms)):
        if bad:
            reasons.append(name)
    means = [statistics.mean(r["net_r"] for r in b) for b in blocks]
    rng = random.Random(protocol.seed)
    boot = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(protocol.bootstrap_replicates)) if means else []
    lower = boot[int(len(boot)*0.025)] if boot else None
    simple = selector(rows)
    portfolio = portfolio_path(simple)
    regime = {k: statistics.mean(r["net_r"] for r in rows if r["regime"] == k) for k in sorted({r["regime"] for r in rows})}
    if lower is None or lower <= 0:
        reasons.append("NO_DEMONSTRABLE_POSITIVE_EDGE")
    if any(v <= 0 for v in regime.values()):
        reasons.append("REGIME_INSTABILITY")
    if portfolio["max_drawdown_r"] > protocol.max_drawdown_r:
        reasons.append("PORTFOLIO_DRAWDOWN")
    report = {"version": VERSION, "dataset_sha256": data["dataset_sha256"],
              "protocol_sha256": digest(protocol.__dict__), "qualified_outcomes": len(rows),
              "effective_sample_upper_bound": len(blocks), "event_count": len({r["event_ms"] for r in rows}),
              "coin_count": len({r["symbol"] for r in rows}), "side_counts": dict(counts),
              "span_ms": span, "block_mean_net_r": statistics.mean(means) if means else None,
              "block_bootstrap_lower_95": lower, "no_trade_baseline_r": 0,
              "simple_selector": portfolio, "regime_means": regime,
              "status": "INSUFFICIENT_EVIDENCE" if any(x in reasons for x in ("OUTCOMES_BELOW_2000", "DEPENDENT_SAMPLE", "COIN_DIVERSITY", "REGIME_DIVERSITY", "SIDE_COVERAGE", "TIME_SPAN")) else "NO_EDGE" if reasons else "REVIEW_REQUIRED",
              "reasons": reasons, "scientifically_accepted": False,
              "training_authority": "NONE", "paper_authority": "NONE"}
    report["report_sha256"] = digest(report)
    return report


def purged_split(rows, boundary_ms, embargo_ms=14400000):
    train = [r for r in rows if r["settled_ms"] < boundary_ms - embargo_ms]
    holdout = [r for r in rows if r["decision_ms"] >= boundary_ms]
    if {r["label_id"] for r in train} & {r["label_id"] for r in holdout}:
        raise ValueError("G6_SPLIT_OVERLAP")
    return train, holdout


def verify_review(envelope, *, key, subject_sha256, purpose, now_ms):
    """Key is independently provisioned; producer has no default approval key."""
    if not isinstance(key, bytes) or len(key) < 32 or not isinstance(envelope, dict):
        raise ValueError("INDEPENDENT_REVIEW_MISSING")
    body = envelope.get("body", {})
    signature = envelope.get("hmac_sha256", "")
    expected = hmac.new(key, ("NBOT-V5-INDEPENDENT-REVIEW\n" + canonical(body)).encode(), hashlib.sha256).hexdigest()
    if (not isinstance(signature, str) or not hmac.compare_digest(signature, expected)
            or body.get("purpose") != purpose or body.get("subject_sha256") != subject_sha256
            or body.get("verdict") != "ACCEPT" or not body.get("reviewer")
            or type(body.get("issued_ms")) is not int or type(body.get("expires_ms")) is not int
            or not body["issued_ms"] <= now_ms < body["expires_ms"]):
        raise ValueError("INDEPENDENT_REVIEW_INVALID")
    return body


def fit_candidate(data, *, boundary_ms, protocol, review=None, reviewer_key=None, now_ms=0,
                  synthetic=False, epochs=100):
    """Deterministic bounded ridge regression plus disjoint calibration.

    Candidate training never promotes a model. Production requires a separate
    independently signed G5 verdict and original grade. No no-trade Champion.
    """
    checked = dataset(data["rows"], cutoff_ms=data["cutoff_ms"], grade=data["grade"])
    if checked["dataset_sha256"] != data["dataset_sha256"]:
        raise ValueError("G6_DATASET_TAMPER")
    report = evaluate(data, protocol)
    if synthetic:
        if data["grade"] != "SYNTHETIC":
            raise ValueError("G6_SYNTHETIC_DATA_REQUIRED")
    else:
        if data["grade"] != "ORIGINAL" or report["status"] != "REVIEW_REQUIRED":
            raise ValueError("G6_G5_SCIENCE_HOLD")
        verify_review(review, key=reviewer_key, subject_sha256=report["report_sha256"], purpose="G5_TRAINING", now_ms=now_ms)
    if type(epochs) is not int or not 1 <= epochs <= 200:
        raise ValueError("G6_JOB_BOUNDS")
    train, holdout = purged_split(checked["rows"], boundary_ms, protocol.embargo_ms)
    if len(train) < 20 or len(holdout) < 20:
        raise ValueError("G6_SPLIT_INSUFFICIENT")
    calibration_boundary = train[int(len(train)*0.8)]["decision_ms"]
    fit, calibration = purged_split(train, calibration_boundary, protocol.embargo_ms)
    if len(fit) < 10 or len(calibration) < 5:
        raise ValueError("G6_CALIBRATION_INSUFFICIENT")
    center = [statistics.mean(r["features"][k] for r in fit) for k in FEATURES]
    scale = [max(1e-8, statistics.pstdev(r["features"][k] for r in fit)) for k in FEATURES]
    def vector(r):
        return [1.0] + [max(-10, min(10, (r["features"][k]-m)/s)) for k, m, s in zip(FEATURES, center, scale)]
    weights = [0.0]*(len(FEATURES)+1)
    vectors = [(vector(r), r["net_r"]) for r in fit]
    # Equal weight per overlap component, rather than per duplicated direction.
    group_sizes = {r["label_id"]: len(b) for b in dependence_blocks(fit) for r in b}
    norm = sum(1/group_sizes[r["label_id"]] for r in fit)
    for _ in range(epochs):
        grad = [0.0]*len(weights)
        for r, (x, y) in zip(fit, vectors):
            error = sum(w*v for w, v in zip(weights, x))-y
            for j, v in enumerate(x):
                grad[j] += error*v/group_sizes[r["label_id"]]
        weights = [w-0.01*(g/norm + (0.01*w if j else 0)) for j, (w, g) in enumerate(zip(weights, grad))]
    def predict(r):
        return sum(w*v for w, v in zip(weights, vector(r)))
    bias = statistics.mean(r["net_r"]-predict(r) for r in calibration)
    residuals = sorted(abs(r["net_r"]-(predict(r)+bias)) for r in calibration)
    uncertainty = residuals[min(len(residuals)-1, math.ceil(len(residuals)*0.95)-1)]
    scores = [(r, predict(r)+bias) for r in holdout]
    selected = [r for r, p in scores if p-uncertainty > 0]
    artifact = {"version": "NBOT_V5_EXPECTED_RETURN_RIDGE_V1", "grade": data["grade"],
                "features": FEATURES, "center": center, "scale": scale, "weights": weights,
                "calibration_bias": bias, "absolute_error_95": uncertainty,
                "dataset_sha256": data["dataset_sha256"], "protocol_sha256": digest(protocol.__dict__),
                "fit_labels_sha256": digest([r["label_id"] for r in fit]),
                "fit_cutoff_ms": max(r["settled_ms"] for r in fit), "holdout_start_ms": boundary_ms,
                "calibration_labels_sha256": digest([r["label_id"] for r in calibration]),
                "holdout_labels": [r["label_id"] for r in holdout],
                "holdout_mse": statistics.mean((p-r["net_r"])**2 for r, p in scores),
                "no_trade_mse": statistics.mean(r["net_r"]**2 for r in holdout),
                "simple_selector": portfolio_path(selector(holdout)),
                "model_selector": portfolio_path(selected), "epochs": epochs,
                "status": "CANDIDATE_REQUIRES_INDEPENDENT_HOLDOUT_REVIEW",
                "trading_eligible": False, "paper_authority": "NONE"}
    artifact["model_sha256"] = digest(artifact)
    return artifact


def infer(artifact, features):
    body = {k: v for k, v in artifact.items() if k != "model_sha256"}
    if digest(body) != artifact.get("model_sha256") or set(features) != set(FEATURES) or not all(finite(v) for v in features.values()):
        raise ValueError("G6_ARTIFACT_OR_FEATURE_INVALID")
    x = [1.0]+[max(-10, min(10, (features[k]-m)/s)) for k, m, s in zip(FEATURES, artifact["center"], artifact["scale"])]
    expected = sum(w*v for w, v in zip(artifact["weights"], x)) + artifact["calibration_bias"]
    lower = expected-artifact["absolute_error_95"]
    return {"expected_net_r": expected, "lower_net_r": lower,
            "action": "REVIEW_ONLY" if lower > 0 else "ABSTAIN", "paper_authority": "NONE"}
