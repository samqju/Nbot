from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase, EvidenceDatabaseError
from nbot.observation.models import Candle, SourceCapture, UniverseCapture, UniverseRow, spread_pct


INTERVAL = 300_000
FIRST_EVENT = 600_000


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


def row(symbol: str, rank: int) -> UniverseRow:
    bid = 100.0 + rank
    ask = bid + 0.05
    return UniverseRow(
        symbol=symbol,
        universe_rank=rank,
        quote_volume_24h_usd=20_000_000.0 - rank * 1_000_000.0,
        bid_price=bid,
        ask_price=ask,
        spread_pct=spread_pct(bid, ask),
        mark_price=bid + 0.02,
        index_price=bid + 0.01,
        funding_rate=0.0001,
        next_funding_time_ms=2_400_000,
    )


def candle(symbol: str, event_open_ms: int, close: float) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_ms=event_open_ms,
        close_time_ms=event_open_ms + INTERVAL - 1,
        open_price=100.0,
        high_price=max(102.0, close),
        low_price=99.0,
        close_price=close,
        base_volume=10.0,
        quote_volume=1_000.0,
        trade_count=20,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=500.0,
    )


def capture(event_open_ms: int) -> UniverseCapture:
    close_ms = event_open_ms + INTERVAL - 1
    return UniverseCapture(
        rows=(row("BTCUSDT", 1), row("ETHUSDT", 2)),
        source_captures=(
            SourceCapture("exchange_info", close_ms + 100, close_ms + 110),
            SourceCapture("ticker_24h", close_ms + 120, close_ms + 130),
            SourceCapture("book_ticker", close_ms + 140, close_ms + 150),
            SourceCapture("premium_index", close_ms + 160, close_ms + 170),
        ),
    )


def store_live(db: EvidenceDatabase, event_open_ms: int = FIRST_EVENT) -> None:
    close_ms = event_open_ms + INTERVAL - 1
    result = db.store_live_event(
        event_open_ms=event_open_ms,
        universe_capture=capture(event_open_ms),
        candles={
            "BTCUSDT": candle("BTCUSDT", event_open_ms, 101.0),
            "ETHUSDT": candle("ETHUSDT", event_open_ms, 102.0),
        },
        candle_errors={},
        capture_started_at_ms=close_ms + 50,
        capture_finished_at_ms=close_ms + 500,
        server_time_before_ms=close_ms + 40,
        server_time_after_ms=close_ms + 490,
    )
    if result != "COMPLETE":
        raise AssertionError(result)


def cover_funding(db: EvidenceDatabase, start_open: int, end_open: int, captured_at_ms: int) -> None:
    db.store_funding_sync(
        start_ms=start_open,
        end_ms=end_open + INTERVAL - 1,
        events=(),
        captured_at_ms=captured_at_ms,
    )


def clean_audit(db: EvidenceDatabase, event_open_ms: int = FIRST_EVENT):
    now_ms = event_open_ms + INTERVAL + 4_000
    cover_funding(db, event_open_ms, event_open_ms, now_ms)
    return db.audit(now_ms=now_ms)


class V337DatabaseOpsAuditTests(unittest.TestCase):
    def test_integrity_check_is_clean_for_initialized_database(self):
        with isolated_live_db() as db:
            db.initialize()
            self.assertEqual(
                db.integrity_check(),
                {"integrity": "ok", "foreign_key_violations": 0, "ok": True},
            )

    def test_integrity_check_reports_foreign_key_violation(self):
        with isolated_live_db() as db:
            db.initialize()
            raw = sqlite3.connect(db.path)
            try:
                raw.execute("PRAGMA foreign_keys=OFF")
                raw.execute(
                    "INSERT INTO source_captures VALUES (999999, 'ticker_24h', 1, 2)"
                )
                raw.commit()
            finally:
                raw.close()
            report = db.integrity_check()
            self.assertEqual(report["integrity"], "ok")
            self.assertEqual(report["foreign_key_violations"], 1)
            self.assertFalse(report["ok"])

    def test_checkpoint_returns_sqlite_result_and_truncates_wal(self):
        with isolated_live_db() as db:
            store_live(db)
            result = db.checkpoint()
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0], 0)
            wal = Path(str(db.path) + "-wal")
            self.assertTrue(not wal.exists() or wal.stat().st_size == 0)

    def test_backup_is_verified_and_restores_same_logical_evidence(self):
        with isolated_live_db() as db:
            store_live(db)
            source = clean_audit(db)
            backup = db.backup(Path("backup/observer-copy.db"))
            self.assertTrue(backup.exists())

            restore_root = Path.cwd() / "restored"
            restored_path = restore_root / "data/observation/live/observer.db"
            restored_path.parent.mkdir(parents=True)
            shutil.copy2(backup, restored_path)
            previous = Path.cwd()
            os.chdir(restore_root)
            try:
                restored_cfg = observation_config_for_profile(get_profile("live-paper"))
                restored = EvidenceDatabase(restored_cfg)
                restored_report = restored.audit(now_ms=FIRST_EVENT + INTERVAL + 4_000)
            finally:
                os.chdir(previous)
            self.assertEqual(restored_report["evidence_digest"], source["evidence_digest"])
            self.assertEqual(restored_report["audit_digest"], source["audit_digest"])
            self.assertTrue(restored_report["healthy"])

    def test_backup_refuses_to_overwrite_live_database(self):
        with isolated_live_db() as db:
            db.initialize()
            with self.assertRaisesRegex(EvidenceDatabaseError, "BACKUP_TARGET_IS_SOURCE"):
                db.backup(db.path)

    def test_empty_database_audit_is_deterministic_and_clean(self):
        with isolated_live_db() as db:
            first = db.audit(now_ms=1_000_000)
            second = db.audit(now_ms=1_000_000)
            self.assertEqual(first["evidence_digest"], second["evidence_digest"])
            self.assertEqual(first["audit_digest"], second["audit_digest"])
            self.assertEqual(first["complete_events"], 0)
            self.assertEqual(first["event_gap_count"], 0)
            self.assertIsNone(first["funding_coverage_complete"])
            self.assertTrue(first["healthy"])

    def test_clean_point_in_time_event_audit_is_research_ready(self):
        with isolated_live_db() as db:
            store_live(db)
            report = clean_audit(db)
            self.assertTrue(report["healthy"])
            self.assertEqual(report["complete_events"], 1)
            self.assertEqual(report["research_ready_events"], 1)
            self.assertEqual(report["context_incomplete_events"], 0)
            self.assertEqual(report["event_gap_count"], 0)
            self.assertEqual(report["missing_point_in_time_snapshots"], 0)
            self.assertEqual(report["source_capture_missing_required_events"], 0)
            self.assertTrue(report["funding_coverage_complete"])

    def test_audit_detects_internal_completed_candle_gap(self):
        with isolated_live_db() as db:
            store_live(db, FIRST_EVENT)
            store_live(db, FIRST_EVENT + 2 * INTERVAL)
            now_ms = FIRST_EVENT + 3 * INTERVAL + 4_000
            cover_funding(db, FIRST_EVENT, FIRST_EVENT + 2 * INTERVAL, now_ms)
            report = db.audit(now_ms=now_ms)
            self.assertEqual(report["internal_event_gaps"], 1)
            self.assertEqual(report["trailing_event_gaps"], 0)
            self.assertEqual(report["event_gap_count"], 1)
            self.assertFalse(report["healthy"])

    def test_audit_detects_trailing_downtime_after_last_event(self):
        with isolated_live_db() as db:
            store_live(db)
            cover_funding(db, FIRST_EVENT, FIRST_EVENT, FIRST_EVENT + 2 * INTERVAL + 4_000)
            report = db.audit(now_ms=FIRST_EVENT + 2 * INTERVAL + 4_000)
            self.assertEqual(report["internal_event_gaps"], 0)
            self.assertEqual(report["trailing_event_gaps"], 1)
            self.assertEqual(report["event_gap_count"], 1)
            self.assertFalse(report["healthy"])

    def test_audit_flags_late_point_in_time_snapshot_context(self):
        with isolated_live_db() as db:
            store_live(db)
            close_ms = FIRST_EVENT + INTERVAL - 1
            with db.connection() as conn:
                conn.execute(
                    "UPDATE market_snapshots SET captured_at_ms=? WHERE symbol='BTCUSDT'",
                    (close_ms + db.config.max_live_context_delay_ms + 1,),
                )
            report = clean_audit(db)
            self.assertEqual(report["late_point_in_time_snapshots"], 1)
            self.assertEqual(report["late_context_events"], 1)
            self.assertFalse(report["healthy"])

    def test_audit_flags_late_source_capture_context(self):
        with isolated_live_db() as db:
            store_live(db)
            close_ms = FIRST_EVENT + INTERVAL - 1
            late = close_ms + db.config.max_live_context_delay_ms + 1
            with db.connection() as conn:
                conn.execute(
                    "UPDATE source_captures SET finished_at_ms=? WHERE source='premium_index'",
                    (late,),
                )
                conn.execute(
                    "UPDATE event_provenance SET capture_finished_at_ms=?, server_time_after_ms=?",
                    (late, late - 10),
                )
            report = clean_audit(db)
            self.assertEqual(report["late_source_captures"], 1)
            self.assertEqual(report["late_context_events"], 1)
            self.assertEqual(report["source_capture_outside_event_bounds"], 0)
            self.assertFalse(report["healthy"])

    def test_audit_flags_server_clock_skew_violation(self):
        with isolated_live_db() as db:
            store_live(db)
            with db.connection() as conn:
                started = conn.execute(
                    "SELECT capture_started_at_ms FROM event_provenance"
                ).fetchone()[0]
                conn.execute(
                    "UPDATE event_provenance SET server_time_before_ms=?",
                    (int(started) - db.config.max_server_clock_skew_ms - 1,),
                )
            report = clean_audit(db)
            self.assertEqual(report["server_clock_skew_violations"], 1)
            self.assertFalse(report["healthy"])

    def test_audit_flags_missing_required_source_capture(self):
        with isolated_live_db() as db:
            store_live(db)
            with db.connection() as conn:
                conn.execute("DELETE FROM source_captures WHERE source='book_ticker'")
            report = clean_audit(db)
            self.assertEqual(report["source_capture_missing_required_events"], 1)
            self.assertFalse(report["healthy"])

    def test_audit_flags_source_capture_outside_event_capture_bounds(self):
        with isolated_live_db() as db:
            store_live(db)
            with db.connection() as conn:
                started = conn.execute(
                    "SELECT capture_started_at_ms FROM event_provenance"
                ).fetchone()[0]
                conn.execute(
                    "UPDATE source_captures SET started_at_ms=? WHERE source='exchange_info'",
                    (int(started) - 1,),
                )
            report = clean_audit(db)
            self.assertEqual(report["source_capture_outside_event_bounds"], 1)
            self.assertFalse(report["healthy"])

    def test_recovered_candle_only_event_remains_explicitly_not_research_ready(self):
        with isolated_live_db() as db:
            store_live(db)
            recovered_open = FIRST_EVENT + INTERVAL
            status = db.store_recovered_event(
                event_open_ms=recovered_open,
                source_universe_event_open_ms=FIRST_EVENT,
                membership=(("BTCUSDT", 1), ("ETHUSDT", 2)),
                candles={
                    "BTCUSDT": candle("BTCUSDT", recovered_open, 103.0),
                    "ETHUSDT": candle("ETHUSDT", recovered_open, 104.0),
                },
                candle_errors={},
                captured_at_ms=recovered_open + INTERVAL + 500,
                capture_duration_ms=100,
                recovery_reason="test honest recovery",
            )
            self.assertEqual(status, "COMPLETE")
            now_ms = recovered_open + INTERVAL + 4_000
            cover_funding(db, FIRST_EVENT, recovered_open, now_ms)
            report = db.audit(now_ms=now_ms)
            self.assertEqual(report["complete_events"], 2)
            self.assertEqual(report["research_ready_events"], 1)
            self.assertEqual(report["context_incomplete_events"], 1)
            self.assertEqual(report["recovered_events"], 1)
            self.assertEqual(report["missing_point_in_time_snapshots"], 0)
            self.assertEqual(report["recovered_fabricated_context_rows"], 0)
            self.assertTrue(report["healthy"])

    def test_audit_detects_fabricated_context_on_recovered_event(self):
        with isolated_live_db() as db:
            store_live(db)
            recovered_open = FIRST_EVENT + INTERVAL
            db.store_recovered_event(
                event_open_ms=recovered_open,
                source_universe_event_open_ms=FIRST_EVENT,
                membership=(("BTCUSDT", 1), ("ETHUSDT", 2)),
                candles={
                    "BTCUSDT": candle("BTCUSDT", recovered_open, 103.0),
                    "ETHUSDT": candle("ETHUSDT", recovered_open, 104.0),
                },
                candle_errors={},
                captured_at_ms=recovered_open + INTERVAL + 500,
                capture_duration_ms=100,
                recovery_reason="test honest recovery",
            )
            with db.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO market_snapshots VALUES (?, 'BTCUSDT', 1, 10000000,
                    100, 100.05, 0.05, 100.02, 100.01, 0.0001, 2400000, ?)
                    """,
                    (recovered_open, recovered_open + INTERVAL + 100),
                )
            now_ms = recovered_open + INTERVAL + 4_000
            cover_funding(db, FIRST_EVENT, recovered_open, now_ms)
            report = db.audit(now_ms=now_ms)
            self.assertEqual(report["recovered_fabricated_context_rows"], 1)
            self.assertFalse(report["healthy"])

    def test_incomplete_funding_coverage_is_explicit_and_fails_clean_audit(self):
        with isolated_live_db() as db:
            store_live(db)
            report = db.audit(now_ms=FIRST_EVENT + INTERVAL + 4_000)
            self.assertEqual(report["funding_coverage_pct"], 0.0)
            self.assertFalse(report["funding_coverage_complete"])
            self.assertFalse(report["healthy"])

    def test_audit_record_is_canonical_and_does_not_change_audit_identity(self):
        with isolated_live_db() as db:
            store_live(db)
            now_ms = FIRST_EVENT + INTERVAL + 4_000
            cover_funding(db, FIRST_EVENT, FIRST_EVENT, now_ms)
            before = db.audit(now_ms=now_ms)
            recorded = db.audit(now_ms=now_ms, record=True)
            after = db.audit(now_ms=now_ms)
            self.assertEqual(before["evidence_digest"], recorded["evidence_digest"])
            self.assertEqual(before["audit_digest"], recorded["audit_digest"])
            self.assertEqual(before["audit_digest"], after["audit_digest"])
            with db.connection() as conn:
                raw = conn.execute("SELECT report_json FROM audit_runs").fetchone()[0]
            parsed = json.loads(raw)
            self.assertEqual(parsed["audit_digest"], before["audit_digest"])
            self.assertEqual(
                raw,
                json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
            )

    def test_evidence_digest_changes_when_raw_source_evidence_changes(self):
        with isolated_live_db() as db:
            store_live(db)
            now_ms = FIRST_EVENT + INTERVAL + 4_000
            cover_funding(db, FIRST_EVENT, FIRST_EVENT, now_ms)
            before = db.audit(now_ms=now_ms)
            with db.connection() as conn:
                conn.execute(
                    "UPDATE market_snapshots SET quote_volume_24h_usd=quote_volume_24h_usd+1 "
                    "WHERE symbol='BTCUSDT'"
                )
            after = db.audit(now_ms=now_ms)
            self.assertNotEqual(before["evidence_digest"], after["evidence_digest"])
            self.assertNotEqual(before["audit_digest"], after["audit_digest"])


if __name__ == "__main__":
    unittest.main()
