from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import statistics
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import (
    CANONICAL_FEATURE_FIELDS,
    CanonicalFeatureError,
    CanonicalFeatureStore,
)
from nbot.observation.models import (
    Candle,
    SourceCapture,
    UniverseCapture,
    UniverseRow,
    spread_pct,
)


INTERVAL = 300_000
SYMBOLS = ("BTCUSDT", "AAAUSDT", "BBBUSDT")


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


def price(symbol: str, index: int) -> float:
    if symbol == "BTCUSDT":
        return 100.0 + index * 0.20
    if symbol == "AAAUSDT":
        return 50.0 + index * 0.30
    return 80.0 - index * 0.08


def make_candle(symbol: str, open_ms: int, close: float) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_ms=open_ms,
        close_time_ms=open_ms + INTERVAL - 1,
        open_price=close * 0.999,
        high_price=close * 1.003,
        low_price=close * 0.997,
        close_price=close,
        base_volume=1_000.0,
        quote_volume=1_000_000.0,
        trade_count=100,
        taker_buy_base_volume=500.0,
        taker_buy_quote_volume=500_000.0,
    )


def store_live(
    db: EvidenceDatabase,
    index: int,
    *,
    overrides: dict[str, float] | None = None,
) -> int:
    open_ms = index * INTERVAL
    close_ms = open_ms + INTERVAL - 1
    rows = []
    candles = {}
    for rank, symbol in enumerate(SYMBOLS, 1):
        close = price(symbol, index)
        if overrides and symbol in overrides:
            close = overrides[symbol]
        bid = close * 0.9999
        ask = close * 1.0001
        rows.append(
            UniverseRow(
                symbol=symbol,
                universe_rank=rank,
                quote_volume_24h_usd=30_000_000.0 / rank + index * 10_000.0,
                bid_price=bid,
                ask_price=ask,
                spread_pct=spread_pct(bid, ask),
                mark_price=close,
                index_price=close,
                funding_rate=0.0001 * rank,
                next_funding_time_ms=close_ms + 8 * 60 * 60 * 1000,
            )
        )
        candles[symbol] = make_candle(symbol, open_ms, close)

    start = close_ms + 1_000
    capture = UniverseCapture(
        rows=tuple(rows),
        source_captures=(
            SourceCapture("exchange_info", start, start + 100),
            SourceCapture("ticker_24h", start + 200, start + 300),
            SourceCapture("book_ticker", start + 400, start + 500),
            SourceCapture("premium_index", start + 600, start + 700),
        ),
    )
    result = db.store_live_event(
        event_open_ms=open_ms,
        universe_capture=capture,
        candles=candles,
        candle_errors={},
        capture_started_at_ms=close_ms + 900,
        capture_finished_at_ms=close_ms + 5_000,
        server_time_before_ms=close_ms + 850,
        server_time_after_ms=close_ms + 4_950,
    )
    if result != "COMPLETE":
        raise AssertionError(result)
    return open_ms


def row_by_symbol(rows, symbol: str):
    return next(row for row in rows if row["symbol"] == symbol)


class V341FeatureCalculationTests(unittest.TestCase):
    def test_v2_equivalent_point_in_time_features_are_calculated(self):
        with isolated_live_db() as db:
            for index in range(49):
                store_live(db, index)
            target = 48 * INTERVAL
            computed_at = target + INTERVAL + 10_000
            rows = CanonicalFeatureStore(db).compute_event_rows(
                target,
                computed_at_ms=computed_at,
            )
            aaa = row_by_symbol(rows, "AAAUSDT")

            self.assertEqual(tuple(aaa), CANONICAL_FEATURE_FIELDS)
            self.assertEqual(aaa["computed_at_ms"], computed_at)
            self.assertEqual(aaa["source_min_event_open_ms"], 0)
            self.assertEqual(aaa["source_max_event_open_ms"], target)
            self.assertEqual(aaa["history_bars"], 49)
            self.assertEqual(aaa["full_history_4h"], 1)
            for field, bars in (
                ("ret_5m", 1),
                ("ret_15m", 3),
                ("ret_30m", 6),
                ("ret_1h", 12),
                ("ret_2h", 24),
                ("ret_4h", 48),
            ):
                expected = price("AAAUSDT", 48) / price("AAAUSDT", 48 - bars) - 1.0
                self.assertAlmostEqual(aaa[field], expected, places=12)

            closes_1h = [price("AAAUSDT", index) for index in range(36, 49)]
            log_returns = [
                math.log(closes_1h[index] / closes_1h[index - 1])
                for index in range(1, len(closes_1h))
            ]
            self.assertAlmostEqual(
                aaa["realized_vol_1h"],
                math.sqrt(sum(value * value for value in log_returns)),
                places=12,
            )
            closes_4h = [price("AAAUSDT", index) for index in range(49)]
            log_returns_4h = [
                math.log(closes_4h[index] / closes_4h[index - 1])
                for index in range(1, len(closes_4h))
            ]
            self.assertAlmostEqual(
                aaa["realized_vol_4h"],
                math.sqrt(sum(value * value for value in log_returns_4h)),
                places=12,
            )

            atr_bars = []
            for index in range(34, 49):
                close = price("AAAUSDT", index)
                atr_bars.append((close * 1.003, close * 0.997, close))
            true_ranges = []
            for index in range(1, len(atr_bars)):
                high, low, _ = atr_bars[index]
                previous_close = atr_bars[index - 1][2]
                true_ranges.append(
                    max(high - low, abs(high - previous_close), abs(low - previous_close))
                )
            expected_atr = statistics.fmean(true_ranges) / price("AAAUSDT", 48)
            self.assertAlmostEqual(aaa["atr14_frac"], expected_atr, places=12)
            self.assertAlmostEqual(aaa["range_frac"], 0.006, places=12)
            self.assertAlmostEqual(aaa["quote_volume_24h_usd"], 15_480_000.0, places=6)
            self.assertAlmostEqual(aaa["spread_pct"], 0.02, places=12)
            self.assertAlmostEqual(aaa["funding_rate"], 0.0002, places=12)
            self.assertEqual(aaa["selection_rank"], 2)
            self.assertAlmostEqual(aaa["liquidity_percentile"], 0.5, places=12)
            self.assertAlmostEqual(aaa["ret_1h_percentile"], 1.0, places=12)
            self.assertAlmostEqual(aaa["ret_4h_percentile"], 1.0, places=12)
            self.assertAlmostEqual(aaa["minutes_to_next_funding"], 480.0, places=12)
            self.assertEqual(aaa["context_delay_ms"], 1_700)

            btc = row_by_symbol(rows, "BTCUSDT")
            self.assertEqual(aaa["btc_ret_5m"], btc["ret_5m"])
            self.assertEqual(aaa["btc_ret_1h"], btc["ret_1h"])
            self.assertEqual(aaa["btc_ret_4h"], btc["ret_4h"])
            self.assertAlmostEqual(aaa["breadth_positive_5m"], 2 / 3, places=12)
            self.assertAlmostEqual(aaa["breadth_positive_1h"], 2 / 3, places=12)
            expected_returns_5m = [
                price(symbol, 48) / price(symbol, 47) - 1.0 for symbol in SYMBOLS
            ]
            expected_returns_1h = [
                price(symbol, 48) / price(symbol, 36) - 1.0 for symbol in SYMBOLS
            ]
            self.assertAlmostEqual(
                aaa["median_ret_5m"], statistics.median(expected_returns_5m), places=12
            )
            self.assertAlmostEqual(
                aaa["median_ret_1h"], statistics.median(expected_returns_1h), places=12
            )
            dt = datetime.fromtimestamp((target + INTERVAL - 1) / 1000, tz=timezone.utc)
            self.assertEqual(
                (aaa["utc_hour"], aaa["utc_minute"], aaa["utc_day_of_week"]),
                (dt.hour, dt.minute, dt.weekday()),
            )

    def test_future_event_cannot_change_earlier_feature_rows(self):
        with isolated_live_db() as db:
            for index in range(49):
                store_live(db, index)
            target = 48 * INTERVAL
            store = CanonicalFeatureStore(db)
            first = store.compute_event_rows(target, computed_at_ms=20_000_000)
            store_live(db, 49, overrides={"AAAUSDT": 9_999.0})
            second = store.compute_event_rows(target, computed_at_ms=20_000_000)
            self.assertEqual(first, second)
            self.assertLess(row_by_symbol(second, "AAAUSDT")["ret_4h"], 1.0)

    def test_incomplete_history_remains_explicit_and_calculation_does_not_persist(self):
        with isolated_live_db() as db:
            target = store_live(db, 0)
            before = db.audit(now_ms=target + 2 * INTERVAL, record=False)["evidence_digest"]
            store = CanonicalFeatureStore(db)
            rows = store.compute_event_rows(target, computed_at_ms=1_000_000)
            after = db.audit(now_ms=target + 2 * INTERVAL, record=False)["evidence_digest"]
            btc = row_by_symbol(rows, "BTCUSDT")
            self.assertEqual(before, after)
            self.assertEqual((btc["history_bars"], btc["full_history_4h"]), (1, 0))
            for field in (
                "ret_5m",
                "ret_15m",
                "ret_30m",
                "ret_1h",
                "ret_2h",
                "ret_4h",
                "realized_vol_1h",
                "realized_vol_4h",
                "atr14_frac",
            ):
                self.assertIsNone(btc[field], field)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM canonical_features").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM feature_builds").fetchone()[0], 0)

    def test_recovered_candle_may_supply_past_history_but_never_be_target(self):
        with isolated_live_db() as db:
            first = store_live(db, 0)
            recovered = INTERVAL
            recovered_prices = {
                "BTCUSDT": 101.5,
                "AAAUSDT": 55.0,
                "BBBUSDT": 79.0,
            }
            status = db.store_recovered_event(
                event_open_ms=recovered,
                source_universe_event_open_ms=first,
                membership=tuple((symbol, rank) for rank, symbol in enumerate(SYMBOLS, 1)),
                candles={
                    symbol: make_candle(symbol, recovered, close)
                    for symbol, close in recovered_prices.items()
                },
                candle_errors={},
                captured_at_ms=recovered + INTERVAL + 1_000,
                capture_duration_ms=100,
                recovery_reason="V3.4.1 objective past-candle history test",
            )
            self.assertEqual(status, "COMPLETE")
            target = store_live(db, 2)
            store = CanonicalFeatureStore(db)
            aaa = row_by_symbol(
                store.compute_event_rows(target, computed_at_ms=2_000_000),
                "AAAUSDT",
            )
            expected = price("AAAUSDT", 2) / recovered_prices["AAAUSDT"] - 1.0
            self.assertAlmostEqual(aaa["ret_5m"], expected, places=12)
            self.assertEqual(aaa["history_bars"], 3)
            with self.assertRaisesRegex(
                CanonicalFeatureError,
                "FEATURE_TARGET_NOT_RESEARCH_READY",
            ):
                store.compute_event_rows(recovered, computed_at_ms=2_000_000)

    def test_same_inputs_and_computation_time_are_exactly_deterministic(self):
        with isolated_live_db() as db:
            for index in range(15):
                store_live(db, index)
            target = 14 * INTERVAL
            store = CanonicalFeatureStore(db)
            first = store.compute_event_rows(target, computed_at_ms=9_999_999)
            second = store.compute_event_rows(target, computed_at_ms=9_999_999)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
