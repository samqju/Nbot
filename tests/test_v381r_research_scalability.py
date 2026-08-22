from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.policies import ExitPolicyLab
from nbot.observation.scalability import (
    REFERENCE_RESET_CONFIRMATION,
    ResearchScalabilityRecovery,
    raw_evidence_manifest,
    verify_ridge_reference_equivalence,
    _score_equivalence,
)
from nbot.observation.selection import (
    FEATURE_VECTOR_NAMES,
    EntrySelectionLab,
    RidgeSufficientStatistics,
    SELECTION_CONFIG,
    _fit_ridge,
    _ridge_score,
)
from nbot.observation.signals import ResearchSignalStore
from tests.test_v343_future_paths import FakePublicClient, INTERVAL, store_live


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class V381RRidgeUnitTests(unittest.TestCase):
    def test_sufficient_statistics_preserve_scores_and_ranks(self):
        rows = []
        for event in range(25):
            event_rows = []
            for symbol_index in range(5):
                vector = {
                    name: (
                        (event + 1) * (index + 3) * 0.0007
                        + (symbol_index - 2) * (index + 1) * 0.00011
                    )
                    for index, name in enumerate(FEATURE_VECTOR_NAMES)
                }
                row = {
                    "event_open_ms": event,
                    "symbol": f"S{symbol_index}USDT",
                    "side": "LONG" if symbol_index % 2 == 0 else "SHORT",
                    "target_net_r": 0.05 * event - 0.02 * symbol_index,
                    "feature_vector_json": json.dumps(vector, sort_keys=True, separators=(",", ":")),
                    "example_digest": f"d-{event}-{symbol_index}",
                }
                event_rows.append(row)
            rows.append(event_rows)

        state = RidgeSufficientStatistics.empty()
        training = []
        for event, event_rows in enumerate(rows):
            if event >= 20:
                old = _fit_ridge(training, SELECTION_CONFIG.ridge_alpha)
                new = state.fit(SELECTION_CONFIG.ridge_alpha)
                old_scored = sorted(
                    [(_ridge_score(old, row["feature_vector_json"]), row["symbol"], row["side"]) for row in event_rows],
                    key=lambda item: (-item[0], item[1], item[2]),
                )
                new_scored = sorted(
                    [(_ridge_score(new, row["feature_vector_json"]), row["symbol"], row["side"]) for row in event_rows],
                    key=lambda item: (-item[0], item[1], item[2]),
                )
                self.assertEqual(
                    [(row[1], row[2]) for row in old_scored],
                    [(row[1], row[2]) for row in new_scored],
                )
                self.assertLessEqual(
                    max(abs(a[0] - b[0]) for a, b in zip(old_scored, new_scored)),
                    1e-8,
                )
            state.add_event(event, event_rows)
            training.extend(event_rows)

    def test_post_test_common_intercept_shift_preserves_relative_scores(self):
        old = [1.2, 0.7, -0.1]
        new = [2.402019443, 1.902019443, 1.102019443]
        report = _score_equivalence(
            new, old, exact_required=False, tolerance=1e-8
        )
        self.assertTrue(report["healthy"], report)
        self.assertEqual(report["centered_mismatch_rows"], 0)
        self.assertGreater(report["raw_mismatch_rows"], 0)

    def test_frozen_champion_window_rejects_same_intercept_shift(self):
        old = [1.2, 0.7, -0.1]
        new = [2.402019443, 1.902019443, 1.102019443]
        report = _score_equivalence(
            new, old, exact_required=True, tolerance=1e-8
        )
        self.assertFalse(report["healthy"], report)
        self.assertGreater(report["raw_mismatch_rows"], 0)

    def test_post_test_relative_score_change_still_fails(self):
        old = [1.2, 0.7, -0.1]
        new = [2.402019443, 1.902119443, 1.102019443]
        report = _score_equivalence(
            new, old, exact_required=False, tolerance=1e-8
        )
        self.assertFalse(report["healthy"], report)
        self.assertGreater(report["centered_mismatch_rows"], 0)


class V381RRecoveryIntegrationTests(unittest.TestCase):
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
        FuturePathStore(
            cls.db,
            FakePublicClient(server_time_ms=86 * INTERVAL),
        ).build(max_events=0)
        ExitPolicyLab(cls.db).build(max_events=0)
        EntrySelectionLab(cls.db).build(max_events=0)
        with cls.db.connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cls.reference = Path(cls.tmp.name) / "reference.db"
        shutil.copy2(cls.db.path, cls.reference)
        cls.reference_sha = sha256_file(cls.reference)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.previous)
        cls.tmp.cleanup()

    def test_reference_equivalence_is_read_only_and_rank_exact(self):
        before = sha256_file(self.reference)
        report = verify_ridge_reference_equivalence(
            self.reference,
            self.reference_sha,
        )
        after = sha256_file(self.reference)
        self.assertEqual(before, after)
        self.assertTrue(report["healthy"], report)
        self.assertEqual(report["rank_mismatches"], 0)
        self.assertEqual(report["metadata_mismatches"], 0)
        self.assertEqual(report["frozen_score_mismatches"], 0)
        self.assertEqual(report["post_test_centered_score_mismatches"], 0)
        self.assertGreater(report["compared_events"], 0)

    def test_reset_drops_only_reproducible_research_state(self):
        reset_tmp = tempfile.TemporaryDirectory(dir=self.tmp.name)
        prior = Path.cwd()
        try:
            os.chdir(reset_tmp.name)
            cfg = observation_config_for_profile(get_profile("live-paper"))
            cfg.database_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.reference, cfg.database_path)
            active = cfg.database_path
            db = EvidenceDatabase(cfg)
            with db.connection() as conn:
                before = raw_evidence_manifest(conn)
            before_bytes = active.stat().st_size
            report = ResearchScalabilityRecovery(db).reset_derived(
                reference_db=self.reference,
                reference_sha256=self.reference_sha,
                confirmation=REFERENCE_RESET_CONFIRMATION,
            )
            with db.connection() as conn:
                after = raw_evidence_manifest(conn)
                tables = {
                    str(row[0])
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            self.assertEqual(before, after)
            self.assertTrue(report["raw_manifest_unchanged"])
            self.assertEqual(report["foreign_key_errors"], 0)
            self.assertEqual(report["quick_check"], "ok")
            self.assertNotIn("entry_selection_predictions", tables)
            self.assertNotIn("exit_policy_results", tables)
            self.assertIn("market_events", tables)
            self.assertLess(active.stat().st_size, before_bytes)
        finally:
            os.chdir(prior)
            reset_tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
