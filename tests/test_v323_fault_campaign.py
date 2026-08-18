from __future__ import annotations

import unittest
from pathlib import Path

from nbot.execution.fault_campaign import (
    V3_2_FAULT_REQUIREMENTS,
    fault_campaign_summary,
    validate_fault_campaign_registry,
)

REPO = Path(__file__).resolve().parents[1]


class V323FaultCampaignRegistryTests(unittest.TestCase):
    def test_registry_has_exact_canonical_entry_stop_emergency_counts(self):
        validate_fault_campaign_registry()
        summary = fault_campaign_summary()
        self.assertEqual(summary["scenario_count"], 20)
        self.assertEqual(summary["category_counts"], {"ENTRY": 10, "STOP": 7, "EMERGENCY": 3})
        self.assertFalse(summary["runtime_fault_injection"])
        self.assertFalse(summary["research_evidence"])
        self.assertEqual(summary["authority"], "TESTNET_MECHANICAL_ONLY")

    def test_every_registered_equivalent_resolves_to_a_real_unittest(self):
        for requirement in V3_2_FAULT_REQUIREMENTS:
            for test_id in requirement.test_ids:
                with self.subTest(scenario=requirement.scenario_id, test_id=test_id):
                    suite = unittest.defaultTestLoader.loadTestsFromName(test_id)
                    self.assertEqual(suite.countTestCases(), 1)
                    # Loader failures materialize as _FailedTest; running the
                    # one target makes that visible without running the entire
                    # campaign twice here.
                    result = unittest.TestResult()
                    suite.run(result)
                    self.assertEqual(result.errors, [], msg=str(result.errors))
                    self.assertEqual(result.failures, [], msg=str(result.failures))
                    self.assertEqual(result.unexpectedSuccesses, [])

    def test_restart_sensitive_stop_faults_remain_flagged_for_physical_v324_followup(self):
        physical = set(fault_campaign_summary()["physical_followup_scenarios"])
        self.assertEqual(
            physical,
            {"STOP_MISSING_AFTER_RESTART", "STOP_ORPHAN_AFTER_CLOSE"},
        )
        for requirement in V3_2_FAULT_REQUIREMENTS:
            if requirement.scenario_id in physical:
                self.assertIsNotNone(requirement.physical_followup)

    def test_runtime_has_no_fault_injection_switch(self):
        source = (REPO / "run_execution.py").read_text(encoding="utf-8")
        for forbidden in (
            "--fault-scenario",
            "--inject-fault",
            "--testnet-fault",
            "FAULT_INJECTION_ENABLED",
        ):
            self.assertNotIn(forbidden, source)

    def test_fault_registry_is_execution_only(self):
        source = (REPO / "nbot/execution/fault_campaign.py").read_text(encoding="utf-8")
        for forbidden in (
            "nbot.observation",
            "nbot.learning",
            "nbot.research",
            "nbot.strategy",
            "nbot.universe",
            "nbot.communication",
        ):
            self.assertNotIn(forbidden, source)

    def test_operations_document_explains_deterministic_equivalent_boundary(self):
        text = (REPO / "docs/OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("V3.2.3 deterministic fault-equivalent campaign", text)
        self.assertIn("does not add runtime fault injection", text)
        self.assertIn("**20 canonical", text)
        self.assertIn("entry/stop/emergency fault requirements", text)


if __name__ == "__main__":
    unittest.main()
