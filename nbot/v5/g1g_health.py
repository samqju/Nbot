"""G1g read-only production observer health audit. No modifications/orders.

The check reads systemd state and V5 SQLite using SQLite URI mode=ro.
It never stops/starts services, deletes data, accesses secrets, trains or trades.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import time

from nbot.v5.g1f_preflight import LEGACY_UNITS

OLD_ENABLED_UNITS = (
    "nbot-observation-live.service",
    "nbot-v4-research.service",
    "nbot-v4-paper-contest.service",
    "nbot-v4-training.timer",
    "nbot-observer.target",
)
SERVICE = "nbot-v5-observation-only.service"
MAX_STALE_MIN = 20
MAX_MEMORY_BYTES = 200 * 1024 * 1024


class HealthHold(ValueError):
    pass


def run_systemctl(args, *, runner=subprocess.run) -> str:
    result = runner(
        ["systemctl", *args], capture_output=True, text=True, timeout=12,
    )
    if result.returncode not in (0, 1, 3):
        raise HealthHold("G1G_SYSTEMCTL_UNAVAILABLE")
    return result.stdout.strip()


def observe(*, path: str = "/home/ubuntu/nbot_v5_data/g1f_observe.sqlite",
            now_ms: int | None = None,
            runner=subprocess.run) -> dict:
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms <= 0:
        raise HealthHold("G1G_BAD_CLOCK")
    blockers = []
    legacy = {}
    for unit in LEGACY_UNITS:
        legacy[unit] = run_systemctl(["is-active", unit], runner=runner)
        if legacy[unit] != "inactive":
            blockers.append("LEGACY_NOT_INACTIVE_" + unit)
    old_boot = {}
    for unit in OLD_ENABLED_UNITS:
        old_boot[unit] = run_systemctl(["is-enabled", unit], runner=runner)
        if old_boot[unit] != "disabled":
            blockers.append("LEGACY_BOOT_ENABLED_" + unit)
    active = run_systemctl(
        ["show", SERVICE, "-p", "ActiveState", "--value"], runner=runner,
    )
    enabled = run_systemctl(
        ["show", SERVICE, "-p", "UnitFileState", "--value"], runner=runner,
    )
    limit_text = run_systemctl(
        ["show", SERVICE, "-p", "MemoryMax", "--value"], runner=runner,
    )
    memory_text = run_systemctl(
        ["show", SERVICE, "-p", "MemoryCurrent", "--value"], runner=runner,
    )
    if active != "active":
        blockers.append("V5_NOT_ACTIVE")
    if enabled != "enabled":
        blockers.append("V5_BOOT_NOT_ENABLED")
    try:
        max_mem = int(limit_text)
        used_mem = int(memory_text)
    except (ValueError, TypeError) as exc:
        raise HealthHold("G1G_MEMORY_COUNTER_INVALID") from exc
    if max_mem > MAX_MEMORY_BYTES or used_mem >= max_mem:
        blockers.append("V5_MEMORY_LIMIT_UNSAFE")
    location = Path(path)
    if location.is_symlink() or not location.is_file():
        raise HealthHold("G1G_DB_MISSING_OR_SYMLINK")
    uri = location.resolve().as_uri().replace("file://", "file:") + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as db:
            integrity = db.execute("PRAGMA quick_check").fetchone()[0]
            if integrity != "ok":
                blockers.append("V5_SQLITE_INTEGRITY_FAILURE")
            count, recent = db.execute(
                "SELECT COUNT(*), MAX(event_open_ms) FROM g1f_event_manifest"
            ).fetchone()
            observed, unscorable = db.execute(
                "SELECT COALESCE(SUM(status='OBSERVED'),0), "
                "COALESCE(SUM(status='UNSCORABLE'),0) "
                "FROM g1f_candidate_events"
            ).fetchone()
            cohorts = db.execute(
                "SELECT COUNT(*) FROM g1f_universe_snapshots"
            ).fetchone()[0]
            if cohorts != 1:
                blockers.append("V5_COHORT_COUNT_INVALID")
            if not recent or now_ms - recent > MAX_STALE_MIN * 60_000:
                blockers.append("V5_LAST_EVENT_STALE")
            if recent and recent > now_ms:
                blockers.append("V5_EVENT_IN_FUTURE")
            if observed + unscorable != count * 100:
                blockers.append("V5_EVENT_DENOMINATOR_MISMATCH")
    except sqlite3.DatabaseError as exc:
        raise HealthHold("G1G_SQLITE_QUERY_FAILED") from exc
    return {
        "status": "PASS" if not blockers else "HOLD",
        "reasons": sorted(set(blockers)),
        "legacy_active": legacy,
        "legacy_boot": old_boot,
        "v5_service_active": active == "active",
        "v5_boot_enabled": enabled == "enabled",
        "v5_memory_bytes": used_mem,
        "v5_memory_limit_bytes": max_mem,
        "database_integrity": integrity,
        "event_count": count,
        "observed_directional_records": observed,
        "unscorable_directional_records": unscorable,
        "last_event_open_ms": recent,
        "research_ready": False,
        "training_labels_created": 0,
        "order_authority": "NONE",
    }


def main() -> int:
    try:
        report = observe()
    except (HealthHold, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc),
                          "research_ready": False, "order_authority": "NONE"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
