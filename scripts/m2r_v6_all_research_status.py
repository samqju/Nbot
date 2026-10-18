#!/usr/bin/env python3
"""Read-only NBOT V6 research progress across all three VPS stages.

Does not start, stop, retry, signal, train or trade. Requires only Python3
standard library and the already written VPS audit/event/status artifacts.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

ROOT = Path("/root/nbot-v6-m1-20261016")
LIB = ROOT / "library-20261018"
P2 = LIB / "profit-protection-next-phase"
P3 = ROOT / "global-25x8-20261018"
SERVICE = (
    ("1. Eight-strategy study", "nbot-v6-library-20261018"),
    ("2. Profit protection", "nbot-v6-profit-protection-next-20261018"),
    ("3. Global AI (25x8)", "nbot-v6-global-20261018"),
)
PLANNED = (
    ("Original No-ML baseline", "baseline/", 3),
    ("8-strategy native backtests", "native/", 24),
    ("Original trailing comparisons", "trailing/", 24),
    ("Hyperopt training", "hyperopt/", 8),
    ("LightGBM diagnostics", "lgbm/", 2),
    ("8h adaptive regime test", "adaptive/", 1),
    ("PPO reinforcement learning", "rl/", 1),
)


def run(*args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       text=True, check=False, timeout=8)
    return p.stdout.strip()


def safe_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return {}


def rows(path):
    if not path.exists():
        return []
    events = []
    try:
        with path.open() as src:
            for line in src:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return events


def main():
    print("=" * 58)
    print("       NBOT V6 — ALL RESEARCH STATUS (READ ONLY)")
    print("=" * 58)
    print("Checked: ", datetime.now(timezone.utc).astimezone(
        ZoneInfo("Asia/Kolkata")).strftime("%d %B %Y, %I:%M:%S %p IST"))
    print()
    print("SERVICE HEALTH")
    for label, service in SERVICE:
        state = run("systemctl", "is-active", service + ".service") or "unknown"
        print(f"  {label}: {state.upper()}")
    print("  Running Docker containers:", len(run("docker", "ps", "-q").splitlines()))
    print()

    print("STAGE 1 — ORIGINAL EIGHT-STRATEGY RESEARCH")
    one = safe_json(LIB / "v6-library-research-status.json")
    entries = rows(LIB / "v6-library-research-events.jsonl")
    finished = {str(x.get("key", "")) for x in entries if x.get("stage") == "complete"}
    failures = {str(x.get("key", "")) for x in entries if x.get("stage") == "error"}
    successes = 0
    alljobs = 0
    for label, prefix, total in PLANNED:
        if prefix in ("baseline/", "native/", "trailing/"):
            # A previously audited job can be RESUMED without a new 'complete'
            # event. The actual native ZIP + economic audit is authoritative.
            kind = prefix.rstrip("/")
            valid = []
            for proof in (LIB / kind).glob("*/*/native-economic-audit.json"):
                obj = safe_json(proof)
                archive = proof.parent / "backtest_results" / str(obj.get("archive_name", ""))
                if (obj.get("kind") == kind
                    and obj.get("trade_count_and_native_cost_audit_passed") is True
                    and archive.is_file()):
                    valid.append((obj.get("family"), obj.get("period")))
            good = len(set(valid))
        else:
            good = sum(key.startswith(prefix) for key in finished)
        bad = sum(key.startswith(prefix) for key in failures)
        successes += good
        alljobs += total
        print(f"  {label:<32} {good:>2}/{total:<2} ({good * 100 / total:>5.1f}%)"
              + (f"  failed/skipped={bad}" if bad else ""))
    print(f"  TOTAL SUCCESSFUL: {successes}/{alljobs}"
          f" ({successes * 100 / alljobs:.1f}%)")
    print("  Batch status:", one.get("status", "not started"))
    print("  Economic audit archives:",
          one.get("economic_audit_count", "pending"))
    print()

    print("STAGE 2 — PROFIT PROTECTION (120 NATIVE EXIT TESTS)")
    two = safe_json(P2 / "status.json")
    complete_p2 = {str(x.get("name", "")) for x in rows(P2 / "events.jsonl")
                   if x.get("stage") == "complete"}
    done2 = min(120, max(len(complete_p2), int(two.get(
        "new_native_archive_count", 0) or 0)))
    print(f"  Completed: {done2}/120 ({done2 / 120 * 100:.1f}%)")
    print("  Batch status:", two.get("status", "NOT STARTED / QUEUE BLOCKED"))
    print()

    print("STAGE 3 — GLOBAL AI RANKING (12 JOBS)")
    three = safe_json(P3 / "progress.json")
    completed = int(three.get("jobs_completed", 0) or 0)
    total = int(three.get("jobs_total", 12) or 12)
    print(f"  Completed: {completed}/{total} ({completed / total * 100:.1f}%)")
    print("  Batch status:", three.get("status", "NOT STARTED / QUEUE BLOCKED"))
    print()

    if failures or any(run("systemctl", "is-failed", s + ".service") == "failed"
                       for _, s in SERVICE):
        print("ATTENTION: Unfinished/failed experiments need controlled recovery.")
        print("  No results should be overwritten or automatically promoted.")
    print("Paper trading: OFF    Live trading: OFF")
    print("=" * 58)


if __name__ == "__main__":
    main()
