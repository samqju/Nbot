import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, FundingEvent, SourceCapture, UniverseRow
from nbot.config import CONFIG, OUTCOME_CONFIG, RESEARCH_CONFIG
from nbot.db import EvidenceDB
from nbot.outcomes import FuturePathEngine, _barrier_hits
from nbot.research import ResearchEngine


class FakeHistoricalClient:
    def __init__(self, cfg, price_fn, latest_closed_index: int, fail_symbols=None):
        self.cfg = cfg
        self.price_fn = price_fn
        self.latest_closed_index = latest_closed_index
        self.fail_symbols = set(fail_symbols or ())

    def server_time_ms(self):
        # latest_closed_open_time_ms() will return latest_closed_index * interval.
        return (self.latest_closed_index + 1) * self.cfg.candle_interval_ms + 1_000

    def historical_candles(self, symbol, start_open_ms, end_open_ms):
        if symbol in self.fail_symbols:
            raise RuntimeError("simulated historical failure")
        rows = {}
        interval = self.cfg.candle_interval_ms
        for open_ms in range(start_open_ms, end_open_ms + 1, interval):
            index = open_ms // interval
            close = self.price_fn(symbol, index)
            rows[open_ms] = Candle(
                symbol,
                open_ms,
                open_ms + interval - 1,
                close * 0.999,
                close * 1.003,
                close * 0.997,
                close,
                1000.0,
                1_000_000.0,
                100,
                500.0,
                500_000.0,
            )
        return rows


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = replace(
            CONFIG,
            database_path=Path(self.tmp.name) / "observer.db",
            observation_universe_size=3,
        )
        self.db = EvidenceDB(self.cfg)
        self.db.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _price(symbol: str, index: int) -> float:
        if symbol == "BTCUSDT":
            return 100.0 + index * 0.20
        if symbol == "AAAUSDT":
            return 50.0 + index * 0.30
        return 80.0 - index * 0.08

    def _store_event(self, index: int):
        interval = self.cfg.candle_interval_ms
        open_ms = index * interval
        close_ms = open_ms + interval - 1
        symbols = ("BTCUSDT", "AAAUSDT", "BBBUSDT")
        rows = []
        candles = {}
        for rank, symbol in enumerate(symbols, 1):
            close = self._price(symbol, index)
            rows.append(
                UniverseRow(
                    symbol,
                    rank,
                    1_000_000_000.0 / rank,
                    close * 0.9999,
                    close * 1.0001,
                    0.02 * rank,
                    close,
                    close,
                    0.0001 * rank,
                    close_ms + 8 * 60 * 60 * 1000,
                )
            )
            candles[symbol] = Candle(
                symbol,
                open_ms,
                close_ms,
                close * 0.999,
                close * 1.003,
                close * 0.997,
                close,
                1000.0,
                1_000_000.0,
                100,
                500.0,
                500_000.0,
            )
        status = self.db.store_event(
            event_open_ms=open_ms,
            event_close_ms=close_ms,
            captured_at_ms=close_ms + 5_000,
            capture_started_at_ms=close_ms + 1_000,
            server_time_before_ms=close_ms + 1_000,
            server_time_after_ms=close_ms + 5_000,
            source_captures=(SourceCapture("point_in_time_context", close_ms + 1_000, close_ms + 2_000),),
            requested_symbols=3,
            universe_rows=rows,
            candles=candles,
            error_count=0,
            capture_duration_ms=4_000,
        )
        self.assertEqual(status, "COMPLETE")
        return open_ms

    def _seed(self, count=70):
        for index in range(count):
            self._store_event(index)
        ResearchEngine(self.cfg, RESEARCH_CONFIG, self.db).build(max_events=0)

    def _funding_cover(self, end_index=100, events=()):
        self.db.store_funding_sync(
            start_ms=0,
            end_ms=end_index * self.cfg.candle_interval_ms,
            events=list(events),
            captured_at_ms=end_index * self.cfg.candle_interval_ms + 1,
        )

    def _engine(self, latest_closed_index=69, *, fail_symbols=None, outcome_cfg=OUTCOME_CONFIG):
        return FuturePathEngine(
            self.cfg,
            outcome_cfg,
            self.db,
            FakeHistoricalClient(self.cfg, self._price, latest_closed_index, fail_symbols=fail_symbols),
        )

    def test_builds_only_mature_feature_events_and_records_objective_path(self):
        self._seed(70)
        self._funding_cover()
        result = self._engine().build(max_events=0)
        self.assertEqual(result.feature_events, 70)
        self.assertEqual(result.mature_events, 22)
        self.assertEqual(result.pending_maturity_events, 48)
        self.assertEqual(result.built_events, 22)
        self.assertEqual(result.path_rows, 66)
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT fwd_ret_5m, fwd_ret_4h, long_mfe_frac, long_mae_frac, "
                "source_min_event_open_ms, source_max_event_open_ms, future_candle_count "
                "FROM future_paths WHERE event_open_ms=0 AND symbol='AAAUSDT'"
            ).fetchone()
        self.assertAlmostEqual(row[0], self._price("AAAUSDT", 1) / self._price("AAAUSDT", 0) - 1.0)
        self.assertAlmostEqual(row[1], self._price("AAAUSDT", 48) / self._price("AAAUSDT", 0) - 1.0)
        self.assertGreater(row[2], 0)
        self.assertGreaterEqual(row[3], 0)
        self.assertEqual(row[4], self.cfg.candle_interval_ms)
        self.assertEqual(row[5], 48 * self.cfg.candle_interval_ms)
        self.assertEqual(row[6], 48)

    def test_immature_events_are_not_labeled(self):
        self._seed(55)
        self._funding_cover()
        result = self._engine(latest_closed_index=50).build(max_events=0)
        self.assertEqual(result.mature_events, 3)
        self.assertEqual(result.built_events, 3)
        with self.db.connection() as conn:
            latest = conn.execute("SELECT MAX(event_open_ms) FROM future_paths").fetchone()[0]
        self.assertEqual(latest, 2 * self.cfg.candle_interval_ms)

    def test_missing_future_candles_are_fetched_into_label_only_cache(self):
        self._seed(70)
        self._funding_cover()
        interval = self.cfg.candle_interval_ms
        with self.db.connection() as conn:
            conn.execute(
                "DELETE FROM candles_5m WHERE symbol='AAAUSDT' AND event_open_ms BETWEEN ? AND ?",
                (interval, 48 * interval),
            )
        result = self._engine().build(max_events=1)
        self.assertEqual(result.built_events, 1)
        self.assertEqual(result.fallback_candles_fetched, 48)
        with self.db.connection() as conn:
            cache = conn.execute(
                "SELECT COUNT(*) FROM future_candle_cache WHERE symbol='AAAUSDT'"
            ).fetchone()[0]
            used = conn.execute(
                "SELECT fallback_candle_count FROM future_paths WHERE event_open_ms=0 AND symbol='AAAUSDT'"
            ).fetchone()[0]
        self.assertEqual(cache, 48)
        self.assertEqual(used, 48)

    def test_future_label_cache_cannot_change_v22_feature_digest(self):
        self._seed(55)
        research = ResearchEngine(self.cfg, RESEARCH_CONFIG, self.db)
        with self.db.connection() as conn:
            before = conn.execute(
                "SELECT feature_digest FROM feature_builds WHERE event_open_ms=?",
                (20 * self.cfg.candle_interval_ms,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO future_candle_cache VALUES (
                    'AAAUSDT', ?, ?, ?, 9999, 9999, 9999, 9999,
                    1, 1, 1, 1, 1, 'BINANCE_HISTORICAL_KLINE', 1
                )
                """,
                (
                    10 * self.cfg.candle_interval_ms,
                    10 * self.cfg.candle_interval_ms,
                    11 * self.cfg.candle_interval_ms - 1,
                ),
            )
        research.build(max_events=0, rebuild=True)
        with self.db.connection() as conn:
            after = conn.execute(
                "SELECT feature_digest FROM feature_builds WHERE event_open_ms=?",
                (20 * self.cfg.candle_interval_ms,),
            ).fetchone()[0]
        self.assertEqual(before, after)

    def test_funding_coverage_is_required_before_cost_complete_label(self):
        self._seed(55)
        result = self._engine(latest_closed_index=54).build(max_events=1)
        self.assertEqual(result.built_events, 0)
        self.assertEqual(result.funding_incomplete_events, 1)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0], 0)

    def test_exact_funding_event_is_included_in_directional_net_returns(self):
        self._seed(70)
        interval = self.cfg.candle_interval_ms
        funding_time = 2 * interval
        rate = 0.001
        self._funding_cover(events=(FundingEvent("AAAUSDT", funding_time, rate, 51.0),))
        self._engine().build(max_events=1)
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT fwd_ret_15m, funding_event_count, funding_rate_sum, "
                "roundtrip_base_cost_frac, net_long_15m, net_short_15m, funding_events_json "
                "FROM future_paths WHERE event_open_ms=0 AND symbol='AAAUSDT'"
            ).fetchone()
        self.assertEqual(row[1], 1)
        self.assertAlmostEqual(row[2], rate)
        expected_long = row[0] - row[3] - rate
        expected_short = -row[0] - row[3] + rate
        self.assertAlmostEqual(row[4], expected_long)
        self.assertAlmostEqual(row[5], expected_short)
        self.assertEqual(json.loads(row[6])[0]["funding_time_ms"], funding_time)

    def test_barrier_same_candle_order_is_explicitly_ambiguous(self):
        interval = self.cfg.candle_interval_ms
        candle = Candle(
            "AAAUSDT", interval, 2 * interval - 1,
            100.0, 102.0, 98.0, 100.0,
            1, 1, 1, 1, 1,
        )
        result = _barrier_hits(
            entry_price=100.0,
            risk_unit_frac=0.01,
            path=[candle],
            barriers=(1.0,),
            interval_minutes=5,
        )
        self.assertEqual(result["sides"]["LONG"]["1R"]["first"], "AMBIGUOUS_SAME_CANDLE")
        self.assertEqual(result["sides"]["SHORT"]["1R"]["first"], "AMBIGUOUS_SAME_CANDLE")

    def test_risk_barriers_remain_unavailable_when_decision_atr_is_missing(self):
        self._seed(70)
        self._funding_cover()
        self._engine().build(max_events=1)
        with self.db.connection() as conn:
            raw = conn.execute(
                "SELECT risk_unit_frac, barrier_hits_json FROM future_paths "
                "WHERE event_open_ms=0 AND symbol='AAAUSDT'"
            ).fetchone()
        self.assertIsNone(raw[0])
        barrier = json.loads(raw[1])
        self.assertFalse(barrier["available"])
        self.assertEqual(barrier["reason"], "ATR14_RISK_UNIT_UNAVAILABLE")

    def test_rebuild_is_deterministic(self):
        self._seed(70)
        self._funding_cover()
        engine = self._engine()
        engine.build(max_events=5)
        with self.db.connection() as conn:
            first = conn.execute(
                "SELECT event_open_ms, path_digest FROM future_path_builds ORDER BY event_open_ms"
            ).fetchall()
        engine.build(max_events=5, rebuild=True)
        with self.db.connection() as conn:
            second = conn.execute(
                "SELECT event_open_ms, path_digest FROM future_path_builds ORDER BY event_open_ms"
            ).fetchall()
        self.assertEqual(first, second)

    def test_same_outcome_version_with_changed_definition_is_rejected(self):
        self._seed(1)
        engine = self._engine(latest_closed_index=0)
        engine.initialize()
        changed = replace(OUTCOME_CONFIG, cost_version="DIFFERENT_COST_V1")
        with self.assertRaises(RuntimeError):
            self._engine(latest_closed_index=0, outcome_cfg=changed).initialize()

    def test_event_build_is_atomic_when_historical_fetch_fails(self):
        self._seed(70)
        self._funding_cover()
        interval = self.cfg.candle_interval_ms
        with self.db.connection() as conn:
            conn.execute(
                "DELETE FROM candles_5m WHERE symbol='AAAUSDT' AND event_open_ms BETWEEN ? AND ?",
                (interval, 48 * interval),
            )
        result = self._engine(fail_symbols={"AAAUSDT"}).build(max_events=1)
        self.assertEqual(result.built_events, 0)
        self.assertEqual(result.path_incomplete_events, 1)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_paths").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM future_path_builds").fetchone()[0], 0)

    def test_audit_detects_changed_future_candle_source(self):
        self._seed(70)
        self._funding_cover()
        engine = self._engine()
        engine.build(max_events=1)
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE candles_5m SET high_price=high_price*1.01 "
                "WHERE symbol='AAAUSDT' AND event_open_ms=?",
                (self.cfg.candle_interval_ms,),
            )
        report = engine.audit()
        self.assertGreater(report["source_candle_digest_mismatches"], 0)

    def test_audit_detects_changed_funding_source(self):
        self._seed(70)
        interval = self.cfg.candle_interval_ms
        funding_time = 2 * interval
        self._funding_cover(events=(FundingEvent("AAAUSDT", funding_time, 0.001, 51.0),))
        engine = self._engine()
        engine.build(max_events=1)
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE funding_events SET funding_rate=0.002 "
                "WHERE symbol='AAAUSDT' AND funding_time_ms=?",
                (funding_time,),
            )
        report = engine.audit()
        self.assertGreater(report["funding_source_digest_mismatches"], 0)

    def test_outcome_audit_is_clean_after_complete_build(self):
        self._seed(70)
        self._funding_cover()
        engine = self._engine()
        engine.build(max_events=5)
        report = engine.audit()
        for key in (
            "definition_mismatch",
            "paths_without_feature",
            "invalid_source_bounds",
            "invalid_path_values",
            "cost_version_mismatches",
            "risk_version_mismatches",
            "build_row_mismatches",
            "future_cache_conflicts",
            "unresolved_attempt_events",
            "json_errors",
            "path_digest_mismatches",
            "build_digest_mismatches",
            "source_candle_digest_mismatches",
            "funding_source_digest_mismatches",
        ):
            self.assertEqual(report[key], 0, key)


if __name__ == "__main__":
    unittest.main()
