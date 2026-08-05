import importlib
import os
import unittest
from unittest.mock import Mock, patch


class Log:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)


class TimeoutSocket:
    def recv(self):
        import websocket
        raise websocket.WebSocketTimeoutException("timeout")

    def close(self):
        pass


class Phase17ARestFallbackTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "TRADING_ENV": "LIVE",
                "EXECUTION_MODE": "SHADOW",
                "LIVE_BASE_URL": "https://fapi.binance.com",
                "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/ws/!ticker@arr",
                "PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS": "2",
                "PAPER_REST_POLL_INTERVAL_SECONDS": "0.5",
                "PAPER_WS_RETRY_INTERVAL_SECONDS": "30",
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

    def test_ws_timeout_switches_to_rest_and_yields_ticks(self):
        log = Log()
        client = self.module.BinanceMarketClient(system_log=log)
        client._public_get = Mock(return_value=[
            {"symbol": "BTCUSDT", "price": "62000.5"},
            {"symbol": "ETHUSDT", "price": "3400.1"},
        ])
        with patch.object(
            self.module.websocket,
            "create_connection",
            return_value=TimeoutSocket(),
        ), patch.object(self.module.time, "monotonic", side_effect=[0, 0, 31]), \
             patch.object(self.module.time, "sleep"):
            stream = client.price_stream()
            tick = next(stream)
        self.assertEqual(tick.symbol, "BTCUSDT")
        self.assertEqual(tick.price, 62000.5)
        self.assertTrue(any("PUBLIC_WS_FIRST_TICK_TIMEOUT" in x for x in log.warnings))
        self.assertTrue(any("PUBLIC_MARKET_REST_FALLBACK_ACTIVE" in x for x in log.warnings))
        self.assertTrue(any("PUBLIC_REST_FIRST_TICK_OK" in x for x in log.infos))

    def test_rest_parser_filters_invalid_rows(self):
        ticks = self.module.BinanceMarketClient._parse_rest_price_rows([
            {"symbol": "BTCUSDT", "price": "100"},
            {"symbol": "ETHBTC", "price": "1"},
            {"symbol": "BADUSDT", "price": "0"},
            {"symbol": "BROKENUSDT", "price": "bad"},
        ])
        self.assertEqual([(x.symbol, x.price) for x in ticks], [("BTCUSDT", 100.0)])

    def test_config_rejects_too_fast_rest_polling(self):
        import subprocess
        import sys

        env = os.environ.copy()
        env["PAPER_REST_POLL_INTERVAL_SECONDS"] = "0.1"
        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAPER_REST_POLL_INTERVAL_SECONDS", result.stderr)


if __name__ == "__main__":
    unittest.main()
