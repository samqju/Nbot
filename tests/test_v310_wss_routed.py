import unittest

from nbot.exchange.contracts import Quote
from nbot.exchange.routed import MarketRoutedExchange


class _Capital:
    def __init__(self):
        self.seen = None
        self.legacy_calls = 0

    def validate_protective_stop_against_quote(self, symbol, side, stop_price, quote):
        self.seen = (symbol, side, stop_price, quote)
        return quote.symbol == symbol and quote.bid > stop_price

    def validate_protective_stop(self, symbol, side, stop_price):
        self.legacy_calls += 1
        raise AssertionError("REST-backed legacy validation must not be used")


class _Market:
    def __init__(self):
        self.calls = []

    def quote(self, symbol):
        self.calls.append(symbol)
        return Quote(symbol, 100.0, 100.1, 1_000)


class RoutedMarketTests(unittest.TestCase):
    def test_stop_feasibility_uses_wss_market_quote(self):
        capital = _Capital()
        market = _Market()
        routed = MarketRoutedExchange(capital=capital, market=market)
        self.assertTrue(routed.validate_protective_stop("BTCUSDT", "LONG", 99.0))
        self.assertEqual(market.calls, ["BTCUSDT"])
        self.assertEqual(capital.legacy_calls, 0)
        self.assertEqual(capital.seen[3].bid, 100.0)


if __name__ == "__main__":
    unittest.main()
