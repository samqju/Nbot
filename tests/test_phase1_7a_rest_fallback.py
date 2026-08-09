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


class Monitor:
    def __init__(self):
        self.counters = []
        self.timings = []

    def increment(self, name, amount=1):
        self.counters.append((name, amount))

    def observe_ms(self, name, value):
        self.timings.append((name, float(value)))


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
                "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/market/ws/!ticker@arr",
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


    def test_position_stream_url_targets_exact_symbol(self):
        client = self.module.BinanceMarketClient(system_log=Log())
        self.assertEqual(
            client._position_stream_url("MMTUSDT"),
            "wss://fstream.binance.com/market/ws/mmtusdt@ticker",
        )

    def test_position_stream_parses_single_symbol_ticker(self):
        import json

        class OneTickSocket:
            def __init__(self):
                self.closed = False

            def recv(self):
                return json.dumps({"s": "MMTUSDT", "c": "0.2143"})

            def close(self):
                self.closed = True

        socket = OneTickSocket()
        log = Log()
        client = self.module.BinanceMarketClient(system_log=log)
        with patch.object(
            self.module.websocket,
            "create_connection",
            return_value=socket,
        ) as create:
            stream = client.position_price_stream("MMTUSDT")
            tick = next(stream)
            stream.close()

        self.assertEqual(tick.symbol, "MMTUSDT")
        self.assertEqual(tick.price, 0.2143)
        self.assertIn("mmtusdt@ticker", create.call_args.args[0])
        self.assertTrue(
            any("PUBLIC_POSITION_WS_FIRST_TICK_OK" in x for x in log.infos)
        )

    def test_position_ws_timeout_falls_back_to_target_symbol_only(self):
        log = Log()
        monitor = Monitor()
        client = self.module.BinanceMarketClient(system_log=log)
        client.set_execution_health_monitor(monitor)
        client.get_last_price = Mock(return_value=0.2141)

        with patch.object(
            self.module.websocket,
            "create_connection",
            return_value=TimeoutSocket(),
        ):
            stream = client.position_price_stream("MMTUSDT")
            tick = next(stream)
            stream.close()

        self.assertEqual((tick.symbol, tick.price), ("MMTUSDT", 0.2141))
        client.get_last_price.assert_called_once_with("MMTUSDT")
        self.assertTrue(
            any("PUBLIC_POSITION_WS_TIMEOUT" in x for x in log.warnings)
        )
        self.assertTrue(
            any(
                "PUBLIC_POSITION_REST_FALLBACK_ACTIVE" in x
                for x in log.warnings
            )
        )
        self.assertFalse(
            any("REST_REFRESH" in x for x in log.infos)
        )
        self.assertIn(("position_ws_disconnects", 1), monitor.counters)
        self.assertIn(("position_rest_fallback_success", 1), monitor.counters)
        self.assertTrue(
            any(name == "position_rest_fallback_ms" for name, _ in monitor.timings)
        )

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
