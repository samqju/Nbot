from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase, EvidenceDatabaseError
from nbot.observation.models import Candle, FundingEvent, SourceCapture, UniverseCapture, UniverseRow, spread_pct
from nbot.observation.observer import MarketEvidenceCollector, ObservationCollectionError


INTERVAL = 300_000
EVENT_OPEN = 600_000


def make_candle(symbol: str, open_ms: int) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_ms=open_ms,
        close_time_ms=open_ms + INTERVAL - 1,
        open_price=100.0,
        high_price=102.0,
        low_price=99.0,
        close_price=101.0,
        base_volume=10.0,
        quote_volume=1_000.0,
        trade_count=20,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=500.0,
    )


def store_live(db: EvidenceDatabase, open_ms: int = EVENT_OPEN) -> None:
    captured = open_ms + INTERVAL + 4_000
    bid = 100.0
    ask = 100.1
    universe = UniverseCapture(
        rows=(
            UniverseRow(
                "BTCUSDT", 1, 50_000_000.0, bid, ask, spread_pct(bid, ask),
                100.05, 100.04, 0.0001, captured + 3_600_000,
            ),
        ),
        source_captures=tuple(
            SourceCapture(source, captured + offset, captured + offset + 1)
            for offset, source in enumerate(
                ("exchange_info", "ticker_24h", "book_ticker", "premium_index")
            )
        ),
    )
    status = db.store_live_event(
        event_open_ms=open_ms,
        universe_capture=universe,
        candles={"BTCUSDT": make_candle("BTCUSDT", open_ms)},
        candle_errors={},
        capture_started_at_ms=captured,
        capture_finished_at_ms=captured + 20,
        server_time_before_ms=captured,
        server_time_after_ms=captured + 10,
    )
    if status != "COMPLETE":
        raise AssertionError(status)


class FundingClient:
    def __init__(self, *, server_ms=1_500_000, events=(), fail=None, local_offset=50):
        self.server = int(server_ms)
        self.events = tuple(events)
        self.fail = fail
        self.local = self.server + int(local_offset)
        self.calls = []

    def server_time_ms(self):
        return self.server

    def local_time_ms(self):
        self.local += 5
        return self.local

    def funding_history(self, start_time_ms, end_time_ms):
        self.calls.append((int(start_time_ms), int(end_time_ms)))
        if self.fail is not None:
            raise self.fail
        return tuple(
            event for event in self.events
            if start_time_ms <= event.funding_time_ms <= end_time_ms
        )

    def eligible_universe_capture(self):
        raise AssertionError("funding sync must not request point-in-time universe")

    def closed_candles(self, symbols, open_time_ms):
        raise AssertionError("funding sync must not request candles")

    def historical_candles_for_symbols(self, symbols, open_times_ms):
        raise AssertionError("funding sync must not request recovery candles")


class V336FundingHistoryTests(unittest.TestCase):
    def setUp(self):
        self.previous = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        self.cfg = observation_config_for_profile(get_profile("live-paper"))
        self.db = EvidenceDatabase(self.cfg)

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def test_funding_sync_starts_at_earliest_canonical_market_event(self):
        self.assertIsNone(self.db.funding_sync_start_ms())
        store_live(self.db, EVENT_OPEN)
        self.assertEqual(self.db.funding_sync_start_ms(), EVENT_OPEN)

    def test_store_funding_sync_persists_events_and_explicit_range(self):
        event = FundingEvent("BTCUSDT", 700_000, 0.0001, 100.5)
        self.assertEqual(
            self.db.store_funding_sync(
                start_ms=600_000, end_ms=900_000, events=(event,), captured_at_ms=910_000
            ),
            1,
        )
        with self.db.connection() as conn:
            funding = conn.execute(
                "SELECT symbol, funding_time_ms, funding_rate, mark_price, ingested_at_ms FROM funding_events"
            ).fetchone()
            sync = conn.execute(
                "SELECT start_ms, end_ms, captured_at_ms, row_count FROM funding_sync_ranges"
            ).fetchone()
        self.assertEqual(funding, ("BTCUSDT", 700_000, 0.0001, 100.5, 910_000))
        self.assertEqual(sync, (600_000, 900_000, 910_000, 1))
        self.assertEqual(self.db.funding_sync_bounds(), (600_000, 900_000))
        self.assertEqual(self.db.funding_sync_start_ms(), 900_001)

    def test_zero_row_sync_still_proves_coverage(self):
        self.assertEqual(
            self.db.store_funding_sync(
                start_ms=10, end_ms=20, events=(), captured_at_ms=30
            ),
            0,
        )
        coverage = self.db.funding_coverage(10, 20)
        self.assertTrue(coverage.complete)
        self.assertEqual((coverage.covered_ms, coverage.total_ms, coverage.coverage_pct), (11, 11, 100.0))
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT row_count FROM funding_sync_ranges").fetchone()[0], 0)

    def test_coverage_merges_overlap_and_exposes_real_gap(self):
        self.db.store_funding_sync(start_ms=0, end_ms=99, events=(), captured_at_ms=100)
        self.db.store_funding_sync(start_ms=50, end_ms=149, events=(), captured_at_ms=200)
        self.db.store_funding_sync(start_ms=200, end_ms=249, events=(), captured_at_ms=300)
        coverage = self.db.funding_coverage(0, 249)
        self.assertFalse(coverage.complete)
        self.assertEqual((coverage.covered_ms, coverage.total_ms, coverage.coverage_pct), (200, 250, 80.0))

    def test_out_of_range_or_duplicate_funding_event_is_rejected(self):
        event = FundingEvent("BTCUSDT", 100, 0.0001, 100.0)
        with self.assertRaisesRegex(EvidenceDatabaseError, "FUNDING_EVENT_OUTSIDE_SYNC_RANGE"):
            self.db.store_funding_sync(start_ms=101, end_ms=200, events=(event,), captured_at_ms=300)
        with self.assertRaisesRegex(EvidenceDatabaseError, "FUNDING_EVENT_DUPLICATE"):
            self.db.store_funding_sync(start_ms=0, end_ms=200, events=(event, event), captured_at_ms=300)

    def test_identical_refetch_is_idempotent_and_preserves_first_ingest_time(self):
        event = FundingEvent("BTCUSDT", 100, 0.0001, 100.0)
        self.db.store_funding_sync(start_ms=0, end_ms=200, events=(event,), captured_at_ms=300)
        self.db.store_funding_sync(start_ms=0, end_ms=200, events=(event,), captured_at_ms=400)
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT funding_rate, mark_price, ingested_at_ms FROM funding_events"
            ).fetchall()
            range_count = conn.execute("SELECT COUNT(*) FROM funding_sync_ranges").fetchone()[0]
        self.assertEqual(rows, [(0.0001, 100.0, 300)])
        self.assertEqual(range_count, 2)

    def test_conflicting_refetch_fails_closed_and_rolls_back_range(self):
        first = FundingEvent("BTCUSDT", 100, 0.0001, 100.0)
        changed = FundingEvent("BTCUSDT", 100, 0.0002, 100.0)
        self.db.store_funding_sync(start_ms=0, end_ms=200, events=(first,), captured_at_ms=300)
        with self.assertRaisesRegex(EvidenceDatabaseError, "FUNDING_EVENT_CONFLICT"):
            self.db.store_funding_sync(start_ms=0, end_ms=250, events=(changed,), captured_at_ms=400)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT funding_rate FROM funding_events").fetchone()[0], 0.0001)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM funding_sync_ranges").fetchone()[0], 1)

    def test_sqlite_failure_rolls_back_funding_events_and_range(self):
        event = FundingEvent("BTCUSDT", 100, 0.0001, 100.0)
        # Force failure only at range insertion after the funding row would have been inserted.
        self.db.initialize()
        with self.db.connection() as conn:
            conn.execute(
                "CREATE TRIGGER fail_funding_range BEFORE INSERT ON funding_sync_ranges "
                "BEGIN SELECT RAISE(ABORT, 'simulated funding range failure'); END"
            )
        with self.assertRaisesRegex(EvidenceDatabaseError, "ATOMIC_FUNDING_SYNC_STORE_FAILED"):
            self.db.store_funding_sync(start_ms=0, end_ms=200, events=(event,), captured_at_ms=300)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM funding_sync_ranges").fetchone()[0], 0)

    def test_funding_sync_due_uses_configured_interval_and_rejects_clock_reverse(self):
        self.assertTrue(self.db.funding_sync_due(1000))
        self.db.store_funding_sync(start_ms=0, end_ms=10, events=(), captured_at_ms=1000)
        self.assertFalse(self.db.funding_sync_due(1000 + 299_999))
        self.assertTrue(self.db.funding_sync_due(1000 + 300_000))
        with self.assertRaisesRegex(EvidenceDatabaseError, "FUNDING_SYNC_CLOCK_REVERSED"):
            self.db.funding_sync_due(999)

    def test_collector_skips_funding_sync_without_market_event(self):
        client = FundingClient()
        result = MarketEvidenceCollector(self.cfg, client, self.db).sync_funding_history(force=True)
        self.assertTrue(result.skipped)
        self.assertEqual(result.reason, "NO_MARKET_EVENTS")
        self.assertEqual(client.calls, [])

    def test_collector_syncs_from_event_history_to_server_time(self):
        store_live(self.db, EVENT_OPEN)
        events = (
            FundingEvent("BTCUSDT", 700_000, 0.0001, 100.0),
            FundingEvent("ETHUSDT", 1_200_000, -0.0002, 200.0),
        )
        client = FundingClient(server_ms=1_500_000, events=events)
        result = MarketEvidenceCollector(self.cfg, client, self.db).sync_funding_history(force=True)
        self.assertFalse(result.skipped)
        self.assertEqual((result.rows, result.start_ms, result.end_ms, result.reason), (2, EVENT_OPEN, 1_500_000, "COMPLETE"))
        self.assertEqual(client.calls, [(EVENT_OPEN, 1_500_000)])
        self.assertTrue(self.db.funding_coverage(EVENT_OPEN, 1_500_000).complete)

    def test_collector_second_sync_advances_cursor_without_overlap(self):
        store_live(self.db, EVENT_OPEN)
        client = FundingClient(server_ms=1_000_000)
        collector = MarketEvidenceCollector(self.cfg, client, self.db)
        first = collector.sync_funding_history(force=True)
        self.assertEqual(first.start_ms, EVENT_OPEN)
        client.server = 1_100_000
        client.local = 1_100_050
        second = collector.sync_funding_history(force=True)
        self.assertEqual(second.start_ms, 1_000_001)
        self.assertEqual(client.calls, [(EVENT_OPEN, 1_000_000), (1_000_001, 1_100_000)])

    def test_collector_nonforced_sync_respects_interval(self):
        store_live(self.db, EVENT_OPEN)
        client = FundingClient(server_ms=1_000_000)
        collector = MarketEvidenceCollector(self.cfg, client, self.db)
        first = collector.sync_funding_history(force=True)
        self.assertFalse(first.skipped)
        client.server = 1_100_000
        client.local = 1_100_050
        second = collector.sync_funding_history(force=False)
        self.assertTrue(second.skipped)
        self.assertEqual(second.reason, "NOT_DUE")
        self.assertEqual(len(client.calls), 1)

    def test_collector_clock_skew_fails_closed_before_funding_fetch(self):
        store_live(self.db, EVENT_OPEN)
        client = FundingClient(server_ms=1_000_000, local_offset=20_000)
        with self.assertRaisesRegex(ObservationCollectionError, "FUNDING_CLOCK_SKEW"):
            MarketEvidenceCollector(self.cfg, client, self.db).sync_funding_history(force=True)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.db.funding_sync_bounds(), (None, None))

    def test_funding_fetch_failure_does_not_claim_coverage(self):
        store_live(self.db, EVENT_OPEN)
        client = FundingClient(server_ms=1_000_000, fail=RuntimeError("network down"))
        with self.assertRaisesRegex(RuntimeError, "network down"):
            MarketEvidenceCollector(self.cfg, client, self.db).sync_funding_history(force=True)
        self.assertEqual(self.db.funding_sync_bounds(), (None, None))


if __name__ == "__main__":
    unittest.main()
