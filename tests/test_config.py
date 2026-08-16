import unittest
from dataclasses import replace

from nbot.config import CONFIG, OUTCOME_CONFIG, POLICY_CONFIG, RESEARCH_CONFIG
from nbot.selection import SELECTION_CONFIG
from nbot.champion import CHAMPION_CONFIG


class ConfigTests(unittest.TestCase):
    def test_default_config_is_observer_only(self):
        CONFIG.validate()
        self.assertEqual(CONFIG.role, "OBSERVER_RESEARCH")
        self.assertEqual(CONFIG.market_environment, "LIVE_PUBLIC")
        self.assertEqual(CONFIG.observation_universe_size, 200)
        self.assertIn("V2_6", CONFIG.schema_version)
        self.assertTrue(CONFIG.gap_recovery_enabled)

    def test_execution_like_role_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(CONFIG, role="EXECUTION").validate()

    def test_negative_recovery_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(CONFIG, gap_recovery_max_events_per_cycle=-1).validate()

    def test_research_config_is_frozen_and_valid(self):
        RESEARCH_CONFIG.validate()
        self.assertEqual(RESEARCH_CONFIG.feature_version, "CANONICAL_FEATURES_V1")
        self.assertEqual(RESEARCH_CONFIG.return_lookback_bars, (1, 3, 6, 12, 24, 48))

    def test_changed_frozen_lookbacks_are_rejected(self):
        with self.assertRaises(ValueError):
            replace(RESEARCH_CONFIG, return_lookback_bars=(1, 12, 48)).validate()

    def test_outcome_config_is_frozen_and_valid(self):
        OUTCOME_CONFIG.validate()
        self.assertEqual(OUTCOME_CONFIG.outcome_version, "FUTURE_PATH_4H_V1")
        self.assertEqual(OUTCOME_CONFIG.forward_horizon_bars, (1, 3, 6, 12, 24, 48))
        self.assertEqual(OUTCOME_CONFIG.risk_unit_version, "ATR14_1X_RESEARCH_R_V1")

    def test_changed_outcome_horizons_are_rejected(self):
        with self.assertRaises(ValueError):
            replace(OUTCOME_CONFIG, forward_horizon_bars=(1, 12, 48)).validate()

    def test_policy_config_is_frozen_and_valid(self):
        POLICY_CONFIG.validate()
        self.assertEqual(POLICY_CONFIG.lab_version, "EXIT_POLICY_LAB_V1")
        self.assertEqual(POLICY_CONFIG.outcome_version, "FUTURE_PATH_4H_V1")
        self.assertEqual(POLICY_CONFIG.risk_unit_version, "ATR14_1X_RESEARCH_R_V1")

    def test_changed_policy_horizon_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(POLICY_CONFIG, max_horizon_bars=24).validate()

    def test_selection_config_is_frozen_and_valid(self):
        SELECTION_CONFIG.validate()
        self.assertEqual(SELECTION_CONFIG.lab_version, "ENTRY_SELECTION_LAB_V1")
        self.assertEqual(SELECTION_CONFIG.target_policy_version, "INTEGER_R_STEP_CONTROL")
        self.assertEqual(SELECTION_CONFIG.learned_selector_version, "RIDGE_EXPECTED_NET_R_V1")

    def test_selection_target_policy_cannot_silently_change(self):
        with self.assertRaises(ValueError):
            replace(SELECTION_CONFIG, target_policy_version="STRUCTURE_TRAIL_V1").validate()

    def test_champion_config_is_frozen_and_research_only(self):
        CHAMPION_CONFIG.validate()
        self.assertEqual(CHAMPION_CONFIG.evaluation_version, "WALK_FORWARD_CHAMPION_V1")
        self.assertEqual(CHAMPION_CONFIG.candidate_selector_version, "RIDGE_EXPECTED_NET_R_V1")
        self.assertEqual(CHAMPION_CONFIG.exit_policy_version, "INTEGER_R_STEP_CONTROL")
        self.assertEqual(CHAMPION_CONFIG.candidate_min_train_events, 20)
        self.assertEqual(CHAMPION_CONFIG.min_validation_events, 20)
        self.assertEqual(CHAMPION_CONFIG.min_test_events, 20)

    def test_champion_final_test_window_cannot_silently_change(self):
        with self.assertRaises(ValueError):
            replace(CHAMPION_CONFIG, min_test_events=5).validate()


if __name__ == "__main__":
    unittest.main()
