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

    def test_runtime_runner_releases_lock_in_finally(self):
        source = Path("runtime_runner.py").read_text(encoding="utf-8")
        self.assertIn("instance_lock.acquire", source)
        self.assertIn("finally:", source)
        self.assertIn("instance_lock.release()", source)
        self.assertIn("BOT_INSTANCE_LOCK_RELEASED", source)


if __name__ == "__main__":
    unittest.main()
