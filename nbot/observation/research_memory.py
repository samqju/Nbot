"""Permanent compact research memory for V3.8.4.

Raw market evidence and expanded relational research detail are intentionally
kept out of this database.  One qualified market event becomes one immutable
compressed training/evidence record plus compact cumulative learner state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable

from .retention import ARCHIVE_VERSION, AUTHORITY, _decode_training_blob
from .selection import SELECTION_CONFIG

MEMORY_VERSION = "RESEARCH_MEMORY_V1"

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_memory_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_memory_events (
    event_open_ms INTEGER PRIMARY KEY,
    archive_version TEXT NOT NULL,
    sealed_at_ms INTEGER NOT NULL,
    example_row_count INTEGER NOT NULL CHECK(example_row_count >= 0),
    training_encoding TEXT NOT NULL,
    training_blob BLOB NOT NULL,
    training_digest TEXT NOT NULL,
    training_uncompressed_bytes INTEGER NOT NULL CHECK(training_uncompressed_bytes > 0),
    training_compressed_bytes INTEGER NOT NULL CHECK(training_compressed_bytes > 0),
    selector_summary_json TEXT NOT NULL,
    policy_summary_json TEXT NOT NULL,
    build_manifest_json TEXT NOT NULL,
    archive_digest TEXT NOT NULL,
    authority TEXT NOT NULL CHECK(authority='RESEARCH_ONLY_NO_EXECUTION'),
    source_generation TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_memory_ridge_state (
    lab_version TEXT PRIMARY KEY,
    selector_version TEXT NOT NULL,
    through_event_ms INTEGER,
    training_event_count INTEGER NOT NULL,
    training_row_count INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    state_digest TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS research_memory_artifacts (
    artifact_key TEXT PRIMARY KEY,
    artifact_json TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    recorded_at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS research_epoch_commits (
    epoch_id TEXT PRIMARY KEY,
    generation TEXT NOT NULL,
    target_start_ms INTEGER NOT NULL,
    target_end_ms INTEGER NOT NULL,
    event_count INTEGER NOT NULL CHECK(event_count > 0),
    imported_at_ms INTEGER NOT NULL,
    source_digest TEXT NOT NULL,
    elapsed_seconds REAL NOT NULL CHECK(elapsed_seconds >= 0)
);
CREATE INDEX IF NOT EXISTS idx_memory_events_time
    ON research_memory_events(event_open_ms);
"""

LEDGER_COLUMNS = (
    "event_open_ms", "archive_version", "sealed_at_ms", "example_row_count",
    "training_encoding", "training_blob", "training_digest",
    "training_uncompressed_bytes", "training_compressed_bytes",
    "selector_summary_json", "policy_summary_json", "build_manifest_json",
    "archive_digest", "authority",
)
RIDGE_COLUMNS = (
    "lab_version", "selector_version", "through_event_ms",
    "training_event_count", "training_row_count", "state_json",
    "state_digest", "updated_at_ms",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ResearchMemoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def initialize(self, *, generation: str, generation_floor_ms: int) -> None:
        generation = str(generation).strip()
        if not generation or int(generation_floor_ms) < 0:
            raise ValueError("NBOT_V384_MEMORY_GENERATION_INVALID")
        expected = {
            "memory_version": MEMORY_VERSION,
            "authority": AUTHORITY,
            "generation": generation,
            "generation_floor_ms": str(int(generation_floor_ms)),
        }
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            existing = dict(conn.execute("SELECT key,value FROM research_memory_meta"))
            for key, value in expected.items():
                if key in existing and str(existing[key]) != str(value):
                    raise RuntimeError(f"NBOT_V384_MEMORY_META_MISMATCH:{key}")
                conn.execute(
                    "INSERT OR IGNORE INTO research_memory_meta(key,value) VALUES(?,?)",
                    (key, str(value)),
                )

    def metadata(self) -> dict[str, str]:
        with self._connect() as conn:
            return {str(k): str(v) for k, v in conn.execute(
                "SELECT key,value FROM research_memory_meta ORDER BY key"
            )}

    def iter_training_rows(
        self, *, after_event_ms: int | None = None
    ):
        """Stream compact training examples without reconstructing raw research.

        Later V3.9 challengers can train from this iterator directly.  Only one
        compressed event blob is decompressed at a time.
        """
        lower = -1 if after_event_ms is None else int(after_event_ms)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_open_ms,training_blob,training_digest "
                "FROM research_memory_events WHERE event_open_ms>? ORDER BY event_open_ms",
                (lower,),
            )
            for event_open_ms, blob, digest in rows:
                decoded = _decode_training_blob(bytes(blob), str(digest))
                for example in decoded:
                    yield int(event_open_ms), example

    def latest_event_ms(self) -> int | None:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(event_open_ms) FROM research_memory_events").fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def history_base(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(example_row_count),0),MAX(event_open_ms) "
                "FROM research_memory_events"
            ).fetchone()
            digest_rows = list(conn.execute(
                "SELECT event_open_ms,archive_digest FROM research_memory_events ORDER BY event_open_ms"
            ))
            ridge = conn.execute(
                "SELECT " + ",".join(RIDGE_COLUMNS) + " FROM research_memory_ridge_state "
                "WHERE lab_version=?",
                (SELECTION_CONFIG.lab_version,),
            ).fetchone()
        digest = _digest_text(_canonical_json([[int(e), str(d)] for e, d in digest_rows]))
        return {
            "event_count": int(row[0]),
            "row_count": int(row[1]),
            "through_event_ms": None if row[2] is None else int(row[2]),
            "source_digest": digest,
            "ridge_state_row": None if ridge is None else tuple(ridge),
        }

    def _verify_ledger_row(self, row: tuple[Any, ...]) -> None:
        mapped = dict(zip(LEDGER_COLUMNS, row))
        if mapped["archive_version"] != ARCHIVE_VERSION:
            raise RuntimeError("NBOT_V384_MEMORY_ARCHIVE_VERSION_INVALID")
        if mapped["authority"] != AUTHORITY:
            raise RuntimeError("NBOT_V384_MEMORY_AUTHORITY_INVALID")
        decoded = _decode_training_blob(
            mapped["training_blob"], str(mapped["training_digest"])
        )
        if len(decoded) != int(mapped["example_row_count"]):
            raise RuntimeError("NBOT_V384_MEMORY_TRAINING_ROW_COUNT_MISMATCH")

    def import_ledger_rows(
        self,
        rows: Iterable[tuple[Any, ...]],
        *,
        source_generation: str,
    ) -> int:
        generation = str(source_generation).strip()
        materialized = [tuple(row) for row in rows]
        for row in materialized:
            if len(row) != len(LEDGER_COLUMNS):
                raise RuntimeError("NBOT_V384_MEMORY_LEDGER_ROW_SHAPE_INVALID")
            self._verify_ledger_row(row)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            imported = 0
            for row in materialized:
                event = int(row[0])
                existing = conn.execute(
                    "SELECT " + ",".join(LEDGER_COLUMNS[1:]) +
                    " FROM research_memory_events WHERE event_open_ms=?",
                    (event,),
                ).fetchone()
                candidate_tail = tuple(row[1:])
                if existing is not None:
                    # Ignore source_generation for immutable replay checks.
                    existing_tail = tuple(existing[:-1]) if len(existing) == len(candidate_tail) + 1 else tuple(existing)
                    if existing_tail != candidate_tail:
                        raise RuntimeError(f"NBOT_V384_MEMORY_EVENT_CONFLICT:{event}")
                    continue
                conn.execute(
                    "INSERT INTO research_memory_events(" + ",".join(LEDGER_COLUMNS) +
                    ",source_generation) VALUES(" + ",".join("?" for _ in range(len(LEDGER_COLUMNS)+1)) + ")",
                    row + (generation,),
                )
                imported += 1
        return imported

    def replace_ridge_state(self, row: tuple[Any, ...]) -> None:
        if len(row) != len(RIDGE_COLUMNS):
            raise RuntimeError("NBOT_V384_MEMORY_RIDGE_ROW_SHAPE_INVALID")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO research_memory_ridge_state(" + ",".join(RIDGE_COLUMNS) +
                ") VALUES(" + ",".join("?" for _ in RIDGE_COLUMNS) + ")",
                tuple(row),
            )

    def preserve_table(self, source: sqlite3.Connection, table: str) -> None:
        present = source.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if present is None:
            return
        cols = [str(row[1]) for row in source.execute(f'PRAGMA table_info("{table}")')]
        rows = [list(row) for row in source.execute(f'SELECT * FROM "{table}"')]
        payload = {"columns": cols, "rows": rows}
        text = _canonical_json(payload)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO research_memory_artifacts("
                "artifact_key,artifact_json,artifact_digest,recorded_at_ms) VALUES(?,?,?,?)",
                (table, text, _digest_text(text), int(time.time()*1000)),
            )

    def migrate_legacy(self, legacy_db: Path, *, source_generation: str) -> dict[str, Any]:
        legacy = Path(legacy_db)
        if not legacy.exists():
            raise FileNotFoundError(legacy)
        source = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True, timeout=30.0)
        source.execute("PRAGMA query_only=ON")
        try:
            tables = {str(r[0]) for r in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "research_event_ledger" not in tables:
                raise RuntimeError("NBOT_V384_LEGACY_LEDGER_MISSING")
            rows = list(source.execute(
                "SELECT event_open_ms,archive_version,sealed_at_ms,example_row_count,"
                "training_encoding,training_blob,training_digest,training_uncompressed_bytes,"
                "training_compressed_bytes,selector_summary_json,policy_summary_json,"
                "build_manifest_json,archive_digest,authority "
                "FROM research_event_ledger ORDER BY event_open_ms"
            ))
            imported = self.import_ledger_rows(rows, source_generation=source_generation)
            if "entry_selection_ridge_state" in tables:
                ridge = source.execute(
                    "SELECT " + ",".join(RIDGE_COLUMNS) +
                    " FROM entry_selection_ridge_state WHERE lab_version=?",
                    (SELECTION_CONFIG.lab_version,),
                ).fetchone()
                if ridge is not None:
                    self.replace_ridge_state(tuple(ridge))
            for table in (
                "research_champion_sets", "research_champion_evaluations", "research_champions",
                "learning_foundations", "model_registry", "challenger_registry", "training_jobs",
                "evaluation_ledger", "drift_reports", "rollback_records",
            ):
                self.preserve_table(source, table)
        finally:
            source.close()
        status = self.status()
        ridge_status = status.get("ridge_state")
        if int(status["events"]) > 0:
            if ridge_status is None:
                raise RuntimeError("NBOT_V384_MEMORY_RIDGE_STATE_MISSING")
            if (
                int(ridge_status["training_event_count"]) != int(status["events"])
                or int(ridge_status["training_row_count"]) != int(status["training_rows"])
                or int(ridge_status["through_event_ms"]) != int(status["latest_event_open_ms"])
            ):
                raise RuntimeError("NBOT_V384_MEMORY_RIDGE_STATE_HISTORY_MISMATCH")
        status["legacy_rows_imported"] = imported
        return status

    def record_epoch(
        self, *, epoch_id: str, generation: str, target_start_ms: int,
        target_end_ms: int, event_count: int, source_digest: str,
        elapsed_seconds: float,
    ) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT generation,target_start_ms,target_end_ms,event_count,source_digest "
                "FROM research_epoch_commits WHERE epoch_id=?", (epoch_id,)
            ).fetchone()
            expected = (
                str(generation), int(target_start_ms), int(target_end_ms),
                int(event_count), str(source_digest),
            )
            if existing is not None and tuple(existing) != expected:
                raise RuntimeError("NBOT_V384_EPOCH_COMMIT_CONFLICT")
            conn.execute(
                "INSERT OR IGNORE INTO research_epoch_commits("
                "epoch_id,generation,target_start_ms,target_end_ms,event_count,imported_at_ms,"
                "source_digest,elapsed_seconds) VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(epoch_id), str(generation), int(target_start_ms), int(target_end_ms),
                    int(event_count), int(time.time()*1000), str(source_digest),
                    float(elapsed_seconds),
                ),
            )

    def artifact(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT artifact_json,artifact_digest,recorded_at_ms "
                "FROM research_memory_artifacts WHERE artifact_key=?",
                (str(key),),
            ).fetchone()
        if row is None:
            return None
        text = str(row[0])
        if _digest_text(text) != str(row[1]):
            raise RuntimeError("NBOT_V384_MEMORY_ARTIFACT_DIGEST_MISMATCH")
        return {
            "artifact_key": str(key),
            "payload": json.loads(text),
            "artifact_digest": str(row[1]),
            "recorded_at_ms": int(row[2]),
        }

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
            events, rows, compressed, raw, latest = conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(example_row_count),0),"
                "COALESCE(SUM(training_compressed_bytes),0),"
                "COALESCE(SUM(training_uncompressed_bytes),0),MAX(event_open_ms) "
                "FROM research_memory_events"
            ).fetchone()
            epochs = int(conn.execute("SELECT COUNT(*) FROM research_epoch_commits").fetchone()[0])
            ridge = conn.execute(
                "SELECT through_event_ms,training_event_count,training_row_count,state_digest "
                "FROM research_memory_ridge_state WHERE lab_version=?",
                (SELECTION_CONFIG.lab_version,),
            ).fetchone()
        return {
            "memory_version": MEMORY_VERSION,
            "authority": AUTHORITY,
            "database": str(self.path),
            "healthy": quick == "ok",
            "quick_check": quick,
            "events": int(events),
            "training_rows": int(rows),
            "training_compressed_bytes": int(compressed),
            "training_uncompressed_bytes": int(raw),
            "latest_event_open_ms": None if latest is None else int(latest),
            "epochs": epochs,
            "ridge_state": None if ridge is None else {
                "through_event_ms": ridge[0],
                "training_event_count": int(ridge[1]),
                "training_row_count": int(ridge[2]),
                "state_digest": str(ridge[3]),
            },
        }
