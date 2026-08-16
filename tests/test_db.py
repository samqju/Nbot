import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, FundingEvent, SourceCapture, UniverseRow
from nbot.config import CONFIG
from nbot.db import EvidenceDB


class DBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = replace(CONFIG, database_path=Path(self.tmp.name) / "observer.db", observation_universe_size=1)
        self.db = EvidenceDB(cfg)
        self.db.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def _row(self):
        return UniverseRow("BTCUSDT", 1, 1_000_000_000.0, 100.0, 100.1, 0.09995, 100.05, 100.04, 0.0001, 123)

    def _candle(self, open_ms=0):
        return Candle("BTCUSDT", open_ms, open_ms + 299_999, 100, 101, 99, 100.5, 10, 1000, 20, 5, 500)

    def _store_live(self, open_ms=0):
        return self.db.store_event(
            event_open_ms=open_ms,
            event_close_ms=open_ms + 299_999,
            captured_at_ms=open_ms + 400_000,
            capture_started_at_ms=open_ms + 300_100,
            server_time_before_ms=open_ms + 300_100,
            server_time_after_ms=open_ms + 400_000,
            requested_symbols=1,
            universe_rows=[self._row()],
            candles={"BTCUSDT": self._candle(open_ms)},
            error_count=0,
            capture_duration_ms=10,
        )

    def test_complete_event_has_point_in_time_provenance(self):
        self.assertEqual(self._store_live(), "COMPLETE")
        self.assertTrue(self.db.has_complete_event(0))
        status = self.db.status()
        self.assertEqual(status["events"], 1)
        self.assertEqual(status["research_ready_events"], 1)
        self.assertEqual(status["recovered_events"], 0)

    def test_partial_attempt_is_not_committed_as_market_event(self):
        status = self.db.store_event(
            event_open_ms=0,
            event_close_ms=299_999,
            captured_at_ms=400_000,
            requested_symbols=1,
            universe_rows=[self._row()],
            candles={},
            error_count=1,
            capture_duration_ms=10,
        )
        self.assertEqual(status, "PARTIAL")
        self.assertFalse(self.db.has_complete_event(0))
        self.assertEqual(self.db.status()["events"], 0)
        with self.db._connect() as conn:
            attempts = conn.execute("SELECT COUNT(*) FROM collection_attempts").fetchone()[0]
        self.assertEqual(attempts, 1)

    def test_gap_detection_is_deterministic(self):
        self._store_live(0)
        self._store_live(600_000)
        self.assertEqual(self.db.missing_event_opens(600_000), [300_000])

    def test_recovered_event_never_claims_point_in_time_context(self):
        self._store_live(0)
        source, membership = self.db.point_in_time_universe_before(300_000)
        status = self.db.store_recovered_event(
            event_open_ms=300_000,
            source_universe_event_open_ms=source,
            membership=membership,
            candles={"BTCUSDT": self._candle(300_000)},
            captured_at_ms=900_000,
            capture_duration_ms=20,
            recovery_reason="test downtime",
        )
        self.assertEqual(status, "COMPLETE")
        snapshot = self.db.status()
        self.assertEqual(snapshot["events"], 2)
        self.assertEqual(snapshot["research_ready_events"], 1)
        self.assertEqual(snapshot["recovered_events"], 1)
        self.assertEqual(snapshot["snapshots"], 1)

    def test_funding_sync_coverage_is_explicit(self):
        self._store_live(0)
        self.db.store_funding_sync(
            start_ms=0,
            end_ms=299_999,
            events=[FundingEvent("BTCUSDT", 1000, 0.0001, 100.0)],
            captured_at_ms=400_000,
        )
        report = self.db.audit(now_ms=500_000)
        self.assertEqual(report["funding_events"], 1)
        self.assertEqual(report["funding_coverage_pct"], 100.0)

    def test_audit_exposes_missing_event_and_integrity(self):
        self._store_live(0)
        self._store_live(600_000)
        report = self.db.audit(now_ms=1_000_000)
        self.assertEqual(report["integrity"], "ok")
        self.assertEqual(report["expected_events"], 3)
        self.assertEqual(report["missing_events"], 1)
        self.assertEqual(report["missing_membership_candles"], 0)
        self.assertEqual(report["candle_gaps"], 0)
        self.assertEqual(report["incomplete_symbol_events"], 0)
        self.assertEqual(report["duplicate_conflicts"], 0)
        self.assertEqual(report["invalid_candles"], 0)
        self.assertEqual(report["future_candles"], 0)

    def test_audit_detects_trailing_downtime_after_last_stored_event(self):
        self._store_live(0)
        report = self.db.audit(now_ms=1_000_000)
        self.assertEqual(report["expected_events"], 3)
        self.assertEqual(report["complete_events"], 1)
        self.assertEqual(report["missing_events"], 2)
        self.assertEqual(report["future_event_rows"], 0)


    def test_audit_flags_late_point_in_time_snapshot(self):
        self.db.store_event(
            event_open_ms=0,
            event_close_ms=299_999,
            captured_at_ms=340_000,
            capture_started_at_ms=300_100,
            server_time_before_ms=300_100,
            server_time_after_ms=340_000,
            source_captures=(SourceCapture("ticker_24h", 339_990, 340_000),),
            requested_symbols=1,
            universe_rows=[self._row()],
            candles={"BTCUSDT": self._candle(0)},
            error_count=0,
            capture_duration_ms=10,
        )
        report = self.db.audit(now_ms=400_000)
        self.assertEqual(report["late_point_in_time_snapshots"], 1)

    def test_backup_is_valid_sqlite_copy(self):
        self._store_live(0)
        target = Path(self.tmp.name) / "backup.db"
        self.db.backup(target)
        con = sqlite3.connect(target)
        try:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 1)
        finally:
            con.close()

    def test_v2_0_database_migrates_without_losing_rows(self):
        old_path = Path(self.tmp.name) / "old-v2.db"
        con = sqlite3.connect(old_path)
        try:
            con.executescript(
                """
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE market_events (
                    event_open_ms INTEGER PRIMARY KEY, event_close_ms INTEGER NOT NULL,
                    captured_at_ms INTEGER NOT NULL, requested_symbols INTEGER NOT NULL,
                    stored_symbols INTEGER NOT NULL, error_count INTEGER NOT NULL,
                    status TEXT NOT NULL, collector_version TEXT NOT NULL,
                    capture_duration_ms INTEGER NOT NULL
                );
                CREATE TABLE candles_5m (
                    event_open_ms INTEGER NOT NULL, symbol TEXT NOT NULL,
                    open_time_ms INTEGER NOT NULL, close_time_ms INTEGER NOT NULL,
                    open_price REAL NOT NULL, high_price REAL NOT NULL, low_price REAL NOT NULL,
                    close_price REAL NOT NULL, base_volume REAL NOT NULL, quote_volume REAL NOT NULL,
                    trade_count INTEGER NOT NULL, taker_buy_base_volume REAL NOT NULL,
                    taker_buy_quote_volume REAL NOT NULL, PRIMARY KEY(event_open_ms, symbol)
                );
                CREATE TABLE market_snapshots (
                    event_open_ms INTEGER NOT NULL, symbol TEXT NOT NULL, universe_rank INTEGER NOT NULL,
                    quote_volume_24h_usd REAL NOT NULL, bid_price REAL NOT NULL, ask_price REAL NOT NULL,
                    spread_pct REAL NOT NULL, mark_price REAL, index_price REAL, funding_rate REAL,
                    next_funding_time_ms INTEGER, captured_at_ms INTEGER NOT NULL,
                    PRIMARY KEY(event_open_ms, symbol)
                );
                """
            )
            # One V2.0 event is within the V2.1 30-second context window; the
            # second is late. Both raw rows must survive migration, but only
            # the timely event may remain research-ready.
            con.execute("INSERT INTO market_events VALUES (0,299999,320000,1,1,0,'COMPLETE','V2.0',100)")
            con.execute("INSERT INTO candles_5m VALUES (0,'BTCUSDT',0,299999,100,101,99,100.5,10,1000,20,5,500)")
            con.execute("INSERT INTO market_snapshots VALUES (0,'BTCUSDT',1,1000000,100,100.1,0.09995,100.05,100.04,0.0001,123,320000)")
            con.execute("INSERT INTO market_events VALUES (300000,599999,700000,1,1,0,'COMPLETE','V2.0',100)")
            con.execute("INSERT INTO candles_5m VALUES (300000,'BTCUSDT',300000,599999,100,101,99,100.5,10,1000,20,5,500)")
            con.execute("INSERT INTO market_snapshots VALUES (300000,'BTCUSDT',1,1000000,100,100.1,0.09995,100.05,100.04,0.0001,123,700000)")
            con.commit()
        finally:
            con.close()

        cfg = replace(CONFIG, database_path=old_path, observation_universe_size=1)
        migrated = EvidenceDB(cfg)
        migrated.initialize()
        status = migrated.status()
        self.assertEqual(status["events"], 2)
        self.assertEqual(status["candles"], 2)
        self.assertEqual(status["snapshots"], 2)
        self.assertEqual(status["research_ready_events"], 1)
        with migrated._connect() as con:
            rows = con.execute(
                "SELECT event_open_ms, evidence_mode, context_complete, membership_quality "
                "FROM event_provenance ORDER BY event_open_ms"
            ).fetchall()
            membership = con.execute(
                "SELECT event_open_ms, membership_quality FROM universe_membership ORDER BY event_open_ms"
            ).fetchall()
        self.assertEqual(
            rows,
            [
                (0, "LIVE_V2_0_MIGRATED", 1, "POINT_IN_TIME"),
                (300000, "LIVE_V2_0_MIGRATED", 0, "POINT_IN_TIME_LATE"),
            ],
        )
        self.assertEqual(membership, [(0, "POINT_IN_TIME"), (300000, "POINT_IN_TIME_LATE")])
        report = migrated.audit(now_ms=700001)
        self.assertEqual(report["late_point_in_time_snapshots"], 0)
        self.assertEqual(report["spread_coverage_pct"], 100.0)
        self.assertEqual(report["context_incomplete_events"], 1)
        self.assertEqual(report["context_incomplete_recovered_events"], 0)
        self.assertEqual(report["late_migrated_events"], 1)

        # Reproduce a database already migrated by the first V2.1 patch and
        # prove initialize() repairs the classification idempotently.
        with migrated._connect() as con:
            con.execute(
                "UPDATE event_provenance SET context_complete=1, membership_quality='POINT_IN_TIME' "
                "WHERE event_open_ms=300000"
            )
            con.execute(
                "UPDATE universe_membership SET membership_quality='POINT_IN_TIME' "
                "WHERE event_open_ms=300000"
            )
        migrated.initialize()
        with migrated._connect() as con:
            repaired = con.execute(
                "SELECT context_complete, membership_quality FROM event_provenance WHERE event_open_ms=300000"
            ).fetchone()
        self.assertEqual(repaired, (0, "POINT_IN_TIME_LATE"))


if __name__ == "__main__":
    unittest.main()
