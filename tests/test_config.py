import unittest
from dataclasses import replace

from nbot.config import CONFIG


class ConfigTests(unittest.TestCase):
    def test_default_config_is_observer_only(self):
        CONFIG.validate()
        self.assertEqual(CONFIG.role, "OBSERVER_RESEARCH")
        self.assertEqual(CONFIG.market_environment, "LIVE_PUBLIC")
        self.assertEqual(CONFIG.observation_universe_size, 200)
        self.assertIn("V2_1", CONFIG.schema_version)
        self.assertTrue(CONFIG.gap_recovery_enabled)

    def test_execution_like_role_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(CONFIG, role="EXECUTION").validate()

    def test_negative_recovery_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(CONFIG, gap_recovery_max_events_per_cycle=-1).validate()


if __name__ == "__main__":
    unittest.main()
