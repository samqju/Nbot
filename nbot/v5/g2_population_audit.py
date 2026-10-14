"""G2 read-only audit of complete point-in-time candidate population.

Independent quality gate over G1f's append-only source journal. Neither this
module nor its CLI creates trade outcomes, learning labels or recommendations.
An explicitly HELD candidate remains in the denominator, not a failed audit;
a missing candidate slot or mutated payload is a failed audit.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import hashlib
import json
import sqlite3
import time

from nbot.v5.observation_contract import INTERVAL_MS, PATTERN_IDS, SCHEMA_VERSION, SIDES
from nbot.v5.g1f_journal import digest, canonical

class PopulationHold(ValueError):
    pass


def audit_population(path: str | Path, *, now_ms: int | None = None) -> dict:
    """Scan all captured candidate slots from SQLite in read-only mode.

    This validates observation integrity, not future trade profitability.
    SQL reads use mode=ro and no table creation, checkpoint or mutation.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PopulationHold("G2_DB_MISSING_OR_SYMLINK")
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms <= 0:
        raise PopulationHold("G2_BAD_CLOCK")
    problems = []
    counts = Counter()
    hold_reasons = Counter()
    hold_events = 0
    interrupted_events = 0
    missing_time_slots = 0
    snapshot = {}
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise PopulationHold("G2_DB_INTEGRITY_FAILURE")
            cohorts = db.execute(
                "SELECT cohort_digest,selection_version,symbols_json,"
                "first_event_open_ms FROM g1f_universe_snapshots"
            ).fetchall()
            if len(cohorts) != 1:
                raise PopulationHold("G2_COHORT_NOT_SINGLE_FROZEN_SNAPSHOT")
            cohort_digest, version, symbols_json, first_event = cohorts[0]
            try:
                symbols = tuple(json.loads(symbols_json))
            except (ValueError, TypeError) as exc:
                raise PopulationHold("G2_COHORT_INVALID_JSON") from exc
            if (len(symbols) < 2 or len(symbols) > 50
                    or len(set(symbols)) != len(symbols)
                    or tuple(sorted(symbols)) != symbols or "BTCUSDT" not in symbols
                    or digest({"selection_version": version,
                               "symbols": symbols}) != cohort_digest):
                raise PopulationHold("G2_COHORT_INVALID")
            snapshot = {"cohort_size": len(symbols), "cohort_digest": cohort_digest}
            symbol_set = set(symbols)
            expected = {(s, side) for s in symbols for side in SIDES}
            manifests = db.execute(
                "SELECT event_open_ms,cohort_digest,committed_ms,state,"
                "verification_json,verification_sha FROM g1f_event_manifest "
                "ORDER BY event_open_ms"
            ).fetchall()
            if not manifests:
                raise PopulationHold("G2_NO_RECORDED_EVENTS")
            last = None
            for event_ms, event_cohort, commit_ms, state, verification, v_sha in manifests:
                counts["events"] += 1
                if event_ms % INTERVAL_MS or event_ms > now_ms:
                    problems.append("EVENT_CLOCK_INVALID")
                if event_cohort != cohort_digest:
                    problems.append("EVENT_COHORT_MISMATCH")
                if type(commit_ms) is not int or commit_ms < event_ms + INTERVAL_MS or commit_ms > now_ms:
                    problems.append("EVENT_COMMIT_CLOCK_INVALID")
                try:
                    summary = json.loads(verification)
                except (ValueError, TypeError):
                    problems.append("MANIFEST_INVALID_JSON")
                    summary = {}
                if (canonical(summary) != verification or digest(summary) != v_sha
                        or summary.get("event_open_ms") != event_ms
                        or summary.get("cohort_digest") != cohort_digest
                        or summary.get("order_authority") != "NONE"
                        or summary.get("training_labels_created") != 0
                        or summary.get("research_ready") is not False):
                    problems.append("MANIFEST_PROOF_INVALID")
                if last is None:
                    # Cohort selection/bootstrap happens before WSS
                    # evidence begins; exclude warm-up slots explicitly.
                    # Bound initial setup to three 5m slots rather than
                    # invent any observations or hide an extended outage.
                    bootstrap_offset = event_ms - first_event
                    if (bootstrap_offset < 0
                            or bootstrap_offset > 3 * INTERVAL_MS
                            or bootstrap_offset % INTERVAL_MS):
                        problems.append("COHORT_FIRST_OBSERVATION_INVALID")
                elif event_ms - last != INTERVAL_MS:
                    interrupted_events += 1
                    if event_ms > last + INTERVAL_MS:
                        missing_time_slots += (event_ms - last) // INTERVAL_MS - 1
                    if summary.get("gap") is not True:
                        problems.append("UNDECLARED_EVENT_GAP")
                elif summary.get("gap") is True:
                    problems.append("FALSE_EVENT_GAP")
                last = event_ms

                slots = set()
                event_status = Counter()
                for (decision_id, symbol, side, status, record_sha, raw) in db.execute(
                    "SELECT decision_id,symbol,direction,status,record_sha,record_json "
                    "FROM g1f_candidate_events WHERE event_open_ms=?", (event_ms,)
                ):
                    pair = (symbol, side)
                    if pair not in expected or pair in slots:
                        problems.append("CANDIDATE_OUTSIDE_OR_DUPLICATED")
                    slots.add(pair)
                    try:
                        record = json.loads(raw)
                    except (ValueError, TypeError):
                        problems.append("CANDIDATE_INVALID_JSON")
                        continue
                    reason_codes = record.get("reason_codes")
                    identity = digest({"schema": SCHEMA_VERSION,
                                       "event_open_ms": event_ms,
                                       "symbol": symbol, "side": side})
                    if (record.get("schema_version") != SCHEMA_VERSION
                            or record.get("decision_id") != decision_id
                            or identity != decision_id
                            or record.get("symbol") != symbol
                            or record.get("side") != side
                            or record.get("event_open_ms") != event_ms
                            or record.get("status") != status
                            or canonical(record) != raw
                            or hashlib.sha256(raw.encode()).hexdigest() != record_sha):
                        problems.append("CANDIDATE_PROOF_INVALID")
                    if (record.get("action") != "OBSERVE_ONLY"
                            or record.get("order_authority") != "NONE"
                            or not isinstance(record.get("decision_at_ms"), int)
                            or not event_ms + INTERVAL_MS <= record.get("decision_at_ms", -1) <= commit_ms):
                        problems.append("CANDIDATE_AUTHORITY_OR_ASOF_INVALID")
                    states = record.get("patterns")
                    if (not isinstance(states, dict) or set(states) != set(PATTERN_IDS)
                            or any(v not in ("MATCH", "NO_MATCH", "UNAVAILABLE")
                                   for v in states.values())):
                        problems.append("PATTERN_DENOMINATOR_INVALID")
                    if status == "UNSCORABLE":
                        if not isinstance(reason_codes, list) or not reason_codes:
                            problems.append("UNSCORABLE_WITHOUT_REASON")
                        else:
                            hold_reasons.update(set(reason_codes))
                    elif status == "OBSERVED":
                        if reason_codes:
                            problems.append("OBSERVED_WITH_HOLD_REASON")
                    else:
                        problems.append("CANDIDATE_STATUS_INVALID")
                    counts[status] += 1
                    event_status[status] += 1
                if slots != expected:
                    problems.append("CANDIDATE_DENOMINATOR_MISSING")
                if (summary.get("observed") != event_status["OBSERVED"]
                        or summary.get("unscorable") != event_status["UNSCORABLE"]):
                    problems.append("EVENT_COUNTER_MISMATCH")
                expected_state = "HOLD" if event_status["UNSCORABLE"] else "OBSERVE_ONLY"
                if state != expected_state or summary.get("status") != state:
                    problems.append("EVENT_HOLD_STATE_MISMATCH")
                if state == "HOLD":
                    hold_events += 1
            dangling = db.execute(
                "SELECT COUNT(*) FROM g1f_candidate_events "
                "WHERE event_open_ms NOT IN (SELECT event_open_ms FROM g1f_event_manifest)"
            ).fetchone()[0]
            if dangling:
                problems.append("CANDIDATE_EVENT_ORPHANS")
    except sqlite3.DatabaseError as exc:
        raise PopulationHold("G2_SQLITE_QUERY_FAILED") from exc

    return {
        "audit": "PASS" if not problems else "HOLD",
        "violations": sorted(set(problems)),
        **snapshot,
        "events": counts["events"],
        "cohort_bootstrap_offset_slots": (manifests[0][0] - first_event) // INTERVAL_MS,
        "first_event_open_ms": manifests[0][0],
        "last_event_open_ms": manifests[-1][0],
        "observed_directional_records": counts["OBSERVED"],
        "unscorable_directional_records": counts["UNSCORABLE"],
        "held_events": hold_events,
        "explicit_event_gaps": interrupted_events,
        "unrepresented_time_slots": missing_time_slots,
        "unscorable_reasons": dict(sorted(hold_reasons.items())),
        "expected_directional_records": counts["events"] * len(expected),
        "training_labels_created": 0,
        "research_ready": False,
        "recommendation_authority": "NONE",
        "order_authority": "NONE",
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="G2 observation-only population integrity")
    parser.add_argument("--db", default="/home/ubuntu/nbot_v5_data/g1f_observe.sqlite")
    args = parser.parse_args()
    try:
        result = audit_population(args.db)
    except (PopulationHold, OSError) as exc:
        print(json.dumps({"audit": "HOLD", "reason": str(exc),
                          "research_ready": False, "order_authority": "NONE"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["audit"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
