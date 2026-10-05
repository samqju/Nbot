"""Read-only report of settled paper trades and their prior predictions."""
from contextlib import closing
from collections import defaultdict
from datetime import datetime, timezone
import sqlite3
import statistics
from .paper_feedback import DAY_MS, VERSION, _verified
from .candidate_setups import REGISTRY, FALLBACK


def paper_learning_report(database, *, release_sha, now_ms):
    lines = ["# Paper auto-learning progress", "",
             "Paper only. No automatic mainnet approval or profitability claim.",
             "Results include simulated fees; funding and real fills/slippage are not fully modelled.", ""]
    if not database.path.is_file():
        return "\n".join(lines + ["No paper database yet."]) + "\n"
    with closing(sqlite3.connect(database.path.resolve().as_uri()+"?mode=ro", uri=True, timeout=2)) as conn:
        conn.execute("BEGIN")
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='paper_feedback_samples'").fetchone():
            return "\n".join(lines + ["No feedback history yet. Start learned live-paper mode."]) + "\n"
        start, decisions = conn.execute("SELECT MIN(decision_ms),COUNT(*) FROM paper_feedback_decisions WHERE release_sha=?", (release_sha,)).fetchone()
        rows = conn.execute("""SELECT sample_json,sample_digest FROM paper_feedback_samples
            WHERE release_sha=? AND available_ms<? ORDER BY closed_ms DESC,outcome_id DESC LIMIT 10001""",
            (release_sha, now_ms)).fetchall()
        samples = sorted([_verified(*r) for r in rows[:10000]], key=lambda s:(s["closed_ms"],s["outcome_id"]))
        row = conn.execute("""SELECT model_json,model_digest FROM paper_feedback_models
            WHERE release_sha=? AND cutoff_ms<? ORDER BY cutoff_ms DESC,model_id DESC LIMIT 1""", (release_sha,now_ms)).fetchone()
        model = _verified(*row) if row else None
        versions = conn.execute("SELECT COUNT(*) FROM paper_feedback_models WHERE release_sha=?", (release_sha,)).fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM paper_feedback_rejections").fetchone()[0]
        check_rows = []
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='paper_feedback_checks'").fetchone():
            check_rows = conn.execute("""SELECT detail_json FROM paper_feedback_checks
                WHERE release_sha=? AND decision_ms<? ORDER BY decision_ms DESC LIMIT 10001""",
                (release_sha, now_ms)).fetchall()
    lines += [f"Algorithm: {VERSION}", f"Release/cohort: {release_sha}",
              f"Recorded recommendation decisions: {decisions} (not all become trades)",
              f"Completed eligible paper trades: {len(samples)}",
              f"Stored feedback snapshots: {versions} (not proof of improvement)",
              f"Excluded or invalid outcomes across all cohorts: {rejected}"]
    if len(rows) > 10000:
        lines += ["Report limited to the latest 10,000 completed trades."]
    if start is not None:
        days = max(0.,(now_ms-start)/DAY_MS)
        lines += [f"Days since first recommendation: {days:.1f} / 30",
                  "30 days reached: review the evidence; do not auto-promote." if days >= 30 else "30-day observation period still running."]
    else:
        lines += ["Waiting for the first eligible recommendation; check base learner and control health."]
    checks = []
    for row in check_rows[:10000]:
        try:
            value = __import__("json").loads(row[0])
            if isinstance(value, dict):
                checks.append(value)
        except (TypeError, ValueError):
            continue
    lines += ["", "## Frozen baseline decision audit", ""]
    if checks:
        changed = sum(bool(c.get("choice_changed")) for c in checks)
        abstained = sum(bool(c.get("no_trade")) for c in checks)
        baseline_positive = sum(float((c.get("baseline") or {}).get("score") or 0) > 0 for c in checks)
        selected_positive = sum(float((c.get("selected") or {}).get("score") or 0) > 0 for c in checks)
        lines += [
            f"Comparable market decisions: {len(checks)}",
            f"Adaptive choice differed from frozen base ranking: {changed} / {len(checks)}",
            f"Adaptive no-trade decisions: {abstained}",
            f"Frozen baseline positive opportunities: {baseline_positive}",
            f"Adaptive positive selections: {selected_positive}",
            "This is a causal selection audit, not counterfactual PnL: an unchosen baseline is not treated as a win or loss.",
        ]
    else:
        lines += ["No comparable decision checks recorded yet."]
    if len(check_rows) > 10000:
        lines += ["Decision audit limited to the latest 10,000 checks."]

    if samples:
        equity = peak = drawdown = 0.
        for sample in samples:
            equity += sample["net_usd"]
            peak = max(peak,equity)
            drawdown = max(drawdown,peak-equity)
        predicted = [s for s in samples if s["predicted_r"] is not None]
        lines += ["", f"After-fee paper PnL: USD {equity:.4f}",
                  f"Closed-trade drawdown: USD {drawdown:.4f} (excludes intratrade drawdown)",
                  f"Winning trades: {sum(s['net_usd']>0 for s in samples)} / {len(samples)}",
                  f"Executed choices changed by feedback: {sum(bool(s['ranking_changed']) for s in samples)}",
                  f"Completed trades with a prediction made before entry: {len(predicted)}"]
        if predicted:
            error = statistics.fmean(abs(s["predicted_r"]-s["learning_r"]) for s in predicted)
            zero = statistics.fmean(abs(s["learning_r"]) for s in predicted)
            lines += [f"Before-entry prediction MAE on clipped paper R: {error:.4f}",
                      f"Always-predict-zero MAE on the SAME trades: {zero:.4f}",
                      "Smaller error is better; neither metric proves profitable selection."]
        if len(predicted) < 20:
            lines += ["INSUFFICIENT forward prediction evidence: fewer than 20 scored completed trades."]
        groups = defaultdict(list)
        for sample in samples:
            week = datetime.fromtimestamp(sample["closed_ms"]/1000, timezone.utc).strftime("%G-W%V")
            groups[week].append(sample)
        lines += ["", "| UTC week | Trades | Paper PnL USD | Mean actual R |", "|---|---:|---:|---:|"]
        for week, items in sorted(groups.items()):
            lines += [f"| {week} | {len(items)} | {sum(s['net_usd'] for s in items):.4f} | {statistics.fmean(s['net_r'] for s in items):.4f} |"]
    else:
        lines += ["", "No completed eligible paper trades yet: no execution feedback is available."]
    lines += ["", "## Candidate results", "",
              "Each completed trade belongs to ONE selected candidate. Matching rules are not extra trades.",
              "Zero trades means untested here, not unsuccessful. These are experimental rules, not proven strategies.",
              "", "| Candidate | Family | Completed trades | Paper PnL USD |",
              "|---|---|---:|---:|"]
    for candidate in [item.tag() for item in REGISTRY] + [FALLBACK]:
        items = [sample for sample in samples if sample.get("candidate_id", "MODEL_ONLY") == candidate["id"]]
        lines += [f"| {candidate['id']} | {candidate['family']} | {len(items)} | {sum(s['net_usd'] for s in items):.4f} |"]
    if model:
        lines += ["", "## Current setup weights", "", f"Snapshot: {model['model_id']}",
                  f"Compatible main paper outcomes used: {model['sample_count']}",
                  f"Compatible shadow outcomes used at reduced weight: {model.get('shadow_sample_count',0)}",
                  f"Active loss pauses at this snapshot: {len(model.get('cooldowns',{}))}",
                  f"Training cap reached: {model['sample_cap_reached']}",
                  "1.0 = unchanged; below 1.0 = downranked; above 1.0 = increased preference.",
                  "Sparse supported evidence is shrunk toward neutral before it can move ranking.",
                  "Time buckets reduce repeated-trade influence; they do not guarantee independence.",
                  "", "| Setup / market / direction | Trades | Buckets | Effective buckets | Raw mean R | Shrunk mean R | Shrinkage | Weight |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for key, group in sorted(model["groups"].items()):
            label = key.replace("|", " / ")
            raw_mean = group.get("raw_mean_clipped_r", group["mean_clipped_r"])
            shrinkage = group.get("shrinkage_factor", 1.0)
            lines += [f"| {label} | {group['trades']} | {group['buckets']} | {group['effective_buckets']:.1f} | {raw_mean:.3f} | {group['mean_clipped_r']:.3f} | {shrinkage:.3f} | {group['factor']:.3f} |"]
        if not any(g["supported"] for g in model["groups"].values()):
            lines += ["Insufficient supported outcome evidence; separate loss pauses or entry-practicality penalties may still apply."]
    lines += ["", "## Review notes", "",
              "Check growing trade counts, supported weight changes, prediction error, weekly PnL and drawdown.",
              "Only executed trades have execution outcomes. Unchosen opportunities are not labelled wins or losses.",
              "Frozen baseline choices are now recorded and summarized causally, but unchosen alternatives still do not receive invented PnL.",
              "This learner adapts supported setups; it does not invent strategy code.",
              "Back up the Observation database, research memory and Execution history off the VPS."]
    return "\n".join(lines) + "\n"
