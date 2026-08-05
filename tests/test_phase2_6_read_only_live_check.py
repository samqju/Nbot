import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.safety import live_readonly_check as runner


class Exchange:
    def read_only_account_snapshot(self):
        return {
            "capabilities": {
                "adapter": "LiveExchange",
                "read_only": True,
                "supports_real_orders": False,
                "write_operations": "BLOCKED",
            },
            "available_balance_usdt": 123.45,
            "positions": [],
            "open_orders": [],
            "protective_stops": [],
            "user_stream_healthy": True,
        }

    def reconcile_read_only(self, *, local_position=None, require_safe=False):
        return SimpleNamespace(status="SAFE", issues=())

    def export_live_snapshot(
        self,
        *,
        path,
        reconciliation,
        previous_snapshot=None,
    ):
        return {
            "capabilities": {
                "adapter": "LiveExchange",
                "read_only": True,
                "supports_real_orders": False,
                "write_operations": "BLOCKED",
            },
            "available_balance_usdt": 123.45,
            "positions": [],
            "open_orders": [],
            "protective_stops": [],
            "user_stream_healthy": True,
            "reconciliation": {
                "status": reconciliation.status,
                "issues": list(reconciliation.issues),
            },
            "drift": {
                "status": "BASELINE_CREATED",
                "issues": [],
                "balance_delta_usdt": None,
            },
        }


class Phase26ReadOnlyLiveCheckTests(unittest.TestCase):
    def test_report_contains_only_read_only_account_observation(self):
        report = runner.build_report(Exchange())
        self.assertEqual(report["mode"], "READ_ONLY")
        self.assertEqual(report["real_orders"], "BLOCKED")
        self.assertTrue(report["user_stream_healthy"])
        self.assertEqual(report["reconciliation"]["status"], "SAFE")
        self.assertFalse(report["capabilities"]["supports_real_orders"])

    def test_current_safe_configuration_is_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(runner, "TRADING_ENV", "LIVE"), patch.object(
                runner, "LIVE_ADAPTER_MODE", "READ_ONLY"
            ), patch.object(
                runner, "LIVE_ORDER_WRITES_ENABLED", False
            ), patch.object(
                runner,
                "LIVE_TRADING_ARM_FILE",
                str(Path(root) / "live_trading.arm"),
            ):
                runner._validate_runner_safety()

    def test_non_live_environment_is_rejected(self):
        with patch.object(runner, "TRADING_ENV", "TESTNET"):
            with self.assertRaisesRegex(
                RuntimeError,
                "LIVE_READ_ONLY_CHECK_ENVIRONMENT_INVALID",
            ):
                runner._validate_runner_safety()

    def test_write_mode_is_rejected(self):
        with patch.object(runner, "TRADING_ENV", "LIVE"), patch.object(
            runner, "LIVE_ADAPTER_MODE", "WRITE_ENABLED"
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "LIVE_READ_ONLY_CHECK_ADAPTER_MODE_INVALID",
            ):
                runner._validate_runner_safety()

    def test_write_request_is_rejected(self):
        with patch.object(runner, "TRADING_ENV", "LIVE"), patch.object(
            runner, "LIVE_ADAPTER_MODE", "READ_ONLY"
        ), patch.object(runner, "LIVE_ORDER_WRITES_ENABLED", True):
            with self.assertRaisesRegex(
                RuntimeError,
                "LIVE_READ_ONLY_CHECK_WRITES_REQUESTED",
            ):
                runner._validate_runner_safety()

    def test_arm_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            arm_file = Path(root) / "live_trading.arm"
            arm_file.write_text("stale")
            with patch.object(runner, "TRADING_ENV", "LIVE"), patch.object(
                runner, "LIVE_ADAPTER_MODE", "READ_ONLY"
            ), patch.object(
                runner, "LIVE_ORDER_WRITES_ENABLED", False
            ), patch.object(
                runner, "LIVE_TRADING_ARM_FILE", str(arm_file)
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "LIVE_READ_ONLY_CHECK_ARM_FILE_PRESENT",
                ):
                    runner._validate_runner_safety()


if __name__ == "__main__":
    unittest.main()
