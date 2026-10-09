from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]


class V39PreV310CleanupTests(unittest.TestCase):
    def test_nbotctl_reports_current_economic_wait_without_numbered_phase_claim(self):
        result = subprocess.run(
            [str(REPO / "nbotctl"), "status"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["phase"], "V3")
        self.assertEqual(
            payload["phase_status"],
            "CURRENT_RESEARCH_BUILD_ECONOMIC_WAIT",
        )
        self.assertEqual(payload["phase_gate_status"], "ECONOMIC_WAIT")
        self.assertEqual(payload["next_phase"], "EVIDENCE_GATED_PROMOTION")
        self.assertEqual(
            payload["deferred_acceptance"],
            ["RESEARCH_CHAMPION", "PAPER_CHAMPION", "ECONOMIC_PROOF"],
        )

    def test_current_docs_are_version_neutral_and_history_remains(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        operations = (REPO / "docs/OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("Current V3 research state", readme)
        self.assertIn("Economic proof:** **NOT PASSED", readme)
        self.assertIn("V3.7 is historically **OPERATIONALLY PROVEN**", readme)
        self.assertIn(
            "NBOT V3 RESEARCH BUILD / ECONOMIC EVIDENCE ACCUMULATING",
            operations,
        )
        self.assertIn("V3.7-A Normal LONG is physically proven", operations)
        self.assertNotIn(
            "Current checkpoint: `V3.7 OPERATIONALLY PROVEN -> V3.8`",
            operations,
        )

    def test_evidence_lineage_contract_is_not_placeholder(self):
        text = (REPO / "docs/EVIDENCE_LINEAGE_CONTRACT.md").read_text(encoding="utf-8")
        self.assertNotIn("Status: V3.0 placeholder", text)
        for token in (
            "Canonical LIVE raw evidence",
            "TESTNET lineage",
            "LIVE_PAPER lineage",
            "96-event epochs",
            "generation floor",
            "Decision-time versus future evidence",
            "After-cost economics",
            "Research Champion lineage",
            "Paper Champion lineage",
            "ExecutionProposal / ExecutionOutcome lineage",
            "LIVE_REAL_CAPITAL boundary",
        ):
            self.assertIn(token, text)

    def test_generated_source_snapshots_are_ignored(self):
        text = (REPO / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("NBOT_CURRENT_FULLSOURCE_*.txt", text)

    def test_active_service_descriptions_are_not_v38_phase_labels(self):
        files = (
            "nbot-observation-live-paper-control.service.in",
            "nbot-execution-live-paper.service.in",
            "nbot-control-tunnel-live-paper.service.in",
            "nbot-research-epoch.timer.in",
            "nbot-research-epoch.service.in",
        )
        for name in files:
            text = (REPO / "deploy/systemd" / name).read_text(encoding="utf-8")
            self.assertNotIn("NBOT V3.8", text, name)

    def test_gap_ledger_keeps_operator_tooling_open(self):
        text = (REPO / "docs/PRE_V310_GAP_LEDGER.md").read_text(encoding="utf-8")
        self.assertIn("[x] Integrate real Observation database integrity", text)
        self.assertIn("[x] Integrate local protocol/profile contract validation", text)
        self.assertIn("[x] Implement `nbotctl cluster doctor/start/stop/status`", text)
        self.assertIn("V3.10 remains hard-blocked", text)


if __name__ == "__main__":
    unittest.main()
