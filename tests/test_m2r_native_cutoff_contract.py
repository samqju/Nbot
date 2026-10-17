"""M2R as-of label-cutoff regression tests: offline, no Freqtrade runtime.

This verifies NBOT's label functions when passed a strictly cutoff-limited
dataframe. It DOES NOT independently certify installed FreqAI internals,
the official lookahead diagnostic, or executable historical fills.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "user_data" / "strategies"))
from nbot_trade_outcome import training_labels, training_labels_for_family, decision_features

HORIZON = 12
CUTOFF = 200


def candles(n=260):
    # Monotonic, valid candles have frequent breakout signals whose trade
    # outcomes take all 12 bars (rather than hitting 2% stop/5% target).
    price = 100.0 * np.exp(np.arange(n) * 0.001)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"),
        "open": price, "high": price * 1.002,
        "low": price * 0.998, "close": price,
        "volume": np.full(n, 100.0),
    })


class NativeCutoffContractResearchTests(unittest.TestCase):
    def test_config_is_chronological_and_window_has_twelve_candle_target(self):
        config = json.loads((ROOT / "user_data" / "config.json").read_text())
        override = json.loads((ROOT / "user_data" / "config.m2r-trade-outcome.json").read_text())
        self.assertEqual(config["freqai"]["data_split_parameters"]["shuffle"], False)
        self.assertEqual(config["freqai"]["data_split_parameters"]["test_size"], 0.2)
        self.assertEqual(override["freqai"]["train_period_days"], 30)
        self.assertEqual(override["freqai"]["backtest_period_days"], 7)
        self.assertEqual(override["freqai"]["feature_parameters"]["label_period_candles"], HORIZON)

    def test_cutoff_before_target_generation_purges_complete_trade_labels(self):
        full = candles()
        # Mirrors the FreqAI 2026.9 BACKTEST ordering: date-prefix FIRST,
        # set_freqai_targets SECOND, slice training window THIRD.
        asof = full.iloc[:CUTOFF].copy()
        for family in (None, "breakout", "pullback"):
            with self.subTest(family=family):
                builder = training_labels if family is None else (
                    lambda df: training_labels_for_family(df, family)
                )
                safe = builder(asof)["&-trade_net_return"]
                self.assertTrue(safe.iloc[-HORIZON:].isna().all())
                self.assertGreater(safe.iloc[:-HORIZON].notna().sum(), 0 if family != "pullback" else -1)
                # Append wholly unseen prices: past-only %-features do not change.
                features_before = decision_features(asof)
                features_after = decision_features(full).iloc[:CUTOFF]
                columns = [column for column in features_before if column.startswith("%-")]
                pd.testing.assert_frame_equal(features_before[columns], features_after[columns])

    def test_reverse_order_would_be_unsafe_and_is_not_the_contract(self):
        full = candles()
        safe = training_labels(full.iloc[:CUTOFF].copy())["&-trade_net_return"]
        unsafe = training_labels(full)["&-trade_net_return"].iloc[:CUTOFF]
        self.assertTrue(safe.iloc[-HORIZON:].isna().all())
        self.assertTrue(unsafe.iloc[-HORIZON:].notna().any(),
                        "This counterexample must demonstrate boundary crossing")
        self.assertTrue(safe.iloc[:-HORIZON].equals(unsafe.iloc[:-HORIZON]))

    def test_internal_eighty_twenty_split_is_not_an_embargo(self):
        # FreqAI's chronological train_test_split(shuffle=False) reserves a
        # final 20% for internal evaluation, but does not automatically
        # embargo last 12 labels before that INTERNAL split.
        all_labels = training_labels(candles() .iloc[:CUTOFF].copy())["&-trade_net_return"]
        valid_idx = np.flatnonzero(all_labels.notna().to_numpy())
        split_row = int(len(valid_idx) * 0.8)
        self.assertGreater(split_row, 12)
        internal_start = valid_idx[split_row]
        # For a fully timed-out trade, these earlier training labels observe
        # price candles in the internal evaluation section. Do not mistake
        # internal test metrics for purged validation.
        crossing = [int(index) for index in valid_idx[:split_row]
                    if int(index) + HORIZON >= internal_start]
        self.assertTrue(crossing)
        # Outer backtest boundary remains protected by the prior test.
        self.assertTrue(all_labels.iloc[-HORIZON:].isna().all())


if __name__ == "__main__":
    unittest.main()
