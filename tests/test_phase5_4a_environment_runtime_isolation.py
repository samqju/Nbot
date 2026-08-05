import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from strategy.candidate_observer import CandidateObservationWriter
from strategy.candidate_outcome import CandidateOutcomeWriter

ROOT = Path(__file__).resolve().parents[1]


def config_values(environment: str):
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
        "LIVE_TRADING_CONFIRMATION": "DISABLED",
        f"{environment}_BASE_URL": base_url,
        f"{environment}_UNIVERSE_MARKET_BASE_URL": base_url,
        f"{environment}_OBSERVATION_UNIVERSE_MARKET_BASE_URL": base_url,
    })
    env.pop("STRUCTURE_UNIVERSE_MARKET_BASE_URL", None)
    env.pop("OBSERVATION_UNIVERSE_MARKET_BASE_URL", None)
    for key in (
        "BOT_STATE_PATH",
        "CANDIDATE_OBSERVATIONS_PATH",
        "CANDIDATE_OUTCOMES_PATH",
        "VIRTUAL_TRADES_PATH",
        "LEARNING_RUNTIME_STATE_PATH",
    ):
        env.pop(key, None)
    code = (
        "import config; print('|'.join([config.BOT_STATE_PATH, "
        "config.CANDIDATE_OBSERVATIONS_PATH, "
        "config.CANDIDATE_OUTCOMES_PATH, config.VIRTUAL_TRADES_PATH, "
        "config.LEARNING_RUNTIME_STATE_PATH]))"
    )
    return subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env,
        text=True, capture_output=True, check=False,
    )


class Candidate:
    observation_id = "obs-1"
    symbol = "BTCUSDT"
    direction = "LONG"
    pattern = "STRUCTURE_5M"
    bucket = 1
    score = 0.5
    score_breakdown = None
    reference_price = 100.0
    risk_plan = None
    structure_fingerprint = "fp"

    class Features:
        @staticmethod
        def as_dict():
            return {
                "short_range": 0.01, "long_range": 0.02,
                "trend_score": 1.0, "wick_ratio_recent": 0.2,
                "body_ratio_recent": 0.8, "range_acceleration": 1.0,
                "dist_high": 0.0, "dist_low": 0.0,
                "directional_consistency": 1,
            }
    features = Features()


class Phase54AEnvironmentRuntimeIsolationTests(unittest.TestCase):
    def test_live_and_testnet_defaults_are_separate(self):
        testnet = config_values("TESTNET")
        live = config_values("LIVE")
        self.assertEqual(testnet.returncode, 0, testnet.stderr)
        self.assertEqual(live.returncode, 0, live.stderr)
        testnet_paths = testnet.stdout.strip().split("|")
        live_paths = live.stdout.strip().split("|")
        self.assertEqual(len(testnet_paths), 5)
        self.assertEqual(len(live_paths), 5)
        self.assertTrue(all("testnet" in path for path in testnet_paths))
        self.assertTrue(all("live" in path for path in live_paths))
        self.assertTrue(set(testnet_paths).isdisjoint(live_paths))

    def test_observation_and_outcome_records_are_tagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observations = root / "observations.jsonl"
            outcomes = root / "outcomes.jsonl"
            CandidateObservationWriter(
                str(observations), environment="LIVE",
                execution_mode="SHADOW",
            ).append(Candidate(), rank=1, selected=True)
            CandidateOutcomeWriter(
                str(outcomes), environment="LIVE",
                execution_mode="SHADOW",
            ).append(
                observation_id="obs-1", outcome_type="VIRTUAL_TRADE",
                symbol="BTCUSDT", direction="LONG", payload={"exit_r": 2},
            )
            observation = json.loads(observations.read_text().strip())
            outcome = json.loads(outcomes.read_text().strip())
            for row in (observation, outcome):
                self.assertEqual(row["environment"], "LIVE")
                self.assertEqual(row["execution_mode"], "SHADOW")

    def test_engine_uses_configured_bot_state_path(self):
        source = (ROOT / "engine/core.py").read_text(encoding="utf-8")
        self.assertIn("StateManager(filename=BOT_STATE_PATH)", source)


if __name__ == "__main__":
    unittest.main()
