import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execution.binance_market_client import BinanceMarketClient
from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange


class Log:
    def __init__(self):
        self.infos = []
    def info(self, message):
        self.infos.append(message)
    def warning(self, message):
        pass


class FakeSession:
    def close(self):
        pass


class FakeMarket:
    def __init__(self):
        self.connected = False
        self.preflight_calls = []
    def connect(self):
        self.connected = True
    def preflight(self, *, symbol, candle_limit):
        self.preflight_calls.append((symbol, candle_limit))
        return {
            "environment": "LIVE", "auth": "NONE", "symbol": symbol,
            "last_price": 100.0, "spread_pct": 0.01,
            "completed_candles": candle_limit, "tick_size": 0.1,
        }
    def disconnect(self):
        pass


class Phase17PreflightTests(unittest.TestCase):
    def test_market_preflight_validates_public_functions(self):
        log = Log()
        with patch.dict("os.environ", {
            "LIVE_BASE_URL": "https://fapi.binance.com",
            "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/market/ws/!ticker@arr",
        }, clear=False):
            client = BinanceMarketClient(system_log=log)
        client._symbol_filters = {"BTCUSDT": {"tickSize": 0.1}}
        client.get_last_price = lambda symbol: 123.45
        client.get_current_spread_pct = lambda *, symbol: 0.02
        client.get_historical_candles = lambda **kwargs: [(1, 1, 1, 1, 1)] * 4
        report = client.preflight(symbol="BTCUSDT", candle_limit=5)
        self.assertEqual(report["auth"], "NONE")
        self.assertEqual(report["symbol"], "BTCUSDT")
        self.assertEqual(report["completed_candles"], 4)
        self.assertTrue(any("PUBLIC_MARKET_PREFLIGHT_OK" in x for x in log.infos))

    def test_paper_exchange_connect_runs_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = Log()
            market = FakeMarket()
            account = PaperAccount(
                starting_balance_usd=10000,
                state_path=str(root / "state.json"),
                trades_path=str(root / "trades.jsonl"),
                source="PAPER_LIVE",
            )
            exchange = PaperExchange(
                market_client=market, account=account, system_log=log
            )
            with patch("execution.paper_exchange.PAPER_PREFLIGHT_SYMBOL", "BTCUSDT"), \
                 patch("execution.paper_exchange.PAPER_PREFLIGHT_CANDLE_LIMIT", 5):
                report = exchange.connect()
            self.assertTrue(market.connected)
            self.assertEqual(market.preflight_calls, [("BTCUSDT", 5)])
            self.assertEqual(report["auth"], "NONE")
            self.assertTrue(any("PAPER_RUNTIME_PREFLIGHT_OK" in x for x in log.infos))

    def test_preflight_rejects_missing_symbol_filter(self):
        log = Log()
        with patch.dict("os.environ", {
            "LIVE_BASE_URL": "https://fapi.binance.com",
            "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/market/ws/!ticker@arr",
        }, clear=False):
            client = BinanceMarketClient(system_log=log)
        client._symbol_filters = {}
        with self.assertRaisesRegex(Exception, "PUBLIC_PREFLIGHT_SYMBOL_FILTER_MISSING"):
            client.preflight(symbol="BTCUSDT", candle_limit=5)

    def test_config_rejects_invalid_preflight_symbol(self):
        import os, subprocess, sys
        env = os.environ.copy()
        env.update({"PAPER_PREFLIGHT_SYMBOL": "BTCUSD", "TRADING_ENV": "LIVE", "EXECUTION_MODE": "SHADOW"})
        result = subprocess.run([sys.executable, "-c", "import config"], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAPER_PREFLIGHT_SYMBOL", result.stderr)


if __name__ == "__main__":
    unittest.main()
