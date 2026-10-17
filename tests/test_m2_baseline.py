"""M2 reproducibility and non-ML signal causality tests (no exchange network)."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import types
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nbot_m2_costs", ROOT / "scripts/m2_evaluate.py")
costs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(costs)
if "freqtrade.strategy" not in sys.modules:
    sys.modules["freqtrade"] = types.ModuleType("freqtrade")
    module = types.ModuleType("freqtrade.strategy")
    module.IStrategy = type("IStrategy", (), {})
    sys.modules["freqtrade.strategy"] = module
strategy_spec = importlib.util.spec_from_file_location(
    "nbot_m2_no_ml", ROOT / "user_data/strategies/NbotV6NoML.py")
baseline = importlib.util.module_from_spec(strategy_spec)
strategy_spec.loader.exec_module(baseline)


def trade(pnl, stake=1000, side=False, pair="BTC/USDT:USDT"):
    return {
        "stake_amount": stake, "leverage": 1.0, "profit_abs": pnl,
        "fee_open": 0.0005, "fee_close": 0.0005, "funding_fees": 0,
        "trade_duration": 30, "is_short": side, "pair": pair,
        "close_date": "2026-10-02 01:00:00+00:00",
    }


def stats(name, trades):
    return {
        "backtest_start": "2026-10-01", "backtest_end": "2026-10-08",
        "max_open_trades": 1, "stake_amount": 1000,
        "starting_balance": 100000, "timeframe": "5m",
        "pairlist": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
        "trades": trades, "profit_total_abs": sum(t["profit_abs"] for t in trades),
        "profit_factor": 0.8, "sharpe": 0, "max_drawdown_abs": 7,
        "rejected_signals": 4,
    }


class M2BenchmarkTests(unittest.TestCase):
    def test_cost_is_additive_per_roundtrip_and_fee_not_double_counted(self):
        rows = [trade(10), trade(-5, stake=500, side=True)]
        result = costs.aggregate(rows, extra_bps=20)
        self.assertEqual(result["pnl_usdt"], 2)
        self.assertEqual(result["incremental_execution_cost_usdt"], 3)
        self.assertEqual(result["winners"], 1)
        self.assertEqual(result["losers"], 1)
        self.assertEqual(result["engine_fee_open_close_rates"], [[0.0005, 0.0005]])

    def test_zero_trade_and_no_trade_baseline(self):
        empty = costs.aggregate([])
        self.assertEqual(empty["pnl_usdt"], 0)
        self.assertEqual(empty["trades"], 0)
        model = costs.evaluate(stats("NbotV6", [trade(-10)]),
                               stats("NbotV6NoML", [trade(5)]))
        self.assertEqual(model["benchmarks"]["NO_TRADE"]["trades"], 0)
        self.assertGreater(model["comparison"]["non_ml_minus_ai_usdt_at_fees_only"], 0)

    def test_cost_cases_never_reward_added_cost(self):
        trades = [trade(0.5, stake=1000)]
        returns = [costs.aggregate(trades, extra_bps=n)["pnl_usdt"]
                   for n in costs.BPS]
        self.assertEqual(returns, sorted(returns, reverse=True))

    def test_mismatched_periods_rejected(self):
        a = stats("a", [trade(1)])
        b = stats("b", [trade(2)])
        b["backtest_end"] = "2026-10-09"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            costs.validate_compatible(a, b)

    def test_negative_cost_refused(self):
        with self.assertRaisesRegex(ValueError, "Negative"):
            costs.aggregate([trade(3)], extra_bps=-1)

    def test_non_ml_strategy_has_only_prior_completed_highs_lows(self):
        s = baseline.NbotV6NoML()
        df = pd.DataFrame({
            "close": [100+i*.1 for i in range(80)],
            "high": [101+i*.1 for i in range(80)],
            "low": [99+i*.1 for i in range(80)],
            "open": [100+i*.1 for i in range(80)],
            "volume": [100]*80,
        })
        a = s.populate_indicators(df.copy(), {})
        df.loc[79, "high"] = 999999  # future candle relative to prior signals
        b = s.populate_indicators(df.copy(), {})
        pd.testing.assert_series_equal(a["previous_high_20"].iloc[:80],
                                       b["previous_high_20"].iloc[:80])
        self.assertEqual(a["previous_high_20"].iloc[79],
                         max(a["high"].iloc[59:79]))

    def test_non_ml_requires_dry_run_and_no_api_keys(self):
        s = baseline.NbotV6NoML()
        s.config = {"dry_run": False, "max_open_trades": 1, "exchange": {}}
        with self.assertRaisesRegex(RuntimeError, "DRY_RUN_ONLY"):
            s.bot_start()
        s.config = {"dry_run": True, "max_open_trades": 1, "exchange": {"key": "bad"}}
        with self.assertRaisesRegex(RuntimeError, "NO_KEYS"):
            s.bot_start()
        s.config = {"dry_run": True, "max_open_trades": 2, "exchange": {}}
        with self.assertRaisesRegex(RuntimeError, "ONE_SLOT_ONLY"):
            s.bot_start()


if __name__ == "__main__":
    unittest.main()
