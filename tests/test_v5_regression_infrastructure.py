"""Check clean progress for successful suite, diagnostic preservation on failure."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from deploy.observation.check_v5_roadmap import ROADMAP, check_paths


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "deploy" / "observation" / "run_quiet_regression.py"


class V5RoadmapGateTests(unittest.TestCase):
    def test_v5_change_requires_roadmap_diff(self):
        self.assertEqual(check_paths(["nbot/observation/v5_accounting.py"])[0], False)
        self.assertTrue(check_paths(["nbot/observation/v5_accounting.py", ROADMAP])[0])
        self.assertTrue(check_paths(["tests/test_v4_policy.py"])[0])

    def test_master_roadmap_exists_and_contains_milestone_gates(self):
        source = (ROOT / ROADMAP).read_text()
        for entry in ("PR #30", "Milestone 1", "Milestone 2", "Decision log",
                      "Cutover", "Forward", "No order authority"):
            self.assertIn(entry, source)


class QuietRegressionRunnerTests(unittest.TestCase):
    @staticmethod
    def _run_fixture(*, fail: bool):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "test_example.py"
            fixture.write_text(
                "import os, sys, unittest\n"
                "print('NOISY_MODULE_IMPORT')\n"
                "class Demo(unittest.TestCase):\n"
                "    def test_example(self):\n"
                "        print('NOISY_STDOUT')\n"
                "        print('NOISY_STDERR', file=sys.stderr)\n"
                "        os.write(1, b'NOISY_RAW_FD\\n')\n"
                + ("        self.fail('EXPECTED_FAILURE')\n" if fail else
                   "        self.assertTrue(True)\n")
            )
            return subprocess.run(
                [sys.executable, str(RUNNER), "--start-directory", directory],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )

    def test_pass_run_has_only_dots_and_unittest_summary(self):
        result = self._run_fixture(fail=False)
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("Ran 1 test", combined)
        self.assertIn("OK", combined)
        for item in ("NOISY_MODULE_IMPORT", "NOISY_STDOUT",
                     "NOISY_STDERR", "NOISY_RAW_FD"):
            self.assertNotIn(item, combined)

    def test_fail_run_retains_failure_trace_and_captured_logs(self):
        result = self._run_fixture(fail=True)
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXPECTED_FAILURE", combined)
        self.assertIn("FAILED", combined)
        for item in ("NOISY_MODULE_IMPORT", "NOISY_STDOUT",
                     "NOISY_STDERR", "NOISY_RAW_FD"):
            self.assertIn(item, combined)


if __name__ == "__main__":
    unittest.main()
