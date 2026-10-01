from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from nbot.observation.context_learning import describe, train, adjustment, explain_gates, SPACING_MS, WINDOW_MS
from nbot.observation.config import observation_config_for_profile
from nbot.config.profiles import get_profile
from nbot.observation.selection import FEATURE_VECTOR_NAMES, _ridge_score
from tests import test_v391_continuous_challengers as fixture


def vector(**changes):
    result = {key: 0.0 for key in FEATURE_VECTOR_NAMES}
    result.update(atr14_frac=.01, ret_4h_side=.03, ret_15m_side=.005,
                  breadth_1h_side=.6, volatility_percentile=.5)
    result.update(changes)
    return result


def record(event, target, values=None, copies=1):
    return {"event_open_ms": event, "examples": [
        {"event_open_ms": event, "symbol": str(i), "side": "LONG",
         "feature_vector_json": json.dumps(values or vector()), "target_net_r": target}
        for i in range(copies)]}


class ContextLearningTests(unittest.TestCase):
    def test_setup_and_condition_detection_is_direction_relative(self):
        self.assertEqual(describe(vector())["setup"], "TREND_CONTINUATION")
        self.assertEqual(describe(vector(ret_15m_side=-.005))["setup"], "TREND_PULLBACK")
        self.assertEqual(describe(vector(ret_4h_side=-.03))["setup"], "STRETCHED_REVERSAL")
        self.assertEqual(describe(vector(range_frac=.03, ret_5m_side=.01))["setup"], "VOLATILITY_EXPANSION")
        self.assertEqual(describe(vector(ret_4h_side=0, ret_1h_percentile_side=.8))["setup"], "RELATIVE_STRENGTH")
        self.assertEqual(describe(vector(breadth_1h_side=-.6))["market_alignment"], "OPPOSED")

    def test_losing_setup_vetoes_positive_prediction_but_good_setup_does_not_inflate_it(self):
        for target, expected in ((-1, 0), (4, 2)):
            model = train([record(i * SPACING_MS, target) for i in range(8)], cutoff_ms=8 * SPACING_MS)
            result = adjustment(model, vector(), 2)
            self.assertEqual(result["adjusted_score"], expected)
            self.assertEqual(result["support_events"], 8)

    def test_same_strategy_can_have_different_results_in_different_conditions(self):
        aligned, opposed = vector(), vector(breadth_1h_side=-.6)
        records = []
        for i in range(8):
            a = record(i * SPACING_MS, 2, aligned)
            a["examples"] += record(i * SPACING_MS, -2, opposed)["examples"]
            records.append(a)
        model = train(records, cutoff_ms=8 * SPACING_MS)
        self.assertGreater(adjustment(model, aligned, 2)["adjusted_score"], 0)
        self.assertLessEqual(adjustment(model, opposed, 2)["adjusted_score"], 0)

    def test_many_coins_do_not_fake_independent_sample_size(self):
        model = train([record(0, -1, copies=100)], cutoff_ms=SPACING_MS)
        result = adjustment(model, vector(), 2)
        self.assertEqual(result["status"], "INSUFFICIENT_SETUP_EVIDENCE_USING_RIDGE")
        self.assertEqual(result["adjusted_score"], 2)
        self.assertEqual(model["groups"]["TREND_CONTINUATION|ALL"]["events"], 1)

    def test_future_overlapping_and_expired_samples_are_rejected(self):
        for records, cutoff in (([record(2, 1)], 1), ([record(0, 1), record(1, 1)], 2),
                                ([record(0, 1)], WINDOW_MS)):
            with self.assertRaises(ValueError):
                train(records, cutoff_ms=cutoff)

    def test_missing_history_does_not_teach_setup(self):
        model = train([record(0, 1, vector(missing_ret_4h=1))], cutoff_ms=1)
        self.assertEqual(model["groups"], {})

    def test_nonfinite_data_and_tampered_contract_fail_closed(self):
        with self.assertRaises(ValueError):
            train([record(0, float('nan'))], cutoff_ms=1)
        model = train([record(0, 1)], cutoff_ms=1)
        model["version"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            adjustment(model, vector(), 1)

    def test_predictions_share_exact_calibration_between_training_and_inference(self):
        model = {"intercept": 2, "means": dict.fromkeys(FEATURE_VECTOR_NAMES, 0),
                 "scales": dict.fromkeys(FEATURE_VECTOR_NAMES, 1),
                 "coefficients": dict.fromkeys(FEATURE_VECTOR_NAMES, 0),
                 "context_calibration": train([record(i * SPACING_MS, -1) for i in range(8)], cutoff_ms=8*SPACING_MS)}
        self.assertEqual(_ridge_score(model, json.dumps(vector())), 0)

    def test_gate_reports_do_not_mislabel_positive_but_unproven_results(self):
        report = explain_gates({"candidate_positive_expectancy_ci": False, "minimum_trade_events": True})
        self.assertEqual(len(report), 1)
        self.assertIn("not supported strongly enough", report[0]["explanation"])

    def test_small_server_settings_and_unit_limits_are_opt_in(self):
        with mock.patch.dict(os.environ, {"NBOT_OBSERVATION_RESOURCE_PROFILE": "tiny"}):
            config = observation_config_for_profile(get_profile("live-paper"))
            self.assertEqual((config.observation_universe_size, config.candle_fetch_workers), (20, 2))
        with mock.patch.dict(os.environ, {"NBOT_OBSERVATION_RESOURCE_PROFILE": "typo"}):
            with self.assertRaises(ValueError):
                observation_config_for_profile(get_profile("live-paper"))
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("installer", root / "deploy/observation/install_services.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as directory:
            import sys
            paths = installer.render_units(repo=root, python=Path(sys.executable), user="ubuntu",
                                           destination=Path(directory), resource_profile="tiny")
            research = next(p for p in paths if p.name == "nbot-research-epoch.service").read_text()
            self.assertIn("MemoryMax=384M", research)
            self.assertIn("NBOT_OBSERVATION_RESOURCE_PROFILE=tiny", research)

    def test_memory_reader_caps_cutoff_and_skips_decompression_between_samples(self):
        from nbot.observation.selection import RidgeSufficientStatistics
        base = fixture.V391ContinuousChallengerTests()
        base.setUp()
        try:
            base._append_events(60, RidgeSufficientStatistics.empty())
            rows = list(base.memory.iter_event_records(through_event_ms=55 * 300_000, minimum_spacing_ms=SPACING_MS))
            self.assertEqual([r["event_open_ms"] for r in rows], [300_000, 50 * 300_000])
        finally:
            base.doCleanups()
            base.tearDown()

    def test_report_explains_sample_size_and_realistic_evaluation_duration(self):
        from nbot.observation.selection import RidgeSufficientStatistics
        from nbot.observation.challengers import ContinuousChallengerCycle
        from nbot.observation.learning_report import learning_report
        base = fixture.V391ContinuousChallengerTests()
        base.setUp()
        try:
            self.assertIn("No model yet", learning_report(base.memory))
            base._append_events(25, RidgeSufficientStatistics.empty())
            cycle = ContinuousChallengerCycle(base.memory, release_sha=base.release_sha)
            cycle.cycle()
            report = learning_report(base.memory)
            self.assertIn("Latest model", report)
            self.assertIn("roughly seven days", report)
            self.assertIn("Recent independent setup samples: 1", report)
            self.assertIn("not actual execution P&L", report)
        finally:
            base.doCleanups()
            base.tearDown()
