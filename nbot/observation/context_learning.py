"""Small, causal setup calibration; no external ML runtime or exchange access.

Each sample is an event mean, not a collection of allegedly independent coins.
Training events have disjoint four-hour label paths. The finite rolling window
lets setup reliability change without discarding the long-history ridge model.
"""
from __future__ import annotations

import json
import math
import statistics

VERSION = "CONTEXT_SETUP_CALIBRATION_V1"
SELECTOR_VERSION = "CONTEXT_CALIBRATED_RIDGE_V1"
WINDOW_MS = 20 * 24 * 60 * 60 * 1000
SPACING_MS = 49 * 300_000
MIN_EVENTS = 8
SETUPS = ("TREND_CONTINUATION", "TREND_PULLBACK", "STRETCHED_REVERSAL",
          "VOLATILITY_EXPANSION", "RELATIVE_STRENGTH", "UNCLASSIFIED")


def describe(vector):
    """Fixed observable proxies, never a claim to recognize all chart patterns."""
    values = {str(k): float(v) for k, v in vector.items()}
    if not all(math.isfinite(v) for v in values.values()):
        raise ValueError("CONTEXT_NONFINITE_FEATURE")
    get = lambda name: values.get(name, 0.0)
    atr = max(get("atr14_frac"), 1e-6)
    trend = get("ret_4h_side") / atr
    recent = get("ret_15m_side") / atr
    breadth = get("breadth_1h_side")
    market = "ALIGNED" if breadth > .3 else "OPPOSED" if breadth < -.3 else "MIXED"
    vol = get("volatility_percentile")
    volatility = "HIGH" if vol >= .75 else "LOW" if vol <= .25 else "NORMAL"
    if trend > 1 and recent < -.25:
        setup = "TREND_PULLBACK"
    elif trend < -2 and recent > .25:
        setup = "STRETCHED_REVERSAL"
    elif get("range_frac") / atr > 1.5 and get("ret_5m_side") > 0:
        setup = "VOLATILITY_EXPANSION"
    elif trend > 1 and recent > 0:
        setup = "TREND_CONTINUATION"
    elif get("ret_1h_percentile_side") > .6:
        setup = "RELATIVE_STRENGTH"
    else:
        setup = "UNCLASSIFIED"
    return {"setup": setup, "market_alignment": market, "volatility": volatility,
            "context": market + ":" + volatility}


def train(records, *, cutoff_ms):
    groups = {}
    count = 0
    previous = None
    first = None
    for record in records:
        event = int(record["event_open_ms"])
        if event > cutoff_ms or event <= cutoff_ms - WINDOW_MS:
            raise ValueError("CONTEXT_TRAINING_WINDOW_INVALID")
        if previous is not None and event - previous < SPACING_MS:
            raise ValueError("CONTEXT_LABEL_PATHS_OVERLAP")
        previous = event
        first = event if first is None else first
        count += 1
        per_event = {}
        for row in record["examples"]:
            vector = json.loads(row["feature_vector_json"])
            info = describe(vector)
            target = float(row["target_net_r"])
            if not math.isfinite(target):
                raise ValueError("CONTEXT_NONFINITE_TARGET")
            if vector.get("missing_ret_4h") or vector.get("missing_vol_4h"):
                continue
            # Record one event-level mean per group. Extra symbols never
            # increase the independent support count for the same event.
            for key in (info["setup"] + "|ALL", info["setup"] + "|" + info["context"]):
                per_event.setdefault(key, []).append(target)
        for key, values in per_event.items():
            groups.setdefault(key, []).append(statistics.fmean(values))
    summary = {}
    for key, values in sorted(groups.items()):
        n = len(values)
        mean = statistics.fmean(values)
        variance = statistics.variance(values) if n > 1 else 0.0
        summary[key] = {"events": n, "mean_net_r": mean, "variance": variance,
                        "cautious_net_r": mean - 2 * math.sqrt(variance / n)}
    return {"version": VERSION, "cutoff_ms": cutoff_ms, "window_ms": WINDOW_MS,
            "spacing_ms": SPACING_MS, "min_events": MIN_EVENTS,
            "sample_unit": "DISJOINT_EVENT_MEAN_NOT_SYMBOL_COUNT",
            "first_event_ms": first, "last_event_ms": previous,
            "independent_events": count, "groups": summary}


def adjustment(calibration, vector, ridge_score):
    if (calibration.get("version") != VERSION or calibration.get("min_events") != MIN_EVENTS
            or calibration.get("window_ms") != WINDOW_MS or calibration.get("spacing_ms") != SPACING_MS):
        raise ValueError("CONTEXT_CONTRACT_INVALID")
    info = describe(vector)
    evidence = None
    source = None
    for key in (info["setup"] + "|" + info["context"], info["setup"] + "|ALL"):
        candidate = calibration["groups"].get(key)
        if candidate is None:
            continue
        n = candidate["events"]
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("CONTEXT_COUNT_INVALID")
        if not all(math.isfinite(float(candidate[k])) for k in ("mean_net_r", "variance", "cautious_net_r")) or candidate["variance"] < 0:
            raise ValueError("CONTEXT_STATISTICS_INVALID")
        if n >= MIN_EVENTS:
            evidence, source = candidate, key
            break
    score = float(ridge_score)
    if not math.isfinite(score):
        raise ValueError("CONTEXT_SCORE_INVALID")
    # An optimistic setup estimate cannot manufacture an entry rejected by
    # ridge. Supported weak setups can lower its ranking or veto it entirely.
    if evidence is not None:
        score = min(score, (score + evidence["cautious_net_r"]) / 2)
        if evidence["cautious_net_r"] <= 0:
            score = min(score, 0.0)
    return {**info, "ridge_score": ridge_score, "adjusted_score": score,
            "evidence_group": source, "support_events": 0 if evidence is None else evidence["events"],
            "status": "INSUFFICIENT_SETUP_EVIDENCE_USING_RIDGE" if evidence is None else "SETUP_CALIBRATED",
            "note": "Two-standard-error caution margin, not a calibrated probability of profit."}


GATE_EXPLANATIONS = {
    "minimum_trade_events": "Too few simulated trades to judge this model.",
    "candidate_positive_expectancy_ci": "Positive average results are not supported strongly enough by this test.",
    "meaningful_lift_vs_frozen_benchmark_ci": "The model has not convincingly beaten the comparison strategy.",
    "ordered_top_middle_bottom": "Higher predictions did not reliably rank better outcomes.",
    "two_x_base_cost_stress_positive": "Results did not remain positive with doubled base trading costs.",
    "drawdown_not_worse_than_benchmark": "The model suffered a larger simulated drawdown than the comparison strategy.",
    "both_test_halves_positive": "Results were not positive in both halves of the test.",
    "not_dependent_on_most_selected_symbol": "Results depended too heavily on the most selected coin.",
    "no_catastrophic_covered_regime": "A sufficiently sampled market condition had severe losses.",
    "winner_capture_not_systematically_poor": "Winning trades captured too little of the available favorable movement.",
}


def explain_gates(gates):
    return [{"check": name, "explanation": GATE_EXPLANATIONS.get(name, "A data-integrity or authority check failed; investigate before use.")}
            for name, passed in gates.items() if not passed]
