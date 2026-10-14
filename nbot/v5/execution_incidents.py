"""E5 bounded durable incident journal for offline synthetic execution.

The wrapper never opens sockets, submits Binance orders, repairs source gaps,
inventories secrets or certifies a live feed. It only fail-closes toy fixtures.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from .execution_engine import PORTFOLIOS, canonical
from .execution_replay import ReplayRefused, SyntheticReplay

MAX_DISTINCT_INCIDENTS = 256
REASON_PATTERN = re.compile(r"^[A-Z0-9_]{3,96}$")


class SyntheticIncidentGuard:
    """Operator-readable incident record separate from durable paper outcomes."""

    def __init__(self, replay: SyntheticReplay):
        self.replay = replay
        self.engine = replay.engine
        self.engine.db.executescript("""
        CREATE TABLE IF NOT EXISTS execution_incidents(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_digest TEXT NOT NULL UNIQUE,
          event_id TEXT NOT NULL, observed_clock_ms INTEGER,
          reason TEXT NOT NULL, severity TEXT NOT NULL,
          grade TEXT NOT NULL CHECK(grade='SYNTHETIC'));
        CREATE TABLE IF NOT EXISTS incident_capacity(
          id INTEGER PRIMARY KEY CHECK(id=1), dropped_distinct INTEGER NOT NULL);
        INSERT OR IGNORE INTO incident_capacity(id,dropped_distinct) VALUES (1,0);
        CREATE TRIGGER IF NOT EXISTS incident_no_update BEFORE UPDATE ON execution_incidents
           BEGIN SELECT RAISE(ABORT,'immutable incident'); END;
        CREATE TRIGGER IF NOT EXISTS incident_no_delete BEFORE DELETE ON execution_incidents
           BEGIN SELECT RAISE(ABORT,'immutable incident'); END;
        """)

    def _record(self, reason: str, event_id: object, clock: object,
                *, fingerprint: str = "", kill_books: bool = False) -> dict:
        if not REASON_PATTERN.fullmatch(reason):
            reason = "UNCLASSIFIED_REPLAY_REJECTION"
        safe_id = event_id if isinstance(event_id, str) and re.fullmatch(
            r"[a-zA-Z0-9_-]{1,128}", event_id) else "MALFORMED_EVENT_ID"
        clock_int = clock if type(clock) is int and clock >= 0 else None
        digest = hashlib.sha256(canonical({"event": safe_id, "clock": clock_int,
                                            "reason": reason, "input_sha256": fingerprint})).hexdigest()
        with self.engine._tx() as c:
            prior = c.execute("SELECT id FROM execution_incidents WHERE event_digest=?",
                              (digest,)).fetchone()
            saturated = False
            if prior:
                incident_id = prior["id"]
            elif c.execute("SELECT COUNT(*) FROM execution_incidents").fetchone()[0] >= MAX_DISTINCT_INCIDENTS:
                c.execute("UPDATE incident_capacity SET dropped_distinct=dropped_distinct+1 WHERE id=1")
                incident_id = None
                saturated = True
            else:
                c.execute("""INSERT INTO execution_incidents
                    (event_digest,event_id,observed_clock_ms,reason,severity,grade)
                    VALUES (?,?,?,?,'HOLD','SYNTHETIC')""",
                    (digest, safe_id, clock_int, reason))
                incident_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            if kill_books:
                for book in PORTFOLIOS:
                    self.engine.kill_book(book)
        return {"incident_id": incident_id, "journal_at_capacity": saturated}

    def observe(self, frame: dict, proposals: list[dict]) -> dict:
        """One-shot offline wrapper; returns HOLD on an unsafe frame."""
        try:
            return self.replay.advance(frame, proposals)
        except ReplayRefused as exc:
            # Hash the request to identify repeats, never store raw proposals,
            # signatures or arbitrary market input in the incident journal.
            try:
                digest = hashlib.sha256(canonical({"frame": frame, "proposals": proposals})).hexdigest()
            except (ValueError, TypeError, OverflowError):
                digest = "NONCANONICAL_INPUT"
            info = self._record(str(exc),
                                frame.get("frame_id") if isinstance(frame, dict) else None,
                                frame.get("at_ms") if isinstance(frame, dict) else None,
                                fingerprint=digest)
            return {"status": "HOLD", "reason": str(exc),
                    "evidence_grade": "SYNTHETIC", "orders_created": 0,
                    **info}

    def check_source_timeout(self, synthetic_now_ms: int) -> dict:
        """Conservative synthetic heartbeat: no speculative closing of open books."""
        if type(synthetic_now_ms) is not int or synthetic_now_ms < 0:
            raise ValueError("invalid synthetic clock")
        last = self.engine.db.execute("SELECT MAX(at_ms) FROM replay_frames").fetchone()[0]
        if last is None:
            info = self._record("NO_REPLAY_EVIDENCE", "timeout-no-source", synthetic_now_ms)
            return {"status": "HOLD", "reason": "NO_REPLAY_EVIDENCE",
                    "pending_positions": "UNKNOWN", **info}
        if synthetic_now_ms < last:
            raise ValueError("regressed heartbeat clock")
        if synthetic_now_ms - last <= self.replay.rules.max_evidence_gap_ms:
            return {"status": "QUALIFIED_SYNTHETIC_RECENT_FRAME",
                    "grade": "SYNTHETIC_ONLY"}
        info = self._record("SOURCE_TIMEOUT", "timeout-source", synthetic_now_ms,
                            kill_books=True)
        positions = {book: len(self.engine.report(book)["open_positions"]) for book in PORTFOLIOS}
        return {"status": "HOLD", "reason": "SOURCE_TIMEOUT",
                "new_entries_blocked": True, "open_positions_unresolved": positions,
                "no_fabricated_exit": True, **info}

    def operator_snapshot(self) -> dict:
        c = self.engine.db
        recent = c.execute("""SELECT id,event_id,observed_clock_ms,reason,severity,grade
                              FROM execution_incidents ORDER BY id DESC LIMIT 20""").fetchall()
        return {"source": "SYNTHETIC_ONLY", "journaled_unique_incidents": c.execute(
                    "SELECT count(*) FROM execution_incidents").fetchone()[0],
                "dropped_distinct_at_capacity": c.execute(
                    "SELECT dropped_distinct FROM incident_capacity WHERE id=1").fetchone()[0],
                "recent": [dict(r) for r in recent],
                "books": {book: {
                    "killed": self.engine.report(book)["killed"],
                    "open_position_count": len(self.engine.report(book)["open_positions"]),
                } for book in PORTFOLIOS},
                "no_order_authority": True}
