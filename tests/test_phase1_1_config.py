import os
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def import_config_with(**overrides):
    env = os.environ.copy()
    # The split Observation Worker supports the STRUCTURE strategy family.
    env["STRATEGY_MODE"] = "STRUCTURE"
    env.update({key: str(value) for key, value in overrides.items()})
    return subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import config; "
                "print(config.TRADING_ENV, config.EXECUTION_MODE, "
                "config.PAPER_STARTING_BALANCE_USD)"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class Phase11ConfigTests(unittest.TestCase):
    def test_live_shadow_configuration_is_valid(self):
        result = import_config_with(
            TRADING_ENV="LIVE",
            EXECUTION_MODE="SHADOW",
            LIVE_TRADING_CONFIRMATION="DISABLED",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LIVE SHADOW", result.stdout)

    def test_testnet_trade_remains_valid(self):
        result = import_config_with(
            TRADING_ENV="TESTNET",
            EXECUTION_MODE="TRADE",
            LIVE_TRADING_CONFIRMATION="DISABLED",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TESTNET TRADE", result.stdout)

    def test_live_trade_is_blocked_without_explicit_confirmation(self):
        result = import_config_with(
            TRADING_ENV="LIVE",
            EXECUTION_MODE="TRADE",
            LIVE_TRADING_CONFIRMATION="DISABLED",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LIVE_TRADING_NOT_CONFIRMED", result.stderr)

    def test_invalid_paper_balance_is_rejected(self):
        result = import_config_with(
            TRADING_ENV="LIVE",
            EXECUTION_MODE="SHADOW",
            PAPER_STARTING_BALANCE_USD="0",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAPER_STARTING_BALANCE_USD", result.stderr)

    def test_paper_state_and_trade_paths_must_differ(self):
        result = import_config_with(
            TRADING_ENV="LIVE",
            EXECUTION_MODE="SHADOW",
            PAPER_STATE_PATH="data/paper.json",
            PAPER_TRADES_PATH="data/paper.json",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAPER_PATHS_MUST_DIFFER", result.stderr)


if __name__ == "__main__":
    unittest.main()
