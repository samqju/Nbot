"""M2 independent funding arithmetic, causal features, and audit-only safety tests.

No network; no Binance credentials; no live bot; no Freqtrade runtime required.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ROOT / "user_data" / "strategies"
if "freqtrade.strategy" not in sys.modules:
    sys.modules["freqtrade"] = types.ModuleType("freqtrade")
    ft = types.ModuleType("freqtrade.strategy")
    ft.IStrategy = type("IStrategy", (), {})
    sys.modules["freqtrade.strategy"] = ft

sys.path.insert(0, str(STRATEGIES))
from NbotV6 import NbotV6
from NbotV6M2Audit import NbotV6M2Audit

spec = importlib.util.spec_from_file_location("nbot_funding", ROOT / "scripts/m2_funding_reconcile.py")
funding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(funding)


def candles(n=360):
    rng = np.random.default_rng(1782)
    prices = 100 * np.exp(rng.normal(0, .004, n).cumsum())
    return pd.DataFrame({
        "close": prices, "open": prices * .999,
        "high": prices * 1.002, "low": prices * .998,
        "volume": rng.integers(1, 500, size=n).astype(float),
    })


class M2AIIntegrityTests(unittest.TestCase):
    def test_all_model_features_are_prefix_causal_and_not_future_target(self):
        base = candles()
        s = NbotV6()
        for period in (14, 28):
            full = s.feature_engineering_expand_all(base.copy(), period)
            prefix = s.feature_engineering_expand_all(base.iloc[:220].copy(), period)
            cols = [x for x in full if x.startswith("%-")]
            self.assertTrue(cols)
            self.assertTrue(all(not x.startswith("&-") for x in cols))
            pd.testing.assert_frame_equal(full.iloc[:220][cols], prefix[cols])
        full = s.feature_engineering_expand_basic(base.copy())
        prefix = s.feature_engineering_expand_basic(base.iloc[:220].copy())
        cols = [x for x in full if x.startswith("%-")]
        pd.testing.assert_frame_equal(full.iloc[:220][cols], prefix[cols])

    def test_forward_return_is_label_only_and_last_12_unavailable(self):
        s = NbotV6()
        s.freqai_info = {"feature_parameters": {"label_period_candles": 12}}
        frame = s.set_freqai_targets(candles())
        self.assertTrue(frame["&-forward_return"].iloc[-12:].isna().all())
        self.assertAlmostEqual(
            frame["&-forward_return"].iloc[100],
            frame["close"].iloc[112] / frame["close"].iloc[100] - 1,
        )
        self.assertFalse(any(k.startswith("%-") and "forward" in k for k in frame))

    def test_audit_strategy_never_allows_live_or_credentials(self):
        s = NbotV6M2Audit()
        c = json.loads((ROOT / "user_data" / "config.json").read_text())
        c["nbot_m2_audit_only"] = True
        c["max_open_trades"] = -1
        s.config = c
        with patch.object(sys, "argv", ["freqtrade", "lookahead-analysis"]):
            s.bot_start()  # intentionally unlimited official lookahead probe
        c["dry_run"] = False
        with patch.object(sys, "argv", ["freqtrade", "lookahead-analysis"]):
            with self.assertRaisesRegex(RuntimeError, "LIVE_NEVER_ALLOWED"):
                s.bot_start()
        c["dry_run"] = True
        c["exchange"]["key"] = "bad"
        with patch.object(sys, "argv", ["freqtrade", "lookahead-analysis"]):
            with self.assertRaisesRegex(RuntimeError, "CREDENTIALS_FORBIDDEN"):
                s.bot_start()
        c["exchange"]["key"] = ""
        with patch.object(sys, "argv", ["freqtrade", "trade"]):
            with self.assertRaisesRegex(RuntimeError, "ONE_GLOBAL_POSITION"):
                s.bot_start()

    def test_funding_short_and_long_boundary_events(self):
        base = {
            "open_date": "2026-10-01 00:00:00+00:00",
            "close_date": "2026-10-01 16:00:00+00:00",
            "amount": 2.0, "is_short": True,
            "funding_fees": 0.02,
        }
        records = [
            {"fundingTime": funding.timestamp_ms("2026-10-01T00:00:00+00:00"),
             "markPrice": "100", "fundingRate": ".0001"},
            {"fundingTime": funding.timestamp_ms("2026-10-01T08:00:00+00:00"),
             "markPrice": "100", "fundingRate": ".0001"},
            {"fundingTime": funding.timestamp_ms("2026-10-01T16:00:00+00:00"),
             "markPrice": "100", "fundingRate": "-.0001"},
        ]
        result = funding.expected_funding(base, records)
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["calculated_usdt"], 0.0)
        self.assertEqual(result["delta_usdt"], -0.02)
        base["is_short"] = False
        result2 = funding.expected_funding(base, records)
        self.assertEqual(result2["calculated_usdt"], 0.0)

    def test_funding_short_receives_long_pays(self):
        base = {
            "open_date": "2026-10-01T00:00:00+00:00",
            "close_date": "2026-10-01T09:00:00+00:00",
            "amount": 2.0, "is_short": True, "funding_fees": 0.02,
        }
        records = [{"fundingTime": funding.timestamp_ms("2026-10-01T08:00:00+00:00"),
                    "markPrice": "100", "fundingRate": ".0001"}]
        self.assertEqual(funding.expected_funding(base, records)["calculated_usdt"], 0.02)
        base["is_short"] = False
        self.assertEqual(funding.expected_funding(base, records)["calculated_usdt"], -0.02)

    def test_zero_minute_stop_is_valid_and_has_no_funding_event(self):
        tick = "2026-09-10T00:30:00+00:00"
        row = {
            "open_date": tick, "close_date": tick,
            "amount": 2.0, "is_short": True, "funding_fees": 0.0
        }
        got = funding.expected_funding(row, [])
        self.assertEqual(got["event_count"], 0)
        self.assertEqual(got["calculated_usdt"], 0.0)

    def test_funding_url_safety_filters(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            funding.symbol_from_pair("BTC/USDT")
        self.assertEqual(funding.symbol_from_pair("BTC/USDT:USDT"), "BTCUSDT")
        with self.assertRaisesRegex(ValueError, "Bad"):
            funding.public_funding("BTC/USDT", 1, 2)


if __name__ == "__main__":
    unittest.main()
