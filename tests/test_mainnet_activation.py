import importlib.machinery
import importlib.util
import tempfile
import unittest
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from nbot.exchange.binance_live import LiveExchangeConfig, LiveTradingGuard
from nbot.execution.ownership import execution_ownership, require_profile_flat
from nbot.execution.state import ExecutionStatePaths, ExecutionStateStore
from nbot.config.validation import MachineRole, forbidden_observation_secrets
from tests.test_mainnet_adapter import armed
from nbot.exchange.binance_testnet import _InstanceLock

REPO = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("mainnet_test_ctl", str(REPO/"nbotctl"))
spec = importlib.util.spec_from_loader(loader.name, loader)
ctl = importlib.util.module_from_spec(spec)
loader.exec_module(ctl)


class MainnetActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = LiveExchangeConfig(api_key="dummy", api_secret="dummy", repo_root=self.root)

    def test_settings_and_api_identity_change_invalidate_approval(self):
        armed(self.cfg)
        for changes in [{"api_key":"different"}, {"risk_per_trade_usd":.5},
                        {"max_entry_notional_usd":50}, {"max_session_entries":2}, {"leverage":2}]:
            with self.subTest(changes=changes):
                self.assertFalse(LiveTradingGuard(replace(self.cfg, **changes)).preflight()["armed"])

    def test_small_trial_caps_cannot_be_disabled_with_configuration(self):
        for changes in [{"risk_per_trade_usd":2}, {"max_entry_notional_usd":101},
                        {"max_session_entries":11}, {"leverage":3}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.cfg, **changes).validate()

    def test_observation_rejects_real_credentials(self):
        self.assertIn("LIVE_API_KEY", forbidden_observation_secrets({"LIVE_API_KEY":"dummy"}))
        self.assertIn("LIVE_API_SECRET", forbidden_observation_secrets({"LIVE_API_SECRET":"dummy"}))

    def test_mainnet_arm_requires_explicit_real_money_confirmation(self):
        with patch.object(ctl, "ROOT", self.root), patch.object(ctl, "detect_role", return_value=MachineRole.EXECUTION):
            with self.assertRaisesRegex(ValueError, "CONFIRM_REAL_MONEY"):
                ctl.cmd_arm(Namespace(profile="live-trade", confirm_real_money=False))
        self.assertFalse(self.cfg.resolved_arm_file.exists())

    def test_arm_binds_settings_and_session_without_network_or_entries(self):
        env = {"LIVE_API_KEY":"dummy", "LIVE_API_SECRET":"dummy"}
        with patch.object(ctl, "ROOT", self.root), patch.object(ctl, "detect_role", return_value=MachineRole.EXECUTION), patch.object(ctl, "_secret_environment", return_value=env), patch.object(ctl, "_git_identity", return_value={"sha":"a"*40}), patch.object(ctl.subprocess, "check_output", return_value=""):
            ctl.cmd_arm(Namespace(profile="live-trade", confirm_real_money=True))
        self.assertTrue(LiveTradingGuard(self.cfg).preflight()["armed"])
        self.assertEqual(LiveTradingGuard(self.cfg).preflight()["session_entries"], 0)

    def test_global_runtime_lock_prevents_another_mode(self):
        with execution_ownership(self.root, "testnet-trade"):
            with self.assertRaises(Exception):
                with execution_ownership(self.root, "live-trade"):
                    self.fail("second mode acquired ownership")

    def test_legacy_mode_lock_prevents_mainnet(self):
        lock = _InstanceLock(self.root/"runtime/execution/testnet/execution.lock")
        lock.acquire()
        self.addCleanup(lock.release)
        with self.assertRaises(Exception):
            with execution_ownership(self.root, "live-trade"):
                self.fail("legacy worker ignored")

    def test_enabled_stopped_profile_blocks_switch(self):
        paths = ExecutionStatePaths.for_profile(self.root, "live-paper")
        store = ExecutionStateStore(paths.state_file, profile="live-paper", market_environment="LIVE")
        store.set_entries_enabled(True)
        with self.assertRaisesRegex(ValueError, "NOT_SAFELY_STOPPED"):
            with execution_ownership(self.root, "live-trade"):
                self.fail("enabled profile ignored")
