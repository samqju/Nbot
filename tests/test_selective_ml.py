import importlib.util
import math
import unittest

from nbot.observation.selection import FEATURE_VECTOR_NAMES
from nbot.observation.selective_ml import (
    ENTRY_FEATURE_NAMES,
    ML_FEATURE_NAMES,
    SelectiveMLConfig,
    augment_vector,
    entry_vector,
)


class SelectiveMLTests(unittest.TestCase):
    def base_vector(self):
        value = {name: 0.0 for name in FEATURE_VECTOR_NAMES}
        value.update({
            "atr14_frac": 0.01,
            "realized_vol_4h": 0.02,
            "realized_vol_1h": 0.01,
            "spread_pct": 0.04,
            "liquidity_percentile": 0.7,
            "volatility_percentile": 0.6,
            "ret_1h_percentile_side": 0.8,
            "ret_4h_side": 0.03,
            "ret_15m_side": -0.004,
            "btc_ret_1h_side": 0.005,
            "ret_1h_side": 0.012,
            "breadth_5m_side": 0.4,
            "breadth_1h_side": 0.3,
            "csm_alignment": 1.0,
            "tsmom_alignment": 1.0,
            "intraday_alignment": 0.0,
        })
        return value

    def test_augmented_feature_schema_is_stable_and_finite(self):
        result = augment_vector(self.base_vector())
        self.assertEqual(tuple(result), ML_FEATURE_NAMES)
        self.assertTrue(all(math.isfinite(v) for v in result.values()))
        self.assertAlmostEqual(result["ret_4h_atr"], 3.0)
        self.assertGreater(result["pullback_15m_vs_4h"], 0)

    def test_entry_feature_schema_has_candidate_and_context(self):
        result = entry_vector(
            score=0.5, bid=100.0, ask=100.1, side="LONG",
            candidate_id="TREND_PULLBACK_V1", context="ALIGNED:NORMAL",
            decision_ms=1_800_100,
        )
        self.assertEqual(tuple(result), ENTRY_FEATURE_NAMES)
        self.assertEqual(result["candidate::TREND_PULLBACK_V1"], 1.0)
        self.assertEqual(result["context::ALIGNED:NORMAL"], 1.0)
        self.assertGreater(result["spread_pct"], 0)

    def test_small_vps_defaults_are_bounded(self):
        cfg = SelectiveMLConfig()
        cfg.validate()
        self.assertEqual(cfg.threads, 1)
        self.assertLessEqual(cfg.max_depth, 4)
        self.assertLessEqual(cfg.num_leaves, 15)
        self.assertLessEqual(cfg.max_rows, 60_000)

    def test_invalid_aggressive_config_is_rejected(self):
        with self.assertRaises(ValueError):
            SelectiveMLConfig(threads=8).validate()
        with self.assertRaises(ValueError):
            SelectiveMLConfig(max_depth=20).validate()

    @unittest.skipUnless(importlib.util.find_spec("lightgbm"), "LightGBM optional dependency not installed")
    def test_lightgbm_dependency_imports(self):
        from nbot.observation.selective_ml import _ml_imports
        lgb, np = _ml_imports()
        self.assertTrue(hasattr(lgb, "train"))
        self.assertTrue(hasattr(np, "asarray"))


if __name__ == "__main__":
    unittest.main()
