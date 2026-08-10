import json
import tempfile
import unittest
from pathlib import Path

from utils.process_lock import BotAlreadyRunningError, SingleInstanceLock


class Phase54BSingleInstanceLockTests(unittest.TestCase):
    def test_second_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.lock"
            first = SingleInstanceLock(str(path))
            second = SingleInstanceLock(str(path))
            first.acquire(environment="LIVE", execution_mode="SHADOW")
            try:
                with self.assertRaises(BotAlreadyRunningError) as ctx:
                    second.acquire(environment="LIVE", execution_mode="SHADOW")
                self.assertIn("BOT_ALREADY_RUNNING", str(ctx.exception))
            finally:
                first.release()

    def test_release_allows_next_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot.lock"
            first = SingleInstanceLock(str(path))
            first.acquire(environment="LIVE", execution_mode="SHADOW")
            first.release()

            second = SingleInstanceLock(str(path))
            second.acquire(environment="TESTNET", execution_mode="TRADE")
            try:
                metadata = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(metadata["environment"], "TESTNET")
                self.assertEqual(metadata["execution_mode"], "TRADE")
            finally:
                second.release()

    def test_split_entrypoints_release_role_locks_in_finally(self):
        for filename, release_marker in (
            ("run_execution.py", "EXECUTION_INSTANCE_LOCK_RELEASED"),
            ("run_observation.py", "OBSERVATION_INSTANCE_LOCK_RELEASED"),
        ):
            with self.subTest(filename=filename):
                source = Path(filename).read_text(encoding="utf-8")
                self.assertIn("lock.acquire", source)
                self.assertIn("finally:", source)
                self.assertIn("lock.release()", source)
                self.assertIn(release_marker, source)


if __name__ == "__main__":
    unittest.main()
