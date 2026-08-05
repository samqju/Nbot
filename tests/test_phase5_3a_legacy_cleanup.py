import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def config_paths(environment):
    env = os.environ.copy()
    base_url = (
        "https://demo-fapi.binance.com"
        if environment == "TESTNET"
        else "https://fapi.binance.com"
    )
    env.update({
        "TRADING_ENV": environment,
        "EXECUTION_MODE": "SHADOW",
        "STRATEGY_MODE": "STRUCTURE",
        f"{environment}_UNIVERSE_MARKET_BASE_URL": base_url,
        f"{environment}_OBSERVATION_UNIVERSE_MARKET_BASE_URL": base_url,
    })
    env.pop("PAPER_STATE_PATH", None)
    env.pop("PAPER_TRADES_PATH", None)
    result = subprocess.run(
        [sys.executable, "-c", "import config; print(config.PAPER_STATE_PATH); print(config.PAPER_TRADES_PATH)"],
        cwd=ROOT, env=env, text=True, capture_output=True,
    )
    return result


class Phase53ALegacyCleanupTests(unittest.TestCase):
    def test_testnet_shadow_uses_testnet_paper_paths(self):
        result = config_paths("TESTNET")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), [
            "data/paper_state_testnet.json",
            "data/paper_trades_testnet.jsonl",
        ])

    def test_live_shadow_uses_live_paper_paths(self):
        result = config_paths("LIVE")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), [
            "data/paper_state_live.json",
            "data/paper_trades_live.jsonl",
        ])

    def test_legacy_learning_path_is_removed(self):
        self.assertFalse((ROOT / "train_model.py").exists())
        joined = "\n".join((ROOT / path).read_text() for path in [
            "config.py",
            "engine/position_lifecycle.py",
            "strategy/strategy.py",
        ])
        for forbidden in ("TRADE_DATASET_PATH", "edge_model.pkl", "record_observation", "from train_model"):
            self.assertNotIn(forbidden, joined)


if __name__ == "__main__":
    unittest.main()
