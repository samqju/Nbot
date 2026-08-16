import shutil
import tempfile
import unittest
from unittest import mock
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, SourceCapture, UniverseRow
from nbot.champion import AUTHORITY, CHAMPION_CONFIG, WalkForwardChampionEvaluator
from nbot.config import CONFIG, OUTCOME_CONFIG, POLICY_CONFIG, RESEARCH_CONFIG
from nbot.db import EvidenceDB
from nbot.outcomes import FuturePathEngine
from nbot.policies import ExitPolicyLab
from nbot.research import ResearchEngine
from nbot.selection import EntrySelectionLab, SELECTION_CONFIG


class FakeHistoricalClient:
    def __init__(self, cfg, price_fn, latest_closed_index):
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


class ChampionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_tmp = tempfile.TemporaryDirectory()
        cls.base_db_path = Path(cls.base_tmp.name) / "observer.db"
        cfg = replace(CONFIG, database_path=cls.base_db_path, observation_universe_size=3)
        db = EvidenceDB(cfg)
        db.initialize()
        cls._seed(db, cfg, 125)
        ResearchEngine(cfg, RESEARCH_CONFIG, db).build(max_events=0)
        db.store_funding_sync(
            start_ms=0,
            end_ms=200 * cfg.candle_interval_ms,
            events=[],
            captured_at_ms=200 * cfg.candle_interval_ms + 1,
        )
        FuturePathEngine(
            cfg,
            OUTCOME_CONFIG,
            db,
            FakeHistoricalClient(cfg, cls._price, latest_closed_index=124),
        ).build(max_events=0)
        ExitPolicyLab(cfg, POLICY_CONFIG, db).build(max_events=0)
        EntrySelectionLab(cfg, SELECTION_CONFIG, db).build(max_events=0)
        db.checkpoint()

    @classmethod
    def tearDownClass(cls):
        cls.base_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "observer.db"
        shutil.copy2(self.base_db_path, path)
        self.cfg = replace(CONFIG, database_path=path, observation_universe_size=3)
        self.db = EvidenceDB(self.cfg)
        self.champion_cfg = replace(CHAMPION_CONFIG, bootstrap_samples=100)
        self.lab = WalkForwardChampionEvaluator(self.cfg, self.champion_cfg, self.db)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _price(symbol: str, index: int) -> float:
        if symbol == "BTCUSDT":
            return 100.0 + index * 0.20 + (index % 5) * 0.03
        if symbol == "AAAUSDT":
            return 50.0 + index * 0.30 + (index % 7) * 0.05
        return 80.0 - index * 0.08 + (index % 3) * 0.02

    @classmethod
    def _seed(cls, db, cfg, count):
        interval = cfg.candle_interval_ms
        for index in range(count):
            open_ms = index * interval
            close_ms = open_ms + interval - 1
            symbols = ("BTCUSDT", "AAAUSDT", "BBBUSDT")
            rows = []
            candles = {}
            for rank, symbol in enumerate(symbols, 1):
                close = cls._price(symbol, index)
                rows.append(UniverseRow(
                    symbol, rank, 1_000_000_000.0 / rank,
                    close * 0.9999, close * 1.0001, 0.02 * rank,
                    close, close, 0.0001 * rank,
                    close_ms + 8 * 60 * 60 * 1000,
                ))
                candles[symbol] = Candle(
                    symbol, open_ms, close_ms,
                    close * 0.999, close * 1.003, close * 0.997, close,
                    1000.0, 1_000_000.0, 100, 500.0, 500_000.0,
                )
            status = db.store_event(
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
            if status != "COMPLETE":
                raise AssertionError(status)

    def test_full_final_window_is_frozen_and_post_test_events_are_excluded(self):
        result = self.lab.evaluate()
        self.assertEqual(result.candidate_scored_events, 40)
        self.assertEqual(result.validation_events, 20)
        self.assertEqual(result.test_events, 20)
        report = self.lab.report()
        self.assertEqual(report["post_test_events_used_for_initial_gate"], 0)
        self.assertEqual(len(report["validation_events"]), 20)
        self.assertEqual(len(report["test_events"]), 20)
        status = self.lab.status()
        self.assertGreater(status["post_test_events"], 0)
        self.assertEqual(status["authority"], AUTHORITY)

    def test_strongest_transparent_benchmark_is_frozen_from_validation(self):
        self.lab.evaluate()
        report = self.lab.report()
        validation = report["validation_baselines"]
        expected = sorted(
            (
                (metrics["mean_net_r"], selector)
                for selector, metrics in validation.items()
                if metrics["events"] == 20 and metrics["mean_net_r"] is not None
            ),
            key=lambda item: (-item[0], item[1]),
        )[0][1]
        self.assertEqual(report["benchmark_selector_version"], expected)

    def test_rebuild_is_deterministic_and_audit_is_clean(self):
        self.lab.evaluate()
        with self.db.connection() as conn:
            before = conn.execute(
                "SELECT source_digest, evaluation_digest FROM research_champion_evaluations WHERE evaluation_version=?",
                (self.champion_cfg.evaluation_version,),
            ).fetchone()
        self.lab.evaluate(rebuild=True)
        with self.db.connection() as conn:
            after = conn.execute(
                "SELECT source_digest, evaluation_digest FROM research_champion_evaluations WHERE evaluation_version=?",
                (self.champion_cfg.evaluation_version,),
            ).fetchone()
        self.assertEqual(before, after)
        audit = self.lab.audit()
        self.assertTrue(all(value == 0 for key, value in audit.items() if key != "evaluation_version"))

    def test_source_prediction_tampering_is_detected(self):
        self.lab.evaluate()
        report = self.lab.report()
        event = report["validation_events"][0]
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE entry_selection_predictions SET prediction_digest='tampered' "
                "WHERE event_open_ms=? AND selector_version=? AND rank_in_event=1",
                (event, self.champion_cfg.candidate_selector_version),
            )
        audit = self.lab.audit()
        self.assertGreater(audit["selection_integrity_failures"], 0)
        self.assertGreater(audit["source_digest_mismatch"] + audit["evaluation_digest_mismatch"], 0)

    def test_rejected_candidate_never_creates_champion_authority(self):
        result = self.lab.evaluate()
        self.assertEqual(result.status, "REJECT_RESEARCH_CHAMPION")
        with self.db.connection() as conn:
            champion_count = conn.execute("SELECT COUNT(*) FROM research_champions").fetchone()[0]
        self.assertEqual(champion_count, 0)

    def test_passing_gate_can_only_create_research_only_champion(self):
        with self.db.connection() as conn:
            synthetic_pass = self.lab._compute(conn)
        synthetic_pass["status"] = "PASS_RESEARCH_CHAMPION"
        synthetic_pass["champion_version"] = self.champion_cfg.champion_version
        synthetic_pass["promotion_gates"] = {"synthetic_gate_test": True}
        with mock.patch.object(self.lab, "_compute", return_value=synthetic_pass):
            result = self.lab.evaluate(rebuild=True)
        self.assertEqual(result.champion_version, self.champion_cfg.champion_version)
        with self.db.connection() as conn:
            champion = conn.execute(
                "SELECT champion_version, authority FROM research_champions WHERE evaluation_version=?",
                (self.champion_cfg.evaluation_version,),
            ).fetchone()
        self.assertEqual(champion, (self.champion_cfg.champion_version, AUTHORITY))

    def test_v25_database_adds_champion_tables_without_changing_existing_research_rows(self):
        with self.db.connection() as conn:
            before = tuple(conn.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM entry_selection_examples), "
                "(SELECT COUNT(*) FROM entry_selection_predictions), "
                "(SELECT COUNT(*) FROM exit_policy_results)"
            ).fetchone())
            conn.execute("DROP TABLE research_champions")
            conn.execute("DROP TABLE research_champion_evaluations")
            conn.execute("DROP TABLE research_champion_sets")
        self.db.initialize()
        with self.db.connection() as conn:
            after = tuple(conn.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM entry_selection_examples), "
                "(SELECT COUNT(*) FROM entry_selection_predictions), "
                "(SELECT COUNT(*) FROM exit_policy_results)"
            ).fetchone())
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'research_champion%'"
            ).fetchall()}
        self.assertEqual(before, after)
        self.assertEqual(tables, {"research_champion_sets", "research_champion_evaluations", "research_champions"})

    def test_insufficient_forward_events_waits_without_promoting(self):
        with self.db.connection() as conn:
            events = [row[0] for row in conn.execute(
                "SELECT DISTINCT event_open_ms FROM entry_selection_predictions "
                "WHERE selector_version=? ORDER BY event_open_ms",
                (self.champion_cfg.candidate_selector_version,),
            ).fetchall()]
            keep = set(events[:6])
            for event in events[6:]:
                conn.execute(
                    "DELETE FROM entry_selection_prediction_builds WHERE event_open_ms=? AND selector_version=?",
                    (event, self.champion_cfg.candidate_selector_version),
                )
                conn.execute(
                    "DELETE FROM entry_selection_predictions WHERE event_open_ms=? AND selector_version=?",
                    (event, self.champion_cfg.candidate_selector_version),
                )
        result = self.lab.evaluate(rebuild=True)
        self.assertEqual(result.status, "WAIT_FOR_VALIDATION_EVIDENCE")
        self.assertEqual(result.candidate_scored_events, 6)
        self.assertEqual(result.validation_events, 6)
        self.assertEqual(result.test_events, 0)
        self.assertIsNone(result.champion_version)


if __name__ == "__main__":
    unittest.main()
