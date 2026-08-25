from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import nbot_admin
from nbot.observation.challengers import CHALLENGER_PREFIX, EVALUATION_PREFIX
from nbot.observation.governance import (
    CHALLENGER_REGISTRY_PREFIX,
    MODEL_REGISTRY_PREFIX,
    ModelGovernanceRegistry,
)
from nbot.observation.operational_regimes import OperationalRegimeLedger
from nbot.observation.paper_champion import PaperChampionGate
from nbot.observation.research_champion import (
    CONFIRMATION,
    CONTRACT_KEY,
    PROMOTION_PREFIX,
    ResearchChampionPromotion,
)
from nbot.observation.research_memory import ResearchMemoryStore


class _Config:
    eligibility_version = "V39_RESEARCH_CHAMPION_ELIGIBILITY_V1"
    min_consecutive_pass_windows = 3


class _FakeGovernance:
    def __init__(self, eligibility):
        self.config = _Config()
        self.eligibility = eligibility
        self.sync_calls = 0

    def sync(self):
        self.sync_calls += 1
        return {"eligibility": self.eligibility}

    def status(self):
        return {"research_champion_eligibility": self.eligibility}


class V396BResearchChampionPromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.memory = ResearchMemoryStore(root / "research_memory.db")
        self.memory.initialize(generation="TEST_V396B", generation_floor_ms=0)
        self.real_governance = ModelGovernanceRegistry(self.memory, root / "models")
        pointer, rollback = self.real_governance._genesis_records()
        from nbot.observation.governance import CHAMPION_POINTER_GENESIS_KEY, ROLLBACK_STATE_GENESIS_KEY
        self.memory.persist_artifact(CHAMPION_POINTER_GENESIS_KEY, pointer)
        self.memory.persist_artifact(ROLLBACK_STATE_GENESIS_KEY, rollback)

    def tearDown(self):
        self.tmp.cleanup()

    def _eligibility(self, eligible=True):
        gates = {"synthetic_frozen_gate": bool(eligible)}
        return {
            "eligibility_version": "V39_RESEARCH_CHAMPION_ELIGIBILITY_V1",
            "window_basis": ["C1", "C2", "C3"],
            "gates": gates,
            "eligible_for_research_champion_review": bool(eligible),
            "decision": "ELIGIBLE_FOR_RESEARCH_CHAMPION_REVIEW" if eligible else "NOT_YET_ELIGIBLE",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        }

    def _install_candidate(self):
        self.memory.persist_artifact(CHALLENGER_PREFIX + "C3", {
            "challenger_version": "C3",
            "challenger_family": "RIDGE_POSITIVE_EXPECTANCY_ABSTAIN_V1",
            "model_version": "M3",
            "training_cutoff_event_ms": 3000,
        })
        self.memory.persist_artifact(EVALUATION_PREFIX + "C3", {
            "challenger_version": "C3",
            "model_version": "M3",
            "status": "PASS_RESEARCH_GATE",
            "evaluation_digest": "EVAL3",
        })
        self.memory.persist_artifact(MODEL_REGISTRY_PREFIX + "M3", {
            "registry_version": "V39_MODEL_REGISTRY_V1",
            "record_type": "MODEL",
            "model_version": "M3",
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        })
        self.memory.persist_artifact(CHALLENGER_REGISTRY_PREFIX + "C3", {
            "registry_version": "V39_MODEL_REGISTRY_V1",
            "record_type": "CHALLENGER",
            "challenger_version": "C3",
            "model_version": "M3",
            "training_cutoff_event_ms": 3000,
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
        })

    def test_contract_and_review_are_fail_closed_without_eligibility(self):
        promotion = ResearchChampionPromotion(self.memory, _FakeGovernance(self._eligibility(False)))
        promotion.sync()
        review = promotion.review()
        self.assertEqual(review["decision"], "WAIT_FOR_FROZEN_RESEARCH_ELIGIBILITY")
        self.assertIsNone(review["candidate"])
        self.assertFalse(review["automatic_promotion"])
        self.assertFalse(review["paper_champion_authority"])
        self.assertEqual(review["execution_authority"], "NONE")
        self.assertIsNotNone(self.memory.artifact(CONTRACT_KEY))

    def test_promotion_requires_explicit_confirmation(self):
        self._install_candidate()
        promotion = ResearchChampionPromotion(self.memory, _FakeGovernance(self._eligibility(True)))
        with self.assertRaisesRegex(ValueError, "CONFIRMATION_REQUIRED"):
            promotion.promote(confirm="NO")
        self.assertEqual(self.memory.list_artifacts(prefix=PROMOTION_PREFIX), [])

    def test_eligible_first_champion_promotes_once_without_paper_or_execution_authority(self):
        self._install_candidate()
        fake = _FakeGovernance(self._eligibility(True))
        promotion = ResearchChampionPromotion(self.memory, fake)
        result = promotion.promote(confirm=CONFIRMATION)
        self.assertEqual(result["result"], "RESEARCH_CHAMPION_PROMOTED")
        self.assertEqual(result["model_version"], "M3")
        self.assertFalse(result["paper_champion_authority"])
        self.assertEqual(result["execution_authority"], "NONE")
        self.assertEqual(fake.sync_calls, 1)

        review = promotion.review()
        self.assertEqual(review["current_research_champion"], "M3")
        self.assertEqual(review["decision"], "RESEARCH_CHAMPION_ALREADY_ACTIVE")
        self.assertEqual(len(self.memory.list_artifacts(prefix=PROMOTION_PREFIX)), 1)

        again = promotion.promote(confirm=CONFIRMATION)
        self.assertEqual(again["result"], "ALREADY_PROMOTED")
        self.assertEqual(len(self.memory.list_artifacts(prefix=PROMOTION_PREFIX)), 1)
        self.assertTrue(promotion.audit()["healthy"])

    def test_latest_pointer_is_visible_to_governance_paper_gate_and_operational_ledger(self):
        self._install_candidate()
        promotion = ResearchChampionPromotion(self.memory, _FakeGovernance(self._eligibility(True)))
        promotion.promote(confirm=CONFIRMATION)

        governance_status = self.real_governance.status()
        self.assertEqual(governance_status["champion_pointer"]["current_research_champion"], "M3")
        self.assertFalse(governance_status["champion_pointer"]["paper_champion_authority"])
        self.assertEqual(governance_status["execution_authority"], "NONE")

        paper = PaperChampionGate(self.memory)
        paper.sync()
        paper_status = paper.status()
        self.assertEqual(paper_status["research_champion"], "M3")
        self.assertEqual(paper_status["decision"], "READY_TO_BEGIN_CONTROLLED_LIVE_PAPER_EVIDENCE")
        self.assertEqual(paper_status["paper_evidence_counted"], 0)
        self.assertFalse(paper_status["paper_champion_authority"])

        ledger = OperationalRegimeLedger(self.memory)
        ledger.sync()
        status = ledger.status()
        self.assertIn("MODEL_PROMOTION", status["accepted_regimes"])
        self.assertNotIn("MODEL_PROMOTION", status["deferred_regimes"])
        self.assertIn("MODEL_ROLLBACK", status["deferred_regimes"])
        self.assertFalse(status["all_required_operational_regimes_proven"])

    def test_admin_parser_exposes_v396b_commands(self):
        parser = nbot_admin.build_parser()
        for command in (
            "research-champion-sync",
            "research-champion-review",
            "research-champion-audit",
        ):
            with self.subTest(command=command):
                self.assertEqual(parser.parse_args([command]).command, command)
        args = parser.parse_args([
            "research-champion-promote",
            "--confirm",
            CONFIRMATION,
        ])
        self.assertEqual(args.command, "research-champion-promote")
        self.assertEqual(args.confirm, CONFIRMATION)


if __name__ == "__main__":
    unittest.main()
