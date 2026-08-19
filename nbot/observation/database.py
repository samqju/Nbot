"""SQLite raw-evidence store for NBOT V3.3.

Only point-in-time market evidence, collection provenance, funding-history
containers, and audit containers live here.  Research features, outcomes,
selection, recommendation, communication, and execution state belong to later
canonical roadmap phases.
"""

from __future__ import annotations

from collections.abc import Mapping
import sqlite3
from pathlib import Path

from .config import ObservationConfig
from .models import Candle, UniverseCapture, UniverseRow


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
