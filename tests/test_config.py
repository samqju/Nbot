import unittest
from dataclasses import replace

from nbot.config import CONFIG


class ConfigTests(unittest.TestCase):
    def test_default_config_is_observer_only(self):
        CONFIG.validate()
        self.assertEqual(CONFIG.role, "OBSERVER_RESEARCH")
        self.assertEqual(CONFIG.market_environment, "LIVE_PUBLIC")
        self.assertEqual(CONFIG.observation_universe_size, 200)

    def test_execution_like_role_is_rejected(self):
        with self.assertRaises(ValueError):
            replace(CONFIG, role="EXECUTION").validate()


if __name__ == "__main__":
    unittest.main()
