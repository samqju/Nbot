from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.models import Candle, SourceCapture, UniverseCapture, UniverseRow, spread_pct
from nbot.observation.observer import (
    CanonicalCollectionClock,
    MarketEvidenceCollector,
    ObservationCollectionError,
    ObservationCollectionNotReady,
    latest_completed_open_time_ms,
)


INTERVAL = 300_000
EVENT_OPEN = 600_000
EVENT_CLOSE = 899_999


def universe_row(symbol: str, rank: int) -> UniverseRow:
    bid = 100.0 + rank
    ask = bid + 0.1
    return UniverseRow(
        symbol=symbol,
        universe_rank=rank,
        quote_volume_24h_usd=20_000_000.0 - rank,
        bid_price=bid,
        ask_price=ask,
        spread_pct=spread_pct(bid, ask),
        mark_price=bid + 0.05,
        index_price=bid + 0.04,
        funding_rate=0.0001,
        next_funding_time_ms=1_800_000,
    )


def candle(symbol: str) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_ms=EVENT_OPEN,
        close_time_ms=EVENT_CLOSE,
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        base_volume=10.0,
        quote_volume=1_000.0,
        trade_count=20,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=500.0,
    )


def complete_universe(*symbols: str, start_ms: int = 904_005, finish_ms: int = 904_020):
    rows = tuple(universe_row(symbol, index) for index, symbol in enumerate(symbols, start=1))
    captures = tuple(
        SourceCapture(source, start_ms + index, finish_ms + index)
        for index, source in enumerate(
            ("exchange_info", "ticker_24h", "book_ticker", "premium_index")
        )
    )
    return UniverseCapture(rows, captures)


class FakeClient:
    def __init__(
        self,
        *,
        local_times=(904_000, 904_050),
        server_times=(904_001, 904_040),
        universe=None,
        candles=None,
        candle_errors=None,
        universe_error: Exception | None = None,
    ):
        self.local_times = list(local_times)
        self.server_times = list(server_times)
        self._last_local = int(local_times[-1])
        self._last_server = int(server_times[-1])
        self.universe = universe if universe is not None else complete_universe("BTCUSDT")
        self.candles = candles if candles is not None else {"BTCUSDT": candle("BTCUSDT")}
        self.candle_errors = candle_errors or {}
        self.universe_error = universe_error
        self.universe_calls = 0
        self.candle_calls = 0

    def local_time_ms(self):
        if self.local_times:
            self._last_local = int(self.local_times.pop(0))
        return self._last_local

    def server_time_ms(self):
        if self.server_times:
            self._last_server = int(self.server_times.pop(0))
        return self._last_server

    def eligible_universe_capture(self):
        self.universe_calls += 1
        if self.universe_error is not None:
            raise self.universe_error
        return self.universe

    def closed_candles(self, symbols, open_time_ms):
        self.candle_calls += 1
        self.last_symbols = tuple(symbols)
        self.last_open_time_ms = open_time_ms
        return self.candles, self.candle_errors

    def historical_candles_for_symbols(self, symbols, open_times_ms):
        return {}, {}

    def funding_history(self, start_time_ms, end_time_ms):
        return ()


@contextmanager
def isolated_collector(client: FakeClient):
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as temp:
        os.chdir(temp)
        try:
            cfg = observation_config_for_profile(get_profile("live-paper"))
            db = EvidenceDatabase(cfg)
            collector = MarketEvidenceCollector(cfg, client, db)
            yield cfg, db, collector
        finally:
            os.chdir(previous)


class V334CollectionClockTests(unittest.TestCase):
    def test_latest_completed_open_time_is_server_clock_aligned(self):
        self.assertEqual(latest_completed_open_time_ms(904_000), EVENT_OPEN)
        self.assertEqual(latest_completed_open_time_ms(1_199_999), EVENT_OPEN)
        self.assertEqual(latest_completed_open_time_ms(1_200_000), 900_000)

    def test_settle_delay_blocks_capture_until_ready(self):
        clock = CanonicalCollectionClock(interval_ms=INTERVAL, settle_delay_ms=4_000)
        with self.assertRaises(ObservationCollectionNotReady) as captured:
            clock.event_open_ms(903_000)
        self.assertEqual(captured.exception.wait_ms, 1_000)
        self.assertEqual(clock.event_open_ms(904_000), EVENT_OPEN)

    def test_seconds_until_next_collection_uses_current_then_next_settle_slot(self):
        clock = CanonicalCollectionClock(interval_ms=INTERVAL, settle_delay_ms=4_000)
        self.assertEqual(clock.seconds_until_next_collection(903_000), 1.0)
        self.assertEqual(clock.seconds_until_next_collection(904_000), 300.0)

    def test_complete_capture_persists_one_atomic_point_in_time_event(self):
        with isolated_collector(FakeClient()) as (_cfg, db, collector):
            result = collector.collect_once()
            self.assertEqual(result.status, "COMPLETE")
            self.assertEqual(result.event_open_ms, EVENT_OPEN)
            self.assertEqual(result.requested_symbols, 1)
            self.assertEqual(result.stored_symbols, 1)
            self.assertEqual(result.errors, 0)
            self.assertFalse(result.skipped)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0], 1)
                self.assertEqual(
                    conn.execute("SELECT context_complete FROM event_provenance").fetchone()[0], 1
                )

    def test_existing_complete_event_skips_market_capture(self):
        with isolated_collector(FakeClient()) as (cfg, db, collector):
            self.assertEqual(collector.collect_once().status, "COMPLETE")
            second_client = FakeClient(
                local_times=(905_000,),
                server_times=(905_000,),
                universe_error=AssertionError("universe capture must be skipped"),
            )
            second = MarketEvidenceCollector(cfg, second_client, db).collect_once()
            self.assertEqual(second.status, "ALREADY_COMPLETE")
            self.assertTrue(second.skipped)
            self.assertEqual(second_client.universe_calls, 0)

    def test_not_ready_fails_before_universe_or_database_event(self):
        client = FakeClient(local_times=(903_000,), server_times=(903_000,))
        with isolated_collector(client) as (_cfg, db, collector):
            with self.assertRaises(ObservationCollectionNotReady):
                collector.collect_once()
            self.assertEqual(client.universe_calls, 0)
            db.initialize()
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)

    def test_initial_clock_skew_fails_closed_before_universe_capture(self):
        client = FakeClient(local_times=(910_001,), server_times=(904_000,))
        with isolated_collector(client) as (_cfg, db, collector):
            with self.assertRaisesRegex(ObservationCollectionError, "CLOCK_SKEW_BEFORE_CAPTURE"):
                collector.collect_once()
            self.assertEqual(client.universe_calls, 0)
            db.initialize()
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)

    def test_late_point_in_time_context_rejects_atomically_without_candle_fetch(self):
        late_universe = complete_universe("BTCUSDT", start_ms=929_900, finish_ms=930_100)
        client = FakeClient(
            local_times=(904_000, 930_200),
            server_times=(904_000, 930_150),
            universe=late_universe,
        )
        with isolated_collector(client) as (cfg, db, collector):
            result = collector.collect_once()
            self.assertEqual(result.status, "PARTIAL_REJECTED")
            self.assertIsNotNone(result.context_delay_ms)
            self.assertGreater(result.context_delay_ms, cfg.max_live_context_delay_ms)
            self.assertEqual(client.candle_calls, 0)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)
                row = conn.execute(
                    "SELECT result, detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
                ).fetchone()
            self.assertEqual(row[0], "PARTIAL_REJECTED")
            self.assertIn("__LATE_CONTEXT__", row[1])

    def test_partial_candle_capture_never_creates_canonical_event(self):
        universe = complete_universe("BTCUSDT", "ETHUSDT")
        client = FakeClient(
            universe=universe,
            candles={"BTCUSDT": candle("BTCUSDT")},
            candle_errors={"ETHUSDT": "simulated missing candle"},
        )
        with isolated_collector(client) as (_cfg, db, collector):
            result = collector.collect_once()
            self.assertEqual(result.status, "PARTIAL_REJECTED")
            self.assertEqual(result.stored_symbols, 0)
            self.assertEqual(result.errors, 1)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM candles_5m").fetchone()[0], 0)

    def test_final_clock_skew_turns_full_market_fetch_into_partial_rejection(self):
        client = FakeClient(
            local_times=(904_000, 911_001),
            server_times=(904_000, 905_000),
        )
        with isolated_collector(client) as (cfg, db, collector):
            result = collector.collect_once()
            self.assertEqual(result.status, "PARTIAL_REJECTED")
            self.assertIsNotNone(result.clock_skew_after_ms)
            self.assertGreater(result.clock_skew_after_ms, cfg.max_server_clock_skew_ms)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)
                detail = conn.execute(
                    "SELECT detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
                ).fetchone()[0]
            self.assertIn("__CLOCK_SKEW_AFTER__", detail)

    def test_empty_universe_is_explicit_partial_not_complete(self):
        client = FakeClient(universe=complete_universe())
        with isolated_collector(client) as (_cfg, db, collector):
            result = collector.collect_once()
            self.assertEqual(result.status, "PARTIAL_REJECTED")
            self.assertEqual(result.requested_symbols, 0)
            self.assertEqual(client.candle_calls, 0)
            with db.connection() as conn:
                detail = conn.execute(
                    "SELECT detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
                ).fetchone()[0]
            self.assertIn("point-in-time universe is empty", detail)

    def test_whole_capture_failure_is_auditable_without_canonical_rows(self):
        client = FakeClient(universe_error=RuntimeError("simulated universe outage"))
        with isolated_collector(client) as (_cfg, db, collector):
            with self.assertRaisesRegex(ObservationCollectionError, "CAPTURE_FAILED"):
                collector.collect_once()
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0], 0)
                row = conn.execute(
                    "SELECT result, error_count, detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
                ).fetchone()
            self.assertEqual(row[0], "CAPTURE_FAILED")
            self.assertGreaterEqual(row[1], 1)
            self.assertIn("simulated universe outage", row[2])


if __name__ == "__main__":
    unittest.main()
