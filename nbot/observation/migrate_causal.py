"""Offline, copy-only upgrade of permanent research memory.

Usage: python -m nbot.observation.migrate_causal --source old.db --output new.db
The caller stops research services first. Execution state is never touched.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from .causal_ridge import STATISTICS_VERSION
from .research_memory import ResearchMemoryStore
from .selection import RidgeSufficientStatistics, SELECTION_CONFIG, _canonical_json, _digest


def migrate(source: Path, output: Path) -> dict:
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if source == output:
        raise ValueError("MIGRATION_REQUIRES_NEW_OUTPUT_FILE")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents replacement of any user's existing database.
    with output.open("xb"):
        pass
    try:
        original = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        copy = sqlite3.connect(output)
        try:
            original.backup(copy)
        finally:
            copy.close()
            original.close()
        memory = ResearchMemoryStore(output)
        before = memory.history_base()
        state = RidgeSufficientStatistics.empty()
        # Verify each compressed record and archive digest during replay.
        for record in memory.iter_event_records():
            state.add_event(record["event_open_ms"], record["examples"])
        if (state.event_count, state.row_count, state.through_event_ms) != (
            before["event_count"], before["row_count"], before["through_event_ms"]
        ):
            raise RuntimeError("MIGRATION_HISTORY_COUNT_MISMATCH")
        payload = state.to_payload()
        # Roundtrip validation before committing replacement statistics.
        RidgeSufficientStatistics.from_payload(payload)
        memory.replace_ridge_state((SELECTION_CONFIG.lab_version,
            SELECTION_CONFIG.learned_selector_version, state.through_event_ms,
            state.event_count, state.row_count, _canonical_json(payload),
            _digest(payload), int(time.time() * 1000)))
        with memory._connect() as conn:
            conn.execute("UPDATE research_memory_artifacts SET artifact_key='legacy-causal:' || artifact_key "
                         "WHERE artifact_key LIKE 'v39:%' AND artifact_key NOT LIKE 'v39:causal-v3:%'")
            # Preserve legacy promotion/evaluation records as history, but do
            # not reuse conclusions based on the old chronology as authority.
            for table in ("research_memory_champions", "research_memory_champion_evaluations"):
                exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if exists:
                    conn.execute(f"CREATE TABLE IF NOT EXISTS legacy_causal_{table} AS SELECT * FROM {table} WHERE 0")
                    conn.execute(f"INSERT INTO legacy_causal_{table} SELECT * FROM {table}")
                    conn.execute(f"DELETE FROM {table}")
            report = {"statistics_version": STATISTICS_VERSION,
                      "source": str(source), "output": str(output),
                      "events_replayed": state.event_count, "rows_replayed": state.row_count,
                      "source_digest": before["source_digest"], "state_digest": _digest(payload),
                      "old_evaluations": "PRESERVED_AS_LEGACY_NOT_REUSED"}
            conn.execute("INSERT OR REPLACE INTO research_memory_meta VALUES(?,?)",
                         ("causal_migration", _canonical_json(report)))
        after = memory.history_base()
        if after["source_digest"] != before["source_digest"]:
            raise RuntimeError("MIGRATION_CHANGED_IMMUTABLE_EVIDENCE")
        return report
    except BaseException:
        # This output was exclusively created above; never delete the source.
        output.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(migrate(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
