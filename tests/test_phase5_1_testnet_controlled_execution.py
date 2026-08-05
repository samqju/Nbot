import tempfile
import unittest
from pathlib import Path

from execution.testnet_trading_guard import TestnetTradingGuard
from execution.exceptions import EntryValidationError


class Exchange:
    def __init__(self, position=None):
        self.position = position

    def get_position(self):
        return self.position


class Phase51ControlledTestnetTests(unittest.TestCase):
    def _guard(self, root, **overrides):
        arm = Path(root) / "arm"
        arm.write_text("ARM_TESTNET_TRADING")
        values = {
            "confirmation": "I_ACCEPT_TESTNET_ORDER_EXECUTION",
            "arm_file": str(arm),
            "max_session_entries": 2,
            "max_entry_notional_usd": 1000,
            "require_flat_start": True,
        }
        values.update(overrides)
        return TestnetTradingGuard(**values)

    def test_valid_gate_arms_and_authorizes_entry(self):
        with tempfile.TemporaryDirectory() as root:
            guard = self._guard(root)
            report = guard.validate_startup(Exchange())
            authorization = guard.authorize_entry(
                symbol="BTCUSDT",
                qty=0.01,
                reference_price=50000,
                current_position=None,
            )
            self.assertEqual(report["status"], "ARMED")
            self.assertTrue(authorization["authorized"])
            self.assertEqual(
                authorization["notional_usd"],
                500,
            )

    def test_confirmation_is_required(self):
        with tempfile.TemporaryDirectory() as root:
            guard = self._guard(
                root,
                confirmation="DISABLED",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TESTNET_TRADING_NOT_CONFIRMED",
            ):
                guard.validate_startup(Exchange())

    def test_arm_file_is_required(self):
        with tempfile.TemporaryDirectory() as root:
            guard = self._guard(root)
            guard.arm_file.unlink()
            with self.assertRaisesRegex(
                RuntimeError,
                "TESTNET_TRADING_ARM_FILE_MISSING",
            ):
                guard.validate_startup(Exchange())

    def test_flat_start_is_required(self):
        with tempfile.TemporaryDirectory() as root:
            guard = self._guard(root)
            with self.assertRaisesRegex(
                RuntimeError,
                "TESTNET_START_REQUIRES_FLAT_ACCOUNT",
            ):
                guard.validate_startup(
                    Exchange(position=object())
                )

    def test_notional_limit_blocks_entry(self):
        with tempfile.TemporaryDirectory() as root:
            guard = self._guard(root)
            guard.validate_startup(Exchange())
            with self.assertRaisesRegex(
                EntryValidationError,
                "TESTNET_ENTRY_NOTIONAL_LIMIT_EXCEEDED",
            ):
                guard.authorize_entry(
                    symbol="BTCUSDT",
                    qty=0.03,
                    reference_price=50000,
                    current_position=None,
                )

    def test_session_entry_limit_blocks_additional_entries(self):
        with tempfile.TemporaryDirectory() as root:
            guard = self._guard(
                root,
                max_session_entries=1,
            )
            guard.validate_startup(Exchange())
            guard.authorize_entry(
                symbol="BTCUSDT",
                qty=0.01,
                reference_price=50000,
                current_position=None,
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "TESTNET_SESSION_ENTRY_LIMIT_REACHED",
            ):
                guard.authorize_entry(
                    symbol="ETHUSDT",
                    qty=0.1,
                    reference_price=3000,
                    current_position=None,
                )


if __name__ == "__main__":
    unittest.main()
