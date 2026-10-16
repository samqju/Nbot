"""Offline contract tests for V6 strategy logic.

A minimal fake IStrategy/FreqAI is used only because the official Freqtrade
runtime is intentionally not installed in this offline test environment.
These tests are NOT a real Freqtrade backtest or installation smoke test.
"""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "user_data" / "config.json"
STRATEGY = ROOT / "user_data" / "strategies" / "NbotV6.py"


if "freqtrade.strategy" not in sys.modules:
    ft = types.ModuleType("freqtrade")
    strategy_module = types.ModuleType("freqtrade.strategy")
    strategy_module.IStrategy = type("IStrategy", (), {})
    sys.modules["freqtrade"] = ft
    sys.modules["freqtrade.strategy"] = strategy_module
spec = importlib.util.spec_from_file_location("nbot_v6_strategy", STRATEGY)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NbotV6 = module.NbotV6


def candles(n=250, direction=1, price=100.0):
    indices = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    close = price * np.exp(direction * np.arange(n) * 0.001)
    return pd.DataFrame({
        "date": indices,
        "open": close * 0.999,
        "close": close,
        "high": close * 1.002,
        "low": close * 0.998,
        "volume": np.full(n, 100.0),
    })


class FakeFreqai:
    def __init__(self):
        self.calls = 0

    def start(self, dataframe, metadata, strategy):
        self.calls += 1
        frame = dataframe.copy()
        frame["do_predict"] = 0
        frame["&-forward_return"] = np.nan
        return frame


class NbotV6OfflineTests(unittest.TestCase):
    def setUp(self):
        self.bot = NbotV6()
        self.bot.config = json.loads(CONFIG.read_text())
        self.bot.freqai_info = self.bot.config["freqai"]
        self.bot.freqai = FakeFreqai()

    def test_prototype_locked_to_dry_run_and_one_position(self):
        self.bot.bot_start()
        self.bot.config["dry_run"] = False
        with self.assertRaisesRegex(RuntimeError, "LIVE_ORDERS_FORBIDDEN"):
            self.bot.bot_start()
        self.bot.config["dry_run"] = True
        self.bot.config["max_open_trades"] = 2
        with self.assertRaisesRegex(RuntimeError, "ONE_GLOBAL_POSITION"):
            self.bot.bot_start()

    def test_training_disabled_cannot_enter(self):
        self.bot.config["freqai"]["enabled"] = False
        with self.assertRaisesRegex(RuntimeError, "REQUIRES_FREQAI"):
            self.bot.bot_start()

    def test_backtest_mode_permitted_without_dry_run(self):
        self.bot.config["runmode"] = "backtest"
        self.bot.config["dry_run"] = False
        self.bot.bot_start()

    def test_always_one_x_leverage(self):
        leverage = self.bot.leverage("BTC/USDT:USDT", None, 100, 10, 50, None, "long")
        self.assertEqual(leverage, 1.0)

    def test_model_target_is_future_only_and_tail_is_missing(self):
        c = candles(40)
        actual = self.bot.set_freqai_targets(c.copy(), metadata={})["&-forward_return"]
        horizon = self.bot.freqai_info["feature_parameters"]["label_period_candles"]
        self.assertEqual(horizon, 12)
        self.assertAlmostEqual(actual.iloc[0], c.close.iloc[12] / c.close.iloc[0] - 1)
        self.assertTrue(actual.tail(horizon).isna().all())

    def test_past_only_features_unaffected_by_appended_future(self):
        short = candles(250)
        extended = candles(280)
        extended.loc[250:, "close"] = 999999
        extended.loc[250:, "high"] = 1000001
        extended.loc[250:, "low"] = 999998
        features_old = self.bot.feature_engineering_expand_all(short.copy(), period=14)
        features_new = self.bot.feature_engineering_expand_all(extended.copy(), period=14)
        for col in ["%-ema_distance", "%-volatility", "%-volume_ratio", "%-momentum"]:
            pd.testing.assert_series_equal(features_old[col], features_new[col].iloc[:250], check_names=True)

    def test_populate_indicators_calls_official_freqai_hook(self):
        out = self.bot.populate_indicators(candles(), {"pair": "BTC/USDT:USDT"})
        self.assertEqual(self.bot.freqai.calls, 1)
        for col in ["ema_fast", "ema_slow", "previous_high_20", "previous_low_20", "long_setup", "short_setup"]:
            self.assertIn(col, out)
        self.assertFalse(out["long_setup"].iloc[0])
        self.assertFalse(out["short_setup"].iloc[0])

    def test_model_not_ready_always_abstains(self):
        frame = self.bot.populate_indicators(candles(), {"pair": "BTC/USDT:USDT"})
        out = self.bot.populate_entry_trend(frame, {})
        self.assertEqual(int(out["enter_long"].sum()), 0)
        self.assertEqual(int(out["enter_short"].sum()), 0)

    def test_long_needs_positive_cost_adjusted_forecast_and_setup(self):
        frame = self.bot.populate_indicators(candles(), {})
        frame.loc[249, "long_setup"] = True
        frame.loc[249, "short_setup"] = False
        frame.loc[249, "do_predict"] = 1
        frame.loc[249, "&-forward_return"] = 0.005
        self.assertEqual(self.bot.populate_entry_trend(frame.copy(), {}).loc[249, "enter_long"], 0)
        frame.loc[249, "&-forward_return"] = 0.01
        self.assertEqual(self.bot.populate_entry_trend(frame.copy(), {}).loc[249, "enter_long"], 1)
        frame.loc[249, "volume"] = 0
        self.assertEqual(self.bot.populate_entry_trend(frame.copy(), {}).loc[249, "enter_long"], 0)

    def test_short_needs_negative_forecast_and_setup(self):
        frame = self.bot.populate_indicators(candles(direction=-1), {})
        frame.loc[249, "short_setup"] = True
        frame.loc[249, "long_setup"] = False
        frame.loc[249, "do_predict"] = 1
        frame.loc[249, "&-forward_return"] = -0.01
        self.assertEqual(self.bot.populate_entry_trend(frame.copy(), {}).loc[249, "enter_short"], 1)
        frame.loc[249, "do_predict"] = 0
        self.assertEqual(self.bot.populate_entry_trend(frame.copy(), {}).loc[249, "enter_short"], 0)

    def test_nan_and_infinite_predictions_cannot_enter(self):
        for val in [np.nan, np.inf, -np.inf]:
            with self.subTest(val=val):
                f = self.bot.populate_indicators(candles(), {})
                f.loc[249, ["long_setup", "short_setup"]] = True
                f.loc[249, "do_predict"] = 1
                f.loc[249, "&-forward_return"] = val
                out = self.bot.populate_entry_trend(f, {})
                self.assertEqual(int(out.loc[249, "enter_long"]), 0)
                self.assertEqual(int(out.loc[249, "enter_short"]), 0)

    def test_exit_on_trend_reversal_without_prediction(self):
        f = self.bot.populate_indicators(candles(), {})
        f.loc[249, "ema_fast"] = 90
        f.loc[249, "ema_slow"] = 100
        out = self.bot.populate_exit_trend(f, {})
        self.assertEqual(out.loc[249, "exit_long"], 1)

    def test_configuration_and_bounded_features(self):
        cfg = self.bot.config
        self.assertTrue(cfg["dry_run"])
        self.assertEqual(cfg["max_open_trades"], 1)
        self.assertEqual(cfg["trading_mode"], "futures")
        self.assertEqual(cfg["margin_mode"], "isolated")
        self.assertEqual(len(cfg["exchange"]["pair_whitelist"]), 8)
        self.assertIn("BTC/USDT:USDT", cfg["freqai"]["feature_parameters"]["include_corr_pairlist"])
        self.assertFalse(cfg["force_entry_enable"])
        self.assertFalse(cfg["api_server"]["enabled"])
        self.assertFalse(cfg["telegram"]["enabled"])
        self.assertEqual(cfg["freqai"]["model_training_parameters"]["n_jobs"], 1)


if __name__ == "__main__":
    unittest.main()
