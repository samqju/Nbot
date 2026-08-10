import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Phase53BRuntimeLoggingCleanupTests(unittest.TestCase):
    def test_split_role_entrypoints_replace_legacy_runtime(self):
        execution = (ROOT / "run_execution.py").read_text(encoding="utf-8")
        observation = (ROOT / "run_observation.py").read_text(encoding="utf-8")

        self.assertIn("ExecutionWorker", execution)
        self.assertIn("ObservationWorker", observation)
        self.assertFalse((ROOT / "run.py").exists())
        self.assertFalse((ROOT / "runtime_runner.py").exists())
        self.assertFalse((ROOT / "engine/core.py").exists())

    def test_high_frequency_success_events_are_debug_only(self):
        universe = (ROOT / "engine/universe.py").read_text(encoding="utf-8")
        observations = (
            ROOT / "strategy/candidate_observer.py"
        ).read_text(encoding="utf-8")
        outcomes = (
            ROOT / "strategy/candidate_outcome.py"
        ).read_text(encoding="utf-8")

        self.assertIn("SYMBOL_WARMUP_READY", universe)
        self.assertIn("UNIVERSE_RELOAD_NO_CHANGE", universe)
        self.assertIn("CANDIDATE_OBSERVATION_WRITTEN", observations)
        self.assertIn("CANDIDATE_OUTCOME_WRITTEN", outcomes)

        self.assertIn('"debug"', universe)
        self.assertIn('"debug"', observations)
        self.assertIn('"debug"', outcomes)

    def test_log_level_can_be_enabled_for_diagnostics(self):
        env = os.environ.copy()
        env["BOT_LOG_LEVEL"] = "DEBUG"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from utils.logger import system_logger; "
                    "import logging; "
                    "print(system_logger().level == logging.DEBUG)"
                ),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
