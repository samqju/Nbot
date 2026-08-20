from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import nbot_admin
from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.learning import (
    FOUNDATION_VERSION,
    LEARNING_TABLES,
    RESEARCH_AUTHORITY,
    ContinuousLearningFoundation,
)


class V347ContinuousLearningFoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = Path.cwd()
        os.chdir(self.tmp.name)
        cfg = observation_config_for_profile(get_profile("live-paper"))
        self.db = EvidenceDatabase(cfg)
        self.foundation = ContinuousLearningFoundation(self.db)

    def tearDown(self):
        os.chdir(self.previous)
        self.tmp.cleanup()

    def test_audit_is_read_only_before_learning_tables_exist(self):
        report = self.foundation.audit()
        self.assertFalse(report["healthy"])
        self.assertEqual(set(report["missing_tables"]), set(LEARNING_TABLES))
        with self.db.connection() as conn:
            present = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        self.assertTrue(set(LEARNING_TABLES).isdisjoint(present))

    def test_initialize_registers_research_only_foundation(self):
        self.foundation.initialize()
        self.assertEqual(self.foundation.definition()["authority"], RESEARCH_AUTHORITY)
        self.assertFalse(self.foundation.definition()["automatic_execution_promotion"])
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT foundation_version,definition_hash FROM learning_foundations"
            ).fetchone()
        self.assertEqual(row, (FOUNDATION_VERSION, self.foundation.definition_hash))
        self.assertTrue(self.foundation.audit()["healthy"])

    def test_model_and_challenger_registry_can_never_claim_execution_authority(self):
        self.foundation.register_model(
            model_version="MODEL-1",
            model_family="RIDGE",
            selector_version="RIDGE_EXPECTED_NET_R_V1",
            model_digest="m" * 64,
            training_data_digest="d" * 64,
            metadata={"purpose": "research"},
        )
        self.foundation.register_challenger(
            challenger_version="CHALLENGER-1",
            model_version="MODEL-1",
        )
        with self.db.connection() as conn:
            model = conn.execute(
                "SELECT authority,status FROM model_registry WHERE model_version='MODEL-1'"
            ).fetchone()
            challenger = conn.execute(
                "SELECT authority,status FROM challenger_registry WHERE challenger_version='CHALLENGER-1'"
            ).fetchone()
        self.assertEqual(model, (RESEARCH_AUTHORITY, "REGISTERED"))
        self.assertEqual(challenger, (RESEARCH_AUTHORITY, "REGISTERED"))

    def test_training_evaluation_drift_and_rollback_ledgers_are_durable(self):
        for version in ("MODEL-A", "MODEL-B"):
            self.foundation.register_model(
                model_version=version,
                model_family="RIDGE",
                model_digest=("a" if version.endswith("A") else "b") * 64,
                training_data_digest="d" * 64,
            )
        self.foundation.register_challenger(
            challenger_version="CHALLENGER-A",
            model_version="MODEL-A",
        )
        self.foundation.record_training_job(
            job_id="TRAIN-1",
            state="SUCCEEDED",
            source_digest="s" * 64,
            challenger_version="CHALLENGER-A",
            training_cutoff_event_ms=123,
            output_model_version="MODEL-A",
            requested_at_ms=10,
            started_at_ms=11,
            completed_at_ms=12,
        )
        evaluation_digest = self.foundation.record_evaluation(
            evaluation_id="EVAL-1",
            challenger_version="CHALLENGER-A",
            evaluator_version="WALK_FORWARD_CHAMPION_V1",
            status="REJECT_RESEARCH_GATE",
            source_digest="e" * 64,
            detail={"reason": "gate"},
            evaluated_at_ms=20,
        )
        drift_digest = self.foundation.record_drift_report(
            report_id="DRIFT-1",
            model_version="MODEL-A",
            window_start_ms=100,
            window_end_ms=200,
            source_digest="r" * 64,
            report={"psi": 0.1},
            recorded_at_ms=30,
        )
        self.foundation.record_rollback(
            rollback_id="ROLLBACK-1",
            from_model_version="MODEL-A",
            to_model_version="MODEL-B",
            reason="research rollback record",
            source_digest="z" * 64,
            recorded_at_ms=40,
        )
        self.assertEqual(len(evaluation_digest), 64)
        self.assertEqual(len(drift_digest), 64)
        status = self.foundation.status()
        self.assertEqual(
            (status.models, status.challengers, status.training_jobs, status.evaluations, status.drift_reports, status.rollback_records),
            (2, 1, 1, 1, 1, 1),
        )
        self.assertTrue(self.foundation.audit()["healthy"])

    def test_duplicate_identity_cannot_be_redefined(self):
        self.foundation.register_model(
            model_version="MODEL-1",
            model_family="RIDGE",
            model_digest="a" * 64,
            training_data_digest="d" * 64,
        )
        with self.assertRaisesRegex(RuntimeError, "MODEL_IDENTITY_MISMATCH"):
            self.foundation.register_model(
                model_version="MODEL-1",
                model_family="TREE",
                model_digest="b" * 64,
                training_data_digest="d" * 64,
            )

    def test_invalid_learning_states_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "TRAINING_STATE_INVALID"):
            self.foundation.record_training_job(
                job_id="TRAIN-1",
                state="PROMOTED_TO_EXECUTION",
                source_digest="s" * 64,
            )
        self.foundation.register_model(
            model_version="MODEL-1",
            model_family="RIDGE",
            model_digest="a" * 64,
            training_data_digest="d" * 64,
        )
        with self.assertRaisesRegex(ValueError, "CHALLENGER_MODEL_MISSING"):
            self.foundation.register_challenger(
                challenger_version="CHALLENGER-X",
                model_version="MISSING",
            )


    def test_admin_cli_exposes_research_build_audit_champion_and_learning_commands(self):
        parser = nbot_admin.build_parser()
        cases = (
            (["build", "features", "--max-events", "0"], "build"),
            (["build", "selection"], "build"),
            (["audit", "champion"], "audit"),
            (["audit", "learning"], "audit"),
            (["champion-evaluate"], "champion-evaluate"),
            (["champion-status"], "champion-status"),
            (["learning-init"], "learning-init"),
            (["learning-status"], "learning-status"),
            (["research-audit"], "research-audit"),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(parser.parse_args(argv).command, expected)
        self.assertEqual(nbot_admin.RESEARCH_PROFILE, "live-paper")

    def test_schema_rejects_non_research_authority_even_with_direct_sql(self):
        self.foundation.initialize()
        with self.db.connection() as conn:
            with self.assertRaises(Exception):
                conn.execute(
                    "INSERT INTO model_registry("
                    "model_version,foundation_version,model_family,selector_version,model_digest,training_data_digest,"
                    "created_at_ms,status,authority,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        "BAD",
                        FOUNDATION_VERSION,
                        "RIDGE",
                        None,
                        "a" * 64,
                        "d" * 64,
                        1,
                        "REGISTERED",
                        "LIVE_REAL_CAPITAL",
                        "{}",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
