import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def config_values(environment):
    env = os.environ.copy()
    env.update({
        "TRADING_ENV": environment,
        "EXECUTION_MODE": "SHADOW",
        "LIVE_BASE_URL": "https://live.example",
        "TESTNET_BASE_URL": "https://testnet.example",
    })
    for name in (
        "STRUCTURE_UNIVERSE_MARKET_BASE_URL",
        "OBSERVATION_UNIVERSE_MARKET_BASE_URL",
        "TESTNET_UNIVERSE_MARKET_BASE_URL",
        "LIVE_UNIVERSE_MARKET_BASE_URL",
        "TESTNET_OBSERVATION_UNIVERSE_MARKET_BASE_URL",
        "LIVE_OBSERVATION_UNIVERSE_MARKET_BASE_URL",
        "TESTNET_UNIVERSE_SNAPSHOT_PATH",
        "LIVE_UNIVERSE_SNAPSHOT_PATH",
        "TESTNET_OBSERVATION_UNIVERSE_SNAPSHOT_PATH",
        "LIVE_OBSERVATION_UNIVERSE_SNAPSHOT_PATH",
    ):
        env.pop(name, None)
    code = (
        "import config; "
        "print(config.STRUCTURE_UNIVERSE_MARKET_BASE_URL); "
        "print(config.OBSERVATION_UNIVERSE_MARKET_BASE_URL); "
        "print(config.UNIVERSE_SNAPSHOT_PATH); "
        "print(config.OBSERVATION_UNIVERSE_SNAPSHOT_PATH)"
    )
    return subprocess.run(
        [sys.executable, "-c", code], cwd=PROJECT_ROOT, env=env,
        capture_output=True, text=True, check=False,
    )


class EnvironmentUniverseTests(unittest.TestCase):
    def test_testnet_is_isolated(self):
        result = config_values("TESTNET")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), [
            "https://testnet.example",
            "https://testnet.example",
            "data/universe_testnet.json",
            "data/observation_universe_testnet.json",
        ])

    def test_live_is_isolated(self):
        result = config_values("LIVE")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), [
            "https://live.example",
            "https://live.example",
            "data/universe_live.json",
            "data/observation_universe_live.json",
        ])


if __name__ == "__main__":
    unittest.main()
