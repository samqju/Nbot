from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.models import (
    Candle,
    FundingEvent,
    SourceCapture,
    UniverseCapture,
    UniverseRow,
    spread_pct,
)
from nbot.observation.outcomes import (
    COST_VERSION,
    FUTURE_PATH_TABLES,
    OUTCOME_VERSION,
    RISK_UNIT_VERSION,
    FuturePathConfig,
    FuturePathError,
    FuturePathStore,
    _barrier_hits,
)


INTERVAL = 300_000
SYMBOL = "AAAUSDT"
TARGET_INDEX = 14
TARGET_OPEN = TARGET_INDEX * INTERVAL
EXPECTED_DEFINITION_HASH = "7a216c7ff1e078ad7e07c63b530d65beee712d7cd1e74f8066ce686761a52d97"


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


def candle_for_index(index: int, *, extreme_first_future: bool = False) -> Candle:
    close = 100.0 + index
    if extreme_first_future and index == TARGET_INDEX + 1:
        high = 116.5
        low = 111.5
    else:
        high = close + 1.0
        low = close - 1.0
    return Candle(
        symbol=SYMBOL,
        open_time_ms=index * INTERVAL,
        close_time_ms=(index + 1) * INTERVAL - 1,
        open_price=close,
        high_price=high,
        low_price=low,
        close_price=close,
        base_volume=1_000.0,
        quote_volume=100_000.0 + index,
        trade_count=100 + index,
        taker_buy_base_volume=500.0,
        taker_buy_quote_volume=50_000.0 + index,
    )


def store_live(db: EvidenceDatabase, index: int, *, extreme_first_future: bool = False) -> int:
    open_ms = index * INTERVAL
    close_ms = open_ms + INTERVAL - 1
    close = 100.0 + index
    bid = close * 0.9999
    ask = close * 1.0001
    start = close_ms + 1_000
    capture = UniverseCapture(
        rows=(
            UniverseRow(
                symbol=SYMBOL,
                universe_rank=1,
                quote_volume_24h_usd=50_000_000.0,
                bid_price=bid,
                ask_price=ask,
                spread_pct=spread_pct(bid, ask),
                mark_price=close,
                index_price=close,
                funding_rate=0.0001,
                next_funding_time_ms=close_ms + 8 * 60 * 60 * 1000,
            ),
        ),
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
        candles={SYMBOL: candle_for_index(index, extreme_first_future=extreme_first_future)},
        candle_errors={},
        capture_started_at_ms=close_ms + 900,
        capture_finished_at_ms=close_ms + 5_000,
        server_time_before_ms=close_ms + 850,
        server_time_after_ms=close_ms + 4_950,
    )
    if result != "COMPLETE":
        raise AssertionError(result)
    return open_ms


def store_recovered(
    db: EvidenceDatabase,
    index: int,
    *,
    source_index: int,
    extreme_first_future: bool = False,
) -> None:
    result = db.store_recovered_event(
        event_open_ms=index * INTERVAL,
        source_universe_event_open_ms=source_index * INTERVAL,
        membership=((SYMBOL, 1),),
        candles={SYMBOL: candle_for_index(index, extreme_first_future=extreme_first_future)},
        candle_errors={},
        captured_at_ms=(index + 1) * INTERVAL + 20_000,
        capture_duration_ms=10,
        recovery_reason="V3.4.3 deterministic test candle history",
    )
    if result != "COMPLETE":
        raise AssertionError(result)


class FakePublicClient:
    def __init__(
        self,
        *,
        server_time_ms: int = 64 * INTERVAL + 1_000,
        fallback: dict[int, Candle] | None = None,
        fail: bool = False,
    ) -> None:
        self._server_time_ms = server_time_ms
        self.fallback = fallback or {}
        self.fail = fail

    def server_time_ms(self) -> int:
        return self._server_time_ms

    def historical_candles_for_symbols(self, symbols, open_times_ms):
        if self.fail:
            raise RuntimeError("synthetic historical fetch failure")
        output = {}
        errors = {}
        opens = tuple(int(value) for value in open_times_ms)
        for symbol in tuple(symbols):
            rows = {}
            for open_ms in opens:
                candle = self.fallback.get(open_ms)
                if candle is None:
                    errors[str(symbol)] = f"missing {open_ms}"
                    break
                rows[open_ms] = candle
            if str(symbol) not in errors:
                output[str(symbol)] = rows
        return output, errors


def seed_target_and_future(
    db: EvidenceDatabase,
    *,
    omit_future_index: int | None = None,
    funding_events: tuple[FundingEvent, ...] = (),
    cover_funding: bool = True,
) -> None:
    store_live(db, 0)
    for index in range(1, TARGET_INDEX):
        store_recovered(db, index, source_index=0)
    store_live(db, TARGET_INDEX)
    for index in range(TARGET_INDEX + 1, TARGET_INDEX + 49):
        if index == omit_future_index:
            continue
        store_recovered(
            db,
            index,
            source_index=TARGET_INDEX,
            extreme_first_future=True,
        )

    CanonicalFeatureStore(db).build(max_events=0)

    if cover_funding:
        db.store_funding_sync(
            start_ms=INTERVAL,
            end_ms=(TARGET_INDEX + 49) * INTERVAL - 1,
            events=funding_events,
            captured_at_ms=(TARGET_INDEX + 50) * INTERVAL,
        )


def outcome_row(db: EvidenceDatabase, event_open_ms: int = TARGET_OPEN):
    with db.connection() as conn:
        return conn.execute(
            """
            SELECT * FROM future_paths
            WHERE event_open_ms=? AND symbol=? AND outcome_version=?
            """,
            (event_open_ms, SYMBOL, OUTCOME_VERSION),
        ).fetchone()


class V343DefinitionAndIsolationTests(unittest.TestCase):
    def test_definition_is_frozen_and_initialization_does_not_change_raw_evidence(self):
        with isolated_live_db() as db:
            target = store_live(db, 0)
            CanonicalFeatureStore(db).build(max_events=1)
            before = db.audit(now_ms=target + 2 * INTERVAL, record=False)["evidence_digest"]
            store = FuturePathStore(db, FakePublicClient())
            self.assertEqual(store.definition_hash, EXPECTED_DEFINITION_HASH)
            store.initialize()
            after = db.audit(now_ms=target + 2 * INTERVAL, record=False)["evidence_digest"]
            self.assertEqual(before, after)
            with db.connection() as conn:
                tables = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertTrue(set(FUTURE_PATH_TABLES).issubset(tables))
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0], 0)

            with self.assertRaisesRegex(ValueError, "COST_ASSUMPTIONS_IMMUTABLE"):
                replace(FuturePathConfig(), taker_fee_rate=0.0004).validate()

    def test_future_label_storage_is_structurally_isolated_from_features_and_signals(self):
        repo = Path(__file__).resolve().parents[1]
        for relative in (
            "nbot/observation/features.py",
            "nbot/observation/signals.py",
        ):
            text = (repo / relative).read_text()
            self.assertNotIn("from .outcomes", text)
            self.assertNotIn("future_candle_cache", text)
            self.assertNotIn("future_paths", text)


class V343PathCalculationTests(unittest.TestCase):
    def test_mature_4h_path_matches_v2_semantics_including_costs_funding_and_barriers(self):
        funding_time = (TARGET_INDEX + 2) * INTERVAL
        funding_rate = 0.001
        funding = FundingEvent(SYMBOL, funding_time, funding_rate, 116.0)
        with isolated_live_db() as db:
            seed_target_and_future(db, funding_events=(funding,))
            store = FuturePathStore(db, FakePublicClient())
            raw_before = db.audit(now_ms=65 * INTERVAL, record=False)["evidence_digest"]

            result = store.build(max_events=0)

            raw_after = db.audit(now_ms=65 * INTERVAL, record=False)["evidence_digest"]
            self.assertEqual(raw_before, raw_after)
            self.assertEqual(result.feature_events, 2)
            self.assertEqual(result.mature_events, 2)
            self.assertEqual(result.built_events, 2)
            self.assertEqual(result.path_rows, 2)

            with db.connection() as conn:
                row = conn.execute(
                    """
                    SELECT entry_price, fwd_ret_5m, fwd_ret_15m, fwd_ret_4h,
                           long_mfe_frac, long_mae_frac,
                           time_to_long_mfe_min, time_to_long_mae_min,
                           future_realized_vol_4h, risk_unit_version, risk_unit_frac,
                           barrier_hits_json, continuation_json,
                           funding_event_count, funding_rate_sum, funding_events_json,
                           cost_version, roundtrip_base_cost_frac,
                           net_long_5m, net_long_15m, net_short_15m,
                           source_min_event_open_ms, source_max_event_open_ms,
                           future_candle_count, fallback_candle_count
                    FROM future_paths
                    WHERE event_open_ms=? AND symbol=? AND outcome_version=?
                    """,
                    (TARGET_OPEN, SYMBOL, OUTCOME_VERSION),
                ).fetchone()

            entry = 114.0
            self.assertEqual(row[0], entry)
            self.assertAlmostEqual(row[1], 115.0 / entry - 1.0, places=12)
            self.assertAlmostEqual(row[2], 117.0 / entry - 1.0, places=12)
            self.assertAlmostEqual(row[3], 162.0 / entry - 1.0, places=12)
            self.assertAlmostEqual(row[4], 163.0 / entry - 1.0, places=12)
            self.assertAlmostEqual(row[5], 1.0 - 111.5 / entry, places=12)
            self.assertEqual(row[6], 48 * 5)
            self.assertEqual(row[7], 5)

            closes = [100.0 + index for index in range(15, 63)]
            values = [entry, *closes]
            log_returns = [
                math.log(values[index] / values[index - 1])
                for index in range(1, len(values))
            ]
            self.assertAlmostEqual(
                row[8],
                math.sqrt(sum(value * value for value in log_returns)),
                places=12,
            )
            self.assertEqual(row[9], RISK_UNIT_VERSION)
            self.assertAlmostEqual(row[10], 2.0 / entry, places=12)
            barrier = json.loads(row[11])
            self.assertTrue(barrier["available"])
            self.assertEqual(
                barrier["sides"]["LONG"]["1R"]["first"],
                "AMBIGUOUS_SAME_CANDLE",
            )
            continuation = json.loads(row[12])
            self.assertIn("1h", continuation)
            self.assertGreater(
                continuation["1h"]["long_max_favorable_continuation_frac"],
                0,
            )
            self.assertEqual(row[13], 1)
            self.assertAlmostEqual(row[14], funding_rate, places=12)
            self.assertEqual(json.loads(row[15])[0]["funding_time_ms"], funding_time)
            self.assertEqual(row[16], COST_VERSION)

            spread_fraction = spread_pct(entry * 0.9999, entry * 1.0001) / 100.0
            base_cost = 2 * 0.0005 + 4 / 10_000 + spread_fraction
            self.assertAlmostEqual(row[17], base_cost, places=12)
            self.assertAlmostEqual(row[18], row[1] - base_cost, places=12)
            self.assertAlmostEqual(row[19], row[2] - base_cost - funding_rate, places=12)
            self.assertAlmostEqual(row[20], -row[2] - base_cost + funding_rate, places=12)
            self.assertEqual(row[21], TARGET_OPEN + INTERVAL)
            self.assertEqual(row[22], TARGET_OPEN + 48 * INTERVAL)
            self.assertEqual(row[23], 48)
            self.assertEqual(row[24], 0)

            audit = store.audit()
            self.assertTrue(audit["healthy"], audit)
            self.assertEqual(audit["source_digest_mismatches"], 0)
            self.assertEqual(audit["funding_source_digest_mismatches"], 0)

    def test_same_candle_barrier_order_is_never_invented(self):
        candle = Candle(
            symbol=SYMBOL,
            open_time_ms=INTERVAL,
            close_time_ms=2 * INTERVAL - 1,
            open_price=100.0,
            high_price=102.0,
            low_price=98.0,
            close_price=100.0,
            base_volume=1.0,
            quote_volume=1.0,
            trade_count=1,
            taker_buy_base_volume=1.0,
            taker_buy_quote_volume=1.0,
        )
        result = _barrier_hits(
            entry_price=100.0,
            risk_unit_frac=0.01,
            path=[candle],
            barriers=(1.0,),
            interval_minutes=5,
        )
        self.assertEqual(
            result["sides"]["LONG"]["1R"]["first"],
            "AMBIGUOUS_SAME_CANDLE",
        )
        self.assertEqual(
            result["sides"]["SHORT"]["1R"]["first"],
            "AMBIGUOUS_SAME_CANDLE",
        )

    def test_unmatured_feature_event_is_not_labeled_or_fetched_early(self):
        with isolated_live_db() as db:
            seed_target_and_future(db)
            # Latest closed open is 61*INTERVAL, so target 14 still lacks its
            # 48th future completed candle at open 62*INTERVAL.
            client = FakePublicClient(server_time_ms=62 * INTERVAL + 1_000, fail=True)
            store = FuturePathStore(db, client)
            result = store.build(max_events=0)
            self.assertEqual(result.feature_events, 2)
            self.assertEqual(result.mature_events, 1)
            self.assertEqual(result.pending_maturity_events, 1)
            self.assertEqual(result.built_events, 1)
            with db.connection() as conn:
                target_rows = conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE event_open_ms=?",
                    (TARGET_OPEN,),
                ).fetchone()[0]
            self.assertEqual(target_rows, 0)

    def test_funding_coverage_is_required_before_any_cost_complete_event_is_written(self):
        with isolated_live_db() as db:
            seed_target_and_future(db, cover_funding=False)
            store = FuturePathStore(db, FakePublicClient())
            result = store.build(max_events=0)
            self.assertEqual(result.built_events, 0)
            self.assertEqual(result.funding_incomplete_events, 2)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_path_builds").fetchone()[0], 0)
                results = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT result FROM future_path_attempts"
                    )
                }
            self.assertEqual(results, {"FUNDING_INCOMPLETE"})


class V343CacheBuildAuditTests(unittest.TestCase):
    def test_missing_future_candle_uses_label_only_cache_without_changing_feature_layer(self):
        missing_index = TARGET_INDEX + 10
        fallback_candle = candle_for_index(missing_index)
        with isolated_live_db() as db:
            seed_target_and_future(db, omit_future_index=missing_index)
            feature_audit_before = CanonicalFeatureStore(db).audit()
            with db.connection() as conn:
                feature_rows_before = conn.execute(
                    "SELECT COUNT(*) FROM canonical_features"
                ).fetchone()[0]
                feature_builds_before = conn.execute(
                    "SELECT COUNT(*) FROM feature_builds"
                ).fetchone()[0]
                feature_digest_before = conn.execute(
                    """
                    SELECT feature_digest FROM feature_builds
                    WHERE event_open_ms=?
                    """,
                    (TARGET_OPEN,),
                ).fetchone()[0]

            client = FakePublicClient(
                fallback={missing_index * INTERVAL: fallback_candle}
            )
            store = FuturePathStore(db, client)
            result = store.build(max_events=0)
            self.assertEqual(result.built_events, 2)
            self.assertEqual(result.fallback_candles_fetched, 1)

            with db.connection() as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM future_candle_cache"
                    ).fetchone()[0],
                    1,
                )
                target_fallback = conn.execute(
                    """
                    SELECT fallback_candle_count FROM future_paths
                    WHERE event_open_ms=? AND symbol=?
                    """,
                    (TARGET_OPEN, SYMBOL),
                ).fetchone()[0]
                self.assertEqual(target_fallback, 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM canonical_features").fetchone()[0], feature_rows_before)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM feature_builds").fetchone()[0], feature_builds_before)
                feature_digest_after = conn.execute(
                    """
                    SELECT feature_digest FROM feature_builds
                    WHERE event_open_ms=?
                    """,
                    (TARGET_OPEN,),
                ).fetchone()[0]
            self.assertEqual(feature_digest_before, feature_digest_after)
            self.assertEqual(feature_audit_before, CanonicalFeatureStore(db).audit())

    def test_failed_historical_fetch_commits_no_partial_future_path_event(self):
        missing_index = TARGET_INDEX + 10
        with isolated_live_db() as db:
            seed_target_and_future(db, omit_future_index=missing_index)
            store = FuturePathStore(db, FakePublicClient(fail=True))
            result = store.build(max_events=0)
            self.assertEqual(result.built_events, 0)
            self.assertEqual(result.path_incomplete_events, 2)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_path_builds").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_candle_cache").fetchone()[0], 0)

    def test_rebuild_is_digest_stable_and_audit_is_read_only(self):
        with isolated_live_db() as db:
            seed_target_and_future(db)
            store = FuturePathStore(db, FakePublicClient())
            first = store.build(max_events=0)
            self.assertEqual(first.built_events, 2)
            with db.connection() as conn:
                before = conn.execute(
                    """
                    SELECT event_open_ms, path_digest, source_digest
                    FROM future_path_builds
                    ORDER BY event_open_ms
                    """
                ).fetchall()
                rows_before = conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0]
                attempts_before = conn.execute("SELECT COUNT(*) FROM future_path_attempts").fetchone()[0]

            with mock.patch("nbot.observation.outcomes.time.time", return_value=999999.0):
                rebuilt = store.build(max_events=0, rebuild=True)
            self.assertEqual(rebuilt.built_events, 2)
            with db.connection() as conn:
                after = conn.execute(
                    """
                    SELECT event_open_ms, path_digest, source_digest
                    FROM future_path_builds
                    ORDER BY event_open_ms
                    """
                ).fetchall()
            self.assertEqual(before, after)

            audit1 = store.audit()
            audit2 = store.audit()
            self.assertEqual(audit1, audit2)
            self.assertTrue(audit1["healthy"], audit1)
            with db.connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0], rows_before)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM future_path_attempts").fetchone()[0],
                    attempts_before + 2,
                )

    def test_audit_detects_feature_candle_funding_and_output_tampering(self):
        funding = FundingEvent(
            SYMBOL,
            (TARGET_INDEX + 2) * INTERVAL,
            0.001,
            116.0,
        )
        with isolated_live_db() as db:
            seed_target_and_future(db, funding_events=(funding,))
            store = FuturePathStore(db, FakePublicClient())
            store.build(max_events=0)
            self.assertTrue(store.audit()["healthy"])

            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE canonical_features SET close_price=close_price+0.5
                    WHERE event_open_ms=? AND symbol=?
                    """,
                    (TARGET_OPEN, SYMBOL),
                )
            feature_report = store.audit()
            self.assertFalse(feature_report["healthy"])
            self.assertGreater(feature_report["source_digest_mismatches"], 0)

        with isolated_live_db() as db:
            seed_target_and_future(db, funding_events=(funding,))
            store = FuturePathStore(db, FakePublicClient())
            store.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE candles_5m SET high_price=high_price+0.25
                    WHERE event_open_ms=? AND symbol=?
                    """,
                    ((TARGET_INDEX + 3) * INTERVAL, SYMBOL),
                )
            candle_report = store.audit()
            self.assertFalse(candle_report["healthy"])
            self.assertGreater(candle_report["source_candle_digest_mismatches"], 0)
            self.assertGreater(candle_report["source_digest_mismatches"], 0)

        with isolated_live_db() as db:
            seed_target_and_future(db, funding_events=(funding,))
            store = FuturePathStore(db, FakePublicClient())
            store.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE funding_events SET funding_rate=0.002
                    WHERE symbol=? AND funding_time_ms=?
                    """,
                    (SYMBOL, funding.funding_time_ms),
                )
            funding_report = store.audit()
            self.assertFalse(funding_report["healthy"])
            self.assertGreater(funding_report["funding_source_digest_mismatches"], 0)
            self.assertGreater(funding_report["source_digest_mismatches"], 0)

        with isolated_live_db() as db:
            seed_target_and_future(db)
            store = FuturePathStore(db, FakePublicClient())
            store.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE future_paths SET net_long_4h=net_long_4h+0.01
                    WHERE event_open_ms=? AND symbol=?
                    """,
                    (TARGET_OPEN, SYMBOL),
                )
            output_report = store.audit()
            self.assertFalse(output_report["healthy"])
            self.assertGreater(output_report["path_digest_mismatches"], 0)

    def test_definition_tamper_is_reported_and_not_repaired_by_audit(self):
        with isolated_live_db() as db:
            store_live(db, 0)
            CanonicalFeatureStore(db).build(max_events=1)
            store = FuturePathStore(db, FakePublicClient())
            store.initialize()
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE future_path_sets SET definition_hash='tampered'
                    WHERE outcome_version=?
                    """,
                    (OUTCOME_VERSION,),
                )

            report = store.audit()
            self.assertFalse(report["healthy"])
            self.assertEqual(report["definition_mismatch"], 1)
            with db.connection() as conn:
                stored = conn.execute(
                    """
                    SELECT definition_hash FROM future_path_sets
                    WHERE outcome_version=?
                    """,
                    (OUTCOME_VERSION,),
                ).fetchone()[0]
            self.assertEqual(stored, "tampered")
            with self.assertRaises(FuturePathError):
                store.initialize()


if __name__ == "__main__":
    unittest.main()
