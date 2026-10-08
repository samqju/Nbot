import importlib.util
import math
import unittest

from nbot.observation.selection import FEATURE_VECTOR_NAMES
from nbot.observation.selective_ml import (
    ML_FEATURE_NAMES,
    SelectiveMLConfig,
    augment_vector,
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

    def test_config_has_no_next_bar_entry_probability_gate(self):
        cfg = SelectiveMLConfig()
        self.assertFalse(hasattr(cfg, "min_fill_probability"))
        self.assertFalse(hasattr(cfg, "entry_min_samples"))
        self.assertFalse(hasattr(cfg, "entry_min_each_class"))

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
    def test_train_serialize_and_score_small_model(self):
        import json
        from nbot.observation.selective_ml import SelectiveMLManager, SelectiveMLRuntime

        class FakeMemory:
            def __init__(self, events):
                self.events = events
                self.saved = []

            def iter_training_rows(self):
                for event_ms, rows in self.events:
                    for row in rows:
                        yield event_ms, row

            def history_base(self):
                return {"through_event_ms": self.events[-1][0]}

            def list_artifacts(self, *, prefix=""):
                return [item for item in self.saved if item["artifact_key"].startswith(prefix)]

            def persist_artifact(self, key, payload, *, recorded_at_ms=None):
                record = {
                    "artifact_key": key,
                    "payload": payload,
                    "artifact_digest": "d" * 64,
                    "recorded_at_ms": int(recorded_at_ms or 1),
                }
                self.saved.append(record)
                return record

        events = []
        start = 1_700_000_000_000
        for event_index in range(60):
            rows = []
            for row_index in range(8):
                vector = self.base_vector()
                signal = ((event_index * 3 + row_index) % 21 - 10) / 200.0
                vector["ret_4h_side"] = signal
                vector["ret_1h_side"] = signal / 2
                vector["ret_15m_side"] = -signal / 5
                vector["ret_1h_percentile_side"] = max(0.0, min(1.0, 0.5 + signal * 5))
                rows.append({
                    "feature_vector_json": json.dumps(vector, sort_keys=True),
                    "target_net_r": signal * 12.0,
                })
            events.append((start + event_index * 300_000, rows))

        cfg = SelectiveMLConfig(
            max_events=100,
            max_rows=10_000,
            min_train_events=40,
            min_validation_events=10,
            num_boost_round=40,
            early_stopping_rounds=5,
            learning_rate=0.08,
            num_leaves=7,
            max_depth=3,
            min_data_in_leaf=10,
            threads=1,
        )
        memory = FakeMemory(events)
        manager = SelectiveMLManager(memory, None, release_sha="a" * 40, config=cfg)
        result = manager.train()
        self.assertEqual(result["status"], "TRAINED")
        self.assertEqual(result["entry_gate_mode"], "EXECUTION_REALTIME_ONLY")
        self.assertEqual(len(memory.saved), 1)
        self.assertEqual(memory.saved[0]["payload"]["entry_gate_mode"], "EXECUTION_REALTIME_ONLY")
        self.assertNotIn("entry_model", memory.saved[0]["payload"])
        runtime = SelectiveMLRuntime(memory.saved[0]["payload"])
        mean, lower = runtime.score(self.base_vector())
        self.assertTrue(math.isfinite(mean))
        self.assertTrue(math.isfinite(lower))

    @unittest.skipUnless(importlib.util.find_spec("lightgbm"), "LightGBM optional dependency not installed")
    def test_lightgbm_dependency_imports(self):
        from nbot.observation.selective_ml import _ml_imports
        lgb, np = _ml_imports()
        self.assertTrue(hasattr(lgb, "train"))
        self.assertTrue(hasattr(np, "asarray"))


if __name__ == "__main__":
    unittest.main()
