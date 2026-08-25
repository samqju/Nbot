from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import nbot_admin
from nbot.observation.governance import ModelGovernanceRegistry
from nbot.observation.market_regimes import CONTRACT_KEY as MARKET_REGIME_CONTRACT_KEY
from nbot.observation.operational_regimes import CONTRACT_KEY as OPERATIONAL_REGIME_CONTRACT_KEY
from nbot.observation.paper_champion import CONFIG, CONTRACT_KEY, PaperChampionGate
from nbot.observation.research_memory import ResearchMemoryStore


class V396PaperChampionGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.memory = ResearchMemoryStore(root / "research_memory.db")
        self.memory.initialize(generation="TEST_V396", generation_floor_ms=0)
        self.governance = ModelGovernanceRegistry(self.memory, root / "model_artifacts")
        self.gate = PaperChampionGate(self.memory)

    def tearDown(self):
        self.tmp.cleanup()

    def _initialize_dependencies(self):
        # Governance cannot create an eligibility epoch without an active challenger
        # in an empty unit-test memory, so install only its safe genesis records.
        pointer, rollback = self.governance._genesis_records()
        from nbot.observation.governance import CHAMPION_POINTER_GENESIS_KEY, ROLLBACK_STATE_GENESIS_KEY
        self.memory.persist_artifact(CHAMPION_POINTER_GENESIS_KEY, pointer)
        self.memory.persist_artifact(ROLLBACK_STATE_GENESIS_KEY, rollback)
        self.memory.persist_artifact(MARKET_REGIME_CONTRACT_KEY, {"version": "TEST_MARKET"})
        self.memory.persist_artifact(OPERATIONAL_REGIME_CONTRACT_KEY, {"version": "TEST_OPERATIONAL"})

    def test_frozen_thresholds_are_conservative_and_authority_free(self):
        c = self.gate.contract()
        t = c["thresholds"]
        self.assertEqual(t["min_completed_paper_trades"], 150)
        self.assertEqual(t["min_independent_market_events"], 100)
        self.assertEqual(t["min_elapsed_days"], 30)
        self.assertEqual(t["min_distinct_utc_dates"], 20)
        self.assertEqual(t["bootstrap_samples"], 2000)
        self.assertEqual(t["confidence_level"], 0.95)
        self.assertEqual(t["max_drawdown_r"], 5.0)
        self.assertEqual(CONFIG.max_mean_operational_degradation_r, 0.10)
        self.assertFalse(c["automatic_promotion"])
        self.assertFalse(c["paper_champion_authority"])
        self.assertEqual(c["execution_authority"], "NONE")

    def test_current_state_waits_for_research_champion(self):
        self._initialize_dependencies()
        self.gate.sync()
        status = self.gate.status()
        self.assertTrue(status["contract_initialized"])
        self.assertIsNone(status["research_champion"])
        self.assertEqual(status["decision"], "WAIT_FOR_RESEARCH_CHAMPION")
        self.assertEqual(status["paper_evidence_counted"], 0)
        self.assertFalse(status["paper_champion_authority"])
        self.assertEqual(status["execution_authority"], "NONE")

    def test_sync_is_immutable_and_audit_rejects_premature_authority(self):
        self._initialize_dependencies()
        a = self.gate.sync()
        b = self.gate.sync()
        self.assertEqual(a["contract_artifact_digest"], b["contract_artifact_digest"])
        self.assertIsNotNone(self.memory.artifact(CONTRACT_KEY))
        audit = self.gate.audit()
        self.assertTrue(audit["healthy"])
        self.assertEqual(audit["premature_paper_champion"], 0)
        self.assertEqual(audit["premature_execution_authority"], 0)
        self.assertEqual(audit["premature_evidence_count"], 0)


    def test_latest_future_research_champion_pointer_is_detectable_without_granting_paper_authority(self):
        self._initialize_dependencies()
        self.memory.persist_artifact(
            "v39:registry:champion-pointer:000001-test",
            {
                "registry_version": "V39_MODEL_REGISTRY_V1",
                "record_type": "CHAMPION_POINTER",
                "generation": 1,
                "current_research_champion": "TEST_RESEARCH_CHAMPION",
                "previous_research_champion": None,
                "automatic_promotion": False,
                "paper_champion_authority": False,
                "execution_authority": "NONE",
                "authority": "RESEARCH_ONLY_NO_EXECUTION",
            },
        )
        self.gate.sync()
        status = self.gate.status()
        self.assertEqual(status["research_champion"], "TEST_RESEARCH_CHAMPION")
        self.assertEqual(status["decision"], "READY_TO_BEGIN_CONTROLLED_LIVE_PAPER_EVIDENCE")
        self.assertEqual(status["paper_evidence_counted"], 0)
        self.assertFalse(status["paper_champion_authority"])
        self.assertEqual(status["execution_authority"], "NONE")

    def test_admin_parser_exposes_v396_commands(self):
        parser = nbot_admin.build_parser()
        for command in (
            "paper-champion-sync",
            "paper-champion-status",
            "paper-champion-audit",
        ):
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command]).command, command)


if __name__ == "__main__":
    unittest.main()
