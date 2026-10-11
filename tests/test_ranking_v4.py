import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot.observation.ranking_v4 import (
    AUTHORITY,
    MIN_OOF_EVENTS,
    VERSION,
    V4RankingChallenger,
    _pav,
    build_calibration,
    calibration_lookup,
    enabled,
    relevance,
)
from nbot.observation.research_memory import ResearchMemoryStore


class V4RankingUnitTests(unittest.TestCase):
    def test_relevance_is_ordinal_not_raw_r(self):
        self.assertEqual(relevance(-2.0), 0)
        self.assertEqual(relevance(-0.25), 1)
        self.assertEqual(relevance(0.1), 2)
        self.assertEqual(relevance(0.75), 3)
        self.assertEqual(relevance(2.0), 4)

    def test_pav_enforces_monotone_calibration(self):
        fitted = _pav([0.2, -0.4, 0.5, 0.1], [10, 10, 10, 10])
        self.assertEqual(len(fitted), 4)
        self.assertTrue(all(a <= b for a, b in zip(fitted, fitted[1:])))

    def test_calibration_is_monotone_and_bounded(self):
        rows = []
        for i in range(MIN_OOF_EVENTS + 10):
            rows.append({
                "event_ms": i,
                "row_id": str(i),
                "margin": i / 100.0,
                "target_net_r": -1.0 if i < 10 else (0.25 if i < 25 else 1.0),
                "positive": i >= 10,
            })
        calibration = build_calibration(rows)
        bins = calibration["bins"]
        self.assertGreaterEqual(len(bins), 2)
        means = [b["calibrated_mean_net_r"] for b in bins]
        probs = [b["calibrated_positive_rate"] for b in bins]
        self.assertTrue(all(a <= b for a, b in zip(means, means[1:])))
        self.assertTrue(all(a <= b for a, b in zip(probs, probs[1:])))
        self.assertTrue(all(0.0 <= p <= 1.0 for p in probs))
        low = calibration_lookup(calibration, -1.0)
        high = calibration_lookup(calibration, 99.0)
        self.assertLessEqual(low["expected_net_r"], high["expected_net_r"])

    def test_calibration_requires_causal_support(self):
        rows = [{
            "event_ms": i,
            "row_id": str(i),
            "margin": float(i),
            "target_net_r": 1.0,
            "positive": True,
        } for i in range(MIN_OOF_EVENTS - 1)]
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_OOF"):
            build_calibration(rows)

    def test_v4_is_opt_in_and_never_has_order_authority(self):
        with tempfile.TemporaryDirectory() as td:
            memory = ResearchMemoryStore(Path(td) / "memory.db")
            memory.persist_artifact("seed", {})
            learner = V4RankingChallenger(memory, release_sha="a" * 40)
            with patch.dict(os.environ, {"NBOT_RANKING_V4": "0"}):
                self.assertFalse(enabled())
                result = learner.train_if_needed()
            self.assertEqual(result["status"], "DISABLED")
            self.assertEqual(result["order_authority"], "NONE")
            self.assertEqual(AUTHORITY, "RESEARCH_CHALLENGER_ONLY_NO_ORDER_AUTHORITY")
            self.assertEqual(VERSION, "SELECTIVE_ML_V4_RANK_CAL_PAPER")

    def test_invalid_enable_setting_fails_closed(self):
        with patch.dict(os.environ, {"NBOT_RANKING_V4": "yes"}):
            with self.assertRaisesRegex(ValueError, "V4_SETTING_INVALID"):
                enabled()


if __name__ == "__main__":
    unittest.main()
