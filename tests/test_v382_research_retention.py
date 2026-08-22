from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.policies import ExitPolicyLab
from nbot.observation.retention import ResearchRetentionManager, RetentionConfig, RETENTION_TABLES
from nbot.observation.selection import EntrySelectionLab
from nbot.observation.scalability import raw_evidence_manifest
from nbot.observation.signals import ResearchSignalStore
from tests.test_v343_future_paths import FakePublicClient, INTERVAL, store_live


class V382ResearchRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.previous = Path.cwd()
        os.chdir(cls.tmp.name)
        cfg = observation_config_for_profile(get_profile("live-paper"))
        cls.db = EvidenceDatabase(cfg)
        for index in range(85):
            store_live(cls.db, index)
        CanonicalFeatureStore(cls.db).build(max_events=0)
        ResearchSignalStore(cls.db).build(max_events=0)
        cls.db.store_funding_sync(
            start_ms=INTERVAL,
            end_ms=85 * INTERVAL - 1,
            events=(),
            captured_at_ms=86 * INTERVAL,
        )
        FuturePathStore(cls.db, FakePublicClient(server_time_ms=86 * INTERVAL)).build(max_events=0)
        ExitPolicyLab(cls.db).build(max_events=0)
        EntrySelectionLab(cls.db).build(max_events=0)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.previous)
        cls.tmp.cleanup()

    def _manager(self):
        # Small protected windows only for the synthetic test. Production
        # RetentionConfig enforces the canonical 60-event frozen window.
        config = object.__new__(RetentionConfig)
        object.__setattr__(config, "archive_version", "COMPACT_RESEARCH_LEDGER_V1")
        object.__setattr__(config, "frozen_detail_selection_events", 2)
        object.__setattr__(config, "recent_detail_selection_events", 2)
        object.__setattr__(config, "max_seal_events", 100)
        object.__setattr__(config, "max_compact_events", 100)
        object.__setattr__(config, "hard_live_bytes", 1_073_741_824)
        # Bypass only the production minimum for this bounded fixture.
        manager = ResearchRetentionManager.__new__(ResearchRetentionManager)
        manager.database = self.db
        manager.config = config
        return manager


    def test_00_audit_is_read_only_before_retention_tables_exist(self):
        with tempfile.TemporaryDirectory() as td:
            prior = Path.cwd()
            try:
                os.chdir(td)
                cfg = observation_config_for_profile(get_profile("live-paper"))
                db = EvidenceDatabase(cfg)
                report = ResearchRetentionManager(db).audit()
                self.assertFalse(report["healthy"])
                self.assertEqual(set(report["missing_tables"]), set(RETENTION_TABLES))
                with db.connection() as conn:
                    present = {
                        str(row[0]) for row in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                self.assertTrue(set(RETENTION_TABLES).isdisjoint(present))
            finally:
                os.chdir(prior)

    def test_01_seal_then_compact_preserves_archive_and_prevents_rebuild(self):
        manager = self._manager()
        manager.initialize()
        sealed = manager.seal(max_events=0)
        self.assertGreaterEqual(sealed["sealed_events"], 6)

        before = manager.status()
        with self.db.connection() as conn:
            raw_before = raw_evidence_manifest(conn)
        compact = manager.compact(max_events=0)
        with self.db.connection() as conn:
            raw_after = raw_evidence_manifest(conn)
        self.assertEqual(raw_before, raw_after)
        self.assertGreater(compact["compacted_events"], 0, compact)
        audit = manager.audit()
        self.assertTrue(audit["healthy"], audit)
        self.assertEqual(audit["compacted_detail_rows"], 0)
        self.assertGreater(audit["archived_training_rows"], 0)
        self.assertLess(audit["training_archive_compression_ratio"], 0.75)
        selection_audit = EntrySelectionLab(self.db).audit()
        self.assertTrue(selection_audit["healthy"], selection_audit)

        with self.db.connection() as conn:
            event = conn.execute(
                "SELECT event_open_ms FROM research_event_ledger WHERE state='COMPACTED' ORDER BY event_open_ms LIMIT 1"
            ).fetchone()[0]
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM canonical_features WHERE event_open_ms=?", (event,)
            ).fetchone()[0], 0)
            archived = manager.load_training_rows(int(event))
            self.assertGreater(len(archived), 0)

        # The raw event still exists, but the feature builder must recognize
        # intentional compaction and must not recreate its detailed rows.
        CanonicalFeatureStore(self.db).build(max_events=0)
        with self.assertRaisesRegex(RuntimeError, "NBOT_V382_SELECTION_REBUILD_BLOCKED_BY_COMPACTED_HISTORY"):
            EntrySelectionLab(self.db).build(max_events=0, rebuild=True)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM canonical_features WHERE event_open_ms=?", (event,)
            ).fetchone()[0], 0)

        after = manager.status()
        self.assertGreaterEqual(after["reusable_bytes"], before["reusable_bytes"])

    def test_02_archive_tamper_is_detected(self):
        manager = self._manager()
        manager.initialize()
        manager.seal(max_events=1)
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT event_open_ms FROM research_event_ledger ORDER BY event_open_ms LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE research_event_ledger SET training_blob=? WHERE event_open_ms=?",
                (b"corrupt-zlib", int(row[0])),
            )
        audit = manager.audit()
        self.assertFalse(audit["healthy"], audit)
        self.assertGreater(audit["archive_digest_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
