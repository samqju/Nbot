from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from nbot.config.profiles import get_profile
from nbot.observation.champion import (
    AUTHORITY,
    RESEARCH_CHAMPION_TABLES,
    ChampionConfig,
    MemoryWalkForwardChampionEvaluator,
    WalkForwardChampionEvaluator,
)
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.policies import ExitPolicyLab
from nbot.observation.research_memory import LEDGER_COLUMNS, ResearchMemoryStore
from nbot.observation.retention import ResearchRetentionManager
from nbot.observation.selection import BASELINE_SELECTORS, EntrySelectionLab
from nbot.observation.signals import ResearchSignalStore
from tests.test_v343_future_paths import FakePublicClient, INTERVAL, store_live


class V346ResearchChampionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._seed_tmp = tempfile.TemporaryDirectory()
        previous = Path.cwd()
        os.chdir(cls._seed_tmp.name)
        try:
            cfg = observation_config_for_profile(get_profile("live-paper"))
            db = EvidenceDatabase(cfg)
            # 180 point-in-time events produce 43 strictly forward-scored ridge
            # events: enough to freeze 20 validation + 20 final-test events and
            # leave later evidence outside the initial promotion decision.
            for index in range(180):
                store_live(db, index)
            CanonicalFeatureStore(db).build(max_events=0)
            ResearchSignalStore(db).build(max_events=0)
            db.store_funding_sync(
                start_ms=INTERVAL,
                end_ms=180 * INTERVAL - 1,
                events=(),
                captured_at_ms=181 * INTERVAL,
            )
            FuturePathStore(
                db,
                FakePublicClient(server_time_ms=181 * INTERVAL),
            ).build(max_events=0)
            ExitPolicyLab(db).build(max_events=0)
            EntrySelectionLab(db).build(max_events=0)
            with db.connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cls._seed_db = Path(cls._seed_tmp.name) / cfg.database_path
        finally:
            os.chdir(previous)

    @classmethod
    def tearDownClass(cls):
        cls._seed_tmp.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._previous = Path.cwd()
        os.chdir(self._tmp.name)
        cfg = observation_config_for_profile(get_profile("live-paper"))
        cfg.database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._seed_db, cfg.database_path)
        self.db = EvidenceDatabase(cfg)
        self.config = replace(ChampionConfig(), bootstrap_samples=100)
        self.lab = WalkForwardChampionEvaluator(self.db, self.config)

    def tearDown(self):
        os.chdir(self._previous)
        self._tmp.cleanup()

    def test_definition_freezes_v2_walk_forward_philosophy_and_research_only_authority(self):
        definition = self.lab.definition()
        self.assertEqual(definition["validation_rule"], "FIRST_20_FORWARD_SCORED_EVENTS")
        self.assertEqual(definition["final_test_rule"], "NEXT_20_FORWARD_SCORED_EVENTS_FROZEN_ONCE_AVAILABLE")
        self.assertEqual(definition["independence_unit"], "MARKET_EVENT_NOT_SYMBOL_ROW")
        self.assertEqual(definition["authority"], "RESEARCH_ONLY_NO_EXECUTION")
        self.assertEqual(AUTHORITY, "RESEARCH_ONLY_NO_EXECUTION")
        self.assertEqual(definition["cost_stress"]["multipliers"], [1.0, 1.5, 2.0])

    def test_audit_is_read_only_before_champion_tables_exist(self):
        report = self.lab.audit()
        self.assertFalse(report["healthy"])
        self.assertEqual(set(report["missing_tables"]), set(RESEARCH_CHAMPION_TABLES))
        with self.db.connection() as conn:
            present = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        self.assertTrue(set(RESEARCH_CHAMPION_TABLES).isdisjoint(present))

    def test_final_window_is_frozen_and_benchmark_uses_validation_only(self):
        result = self.lab.evaluate()
        self.assertEqual(result.candidate_scored_events, 40)
        self.assertEqual(result.validation_events, 20)
        self.assertEqual(result.test_events, 20)
        report = self.lab.report()
        self.assertEqual(report["post_test_events_used_for_initial_gate"], 0)
        self.assertEqual(len(report["validation_events"]), 20)
        self.assertEqual(len(report["test_events"]), 20)
        validation = report["validation_baselines"]
        expected = sorted(
            (
                (metrics["mean_net_r"], selector.selector_version)
                for selector in BASELINE_SELECTORS
                for metrics in (validation[selector.selector_version],)
                if metrics["events"] == 20 and metrics["mean_net_r"] is not None
            ),
            key=lambda item: (-item[0], item[1]),
        )[0][1]
        self.assertEqual(report["benchmark_selector_version"], expected)
        self.assertGreater(self.lab.status()["post_test_events"], 0)

    def test_rebuild_is_deterministic_and_audit_clean(self):
        self.lab.evaluate()
        with self.db.connection() as conn:
            before = conn.execute(
                "SELECT source_digest,evaluation_digest FROM research_champion_evaluations "
                "WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
        self.lab.evaluate(rebuild=True)
        with self.db.connection() as conn:
            after = conn.execute(
                "SELECT source_digest,evaluation_digest FROM research_champion_evaluations "
                "WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
        self.assertEqual(before, after)
        audit = self.lab.audit()
        self.assertTrue(audit["healthy"], audit)

    def test_rejected_candidate_never_gets_authority(self):
        result = self.lab.evaluate()
        self.assertEqual(result.status, "REJECT_RESEARCH_CHAMPION")
        with self.db.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM research_champions").fetchone()[0]
        self.assertEqual(count, 0)

    def test_synthetic_pass_can_only_create_research_only_authority(self):
        with self.db.connection() as conn:
            self.lab.initialize()
            synthetic = self.lab._compute(conn)
        synthetic["status"] = "PASS_RESEARCH_CHAMPION"
        synthetic["champion_version"] = self.config.champion_version
        synthetic["promotion_gates"] = {"synthetic_test": True}
        with mock.patch.object(self.lab, "_compute", return_value=synthetic):
            result = self.lab.evaluate(rebuild=True)
        self.assertEqual(result.champion_version, self.config.champion_version)
        with self.db.connection() as conn:
            champion = conn.execute(
                "SELECT champion_version,authority FROM research_champions WHERE evaluation_version=?",
                (self.config.evaluation_version,),
            ).fetchone()
        self.assertEqual(champion, (self.config.champion_version, AUTHORITY))

    def test_compact_memory_replay_matches_frozen_relational_gate(self):
        relational_result = self.lab.evaluate()
        relational_report = self.lab.report()

        retention = ResearchRetentionManager(self.db)
        retention.initialize()
        retention.seal(max_events=0)
        with self.db.connection() as conn:
            rows = list(conn.execute(
                "SELECT " + ",".join(LEDGER_COLUMNS)
                + " FROM research_event_ledger ORDER BY event_open_ms"
            ))

        memory = ResearchMemoryStore(Path("research_memory.db"))
        memory.initialize(generation="TEST_V39", generation_floor_ms=0)
        memory.import_ledger_rows(rows, source_generation="TEST_V39")
        compact = MemoryWalkForwardChampionEvaluator(memory, self.config)
        compact_result = compact.evaluate()
        compact_report = compact.report()

        self.assertEqual(compact_result.status, relational_result.status)
        self.assertEqual(compact_result.validation_events, relational_result.validation_events)
        self.assertEqual(compact_result.test_events, relational_result.test_events)
        self.assertEqual(
            compact_report["benchmark_selector_version"],
            relational_report["benchmark_selector_version"],
        )
        self.assertEqual(
            compact_report["promotion_gates"],
            relational_report["promotion_gates"],
        )
        self.assertEqual(
            compact_report["final_test"]["candidate"],
            relational_report["final_test"]["candidate"],
        )
        self.assertEqual(
            compact_report["final_test"]["benchmark"],
            relational_report["final_test"]["benchmark"],
        )
        self.assertEqual(
            compact_report["final_test"]["paired_lift"],
            relational_report["final_test"]["paired_lift"],
        )
        self.assertEqual(
            compact_report["final_test"]["bucket_separation"],
            relational_report["final_test"]["bucket_separation"],
        )
        self.assertEqual(
            compact_report["final_test"]["cost_and_capture"],
            relational_report["final_test"]["cost_and_capture"],
        )
        self.assertEqual(
            compact_report["final_test"]["stability"],
            relational_report["final_test"]["stability"],
        )
        self.assertTrue(compact.audit()["healthy"])
        self.assertGreater(compact.status()["post_test_events"], 0)

    def test_source_tampering_is_detected(self):
        self.lab.evaluate()
        event = self.lab.report()["validation_events"][0]
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE entry_selection_predictions SET prediction_digest='tampered' "
                "WHERE event_open_ms=? AND selector_version=? AND rank_in_event=1",
                (event, self.config.candidate_selector_version),
            )
        audit = self.lab.audit()
        self.assertFalse(audit["healthy"])
        self.assertGreater(audit["selection_integrity_failures"], 0)

    def test_insufficient_evidence_waits_without_promoting(self):
        with self.db.connection() as conn:
            events = [
                int(row[0])
                for row in conn.execute(
                    "SELECT DISTINCT event_open_ms FROM entry_selection_predictions "
                    "WHERE selector_version=? ORDER BY event_open_ms",
                    (self.config.candidate_selector_version,),
                ).fetchall()
            ]
            for event in events[6:]:
                conn.execute(
                    "DELETE FROM entry_selection_prediction_builds "
                    "WHERE event_open_ms=? AND selector_version=?",
                    (event, self.config.candidate_selector_version),
                )
                conn.execute(
                    "DELETE FROM entry_selection_predictions "
                    "WHERE event_open_ms=? AND selector_version=?",
                    (event, self.config.candidate_selector_version),
                )
        result = self.lab.evaluate(rebuild=True)
        self.assertEqual(result.status, "WAIT_FOR_VALIDATION_EVIDENCE")
        self.assertEqual(result.candidate_scored_events, 6)
        self.assertIsNone(result.champion_version)


if __name__ == "__main__":
    unittest.main()
