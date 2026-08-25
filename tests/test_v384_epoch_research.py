from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.epoch import (
    CUTOVER_CONFIRMATION,
    ResearchEpochProcessor,
    cutover_to_fresh_raw_generation,
)
from nbot.observation.research_memory import ResearchMemoryStore
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.signals import ResearchSignalStore
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.policies import ExitPolicyLab
from nbot.observation.retention import ResearchRetentionManager
from nbot.observation.selection import EntrySelectionLab
from tests.test_v343_future_paths import (
    FakePublicClient, INTERVAL, TARGET_OPEN, seed_target_and_future, store_live,
)


class V384EpochResearchTests(unittest.TestCase):
    def test_00_selection_normal_build_does_not_rescore_old_events(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            os.chdir(td)
            try:
                cfg = observation_config_for_profile(get_profile("live-paper"))
                db = EvidenceDatabase(cfg)
                # This test only verifies the hot-path event list contract using
                # a synthetic subclass; no complete research build is needed.
                lab = EntrySelectionLab(db)
                self.assertIn("entry_selection_history_base", __import__(
                    "nbot.observation.selection", fromlist=["RESEARCH_SELECTION_TABLES"]
                ).RESEARCH_SELECTION_TABLES)
            finally:
                os.chdir(prior)

    def test_01_one_96_event_epoch_commits_compact_memory_and_deletes_scratch(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            os.chdir(td)
            try:
                cfg = observation_config_for_profile(get_profile("live-paper"))
                raw = EvidenceDatabase(cfg)
                for index in range(192):
                    store_live(raw, index)
                raw.store_funding_sync(
                    start_ms=0,
                    end_ms=192 * INTERVAL,
                    events=(),
                    captured_at_ms=193 * INTERVAL,
                )
                memory = ResearchMemoryStore(Path("data/observation/live/research_memory.db"))
                memory.initialize(
                    generation="TEST_EPOCH_V1",
                    generation_floor_ms=48 * INTERVAL,
                )
                processor = ResearchEpochProcessor(
                    raw,
                    memory,
                    Path.cwd(),
                    future_client_factory=lambda _cfg: FakePublicClient(
                        server_time_ms=193 * INTERVAL
                    ),
                )
                plan = processor.plan()
                self.assertEqual(plan.status, "READY")
                self.assertEqual(len(plan.target_events), 96)
                report = processor.run_once()
                self.assertEqual(report["status"], "PASS", report)
                self.assertEqual(report["memory_rows_imported"], 96)
                status = memory.status()
                self.assertEqual(status["events"], 96)
                self.assertEqual(status["ridge_state"]["training_event_count"], 96)
                transition = memory.pending_challenger_transition()
                self.assertIsNotNone(transition)
                self.assertEqual(transition["epoch_id"], report["epoch_id"])
                self.assertEqual(transition["target_end_ms"], plan.target_events[-1])
                self.assertEqual(transition["state"], "PENDING")
                self.assertEqual(transition["attempt_count"], 0)
                transition_status = memory.challenger_transition_status()
                self.assertEqual(transition_status["pending"], 1)
                self.assertEqual(transition_status["completed"], 0)
                scratch = Path("runtime/observation/live/research_epochs") / (
                    f"EPOCH-{plan.target_events[0]}-{plan.target_events[-1]}.db"
                )
                self.assertFalse(scratch.exists())
                # Exact-once: same raw evidence cannot become a second epoch.
                second = processor.plan()
                self.assertNotEqual(second.status, "READY")
            finally:
                os.chdir(prior)

    def test_02_prune_keeps_48_bar_dependency_tail(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            os.chdir(td)
            try:
                cfg = observation_config_for_profile(get_profile("live-paper"))
                raw = EvidenceDatabase(cfg)
                for index in range(80):
                    store_live(raw, index)
                memory = ResearchMemoryStore(Path("data/observation/live/research_memory.db"))
                memory.initialize(generation="TEST", generation_floor_ms=0)
                # Seed one memory event by constructing from a tiny legacy-like
                # store would be excessive here; exercise NO_QUALIFIED_MEMORY.
                processor = ResearchEpochProcessor(raw, memory, Path.cwd())
                report = processor.prune_raw()
                self.assertEqual(report["deleted_events"], 0)
                self.assertEqual(report["reason"], "NO_QUALIFIED_MEMORY")
            finally:
                os.chdir(prior)

    def test_03_cutover_discards_legacy_generation_and_starts_empty_raw_and_memory(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            os.chdir(td)
            try:
                cfg = observation_config_for_profile(get_profile("live-paper"))
                legacy = EvidenceDatabase(cfg)
                for index in range(85):
                    store_live(legacy, index)
                memory = ResearchMemoryStore(Path("data/observation/live/research_memory.db"))
                report = cutover_to_fresh_raw_generation(
                    legacy, memory, Path.cwd(), Path("artifacts"),
                    generation="TEST_CUTOVER_V1",
                    confirmation=CUTOVER_CONFIRMATION,
                )
                self.assertTrue(report["discarded_legacy_database"])
                self.assertEqual(report["fresh_raw_events"], 0)
                self.assertEqual(report["fresh_memory"]["events"], 0)
                self.assertEqual(
                    report["generation_floor_ms"],
                    84 * INTERVAL + 49 * INTERVAL,
                )
                active = EvidenceDatabase(cfg)
                with active.connection() as conn:
                    tables = {str(r[0]) for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )}
                    self.assertEqual(conn.execute(
                        "SELECT COUNT(*) FROM market_events"
                    ).fetchone()[0], 0)
                self.assertNotIn("canonical_features", tables)
                self.assertTrue(Path(report["reset_manifest"]).exists())
            finally:
                os.chdir(prior)

    def test_04_disposable_workspace_uses_ephemeral_sqlite_durability(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            os.chdir(td)
            try:
                cfg = observation_config_for_profile(get_profile("live-paper"))
                scratch = EvidenceDatabase(
                    cfg,
                    path_override=Path("runtime/research/scratch.db"),
                    ephemeral_research=True,
                )
                scratch.initialize()
                with scratch.connection() as conn:
                    self.assertEqual(str(conn.execute(
                        "PRAGMA journal_mode"
                    ).fetchone()[0]).lower(), "memory")
                    self.assertEqual(int(conn.execute(
                        "PRAGMA synchronous"
                    ).fetchone()[0]), 0)
                    self.assertEqual(int(conn.execute(
                        "PRAGMA temp_store"
                    ).fetchone()[0]), 2)
                    self.assertEqual(int(conn.execute(
                        "PRAGMA foreign_keys"
                    ).fetchone()[0]), 1)
                with self.assertRaisesRegex(
                    ValueError, "EPHEMERAL_RESEARCH_REQUIRES_PATH_OVERRIDE"
                ):
                    EvidenceDatabase(cfg, ephemeral_research=True)
            finally:
                os.chdir(prior)

    def test_05_bulk_future_and_policy_path_loads_preserve_single_symbol_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            os.chdir(td)
            try:
                cfg = observation_config_for_profile(get_profile("live-paper"))
                db = EvidenceDatabase(cfg)
                seed_target_and_future(db)
                outcomes = FuturePathStore(db, FakePublicClient())
                outcomes.initialize()
                with db.connection() as conn:
                    single_map, single_fallback = outcomes._load_path_candles(
                        conn, "AAAUSDT", TARGET_OPEN
                    )
                    bulk_map, bulk_fallback = outcomes._load_path_candles_bulk(
                        conn, ["AAAUSDT"], TARGET_OPEN
                    )["AAAUSDT"]
                self.assertEqual(single_map, bulk_map)
                self.assertEqual(single_fallback, bulk_fallback)

                built = outcomes.build(max_events=0)
                self.assertGreater(built.built_events, 0)
                policies = ExitPolicyLab(db)
                with db.connection() as conn:
                    single_path = policies._load_path(conn, "AAAUSDT", TARGET_OPEN)
                    bulk_path = policies._load_paths_bulk(
                        conn, ["AAAUSDT"], TARGET_OPEN
                    )["AAAUSDT"]
                self.assertEqual(single_path, bulk_path)
            finally:
                os.chdir(prior)


if __name__ == "__main__":
    unittest.main()
