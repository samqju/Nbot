import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, SourceCapture, UniverseRow
from nbot.config import CONFIG, OUTCOME_CONFIG, POLICY_CONFIG, RESEARCH_CONFIG
from nbot.db import EvidenceDB
from nbot.outcomes import FuturePathEngine
from nbot.policies import ExitPolicyLab
from nbot.research import ResearchEngine
from nbot.selection import BASELINE_SELECTORS, SELECTORS, EntrySelectionLab, SELECTION_CONFIG


class FakeHistoricalClient:
    def __init__(self, cfg, price_fn, latest_closed_index=69):
        self.cfg = cfg
        self.price_fn = price_fn
        self.latest_closed_index = latest_closed_index

    def server_time_ms(self):
        return (self.latest_closed_index + 1) * self.cfg.candle_interval_ms + 1_000

    def historical_candles(self, symbol, start_open_ms, end_open_ms):
        rows = {}
        interval = self.cfg.candle_interval_ms
        for open_ms in range(start_open_ms, end_open_ms + 1, interval):
            index = open_ms // interval
            close = self.price_fn(symbol, index)
            rows[open_ms] = Candle(
                symbol, open_ms, open_ms + interval - 1,
                close * 0.999, close * 1.003, close * 0.997, close,
                1000.0, 1_000_000.0, 100, 500.0, 500_000.0,
            )
        return rows


class SelectionLabIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = replace(CONFIG, database_path=Path(self.tmp.name) / "observer.db", observation_universe_size=3)
        self.selection_cfg = replace(SELECTION_CONFIG, min_train_events=3)
        self.db = EvidenceDB(self.cfg)
        self.db.initialize()
        self._seed(70)
        ResearchEngine(self.cfg, RESEARCH_CONFIG, self.db).build(max_events=0)
        self.db.store_funding_sync(
            start_ms=0,
            end_ms=100 * self.cfg.candle_interval_ms,
            events=[],
            captured_at_ms=100 * self.cfg.candle_interval_ms + 1,
        )
        FuturePathEngine(
            self.cfg,
            OUTCOME_CONFIG,
            self.db,
            FakeHistoricalClient(self.cfg, self._price, latest_closed_index=69),
        ).build(max_events=0)
        self.policy_lab = ExitPolicyLab(self.cfg, POLICY_CONFIG, self.db)
        self.policy_lab.build(max_events=0)
        self.lab = EntrySelectionLab(self.cfg, self.selection_cfg, self.db)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _price(symbol: str, index: int) -> float:
        # Deliberately different symbol behavior gives selectors something to rank.
        if symbol == "BTCUSDT":
            return 100.0 + index * 0.20 + (index % 5) * 0.03
        if symbol == "AAAUSDT":
            return 50.0 + index * 0.30 + (index % 7) * 0.05
        return 80.0 - index * 0.08 + (index % 3) * 0.02

    def _seed(self, count):
        interval = self.cfg.candle_interval_ms
        for index in range(count):
            open_ms = index * interval
            close_ms = open_ms + interval - 1
            symbols = ("BTCUSDT", "AAAUSDT", "BBBUSDT")
            rows = []
            candles = {}
            for rank, symbol in enumerate(symbols, 1):
                close = self._price(symbol, index)
                rows.append(UniverseRow(
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
                ))
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

    def test_catalog_has_five_transparent_baselines_and_one_learned_selector(self):
        self.assertEqual(len(BASELINE_SELECTORS), 5)
        self.assertEqual(len(SELECTORS), 6)
        learned = [spec.selector_version for spec in SELECTORS if spec.is_learned]
        self.assertEqual(learned, ["RIDGE_EXPECTED_NET_R_V1"])

    def test_every_target_policy_symbol_side_becomes_an_example_without_signal_gating(self):
        result = self.lab.build(max_events=0)
        with self.db.connection() as conn:
            target_rows = conn.execute(
                "SELECT COUNT(*) FROM exit_policy_results WHERE lab_version=? AND policy_version=?",
                (POLICY_CONFIG.lab_version, self.selection_cfg.target_policy_version),
            ).fetchone()[0]
            examples = conn.execute(
                "SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=?",
                (self.selection_cfg.lab_version,),
            ).fetchone()[0]
        self.assertEqual(result.example_rows, target_rows)
        self.assertEqual(examples, target_rows)
        self.assertGreater(examples, 0)

    def test_baselines_score_every_example_and_learned_selector_is_forward_chained(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            example_events = conn.execute(
                "SELECT event_open_ms, COUNT(*) FROM entry_selection_examples WHERE lab_version=? GROUP BY event_open_ms ORDER BY event_open_ms",
                (self.selection_cfg.lab_version,),
            ).fetchall()
            self.assertGreaterEqual(len(example_events), 4)
            for event_open_ms, count in example_events:
                for spec in BASELINE_SELECTORS:
                    pred_count = conn.execute(
                        "SELECT COUNT(*) FROM entry_selection_predictions WHERE event_open_ms=? AND selector_version=?",
                        (event_open_ms, spec.selector_version),
                    ).fetchone()[0]
                    self.assertEqual(pred_count, count)
            learned = conn.execute(
                "SELECT DISTINCT event_open_ms, trained_through_event_ms, training_event_count "
                "FROM entry_selection_predictions WHERE selector_version=? ORDER BY event_open_ms",
                (self.selection_cfg.learned_selector_version,),
            ).fetchall()
        self.assertGreater(len(learned), 0)
        for event_open_ms, trained_through, training_events in learned:
            self.assertLess(trained_through, event_open_ms)
            self.assertGreaterEqual(training_events, self.selection_cfg.min_train_events)

    def test_prediction_ranks_are_complete_per_event(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT event_open_ms, selector_version, COUNT(*), MIN(rank_in_event), MAX(rank_in_event), COUNT(DISTINCT rank_in_event) "
                "FROM entry_selection_predictions GROUP BY event_open_ms, selector_version"
            ).fetchall()
        self.assertGreater(len(rows), 0)
        for _event, _selector, count, minimum, maximum, distinct_count in rows:
            self.assertEqual(minimum, 1)
            self.assertEqual(maximum, count)
            self.assertEqual(distinct_count, count)

    def test_report_is_economic_research_only_not_probability_calibration(self):
        self.lab.build(max_events=0)
        report = self.lab.report()
        self.assertEqual(report["authority"], "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION")
        self.assertIn("NOT_A_PROBABILITY_MODEL", report["calibration_note"])
        self.assertIn("RANDOM_HASH_BASELINE_V1", report["selectors"])
        self.assertIn("RIDGE_EXPECTED_NET_R_V1", report["selectors"])
        learned = report["selectors"]["RIDGE_EXPECTED_NET_R_V1"]
        self.assertGreater(learned["independent_market_events"], 0)
        self.assertIn("mean_event_selection_regret_r", learned)
        self.assertIn("top_minus_bottom_net_r", learned)

    def test_audit_is_clean_and_rebuild_is_deterministic(self):
        self.lab.build(max_events=0)
        first_audit = self.lab.audit()
        self.assertTrue(all(value == 0 for key, value in first_audit.items() if key not in {"lab_version", "target_policy_version", "example_rows", "prediction_rows"}))
        with self.db.connection() as conn:
            before_examples = conn.execute(
                "SELECT event_open_ms, example_digest FROM entry_selection_builds ORDER BY event_open_ms"
            ).fetchall()
            before_predictions = conn.execute(
                "SELECT event_open_ms, selector_version, prediction_digest FROM entry_selection_prediction_builds ORDER BY event_open_ms, selector_version"
            ).fetchall()
        self.lab.build(max_events=0, rebuild=True)
        with self.db.connection() as conn:
            after_examples = conn.execute(
                "SELECT event_open_ms, example_digest FROM entry_selection_builds ORDER BY event_open_ms"
            ).fetchall()
            after_predictions = conn.execute(
                "SELECT event_open_ms, selector_version, prediction_digest FROM entry_selection_prediction_builds ORDER BY event_open_ms, selector_version"
            ).fetchall()
        self.assertEqual(before_examples, after_examples)
        self.assertEqual(before_predictions, after_predictions)
        self.assertEqual(self.lab.audit()["prediction_digest_mismatches"], 0)

    def test_policy_result_mutation_is_detected(self):
        self.lab.build(max_events=1)
        with self.db.connection() as conn:
            target = conn.execute(
                "SELECT event_open_ms, symbol, side FROM entry_selection_examples LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE exit_policy_results SET result_digest='tampered' WHERE event_open_ms=? AND symbol=? AND side=? AND policy_version=?",
                (*target, self.selection_cfg.target_policy_version),
            )
        audit = self.lab.audit()
        self.assertGreater(audit["policy_result_digest_mismatches"], 0)
        self.assertGreater(audit["example_build_source_digest_mismatches"], 0)

    def test_future_feature_source_is_detected(self):
        self.lab.build(max_events=1)
        with self.db.connection() as conn:
            target = conn.execute(
                "SELECT event_open_ms, symbol FROM entry_selection_examples LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE canonical_features SET source_max_event_open_ms=event_open_ms+? WHERE event_open_ms=? AND symbol=?",
                (self.cfg.candle_interval_ms, *target),
            )
        self.assertGreater(self.lab.audit()["future_feature_source_rows"], 0)


if __name__ == "__main__":
    unittest.main()
