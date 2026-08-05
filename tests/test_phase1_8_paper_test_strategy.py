import importlib
import os
import subprocess
import sys
import unittest
from unittest.mock import patch


class Log:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def error(self, message):
        pass


class Phase18PaperTestStrategyTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "TRADING_ENV": "LIVE",
                "EXECUTION_MODE": "SHADOW",
                "STRATEGY_MODE": "PAPER_TEST",
                "PAPER_TEST_MIN_MOVE_PCT": "0.10",
                "PAPER_TEST_COOLDOWN_CANDLES": "6",
            },
            clear=False,
        )
        self.env.start()
        import config
        import strategy.paper_test_strategy as paper_module
        import strategy.strategy_factory as factory_module
        importlib.reload(config)
        self.paper_module = importlib.reload(paper_module)
        self.factory_module = importlib.reload(factory_module)

    def tearDown(self):
        self.env.stop()

    def _strategy(self, closes):
        log = Log()
        strategy = self.paper_module.PaperTestStrategy(system_log=log)
        strategy._universe = {"BTCUSDT"}
        strategy._warmed_up = True
        strategy._candle_history["BTCUSDT"].extend(
            [(x, x, x, x) for x in closes]
        )
        strategy._current_candle["BTCUSDT"] = {
            "bucket": 100, "open": closes[-1], "high": closes[-1],
            "low": closes[-1], "close": closes[-1],
        }
        return strategy, log

    def test_three_rising_closes_create_long(self):
        strategy, log = self._strategy([100.0, 100.1, 100.2])
        intent = strategy.propose_intent()
        self.assertEqual(intent.direction, "LONG")
        self.assertEqual(intent.pattern, "PAPER_TEST_MOMENTUM")
        self.assertFalse(intent.structure_fingerprint["eligible_for_training"])
        self.assertTrue(any("PAPER_TEST_INTENT" in x for x in log.warnings))

    def test_three_falling_closes_create_short(self):
        strategy, _ = self._strategy([100.2, 100.1, 100.0])
        intent = strategy.propose_intent()
        self.assertEqual(intent.direction, "SHORT")

    def test_small_move_creates_no_intent(self):
        strategy, _ = self._strategy([100.0, 100.02, 100.04])
        self.assertIsNone(strategy.propose_intent())

    def test_same_bucket_does_not_repeat(self):
        strategy, _ = self._strategy([100.0, 100.1, 100.2])
        self.assertIsNotNone(strategy.propose_intent())
        self.assertIsNone(strategy.propose_intent())

    def test_factory_selects_paper_test(self):
        strategy = self.factory_module.build_strategy(system_log=Log())
        self.assertIsInstance(strategy, self.paper_module.PaperTestStrategy)

    def test_config_blocks_paper_test_in_trade_mode(self):
        env = os.environ.copy()
        env.update({
            "TRADING_ENV": "TESTNET",
            "EXECUTION_MODE": "TRADE",
            "STRATEGY_MODE": "PAPER_TEST",
        })
        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            env=env, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAPER_TEST_REQUIRES_SHADOW", result.stderr)


if __name__ == "__main__":
    unittest.main()
