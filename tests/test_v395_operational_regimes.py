from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import nbot_admin
from nbot.observation.operational_regimes import (
    CONTRACT_KEY,
    REQUIREMENTS,
    OperationalRegimeLedger,
)
from nbot.observation.research_memory import ResearchMemoryStore


class V395OperationalRegimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.memory = ResearchMemoryStore(Path(self.tmp.name) / "research_memory.db")
        self.memory.initialize(generation="TEST_V395", generation_floor_ms=0)
        self.ledger = OperationalRegimeLedger(self.memory)

    def tearDown(self):
        self.tmp.cleanup()

    def test_contract_has_exact_ten_roadmap_regimes_and_no_authority(self):
        contract = self.ledger.contract()
        self.assertEqual(contract["requirement_count"], 10)
        self.assertEqual(len(REQUIREMENTS), 10)
        self.assertFalse(contract["automatic_promotion"])
        self.assertFalse(contract["paper_champion_authority"])
        self.assertEqual(contract["execution_authority"], "NONE")
        self.assertEqual({r["regime_id"] for r in contract["requirements"]}, {
            "OBSERVATION_RESTART", "EXECUTION_RESTART", "NETWORK_INTERRUPTION",
            "PUBLIC_FEED_RECOVERY", "LARGE_DB_GROWTH", "HEAVY_TRAINING_CPU",
            "DISK_PRESSURE_ALERT", "MODEL_PROMOTION", "MODEL_ROLLBACK",
            "OPERATOR_TELEGRAM_FAILURE",
        })

    def test_sync_is_immutable_and_status_does_not_claim_full_pass(self):
        first = self.ledger.sync()
        second = self.ledger.sync()
        self.assertEqual(first["contract_artifact_digest"], second["contract_artifact_digest"])
        self.assertIsNotNone(self.memory.artifact(CONTRACT_KEY))
        status = self.ledger.status()
        self.assertEqual(status["requirement_count"], 10)
        self.assertEqual(status["accepted_evidence_count"], 6)
        self.assertEqual(status["deterministic_equivalent_count"], 2)
        self.assertEqual(status["deferred_authority_count"], 2)
        self.assertFalse(status["all_required_operational_regimes_proven"])
        self.assertFalse(status["automatic_promotion"])
        self.assertFalse(status["paper_champion_authority"])
        self.assertEqual(status["execution_authority"], "NONE")

    def test_promotion_and_rollback_are_explicitly_deferred(self):
        self.ledger.sync()
        status = self.ledger.status()
        self.assertEqual(set(status["deferred_regimes"]), {"MODEL_PROMOTION", "MODEL_ROLLBACK"})
        rows = {r["regime_id"]: r for r in status["requirements"]}
        self.assertEqual(rows["MODEL_PROMOTION"]["status"], "NOT_YET_APPLICABLE")
        self.assertEqual(rows["MODEL_ROLLBACK"]["status"], "NOT_YET_APPLICABLE")

    def test_audit_requires_initialized_exact_contract(self):
        self.assertFalse(self.ledger.audit()["healthy"])
        self.ledger.sync()
        audit = self.ledger.audit()
        self.assertTrue(audit["healthy"])
        self.assertEqual(audit["authority_violation"], 0)
        self.assertEqual(audit["premature_operational_pass"], 0)

    def test_admin_parser_exposes_v395_commands(self):
        parser = nbot_admin.build_parser()
        for command in (
            "operational-regime-sync",
            "operational-regime-status",
            "operational-regime-audit",
        ):
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command]).command, command)


if __name__ == "__main__":
    unittest.main()
