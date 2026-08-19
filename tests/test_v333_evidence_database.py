from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import (
    RAW_EVIDENCE_TABLES,
    EvidenceDatabase,
    EvidenceDatabaseError,
)
from nbot.observation.models import Candle, SourceCapture, UniverseCapture, UniverseRow, spread_pct


EVENT_OPEN = 600_000

@contextmanager
def isolated_live_db():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as temp:
        os.chdir(temp)
        try:
            cfg = observation_config_for_profile(get_profile("live-paper"))
            yield EvidenceDatabase(cfg)
        finally:
            os.chdir(previous)


def universe_row(symbol: str, rank: int, volume: float) -> UniverseRow:
    bid = 100.0 + rank
    ask = bid + 0.05
    return UniverseRow(
        symbol=symbol,
        universe_rank=rank,
        quote_volume_24h_usd=volume,
        bid_price=bid,
        ask_price=ask,
        spread_pct=spread_pct(bid, ask),
        mark_price=bid + 0.02,
        index_price=bid + 0.01,
        funding_rate=0.0001 * rank,
        next_funding_time_ms=1_800_000,
    )


def candle(symbol: str, open_ms: int = EVENT_OPEN, close: float = 101.0) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_ms=open_ms,
        close_time_ms=open_ms + 300_000 - 1,
        open_price=100.0,
        high_price=102.0,
        low_price=99.0,
        close_price=close,
        base_volume=10.0,
        quote_volume=1_000.0,
        trade_count=20,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=500.0,
    )


def capture() -> UniverseCapture:
    return UniverseCapture(
        rows=(
            universe_row("BTCUSDT", 1, 20_000_000.0),
            universe_row("ETHUSDT", 2, 15_000_000.0),
        ),
        source_captures=(
            SourceCapture("exchange_info", 900_100, 900_110),
            SourceCapture("ticker_24h", 900_120, 900_130),
            SourceCapture("book_ticker", 900_140, 900_150),
            SourceCapture("premium_index", 900_160, 900_170),
        ),
    )


def store(db: EvidenceDatabase, *, candles=None, errors=None, universe=None):
    candles = candles or {
        "BTCUSDT": candle("BTCUSDT", close=101.0),
        "ETHUSDT": candle("ETHUSDT", close=102.0),
    }
    return db.store_live_event(
        event_open_ms=EVENT_OPEN,
        universe_capture=universe or capture(),
        candles=candles,
        candle_errors=errors or {},
        capture_started_at_ms=900_050,
        capture_finished_at_ms=900_500,
        server_time_before_ms=900_040,
        server_time_after_ms=900_490,
    )


class V333EvidenceDatabaseTests(unittest.TestCase):
    def test_initialize_creates_only_v33_raw_evidence_schema_and_metadata(self):
        with isolated_live_db() as db:
            db.initialize()
            self.assertEqual(
                db.metadata(),
                {
                    "market_environment": "LIVE",
                    "role": "OBSERVATION",
                    "schema_version": "NBOT_V3_MARKET_EVIDENCE_V1",
                },
            )
            with db.connection() as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
            self.assertEqual(tables, set(RAW_EVIDENCE_TABLES))
            self.assertNotIn("canonical_features", tables)
            self.assertNotIn("execution_outcomes", tables)
            self.assertNotIn("recommendations", tables)

    def test_sqlite_policy_is_wal_full_foreign_keys_and_busy_timeout(self):
        with isolated_live_db() as db:
            db.initialize()
            with db.connection() as conn:
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
                self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 30_000)

    def test_existing_database_environment_identity_cannot_be_relabelled(self):
        with isolated_live_db() as db:
            db.initialize()
            with db.connection() as conn:
                conn.execute("UPDATE metadata SET value='TESTNET' WHERE key='market_environment'")
            with self.assertRaisesRegex(EvidenceDatabaseError, "DB_METADATA_MISMATCH:market_environment"):
                db.initialize()
            with db.connection() as conn:
                value = conn.execute(
                    "SELECT value FROM metadata WHERE key='market_environment'"
                ).fetchone()[0]
            self.assertEqual(value, "TESTNET")

    def test_complete_event_is_one_atomic_point_in_time_evidence_unit(self):
        with isolated_live_db() as db:
            self.assertEqual(store(db), "COMPLETE")
            self.assertTrue(db.has_complete_event(EVENT_OPEN))
            with db.connection() as conn:
                event = conn.execute(
                    "SELECT status, requested_symbols, stored_symbols, error_count FROM market_events"
                ).fetchone()
                provenance = conn.execute(
                    "SELECT evidence_mode, context_complete, membership_quality FROM event_provenance"
                ).fetchone()
                counts = {
                    table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "candles_5m", "market_snapshots", "universe_membership",
                        "source_captures", "collection_attempts",
                    )
                }
            self.assertEqual(event, ("COMPLETE", 2, 2, 0))
            self.assertEqual(provenance, ("LIVE_POINT_IN_TIME", 1, "POINT_IN_TIME"))
            self.assertEqual(counts["candles_5m"], 2)
            self.assertEqual(counts["market_snapshots"], 2)
            self.assertEqual(counts["universe_membership"], 2)
            self.assertEqual(counts["source_captures"], 4)
            self.assertEqual(counts["collection_attempts"], 1)

    def test_snapshot_context_time_comes_from_point_in_time_source_capture(self):
        with isolated_live_db() as db:
            store(db)
            with db.connection() as conn:
                times = {
                    row[0] for row in conn.execute("SELECT captured_at_ms FROM market_snapshots")
                }
            self.assertEqual(times, {900_170})

    def test_partial_candle_capture_records_attempt_but_no_canonical_event(self):
        with isolated_live_db() as db:
            result = store(
                db,
                candles={"BTCUSDT": candle("BTCUSDT")},
                errors={"ETHUSDT": "NBOT_OBSERVATION_CANONICAL_CANDLE_MISSING"},
            )
            self.assertEqual(result, "PARTIAL_REJECTED")
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0], 0)
                attempt = conn.execute(
                    "SELECT result, requested_symbols, stored_symbols, error_count FROM collection_attempts"
                ).fetchone()
            self.assertEqual(attempt, ("PARTIAL_REJECTED", 2, 1, 1))

    def test_candle_set_mismatch_cannot_be_promoted_to_complete(self):
        with isolated_live_db() as db:
            result = store(db, candles={"BTCUSDT": candle("BTCUSDT")})
            self.assertEqual(result, "PARTIAL_REJECTED")
            self.assertFalse(db.has_complete_event(EVENT_OPEN))

    def test_incomplete_point_in_time_source_set_cannot_be_promoted(self):
        with isolated_live_db() as db:
            incomplete = UniverseCapture(
                rows=capture().rows,
                source_captures=(SourceCapture("ticker_24h", 900_120, 900_130),),
            )
            self.assertEqual(store(db, universe=incomplete), "PARTIAL_REJECTED")
            self.assertFalse(db.has_complete_event(EVENT_OPEN))

    def test_wrong_event_candle_identity_cannot_be_promoted(self):
        with isolated_live_db() as db:
            wrong = {
                "BTCUSDT": candle("BTCUSDT", open_ms=900_000),
                "ETHUSDT": candle("ETHUSDT", open_ms=900_000),
            }
            self.assertEqual(store(db, candles=wrong), "PARTIAL_REJECTED")
            self.assertFalse(db.has_complete_event(EVENT_OPEN))

    def test_existing_complete_event_is_immutable_on_duplicate_store(self):
        with isolated_live_db() as db:
            self.assertEqual(store(db), "COMPLETE")
            original = None
            with db.connection() as conn:
                original = conn.execute(
                    "SELECT close_price FROM candles_5m WHERE symbol='BTCUSDT'"
                ).fetchone()[0]
            replacement = {
                "BTCUSDT": candle("BTCUSDT", close=101.5),
                "ETHUSDT": candle("ETHUSDT", close=101.8),
            }
            self.assertEqual(store(db, candles=replacement), "ALREADY_COMPLETE")
            with db.connection() as conn:
                current = conn.execute(
                    "SELECT close_price FROM candles_5m WHERE symbol='BTCUSDT'"
                ).fetchone()[0]
                attempts = [
                    row[0] for row in conn.execute("SELECT result FROM collection_attempts ORDER BY id")
                ]
            self.assertEqual(current, original)
            self.assertEqual(attempts, ["COMPLETE", "ALREADY_COMPLETE"])

    def test_database_failure_rolls_back_entire_canonical_event(self):
        with isolated_live_db() as db:
            db.initialize()
            with db.connection() as conn:
                conn.execute(
                    """
                    CREATE TRIGGER fail_eth BEFORE INSERT ON candles_5m
                    WHEN NEW.symbol='ETHUSDT'
                    BEGIN
                        SELECT RAISE(ABORT, 'simulated candle insert failure');
                    END
                    """
                )
            with self.assertRaisesRegex(EvidenceDatabaseError, "ATOMIC_EVENT_STORE_FAILED"):
                store(db)
            with db.connection() as conn:
                for table in (
                    "market_events", "candles_5m", "market_snapshots",
                    "event_provenance", "universe_membership", "source_captures",
                ):
                    self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
                result = conn.execute("SELECT result FROM collection_attempts").fetchone()[0]
            self.assertEqual(result, "STORE_FAILED")

    def test_record_collection_attempt_supports_failures_before_canonical_insert(self):
        with isolated_live_db() as db:
            db.record_collection_attempt(
                event_open_ms=EVENT_OPEN,
                attempted_at_ms=900_100,
                requested_symbols=0,
                stored_symbols=0,
                error_count=1,
                result="PUBLIC_FETCH_REJECTED",
                capture_duration_ms=50,
                detail="exchange info unavailable",
            )
            with db.connection() as conn:
                row = conn.execute(
                    "SELECT result, detail FROM collection_attempts"
                ).fetchone()
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)
            self.assertEqual(row, ("PUBLIC_FETCH_REJECTED", "exchange info unavailable"))


if __name__ == "__main__":
    unittest.main()
