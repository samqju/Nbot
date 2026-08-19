from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase, EvidenceDatabaseError
from nbot.observation.models import Candle, SourceCapture, UniverseCapture, UniverseRow, spread_pct
from nbot.observation.observer import MarketEvidenceCollector


INTERVAL = 300_000
SOURCE_OPEN = 300_000
GAP_OPEN = 600_000
LATER_OPEN = 900_000


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


def make_universe(symbols: tuple[str, ...], captured_ms: int) -> UniverseCapture:
    rows = []
    for rank, symbol in enumerate(symbols, start=1):
        bid = 100.0 + rank
        ask = bid + 0.1
        rows.append(
            UniverseRow(
                symbol=symbol,
                universe_rank=rank,
                quote_volume_24h_usd=50_000_000.0 - rank,
                bid_price=bid,
                ask_price=ask,
                spread_pct=spread_pct(bid, ask),
                mark_price=bid + 0.05,
                index_price=bid + 0.04,
                funding_rate=0.0001,
                next_funding_time_ms=captured_ms + 3_600_000,
            )
        )
    captures = tuple(
        SourceCapture(source, captured_ms + offset, captured_ms + 10 + offset)
        for offset, source in enumerate(
            ("exchange_info", "ticker_24h", "book_ticker", "premium_index")
        )
    )
    return UniverseCapture(tuple(rows), captures)


def store_live(db: EvidenceDatabase, open_ms: int, symbols=("BTCUSDT", "ETHUSDT")) -> None:
    capture_start = open_ms + INTERVAL + 4_000
    universe = make_universe(tuple(symbols), capture_start)
    candles = {symbol: make_candle(symbol, open_ms) for symbol in symbols}
    status = db.store_live_event(
        event_open_ms=open_ms,
        universe_capture=universe,
        candles=candles,
        candle_errors={},
        capture_started_at_ms=capture_start,
        capture_finished_at_ms=capture_start + 100,
        server_time_before_ms=capture_start,
        server_time_after_ms=capture_start + 90,
    )
    if status != "COMPLETE":
        raise AssertionError(status)


class RecoveryClient:
    def __init__(
        self,
        *,
        server_time_ms: int = 1_204_000,
        errors: dict[str, str] | None = None,
        fail: Exception | None = None,
    ) -> None:
        self.server = server_time_ms
        self.errors = errors or {}
        self.fail = fail
        self.local = server_time_ms + 50
        self.history_calls: list[tuple[tuple[str, ...], tuple[int, ...]]] = []

    def server_time_ms(self):
        return self.server

    def local_time_ms(self):
        self.local += 5
        return self.local

    def historical_candles_for_symbols(self, symbols, open_times_ms):
        symbols = tuple(symbols)
        opens = tuple(open_times_ms)
        self.history_calls.append((symbols, opens))
        if self.fail is not None:
            raise self.fail
        history = {
            symbol: {open_ms: make_candle(symbol, open_ms) for open_ms in opens}
            for symbol in symbols
            if symbol not in self.errors
        }
        return history, self.errors

    def eligible_universe_capture(self):
        raise AssertionError("gap recovery must not request current universe context")

    def closed_candles(self, symbols, open_time_ms):
        raise AssertionError("gap recovery must use historical candle API")

    def funding_history(self, start_time_ms, end_time_ms):
        return ()


class V335GapRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.previous = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        self.cfg = observation_config_for_profile(get_profile("live-paper"))
        self.db = EvidenceDatabase(self.cfg)

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def _membership(self):
        source = self.db.point_in_time_universe_before(GAP_OPEN)
        self.assertIsNotNone(source)
        return source

    def test_missing_event_opens_detects_internal_and_trailing_gaps(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, LATER_OPEN)
        self.assertEqual(self.db.missing_event_opens(1_200_000), [GAP_OPEN, 1_200_000])

    def test_missing_event_boundary_must_be_aligned(self):
        store_live(self.db, SOURCE_OPEN)
        with self.assertRaisesRegex(EvidenceDatabaseError, "GAP_BOUNDARY_INVALID"):
            self.db.missing_event_opens(900_001)

    def test_recovered_event_is_candle_only_and_context_incomplete(self):
        store_live(self.db, SOURCE_OPEN)
        source_open, membership = self._membership()
        candles = {symbol: make_candle(symbol, GAP_OPEN) for symbol, _rank in membership}
        status = self.db.store_recovered_event(
            event_open_ms=GAP_OPEN,
            source_universe_event_open_ms=source_open,
            membership=membership,
            candles=candles,
            candle_errors={},
            captured_at_ms=1_300_000,
            capture_duration_ms=50,
            recovery_reason="test candle-only recovery",
        )
        self.assertEqual(status, "COMPLETE")
        with self.db.connection() as conn:
            provenance = conn.execute(
                "SELECT evidence_mode, context_complete, membership_quality, source_universe_event_open_ms "
                "FROM event_provenance WHERE event_open_ms=?",
                (GAP_OPEN,),
            ).fetchone()
            self.assertEqual(provenance, ("BACKFILL_CANDLE_ONLY", 0, "INHERITED", SOURCE_OPEN))
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM market_snapshots WHERE event_open_ms=?", (GAP_OPEN,)).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM source_captures WHERE event_open_ms=?", (GAP_OPEN,)).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM candles_5m WHERE event_open_ms=?", (GAP_OPEN,)).fetchone()[0],
                len(membership),
            )

    def test_recovered_event_never_becomes_point_in_time_source(self):
        store_live(self.db, SOURCE_OPEN)
        source_open, membership = self._membership()
        candles = {symbol: make_candle(symbol, GAP_OPEN) for symbol, _rank in membership}
        self.assertEqual(
            self.db.store_recovered_event(
                event_open_ms=GAP_OPEN,
                source_universe_event_open_ms=source_open,
                membership=membership,
                candles=candles,
                candle_errors={},
                captured_at_ms=1_300_000,
                capture_duration_ms=50,
                recovery_reason="test",
            ),
            "COMPLETE",
        )
        source = self.db.point_in_time_universe_before(LATER_OPEN)
        self.assertEqual(source[0], SOURCE_OPEN)

    def test_partial_recovery_missing_candle_creates_no_event(self):
        store_live(self.db, SOURCE_OPEN)
        source_open, membership = self._membership()
        candles = {membership[0][0]: make_candle(membership[0][0], GAP_OPEN)}
        status = self.db.store_recovered_event(
            event_open_ms=GAP_OPEN,
            source_universe_event_open_ms=source_open,
            membership=membership,
            candles=candles,
            candle_errors={},
            captured_at_ms=1_300_000,
            capture_duration_ms=50,
            recovery_reason="test",
        )
        self.assertEqual(status, "PARTIAL_REJECTED")
        self.assertFalse(self.db.has_complete_event(GAP_OPEN))

    def test_historical_error_creates_explicit_partial_attempt(self):
        store_live(self.db, SOURCE_OPEN)
        source_open, membership = self._membership()
        status = self.db.store_recovered_event(
            event_open_ms=GAP_OPEN,
            source_universe_event_open_ms=source_open,
            membership=membership,
            candles={},
            candle_errors={"BTCUSDT": "simulated missing history"},
            captured_at_ms=1_300_000,
            capture_duration_ms=50,
            recovery_reason="test",
        )
        self.assertEqual(status, "PARTIAL_REJECTED")
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT result, detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row[0], "RECOVERY_PARTIAL_REJECTED")
        self.assertIn("historical candle errors", row[1])

    def test_existing_point_in_time_event_is_never_rewritten_by_recovery(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, GAP_OPEN)
        source = self.db.point_in_time_universe_before(GAP_OPEN)
        status = self.db.store_recovered_event(
            event_open_ms=GAP_OPEN,
            source_universe_event_open_ms=source[0],
            membership=source[1],
            candles={symbol: make_candle(symbol, GAP_OPEN) for symbol, _rank in source[1]},
            candle_errors={},
            captured_at_ms=1_300_000,
            capture_duration_ms=50,
            recovery_reason="must not rewrite",
        )
        self.assertEqual(status, "ALREADY_COMPLETE")
        with self.db.connection() as conn:
            provenance = conn.execute(
                "SELECT evidence_mode, context_complete FROM event_provenance WHERE event_open_ms=?",
                (GAP_OPEN,),
            ).fetchone()
        self.assertEqual(provenance, ("LIVE_POINT_IN_TIME", 1))

    def test_recovery_membership_must_exactly_match_source_event(self):
        store_live(self.db, SOURCE_OPEN)
        source_open, membership = self._membership()
        wrong = ((membership[0][0], 1), ("XRPUSDT", 2))
        with self.assertRaisesRegex(EvidenceDatabaseError, "MEMBERSHIP_SOURCE_MISMATCH"):
            self.db.store_recovered_event(
                event_open_ms=GAP_OPEN,
                source_universe_event_open_ms=source_open,
                membership=wrong,
                candles={symbol: make_candle(symbol, GAP_OPEN) for symbol, _rank in wrong},
                candle_errors={},
                captured_at_ms=1_300_000,
                capture_duration_ms=50,
                recovery_reason="test",
            )

    def test_collector_recovers_gap_without_requesting_historical_context(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, LATER_OPEN)
        client = RecoveryClient()
        result = MarketEvidenceCollector(self.cfg, client, self.db).recover_gaps()
        self.assertEqual((result.missing, result.selected, result.attempted), (1, 1, 1))
        self.assertEqual((result.recovered, result.failed, result.unrecoverable), (1, 0, 0))
        self.assertEqual(client.history_calls, [(("BTCUSDT", "ETHUSDT"), (GAP_OPEN,))])
        with self.db.connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM market_snapshots WHERE event_open_ms=?", (GAP_OPEN,)).fetchone()[0],
                0,
            )

    def test_collector_limit_selects_oldest_gaps_deterministically(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, 1_500_000)
        client = RecoveryClient(server_time_ms=1_804_000)
        result = MarketEvidenceCollector(self.cfg, client, self.db).recover_gaps(max_events=2)
        self.assertEqual(result.missing, 3)
        self.assertEqual(result.selected, 2)
        self.assertEqual(result.recovered, 2)
        self.assertEqual(client.history_calls[0][1], (600_000, 900_000))
        self.assertFalse(self.db.has_complete_event(1_200_000))

    def test_recovery_fetch_failure_is_audited_and_not_promoted(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, LATER_OPEN)
        client = RecoveryClient(fail=RuntimeError("simulated history outage"))
        result = MarketEvidenceCollector(self.cfg, client, self.db).recover_gaps()
        self.assertEqual((result.attempted, result.recovered, result.failed), (1, 0, 1))
        self.assertFalse(self.db.has_complete_event(GAP_OPEN))
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT result, detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row[0], "RECOVERY_FETCH_FAILED")
        self.assertIn("simulated history outage", row[1])

    def test_no_prior_point_in_time_membership_is_explicitly_unrecoverable(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, LATER_OPEN)
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE event_provenance SET context_complete=0, membership_quality='INHERITED' "
                "WHERE event_open_ms=?",
                (SOURCE_OPEN,),
            )
            conn.execute(
                "UPDATE universe_membership SET membership_quality='INHERITED' "
                "WHERE event_open_ms=?",
                (SOURCE_OPEN,),
            )
        client = RecoveryClient()
        result = MarketEvidenceCollector(self.cfg, client, self.db).recover_gaps()
        self.assertEqual((result.missing, result.selected), (1, 1))
        self.assertEqual((result.attempted, result.recovered, result.failed), (0, 0, 0))
        self.assertEqual(result.unrecoverable, 1)
        self.assertEqual(client.history_calls, [])
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT result, detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row[0], "RECOVERY_UNRECOVERABLE")
        self.assertIn("not fabricated", row[1])

    def test_recovery_store_failure_rolls_back_all_canonical_rows(self):
        store_live(self.db, SOURCE_OPEN)
        source_open, membership = self._membership()
        candles = {symbol: make_candle(symbol, GAP_OPEN) for symbol, _rank in membership}
        with patch.object(
            EvidenceDatabase,
            "_insert_candle",
            side_effect=sqlite3.OperationalError("simulated recovery write failure"),
        ):
            with self.assertRaisesRegex(EvidenceDatabaseError, "ATOMIC_RECOVERY_STORE_FAILED"):
                self.db.store_recovered_event(
                    event_open_ms=GAP_OPEN,
                    source_universe_event_open_ms=source_open,
                    membership=membership,
                    candles=candles,
                    candle_errors={},
                    captured_at_ms=1_300_000,
                    capture_duration_ms=50,
                    recovery_reason="test rollback",
                )
        with self.db.connection() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM market_events WHERE event_open_ms=?", (GAP_OPEN,)).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM candles_5m WHERE event_open_ms=?", (GAP_OPEN,)).fetchone()[0],
                0,
            )
            row = conn.execute(
                "SELECT result, detail FROM collection_attempts ORDER BY id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row[0], "RECOVERY_STORE_FAILED")
        self.assertIn("simulated recovery write failure", row[1])

    def test_recovery_respects_settle_delay_and_disable_switch(self):
        store_live(self.db, SOURCE_OPEN)
        store_live(self.db, LATER_OPEN)
        client = RecoveryClient(server_time_ms=1_202_000)
        collector = MarketEvidenceCollector(self.cfg, client, self.db)
        self.assertEqual(collector.latest_recovery_open_ms(1_202_000), GAP_OPEN)
        self.assertEqual(collector.recover_gaps().missing, 1)

        disabled = replace(self.cfg, gap_recovery_enabled=False)
        result = MarketEvidenceCollector(disabled, client, self.db).recover_gaps()
        self.assertEqual((result.missing, result.selected, result.attempted), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
