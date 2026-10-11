"""Versioned, fail-closed paper Champion gates. No exchange authority."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import hashlib
import json
import math
import sqlite3
from typing import Any

POLICY = {
    "version": "NBOT_V4_PAPER_PROMOTION_V1",
    "checkpoint_trades": 100,
    "min_elapsed_hours": 72,
    "min_utc_days": 3,
    "block_hours": 4,
    "min_blocks": 6,
    "min_side_trades": 20,
    "min_mean_net_r": 0.10,
    "min_positive_rate": 0.50,
    "max_drawdown_r": 10.0,
    "min_worst_net_r": -3.0,
    "max_unscorable_fraction": 0.20,
    "min_volatility_regimes": 2,
    "min_regime_trades": 10,
    "min_lift_mean_r": 0.10,
}
DAY_MS = 86_400_000
BLOCK_MS = 4 * 3_600_000


@contextmanager
def connect(*args, **kwargs):
    """Commit/rollback and close: Connection.__exit__ alone does not close."""
    conn = sqlite3.connect(*args, **kwargs)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def rows(conn: sqlite3.Connection, sql: str, args=()) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, args)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _verified_trades(trades, record, admission, ledger, contest, now_ms):
    artifact = json.loads(record["artifact_json"])
    body = {k: v for k, v in artifact.items() if k != "model_digest"}
    generation = admission["generation"]
    if (hashlib.sha256(record["artifact_json"].encode()).hexdigest() != record["artifact_digest"]
            or digest(body) != artifact.get("model_digest")
            or artifact.get("model_digest") != admission["model_digest"]
            or artifact.get("order_authority") != "NONE"
            or record["qualification_status"] != admission["qualification"]
            or record["qualification_status"] not in {"BASELINE_READY", "CHALLENGER_READY"}
            or (record["qualification_status"] == "BASELINE_READY" and generation != 1)):
        raise ValueError("FROZEN_MODEL_PROOF_INVALID")
    verified = []
    for trade in trades:
        if trade["status"] != "CLOSED":
            continue
        decision = rows(ledger, "SELECT * FROM frozen_decisions WHERE decision_id=?",
                        (trade["decision_id"],))
        outcomes = rows(ledger, "SELECT * FROM matured_outcomes WHERE decision_id=? AND actual_execution=0",
                        (trade["decision_id"],))
        if len(decision) != 1 or len(outcomes) != 1:
            raise ValueError("SCORED_LEDGER_PROOF_MISSING")
        d, o = decision[0], outcomes[0]
        dp, op = json.loads(d["payload_json"]), json.loads(o["payload_json"])
        extra = dp.get("extras", {})
        if (digest(dp) != d["digest"] or digest(op) != o["digest"]
                or o["quality"] != "AGGTRADE_RESOLVED" or op.get("quality") != o["quality"]
                or op.get("actual_execution") is not False
                or dp.get("decision_id") != trade["decision_id"]
                or dp.get("model_id") != f"V4_MODEL_GEN_{generation:03d}"
                or dp.get("approved") is not True
                or dp.get("policy_id") != "TICK_INTEGER_R_V1"
                or extra.get("v4_paper_contract") != "NBOT_V4_PAPER_CONTEST_V1"
                or digest(extra.get("feature_vector")) != dp.get("feature_digest")
                or op.get("decision_id") != trade["decision_id"]
                or dp.get("symbol") != trade["symbol"] or dp.get("side") != trade["side"]
                or extra.get("contest_id") != contest["contest_id"]
                or extra.get("generation") != generation
                or extra.get("model_digest") != artifact["model_digest"]
                or extra.get("order_authority") != "NONE"
                or dp.get("decision_time_ms") != trade["entry_time_ms"]
                or op.get("net_r") != trade["net_r"]
                or op.get("exit_reason") != trade["exit_reason"]
                or op.get("source_digest") != trade["source_digest"]
                or not trade["source_digest"]
                or op.get("evidence", {}).get("exit_time_ms") != trade["exit_time_ms"]
                or d["policy_id"] != o["policy_id"] or op.get("policy_id") != d["policy_id"]
                or ledger.execute("SELECT 1 FROM unresolved_outcomes WHERE decision_id=?",
                                  (trade["decision_id"],)).fetchone()):
            raise ValueError("SCORED_LEDGER_PROOF_INVALID")
        entry, exit_ms, net_r = trade["entry_time_ms"], trade["exit_time_ms"], trade["net_r"]
        if (trade["side"] not in {"LONG", "SHORT"} or not math.isfinite(float(net_r))
                or exit_ms is None or not contest["started_at_ms"] <= entry <= exit_ms <= now_ms
                or not artifact["trained_at_ms"] <= entry
                or not 0 < float(trade["one_r_price"]) < float(trade["entry_price"])):
            raise ValueError("SCORED_CHRONOLOGY_INVALID")
        vector = extra.get("feature_vector", {})
        vol = float(vector["volatility_percentile"])
        if not math.isfinite(vol) or not 0 <= vol <= 1:
            raise ValueError("REGIME_EVIDENCE_INVALID")
        regime = "LOW" if vol <= .25 else "HIGH" if vol >= .75 else "NORMAL"
        verified.append({**trade, "volatility_regime": regime})
    ordered = sorted(verified, key=lambda t: (t["entry_time_ms"], t["decision_id"]))
    if any(a["exit_time_ms"] > b["entry_time_ms"] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("PAPER_POSITIONS_OVERLAP")
    return ordered


def _metrics(trades, unscorable):
    values = [float(t["net_r"]) for t in trades]
    blocks, regimes = defaultdict(list), defaultdict(list)
    for t in trades:
        blocks[t["entry_time_ms"] // BLOCK_MS].append(float(t["net_r"]))
        regimes[t["volatility_regime"]].append(float(t["net_r"]))
    realized = peak = drawdown = 0.0
    for t in sorted(trades, key=lambda t: (t["exit_time_ms"], t["decision_id"])):
        realized += float(t["net_r"])
        peak = max(peak, realized)
        drawdown = max(drawdown, peak - realized)
    block_totals = {str(k): sum(v) for k, v in blocks.items()}
    best = max(blocks, key=lambda k: sum(blocks[k])) if blocks else None
    remaining = [r for k, vals in blocks.items() if k != best for r in vals]
    halves = (values[:len(values)//2], values[len(values)//2:])
    return {
        "completed_trades": len(values), "realized_r": sum(values),
        "mean_net_r": sum(values)/len(values) if values else None,
        "positive_rate": sum(r > 0 for r in values)/len(values) if values else 0,
        "max_drawdown_r": drawdown, "worst_net_r": min(values) if values else None,
        "elapsed_hours": (max(t["exit_time_ms"] for t in trades)-min(t["entry_time_ms"] for t in trades))/3_600_000 if trades else 0,
        "utc_days": len({t["entry_time_ms"]//DAY_MS for t in trades}),
        "block_count": len(blocks), "block_net_r": block_totals,
        "positive_block_fraction": sum(v > 0 for v in block_totals.values())/len(blocks) if blocks else 0,
        "without_best_block_mean_r": sum(remaining)/len(remaining) if remaining else None,
        "half_mean_r": [sum(v)/len(v) if v else None for v in halves],
        "sides": {side: {"trades": len(v := [float(t["net_r"]) for t in trades if t["side"] == side]),
                         "mean_net_r": sum(v)/len(v) if v else None} for side in ("LONG", "SHORT")},
        "regimes": {k: {"trades": len(v), "mean_net_r": sum(v)/len(v)} for k, v in regimes.items()},
        "unscorable_trades": unscorable,
        "unscorable_fraction": unscorable/(len(values)+unscorable) if values or unscorable else 0,
    }


def promotion_report(contest_conn, generation_conn, ledger_conn, *, now_ms):
    """Recompute from immutable evidence; never trust cached status counters."""
    contests = rows(contest_conn, "SELECT * FROM contests WHERE status IN ('ACTIVE','REVIEW_REQUIRED') ORDER BY contest_id DESC LIMIT 1")
    report = {"policy": dict(POLICY), "eligible": False, "failed_checks": [], "models": {},
              "order_authority": "NONE", "automatic_promotion": False, "evaluated_at_ms": now_ms}
    if not contests:
        report["failed_checks"] = ["NO_ACTIVE_CONTEST"]
        return report
    contest = contests[0]
    report["contest_id"] = contest["contest_id"]
    report["mode"] = contest["mode"]
    failed = report["failed_checks"]
    if contest["status"] != "REVIEW_REQUIRED":
        failed.append("CHECKPOINT_NOT_REVIEW_READY")
    champ, challenger = contest["champion_generation"], contest["challenger_generation"]
    expected = {challenger: "CHALLENGER"}
    if champ is not None:
        expected[champ] = "CHAMPION"
    state = dict(generation_conn.execute("SELECT key,value FROM state"))
    if (state.get("champion_generation") != (None if champ is None else str(champ))
            or state.get("challenger_generation") != str(challenger)
            or contest["mode"] != ("BASELINE_EXAM" if champ is None else "HEAD_TO_HEAD")
            or len(expected) != (1 if champ is None else 2)):
        failed.append("CONTEST_GENERATION_STATE_CHANGED")
    model_rows = rows(contest_conn, "SELECT * FROM contest_models WHERE contest_id=?", (contest["contest_id"],))
    if {m["generation"]: m["role"] for m in model_rows} != expected:
        failed.append("CONTEST_MODEL_ROLES_INVALID")
    all_trades = rows(contest_conn, "SELECT * FROM paper_trades WHERE contest_id=? ORDER BY entry_time_ms,decision_id", (contest["contest_id"],))
    if any(t["status"] == "OPEN" for t in all_trades):
        failed.append("OPEN_PAPER_POSITIONS")
    if any(t["generation"] not in expected or t["status"] not in {"OPEN", "CLOSED", "UNSCORABLE"} for t in all_trades):
        failed.append("PAPER_TRADE_STATE_INVALID")
    evidence_digests = {}
    for generation, role in expected.items():
        try:
            record = rows(generation_conn, "SELECT * FROM generations WHERE generation=?", (generation,))[0]
            admission = rows(contest_conn, "SELECT * FROM paper_models WHERE generation=?", (generation,))[0]
            trades = [t for t in all_trades if t["generation"] == generation]
            verified = _verified_trades(trades, record, admission, ledger_conn, contest, now_ms)
            m = _metrics(verified, sum(t["status"] == "UNSCORABLE" for t in trades))
            report["models"][str(generation)] = m
            evidence_digests[str(generation)] = {"artifact_digest": record["artifact_digest"], "trades_digest": digest(verified)}
            cached = next(r for r in model_rows if r["generation"] == generation)
            if (cached["completed_trades"] != m["completed_trades"]
                    or cached["positive_trades"] != sum(t["net_r"] > 0 for t in verified)
                    or not math.isclose(cached["realized_r"], m["realized_r"], abs_tol=1e-8)
                    or not math.isclose(cached["max_drawdown_r"], m["max_drawdown_r"], abs_tol=1e-8)):
                failed.append(f"{role}:CACHED_COUNTERS_MISMATCH")
            if m["completed_trades"] != POLICY["checkpoint_trades"]:
                failed.append(f"{role}:NEEDS_100_SCORED_TRADES")
            if role != "CHALLENGER":
                continue
            gates = {
                "POSITIVE_EXPECTANCY": m["mean_net_r"] is not None and m["mean_net_r"] >= POLICY["min_mean_net_r"],
                "POSITIVE_RATE": m["positive_rate"] >= POLICY["min_positive_rate"],
                "DRAWDOWN_LIMIT": m["max_drawdown_r"] <= POLICY["max_drawdown_r"],
                "TAIL_LOSS_LIMIT": m["worst_net_r"] is not None and m["worst_net_r"] >= POLICY["min_worst_net_r"],
                "FUTURE_TIME_COVERAGE": m["elapsed_hours"] >= POLICY["min_elapsed_hours"] and m["utc_days"] >= POLICY["min_utc_days"],
                "TIME_BLOCK_SUPPORT": m["block_count"] >= POLICY["min_blocks"] and m["positive_block_fraction"] >= .50,
                "NOT_ONE_LUCKY_BLOCK": m["without_best_block_mean_r"] is not None and m["without_best_block_mean_r"] > 0,
                "BOTH_HALVES_POSITIVE": all(v is not None and v > 0 for v in m["half_mean_r"]),
                "SIDE_SUPPORT": all(s["trades"] >= POLICY["min_side_trades"] and s["mean_net_r"] is not None and s["mean_net_r"] > 0 for s in m["sides"].values()),
                "REGIME_SUPPORT": sum(r["trades"] >= POLICY["min_regime_trades"] for r in m["regimes"].values()) >= POLICY["min_volatility_regimes"] and all(r["mean_net_r"] > 0 for r in m["regimes"].values() if r["trades"] >= POLICY["min_regime_trades"]),
                "CONTINUITY_SUPPORT": m["unscorable_fraction"] <= POLICY["max_unscorable_fraction"],
            }
            failed.extend(f"{role}:{name}" for name, ok in gates.items() if not ok)
        except (ValueError, TypeError, KeyError, IndexError, StopIteration, sqlite3.Error, OverflowError) as exc:
            failed.append(f"{role}:EVIDENCE_INVALID:{type(exc).__name__}")
    if champ is not None and all(str(g) in report["models"] for g in (champ, challenger)):
        c, b = report["models"][str(challenger)], report["models"][str(champ)]
        if c["mean_net_r"] is None or b["mean_net_r"] is None or c["mean_net_r"]-b["mean_net_r"] < POLICY["min_lift_mean_r"]-1e-12:
            failed.append("CHALLENGER:INSUFFICIENT_LIFT")
        if c["max_drawdown_r"] > b["max_drawdown_r"]+1e-12 or c["worst_net_r"] is None or b["worst_net_r"] is None or c["worst_net_r"] < b["worst_net_r"]-1e-12:
            failed.append("CHALLENGER:RISK_WORSE_THAN_CHAMPION")
        common = set(c["block_net_r"]) & set(b["block_net_r"])
        if len(common) < POLICY["min_blocks"]:
            failed.append("CHALLENGER:INSUFFICIENT_SHARED_TIME_BLOCKS")
        differences = [c["block_net_r"].get(k, 0)-b["block_net_r"].get(k, 0)
                       for k in set(c["block_net_r"]) | set(b["block_net_r"])]
        if not differences or sum(differences)-max(differences) <= 0:
            failed.append("CHALLENGER:LIFT_DEPENDS_ON_ONE_BLOCK")
    report["evidence"] = evidence_digests
    report["eligible"] = not failed
    return report
