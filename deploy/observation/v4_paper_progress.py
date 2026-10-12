#!/usr/bin/env python3
"""Read-only V4 paper-contest progress, open positions, outcomes and decisions.

Works even when no Champion exists, and for historical contests by ID.
No database initialization/migration, service restart, or order authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def utc(ms):
    if ms is None:
        return "-"
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def report(root: Path, *, contest_id: int | None = None, limit: int = 10) -> str:
    db = (root / "data/observation/v4/paper_contest.db").resolve()
    if not db.is_file():
        return "Paper-contest database missing; verify Observation repo directory."
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        history = conn.execute(
            "SELECT contest_id,mode,status,champion_generation,challenger_generation,"
            "checkpoint_trades,started_at_ms FROM contests ORDER BY contest_id DESC LIMIT 12"
        ).fetchall()
        if not history:
            return "No V4 paper contests recorded yet."
        target = (
            int(contest_id) if contest_id is not None
            else int(next((r for r in history if r["status"] in ("ACTIVE","REVIEW_REQUIRED")),
                          history[0])["contest_id"])
        )
        contest = conn.execute(
            "SELECT * FROM contests WHERE contest_id=?", (target,)
        ).fetchone()
        if contest is None:
            return f"No paper contest with ID {contest_id}."
        cid = int(contest["contest_id"])
        models = conn.execute(
            "SELECT * FROM contest_models WHERE contest_id=? ORDER BY generation", (cid,)
        ).fetchall()
        trades = conn.execute(
            "SELECT generation,symbol,side,status,entry_time_ms,exit_time_ms,net_r,exit_reason "
            "FROM paper_trades WHERE contest_id=? ORDER BY entry_time_ms DESC LIMIT ?",
            (cid, limit)
        ).fetchall()
        decisions = conn.execute(
            "SELECT generation,event_open_ms,action,reason,symbol,side,score "
            "FROM paper_decisions WHERE contest_id=? ORDER BY event_open_ms DESC,generation LIMIT ?",
            (cid, limit)
        ).fetchall()
        stats = {
            int(r["generation"]): r for r in conn.execute(
                "SELECT generation,COUNT(*) AS total,"
                "SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open_count,"
                "SUM(CASE WHEN status='UNSCORABLE' THEN 1 ELSE 0 END) AS unscorable,"
                "AVG(CASE WHEN status='CLOSED' THEN net_r END) AS mean_r,"
                "SUM(CASE WHEN status='CLOSED' AND side='LONG' THEN 1 ELSE 0 END) AS longs,"
                "SUM(CASE WHEN status='CLOSED' AND side='SHORT' THEN 1 ELSE 0 END) AS shorts "
                "FROM paper_trades WHERE contest_id=? GROUP BY generation", (cid,)
            )
        }
    lines = [
        "=== V4 PAPER CONTESTS (newest first) ===",
        *[
            f"#{r['contest_id']} {r['mode']} {r['status']} "
            f"champion={r['champion_generation'] or '-'} "
            f"challenger={r['challenger_generation']} target={r['checkpoint_trades']}"
            for r in history
        ],
        "",
        f"=== CONTEST #{cid}: {contest['mode']} / {contest['status']} ===",
        f"Started: {utc(contest['started_at_ms'])}",
        f"Champion: {contest['champion_generation'] or 'none'} | "
        f"Challenger: {contest['challenger_generation']} | "
        f"Scored trades needed per model: {contest['checkpoint_trades']}",
        f"Review decision: {contest['review_decision'] or '-'}",
        "",
        "=== MODEL PROGRESS ===",
    ]
    for m in models:
        g = int(m["generation"])
        n = int(m["completed_trades"])
        positive = int(m["positive_trades"])
        x = stats.get(g)
        lines.extend([
            f"Gen-{g} ({m['role']}, {m['status']}): "
            f"{n}/{contest['checkpoint_trades']} scored | "
            f"{positive}/{n} positive ({100 * positive / n:.1f}%)" if n else
            f"Gen-{g} ({m['role']}, {m['status']}): 0/{contest['checkpoint_trades']} scored",
            f"  Result {float(m['realized_r']):+.3f}R | "
            f"Mean {float(x['mean_r']):+.3f}R" if x and x["mean_r"] is not None
                else f"  Result {float(m['realized_r']):+.3f}R | Mean n/a",
            f"  Max realized drawdown {float(m['max_drawdown_r']):.3f}R | "
            f"Open {int(x['open_count'] or 0) if x else 0} | "
            f"Unscorable {int(x['unscorable'] or 0) if x else 0} | "
            f"Closed LONG {int(x['longs'] or 0) if x else 0}, "
            f"SHORT {int(x['shorts'] or 0) if x else 0}",
        ])
    lines.extend(["", f"=== LATEST {limit} PAPER TRADES (UTC) ==="])
    for t in trades:
        r = "-" if t["net_r"] is None else f"{float(t['net_r']):+.3f}R"
        lines.append(
            f"Gen-{t['generation']} {t['symbol']} {t['side']} {t['status']} "
            f"entry={utc(t['entry_time_ms'])} exit={utc(t['exit_time_ms'])} "
            f"result={r} reason={t['exit_reason'] or '-'}"
        )
    lines.extend(["", f"=== LATEST {limit} PAPER DECISIONS ==="])
    for d in decisions:
        score = "-" if d["score"] is None else f"{float(d['score']):+.4f}"
        lines.append(
            f"{utc(d['event_open_ms'])} Gen-{d['generation']} {d['action']} "
            f"{d['symbol'] or '-'} {d['side'] or '-'} rank_score={score} "
            f"reason={d['reason']}"
        )
    lines.append("\nRead-only paper data; no trading authority. Rank score is NOT predicted profit.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contest", type=int, help="Specific historical contest ID")
    parser.add_argument("--limit", type=int, default=10, help="Recent trades/decisions (1–100)")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if args.contest is not None and args.contest < 1:
        parser.error("--contest must be positive")
    print(report(Path(__file__).resolve().parents[2], contest_id=args.contest, limit=args.limit))


if __name__ == "__main__":
    main()
