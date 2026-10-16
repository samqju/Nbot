"""Offline tests for owner-gated REAL order permission. No exchange calls."""
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = ROOT / "user_data" / "strategies" / "NbotV6.py"
LIVE_CLI = ROOT / "scripts" / "owner_live_approval.py"
CONFIG = ROOT / "user_data" / "config.json"

if "freqtrade.strategy" not in sys.modules:
    sys.modules["freqtrade"] = types.ModuleType("freqtrade")
    s = types.ModuleType("freqtrade.strategy")
    s.IStrategy = type("IStrategy", (), {})
    sys.modules["freqtrade.strategy"] = s
spec = importlib.util.spec_from_file_location("nbot_v6_owner_strategy", STRATEGY)
strategy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strategy)
cmdspec = importlib.util.spec_from_file_location("nbot_v6_arm", LIVE_CLI)
arm = importlib.util.module_from_spec(cmdspec)
cmdspec.loader.exec_module(arm)


def live_config():
    config = json.loads(CONFIG.read_text())
    config.update(
        dry_run=False,
        nbot_live_mode=True,
        nbot_owner_telegram_id="123456789",
        max_open_trades=1,
        force_entry_enable=False,
        stake_amount=1000,
        db_url="sqlite:////freqtrade/user_data/tradesv3.live.sqlite",
    )
    config["exchange"]["key"] = "test-only-key"
    config["exchange"]["secret"] = "test-only-secret"
    config["freqai"]["identifier"] = "nbot-v6-approved-001"
    config["telegram"] = {
        "enabled": True,
        "token": "test-only-telegram-token",
        "chat_id": "123456789",
        "authorized_users": ["123456789"],
    }
    return config


class OwnerGateTests(unittest.TestCase):
    def setUp(self):
        self.config = live_config()
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.path = Path(self.sandbox.name) / "approval.json"
        self.patched_path = patch.object(strategy, "LIVE_ARM_PATH", self.path)
        self.patched_path.start()
        self.addCleanup(self.patched_path.stop)
        self.issued = 1_800_000_000
        self.now = 1_800_000_010

    def write_arm(self, *, issued=None, expires=None, model=None, owner=None):
        payload = arm.make_approval(
            owner or "123456789", model or "nbot-v6-approved-001", 8,
            self.issued if issued is None else issued
        )
        if expires is not None:
            payload["expires_at"] = expires
        self.path.write_text(json.dumps(payload))
        self.path.chmod(0o600)
        return payload

    def test_disarmed_by_default_and_never_starts(self):
        self.assertFalse(strategy.owner_live_authorized(self.config))
        bot = strategy.NbotV6()
        bot.config = self.config
        with self.assertRaisesRegex(RuntimeError, "OWNER_APPROVAL_REQUIRED"):
            bot.bot_start()

    def test_owner_can_arm_but_only_for_valid_time(self):
        self.write_arm()
        from datetime import datetime, timezone
        when = datetime.fromtimestamp(self.now, tz=timezone.utc)
        self.assertTrue(strategy.owner_live_authorized(self.config, now=when))
        later = datetime.fromtimestamp(self.issued + 28800, tz=timezone.utc)
        self.assertFalse(strategy.owner_live_authorized(self.config, now=later))
        self.path.unlink()
        self.assertFalse(strategy.owner_live_authorized(self.config, now=when))

    def test_reject_other_chats_groups_and_telegram_disabled(self):
        from datetime import datetime, timezone
        self.write_arm()
        moment = datetime.fromtimestamp(self.now, tz=timezone.utc)
        configs = []
        def modified(fn):
            c = json.loads(json.dumps(self.config))
            fn(c)
            configs.append(c)
        modified(lambda c: c["telegram"].update(chat_id="-100123456789"))
        modified(lambda c: c["telegram"].update(authorized_users=["987654321"]))
        modified(lambda c: c["telegram"].update(authorized_users=["123456789", "987654321"]))
        modified(lambda c: c["telegram"].update(enabled=False))
        modified(lambda c: c.update(nbot_owner_telegram_id="987654321"))
        modified(lambda c: c["telegram"].update(token=""))
        for c in configs:
            self.assertFalse(strategy.owner_live_authorized(c, now=moment))

    def test_reject_invalid_risk_and_config_changes(self):
        from datetime import datetime, timezone
        self.write_arm()
        moment = datetime.fromtimestamp(self.now, tz=timezone.utc)
        changes = [
            lambda c: c.update(max_open_trades=2),
            lambda c: c.update(stake_amount=1001),
            lambda c: c.update(stake_amount="unlimited"),
            lambda c: c.update(nbot_live_mode=False),
            lambda c: c.update(nbot_paper_research_mode=True),
            lambda c: c.update(dry_run=True),
            lambda c: c.update(force_entry_enable=True),
            lambda c: c.update(trading_mode="spot"),
            lambda c: c["api_server"].update(enabled=True),
            lambda c: c["exchange"].update(secret=""),
            lambda c: c["freqai"].update(identifier="unapproved-model"),
            lambda c: c["freqai"].update(expiration_hours=0),
        ]
        for f in changes:
            config = json.loads(json.dumps(self.config))
            f(config)
            self.assertFalse(strategy.owner_live_authorized(config, now=moment))

    def test_expired_long_and_wrong_permissions_fail(self):
        from datetime import datetime, timezone
        self.write_arm()
        moment = datetime.fromtimestamp(self.now, tz=timezone.utc)
        self.path.chmod(0o644)
        self.assertFalse(strategy.owner_live_authorized(self.config, now=moment))
        self.path.chmod(0o600)
        contents = json.loads(self.path.read_text())
        contents["expires_at"] = self.issued + 86401
        self.path.write_text(json.dumps(contents))
        self.assertFalse(strategy.owner_live_authorized(self.config, now=moment))
        contents["expires_at"] = self.issued + 1
        self.path.write_text(json.dumps(contents))
        self.assertFalse(strategy.owner_live_authorized(self.config, now=moment))

    def test_live_entry_callback_checks_again_without_blocking_exit(self):
        from datetime import datetime, timezone
        bot = strategy.NbotV6()
        bot.config = self.config
        self.write_arm()
        # The entry hook must deny once revoked, even if the process was live.
        self.path.unlink()
        self.assertFalse(bot.confirm_trade_entry(
            "BTC/USDT:USDT", "limit", 1000, 1000, "gtc", None, None, "long"
        ))
        # No global stop method or exit callback is overridden by this gate.
        self.assertFalse(hasattr(strategy.NbotV6, "confirm_trade_exit"))

    def test_owner_cli_uses_explicit_challenge_and_protects_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "secrets"
            with patch.object(arm, "PRIVATE_DIR", target), patch.object(arm, "APPROVAL", target / "approval.json"):
                with patch("builtins.input", return_value="NO"):
                    self.assertEqual(arm.main([
                        "--arm", "--owner-telegram-id", "123456789",
                        "--model-identifier", "nbot-v6-approved-001"
                    ]), 1)
                self.assertFalse((target / "approval.json").exists())
                with patch("builtins.input", return_value=arm.CHALLENGE):
                    self.assertEqual(arm.main([
                        "--arm", "--owner-telegram-id", "123456789",
                        "--model-identifier", "nbot-v6-approved-001"
                    ]), 0)
                self.assertEqual((target / "approval.json").stat().st_mode & 0o777, 0o600)
                self.assertEqual(target.stat().st_mode & 0o777, 0o700)
                self.assertEqual(arm.main(["--revoke"]), 0)
                self.assertFalse((target / "approval.json").exists())


if __name__ == "__main__":
    unittest.main()
