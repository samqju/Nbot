"""No-network tests for the V6 historical bootstrap helper."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "bootstrap_history.py"
spec = importlib.util.spec_from_file_location("nbot_history_bootstrap", path)
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
CONFIG = json.loads((ROOT / "user_data" / "config.json").read_text())


class HistoryBootstrapTests(unittest.TestCase):
    def test_default_requests_60_days_with_btc(self):
        plan = boot.build_plan(["SOL", "NEAR/USDT:USDT"], 60, CONFIG)
        self.assertEqual(plan["requested_pairs"], [
            "SOL/USDT:USDT", "NEAR/USDT:USDT", "BTC/USDT:USDT"
        ])
        self.assertEqual(plan["rolling_training_days"], 30)
        self.assertEqual(plan["state"], "PLAN_ONLY")
        dl = plan["commands"]["download"]
        self.assertEqual(dl[:8], [
            "docker", "compose", "--profile", "research", "run", "--rm",
            "paper-research", "download-data",
        ])
        self.assertIn("--trading-mode", dl)
        self.assertEqual(dl[dl.index("--trading-mode") + 1], "futures")
        self.assertEqual(dl[dl.index("--days") + 1], "60")
        self.assertEqual(dl[dl.index("--timeframes") + 1:dl.index("--timeframes") + 3],
                         ["5m", "1h"])
        self.assertIn("list-data", plan["commands"]["inspect_local_ranges"])
        self.assertIn("--show-timerange", plan["commands"]["inspect_local_ranges"])

    def test_maximum_10_new_pairs_and_deduplication(self):
        symbols = [f"T{i:02d}" for i in range(10)]
        got = boot.candidate_pairs(symbols + ["T01", "BTC"])
        self.assertEqual(len(got), 11)
        self.assertEqual(got.count("BTC/USDT:USDT"), 1)
        with self.assertRaisesRegex(ValueError, "At most 10"):
            boot.candidate_pairs(symbols + ["T10"])

    def test_reject_invalid_pair_injection_and_wrong_market(self):
        bad = ["eth", "ETH/USDT", "BTC/USDC:USDC", "ETH;rm -rf x", "SOL/USDT:USDT --erase"]
        for pair in bad:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                boot.candidate_pairs([pair])

    def test_cannot_download_without_minimum_training_plus_warmup(self):
        self.assertEqual(boot.minimum_history_days(CONFIG), 45)
        for days in [0, 30, 44, 181]:
            with self.subTest(days=days), self.assertRaises(ValueError):
                boot.build_plan(["SOL"], days, CONFIG)
        self.assertEqual(boot.build_plan(["SOL"], 45, CONFIG)["requested_history_days"], 45)

    def test_refuses_live_config_and_missing_btc_context(self):
        for mutate in [
            lambda c: c.update(dry_run=False),
            lambda c: c["freqai"]["feature_parameters"].update(include_corr_pairlist=[]),
            lambda c: c.update(trading_mode="spot"),
            lambda c: c["exchange"].update(name="other"),
        ]:
            conf = json.loads(json.dumps(CONFIG))
            mutate(conf)
            with self.assertRaises(ValueError):
                boot.build_plan(["SOL"], 60, conf)

    def test_default_cli_does_not_touch_exchange_or_spawn_process(self):
        with patch.object(boot.subprocess, "run") as run:
            self.assertEqual(boot.main(["--pair", "SOL"]), 0)
            run.assert_not_called()

    def test_execute_uses_official_commands_but_does_not_enable_coin(self):
        with patch.object(boot.subprocess, "run") as run, \
             patch.object(boot.Path, "write_text") as writer, \
             patch.object(boot.Path, "mkdir") as mkdir:
            self.assertEqual(boot.main(["--pair", "SOL", "--execute"]), 0)
            self.assertEqual(run.call_count, 2)
            cmd1 = run.call_args_list[0].args[0]
            cmd2 = run.call_args_list[1].args[0]
            self.assertIn("download-data", cmd1)
            self.assertIn("list-data", cmd2)
            for item in (cmd1, cmd2):
                self.assertNotIn("trade", item)
                self.assertNotIn("start", item)
                self.assertNotIn("--erase", item)
                self.assertIn("--config", item)
            manifest = json.loads(writer.call_args.args[0])
            self.assertEqual(manifest["state"], "DOWNLOADED_UNVERIFIED")
            self.assertEqual(manifest["requested_history_days"], 60)
            mkdir.assert_called_once()

    def test_download_failure_is_not_marked_ready(self):
        import subprocess
        with patch.object(boot.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "docker")), \
             patch.object(boot.Path, "write_text") as writer:
            self.assertEqual(boot.main(["--pair", "SOL", "--execute"]), 1)
            writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
