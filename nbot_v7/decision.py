"""Reusable causal decision policy, shared by runtime and historical harness."""
import math


def score(brain, rows, kind):
    allowed=("review_ms","symbol","regime","features","source_hash") if kind=="watch" else (
        "decision_ms","symbol","side","family","regime","features","source_hash")
    causal=[{k:r[k] for k in allowed} for r in rows]
    predictions=brain.score(causal,kind)
    if len(predictions)!=len(rows) or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in predictions):
        raise ValueError("INVALID_BRAIN_OUTPUT_HOLD")
    return predictions


def watchlist(brain,rows,capacity=20):
    if not 1<=capacity<=20:
        raise ValueError("WATCH_CAPACITY_OUTSIDE_RISK_ENVELOPE")
    predictions=score(brain,rows,"watch")
    ranked=sorted(zip(rows,predictions),key=lambda item:(-item[1][1],-item[1][0],item[0]["symbol"]))
    return [r["symbol"] for r,p in ranked if p[0]>0][:capacity],predictions


def choose(brain,rows):
    predictions=score(brain,rows,"opportunity")
    viable=[(r,p) for r,p in zip(rows,predictions) if p[0]>0]
    chosen=max(viable,key=lambda item:(item[1][1],item[1][0],item[0]["symbol"])) if viable else None
    return chosen,predictions
