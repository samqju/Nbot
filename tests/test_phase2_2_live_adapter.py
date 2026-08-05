import os
import unittest
from unittest.mock import Mock, patch

from execution.exchange_contract import inspect_exchange_adapter
from execution.live_exchange import LiveExchange


class Response:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.text = str(data)
    def json(self):
        return self._data


class Log:
    def __init__(self):
        self.infos = []
    def info(self, message):
        self.infos.append(message)


class Market:
    def price_stream(self): return iter(())
    def get_historical_candles(self, **kwargs): return []
    def get_current_spread_pct(self, **kwargs): return 0.01
    def get_last_price(self, symbol): return 100.0
    def quantize_price(self, symbol, price): return price



class UserStream:
    ready_timeout_seconds = 20.0
    def __init__(self):
        self.started = False
        self.stopped = False
    def start(self): self.started = True
    def stop(self): self.stopped = True
    def wait_ready(self, timeout=None): return True
    def is_healthy(self): return True
    def drain_events(self, limit=None): return []


class Phase22LiveAdapterTests(unittest.TestCase):
    def _exchange(self, responses=None):
        session = Mock()
        session.headers = {}
        session.get.side_effect = responses or [
            Response({}),
            Response({"availableBalance": "100"}),
        ]
        env = {
            "LIVE_API_KEY": "key",
            "LIVE_API_SECRET": "secret",
            "LIVE_BASE_URL": "https://fapi.binance.com",
        }
        with patch.dict(os.environ, env, clear=False):
            return LiveExchange(
                Log(),
                session=session,
                market_client=Market(),
                user_stream=UserStream(),
            )

    def test_live_adapter_satisfies_formal_contract(self):
        exchange = self._exchange()
        report = inspect_exchange_adapter(exchange)
        self.assertTrue(report.valid, report.missing_methods)

    def test_connect_uses_public_and_signed_get_only(self):
        exchange = self._exchange([Response({}), Response({"assets": []})])
        exchange.connect()
        self.assertTrue(exchange._connected)
        self.assertEqual(exchange.session.get.call_count, 2)
        self.assertTrue(exchange.user_stream.started)
        self.assertTrue(exchange.is_user_stream_healthy())
        self.assertTrue(any("READ_ONLY_CONNECTED" in x for x in exchange.system_log.infos))

    def test_balance_and_position_are_read_only_queries(self):
        exchange = self._exchange([
            Response([{"asset": "USDT", "availableBalance": "321.5"}]),
            Response([{"symbol": "BTCUSDT", "positionAmt": "0"}]),
        ])
        self.assertEqual(exchange.get_available_balance(), 321.5)
        self.assertIsNone(exchange.get_position())

    def test_every_account_changing_method_is_blocked(self):
        exchange = self._exchange()
        operations = [
            ("set_leverage", {"symbol": "BTCUSDT", "leverage": 5}),
            ("enforce_leverage_for_universe", {"symbols": ["BTCUSDT"]}),
            ("place_entry", {}),
            ("resolve_ambiguous_entry", {}),
            ("place_initial_sl", {}),
            ("update_sl", {}),
            ("cancel_pending_entries", {}),
            ("emergency_exit", {}),
        ]
        for name, kwargs in operations:
            with self.subTest(operation=name):
                with self.assertRaisesRegex(RuntimeError, "LIVE_ADAPTER_READ_ONLY"):
                    getattr(exchange, name)(**kwargs)

    def test_mainnet_host_is_enforced(self):
        env = {
            "LIVE_API_KEY": "key",
            "LIVE_API_SECRET": "secret",
            "LIVE_BASE_URL": "https://demo-fapi.binance.com",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(RuntimeError, "LIVE_REST_HOST_UNEXPECTED"):
                LiveExchange(Log(), session=Mock(), market_client=Market())


if __name__ == "__main__":
    unittest.main()
