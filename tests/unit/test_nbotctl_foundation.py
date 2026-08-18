from pathlib import Path
import subprocess
import unittest


class NbotctlFoundationTests(unittest.TestCase):
    def test_bootstrap_command_is_exposed_without_mutating_runtime(self):
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [str(repo / "nbotctl"), "bootstrap", "--help"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: nbotctl bootstrap", result.stdout)


if __name__ == "__main__":
    unittest.main()
