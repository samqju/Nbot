from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Sequence

from .binance import Candle, FundingEvent, SourceCapture, UniverseRow, validate_candle
from .config import ObserverConfig


class ClosingConnection(sqlite3.Connection):
    """SQLite connection whose context-manager exit also closes the handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


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
    requested_symbols INTEGER NOT NULL,
    stored_symbols INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    result TEXT NOT NULL,
    capture_duration_ms INTEGER NOT NULL,
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
    row_count INTEGER NOT NULL,
    collector_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at_ms INTEGER NOT NULL,
    database_bytes INTEGER NOT NULL,
    wal_bytes INTEGER NOT NULL,
    complete_events INTEGER NOT NULL,
    research_ready_events INTEGER NOT NULL,
    report_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_sets (
    feature_version TEXT PRIMARY KEY,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_features (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    computed_at_ms INTEGER NOT NULL,
    source_min_event_open_ms INTEGER NOT NULL,
    source_max_event_open_ms INTEGER NOT NULL,
    history_bars INTEGER NOT NULL,
    full_history_4h INTEGER NOT NULL CHECK (full_history_4h IN (0, 1)),
    close_price REAL NOT NULL,
    ret_5m REAL,
    ret_15m REAL,
    ret_30m REAL,
    ret_1h REAL,
    ret_2h REAL,
    ret_4h REAL,
    realized_vol_1h REAL,
    realized_vol_4h REAL,
    atr14_frac REAL,
    range_frac REAL,
    quote_volume_24h_usd REAL NOT NULL,
    spread_pct REAL NOT NULL,
    funding_rate REAL,
    minutes_to_next_funding REAL,
    selection_rank INTEGER NOT NULL,
    liquidity_percentile REAL,
    ret_1h_percentile REAL,
    ret_4h_percentile REAL,
    volatility_percentile REAL,
    btc_ret_5m REAL,
    btc_ret_1h REAL,
    btc_ret_4h REAL,
    breadth_positive_5m REAL,
    breadth_positive_1h REAL,
    median_ret_5m REAL,
    median_ret_1h REAL,
    utc_hour INTEGER NOT NULL,
    utc_minute INTEGER NOT NULL,
    utc_day_of_week INTEGER NOT NULL,
    context_delay_ms INTEGER NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, feature_version),
    FOREIGN KEY (event_open_ms, symbol)
        REFERENCES market_snapshots(event_open_ms, symbol) ON DELETE CASCADE,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS signal_sets (
    signal_version TEXT PRIMARY KEY,
    signal_name TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS signal_annotations (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    signal_version TEXT NOT NULL,
    computed_at_ms INTEGER NOT NULL,
    score REAL,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'NONE')),
    reason TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, signal_version),
    FOREIGN KEY (event_open_ms, symbol, feature_version)
        REFERENCES canonical_features(event_open_ms, symbol, feature_version) ON DELETE CASCADE,
    FOREIGN KEY (signal_version) REFERENCES signal_sets(signal_version)
);

CREATE TABLE IF NOT EXISTS feature_builds (
    event_open_ms INTEGER NOT NULL,
    feature_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    feature_row_count INTEGER NOT NULL,
    feature_digest TEXT NOT NULL,
    signal_annotation_count INTEGER NOT NULL,
    signal_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, feature_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS future_path_sets (
    outcome_version TEXT PRIMARY KEY,
    feature_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS future_candle_cache (
    symbol TEXT NOT NULL,
    event_open_ms INTEGER NOT NULL,
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
    source TEXT NOT NULL CHECK (source IN ('BINANCE_HISTORICAL_KLINE')),
    ingested_at_ms INTEGER NOT NULL,
    PRIMARY KEY (symbol, event_open_ms)
);

CREATE TABLE IF NOT EXISTS future_paths (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    outcome_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    source_min_event_open_ms INTEGER NOT NULL,
    source_max_event_open_ms INTEGER NOT NULL,
    future_candle_count INTEGER NOT NULL,
    fallback_candle_count INTEGER NOT NULL,
    source_candle_digest TEXT NOT NULL,
    fwd_ret_5m REAL NOT NULL,
    fwd_ret_15m REAL NOT NULL,
    fwd_ret_30m REAL NOT NULL,
    fwd_ret_1h REAL NOT NULL,
    fwd_ret_2h REAL NOT NULL,
    fwd_ret_4h REAL NOT NULL,
    long_mfe_frac REAL NOT NULL,
    long_mae_frac REAL NOT NULL,
    short_mfe_frac REAL NOT NULL,
    short_mae_frac REAL NOT NULL,
    time_to_long_mfe_min INTEGER NOT NULL,
    time_to_long_mae_min INTEGER NOT NULL,
    time_to_short_mfe_min INTEGER NOT NULL,
    time_to_short_mae_min INTEGER NOT NULL,
    future_realized_vol_4h REAL NOT NULL,
    risk_unit_version TEXT NOT NULL,
    risk_unit_frac REAL,
    barrier_hits_json TEXT NOT NULL,
    continuation_json TEXT NOT NULL,
    funding_complete INTEGER NOT NULL CHECK (funding_complete IN (0, 1)),
    funding_event_count INTEGER NOT NULL,
    funding_rate_sum REAL NOT NULL,
    funding_events_json TEXT NOT NULL,
    funding_source_digest TEXT NOT NULL,
    cost_version TEXT NOT NULL,
    roundtrip_base_cost_frac REAL NOT NULL,
    net_long_5m REAL NOT NULL,
    net_long_15m REAL NOT NULL,
    net_long_30m REAL NOT NULL,
    net_long_1h REAL NOT NULL,
    net_long_2h REAL NOT NULL,
    net_long_4h REAL NOT NULL,
    net_short_5m REAL NOT NULL,
    net_short_15m REAL NOT NULL,
    net_short_30m REAL NOT NULL,
    net_short_1h REAL NOT NULL,
    net_short_2h REAL NOT NULL,
    net_short_4h REAL NOT NULL,
    path_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, outcome_version),
    FOREIGN KEY (event_open_ms, symbol, feature_version)
        REFERENCES canonical_features(event_open_ms, symbol, feature_version) ON DELETE CASCADE,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);

CREATE TABLE IF NOT EXISTS future_path_builds (
    event_open_ms INTEGER NOT NULL,
    outcome_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    path_row_count INTEGER NOT NULL,
    path_digest TEXT NOT NULL,
    fallback_candle_count INTEGER NOT NULL,
    PRIMARY KEY (event_open_ms, outcome_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);

CREATE TABLE IF NOT EXISTS future_path_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_open_ms INTEGER NOT NULL,
    attempted_at_ms INTEGER NOT NULL,
    outcome_version TEXT NOT NULL,
    result TEXT NOT NULL,
    expected_symbols INTEGER NOT NULL,
    completed_symbols INTEGER NOT NULL,
    missing_candles INTEGER NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS exit_policy_labs (
    lab_version TEXT PRIMARY KEY,
    outcome_version TEXT NOT NULL,
    catalog_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);

CREATE TABLE IF NOT EXISTS exit_policy_sets (
    policy_version TEXT PRIMARY KEY,
    lab_version TEXT NOT NULL,
    family TEXT NOT NULL,
    is_control INTEGER NOT NULL CHECK (is_control IN (0, 1)),
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (lab_version) REFERENCES exit_policy_labs(lab_version)
);

CREATE TABLE IF NOT EXISTS exit_policy_results (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    feature_version TEXT NOT NULL,
    outcome_version TEXT NOT NULL,
    lab_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    initial_risk_frac REAL NOT NULL CHECK (initial_risk_frac > 0),
    source_path_digest TEXT NOT NULL,
    source_candle_digest TEXT NOT NULL,
    exit_bar INTEGER NOT NULL CHECK (exit_bar BETWEEN 1 AND 48),
    exit_time_ms INTEGER NOT NULL,
    exit_price REAL NOT NULL,
    exit_reason TEXT NOT NULL,
    gross_return_frac REAL NOT NULL,
    gross_r REAL NOT NULL,
    funding_cost_frac REAL NOT NULL,
    roundtrip_base_cost_frac REAL NOT NULL,
    net_return_frac REAL NOT NULL,
    net_r REAL NOT NULL,
    mfe_r REAL NOT NULL,
    mae_r REAL NOT NULL,
    capture_ratio REAL,
    peak_favorable_r REAL NOT NULL,
    peak_giveback_r REAL NOT NULL,
    time_to_mfe_min INTEGER NOT NULL,
    holding_minutes INTEGER NOT NULL,
    post_exit_mfe_r REAL NOT NULL,
    missed_extension_r REAL NOT NULL,
    stop_updates INTEGER NOT NULL,
    stop_trace_json TEXT NOT NULL,
    ambiguous_stop_bar INTEGER NOT NULL CHECK (ambiguous_stop_bar IN (0, 1)),
    result_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, side, policy_version),
    FOREIGN KEY (event_open_ms, symbol, outcome_version)
        REFERENCES future_paths(event_open_ms, symbol, outcome_version) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES exit_policy_labs(lab_version),
    FOREIGN KEY (policy_version) REFERENCES exit_policy_sets(policy_version)
);

CREATE TABLE IF NOT EXISTS exit_policy_builds (
    event_open_ms INTEGER NOT NULL,
    lab_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    eligible_path_count INTEGER NOT NULL,
    result_row_count INTEGER NOT NULL,
    source_digest TEXT NOT NULL,
    result_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, lab_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES exit_policy_labs(lab_version)
);

CREATE TABLE IF NOT EXISTS entry_selection_labs (
    lab_version TEXT PRIMARY KEY,
    feature_version TEXT NOT NULL,
    policy_lab_version TEXT NOT NULL,
    target_policy_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version),
    FOREIGN KEY (policy_lab_version) REFERENCES exit_policy_labs(lab_version),
    FOREIGN KEY (target_policy_version) REFERENCES exit_policy_sets(policy_version)
);

CREATE TABLE IF NOT EXISTS entry_selector_sets (
    selector_version TEXT PRIMARY KEY,
    lab_version TEXT NOT NULL,
    family TEXT NOT NULL,
    is_learned INTEGER NOT NULL CHECK (is_learned IN (0, 1)),
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version)
);

CREATE TABLE IF NOT EXISTS entry_selection_examples (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    lab_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    target_policy_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    target_net_r REAL NOT NULL,
    target_net_return_frac REAL NOT NULL,
    target_mfe_r REAL NOT NULL,
    target_mae_r REAL NOT NULL,
    source_policy_result_digest TEXT NOT NULL,
    source_feature_digest TEXT NOT NULL,
    source_signal_digest TEXT NOT NULL,
    feature_vector_json TEXT NOT NULL,
    example_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, side, lab_version),
    FOREIGN KEY (event_open_ms, symbol, side, target_policy_version)
        REFERENCES exit_policy_results(event_open_ms, symbol, side, policy_version) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version)
);

CREATE TABLE IF NOT EXISTS entry_selection_builds (
    event_open_ms INTEGER NOT NULL,
    lab_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    example_row_count INTEGER NOT NULL,
    source_digest TEXT NOT NULL,
    example_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, lab_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version)
);

CREATE TABLE IF NOT EXISTS entry_selection_predictions (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    lab_version TEXT NOT NULL,
    selector_version TEXT NOT NULL,
    scored_at_ms INTEGER NOT NULL,
    score REAL NOT NULL,
    rank_in_event INTEGER NOT NULL CHECK (rank_in_event > 0),
    trained_through_event_ms INTEGER,
    training_event_count INTEGER NOT NULL,
    training_row_count INTEGER NOT NULL,
    model_digest TEXT,
    source_example_digest TEXT NOT NULL,
    prediction_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, side, selector_version),
    FOREIGN KEY (event_open_ms, symbol, side, lab_version)
        REFERENCES entry_selection_examples(event_open_ms, symbol, side, lab_version) ON DELETE CASCADE,
    FOREIGN KEY (selector_version) REFERENCES entry_selector_sets(selector_version)
);

CREATE TABLE IF NOT EXISTS entry_selection_prediction_builds (
    event_open_ms INTEGER NOT NULL,
    lab_version TEXT NOT NULL,
    selector_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    prediction_row_count INTEGER NOT NULL,
    training_event_count INTEGER NOT NULL,
    training_row_count INTEGER NOT NULL,
    trained_through_event_ms INTEGER,
    model_digest TEXT,
    source_digest TEXT NOT NULL,
    prediction_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, lab_version, selector_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (lab_version) REFERENCES entry_selection_labs(lab_version),
    FOREIGN KEY (selector_version) REFERENCES entry_selector_sets(selector_version)
);

CREATE INDEX IF NOT EXISTS idx_entry_selection_examples_event
    ON entry_selection_examples(event_open_ms, symbol, side);
CREATE INDEX IF NOT EXISTS idx_entry_selection_predictions_selector_event
    ON entry_selection_predictions(selector_version, event_open_ms, rank_in_event);

CREATE INDEX IF NOT EXISTS idx_exit_policy_results_policy_side
    ON exit_policy_results(policy_version, side, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_exit_policy_results_event
    ON exit_policy_results(event_open_ms, symbol, side);

CREATE INDEX IF NOT EXISTS idx_future_cache_symbol_time
    ON future_candle_cache(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_future_paths_symbol_time
    ON future_paths(symbol, event_open_ms, outcome_version);
CREATE INDEX IF NOT EXISTS idx_future_attempts_event_time
    ON future_path_attempts(event_open_ms, attempted_at_ms);

CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time
    ON market_snapshots(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_time
    ON candles_5m(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_membership_symbol_time
    ON universe_membership(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_funding_symbol_time
    ON funding_events(symbol, funding_time_ms);
CREATE INDEX IF NOT EXISTS idx_attempts_event_time
    ON collection_attempts(event_open_ms, attempted_at_ms);
CREATE INDEX IF NOT EXISTS idx_features_symbol_time
    ON canonical_features(symbol, event_open_ms, feature_version);
CREATE INDEX IF NOT EXISTS idx_signals_event_version
    ON signal_annotations(event_open_ms, signal_version, active);
"""


class EvidenceDB:
    def __init__(self, config: ObserverConfig):
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
        """Open a configured connection for other NBOT modules using the canonical DB."""
        return self._connect()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            for key, value in (
                ("schema_version", self.config.schema_version),
                ("role", self.config.role),
                ("market_environment", self.config.market_environment),
            ):
                conn.execute(
                    "INSERT INTO metadata(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )

            # V2.0 -> V2.1 migration. Preserve old snapshots, but only mark
            # them research-ready when V2.0's own captured_at timestamp proves
            # the context was inside V2.1's allowed post-close window. V2.0 did
            # not store source-level timestamps, so late rows remain preserved
            # as honest context-incomplete evidence rather than being deleted.
            conn.execute(
                """
                INSERT OR IGNORE INTO event_provenance(
                    event_open_ms, evidence_mode, context_complete,
                    membership_quality, source_universe_event_open_ms,
                    server_time_before_ms, server_time_after_ms,
                    capture_started_at_ms, capture_finished_at_ms, recovery_reason
                )
                SELECT
                    e.event_open_ms,
                    'LIVE_V2_0_MIGRATED',
                    CASE
                        WHEN e.status='COMPLETE'
                         AND e.captured_at_ms - e.event_close_ms <= ? THEN 1
                        ELSE 0
                    END,
                    CASE
                        WHEN e.status='COMPLETE'
                         AND e.captured_at_ms - e.event_close_ms <= ? THEN 'POINT_IN_TIME'
                        ELSE 'POINT_IN_TIME_LATE'
                    END,
                    e.event_open_ms,
                    NULL,
                    NULL,
                    MAX(e.event_close_ms + 1, e.captured_at_ms - e.capture_duration_ms),
                    e.captured_at_ms,
                    CASE
                        WHEN e.status='COMPLETE'
                         AND e.captured_at_ms - e.event_close_ms <= ?
                            THEN 'V2.0 did not store source-level timing'
                        ELSE 'V2.0 context exceeded V2.1 live-context delay limit'
                    END
                FROM market_events e
                """,
                (
                    self.config.max_live_context_delay_ms,
                    self.config.max_live_context_delay_ms,
                    self.config.max_live_context_delay_ms,
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO universe_membership(
                    event_open_ms, symbol, universe_rank,
                    membership_quality, source_universe_event_open_ms
                )
                SELECT event_open_ms, symbol, universe_rank, 'POINT_IN_TIME', event_open_ms
                FROM market_snapshots
                """
            )

            # Repair databases already migrated by the first V2.1 patch. This
            # is intentionally idempotent and only touches V2.0 migration rows.
            conn.execute(
                """
                UPDATE event_provenance
                SET context_complete = CASE
                        WHEN (SELECT e.status FROM market_events e
                              WHERE e.event_open_ms=event_provenance.event_open_ms)='COMPLETE'
                         AND (SELECT e.captured_at_ms - e.event_close_ms FROM market_events e
                              WHERE e.event_open_ms=event_provenance.event_open_ms) <= ? THEN 1
                        ELSE 0
                    END,
                    membership_quality = CASE
                        WHEN (SELECT e.status FROM market_events e
                              WHERE e.event_open_ms=event_provenance.event_open_ms)='COMPLETE'
                         AND (SELECT e.captured_at_ms - e.event_close_ms FROM market_events e
                              WHERE e.event_open_ms=event_provenance.event_open_ms) <= ?
                            THEN 'POINT_IN_TIME'
                        ELSE 'POINT_IN_TIME_LATE'
                    END,
                    recovery_reason = CASE
                        WHEN (SELECT e.status FROM market_events e
                              WHERE e.event_open_ms=event_provenance.event_open_ms)='COMPLETE'
                         AND (SELECT e.captured_at_ms - e.event_close_ms FROM market_events e
                              WHERE e.event_open_ms=event_provenance.event_open_ms) <= ?
                            THEN 'V2.0 did not store source-level timing'
                        ELSE 'V2.0 context exceeded V2.1 live-context delay limit'
                    END
                WHERE evidence_mode='LIVE_V2_0_MIGRATED'
                """,
                (
                    self.config.max_live_context_delay_ms,
                    self.config.max_live_context_delay_ms,
                    self.config.max_live_context_delay_ms,
                ),
            )
            conn.execute(
                """
                UPDATE universe_membership
                SET membership_quality = COALESCE(
                    (SELECT p.membership_quality FROM event_provenance p
                     WHERE p.event_open_ms=universe_membership.event_open_ms),
                    membership_quality
                )
                WHERE event_open_ms IN (
                    SELECT event_open_ms FROM event_provenance
                    WHERE evidence_mode='LIVE_V2_0_MIGRATED'
                )
                """
            )

    def has_complete_event(self, event_open_ms: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM market_events WHERE event_open_ms=? AND status='COMPLETE'",
                (event_open_ms,),
            ).fetchone()
        return row is not None

    def _record_attempt(
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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collection_attempts(
                    event_open_ms, attempted_at_ms, requested_symbols, stored_symbols,
                    error_count, result, capture_duration_ms, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    attempted_at_ms,
                    requested_symbols,
                    stored_symbols,
                    error_count,
                    result,
                    capture_duration_ms,
                    detail,
                ),
            )

    def _validated_live_rows(
        self,
        event_open_ms: int,
        event_close_ms: int,
        requested_symbols: int,
        universe_rows: Iterable[UniverseRow],
        candles: dict[str, Candle],
    ) -> tuple[dict[str, UniverseRow], str | None]:
        universe_list = list(universe_rows)
        if len(universe_list) != requested_symbols:
            return {}, "universe row count differs from requested_symbols"
        symbols = [row.symbol for row in universe_list]
        if len(set(symbols)) != len(symbols):
            return {}, "duplicate symbol in live universe"
        if set(symbols) != set(candles):
            return {}, "live candle set differs from point-in-time universe"
        for symbol in symbols:
            candle = candles[symbol]
            try:
                validate_candle(candle, self.config.candle_interval_ms)
            except ValueError as exc:
                return {}, f"{symbol}: {exc}"
            if candle.symbol != symbol or candle.open_time_ms != event_open_ms:
                return {}, f"{symbol}: candle identity mismatch"
            if candle.close_time_ms != event_close_ms:
                return {}, f"{symbol}: candle close mismatch"
        return {row.symbol: row for row in universe_list}, None

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
        capture_started_at_ms: int | None = None,
        server_time_before_ms: int | None = None,
        server_time_after_ms: int | None = None,
        source_captures: Sequence[SourceCapture] = (),
        failure_detail: str | None = None,
    ) -> str:
        rows, validation_error = self._validated_live_rows(
            event_open_ms,
            event_close_ms,
            requested_symbols,
            universe_rows,
            candles,
        )
        is_complete = error_count == 0 and validation_error is None
        if not is_complete:
            self._record_attempt(
                event_open_ms=event_open_ms,
                attempted_at_ms=captured_at_ms,
                requested_symbols=requested_symbols,
                stored_symbols=len(candles),
                error_count=max(error_count, 1 if validation_error else 0),
                result="PARTIAL_REJECTED",
                capture_duration_ms=capture_duration_ms,
                detail="; ".join(value for value in (failure_detail, validation_error) if value) or None,
            )
            return "PARTIAL"

        started_at_ms = capture_started_at_ms
        if started_at_ms is None:
            started_at_ms = max(event_close_ms + 1, captured_at_ms - capture_duration_ms)

        context_captured_at_ms = (
            max(capture.finished_at_ms for capture in source_captures)
            if source_captures
            else captured_at_ms
        )

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM market_events WHERE event_open_ms=?", (event_open_ms,))
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
                    captured_at_ms,
                    requested_symbols,
                    requested_symbols,
                    self.config.collector_version,
                    capture_duration_ms,
                ),
            )
            conn.execute(
                """
                INSERT INTO event_provenance VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    "LIVE_POINT_IN_TIME",
                    1,
                    "POINT_IN_TIME",
                    event_open_ms,
                    server_time_before_ms,
                    server_time_after_ms,
                    started_at_ms,
                    captured_at_ms,
                    None,
                ),
            )
            for capture in source_captures:
                conn.execute(
                    "INSERT INTO source_captures VALUES (?, ?, ?, ?)",
                    (event_open_ms, capture.source, capture.started_at_ms, capture.finished_at_ms),
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
                        context_captured_at_ms,
                    ),
                )
                conn.execute(
                    "INSERT INTO universe_membership VALUES (?, ?, ?, 'POINT_IN_TIME', ?)",
                    (event_open_ms, symbol, row.universe_rank, event_open_ms),
                )
            conn.execute(
                """
                INSERT INTO collection_attempts(
                    event_open_ms, attempted_at_ms, requested_symbols, stored_symbols,
                    error_count, result, capture_duration_ms, detail
                ) VALUES (?, ?, ?, ?, 0, 'COMPLETE', ?, NULL)
                """,
                (event_open_ms, captured_at_ms, requested_symbols, requested_symbols, capture_duration_ms),
            )
        return "COMPLETE"

    def point_in_time_universe_before(self, event_open_ms: int) -> tuple[int, list[tuple[str, int]]] | None:
        self.initialize()
        with self._connect() as conn:
            source = conn.execute(
                """
                SELECT MAX(p.event_open_ms)
                FROM event_provenance p
                WHERE p.event_open_ms < ?
                  AND p.context_complete=1
                  AND p.membership_quality='POINT_IN_TIME'
                """,
                (event_open_ms,),
            ).fetchone()[0]
            if source is None:
                return None
            rows = conn.execute(
                """
                SELECT symbol, universe_rank
                FROM universe_membership
                WHERE event_open_ms=? AND membership_quality='POINT_IN_TIME'
                ORDER BY universe_rank, symbol
                """,
                (source,),
            ).fetchall()
        if not rows:
            return None
        return int(source), [(str(symbol), int(rank)) for symbol, rank in rows]

    def store_recovered_event(
        self,
        *,
        event_open_ms: int,
        source_universe_event_open_ms: int,
        membership: Sequence[tuple[str, int]],
        candles: dict[str, Candle],
        captured_at_ms: int,
        capture_duration_ms: int,
        recovery_reason: str,
    ) -> str:
        requested_symbols = len(membership)
        symbols = [symbol for symbol, _ in membership]
        if requested_symbols == 0:
            return "PARTIAL"
        if len(set(symbols)) != requested_symbols or set(symbols) != set(candles):
            self._record_attempt(
                event_open_ms=event_open_ms,
                attempted_at_ms=captured_at_ms,
                requested_symbols=requested_symbols,
                stored_symbols=len(candles),
                error_count=max(1, requested_symbols - len(candles)),
                result="RECOVERY_PARTIAL_REJECTED",
                capture_duration_ms=capture_duration_ms,
                detail="recovered candle set differs from inherited universe",
            )
            return "PARTIAL"

        event_close_ms = event_open_ms + self.config.candle_interval_ms - 1
        for symbol in symbols:
            candle = candles[symbol]
            try:
                validate_candle(candle, self.config.candle_interval_ms)
            except ValueError as exc:
                self._record_attempt(
                    event_open_ms=event_open_ms,
                    attempted_at_ms=captured_at_ms,
                    requested_symbols=requested_symbols,
                    stored_symbols=len(candles),
                    error_count=1,
                    result="RECOVERY_PARTIAL_REJECTED",
                    capture_duration_ms=capture_duration_ms,
                    detail=f"{symbol}: {exc}",
                )
                return "PARTIAL"
            if candle.open_time_ms != event_open_ms or candle.close_time_ms != event_close_ms:
                return "PARTIAL"

        started_at_ms = max(event_close_ms + 1, captured_at_ms - capture_duration_ms)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM market_events WHERE event_open_ms=?", (event_open_ms,))
            conn.execute(
                """
                INSERT INTO market_events VALUES (?, ?, ?, ?, ?, 0, 'COMPLETE', ?, ?)
                """,
                (
                    event_open_ms,
                    event_close_ms,
                    captured_at_ms,
                    requested_symbols,
                    requested_symbols,
                    self.config.collector_version,
                    capture_duration_ms,
                ),
            )
            conn.execute(
                """
                INSERT INTO event_provenance VALUES (?, 'BACKFILL_CANDLE_ONLY', 0, 'INHERITED', ?, NULL, NULL, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    source_universe_event_open_ms,
                    started_at_ms,
                    captured_at_ms,
                    recovery_reason,
                ),
            )
            for symbol, rank in membership:
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
                    "INSERT INTO universe_membership VALUES (?, ?, ?, 'INHERITED', ?)",
                    (event_open_ms, symbol, rank, source_universe_event_open_ms),
                )
            conn.execute(
                """
                INSERT INTO collection_attempts(
                    event_open_ms, attempted_at_ms, requested_symbols, stored_symbols,
                    error_count, result, capture_duration_ms, detail
                ) VALUES (?, ?, ?, ?, 0, 'RECOVERED_CANDLES_ONLY', ?, ?)
                """,
                (
                    event_open_ms,
                    captured_at_ms,
                    requested_symbols,
                    requested_symbols,
                    capture_duration_ms,
                    recovery_reason,
                ),
            )
        return "COMPLETE"

    def missing_event_opens(self, latest_open_ms: int) -> list[int]:
        self.initialize()
        with self._connect() as conn:
            earliest = conn.execute("SELECT MIN(event_open_ms) FROM market_events").fetchone()[0]
            if earliest is None or latest_open_ms < int(earliest):
                return []
            present = {
                int(row[0])
                for row in conn.execute(
                    "SELECT event_open_ms FROM market_events WHERE status='COMPLETE' AND event_open_ms BETWEEN ? AND ?",
                    (earliest, latest_open_ms),
                )
            }
        interval = self.config.candle_interval_ms
        return [value for value in range(int(earliest), latest_open_ms + 1, interval) if value not in present]

    def funding_sync_bounds(self) -> tuple[int | None, int | None]:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("SELECT MIN(start_ms), MAX(end_ms) FROM funding_sync_ranges").fetchone()
        return (None if row[0] is None else int(row[0]), None if row[1] is None else int(row[1]))

    def funding_sync_due(self, now_ms: int) -> bool:
        self.initialize()
        with self._connect() as conn:
            last = conn.execute("SELECT MAX(captured_at_ms) FROM funding_sync_ranges").fetchone()[0]
        return last is None or now_ms - int(last) >= self.config.funding_sync_interval_seconds * 1000

    def funding_sync_start_ms(self) -> int | None:
        self.initialize()
        with self._connect() as conn:
            synced = conn.execute("SELECT MAX(end_ms) FROM funding_sync_ranges").fetchone()[0]
            if synced is not None:
                return int(synced) + 1
            earliest = conn.execute("SELECT MIN(event_open_ms) FROM market_events").fetchone()[0]
        return None if earliest is None else int(earliest)

    def store_funding_sync(
        self,
        *,
        start_ms: int,
        end_ms: int,
        events: Sequence[FundingEvent],
        captured_at_ms: int,
    ) -> int:
        if end_ms < start_ms:
            return 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for row in events:
                conn.execute(
                    """
                    INSERT INTO funding_events(symbol, funding_time_ms, funding_rate, mark_price, ingested_at_ms)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, funding_time_ms) DO UPDATE SET
                        funding_rate=excluded.funding_rate,
                        mark_price=excluded.mark_price,
                        ingested_at_ms=excluded.ingested_at_ms
                    """,
                    (row.symbol, row.funding_time_ms, row.funding_rate, row.mark_price, captured_at_ms),
                )
            conn.execute(
                "INSERT INTO funding_sync_ranges(start_ms, end_ms, captured_at_ms, row_count, collector_version) VALUES (?, ?, ?, ?, ?)",
                (start_ms, end_ms, captured_at_ms, len(events), self.config.collector_version),
            )
        return len(events)

    def _funding_coverage_ms(self, start_ms: int, end_ms: int, conn: sqlite3.Connection) -> int:
        if end_ms < start_ms:
            return 0
        ranges = conn.execute(
            "SELECT start_ms, end_ms FROM funding_sync_ranges WHERE end_ms >= ? AND start_ms <= ? ORDER BY start_ms",
            (start_ms, end_ms),
        ).fetchall()
        merged: list[list[int]] = []
        for raw_start, raw_end in ranges:
            left = max(start_ms, int(raw_start))
            right = min(end_ms, int(raw_end))
            if not merged or left > merged[-1][1] + 1:
                merged.append([left, right])
            else:
                merged[-1][1] = max(merged[-1][1], right)
        return sum(right - left + 1 for left, right in merged)

    def status(self) -> dict[str, object]:
        self.initialize()
        with self._connect() as conn:
            events = conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0]
            complete = conn.execute("SELECT COUNT(*) FROM market_events WHERE status='COMPLETE'").fetchone()[0]
            partial = conn.execute("SELECT COUNT(*) FROM market_events WHERE status='PARTIAL'").fetchone()[0]
            research_ready = conn.execute(
                "SELECT COUNT(*) FROM event_provenance WHERE context_complete=1"
            ).fetchone()[0]
            recovered = conn.execute(
                "SELECT COUNT(*) FROM event_provenance WHERE evidence_mode='BACKFILL_CANDLE_ONLY'"
            ).fetchone()[0]
            candles = conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0]
            snapshots = conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
            funding = conn.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0]
            latest = conn.execute(
                """
                SELECT e.event_open_ms, e.stored_symbols, e.requested_symbols, e.status,
                       e.capture_duration_ms, p.evidence_mode, p.context_complete
                FROM market_events e
                LEFT JOIN event_provenance p USING(event_open_ms)
                ORDER BY e.event_open_ms DESC LIMIT 1
                """
            ).fetchone()
            meta = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
        return {
            "events": events,
            "complete_events": complete,
            "partial_events": partial,
            "research_ready_events": research_ready,
            "recovered_events": recovered,
            "candles": candles,
            "snapshots": snapshots,
            "funding_events": funding,
            "latest_event": latest,
            "metadata": meta,
            "database_path": str(self.path),
        }

    def audit(self, *, now_ms: int | None = None, record: bool = False) -> dict[str, object]:
        self.initialize()
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        db_bytes = self.path.stat().st_size if self.path.exists() else 0
        wal_path = Path(str(self.path) + "-wal")
        wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0

        with self._connect() as conn:
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_keys = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            event_bounds = conn.execute("SELECT MIN(event_open_ms), MAX(event_open_ms) FROM market_events").fetchone()
            earliest = None if event_bounds[0] is None else int(event_bounds[0])
            latest = None if event_bounds[1] is None else int(event_bounds[1])
            complete_events = int(conn.execute("SELECT COUNT(*) FROM market_events WHERE status='COMPLETE'").fetchone()[0])
            research_ready = int(conn.execute("SELECT COUNT(*) FROM event_provenance WHERE context_complete=1").fetchone()[0])
            context_incomplete_events = int(conn.execute(
                "SELECT COUNT(*) FROM event_provenance WHERE context_complete=0"
            ).fetchone()[0])
            recovered = int(conn.execute(
                "SELECT COUNT(*) FROM event_provenance WHERE evidence_mode='BACKFILL_CANDLE_ONLY'"
            ).fetchone()[0])
            late_migrated = int(conn.execute(
                "SELECT COUNT(*) FROM event_provenance "
                "WHERE evidence_mode='LIVE_V2_0_MIGRATED' AND context_complete=0"
            ).fetchone()[0])
            attempts_rejected = int(conn.execute("SELECT COUNT(*) FROM collection_attempts WHERE result LIKE '%REJECTED%'").fetchone()[0])
            candles = int(conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0])
            snapshots = int(conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0])
            membership_rows = int(conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0])
            funding_events = int(conn.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0])

            missing_candles = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM universe_membership u
                LEFT JOIN candles_5m c
                  ON c.event_open_ms=u.event_open_ms AND c.symbol=u.symbol
                WHERE c.symbol IS NULL
                """
            ).fetchone()[0])
            missing_snapshots = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM universe_membership u
                LEFT JOIN market_snapshots s
                  ON s.event_open_ms=u.event_open_ms AND s.symbol=u.symbol
                WHERE u.membership_quality='POINT_IN_TIME' AND s.symbol IS NULL
                """
            ).fetchone()[0])
            incomplete_symbol_events = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM market_events e
                LEFT JOIN event_provenance p USING(event_open_ms)
                WHERE e.status='COMPLETE'
                  AND (
                      e.stored_symbols != e.requested_symbols
                      OR (SELECT COUNT(*) FROM universe_membership u WHERE u.event_open_ms=e.event_open_ms) != e.requested_symbols
                      OR (SELECT COUNT(*) FROM candles_5m c WHERE c.event_open_ms=e.event_open_ms) != e.requested_symbols
                      OR (p.context_complete=1 AND (SELECT COUNT(*) FROM market_snapshots s WHERE s.event_open_ms=e.event_open_ms) != e.requested_symbols)
                  )
                """
            ).fetchone()[0])
            duplicate_candles = int(conn.execute(
                """
                SELECT COALESCE(SUM(n - 1), 0) FROM (
                    SELECT COUNT(*) n FROM candles_5m GROUP BY event_open_ms, symbol HAVING n > 1
                )
                """
            ).fetchone()[0])
            duplicate_snapshots = int(conn.execute(
                """
                SELECT COALESCE(SUM(n - 1), 0) FROM (
                    SELECT COUNT(*) n FROM market_snapshots GROUP BY event_open_ms, symbol HAVING n > 1
                )
                """
            ).fetchone()[0])
            duplicate_memberships = int(conn.execute(
                """
                SELECT COALESCE(SUM(n - 1), 0) FROM (
                    SELECT COUNT(*) n FROM universe_membership GROUP BY event_open_ms, symbol HAVING n > 1
                )
                """
            ).fetchone()[0])
            duplicate_conflicts = duplicate_candles + duplicate_snapshots + duplicate_memberships
            invalid_candles = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM candles_5m c
                JOIN market_events e USING(event_open_ms)
                WHERE c.open_time_ms != c.event_open_ms
                   OR c.close_time_ms != e.event_close_ms
                   OR c.open_price <= 0 OR c.high_price <= 0 OR c.low_price <= 0 OR c.close_price <= 0
                   OR c.high_price < c.open_price OR c.high_price < c.close_price OR c.high_price < c.low_price
                   OR c.low_price > c.open_price OR c.low_price > c.close_price OR c.low_price > c.high_price
                   OR c.base_volume < 0 OR c.quote_volume < 0 OR c.trade_count < 0
                """
            ).fetchone()[0])
            future_candles = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM candles_5m c
                JOIN market_events e USING(event_open_ms)
                WHERE c.close_time_ms >= e.captured_at_ms
                """
            ).fetchone()[0])
            invalid_spreads = int(conn.execute(
                """
                SELECT COUNT(*) FROM market_snapshots
                WHERE bid_price <= 0 OR ask_price <= 0 OR ask_price < bid_price OR spread_pct < 0
                """
            ).fetchone()[0])
            point_in_time_membership_rows = int(conn.execute(
                "SELECT COUNT(*) FROM universe_membership WHERE membership_quality='POINT_IN_TIME'"
            ).fetchone()[0])
            spread_rows = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM market_snapshots s
                JOIN universe_membership u
                  ON u.event_open_ms=s.event_open_ms AND u.symbol=s.symbol
                WHERE u.membership_quality='POINT_IN_TIME'
                """
            ).fetchone()[0])
            late_point_in_time_snapshots = int(conn.execute(
                """
                SELECT COUNT(*)
                FROM market_snapshots s
                JOIN market_events e USING(event_open_ms)
                JOIN event_provenance p USING(event_open_ms)
                WHERE p.context_complete=1
                  AND s.captured_at_ms - e.event_close_ms > ?
                """,
                (self.config.max_live_context_delay_ms,),
            ).fetchone()[0])
            context_skew = conn.execute(
                """
                SELECT MAX(max_finish - min_start), AVG(max_finish - min_start)
                FROM (
                    SELECT event_open_ms, MIN(started_at_ms) min_start, MAX(finished_at_ms) max_finish
                    FROM source_captures GROUP BY event_open_ms
                )
                """
            ).fetchone()
            max_source_skew_ms = None if context_skew[0] is None else int(context_skew[0])
            avg_source_skew_ms = None if context_skew[1] is None else int(context_skew[1])
            clock_skew = conn.execute(
                """
                SELECT MAX(
                    MAX(
                        ABS(capture_started_at_ms - server_time_before_ms),
                        ABS(capture_finished_at_ms - server_time_after_ms)
                    )
                )
                FROM event_provenance
                WHERE server_time_before_ms IS NOT NULL AND server_time_after_ms IS NOT NULL
                """
            ).fetchone()[0]
            max_abs_server_clock_skew_ms = None if clock_skew is None else int(clock_skew)
            capture_stats = conn.execute(
                "SELECT MAX(capture_duration_ms), AVG(capture_duration_ms) FROM market_events WHERE status='COMPLETE'"
            ).fetchone()
            max_capture_duration_ms = None if capture_stats[0] is None else int(capture_stats[0])
            avg_capture_duration_ms = None if capture_stats[1] is None else int(capture_stats[1])

            if earliest is None or latest is None:
                expected_events = 0
                missing_events = 0
                future_event_rows = 0
                data_age_ms = None
                funding_coverage_pct = None
            else:
                interval_ms = self.config.candle_interval_ms
                expected_latest_open_ms = ((now_ms // interval_ms) - 1) * interval_ms
                if expected_latest_open_ms < earliest:
                    expected_events = 0
                    complete_expected_events = 0
                else:
                    expected_events = ((expected_latest_open_ms - earliest) // interval_ms) + 1
                    complete_expected_events = int(conn.execute(
                        "SELECT COUNT(*) FROM market_events WHERE status='COMPLETE' AND event_open_ms BETWEEN ? AND ?",
                        (earliest, expected_latest_open_ms),
                    ).fetchone()[0])
                missing_events = max(0, expected_events - complete_expected_events)
                future_event_rows = int(conn.execute(
                    "SELECT COUNT(*) FROM market_events WHERE event_open_ms > ?",
                    (expected_latest_open_ms,),
                ).fetchone()[0])
                latest_close = latest + interval_ms - 1
                data_age_ms = max(0, now_ms - latest_close)
                total_funding_span = latest_close - earliest + 1
                covered_ms = self._funding_coverage_ms(earliest, latest_close, conn)
                funding_coverage_pct = round((covered_ms / total_funding_span) * 100.0, 6)

            previous = conn.execute(
                "SELECT captured_at_ms, database_bytes FROM audit_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if previous is None or now_ms <= int(previous[0]):
                database_growth_bytes_per_hour = None
            else:
                elapsed_hours = (now_ms - int(previous[0])) / 3_600_000.0
                database_growth_bytes_per_hour = round((db_bytes - int(previous[1])) / elapsed_hours, 3)

            report: dict[str, object] = {
                "integrity": integrity,
                "foreign_key_violations": foreign_keys,
                "expected_events": expected_events,
                "complete_events": complete_events,
                "missing_events": missing_events,
                "research_ready_events": research_ready,
                "context_incomplete_events": context_incomplete_events,
                "context_incomplete_recovered_events": recovered,
                "late_migrated_events": late_migrated,
                "rejected_collection_attempts": attempts_rejected,
                "candles": candles,
                "snapshots": snapshots,
                "universe_membership_rows": membership_rows,
                "missing_membership_candles": missing_candles,
                "candle_gaps": missing_candles,
                "missing_point_in_time_snapshots": missing_snapshots,
                "incomplete_symbol_events": incomplete_symbol_events,
                "duplicate_conflicts": duplicate_conflicts,
                "invalid_candles": invalid_candles,
                "future_candles": future_candles,
                "future_event_rows": future_event_rows,
                "invalid_spreads": invalid_spreads,
                "late_point_in_time_snapshots": late_point_in_time_snapshots,
                "spread_coverage_pct": None if point_in_time_membership_rows == 0 else round((spread_rows / point_in_time_membership_rows) * 100.0, 6),
                "funding_events": funding_events,
                "funding_coverage_pct": funding_coverage_pct,
                "data_age_ms": data_age_ms,
                "max_capture_duration_ms": max_capture_duration_ms,
                "avg_capture_duration_ms": avg_capture_duration_ms,
                "max_source_capture_skew_ms": max_source_skew_ms,
                "avg_source_capture_skew_ms": avg_source_skew_ms,
                "max_abs_server_clock_skew_ms": max_abs_server_clock_skew_ms,
                "database_bytes": db_bytes,
                "wal_bytes": wal_bytes,
                "database_growth_bytes_per_hour": database_growth_bytes_per_hour,
            }
            if record:
                conn.execute(
                    """
                    INSERT INTO audit_runs(
                        captured_at_ms, database_bytes, wal_bytes,
                        complete_events, research_ready_events, report_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (now_ms, db_bytes, wal_bytes, complete_events, research_ready, json.dumps(report, sort_keys=True)),
                )
        return report

    def checkpoint(self) -> tuple[int, int, int]:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        return int(row[0]), int(row[1]), int(row[2])

    def backup(self, destination: Path | None = None) -> Path:
        self.initialize()
        if destination is None:
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            destination = self.config.backup_directory / f"observer-{stamp}.db"
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
        return destination
