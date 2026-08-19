"""SQLite raw-evidence store for NBOT V3.3.

Only point-in-time market evidence, collection provenance, funding-history
containers, and audit containers live here.  Research features, outcomes,
selection, recommendation, communication, and execution state belong to later
canonical roadmap phases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .config import ObservationConfig
from .models import Candle, FundingEvent, UniverseCapture, UniverseRow


REQUIRED_LIVE_CONTEXT_SOURCES = frozenset(
    {"exchange_info", "ticker_24h", "book_ticker", "premium_index"}
)

RAW_EVIDENCE_TABLES = (
    "metadata",
    "market_events",
    "candles_5m",
    "market_snapshots",
    "event_provenance",
    "universe_membership",
    "source_captures",
    "collection_attempts",
    "funding_events",
    "funding_sync_ranges",
    "audit_runs",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_events (
    event_open_ms INTEGER PRIMARY KEY,
    event_close_ms INTEGER NOT NULL,
    captured_at_ms INTEGER NOT NULL,
    requested_symbols INTEGER NOT NULL CHECK (requested_symbols > 0),
    stored_symbols INTEGER NOT NULL CHECK (stored_symbols > 0),
    error_count INTEGER NOT NULL CHECK (error_count = 0),
    status TEXT NOT NULL CHECK (status = 'COMPLETE'),
    collector_version TEXT NOT NULL,
    capture_duration_ms INTEGER NOT NULL CHECK (capture_duration_ms >= 0)
);

CREATE TABLE IF NOT EXISTS candles_5m (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL,
    close_time_ms INTEGER NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    base_volume REAL NOT NULL,
    quote_volume REAL NOT NULL,
    trade_count INTEGER NOT NULL,
    taker_buy_base_volume REAL NOT NULL,
    taker_buy_quote_volume REAL NOT NULL,
    PRIMARY KEY (event_open_ms, symbol),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    universe_rank INTEGER NOT NULL,
    quote_volume_24h_usd REAL NOT NULL,
    bid_price REAL NOT NULL,
    ask_price REAL NOT NULL,
    spread_pct REAL NOT NULL,
    mark_price REAL,
    index_price REAL,
    funding_rate REAL,
    next_funding_time_ms INTEGER,
    captured_at_ms INTEGER NOT NULL,
    PRIMARY KEY (event_open_ms, symbol),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_provenance (
    event_open_ms INTEGER PRIMARY KEY,
    evidence_mode TEXT NOT NULL,
    context_complete INTEGER NOT NULL CHECK (context_complete IN (0, 1)),
    membership_quality TEXT NOT NULL,
    source_universe_event_open_ms INTEGER,
    server_time_before_ms INTEGER,
    server_time_after_ms INTEGER,
    capture_started_at_ms INTEGER NOT NULL,
    capture_finished_at_ms INTEGER NOT NULL,
    recovery_reason TEXT,
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS universe_membership (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    universe_rank INTEGER NOT NULL,
    membership_quality TEXT NOT NULL,
    source_universe_event_open_ms INTEGER,
    PRIMARY KEY (event_open_ms, symbol),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS source_captures (
    event_open_ms INTEGER NOT NULL,
    source TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL,
    finished_at_ms INTEGER NOT NULL,
    PRIMARY KEY (event_open_ms, source),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collection_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_open_ms INTEGER NOT NULL,
    attempted_at_ms INTEGER NOT NULL,
    requested_symbols INTEGER NOT NULL CHECK (requested_symbols >= 0),
    stored_symbols INTEGER NOT NULL CHECK (stored_symbols >= 0),
    error_count INTEGER NOT NULL CHECK (error_count >= 0),
    result TEXT NOT NULL,
    capture_duration_ms INTEGER NOT NULL CHECK (capture_duration_ms >= 0),
    detail TEXT
);

CREATE TABLE IF NOT EXISTS funding_events (
    symbol TEXT NOT NULL,
    funding_time_ms INTEGER NOT NULL,
    funding_rate REAL NOT NULL,
    mark_price REAL,
    ingested_at_ms INTEGER NOT NULL,
    PRIMARY KEY (symbol, funding_time_ms)
);

CREATE TABLE IF NOT EXISTS funding_sync_ranges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    captured_at_ms INTEGER NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    collector_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at_ms INTEGER NOT NULL,
    database_bytes INTEGER NOT NULL CHECK (database_bytes >= 0),
    wal_bytes INTEGER NOT NULL CHECK (wal_bytes >= 0),
    complete_events INTEGER NOT NULL CHECK (complete_events >= 0),
    research_ready_events INTEGER NOT NULL CHECK (research_ready_events >= 0),
    report_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_time
    ON candles_5m(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time
    ON market_snapshots(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_membership_symbol_time
    ON universe_membership(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_attempts_event_time
    ON collection_attempts(event_open_ms, attempted_at_ms);
CREATE INDEX IF NOT EXISTS idx_funding_symbol_time
    ON funding_events(symbol, funding_time_ms);
"""


@dataclass(frozen=True)
class FundingCoverage:
    """Auditable coverage of a requested funding-history time range."""

    start_ms: int
    end_ms: int
    covered_ms: int
    total_ms: int
    coverage_pct: float
    complete: bool


class EvidenceDatabaseError(RuntimeError):
    """Raw evidence cannot be initialized or persisted without ambiguity."""


class ClosingConnection(sqlite3.Connection):
    """SQLite connection whose context-manager exit also closes the handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class EvidenceDatabase:
    """Observation-owned SQLite store for atomic raw market evidence."""

    def __init__(self, config: ObservationConfig) -> None:
        config.validate()
        self.config = config
        self.path = Path(config.database_path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0, factory=ClosingConnection)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def connection(self) -> sqlite3.Connection:
        """Open a configured connection for deterministic inspection/tests."""

        return self._connect()

    def initialize(self) -> None:
        expected = {
            "schema_version": self.config.schema_version,
            "role": "OBSERVATION",
            "market_environment": self.config.market_environment,
        }
        with self._connect() as conn:
            metadata_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'"
            ).fetchone() is not None
            existing: dict[str, str] = {}
            if metadata_exists:
                try:
                    existing = {
                        str(key): str(value)
                        for key, value in conn.execute("SELECT key, value FROM metadata")
                    }
                except sqlite3.Error as exc:
                    raise EvidenceDatabaseError(
                        "NBOT_OBSERVATION_DB_METADATA_UNREADABLE"
                    ) from exc
                for key, value in expected.items():
                    present = existing.get(key)
                    if present is not None and present != value:
                        raise EvidenceDatabaseError(
                            f"NBOT_OBSERVATION_DB_METADATA_MISMATCH:{key}:{present}:{value}"
                        )

            conn.executescript(SCHEMA)
            for key, value in expected.items():
                conn.execute(
                    "INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)",
                    (key, value),
                )

    def metadata(self) -> dict[str, str]:
        self.initialize()
        with self._connect() as conn:
            return {
                str(key): str(value)
                for key, value in conn.execute("SELECT key, value FROM metadata ORDER BY key")
            }

    def has_complete_event(self, event_open_ms: int) -> bool:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM market_events WHERE event_open_ms=? AND status='COMPLETE'",
                (int(event_open_ms),),
            ).fetchone()
        return row is not None

    @staticmethod
    def _bounded_detail(detail: str | None) -> str | None:
        if detail is None:
            return None
        value = str(detail).strip()
        return value[:2048] if value else None

    def record_collection_attempt(
        self,
        *,
        event_open_ms: int,
        attempted_at_ms: int,
        requested_symbols: int,
        stored_symbols: int,
        error_count: int,
        result: str,
        capture_duration_ms: int,
        detail: str | None = None,
    ) -> None:
        self.initialize()
        values = (
            int(event_open_ms),
            int(attempted_at_ms),
            int(requested_symbols),
            int(stored_symbols),
            int(error_count),
            str(result).strip(),
            int(capture_duration_ms),
        )
        if values[0] < 0 or values[1] < 0:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_COLLECTION_ATTEMPT_TIME_INVALID")
        if min(values[2], values[3], values[4], values[6]) < 0 or not values[5]:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_COLLECTION_ATTEMPT_INVALID")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collection_attempts(
                    event_open_ms, attempted_at_ms, requested_symbols, stored_symbols,
                    error_count, result, capture_duration_ms, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values + (self._bounded_detail(detail),),
            )

    def _live_validation_error(
        self,
        *,
        event_open_ms: int,
        universe_capture: UniverseCapture,
        candles: Mapping[str, Candle],
        candle_errors: Mapping[str, str],
        capture_started_at_ms: int,
        capture_finished_at_ms: int,
        server_time_before_ms: int,
        server_time_after_ms: int,
    ) -> str | None:
        interval = self.config.candle_interval_ms
        event_close_ms = event_open_ms + interval - 1
        if event_open_ms < 0 or event_open_ms % interval != 0:
            return "event open is not aligned to canonical 5-minute clock"
        if capture_finished_at_ms < capture_started_at_ms:
            return "capture finish precedes capture start"
        if server_time_before_ms < 0 or server_time_after_ms < server_time_before_ms:
            return "server-time provenance is invalid"
        rows = tuple(universe_capture.rows)
        if not rows:
            return "point-in-time universe is empty"
        symbols = tuple(row.symbol for row in rows)
        if candle_errors:
            return "candle errors present: " + "; ".join(
                f"{symbol}={candle_errors[symbol]}" for symbol in sorted(candle_errors)
            )
        if set(candles) != set(symbols):
            return "canonical candle set differs from point-in-time universe"
        sources = {capture.source for capture in universe_capture.source_captures}
        if sources != REQUIRED_LIVE_CONTEXT_SOURCES:
            return "point-in-time source capture set is incomplete"
        for capture in universe_capture.source_captures:
            if (
                capture.started_at_ms < capture_started_at_ms
                or capture.finished_at_ms > capture_finished_at_ms
            ):
                return f"source capture outside event capture bounds: {capture.source}"
        for symbol in symbols:
            candle = candles[symbol]
            if candle.symbol != symbol or candle.open_time_ms != event_open_ms:
                return f"canonical candle identity mismatch: {symbol}"
            if candle.close_time_ms != event_close_ms:
                return f"canonical candle close mismatch: {symbol}"
        return None

    @staticmethod
    def _insert_candle(conn: sqlite3.Connection, event_open_ms: int, candle: Candle) -> None:
        conn.execute(
            """
            INSERT INTO candles_5m VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_open_ms,
                candle.symbol,
                candle.open_time_ms,
                candle.close_time_ms,
                candle.open_price,
                candle.high_price,
                candle.low_price,
                candle.close_price,
                candle.base_volume,
                candle.quote_volume,
                candle.trade_count,
                candle.taker_buy_base_volume,
                candle.taker_buy_quote_volume,
            ),
        )

    @staticmethod
    def _insert_snapshot(
        conn: sqlite3.Connection,
        event_open_ms: int,
        row: UniverseRow,
        context_captured_at_ms: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO market_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_open_ms,
                row.symbol,
                row.universe_rank,
                row.quote_volume_24h_usd,
                row.bid_price,
                row.ask_price,
                row.spread_pct,
                row.mark_price,
                row.index_price,
                row.funding_rate,
                row.next_funding_time_ms,
                context_captured_at_ms,
            ),
        )

    def store_live_event(
        self,
        *,
        event_open_ms: int,
        universe_capture: UniverseCapture,
        candles: Mapping[str, Candle],
        candle_errors: Mapping[str, str],
        capture_started_at_ms: int,
        capture_finished_at_ms: int,
        server_time_before_ms: int,
        server_time_after_ms: int,
    ) -> str:
        """Persist one complete LIVE/Testnet-public event atomically.

        Partial or inconsistent captures are recorded only as collection
        attempts.  Once a complete canonical event exists, a repeated call is
        audit-recorded but never rewrites the stored point-in-time evidence.
        """

        self.initialize()
        event_open_ms = int(event_open_ms)
        started = int(capture_started_at_ms)
        finished = int(capture_finished_at_ms)
        requested = len(universe_capture.rows)
        stored = len(candles)
        errors = len(candle_errors)
        duration = max(0, finished - started)

        if self.has_complete_event(event_open_ms):
            self.record_collection_attempt(
                event_open_ms=event_open_ms,
                attempted_at_ms=max(0, finished),
                requested_symbols=requested,
                stored_symbols=stored,
                error_count=errors,
                result="ALREADY_COMPLETE",
                capture_duration_ms=duration,
                detail="canonical event already exists; raw evidence not rewritten",
            )
            return "ALREADY_COMPLETE"

        validation_error = self._live_validation_error(
            event_open_ms=event_open_ms,
            universe_capture=universe_capture,
            candles=candles,
            candle_errors=candle_errors,
            capture_started_at_ms=started,
            capture_finished_at_ms=finished,
            server_time_before_ms=int(server_time_before_ms),
            server_time_after_ms=int(server_time_after_ms),
        )
        if validation_error is not None:
            self.record_collection_attempt(
                event_open_ms=max(0, event_open_ms),
                attempted_at_ms=max(0, finished),
                requested_symbols=requested,
                stored_symbols=stored,
                error_count=max(errors, 1),
                result="PARTIAL_REJECTED",
                capture_duration_ms=duration,
                detail=validation_error,
            )
            return "PARTIAL_REJECTED"

        event_close_ms = event_open_ms + self.config.candle_interval_ms - 1
        context_captured_at_ms = max(
            capture.finished_at_ms for capture in universe_capture.source_captures
        )

        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute(
                    "SELECT 1 FROM market_events WHERE event_open_ms=?",
                    (event_open_ms,),
                ).fetchone() is not None:
                    raise EvidenceDatabaseError("NBOT_OBSERVATION_EVENT_RACE_ALREADY_STORED")
                conn.execute(
                    """
                    INSERT INTO market_events(
                        event_open_ms, event_close_ms, captured_at_ms,
                        requested_symbols, stored_symbols, error_count,
                        status, collector_version, capture_duration_ms
                    ) VALUES (?, ?, ?, ?, ?, 0, 'COMPLETE', ?, ?)
                    """,
                    (
                        event_open_ms,
                        event_close_ms,
                        finished,
                        requested,
                        requested,
                        self.config.collector_version,
                        duration,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO event_provenance(
                        event_open_ms, evidence_mode, context_complete,
                        membership_quality, source_universe_event_open_ms,
                        server_time_before_ms, server_time_after_ms,
                        capture_started_at_ms, capture_finished_at_ms, recovery_reason
                    ) VALUES (?, 'LIVE_POINT_IN_TIME', 1, 'POINT_IN_TIME', ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        event_open_ms,
                        event_open_ms,
                        int(server_time_before_ms),
                        int(server_time_after_ms),
                        started,
                        finished,
                    ),
                )
                for capture in universe_capture.source_captures:
                    conn.execute(
                        "INSERT INTO source_captures VALUES (?, ?, ?, ?)",
                        (
                            event_open_ms,
                            capture.source,
                            capture.started_at_ms,
                            capture.finished_at_ms,
                        ),
                    )
                for row in universe_capture.rows:
                    candle = candles[row.symbol]
                    self._insert_candle(conn, event_open_ms, candle)
                    self._insert_snapshot(conn, event_open_ms, row, context_captured_at_ms)
                    conn.execute(
                        """
                        INSERT INTO universe_membership(
                            event_open_ms, symbol, universe_rank,
                            membership_quality, source_universe_event_open_ms
                        ) VALUES (?, ?, ?, 'POINT_IN_TIME', ?)
                        """,
                        (event_open_ms, row.symbol, row.universe_rank, event_open_ms),
                    )
                conn.execute(
                    """
                    INSERT INTO collection_attempts(
                        event_open_ms, attempted_at_ms, requested_symbols, stored_symbols,
                        error_count, result, capture_duration_ms, detail
                    ) VALUES (?, ?, ?, ?, 0, 'COMPLETE', ?, NULL)
                    """,
                    (event_open_ms, finished, requested, requested, duration),
                )
        except EvidenceDatabaseError:
            raise
        except sqlite3.Error as exc:
            self.record_collection_attempt(
                event_open_ms=event_open_ms,
                attempted_at_ms=finished,
                requested_symbols=requested,
                stored_symbols=stored,
                error_count=max(errors, 1),
                result="STORE_FAILED",
                capture_duration_ms=duration,
                detail=f"{type(exc).__name__}: {exc}",
            )
            raise EvidenceDatabaseError("NBOT_OBSERVATION_ATOMIC_EVENT_STORE_FAILED") from exc

        return "COMPLETE"

    def point_in_time_universe_before(
        self, event_open_ms: int
    ) -> tuple[int, tuple[tuple[str, int], ...]] | None:
        """Return the latest genuinely point-in-time universe before an event."""

        self.initialize()
        target = int(event_open_ms)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(event_open_ms)
                FROM event_provenance
                WHERE event_open_ms < ?
                  AND context_complete=1
                  AND membership_quality='POINT_IN_TIME'
                """,
                (target,),
            ).fetchone()
            source = None if row is None else row[0]
            if source is None:
                return None
            membership = tuple(
                (str(symbol), int(rank))
                for symbol, rank in conn.execute(
                    """
                    SELECT symbol, universe_rank
                    FROM universe_membership
                    WHERE event_open_ms=? AND membership_quality='POINT_IN_TIME'
                    ORDER BY universe_rank, symbol
                    """,
                    (int(source),),
                )
            )
        if not membership:
            return None
        return int(source), membership

    def missing_event_opens(self, latest_open_ms: int) -> list[int]:
        """Return deterministic candle-clock gaps from first stored event onward."""

        self.initialize()
        latest = int(latest_open_ms)
        interval = self.config.candle_interval_ms
        if latest < 0 or latest % interval:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_GAP_BOUNDARY_INVALID")
        with self._connect() as conn:
            earliest = conn.execute(
                "SELECT MIN(event_open_ms) FROM market_events WHERE status='COMPLETE'"
            ).fetchone()[0]
            if earliest is None or latest < int(earliest):
                return []
            present = {
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT event_open_ms
                    FROM market_events
                    WHERE status='COMPLETE' AND event_open_ms BETWEEN ? AND ?
                    """,
                    (int(earliest), latest),
                )
            }
        return [
            value
            for value in range(int(earliest), latest + 1, interval)
            if value not in present
        ]

    def store_recovered_event(
        self,
        *,
        event_open_ms: int,
        source_universe_event_open_ms: int,
        membership: Sequence[tuple[str, int]],
        candles: Mapping[str, Candle],
        candle_errors: Mapping[str, str],
        captured_at_ms: int,
        capture_duration_ms: int,
        recovery_reason: str,
    ) -> str:
        """Persist candle-only recovery without fabricating historical context.

        Recovered rows inherit only a previously observed point-in-time universe.
        They intentionally contain no market snapshots or source captures and are
        permanently marked context-incomplete, so later research cannot silently
        treat them as point-in-time complete evidence.
        """

        self.initialize()
        event_open = int(event_open_ms)
        source_open = int(source_universe_event_open_ms)
        captured = int(captured_at_ms)
        duration = int(capture_duration_ms)
        members = tuple((str(symbol), int(rank)) for symbol, rank in membership)
        requested = len(members)
        stored = len(candles)
        errors = {str(key): str(value) for key, value in candle_errors.items()}

        if self.has_complete_event(event_open):
            self.record_collection_attempt(
                event_open_ms=max(0, event_open),
                attempted_at_ms=max(0, captured),
                requested_symbols=requested,
                stored_symbols=stored,
                error_count=len(errors),
                result="ALREADY_COMPLETE",
                capture_duration_ms=max(0, duration),
                detail="canonical event already exists; recovery did not rewrite evidence",
            )
            return "ALREADY_COMPLETE"

        validation_error: str | None = None
        interval = self.config.candle_interval_ms
        symbols = tuple(symbol for symbol, _rank in members)
        ranks = tuple(rank for _symbol, rank in members)
        event_close = event_open + interval - 1
        if event_open < 0 or event_open % interval:
            validation_error = "recovery event open is not aligned"
        elif source_open < 0 or source_open >= event_open:
            validation_error = "recovery source universe must precede event"
        elif captured < 0 or duration < 0:
            validation_error = "recovery capture timing is invalid"
        elif requested == 0:
            validation_error = "recovery inherited universe is empty"
        elif len(set(symbols)) != requested:
            validation_error = "recovery inherited universe has duplicate symbols"
        elif ranks != tuple(range(1, requested + 1)):
            validation_error = "recovery inherited universe ranks are non-deterministic"
        elif errors:
            validation_error = "historical candle errors present: " + "; ".join(
                f"{symbol}={errors[symbol]}" for symbol in sorted(errors)
            )
        elif set(candles) != set(symbols):
            validation_error = "recovered candle set differs from inherited universe"
        else:
            for symbol in symbols:
                candle = candles[symbol]
                if candle.symbol != symbol or candle.open_time_ms != event_open:
                    validation_error = f"recovered candle identity mismatch: {symbol}"
                    break
                if candle.close_time_ms != event_close:
                    validation_error = f"recovered candle close mismatch: {symbol}"
                    break

        if validation_error is not None:
            self.record_collection_attempt(
                event_open_ms=max(0, event_open),
                attempted_at_ms=max(0, captured),
                requested_symbols=requested,
                stored_symbols=stored,
                error_count=max(1, len(errors), requested - stored),
                result="RECOVERY_PARTIAL_REJECTED",
                capture_duration_ms=max(0, duration),
                detail=validation_error,
            )
            return "PARTIAL_REJECTED"

        reason = self._bounded_detail(recovery_reason)
        if reason is None:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_RECOVERY_REASON_REQUIRED")

        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                source_row = conn.execute(
                    """
                    SELECT context_complete, membership_quality
                    FROM event_provenance
                    WHERE event_open_ms=?
                    """,
                    (source_open,),
                ).fetchone()
                if source_row != (1, "POINT_IN_TIME"):
                    raise EvidenceDatabaseError(
                        "NBOT_OBSERVATION_RECOVERY_SOURCE_NOT_POINT_IN_TIME"
                    )
                source_membership = tuple(
                    (str(symbol), int(rank))
                    for symbol, rank in conn.execute(
                        """
                        SELECT symbol, universe_rank
                        FROM universe_membership
                        WHERE event_open_ms=? AND membership_quality='POINT_IN_TIME'
                        ORDER BY universe_rank, symbol
                        """,
                        (source_open,),
                    )
                )
                if source_membership != members:
                    raise EvidenceDatabaseError(
                        "NBOT_OBSERVATION_RECOVERY_MEMBERSHIP_SOURCE_MISMATCH"
                    )
                if conn.execute(
                    "SELECT 1 FROM market_events WHERE event_open_ms=?",
                    (event_open,),
                ).fetchone() is not None:
                    raise EvidenceDatabaseError(
                        "NBOT_OBSERVATION_RECOVERY_EVENT_RACE_ALREADY_STORED"
                    )

                conn.execute(
                    """
                    INSERT INTO market_events(
                        event_open_ms, event_close_ms, captured_at_ms,
                        requested_symbols, stored_symbols, error_count,
                        status, collector_version, capture_duration_ms
                    ) VALUES (?, ?, ?, ?, ?, 0, 'COMPLETE', ?, ?)
                    """,
                    (
                        event_open,
                        event_close,
                        captured,
                        requested,
                        requested,
                        self.config.collector_version,
                        duration,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO event_provenance(
                        event_open_ms, evidence_mode, context_complete,
                        membership_quality, source_universe_event_open_ms,
                        server_time_before_ms, server_time_after_ms,
                        capture_started_at_ms, capture_finished_at_ms, recovery_reason
                    ) VALUES (?, 'BACKFILL_CANDLE_ONLY', 0, 'INHERITED', ?, NULL, NULL, ?, ?, ?)
                    """,
                    (
                        event_open,
                        source_open,
                        max(0, captured - duration),
                        captured,
                        reason,
                    ),
                )
                for symbol, rank in members:
                    self._insert_candle(conn, event_open, candles[symbol])
                    conn.execute(
                        """
                        INSERT INTO universe_membership(
                            event_open_ms, symbol, universe_rank,
                            membership_quality, source_universe_event_open_ms
                        ) VALUES (?, ?, ?, 'INHERITED', ?)
                        """,
                        (event_open, symbol, rank, source_open),
                    )
                conn.execute(
                    """
                    INSERT INTO collection_attempts(
                        event_open_ms, attempted_at_ms, requested_symbols, stored_symbols,
                        error_count, result, capture_duration_ms, detail
                    ) VALUES (?, ?, ?, ?, 0, 'RECOVERED_CANDLES_ONLY', ?, ?)
                    """,
                    (event_open, captured, requested, requested, duration, reason),
                )
        except EvidenceDatabaseError:
            raise
        except sqlite3.Error as exc:
            self.record_collection_attempt(
                event_open_ms=event_open,
                attempted_at_ms=captured,
                requested_symbols=requested,
                stored_symbols=stored,
                error_count=max(1, len(errors)),
                result="RECOVERY_STORE_FAILED",
                capture_duration_ms=duration,
                detail=f"{type(exc).__name__}: {exc}",
            )
            raise EvidenceDatabaseError(
                "NBOT_OBSERVATION_ATOMIC_RECOVERY_STORE_FAILED"
            ) from exc

        return "COMPLETE"

    def funding_sync_bounds(self) -> tuple[int | None, int | None]:
        """Return the earliest and latest explicitly synced funding-history bounds."""

        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MIN(start_ms), MAX(end_ms) FROM funding_sync_ranges"
            ).fetchone()
        return (
            None if row[0] is None else int(row[0]),
            None if row[1] is None else int(row[1]),
        )

    def funding_sync_due(self, now_ms: int) -> bool:
        """Return whether the configured funding-history sync interval has elapsed."""

        now = int(now_ms)
        if now < 0:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_SYNC_TIME_INVALID")
        self.initialize()
        with self._connect() as conn:
            last = conn.execute(
                "SELECT MAX(captured_at_ms) FROM funding_sync_ranges"
            ).fetchone()[0]
        if last is None:
            return True
        last_ms = int(last)
        if now < last_ms:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_SYNC_CLOCK_REVERSED")
        return now - last_ms >= self.config.funding_sync_interval_seconds * 1000

    def funding_sync_start_ms(self) -> int | None:
        """Return the first millisecond not yet covered by the forward sync cursor."""

        self.initialize()
        with self._connect() as conn:
            synced = conn.execute(
                "SELECT MAX(end_ms) FROM funding_sync_ranges"
            ).fetchone()[0]
            if synced is not None:
                return int(synced) + 1
            earliest = conn.execute(
                "SELECT MIN(event_open_ms) FROM market_events WHERE status='COMPLETE'"
            ).fetchone()[0]
        return None if earliest is None else int(earliest)

    @staticmethod
    def _same_optional_float(left: float | None, right: float | None) -> bool:
        if left is None or right is None:
            return left is None and right is None
        return float(left) == float(right)

    def store_funding_sync(
        self,
        *,
        start_ms: int,
        end_ms: int,
        events: Sequence[FundingEvent],
        captured_at_ms: int,
    ) -> int:
        """Atomically persist objective funding events and the proven queried range.

        Empty ranges are persisted too because a successful zero-row query is
        still evidence that the requested interval was checked. Existing funding
        events are immutable: an identical re-fetch is accepted, while a changed
        rate/mark price for the same symbol/timestamp fails closed.
        """

        start = int(start_ms)
        end = int(end_ms)
        captured = int(captured_at_ms)
        if start < 0 or end < start or captured < 0:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_SYNC_RANGE_INVALID")

        normalized = tuple(
            sorted(tuple(events), key=lambda row: (row.funding_time_ms, row.symbol))
        )
        keys: set[tuple[str, int]] = set()
        for event in normalized:
            if not isinstance(event, FundingEvent):
                raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_EVENT_INVALID")
            if not start <= event.funding_time_ms <= end:
                raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_EVENT_OUTSIDE_SYNC_RANGE")
            key = (event.symbol, event.funding_time_ms)
            if key in keys:
                raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_EVENT_DUPLICATE")
            keys.add(key)

        self.initialize()
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                for event in normalized:
                    existing = conn.execute(
                        """
                        SELECT funding_rate, mark_price
                        FROM funding_events
                        WHERE symbol=? AND funding_time_ms=?
                        """,
                        (event.symbol, event.funding_time_ms),
                    ).fetchone()
                    if existing is None:
                        conn.execute(
                            """
                            INSERT INTO funding_events(
                                symbol, funding_time_ms, funding_rate, mark_price, ingested_at_ms
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                event.symbol,
                                event.funding_time_ms,
                                event.funding_rate,
                                event.mark_price,
                                captured,
                            ),
                        )
                    elif (
                        float(existing[0]) != event.funding_rate
                        or not self._same_optional_float(existing[1], event.mark_price)
                    ):
                        raise EvidenceDatabaseError(
                            "NBOT_OBSERVATION_FUNDING_EVENT_CONFLICT:"
                            f"{event.symbol}:{event.funding_time_ms}"
                        )

                conn.execute(
                    """
                    INSERT INTO funding_sync_ranges(
                        start_ms, end_ms, captured_at_ms, row_count, collector_version
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (start, end, captured, len(normalized), self.config.collector_version),
                )
        except EvidenceDatabaseError:
            raise
        except sqlite3.Error as exc:
            raise EvidenceDatabaseError(
                "NBOT_OBSERVATION_ATOMIC_FUNDING_SYNC_STORE_FAILED"
            ) from exc
        return len(normalized)

    def funding_coverage(self, start_ms: int, end_ms: int) -> FundingCoverage:
        """Return merged explicit sync-range coverage for an inclusive interval."""

        start = int(start_ms)
        end = int(end_ms)
        if start < 0 or end < start:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_FUNDING_COVERAGE_RANGE_INVALID")
        self.initialize()
        with self._connect() as conn:
            ranges = tuple(
                conn.execute(
                    """
                    SELECT start_ms, end_ms
                    FROM funding_sync_ranges
                    WHERE end_ms >= ? AND start_ms <= ?
                    ORDER BY start_ms, end_ms
                    """,
                    (start, end),
                )
            )

        merged: list[list[int]] = []
        for raw_start, raw_end in ranges:
            left = max(start, int(raw_start))
            right = min(end, int(raw_end))
            if right < left:
                continue
            if not merged or left > merged[-1][1] + 1:
                merged.append([left, right])
            else:
                merged[-1][1] = max(merged[-1][1], right)

        covered = sum(right - left + 1 for left, right in merged)
        total = end - start + 1
        return FundingCoverage(
            start_ms=start,
            end_ms=end,
            covered_ms=covered,
            total_ms=total,
            coverage_pct=(covered * 100.0 / total),
            complete=covered == total,
        )

    @staticmethod
    def _canonical_row_bytes(table: str, row: Sequence[object]) -> bytes:
        payload = json.dumps(
            [table, *row],
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=True,
        )
        return payload.encode("utf-8") + b"\n"

    @classmethod
    def _evidence_digest(cls, conn: sqlite3.Connection) -> str:
        """Hash logical raw evidence in a stable table/key order.

        Audit rows are deliberately excluded so recording an audit cannot change
        the identity of the evidence being audited.
        """

        queries = (
            ("metadata", "SELECT key, value FROM metadata ORDER BY key"),
            (
                "market_events",
                "SELECT * FROM market_events ORDER BY event_open_ms",
            ),
            (
                "candles_5m",
                "SELECT * FROM candles_5m ORDER BY event_open_ms, symbol",
            ),
            (
                "market_snapshots",
                "SELECT * FROM market_snapshots ORDER BY event_open_ms, symbol",
            ),
            (
                "event_provenance",
                "SELECT * FROM event_provenance ORDER BY event_open_ms",
            ),
            (
                "universe_membership",
                "SELECT * FROM universe_membership "
                "ORDER BY event_open_ms, universe_rank, symbol",
            ),
            (
                "source_captures",
                "SELECT * FROM source_captures ORDER BY event_open_ms, source",
            ),
            (
                "collection_attempts",
                "SELECT * FROM collection_attempts ORDER BY id",
            ),
            (
                "funding_events",
                "SELECT * FROM funding_events ORDER BY funding_time_ms, symbol",
            ),
            (
                "funding_sync_ranges",
                "SELECT * FROM funding_sync_ranges ORDER BY id",
            ),
        )
        digest = hashlib.sha256()
        for table, query in queries:
            for row in conn.execute(query):
                digest.update(cls._canonical_row_bytes(table, tuple(row)))
        return digest.hexdigest()

    @staticmethod
    def _merged_coverage_ms(
        conn: sqlite3.Connection, start_ms: int, end_ms: int
    ) -> int:
        ranges = tuple(
            conn.execute(
                """
                SELECT start_ms, end_ms
                FROM funding_sync_ranges
                WHERE end_ms >= ? AND start_ms <= ?
                ORDER BY start_ms, end_ms
                """,
                (start_ms, end_ms),
            )
        )
        merged: list[list[int]] = []
        for raw_start, raw_end in ranges:
            left = max(start_ms, int(raw_start))
            right = min(end_ms, int(raw_end))
            if right < left:
                continue
            if not merged or left > merged[-1][1] + 1:
                merged.append([left, right])
            else:
                merged[-1][1] = max(merged[-1][1], right)
        return sum(right - left + 1 for left, right in merged)

    def integrity_check(self) -> dict[str, object]:
        """Run SQLite integrity and foreign-key checks without mutating evidence."""

        self.initialize()
        try:
            with self._connect() as conn:
                rows = tuple(str(row[0]) for row in conn.execute("PRAGMA integrity_check"))
                foreign_keys = tuple(tuple(row) for row in conn.execute("PRAGMA foreign_key_check"))
        except sqlite3.Error as exc:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_DB_INTEGRITY_CHECK_FAILED") from exc
        return {
            "integrity": "ok" if rows == ("ok",) else "; ".join(rows),
            "foreign_key_violations": len(foreign_keys),
            "ok": rows == ("ok",) and not foreign_keys,
        }

    def checkpoint(self) -> tuple[int, int, int]:
        """Checkpoint and truncate the WAL, returning SQLite's result tuple."""

        self.initialize()
        try:
            with self._connect() as conn:
                row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        except sqlite3.Error as exc:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_DB_CHECKPOINT_FAILED") from exc
        if row is None or len(row) != 3:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_DB_CHECKPOINT_RESULT_INVALID")
        return int(row[0]), int(row[1]), int(row[2])

    def backup(self, destination: Path | None = None) -> Path:
        """Create and verify a consistent SQLite backup of the evidence store."""

        self.initialize()
        if destination is None:
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            destination = self.config.backup_directory / f"observer-{stamp}.db"
        target_path = Path(destination)
        if target_path.resolve() == self.path.resolve():
            raise EvidenceDatabaseError("NBOT_OBSERVATION_BACKUP_TARGET_IS_SOURCE")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as source:
                target = sqlite3.connect(target_path)
                try:
                    source.backup(target)
                finally:
                    target.close()
            with sqlite3.connect(target_path) as verify:
                rows = tuple(str(row[0]) for row in verify.execute("PRAGMA integrity_check"))
                foreign_keys = tuple(verify.execute("PRAGMA foreign_key_check"))
                metadata = {
                    str(key): str(value)
                    for key, value in verify.execute("SELECT key, value FROM metadata")
                }
            expected = {
                "schema_version": self.config.schema_version,
                "role": "OBSERVATION",
                "market_environment": self.config.market_environment,
            }
            if rows != ("ok",) or foreign_keys or any(
                metadata.get(key) != value for key, value in expected.items()
            ):
                raise EvidenceDatabaseError("NBOT_OBSERVATION_BACKUP_VERIFICATION_FAILED")
        except EvidenceDatabaseError:
            raise
        except sqlite3.Error as exc:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_BACKUP_FAILED") from exc
        return target_path

    def audit(self, *, now_ms: int | None = None, record: bool = False) -> dict[str, object]:
        """Audit raw evidence deterministically and optionally persist the report.

        `evidence_digest` hashes logical raw evidence only. `audit_digest` hashes
        the semantic audit result for the supplied clock. File/WAL byte sizes are
        reported for operations but intentionally excluded from `audit_digest`.
        """

        self.initialize()
        now = int(time.time() * 1000) if now_ms is None else int(now_ms)
        if now < 0:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_AUDIT_TIME_INVALID")
        db_bytes = self.path.stat().st_size if self.path.exists() else 0
        wal_path = Path(str(self.path) + "-wal")
        wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
        interval = self.config.candle_interval_ms
        settle_ms = int(self.config.capture_settle_seconds * 1000)

        try:
            with self._connect() as conn:
                integrity_rows = tuple(
                    str(row[0]) for row in conn.execute("PRAGMA integrity_check")
                )
                foreign_key_violations = len(
                    tuple(conn.execute("PRAGMA foreign_key_check"))
                )
                event_opens = tuple(
                    int(row[0])
                    for row in conn.execute(
                        "SELECT event_open_ms FROM market_events "
                        "WHERE status='COMPLETE' ORDER BY event_open_ms"
                    )
                )
                complete_events = len(event_opens)
                research_ready_events = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM event_provenance
                        WHERE context_complete=1 AND membership_quality='POINT_IN_TIME'
                        """
                    ).fetchone()[0]
                )
                context_incomplete_events = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM event_provenance WHERE context_complete=0"
                    ).fetchone()[0]
                )
                recovered_events = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM event_provenance "
                        "WHERE evidence_mode='BACKFILL_CANDLE_ONLY'"
                    ).fetchone()[0]
                )
                recovered_context_conflicts = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM event_provenance
                        WHERE evidence_mode='BACKFILL_CANDLE_ONLY'
                          AND (context_complete != 0 OR membership_quality != 'INHERITED')
                        """
                    ).fetchone()[0]
                )
                recovered_fabricated_context_rows = int(
                    conn.execute(
                        """
                        SELECT
                          (SELECT COUNT(*) FROM market_snapshots s
                           JOIN event_provenance p USING(event_open_ms)
                           WHERE p.evidence_mode='BACKFILL_CANDLE_ONLY')
                          +
                          (SELECT COUNT(*) FROM source_captures s
                           JOIN event_provenance p USING(event_open_ms)
                           WHERE p.evidence_mode='BACKFILL_CANDLE_ONLY')
                        """
                    ).fetchone()[0]
                )
                candles = int(conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0])
                snapshots = int(
                    conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
                )
                membership_rows = int(
                    conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0]
                )
                funding_events = int(
                    conn.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0]
                )
                rejected_attempts = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM collection_attempts
                        WHERE result LIKE '%REJECTED%' OR result LIKE '%FAILED%'
                           OR result LIKE '%UNRECOVERABLE%'
                        """
                    ).fetchone()[0]
                )
                missing_membership_candles = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM universe_membership u
                        LEFT JOIN candles_5m c
                          ON c.event_open_ms=u.event_open_ms AND c.symbol=u.symbol
                        WHERE c.symbol IS NULL
                        """
                    ).fetchone()[0]
                )
                missing_point_in_time_snapshots = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM universe_membership u
                        LEFT JOIN market_snapshots s
                          ON s.event_open_ms=u.event_open_ms AND s.symbol=u.symbol
                        WHERE u.membership_quality='POINT_IN_TIME' AND s.symbol IS NULL
                        """
                    ).fetchone()[0]
                )
                incomplete_symbol_events = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM market_events e
                        JOIN event_provenance p USING(event_open_ms)
                        WHERE e.status='COMPLETE' AND (
                            e.stored_symbols != e.requested_symbols
                            OR (SELECT COUNT(*) FROM universe_membership u
                                WHERE u.event_open_ms=e.event_open_ms) != e.requested_symbols
                            OR (SELECT COUNT(*) FROM candles_5m c
                                WHERE c.event_open_ms=e.event_open_ms) != e.requested_symbols
                            OR (p.context_complete=1 AND
                                (SELECT COUNT(*) FROM market_snapshots s
                                 WHERE s.event_open_ms=e.event_open_ms) != e.requested_symbols)
                        )
                        """
                    ).fetchone()[0]
                )
                invalid_candles = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM candles_5m c JOIN market_events e USING(event_open_ms)
                        WHERE c.open_time_ms != c.event_open_ms
                           OR c.close_time_ms != e.event_close_ms
                           OR c.open_price <= 0 OR c.high_price <= 0
                           OR c.low_price <= 0 OR c.close_price <= 0
                           OR c.high_price < c.open_price OR c.high_price < c.close_price
                           OR c.high_price < c.low_price OR c.low_price > c.open_price
                           OR c.low_price > c.close_price OR c.low_price > c.high_price
                           OR c.base_volume < 0 OR c.quote_volume < 0 OR c.trade_count < 0
                           OR c.taker_buy_base_volume < 0 OR c.taker_buy_quote_volume < 0
                        """
                    ).fetchone()[0]
                )
                invalid_spreads = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM market_snapshots
                        WHERE bid_price <= 0 OR ask_price <= 0 OR ask_price < bid_price
                           OR spread_pct < 0
                        """
                    ).fetchone()[0]
                )

                source_rows = tuple(
                    conn.execute(
                        """
                        SELECT p.event_open_ms, p.capture_started_at_ms,
                               p.capture_finished_at_ms, e.event_close_ms,
                               s.source, s.started_at_ms, s.finished_at_ms
                        FROM event_provenance p
                        JOIN market_events e USING(event_open_ms)
                        LEFT JOIN source_captures s USING(event_open_ms)
                        WHERE p.context_complete=1
                        ORDER BY p.event_open_ms, s.source
                        """
                    )
                )
                sources_by_event: dict[int, set[str]] = {}
                spans_by_event: dict[int, list[int]] = {}
                source_capture_outside_event_bounds = 0
                late_source_captures = 0
                late_source_events: set[int] = set()
                for (
                    event_open,
                    event_started,
                    event_finished,
                    event_close,
                    source,
                    source_started,
                    source_finished,
                ) in source_rows:
                    event_key = int(event_open)
                    sources_by_event.setdefault(event_key, set())
                    if source is None:
                        continue
                    sources_by_event[event_key].add(str(source))
                    started = int(source_started)
                    finished = int(source_finished)
                    spans_by_event.setdefault(event_key, []).extend((started, finished))
                    if (
                        finished < started
                        or started < int(event_started)
                        or finished > int(event_finished)
                    ):
                        source_capture_outside_event_bounds += 1
                    if finished - int(event_close) > self.config.max_live_context_delay_ms:
                        late_source_captures += 1
                        late_source_events.add(event_key)

                source_capture_missing_required_events = sum(
                    1
                    for names in sources_by_event.values()
                    if names != REQUIRED_LIVE_CONTEXT_SOURCES
                )
                source_capture_extra_names = sum(
                    len(names - REQUIRED_LIVE_CONTEXT_SOURCES)
                    for names in sources_by_event.values()
                )
                source_spans = [
                    max(values) - min(values) for values in spans_by_event.values() if values
                ]
                max_source_capture_span_ms = max(source_spans) if source_spans else None

                late_snapshot_rows = tuple(
                    conn.execute(
                        """
                        SELECT s.event_open_ms, s.captured_at_ms - e.event_close_ms
                        FROM market_snapshots s
                        JOIN market_events e USING(event_open_ms)
                        JOIN event_provenance p USING(event_open_ms)
                        WHERE p.context_complete=1
                          AND s.captured_at_ms - e.event_close_ms > ?
                        ORDER BY s.event_open_ms, s.symbol
                        """,
                        (self.config.max_live_context_delay_ms,),
                    )
                )
                late_point_in_time_snapshots = len(late_snapshot_rows)
                late_context_events = len(
                    late_source_events | {int(row[0]) for row in late_snapshot_rows}
                )
                max_context_delay = conn.execute(
                    """
                    SELECT MAX(delay_ms) FROM (
                        SELECT s.captured_at_ms - e.event_close_ms AS delay_ms
                        FROM market_snapshots s
                        JOIN market_events e USING(event_open_ms)
                        JOIN event_provenance p USING(event_open_ms)
                        WHERE p.context_complete=1
                        UNION ALL
                        SELECT s.finished_at_ms - e.event_close_ms AS delay_ms
                        FROM source_captures s
                        JOIN market_events e USING(event_open_ms)
                        JOIN event_provenance p USING(event_open_ms)
                        WHERE p.context_complete=1
                    )
                    """
                ).fetchone()[0]
                max_live_context_delay_observed_ms = (
                    None if max_context_delay is None else int(max_context_delay)
                )
                clock_skew = conn.execute(
                    """
                    SELECT MAX(
                        MAX(
                            ABS(capture_started_at_ms - server_time_before_ms),
                            ABS(capture_finished_at_ms - server_time_after_ms)
                        )
                    )
                    FROM event_provenance
                    WHERE server_time_before_ms IS NOT NULL
                      AND server_time_after_ms IS NOT NULL
                    """
                ).fetchone()[0]
                max_abs_server_clock_skew_ms = (
                    None if clock_skew is None else int(clock_skew)
                )
                server_clock_skew_violations = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM event_provenance
                        WHERE server_time_before_ms IS NOT NULL
                          AND server_time_after_ms IS NOT NULL
                          AND (
                            ABS(capture_started_at_ms - server_time_before_ms) > ?
                            OR ABS(capture_finished_at_ms - server_time_after_ms) > ?
                          )
                        """,
                        (
                            self.config.max_server_clock_skew_ms,
                            self.config.max_server_clock_skew_ms,
                        ),
                    ).fetchone()[0]
                )

                internal_event_gaps = 0
                if len(event_opens) >= 2:
                    for left, right in zip(event_opens, event_opens[1:]):
                        if right > left + interval:
                            internal_event_gaps += ((right - left) // interval) - 1
                adjusted_now = now - settle_ms
                if adjusted_now < interval:
                    expected_latest_open_ms = None
                else:
                    expected_latest_open_ms = ((adjusted_now // interval) - 1) * interval
                trailing_event_gaps = 0
                future_event_rows = 0
                data_age_ms = None
                if event_opens:
                    latest = event_opens[-1]
                    latest_close = latest + interval - 1
                    data_age_ms = max(0, now - latest_close)
                    if expected_latest_open_ms is not None:
                        if latest < expected_latest_open_ms:
                            trailing_event_gaps = (
                                (expected_latest_open_ms - latest) // interval
                            )
                        future_event_rows = sum(
                            1 for value in event_opens if value > expected_latest_open_ms
                        )
                event_gap_count = internal_event_gaps + trailing_event_gaps

                funding_coverage_pct = None
                funding_coverage_complete = None
                if event_opens:
                    funding_start = event_opens[0]
                    funding_end = event_opens[-1] + interval - 1
                    total_ms = funding_end - funding_start + 1
                    covered_ms = self._merged_coverage_ms(conn, funding_start, funding_end)
                    funding_coverage_pct = round(covered_ms * 100.0 / total_ms, 6)
                    funding_coverage_complete = covered_ms == total_ms

                evidence_digest = self._evidence_digest(conn)
                integrity = "ok" if integrity_rows == ("ok",) else "; ".join(integrity_rows)
                anomaly_counts = {
                    "foreign_key_violations": foreign_key_violations,
                    "event_gap_count": event_gap_count,
                    "future_event_rows": future_event_rows,
                    "missing_membership_candles": missing_membership_candles,
                    "missing_point_in_time_snapshots": missing_point_in_time_snapshots,
                    "incomplete_symbol_events": incomplete_symbol_events,
                    "invalid_candles": invalid_candles,
                    "invalid_spreads": invalid_spreads,
                    "late_point_in_time_snapshots": late_point_in_time_snapshots,
                    "late_source_captures": late_source_captures,
                    "source_capture_missing_required_events": source_capture_missing_required_events,
                    "source_capture_extra_names": source_capture_extra_names,
                    "source_capture_outside_event_bounds": source_capture_outside_event_bounds,
                    "server_clock_skew_violations": server_clock_skew_violations,
                    "recovered_context_conflicts": recovered_context_conflicts,
                    "recovered_fabricated_context_rows": recovered_fabricated_context_rows,
                }
                healthy = (
                    integrity == "ok"
                    and all(value == 0 for value in anomaly_counts.values())
                    and (funding_coverage_complete is not False)
                )
                semantic: dict[str, object] = {
                    "now_ms": now,
                    "integrity": integrity,
                    **anomaly_counts,
                    "complete_events": complete_events,
                    "research_ready_events": research_ready_events,
                    "context_incomplete_events": context_incomplete_events,
                    "recovered_events": recovered_events,
                    "rejected_collection_attempts": rejected_attempts,
                    "candles": candles,
                    "snapshots": snapshots,
                    "universe_membership_rows": membership_rows,
                    "funding_events": funding_events,
                    "funding_coverage_pct": funding_coverage_pct,
                    "funding_coverage_complete": funding_coverage_complete,
                    "internal_event_gaps": internal_event_gaps,
                    "trailing_event_gaps": trailing_event_gaps,
                    "expected_latest_open_ms": expected_latest_open_ms,
                    "data_age_ms": data_age_ms,
                    "late_context_events": late_context_events,
                    "max_live_context_delay_observed_ms": max_live_context_delay_observed_ms,
                    "max_source_capture_span_ms": max_source_capture_span_ms,
                    "max_abs_server_clock_skew_ms": max_abs_server_clock_skew_ms,
                    "evidence_digest": evidence_digest,
                    "healthy": healthy,
                }
                audit_digest = hashlib.sha256(
                    json.dumps(
                        semantic,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode("utf-8")
                ).hexdigest()
                report = {
                    **semantic,
                    "audit_digest": audit_digest,
                    "database_bytes": db_bytes,
                    "wal_bytes": wal_bytes,
                }
                if record:
                    conn.execute(
                        """
                        INSERT INTO audit_runs(
                            captured_at_ms, database_bytes, wal_bytes,
                            complete_events, research_ready_events, report_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now,
                            db_bytes,
                            wal_bytes,
                            complete_events,
                            research_ready_events,
                            json.dumps(
                                report,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=True,
                            ),
                        ),
                    )
        except EvidenceDatabaseError:
            raise
        except sqlite3.Error as exc:
            raise EvidenceDatabaseError("NBOT_OBSERVATION_DB_AUDIT_FAILED") from exc
        return report
