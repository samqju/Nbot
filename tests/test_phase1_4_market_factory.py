import importlib
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class NullLog:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class Phase14MarketClientTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "TRADING_ENV": "LIVE",
                "EXECUTION_MODE": "SHADOW",
                "LIVE_BASE_URL": "https://fapi.binance.com",
                "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/market/ws/!ticker@arr",
            },
            clear=False,
        )
        self.env.start()
        import config
        import execution.binance_market_client as module
        importlib.reload(config)
        self.module = importlib.reload(module)

    def tearDown(self):
        self.env.stop()

    def test_connect_uses_public_endpoints_and_loads_tick_size(self):
        client = self.module.BinanceMarketClient(system_log=NullLog())
        client.session.get = Mock(side_effect=[
            FakeResponse({}),
            FakeResponse({
                "symbols": [{
                    "symbol": "BTCUSDT",
                    "filters": [{"filterType": "PRICE_FILTER", "tickSize": "0.10"}],
                }]
            }),
        ])
        client.connect()
        self.assertEqual(client.quantize_price("BTCUSDT", 100.27), 100.2)
        for call in client.session.get.call_args_list:
            self.assertNotIn("signature", call.kwargs.get("params", {}))

    def test_wrong_live_host_is_rejected(self):
        with patch.dict(os.environ, {"LIVE_BASE_URL": "https://demo-fapi.binance.com"}):
            with self.assertRaisesRegex(RuntimeError, "LIVE_REST_HOST_UNEXPECTED"):
                self.module.BinanceMarketClient(system_log=NullLog())

    def test_historical_candles_exclude_open_candle(self):
        client = self.module.BinanceMarketClient(system_log=NullLog())
        now = 10_000
        client._public_get = Mock(return_value=[
            [1, "100", "110", "90", "105", "0", 9_000],
            [2, "105", "111", "100", "108", "0", 11_000],
        ])
        with patch.object(self.module.time, "time", return_value=10):
            candles = client.get_historical_candles(
                symbol="BTCUSDT", interval="5m", limit=2,
            )
        self.assertEqual(candles, [(1, 100.0, 110.0, 90.0, 105.0)])


class Phase14FactoryTests(unittest.TestCase):
    def _run_factory(self, **overrides):
        env = os.environ.copy()
        # These tests validate exchange routing, not the temporary
        # paper-test strategy safety gate.
        env["STRATEGY_MODE"] = "STRUCTURE"
        env.update(overrides)
        code = r'''
from unittest.mock import patch
class Log:
    def __getattr__(self, name): return lambda *a, **k: None
class Market:
    def __init__(self, **kwargs): pass
class Account:
    def __init__(self, **kwargs): self.kwargs = kwargs
class Paper:
    def __init__(self, **kwargs): self.kwargs = kwargs
with patch("execution.exchange_factory.BinanceMarketClient", Market), \
     patch("execution.exchange_factory.PaperAccount", Account), \
     patch("execution.exchange_factory.PaperExchange", Paper):
    from execution.exchange_factory import build_exchange
    exchange = build_exchange(system_log=Log())
    print(type(exchange).__name__, exchange.kwargs["account"].kwargs["source"])
'''
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_live_shadow_selects_paper_live(self):
        result = self._run_factory(
            TRADING_ENV="LIVE",
            EXECUTION_MODE="SHADOW",
            LIVE_BASE_URL="https://fapi.binance.com",
            LIVE_MARKET_WS_URL="wss://fstream.binance.com/market/ws/!ticker@arr",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Paper PAPER_LIVE", result.stdout)

    def test_testnet_shadow_selects_paper_testnet(self):
        result = self._run_factory(
            TRADING_ENV="TESTNET",
            EXECUTION_MODE="SHADOW",
            TESTNET_BASE_URL="https://demo-fapi.binance.com",
            TESTNET_MARKET_WS_URL="wss://stream.binancefuture.com/ws/!ticker@arr",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Paper PAPER_TESTNET", result.stdout)

    def test_live_trade_remains_fail_closed(self):
        env = os.environ.copy()
        env.update({
            "TRADING_ENV": "LIVE",
            "EXECUTION_MODE": "TRADE",
            "LIVE_TRADING_CONFIRMATION": "I_ACCEPT_REAL_MONEY_EXECUTION",
            "LIVE_API_KEY": "NBOT_UNIT_TEST_KEY",
            "LIVE_API_SECRET": "NBOT_UNIT_TEST_SECRET",
            "STRATEGY_MODE": "STRUCTURE",
        })
        result = subprocess.run(
            [sys.executable, "-c", "from execution.exchange_factory import build_exchange; build_exchange(system_log=type('L',(),{'info':lambda *a:None})())"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
