from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .binance import Candle, UniverseRow
from .config import ObserverConfig


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_events (
    event_open_ms INTEGER PRIMARY KEY,
    event_close_ms INTEGER NOT NULL,
    captured_at_ms INTEGER NOT NULL,
    requested_symbols INTEGER NOT NULL,
    stored_symbols INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMPLETE', 'PARTIAL')),
    collector_version TEXT NOT NULL,
    capture_duration_ms INTEGER NOT NULL
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

CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time
    ON market_snapshots(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_time
    ON candles_5m(symbol, event_open_ms);
"""


class EvidenceDB:
    def __init__(self, config: ObserverConfig):
        self.config = config
        self.path = Path(config.database_path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT INTO metadata(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (self.config.schema_version,),
            )
            conn.execute(
                "INSERT INTO metadata(key, value) VALUES('role', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (self.config.role,),
            )
            conn.execute(
                "INSERT INTO metadata(key, value) VALUES('market_environment', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (self.config.market_environment,),
            )

    def has_complete_event(self, event_open_ms: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM market_events WHERE event_open_ms=? AND status='COMPLETE'",
                (event_open_ms,),
            ).fetchone()
        return row is not None

    def store_event(
        self,
        *,
        event_open_ms: int,
        event_close_ms: int,
        captured_at_ms: int,
        requested_symbols: int,
        universe_rows: Iterable[UniverseRow],
        candles: dict[str, Candle],
        error_count: int,
        capture_duration_ms: int,
    ) -> str:
        rows = {row.symbol: row for row in universe_rows if row.symbol in candles}
        stored_symbols = len(rows)
        status = "COMPLETE" if stored_symbols == requested_symbols and error_count == 0 else "PARTIAL"

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM market_events WHERE event_open_ms=?", (event_open_ms,))
            conn.execute(
                """
                INSERT INTO market_events(
                    event_open_ms, event_close_ms, captured_at_ms,
                    requested_symbols, stored_symbols, error_count,
                    status, collector_version, capture_duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    event_close_ms,
                    captured_at_ms,
                    requested_symbols,
                    stored_symbols,
                    error_count,
                    status,
                    self.config.collector_version,
                    capture_duration_ms,
                ),
            )
            for symbol, row in rows.items():
                candle = candles[symbol]
                conn.execute(
                    """
                    INSERT INTO candles_5m VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_open_ms,
                        symbol,
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
                conn.execute(
                    """
                    INSERT INTO market_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_open_ms,
                        symbol,
                        row.universe_rank,
                        row.quote_volume_24h_usd,
                        row.bid_price,
                        row.ask_price,
                        row.spread_pct,
                        row.mark_price,
                        row.index_price,
                        row.funding_rate,
                        row.next_funding_time_ms,
                        captured_at_ms,
                    ),
                )
        return status

    def status(self) -> dict[str, object]:
        self.initialize()
        with self._connect() as conn:
            events = conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0]
            complete = conn.execute("SELECT COUNT(*) FROM market_events WHERE status='COMPLETE'").fetchone()[0]
            partial = conn.execute("SELECT COUNT(*) FROM market_events WHERE status='PARTIAL'").fetchone()[0]
            candles = conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0]
            snapshots = conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
            latest = conn.execute(
                "SELECT event_open_ms, stored_symbols, requested_symbols, status, capture_duration_ms "
                "FROM market_events ORDER BY event_open_ms DESC LIMIT 1"
            ).fetchone()
            meta = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
        return {
            "events": events,
            "complete_events": complete,
            "partial_events": partial,
            "candles": candles,
            "snapshots": snapshots,
            "latest_event": latest,
            "metadata": meta,
            "database_path": str(self.path),
        }
