import json
import unittest

from nbot.exchange.binance_stream import (
    AggTrade,
    BinanceLiveStreamConfig,
    BinanceLiveStreamError,
    BinanceLiveWebSocketMarketData,
    QuoteUpdate,
)


class _Rest:
    def __init__(self):
        self.connected = False
        self.recovery_calls = []

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def quote(self, symbol):
        self.recovery_calls.append(symbol)
        from nbot.exchange.contracts import Quote
        return Quote(symbol, 99.0, 101.0, 1_000)


class _WS:
    def __init__(self):
        self.sent = []

    def send(self, value):
        self.sent.append(json.loads(value))


class BinanceStreamTests(unittest.TestCase):
    def test_book_ticker_is_primary_and_subscription_is_dynamic(self):
        clock = [1_000]
        market = BinanceLiveWebSocketMarketData(
            BinanceLiveStreamConfig(max_quote_age_ms=2_000),
            rest_recovery=_Rest(),
            now_ms_fn=lambda: clock[0],
        )
        ws = _WS()
        market._ws = ws
        market._connected.set()
        market.subscribe("BTCUSDT")
        self.assertEqual(ws.sent[0]["params"], ["btcusdt@bookTicker"])
        market._on_message(ws, json.dumps({
            "e": "bookTicker", "E": 1_000, "s": "BTCUSDT",
            "b": "100.0", "a": "100.1",
        }))
        update = market.wait_quote("BTCUSDT", timeout_seconds=.01)
        self.assertEqual(update.quote.bid, 100.0)
        self.assertEqual(update.quote.ask, 100.1)
        self.assertEqual(market._rest.recovery_calls, [])

    def test_repeated_quote_calls_require_new_wss_sequence(self):
        market = BinanceLiveWebSocketMarketData(
            BinanceLiveStreamConfig(),
            rest_recovery=_Rest(),
            now_ms_fn=lambda: 2_000,
        )
        after = []
        def wait(symbol, *, after_sequence=0, timeout_seconds=None):
            after.append(after_sequence)
            seq = len(after)
            return QuoteUpdate(seq, Quote(symbol, 100.0, 100.1, 2_000), 2_000)
        from nbot.exchange.contracts import Quote
        market.wait_quote = wait
        market.quote("BTCUSDT")
        market.quote("BTCUSDT")
        self.assertEqual(after, [0, 1])

    def test_stale_wss_quote_fails_instead_of_silent_rest_entry_fallback(self):
        clock = [10_000]
        rest = _Rest()
        market = BinanceLiveWebSocketMarketData(
            BinanceLiveStreamConfig(max_quote_age_ms=500, first_event_timeout_seconds=.1),
            rest_recovery=rest,
            now_ms_fn=lambda: clock[0],
        )
        ws = _WS()
        market._ws = ws
        market._connected.set()
        market._on_message(ws, json.dumps({
            "e": "bookTicker", "E": 1_000, "s": "BTCUSDT",
            "b": "100", "a": "101",
        }))
        with self.assertRaises(BinanceLiveStreamError):
            market.wait_quote("BTCUSDT", timeout_seconds=.01)
        self.assertEqual(rest.recovery_calls, [])
        recovered = market.recovery_quote("BTCUSDT")
        self.assertEqual(recovered.bid, 99.0)
        self.assertEqual(rest.recovery_calls, ["BTCUSDT"])

    def test_aggtrade_listener_gets_chronological_trade_fields(self):
        market = BinanceLiveWebSocketMarketData(
            BinanceLiveStreamConfig(enable_book_ticker=False, enable_agg_trade=True),
            rest_recovery=_Rest(),
            now_ms_fn=lambda: 2_000,
        )
        seen = []
        market.add_trade_listener(seen.append)
        market._on_message(_WS(), json.dumps({
            "e": "aggTrade", "E": 1_999, "s": "ETHUSDT", "a": 7,
            "p": "2500.5", "q": "0.2", "f": 10, "l": 11,
            "T": 1_998, "m": True,
        }))
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], AggTrade)
        self.assertEqual(seen[0].trade_time_ms, 1_998)
        self.assertTrue(seen[0].buyer_is_maker)

    def test_config_pins_binance_host(self):
        with self.assertRaises(ValueError):
            BinanceLiveStreamConfig(ws_url="wss://example.invalid/ws").validate()


if __name__ == "__main__":
    unittest.main()
