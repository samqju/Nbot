import json
from pathlib import Path
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]


class V325AcceptanceClosureTests(unittest.TestCase):
    def test_nbotctl_reports_v32_accepted(self):
        result = subprocess.run(
            [str(REPO / "nbotctl"), "status"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["phase"], "V3.2")
        self.assertEqual(payload["active_execution_phase"], "V3.2")

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

    def test_readme_advances_only_to_v32(self):
        text = (REPO / "README.md").read_text()
        self.assertIn(
            "V3.2 EXECUTION TESTNET MECHANICAL — ACCEPTANCE CLOSURE",
            text,
        )
        self.assertIn(
            "Next is V3.3: the independent Observation evidence worker",
            text,
        )
        self.assertIn("`live-trade` remains forbidden until V3.10", text)


if __name__ == "__main__":
    unittest.main()
