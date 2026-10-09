import json
from pathlib import Path
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]


class V325AcceptanceClosureTests(unittest.TestCase):
    def test_nbotctl_reports_current_economic_wait_status(self):
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
        self.assertEqual(payload["active_execution_phase"], "V3")
        self.assertEqual(payload["phase_status"], "CURRENT_RESEARCH_BUILD_ECONOMIC_WAIT")
        self.assertEqual(payload["phase_gate_status"], "ECONOMIC_WAIT")
        self.assertEqual(payload["next_phase"], "EVIDENCE_GATED_PROMOTION")
        self.assertEqual(payload["deferred_acceptance"], ["RESEARCH_CHAMPION", "PAPER_CHAMPION", "ECONOMIC_PROOF"])

    def test_operations_records_offline_stop_deterministic_equivalent(self):
        text = (REPO / "docs/OPERATIONS.md").read_text()
        self.assertIn("## V3.2.5 acceptance closure", text)
        self.assertIn(
            "test_active_breached_stop_settles_during_grace",
            text,
        )
        self.assertIn(
            "test_recover_finished_algo_stop_when_user_trades_missing",
            text,
        )
        self.assertIn(
            "v3.2-execution-testnet-mechanical-proven",
            text,
        )

    def test_readme_preserves_v37_history_and_reports_current_boundary(self):
        text = (REPO / "README.md").read_text()
        self.assertIn("V3.7 is historically **OPERATIONALLY PROVEN**", text)
        self.assertIn("Current V3 research state", text)
        self.assertIn("Economic proof:** **NOT PASSED", text)
        self.assertIn("Historical V3.9/V3.10 milestone names remain only", text)
        self.assertIn("explicit, bounded mainnet trial", text)
        self.assertIn("still-unpassed automatic Champion gates", text)


if __name__ == "__main__":
    unittest.main()
