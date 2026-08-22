"""V3.8.2 compact research ledger and derived-data lifecycle.

Canonical raw LIVE evidence remains durable.  Completed research events are
sealed into a compact, digest-verified training/evidence archive before old
reproducible detail is removed.  This module has research-only authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import sqlite3
import statistics
import time
from typing import Any
import zlib

from .database import EvidenceDatabase
from .features import CANONICAL_FEATURE_VERSION
from .outcomes import OUTCOME_VERSION
from .policies import LAB_VERSION as POLICY_LAB_VERSION
from .selection import SELECTION_CONFIG


ARCHIVE_VERSION = "COMPACT_RESEARCH_LEDGER_V1"
AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"


@dataclass(frozen=True)
class RetentionConfig:
    archive_version: str = ARCHIVE_VERSION
    frozen_detail_selection_events: int = 60
    recent_detail_selection_events: int = 64
    max_seal_events: int = 32
    max_compact_events: int = 8
    hard_live_bytes: int = 1_073_741_824

    def validate(self) -> None:
        if self.archive_version != ARCHIVE_VERSION:
            raise ValueError("NBOT_V382_ARCHIVE_VERSION_IMMUTABLE")
        if self.frozen_detail_selection_events < 60:
            raise ValueError("NBOT_V382_FROZEN_DETAIL_WINDOW_TOO_SMALL")
        if self.recent_detail_selection_events <= 0:
            raise ValueError("NBOT_V382_RECENT_DETAIL_WINDOW_INVALID")
        if self.max_seal_events <= 0 or self.max_compact_events <= 0:
            raise ValueError("NBOT_V382_BATCH_LIMIT_INVALID")
        if self.hard_live_bytes <= 0:
            raise ValueError("NBOT_V382_HARD_LIVE_BYTES_INVALID")


RETENTION_CONFIG = RetentionConfig()
RETENTION_CONFIG.validate()

RETENTION_TABLES: tuple[str, ...] = (
    "research_retention_sets",
    "research_event_ledger",
    "research_compaction_runs",
)

RETENTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_retention_sets (
    archive_version TEXT PRIMARY KEY,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS research_event_ledger (
    event_open_ms INTEGER PRIMARY KEY,
    archive_version TEXT NOT NULL,
    sealed_at_ms INTEGER NOT NULL,
    compacted_at_ms INTEGER,
    state TEXT NOT NULL CHECK (state IN ('SEALED','COMPACTED')),
    example_row_count INTEGER NOT NULL CHECK (example_row_count >= 0),
    training_encoding TEXT NOT NULL CHECK (training_encoding='ZLIB_CANONICAL_JSON_V1'),
    training_blob BLOB NOT NULL,
    training_digest TEXT NOT NULL,
    training_uncompressed_bytes INTEGER NOT NULL CHECK (training_uncompressed_bytes > 0),
    training_compressed_bytes INTEGER NOT NULL CHECK (training_compressed_bytes > 0),
    selector_summary_json TEXT NOT NULL,
    policy_summary_json TEXT NOT NULL,
    build_manifest_json TEXT NOT NULL,
    archive_digest TEXT NOT NULL,
    authority TEXT NOT NULL CHECK (authority='RESEARCH_ONLY_NO_EXECUTION'),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms),
    FOREIGN KEY (archive_version) REFERENCES research_retention_sets(archive_version)
);

CREATE TABLE IF NOT EXISTS research_compaction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archive_version TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    completed_at_ms INTEGER NOT NULL,
    attempted_events INTEGER NOT NULL CHECK (attempted_events >= 0),
    compacted_events INTEGER NOT NULL CHECK (compacted_events >= 0),
    database_bytes_before INTEGER NOT NULL CHECK (database_bytes_before >= 0),
    database_bytes_after INTEGER NOT NULL CHECK (database_bytes_after >= 0),
    live_bytes_before INTEGER NOT NULL CHECK (live_bytes_before >= 0),
    live_bytes_after INTEGER NOT NULL CHECK (live_bytes_after >= 0),
    reusable_bytes_after INTEGER NOT NULL CHECK (reusable_bytes_after >= 0),
    detail_json TEXT NOT NULL,
    FOREIGN KEY (archive_version) REFERENCES research_retention_sets(archive_version)
);

CREATE INDEX IF NOT EXISTS idx_research_ledger_state_time
    ON research_event_ledger(state, event_open_ms);
"""

TRAINING_COLUMNS: tuple[str, ...] = (
    "event_open_ms", "symbol", "side", "feature_vector_json",
    "target_net_r", "target_net_return_frac", "target_mfe_r", "target_mae_r",
    "source_policy_result_digest", "source_feature_digest", "source_signal_digest",
    "example_digest",
)

DETAIL_TABLES: tuple[str, ...] = (
    "entry_selection_predictions",
    "entry_selection_prediction_builds",
    "entry_selection_examples",
    "entry_selection_builds",
    "exit_policy_results",
    "exit_policy_builds",
    "future_path_attempts",
    "future_paths",
    "future_path_builds",
    "signal_annotations",
    "signal_builds",
    "canonical_features",
    "feature_builds",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _encode_training_rows(rows: list[dict[str, Any]]) -> tuple[bytes, str, int]:
    payload = [[row[column] for column in TRAINING_COLUMNS] for row in rows]
    raw = _canonical_json(payload).encode("utf-8")
    return zlib.compress(raw, level=9), hashlib.sha256(raw).hexdigest(), len(raw)


def _decode_training_blob(blob: bytes, expected_digest: str) -> list[dict[str, Any]]:
    try:
        raw = zlib.decompress(bytes(blob))
    except (TypeError, zlib.error) as exc:
        raise ValueError("NBOT_V382_TRAINING_BLOB_INVALID") from exc
    if hashlib.sha256(raw).hexdigest() != str(expected_digest):
        raise ValueError("NBOT_V382_TRAINING_BLOB_DIGEST_MISMATCH")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("NBOT_V382_TRAINING_BLOB_JSON_INVALID") from exc
    if not isinstance(payload, list):
        raise ValueError("NBOT_V382_TRAINING_BLOB_ROWS_INVALID")
    if _canonical_json(payload).encode("utf-8") != raw:
        raise ValueError("NBOT_V382_TRAINING_BLOB_NOT_CANONICAL")
    rows: list[dict[str, Any]] = []
    for values in payload:
        if not isinstance(values, list) or len(values) != len(TRAINING_COLUMNS):
            raise ValueError("NBOT_V382_TRAINING_BLOB_ROW_SHAPE_INVALID")
        rows.append(dict(zip(TRAINING_COLUMNS, values)))
    return rows


def _definition(config: RetentionConfig) -> dict[str, Any]:
    return {
        "archive_version": config.archive_version,
        "canonical_raw_policy": "DURABLE_NOT_COMPACTED",
        "training_archive": "ONE_ZLIB_CANONICAL_EVENT_BLOB_WITH_DECISION_TIME_FEATURE_VECTOR_PLUS_AFTER_COST_TARGET",
        "frozen_detail_selection_events": config.frozen_detail_selection_events,
        "recent_detail_selection_events": config.recent_detail_selection_events,
        "compaction_rule": "SEAL_VERIFY_THEN_PURGE_REPRODUCIBLE_EVENT_DETAIL",
        "future_candle_cache": "SHARED_LABEL_CACHE_RETAINED",
        "authority": AUTHORITY,
    }


def _storage(conn: sqlite3.Connection) -> dict[str, int]:
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    freelist = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
    return {
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": freelist,
        "allocated_bytes": page_size * page_count,
        "reusable_bytes": page_size * freelist,
        "live_bytes": page_size * max(0, page_count - freelist),
    }


class ResearchRetentionManager:
    def __init__(self, database: EvidenceDatabase, config: RetentionConfig = RETENTION_CONFIG):
        config.validate()
        self.database = database
        self.config = config

    def initialize(self) -> None:
        definition = _definition(self.config)
        definition_json = _canonical_json(definition)
        definition_hash = _digest(definition)
        with self.database.connection() as conn:
            conn.executescript(RETENTION_SCHEMA)
            now_ms = int(time.time() * 1000)
            conn.execute(
                "INSERT OR IGNORE INTO research_retention_sets(archive_version,definition_hash,definition_json,registered_at_ms) VALUES(?,?,?,?)",
                (self.config.archive_version, definition_hash, definition_json, now_ms),
            )
            stored = conn.execute(
                "SELECT definition_hash,definition_json FROM research_retention_sets WHERE archive_version=?",
                (self.config.archive_version,),
            ).fetchone()
            if stored != (definition_hash, definition_json):
                raise RuntimeError("NBOT_V382_RETENTION_DEFINITION_MISMATCH")

    def _training_rows(self, conn: sqlite3.Connection, event_open_ms: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT " + ",".join(TRAINING_COLUMNS) + " FROM entry_selection_examples "
            "WHERE event_open_ms=? AND lab_version=? ORDER BY symbol,side",
            (event_open_ms, SELECTION_CONFIG.lab_version),
        ).fetchall()
        return [dict(zip(TRAINING_COLUMNS, row)) for row in rows]

    def _build_manifest(self, conn: sqlite3.Connection, event_open_ms: int) -> dict[str, Any]:
        def one(sql: str, params: tuple[Any, ...]) -> list[Any] | None:
            row = conn.execute(sql, params).fetchone()
            return None if row is None else list(row)

        prediction_builds = [list(row) for row in conn.execute(
            "SELECT selector_version,prediction_row_count,training_event_count,training_row_count,trained_through_event_ms,model_digest,source_digest,prediction_digest "
            "FROM entry_selection_prediction_builds WHERE event_open_ms=? AND lab_version=? ORDER BY selector_version",
            (event_open_ms, SELECTION_CONFIG.lab_version),
        )]
        return {
            "feature": one(
                "SELECT feature_row_count,source_digest,feature_digest FROM feature_builds WHERE event_open_ms=? AND feature_version=?",
                (event_open_ms, CANONICAL_FEATURE_VERSION),
            ),
            "signals": one(
                "SELECT feature_row_count,signal_annotation_count,source_digest,signal_digest FROM signal_builds WHERE event_open_ms=? AND feature_version=?",
                (event_open_ms, CANONICAL_FEATURE_VERSION),
            ),
            "outcomes": one(
                "SELECT path_row_count,path_digest,source_digest,fallback_candle_count FROM future_path_builds WHERE event_open_ms=? AND outcome_version=?",
                (event_open_ms, OUTCOME_VERSION),
            ),
            "outcome_attempt_count": int(conn.execute(
                "SELECT COUNT(*) FROM future_path_attempts WHERE event_open_ms=? AND outcome_version=?",
                (event_open_ms, OUTCOME_VERSION),
            ).fetchone()[0]),
            "policies": one(
                "SELECT eligible_path_count,result_row_count,source_digest,result_digest FROM exit_policy_builds WHERE event_open_ms=? AND lab_version=?",
                (event_open_ms, POLICY_LAB_VERSION),
            ),
            "selection": one(
                "SELECT example_row_count,source_digest,example_digest FROM entry_selection_builds WHERE event_open_ms=? AND lab_version=?",
                (event_open_ms, SELECTION_CONFIG.lab_version),
            ),
            "prediction_builds": prediction_builds,
        }

    def _selector_summary(self, conn: sqlite3.Connection, event_open_ms: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        selectors = conn.execute(
            "SELECT selector_version,COUNT(*) FROM entry_selection_predictions WHERE event_open_ms=? AND lab_version=? GROUP BY selector_version ORDER BY selector_version",
            (event_open_ms, SELECTION_CONFIG.lab_version),
        ).fetchall()
        for selector, count in selectors:
            top = conn.execute(
                "SELECT symbol,side,score,rank_in_event,training_event_count,training_row_count,trained_through_event_ms,model_digest,prediction_digest "
                "FROM entry_selection_predictions WHERE event_open_ms=? AND lab_version=? AND selector_version=? ORDER BY rank_in_event,symbol,side LIMIT 1",
                (event_open_ms, SELECTION_CONFIG.lab_version, selector),
            ).fetchone()
            result[str(selector)] = {"prediction_rows": int(count), "top": None if top is None else list(top)}
        return result

    def _policy_summary(self, conn: sqlite3.Connection, event_open_ms: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        versions = [str(row[0]) for row in conn.execute(
            "SELECT DISTINCT policy_version FROM exit_policy_results WHERE event_open_ms=? AND lab_version=? ORDER BY policy_version",
            (event_open_ms, POLICY_LAB_VERSION),
        )]
        for version in versions:
            rows = conn.execute(
                "SELECT net_r,capture_ratio,holding_minutes,missed_extension_r FROM exit_policy_results "
                "WHERE event_open_ms=? AND lab_version=? AND policy_version=? ORDER BY symbol,side",
                (event_open_ms, POLICY_LAB_VERSION, version),
            ).fetchall()
            net_r = [float(row[0]) for row in rows]
            captures = [float(row[1]) for row in rows if row[1] is not None]
            holding = [float(row[2]) for row in rows]
            missed = [float(row[3]) for row in rows]
            result[version] = {
                "rows": len(rows),
                "mean_net_r": statistics.fmean(net_r) if net_r else None,
                "median_net_r": statistics.median(net_r) if net_r else None,
                "mean_capture_ratio": statistics.fmean(captures) if captures else None,
                "mean_holding_minutes": statistics.fmean(holding) if holding else None,
                "mean_missed_extension_r": statistics.fmean(missed) if missed else None,
            }
        return result

    def _archive_digest(self, event_open_ms: int, selector_json: str, policy_json: str, manifest_json: str,
                        training_digest: str, example_row_count: int) -> str:
        return _digest({
            "archive_version": self.config.archive_version,
            "event_open_ms": event_open_ms,
            "selector_summary": json.loads(selector_json),
            "policy_summary": json.loads(policy_json),
            "build_manifest": json.loads(manifest_json),
            "training_digest": training_digest,
            "example_row_count": int(example_row_count),
        })

    def seal(self, *, max_events: int | None = None) -> dict[str, Any]:
        self.initialize()
        limit = self.config.max_seal_events if max_events is None else int(max_events)
        if limit < 0:
            raise ValueError("NBOT_V382_SEAL_LIMIT_INVALID")
        with self.database.connection() as conn:
            sql = (
                "SELECT b.event_open_ms FROM entry_selection_builds b "
                "WHERE b.lab_version=? AND NOT EXISTS (SELECT 1 FROM research_event_ledger l WHERE l.event_open_ms=b.event_open_ms) "
                "ORDER BY b.event_open_ms"
            )
            params: list[Any] = [SELECTION_CONFIG.lab_version]
            if limit > 0:
                sql += " LIMIT ?"
                params.append(limit)
            targets = [int(row[0]) for row in conn.execute(sql, params)]

        sealed = 0
        for event_open_ms in targets:
            with self.database.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute("SELECT 1 FROM research_event_ledger WHERE event_open_ms=?", (event_open_ms,)).fetchone():
                    continue
                training_rows = self._training_rows(conn, event_open_ms)
                if not training_rows:
                    raise RuntimeError(f"NBOT_V382_ARCHIVE_EXAMPLES_MISSING:{event_open_ms}")
                manifest = self._build_manifest(conn, event_open_ms)
                if manifest["selection"] is None or manifest["policies"] is None or manifest["outcomes"] is None:
                    raise RuntimeError(f"NBOT_V382_ARCHIVE_BUILD_MANIFEST_INCOMPLETE:{event_open_ms}")
                selector_json = _canonical_json(self._selector_summary(conn, event_open_ms))
                policy_json = _canonical_json(self._policy_summary(conn, event_open_ms))
                manifest_json = _canonical_json(manifest)
                training_blob, training_digest, training_uncompressed_bytes = _encode_training_rows(training_rows)
                digest = self._archive_digest(
                    event_open_ms, selector_json, policy_json, manifest_json,
                    training_digest, len(training_rows),
                )
                now_ms = int(time.time() * 1000)
                conn.execute(
                    "INSERT INTO research_event_ledger(event_open_ms,archive_version,sealed_at_ms,compacted_at_ms,state,example_row_count,training_encoding,training_blob,training_digest,training_uncompressed_bytes,training_compressed_bytes,selector_summary_json,policy_summary_json,build_manifest_json,archive_digest,authority) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        event_open_ms, self.config.archive_version, now_ms, None, "SEALED", len(training_rows),
                        "ZLIB_CANONICAL_JSON_V1", sqlite3.Binary(training_blob), training_digest,
                        training_uncompressed_bytes, len(training_blob), selector_json, policy_json,
                        manifest_json, digest, AUTHORITY,
                    ),
                )
                if not self._audit_event(conn, event_open_ms):
                    raise RuntimeError(f"NBOT_V382_ARCHIVE_VERIFY_FAILED:{event_open_ms}")
            sealed += 1
        return {"attempted_events": len(targets), "sealed_events": sealed, "authority": AUTHORITY}

    def _detail_archive_digest(self, conn: sqlite3.Connection, event_open_ms: int) -> str:
        training_rows = self._training_rows(conn, event_open_ms)
        selector_json = _canonical_json(self._selector_summary(conn, event_open_ms))
        policy_json = _canonical_json(self._policy_summary(conn, event_open_ms))
        manifest_json = _canonical_json(self._build_manifest(conn, event_open_ms))
        _blob, training_digest, _raw_bytes = _encode_training_rows(training_rows)
        return self._archive_digest(
            event_open_ms, selector_json, policy_json, manifest_json,
            training_digest, len(training_rows),
        )

    def _detail_matches_archive(self, conn: sqlite3.Connection, event_open_ms: int) -> bool:
        row = conn.execute(
            "SELECT archive_digest FROM research_event_ledger WHERE event_open_ms=? AND archive_version=?",
            (event_open_ms, self.config.archive_version),
        ).fetchone()
        if row is None:
            return False
        try:
            return self._detail_archive_digest(conn, event_open_ms) == str(row[0])
        except (sqlite3.DatabaseError, TypeError, ValueError, json.JSONDecodeError):
            return False

    def _archived_training_rows(self, conn: sqlite3.Connection, event_open_ms: int) -> list[dict[str, Any]]:
        row = conn.execute(
            "SELECT training_blob,training_digest FROM research_event_ledger WHERE event_open_ms=? AND archive_version=?",
            (event_open_ms, self.config.archive_version),
        ).fetchone()
        if row is None:
            return []
        return _decode_training_blob(bytes(row[0]), str(row[1]))

    def load_training_rows(self, event_open_ms: int) -> list[dict[str, Any]]:
        """Read the compact permanent training representation for later challengers."""
        with self.database.connection() as conn:
            return self._archived_training_rows(conn, int(event_open_ms))


    def _audit_event(self, conn: sqlite3.Connection, event_open_ms: int) -> bool:
        row = conn.execute(
            "SELECT example_row_count,training_encoding,training_blob,training_digest,training_uncompressed_bytes,training_compressed_bytes,selector_summary_json,policy_summary_json,build_manifest_json,archive_digest,authority "
            "FROM research_event_ledger WHERE event_open_ms=? AND archive_version=?",
            (event_open_ms, self.config.archive_version),
        ).fetchone()
        if row is None or str(row[10]) != AUTHORITY or str(row[1]) != "ZLIB_CANONICAL_JSON_V1":
            return False
        try:
            blob = bytes(row[2])
            training = _decode_training_blob(blob, str(row[3]))
            if len(training) != int(row[0]) or len(blob) != int(row[5]):
                return False
            canonical = _canonical_json(
                [[item[column] for column in TRAINING_COLUMNS] for item in training]
            ).encode("utf-8")
            if len(canonical) != int(row[4]):
                return False
            digest = self._archive_digest(
                event_open_ms, str(row[6]), str(row[7]), str(row[8]),
                str(row[3]), int(row[0]),
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return digest == str(row[9])

    def _detail_count(self, conn: sqlite3.Connection, event_open_ms: int) -> int:
        total = 0
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in DETAIL_TABLES:
            if table in tables:
                total += int(conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE event_open_ms=?', (event_open_ms,)).fetchone()[0])
        return total

    def _protected_events(self, conn: sqlite3.Connection) -> tuple[set[int], set[int], list[int]]:
        events = [int(row[0]) for row in conn.execute(
            "SELECT event_open_ms FROM research_event_ledger WHERE archive_version=? ORDER BY event_open_ms",
            (self.config.archive_version,),
        )]
        frozen = set(events[: self.config.frozen_detail_selection_events])
        recent = set(events[-self.config.recent_detail_selection_events :]) if events else set()
        return frozen, recent, events

    def compact(self, *, max_events: int | None = None) -> dict[str, Any]:
        self.initialize()
        limit = self.config.max_compact_events if max_events is None else int(max_events)
        if limit < 0:
            raise ValueError("NBOT_V382_COMPACT_LIMIT_INVALID")
        path = self.database.path
        before_size = path.stat().st_size if path.exists() else 0
        started = int(time.time() * 1000)
        with self.database.connection() as conn:
            before_storage = _storage(conn)
            frozen, recent, _events = self._protected_events(conn)
            candidates = [
                int(row[0]) for row in conn.execute(
                    "SELECT event_open_ms FROM research_event_ledger WHERE archive_version=? AND state='SEALED' ORDER BY event_open_ms",
                    (self.config.archive_version,),
                )
                if int(row[0]) not in frozen and int(row[0]) not in recent
            ]
        targets = candidates if limit == 0 else candidates[:limit]
        compacted: list[int] = []
        for event_open_ms in targets:
            with self.database.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if not self._audit_event(conn, event_open_ms):
                    raise RuntimeError(f"NBOT_V382_ARCHIVE_VERIFY_FAILED:{event_open_ms}")
                if self._detail_count(conn, event_open_ms) > 0 and not self._detail_matches_archive(conn, event_open_ms):
                    raise RuntimeError(f"NBOT_V382_DETAIL_CHANGED_AFTER_SEAL:{event_open_ms}")
                if self._detail_count(conn, event_open_ms) == 0:
                    conn.execute(
                        "UPDATE research_event_ledger SET state='COMPACTED',compacted_at_ms=COALESCE(compacted_at_ms,?) WHERE event_open_ms=?",
                        (int(time.time() * 1000), event_open_ms),
                    )
                    compacted.append(event_open_ms)
                    continue
                for table in DETAIL_TABLES:
                    present = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                    if present:
                        conn.execute(f'DELETE FROM "{table}" WHERE event_open_ms=?', (event_open_ms,))
                if self._detail_count(conn, event_open_ms) != 0:
                    raise RuntimeError(f"NBOT_V382_DETAIL_PURGE_INCOMPLETE:{event_open_ms}")
                conn.execute(
                    "UPDATE research_event_ledger SET state='COMPACTED',compacted_at_ms=? WHERE event_open_ms=?",
                    (int(time.time() * 1000), event_open_ms),
                )
                if not self._audit_event(conn, event_open_ms):
                    raise RuntimeError(f"NBOT_V382_ARCHIVE_CHANGED_DURING_COMPACTION:{event_open_ms}")
                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                if fk:
                    raise RuntimeError(f"NBOT_V382_FOREIGN_KEY_ERROR:{event_open_ms}")
            compacted.append(event_open_ms)

        completed = int(time.time() * 1000)
        after_size = path.stat().st_size if path.exists() else 0
        with self.database.connection() as conn:
            after_storage = _storage(conn)
            conn.execute(
                "INSERT INTO research_compaction_runs(archive_version,started_at_ms,completed_at_ms,attempted_events,compacted_events,database_bytes_before,database_bytes_after,live_bytes_before,live_bytes_after,reusable_bytes_after,detail_json) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    self.config.archive_version, started, completed, len(targets), len(compacted),
                    before_size, after_size, before_storage["live_bytes"], after_storage["live_bytes"],
                    after_storage["reusable_bytes"], _canonical_json({"compacted_event_open_ms": compacted}),
                ),
            )
        return {
            "attempted_events": len(targets), "compacted_events": len(compacted),
            "compacted_event_open_ms": compacted,
            "database_bytes_before": before_size, "database_bytes_after": after_size,
            "live_bytes_before": before_storage["live_bytes"], "live_bytes_after": after_storage["live_bytes"],
            "reusable_bytes_after": after_storage["reusable_bytes"], "authority": AUTHORITY,
        }

    def audit(self) -> dict[str, Any]:
        """Read-only archive/integrity audit; never initializes tables."""
        report = {
            "archive_version": self.config.archive_version,
            "authority": AUTHORITY,
            "definition_mismatch": 0,
            "archive_digest_mismatches": 0,
            "archive_row_count_mismatches": 0,
            "sealed_detail_mismatches": 0,
            "compacted_detail_rows": 0,
            "compacted_events": 0,
            "sealed_events": 0,
            "archived_training_rows": 0,
            "training_archive_compressed_bytes": 0,
            "training_archive_uncompressed_bytes": 0,
            "missing_tables": [],
        }
        definition = _definition(self.config)
        expected_hash = _digest(definition)
        expected_json = _canonical_json(definition)
        with self.database.connection() as conn:
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = [table for table in RETENTION_TABLES if table not in tables]
            report["missing_tables"] = missing
            if missing:
                report["healthy"] = False
                return report
            stored = conn.execute(
                "SELECT definition_hash,definition_json FROM research_retention_sets WHERE archive_version=?",
                (self.config.archive_version,),
            ).fetchone()
            report["definition_mismatch"] = int(stored != (expected_hash, expected_json))
            rows = conn.execute(
                "SELECT event_open_ms,state,example_row_count FROM research_event_ledger WHERE archive_version=? ORDER BY event_open_ms",
                (self.config.archive_version,),
            ).fetchall()
            report["sealed_events"] = sum(str(row[1]) == "SEALED" for row in rows)
            report["compacted_events"] = sum(str(row[1]) == "COMPACTED" for row in rows)
            totals = conn.execute(
                "SELECT COALESCE(SUM(example_row_count),0),COALESCE(SUM(training_compressed_bytes),0),COALESCE(SUM(training_uncompressed_bytes),0) "
                "FROM research_event_ledger WHERE archive_version=?",
                (self.config.archive_version,),
            ).fetchone()
            report["archived_training_rows"] = int(totals[0])
            report["training_archive_compressed_bytes"] = int(totals[1])
            report["training_archive_uncompressed_bytes"] = int(totals[2])
            for event_open_ms, state, expected_rows in rows:
                try:
                    actual = len(self._archived_training_rows(conn, int(event_open_ms)))
                except ValueError:
                    actual = -1
                report["archive_row_count_mismatches"] += int(actual != int(expected_rows))
                report["archive_digest_mismatches"] += int(not self._audit_event(conn, int(event_open_ms)))
                detail_count = self._detail_count(conn, int(event_open_ms))
                if str(state) == "SEALED" and detail_count > 0:
                    report["sealed_detail_mismatches"] += int(
                        not self._detail_matches_archive(conn, int(event_open_ms))
                    )
                if str(state) == "COMPACTED":
                    report["compacted_detail_rows"] += detail_count
            storage = _storage(conn)
        report.update(storage)
        raw_bytes = int(report["training_archive_uncompressed_bytes"])
        report["training_archive_compression_ratio"] = (
            float(report["training_archive_compressed_bytes"]) / raw_bytes
            if raw_bytes else 0.0
        )
        report["healthy"] = all(
            int(report[key]) == 0
            for key in (
                "definition_mismatch", "archive_digest_mismatches",
                "archive_row_count_mismatches", "sealed_detail_mismatches",
                "compacted_detail_rows",
            )
        ) and not report["missing_tables"]
        return report

    def status(self) -> dict[str, Any]:
        """Read-only lifecycle/storage status."""
        audit = self.audit()
        if audit.get("missing_tables"):
            return {
                **audit,
                "database": str(self.database.path),
                "database_bytes": self.database.path.stat().st_size if self.database.path.exists() else 0,
                "ledger_events": 0,
                "detailed_selection_events": 0,
                "protected_frozen_events": 0,
                "protected_recent_events": 0,
                "latest_ledger": None,
            }
        with self.database.connection() as conn:
            frozen, recent, events = self._protected_events(conn)
            detail_events = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_builds WHERE lab_version=?",
                (SELECTION_CONFIG.lab_version,),
            ).fetchone()[0])
            latest = conn.execute(
                "SELECT event_open_ms,state,archive_digest FROM research_event_ledger WHERE archive_version=? ORDER BY event_open_ms DESC LIMIT 1",
                (self.config.archive_version,),
            ).fetchone()
        return {
            **audit,
            "database": str(self.database.path),
            "database_bytes": self.database.path.stat().st_size if self.database.path.exists() else 0,
            "ledger_events": len(events),
            "detailed_selection_events": detail_events,
            "protected_frozen_events": len(frozen),
            "protected_recent_events": len(recent),
            "latest_ledger": None if latest is None else {
                "event_open_ms": int(latest[0]), "state": str(latest[1]), "archive_digest": str(latest[2])
            },
        }

    def maintain(self, *, seal_max_events: int | None = None, compact_max_events: int | None = None) -> dict[str, Any]:
        seal_report = self.seal(max_events=seal_max_events)
        compact_report = self.compact(max_events=compact_max_events)
        audit = self.audit()
        if not audit.get("healthy"):
            raise RuntimeError("NBOT_V382_RETENTION_AUDIT_FAILED")
        if int(audit["live_bytes"]) > self.config.hard_live_bytes:
            raise RuntimeError(
                f"NBOT_V382_LIVE_STORAGE_HARD_CAP_EXCEEDED:{audit['live_bytes']}"
            )
        return {
            "seal": seal_report,
            "compact": compact_report,
            "audit": audit,
            "hard_live_bytes": self.config.hard_live_bytes,
            "hard_live_bytes_ok": True,
            "authority": AUTHORITY,
        }
