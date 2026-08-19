from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import (
    CANONICAL_FEATURE_FIELDS,
    CANONICAL_FEATURE_VERSION,
    RESEARCH_FEATURE_TABLES,
    V2_REFERENCE_FEATURE_VERSION,
    CanonicalFeatureConfig,
    CanonicalFeatureError,
    CanonicalFeatureStore,
)
from nbot.observation.models import Candle, SourceCapture, UniverseCapture, UniverseRow, spread_pct


INTERVAL = 300_000
SYMBOLS = ("BTCUSDT", "ETHUSDT")


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


def candle(symbol: str, open_ms: int, close: float) -> Candle:
    return Candle(
        symbol=symbol,
        open_time_ms=open_ms,
        close_time_ms=open_ms + INTERVAL - 1,
        open_price=close * 0.999,
        high_price=close * 1.003,
        low_price=close * 0.997,
        close_price=close,
        base_volume=10.0,
        quote_volume=1_000.0,
        trade_count=20,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=500.0,
    )


def store_live(db: EvidenceDatabase, open_ms: int) -> None:
    close_ms = open_ms + INTERVAL - 1
    rows = []
    candles = {}
    for rank, symbol in enumerate(SYMBOLS, 1):
        close = 100.0 + rank
        bid = close * 0.9999
        ask = close * 1.0001
        rows.append(
            UniverseRow(
                symbol=symbol,
                universe_rank=rank,
                quote_volume_24h_usd=20_000_000.0 / rank,
                bid_price=bid,
                ask_price=ask,
                spread_pct=spread_pct(bid, ask),
                mark_price=close,
                index_price=close,
                funding_rate=0.0001 * rank,
                next_funding_time_ms=close_ms + 8 * 60 * 60 * 1000,
            )
        )
        candles[symbol] = candle(symbol, open_ms, close)
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


class V341FeatureFoundationTests(unittest.TestCase):
    def test_definition_freezes_v2_equivalent_feature_inventory_under_new_v3_version(self):
        with isolated_live_db() as db:
            store = CanonicalFeatureStore(db)
            definition = store.feature_definition()
            self.assertEqual(CANONICAL_FEATURE_VERSION, "CANONICAL_FEATURES_V3_V1")
            self.assertEqual(definition["reference_definition"], V2_REFERENCE_FEATURE_VERSION)
            self.assertEqual(definition["return_lookback_bars"], [1, 3, 6, 12, 24, 48])
            self.assertEqual((definition["realized_vol_1h_bars"], definition["realized_vol_4h_bars"]), (12, 48))
            self.assertEqual(definition["atr_bars"], 14)
            self.assertEqual(tuple(definition["fields"]), CANONICAL_FEATURE_FIELDS)
            self.assertEqual(len(store.definition_hash), 64)

    def test_same_feature_version_cannot_silently_change_semantics(self):
        changed = replace(CanonicalFeatureConfig(), atr_bars=15)
        with self.assertRaisesRegex(ValueError, "ATR_LOOKBACK_IMMUTABLE"):
            changed.validate()

    def test_derived_schema_initialization_does_not_change_raw_evidence_digest(self):
        with isolated_live_db() as db:
            store_live(db, 600_000)
            before = db.audit(now_ms=1_204_000, record=False)["evidence_digest"]
            feature_store = CanonicalFeatureStore(db)
            feature_store.initialize()
            after = db.audit(now_ms=1_204_000, record=False)["evidence_digest"]
            self.assertEqual(before, after)
            with db.connection() as conn:
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
            self.assertTrue(set(RESEARCH_FEATURE_TABLES).issubset(tables))
            self.assertNotIn("signal_annotations", tables)
            self.assertNotIn("future_paths", tables)
            self.assertNotIn("recommendations", tables)

    def test_registered_definition_hash_mismatch_fails_closed(self):
        with isolated_live_db() as db:
            store = CanonicalFeatureStore(db)
            store.initialize()
            with db.connection() as conn:
                conn.execute(
                    "UPDATE feature_sets SET definition_hash='tampered' WHERE feature_version=?",
                    (CANONICAL_FEATURE_VERSION,),
                )
            with self.assertRaisesRegex(CanonicalFeatureError, "DEFINITION_HASH_MISMATCH"):
                store.initialize()

    def test_recovered_context_incomplete_event_is_not_research_ready_target(self):
        with isolated_live_db() as db:
            first = 600_000
            recovered = first + INTERVAL
            store_live(db, first)
            status = db.store_recovered_event(
                event_open_ms=recovered,
                source_universe_event_open_ms=first,
                membership=(("BTCUSDT", 1), ("ETHUSDT", 2)),
                candles={
                    "BTCUSDT": candle("BTCUSDT", recovered, 103.0),
                    "ETHUSDT": candle("ETHUSDT", recovered, 104.0),
                },
                candle_errors={},
                captured_at_ms=recovered + INTERVAL + 1_000,
                capture_duration_ms=100,
                recovery_reason="V3.4.1 feature-target eligibility test",
            )
            self.assertEqual(status, "COMPLETE")
            self.assertEqual(CanonicalFeatureStore(db).research_ready_event_opens(), (first,))


if __name__ == "__main__":
    unittest.main()
