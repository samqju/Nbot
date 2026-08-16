import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, SourceCapture, UniverseRow
from nbot.config import CONFIG, RESEARCH_CONFIG
from nbot.db import EvidenceDB
from nbot.research import ResearchEngine, SIGNAL_VERSIONS


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = replace(
            CONFIG,
            database_path=Path(self.tmp.name) / "observer.db",
            observation_universe_size=3,
        )
        self.db = EvidenceDB(self.cfg)
        self.db.initialize()
        self.engine = ResearchEngine(self.cfg, RESEARCH_CONFIG, self.db)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _price(symbol: str, index: int) -> float:
        if symbol == "BTCUSDT":
            return 100.0 + index * 0.20
        if symbol == "AAAUSDT":
            return 50.0 + index * 0.30
        return 80.0 - index * 0.08

    def _store_event(self, index: int, *, context_complete: bool = True, future_override: dict[str, float] | None = None):
        open_ms = index * self.cfg.candle_interval_ms
        close_ms = open_ms + self.cfg.candle_interval_ms - 1
        symbols = ("BTCUSDT", "AAAUSDT", "BBBUSDT")
        rows = []
        candles = {}
        for rank, symbol in enumerate(symbols, 1):
            close = self._price(symbol, index)
            if future_override and symbol in future_override:
                close = future_override[symbol]
            open_price = close * 0.999
            high = close * 1.003
            low = close * 0.997
            rows.append(
                UniverseRow(
                    symbol,
                    rank,
                    1_000_000_000.0 / rank + index * 10_000.0,
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
                open_price,
                high,
                low,
                close,
                1000.0,
                1_000_000.0,
                100,
                500.0,
                500_000.0,
            )
        captured = close_ms + 5_000
        status = self.db.store_event(
            event_open_ms=open_ms,
            event_close_ms=close_ms,
            captured_at_ms=captured,
            capture_started_at_ms=close_ms + 1_000,
            server_time_before_ms=close_ms + 1_000,
            server_time_after_ms=captured,
            source_captures=(SourceCapture("point_in_time_context", close_ms + 1_000, close_ms + 2_000),),
            requested_symbols=3,
            universe_rows=rows,
            candles=candles,
            error_count=0,
            capture_duration_ms=4_000,
        )
        self.assertEqual(status, "COMPLETE")
        if not context_complete:
            with self.db.connection() as conn:
                conn.execute("UPDATE event_provenance SET context_complete=0 WHERE event_open_ms=?", (open_ms,))
        return open_ms

    def _seed_50_events(self):
        for index in range(50):
            override = {"AAAUSDT": 9999.0} if index == 49 else None
            self._store_event(index, future_override=override)

    def test_every_research_ready_snapshot_gets_feature_and_all_signal_annotations(self):
        self._seed_50_events()
        before = self.db.status()["snapshots"]
        result = self.engine.build(max_events=0)
        after = self.db.status()["snapshots"]
        self.assertEqual(before, 150)
        self.assertEqual(after, before)
        self.assertEqual(result.feature_rows, 150)
        self.assertEqual(result.signal_annotations, 150 * len(SIGNAL_VERSIONS))
        status = self.engine.status()
        self.assertEqual(status["feature_rows"], 150)
        self.assertGreater(status["feature_rows_with_no_active_signal"], 0)

    def test_feature_history_never_reads_future_candle(self):
        self._seed_50_events()
        self.engine.build(max_events=0)
        target = 48 * self.cfg.candle_interval_ms
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT ret_4h, source_max_event_open_ms FROM canonical_features "
                "WHERE event_open_ms=? AND symbol='AAAUSDT' AND feature_version=?",
                (target, RESEARCH_CONFIG.feature_version),
            ).fetchone()
        expected = self._price("AAAUSDT", 48) / self._price("AAAUSDT", 0) - 1.0
        self.assertAlmostEqual(row[0], expected, places=12)
        self.assertEqual(row[1], target)
        # Event 49 contains an intentionally absurd future AAA price. It must not affect event 48.
        self.assertLess(row[0], 1.0)

    def test_incomplete_history_row_is_retained_and_signals_are_none(self):
        self._store_event(0)
        self.engine.build(max_events=0)
        with self.db.connection() as conn:
            feature = conn.execute(
                "SELECT history_bars, full_history_4h, ret_4h FROM canonical_features WHERE symbol='BTCUSDT'"
            ).fetchone()
            signals = conn.execute(
                "SELECT COUNT(*), SUM(active) FROM signal_annotations WHERE symbol='BTCUSDT'"
            ).fetchone()
        self.assertEqual(feature, (1, 0, None))
        self.assertEqual(signals[0], len(SIGNAL_VERSIONS))
        self.assertEqual(signals[1], 0)

    def test_context_incomplete_event_is_not_feature_target(self):
        self._store_event(0)
        self._store_event(1, context_complete=False)
        result = self.engine.build(max_events=0)
        self.assertEqual(result.research_ready_events, 1)
        self.assertEqual(result.feature_rows, 3)
        with self.db.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM canonical_features").fetchone()[0]
        self.assertEqual(count, 3)

    def test_rebuild_is_deterministic(self):
        self._seed_50_events()
        self.engine.build(max_events=0)
        with self.db.connection() as conn:
            first = conn.execute(
                "SELECT event_open_ms, feature_digest, signal_digest FROM feature_builds ORDER BY event_open_ms"
            ).fetchall()
        self.engine.build(max_events=0, rebuild=True)
        with self.db.connection() as conn:
            second = conn.execute(
                "SELECT event_open_ms, feature_digest, signal_digest FROM feature_builds ORDER BY event_open_ms"
            ).fetchall()
        self.assertEqual(first, second)

    def test_same_version_with_changed_definition_is_rejected(self):
        self.engine.initialize()
        changed = replace(RESEARCH_CONFIG, csm_active_abs_score=0.70)
        with self.assertRaises(RuntimeError):
            ResearchEngine(self.cfg, changed, self.db).initialize()

    def test_research_audit_is_clean_after_complete_build(self):
        self._seed_50_events()
        self.engine.build(max_events=0)
        report = self.engine.audit()
        self.assertEqual(report["unbuilt_events"], 0)
        for key in (
            "feature_definition_mismatch",
            "signal_definition_mismatches",
            "context_incomplete_feature_rows",
            "feature_rows_without_snapshot",
            "future_source_rows",
            "invalid_percentiles",
            "feature_row_count_mismatches",
            "signal_rows_without_feature",
            "annotation_count_mismatches",
            "invalid_active_signals",
            "digest_mismatches",
        ):
            self.assertEqual(report[key], 0, key)


if __name__ == "__main__":
    unittest.main()
