import json
from pathlib import Path
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]


class V325AcceptanceClosureTests(unittest.TestCase):
    def test_nbotctl_reports_current_v37_transition_status(self):
        result = subprocess.run(
            [str(REPO / "nbotctl"), "status"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["phase"], "V3.7")
        self.assertEqual(payload["active_execution_phase"], "V3.7")
        self.assertEqual(payload["phase_status"], "V3.7_A_PASS_B_DEFERRED")
        self.assertEqual(payload["phase_gate_status"], "NOT_FULLY_PASSED")
        self.assertEqual(payload["next_phase"], "V3.8")
        self.assertEqual(payload["deferred_acceptance"], ["V3.7-B_NORMAL_SHORT"])

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

    def test_readme_reports_current_v37_to_v38_transition(self):
        text = (REPO / "README.md").read_text()
        self.assertIn("V3.7 -> V3.8 TRANSITION", text)
        self.assertIn("A — Normal LONG: PASS", text)
        self.assertIn("B — Normal SHORT: DEFERRED", text)
        self.assertIn("Next implementation phase: **V3.8 LIVE_PAPER**", text)
        self.assertIn("`live-trade` remains forbidden until V3.10", text)


if __name__ == "__main__":
    unittest.main()
