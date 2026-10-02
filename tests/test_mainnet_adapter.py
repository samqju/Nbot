from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot.exchange.binance_live import BinanceLiveExchange, LiveExchangeConfig, LiveTradingGuard, _NoRedirect
from nbot.exchange.binance_testnet import BinanceTestnetExchange, TestnetExchangeConfig, TestnetTradingGuard, TestnetExchangeError
from tests import test_v319_testnet as old


class LiveHarness(old.Harness, BinanceLiveExchange):
    hedge = False
    multi_asset = False

    def _request(self, method, path, params=None, **kwargs):
        if path == "/fapi/v1/positionSide/dual":
            self.calls.append((method, path, params, True, False))
            return {"dualSidePosition": self.hedge}
        if path == "/fapi/v1/multiAssetsMargin":
            self.calls.append((method, path, params, True, False))
            return {"multiAssetsMargin": self.multi_asset}
        return super()._request(method, path, params, **kwargs)


def armed(config, *, sha="abc", armed_at="2026-10-01T00:00:00Z"):
    path = config.resolved_arm_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"profile=live-trade\nsha={sha}\narmed_at={armed_at}\nauthorization=EXPLICIT_SMALL_MAINNET_TRIAL_V1\nsettings_digest={config.authorization_digest()}\n")
    LiveTradingGuard(config).initialize_new_arm_session()


def loaded(root, **overrides):
    values = dict(api_key="dummy", api_secret="dummy-secret", repo_root=root,
                  max_entry_notional_usd=100, max_session_entries=10,
                  entry_resolution_timeout_seconds=.01, stop_resolution_timeout_seconds=.01,
                  close_settlement_retries=1, close_settlement_retry_seconds=0)
    values.update(overrides)
    ex = LiveHarness(LiveExchangeConfig(**values))
    ex._load_filters()
    return ex


class MainnetConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = LiveExchangeConfig(api_key="dummy", api_secret="dummy", repo_root=Path(self.tmp.name))

    def test_mainnet_is_pinned_and_testnet_adapter_refuses_it(self):
        self.cfg.validate()
        self.assertEqual(self.cfg.base_url, "https://fapi.binance.com")
        with self.assertRaisesRegex(ValueError, "PROFILE_MISMATCH"):
            BinanceTestnetExchange(self.cfg)
        with self.assertRaisesRegex(ValueError, "PROFILE_MISMATCH"):
            BinanceLiveExchange(TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=self.cfg.repo_root))

    def test_host_and_path_rejection(self):
        for url in ["https://demo-fapi.binance.com", "http://fapi.binance.com",
                    "https://fapi.binance.com.evil.test", "https://fapi.binance.com/x",
                    "https://user@fapi.binance.com", "https://fapi.binance.com:443"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                replace(self.cfg, base_url=url).validate()

    def test_credentials_never_fall_back_to_testnet(self):
        cfg = LiveExchangeConfig.from_env(repo_root=self.cfg.repo_root,
                                         environ={"TESTNET_API_KEY":"x","TESTNET_API_SECRET":"y"})
        with self.assertRaisesRegex(ValueError, "LIVE_CREDENTIALS_MISSING"):
            cfg.validate()

    def test_foreign_state_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "STATE_PATH_OVERRIDE"):
            replace(self.cfg, arm_file=self.cfg.repo_root/"runtime/execution/testnet/TESTNET_TRADING_ARMED").validate()

    def test_nonfinite_configuration_rejected(self):
        for name in ["request_timeout_seconds", "max_entry_notional_usd",
                     "entry_resolution_timeout_seconds", "stop_resolution_timeout_seconds",
                     "close_settlement_retry_seconds"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(self.cfg, **{name:float("nan")}).validate()

    def test_redirect_is_not_followed(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test"))

    def test_testnet_arm_cannot_authorize_mainnet(self):
        cfg = self.cfg
        cfg.resolved_arm_file.parent.mkdir(parents=True)
        cfg.resolved_arm_file.write_text("profile=testnet-trade\nsha=abc\narmed_at=x\n")
        self.assertFalse(LiveTradingGuard(cfg).preflight()["armed"])

    def test_live_session_survives_restart_and_blocks_second_entry(self):
        cfg = self.cfg
        armed(cfg)
        g = LiveTradingGuard(cfg)
        g.authorize_entry(symbol="BTCUSDT", quantity=.1, price=100, position=None)
        restored = LiveTradingGuard(cfg)
        self.assertEqual(restored.preflight()["session_entries"], 1)
        with self.assertRaisesRegex(TestnetExchangeError, "SESSION_ENTRY_LIMIT"):
            restored.authorize_entry(symbol="BTCUSDT", quantity=.1, price=100, position=None)

    def test_missing_bound_session_fails_closed(self):
        armed(self.cfg)
        self.cfg.resolved_guard_state_path.unlink()
        self.assertFalse(LiveTradingGuard(self.cfg).preflight()["armed"])

    def test_incompatible_account_releases_instance_lock(self):
        for field in ["hedge", "multi_asset"]:
            ex = loaded(self.cfg.repo_root)
            setattr(ex, field, True)
            with self.subTest(field=field), self.assertRaises(TestnetExchangeError):
                ex.connect()
            self.assertFalse(ex._instance_lock.held)

    def test_connection_uses_only_reads_without_arming(self):
        ex = loaded(self.cfg.repo_root)
        ex.connect()
        self.addCleanup(ex.disconnect)
        self.assertTrue(ex.is_healthy())
        self.assertTrue(all(row[0]=="GET" for row in ex.calls))


class MainnetContractMixin:
    def setUp(self):
        super().setUp()
        for name, value in [("loaded_exchange", loaded), ("arm", armed), ("TestnetTradingGuard", LiveTradingGuard)]:
            p = patch.object(old, name, value)
            p.start()
            self.addCleanup(p.stop)


class MainnetEntryTests(MainnetContractMixin, old.V319EntryTests):
    def test_set_leverage_requires_arm(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded(Path(td))
            ex.guard.initialize_unarmed_state()
            with self.assertRaisesRegex(TestnetExchangeError, "NOT_ARMED"):
                ex.set_leverage("BTCUSDT", ex.config.leverage)

    def test_set_leverage_confirms_exchange_response(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded(Path(td))
            armed(ex.config)
            ex.set_leverage("BTCUSDT", ex.config.leverage)

    def test_unapproved_leverage_never_reaches_exchange(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded(Path(td))
            armed(ex.config)
            before = list(ex.calls)
            for leverage in (2, 5, 1.5, True):
                with self.subTest(leverage=leverage), self.assertRaisesRegex(
                        TestnetExchangeError, "LEVERAGE_OUTSIDE_APPROVED_SETTINGS"):
                    ex.set_leverage("BTCUSDT", leverage)
            self.assertEqual(ex.calls, before)


class MainnetStopTests(MainnetContractMixin, old.V319StopTests):
    pass


class MainnetCloseTests(MainnetContractMixin, old.V319CloseRecoveryTests):
    pass


class MainnetPreSubmitTests(MainnetContractMixin, old.V319PreSubmitRejectionTests):
    pass
