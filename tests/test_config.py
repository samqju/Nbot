import unittest
from dataclasses import replace

from nbot.config import CONFIG, RESEARCH_CONFIG


class ConfigTests(unittest.TestCase):
    def test_default_config_is_observer_only(self):
        CONFIG.validate()
        self.assertEqual(CONFIG.role, "OBSERVER_RESEARCH")
        self.assertEqual(CONFIG.market_environment, "LIVE_PUBLIC")
        self.assertEqual(CONFIG.observation_universe_size, 200)
        self.assertIn("V2_2", CONFIG.schema_version)
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


if __name__ == "__main__":
    unittest.main()
