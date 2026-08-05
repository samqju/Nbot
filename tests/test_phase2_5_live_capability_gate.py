import tempfile
import unittest
from pathlib import Path

from execution.live_trading_guard import LiveTradingGuard


class Adapter:
    READ_ONLY = True


class WritableAdapter:
    READ_ONLY = False


class Phase25LiveCapabilityGateTests(unittest.TestCase):
    def _guard(self, root, **overrides):
        values = {
            "environment": "LIVE",
            "execution_mode": "TRADE",
            "adapter_mode": "READ_ONLY",
            "confirmation": "I_ACCEPT_REAL_MONEY_EXECUTION",
            "writes_requested": False,
            "arm_file": str(Path(root) / "live_trading.arm"),
            "adapter": Adapter(),
        }
        values.update(overrides)
        return LiveTradingGuard(**values)

    def test_read_only_live_context_is_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            report = self._guard(root).validate_read_only()
            self.assertTrue(report.read_only_safe)

    def test_missing_confirmation_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError, "LIVE_GUARD_CONFIRMATION_MISSING"):
                self._guard(root, confirmation="DISABLED").validate_read_only()

    def test_write_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError, "LIVE_GUARD_WRITE_MODE_REJECTED"):
                self._guard(root, adapter_mode="WRITE_ENABLED").validate_read_only()

    def test_write_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError, "LIVE_GUARD_WRITES_REQUESTED"):
                self._guard(root, writes_requested=True).validate_read_only()

    def test_unexpected_writable_adapter_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(
                RuntimeError,
                "LIVE_GUARD_UNEXPECTED_WRITE_CAPABILITY",
            ):
                self._guard(root, adapter=WritableAdapter()).validate_read_only()

    def test_stale_arm_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            arm_file = Path(root) / "live_trading.arm"
            arm_file.write_text("stale")
            with self.assertRaisesRegex(
                RuntimeError,
                "LIVE_GUARD_STALE_ARM_FILE_PRESENT",
            ):
                self._guard(root, arm_file=str(arm_file)).validate_read_only()


if __name__ == "__main__":
    unittest.main()
