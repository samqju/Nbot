from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.policies import CONTROL_POLICY_VERSION, ExitPolicyLab, LAB_VERSION
from nbot.observation.selection import (
    BASELINE_SELECTORS,
    FEATURE_VECTOR_NAMES,
    RESEARCH_SELECTION_TABLES,
    SELECTORS,
    EntrySelectionLab,
    SelectionConfig,
)
from nbot.observation.signals import ResearchSignalStore
from tests.test_v343_future_paths import FakePublicClient, INTERVAL, store_live


def digest_tables(db: EvidenceDatabase, tables: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    with db.connection() as conn:
        for table in tables:
            columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
            order = ",".join(columns)
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                payload = json.dumps(
                    [table, list(row)],
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=True,
                ).encode("utf-8")
                digest.update(payload)
                digest.update(b"\n")
    return digest.hexdigest()


RAW_TABLES = (
    "metadata",
    "market_events",
    "candles_5m",
    "market_snapshots",
    "event_provenance",
    "universe_membership",
    "source_captures",
    "funding_events",
    "funding_sync_ranges",
)
FEATURE_TABLES = ("feature_sets", "canonical_features", "feature_builds")
SIGNAL_TABLES = ("signal_sets", "signal_annotations", "signal_builds")
FUTURE_TABLES = (
    "future_path_sets",
    "future_candle_cache",
    "future_paths",
    "future_path_builds",
    "future_path_attempts",
)
POLICY_TABLES = (
    "exit_policy_labs",
    "exit_policy_sets",
    "exit_policy_results",
    "exit_policy_builds",
)


class V345EntrySelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._seed_tmp = tempfile.TemporaryDirectory()
        previous = Path.cwd()
        os.chdir(cls._seed_tmp.name)
        try:
            cfg = observation_config_for_profile(get_profile("live-paper"))
            db = EvidenceDatabase(cfg)
            # 85 point-in-time events leave 23 ATR-risk-eligible events with a
            # fully mature 48-bar future path (events 14..36), enough to prove
            # the frozen 20-prior-event ridge chronology without weakening it.
            for index in range(85):
                store_live(db, index)
            CanonicalFeatureStore(db).build(max_events=0)
            ResearchSignalStore(db).build(max_events=0)
            db.store_funding_sync(
                start_ms=INTERVAL,
                end_ms=85 * INTERVAL - 1,
                events=(),
                captured_at_ms=86 * INTERVAL,
            )
            FuturePathStore(
                db,
                FakePublicClient(server_time_ms=86 * INTERVAL),
            ).build(max_events=0)
            ExitPolicyLab(db).build(max_events=0)
            with db.connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cls._seed_db = Path(cls._seed_tmp.name) / cfg.database_path
            cls._expected_source = (23, 46)
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
        self.lab = EntrySelectionLab(self.db)

    def tearDown(self):
        os.chdir(self._previous)
        self._tmp.cleanup()

    def test_catalog_and_definition_are_frozen_and_research_only(self):
        self.assertEqual(len(BASELINE_SELECTORS), 5)
        self.assertEqual(len(SELECTORS), 6)
        self.assertEqual(
            [spec.selector_version for spec in SELECTORS if spec.is_learned],
            ["RIDGE_EXPECTED_NET_R_V1"],
        )
        self.assertEqual(self.lab.definition()["target_name"], "AFTER_COST_NET_R")
        self.assertEqual(
            self.lab.definition()["authority"],
            "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION",
        )
        with self.assertRaisesRegex(ValueError, "MIN_TRAIN_EVENTS_IMMUTABLE"):
            replace(SelectionConfig(), min_train_events=19).validate()
        with self.assertRaisesRegex(ValueError, "RIDGE_ALPHA_IMMUTABLE"):
            replace(SelectionConfig(), ridge_alpha=1.0).validate()

    def test_audit_is_read_only_when_selection_tables_do_not_exist(self):
        report = self.lab.audit()
        self.assertFalse(report["healthy"])
        self.assertEqual(set(report["missing_tables"]), set(RESEARCH_SELECTION_TABLES))
        with self.db.connection() as conn:
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertTrue(set(RESEARCH_SELECTION_TABLES).isdisjoint(tables))

    def test_every_control_policy_symbol_side_becomes_example_without_signal_gating(self):
        result = self.lab.build(max_events=0)
        self.assertEqual((result.source_events, result.source_rows), self._expected_source)
        self.assertEqual(result.example_rows, result.source_rows)
        with self.db.connection() as conn:
            target_rows = int(conn.execute(
                "SELECT COUNT(*) FROM exit_policy_results WHERE lab_version=? AND policy_version=?",
                (LAB_VERSION, CONTROL_POLICY_VERSION),
            ).fetchone()[0])
            examples = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_examples WHERE lab_version=?",
                (self.lab.config.lab_version,),
            ).fetchone()[0])
            sides = conn.execute(
                "SELECT side,COUNT(*) FROM entry_selection_examples GROUP BY side ORDER BY side"
            ).fetchall()
        self.assertEqual(examples, target_rows)
        self.assertEqual(sides, [("LONG", 23), ("SHORT", 23)])

    def test_baselines_score_every_example_and_ridge_is_strictly_forward_chained(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            events = conn.execute(
                "SELECT event_open_ms,COUNT(*) FROM entry_selection_examples "
                "GROUP BY event_open_ms ORDER BY event_open_ms"
            ).fetchall()
            for event_open_ms, count in events:
                for spec in BASELINE_SELECTORS:
                    actual = int(conn.execute(
                        "SELECT COUNT(*) FROM entry_selection_predictions "
                        "WHERE event_open_ms=? AND selector_version=?",
                        (event_open_ms, spec.selector_version),
                    ).fetchone()[0])
                    self.assertEqual(actual, count)
            learned = conn.execute(
                "SELECT DISTINCT event_open_ms,trained_through_event_ms,training_event_count,training_row_count "
                "FROM entry_selection_predictions WHERE selector_version=? ORDER BY event_open_ms",
                (self.lab.config.learned_selector_version,),
            ).fetchall()
        # These 23 adjacent events all fall inside the 48-bar label horizon.
        self.assertEqual(len(learned), 0)
        for event_open_ms, trained_through, training_events, training_rows in learned:
            self.assertLess(trained_through, event_open_ms)
            self.assertGreaterEqual(training_events, 20)
            self.assertEqual(training_rows, training_events * 2)

    def test_prediction_ranks_are_complete_and_vectors_contain_decision_time_inputs_only(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            ranks = conn.execute(
                "SELECT event_open_ms,selector_version,COUNT(*),MIN(rank_in_event),MAX(rank_in_event),"
                "COUNT(DISTINCT rank_in_event) FROM entry_selection_predictions "
                "GROUP BY event_open_ms,selector_version"
            ).fetchall()
            vectors = [
                json.loads(str(row[0]))
                for row in conn.execute(
                    "SELECT feature_vector_json FROM entry_selection_examples LIMIT 4"
                ).fetchall()
            ]
        for _event, _selector, count, minimum, maximum, distinct_count in ranks:
            self.assertEqual((minimum, maximum, distinct_count), (1, count, count))
        for vector in vectors:
            self.assertEqual(set(vector), set(FEATURE_VECTOR_NAMES))
            self.assertEqual(len(vector), len(FEATURE_VECTOR_NAMES))
            self.assertNotIn("target_net_r", vector)
            self.assertNotIn("net_r", vector)

    def test_build_is_deterministic_and_does_not_mutate_lower_layers(self):
        lower = RAW_TABLES + FEATURE_TABLES + SIGNAL_TABLES + FUTURE_TABLES + POLICY_TABLES
        before = digest_tables(self.db, lower)
        first = self.lab.build(max_events=0)
        self.assertEqual(first.example_rows, 46)
        after_build = digest_tables(self.db, lower)
        self.assertEqual(before, after_build)
        with self.db.connection() as conn:
            examples_before = conn.execute(
                "SELECT event_open_ms,source_digest,example_digest FROM entry_selection_builds ORDER BY event_open_ms"
            ).fetchall()
            predictions_before = conn.execute(
                "SELECT event_open_ms,selector_version,source_digest,prediction_digest,model_digest "
                "FROM entry_selection_prediction_builds ORDER BY event_open_ms,selector_version"
            ).fetchall()
        rebuilt = self.lab.build(max_events=1, rebuild=True)
        self.assertEqual(rebuilt.built_example_events, 1)
        with self.db.connection() as conn:
            examples_after = conn.execute(
                "SELECT event_open_ms,source_digest,example_digest FROM entry_selection_builds ORDER BY event_open_ms"
            ).fetchall()
            predictions_after = conn.execute(
                "SELECT event_open_ms,selector_version,source_digest,prediction_digest,model_digest "
                "FROM entry_selection_prediction_builds ORDER BY event_open_ms,selector_version"
            ).fetchall()
        self.assertEqual(examples_before, examples_after)
        self.assertEqual(predictions_before, predictions_after)
        self.assertEqual(before, digest_tables(self.db, lower))
        audit = self.lab.audit()
        self.assertTrue(audit["healthy"], audit)

    def test_report_is_economic_research_only(self):
        self.lab.build(max_events=0)
        report = self.lab.report()
        self.assertEqual(
            report["authority"],
            "RESEARCH_ONLY_NO_CHAMPION_NO_RECOMMENDATION_NO_EXECUTION",
        )
        self.assertIn("NOT_A_PROBABILITY_MODEL", report["calibration_note"])
        self.assertEqual(set(report["selectors"]), {spec.selector_version for spec in SELECTORS})
        learned = report["selectors"]["RIDGE_EXPECTED_NET_R_V1"]
        self.assertEqual(learned["independent_market_events"], 0)
        self.assertEqual(learned["rows"], 0)
        self.assertNotIn("mean_event_selection_regret_r", learned)

    def test_restart_scores_committed_examples_after_interrupted_build(self):
        with patch.object(self.lab, "_score_event", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                self.lab.build(max_events=0)
        self.lab.build(max_events=0)
        self.assertTrue(self.lab.audit()["healthy"])
        with self.db.connection() as conn:
            self.assertEqual(self.lab._load_ridge_state(conn).event_count, 23)

    def test_audit_detects_policy_feature_and_signal_source_mutation(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            event_open_ms, symbol, side = conn.execute(
                "SELECT event_open_ms,symbol,side FROM entry_selection_examples ORDER BY event_open_ms LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE exit_policy_results SET net_r=net_r+1 WHERE event_open_ms=? AND symbol=? "
                "AND side=? AND lab_version=? AND policy_version=?",
                (event_open_ms, symbol, side, LAB_VERSION, CONTROL_POLICY_VERSION),
            )
        policy = self.lab.audit()
        self.assertFalse(policy["healthy"])
        self.assertGreater(policy["policy_result_integrity_mismatches"], 0)

        # Restore from a fresh copy for independent feature and signal checks.
        self.tearDown()
        self.setUp()
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            event_open_ms, symbol = conn.execute(
                "SELECT event_open_ms,symbol FROM entry_selection_examples ORDER BY event_open_ms LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE canonical_features SET ret_5m=ret_5m+0.01 WHERE event_open_ms=? AND symbol=?",
                (event_open_ms, symbol),
            )
        feature = self.lab.audit()
        self.assertFalse(feature["healthy"])
        self.assertGreater(feature["feature_build_integrity_mismatches"], 0)
        self.assertGreater(feature["feature_vector_mismatches"], 0)

        self.tearDown()
        self.setUp()
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            event_open_ms, symbol = conn.execute(
                "SELECT event_open_ms,symbol FROM entry_selection_examples ORDER BY event_open_ms LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE signal_annotations SET score=COALESCE(score,0)+0.25 "
                "WHERE event_open_ms=? AND symbol=? AND signal_version='CSM_RANK_1H_4H_V1'",
                (event_open_ms, symbol),
            )
        signal = self.lab.audit()
        self.assertFalse(signal["healthy"])
        self.assertGreater(signal["signal_build_integrity_mismatches"], 0)
        self.assertGreater(signal["feature_vector_mismatches"], 0)

    def test_audit_detects_prediction_tamper(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT event_open_ms,symbol,side,selector_version FROM entry_selection_predictions "
                "ORDER BY event_open_ms,selector_version,rank_in_event LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE entry_selection_predictions SET score=score+1 WHERE event_open_ms=? AND symbol=? "
                "AND side=? AND selector_version=?",
                row,
            )
        report = self.lab.audit()
        self.assertFalse(report["healthy"])
        self.assertGreater(report["prediction_digest_mismatches"], 0)
        self.assertGreater(report["prediction_value_mismatches"], 0)

    def test_definition_tamper_is_detected_without_repair(self):
        self.lab.build(max_events=0)
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE entry_selector_sets SET definition_hash='tampered' WHERE selector_version='LIQUIDITY_BASELINE_V1'"
            )
        report = self.lab.audit()
        self.assertFalse(report["healthy"])
        self.assertGreater(report["selector_definition_mismatches"], 0)
        with self.db.connection() as conn:
            stored = conn.execute(
                "SELECT definition_hash FROM entry_selector_sets WHERE selector_version='LIQUIDITY_BASELINE_V1'"
            ).fetchone()[0]
        self.assertEqual(stored, "tampered")


if __name__ == "__main__":
    unittest.main()
