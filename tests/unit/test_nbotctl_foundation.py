from pathlib import Path
import os
import subprocess
import tempfile
import unittest


class NbotctlFoundationTests(unittest.TestCase):
    def test_live_paper_doctor_passes_for_observation_without_secrets(self):
        repo = Path(__file__).resolve().parents[2]
        role_file = repo / ".nbot-role"
        previous = role_file.read_bytes() if role_file.exists() else None
        try:
            role_file.write_text("OBSERVATION\n", encoding="utf-8")
            env = dict(os.environ)
            for key in list(env):
                if "BINANCE" in key and "SECRET" in key:
                    env.pop(key, None)
            result = subprocess.run(
                [str(repo / "nbotctl"), "doctor", "live-paper"],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"status": "PASS"', result.stdout)
            self.assertIn('"role": "OBSERVATION"', result.stdout)
        finally:
            if previous is None:
                role_file.unlink(missing_ok=True)
            else:
                role_file.write_bytes(previous)


if __name__ == "__main__":
    unittest.main()
