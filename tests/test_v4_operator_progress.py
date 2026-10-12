"""Regression tests for bounded tiny universe and read-only V4 contest viewer."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.v4_paper_contest import V4PaperContestStore
from deploy.observation.v4_paper_progress import report


class TinyCollectorCapacityTests(unittest.TestCase):
    def test_tiny_default_keeps_existing_small_vps_limits(self):
        with patch.dict(os.environ, {"NBOT_OBSERVATION_RESOURCE_PROFILE": "tiny"}, clear=False):
            with patch.dict(os.environ, {"NBOT_OBSERVATION_UNIVERSE_SIZE": ""}, clear=False):
                os.environ.pop("NBOT_OBSERVATION_UNIVERSE_SIZE", None)
                c = observation_config_for_profile(get_profile("live-paper"))
        self.assertEqual((c.observation_universe_size, c.candle_fetch_workers,
                          c.gap_recovery_max_events_per_cycle), (20, 2, 4))

    def test_tiny_override_increases_symbols_not_workers_or_recovery(self):
        with patch.dict(os.environ, {
            "NBOT_OBSERVATION_RESOURCE_PROFILE": "tiny",
            "NBOT_OBSERVATION_UNIVERSE_SIZE": "60",
        }):
            c = observation_config_for_profile(get_profile("live-paper"))
        self.assertEqual((c.observation_universe_size, c.candle_fetch_workers,
                          c.gap_recovery_max_events_per_cycle), (60, 2, 4))

    def test_invalid_tiny_overrides_are_rejected(self):
        for invalid in ("0", "-2", "101", "test", "1.5"):
            with self.subTest(invalid=invalid), patch.dict(os.environ, {
                "NBOT_OBSERVATION_RESOURCE_PROFILE": "tiny",
                "NBOT_OBSERVATION_UNIVERSE_SIZE": invalid,
            }):
                with self.assertRaisesRegex(ValueError, "NBOT_TINY_UNIVERSE_SIZE_INVALID"):
                    observation_config_for_profile(get_profile("live-paper"))

    def test_standard_remains_default_unless_explicitly_changed_in_other_code(self):
        with patch.dict(os.environ, {
            "NBOT_OBSERVATION_RESOURCE_PROFILE": "standard",
            "NBOT_OBSERVATION_UNIVERSE_SIZE": "60",
        }):
            c = observation_config_for_profile(get_profile("live-paper"))
        self.assertEqual(c.observation_universe_size, 200)
        self.assertEqual(c.candle_fetch_workers, 16)


class PaperViewerTests(unittest.TestCase):
    def test_missing_db_does_not_create_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertIn("missing", report(root))
            self.assertFalse((root / "data/observation/v4/paper_contest.db").exists())

    def test_active_and_historical_contest_readable_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            db = root / "data/observation/v4/paper_contest.db"
            store = V4PaperContestStore(db)
            model = type("FakeModel", (), {
                "qualification": "BASELINE_READY",
                "model_digest": "sampledigest",
            })()
            contest = store.ensure_contest(
                champion_generation=None, challenger_generation=1,
                models={1: model}, now_ms=1,
            )
            store.open_trade(
                decision_id="paper-1", contest_id=contest, generation=1,
                event_open_ms=300000, symbol="BTCUSDT", side="LONG",
                entry_time_ms=300001, entry_price=100, one_r_price=1,
            )
            first = report(root)
            self.assertIn("CONTEST #1", first)
            self.assertIn("1", first)
            self.assertIn("BTCUSDT LONG OPEN", first)
            store.close_trade("paper-1", net_r=1.25, mfe_r=1.5, mae_r=-.2,
                              exit_time_ms=600001, exit_reason="TAKE_PROFIT",
                              source_digest="digest")
            second = report(root, contest_id=contest)
            self.assertIn("+1.250R", second)
            self.assertIn("1/100", second)
            self.assertIn("1/1 positive", second)
            self.assertIn("BTCUSDT LONG CLOSED", second)
            self.assertEqual(store.contest_model_status(contest, 1)["completed_trades"], 1)


if __name__ == "__main__":
    unittest.main()
