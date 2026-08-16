import unittest

from nbot.binance import BinancePublicClient, Candle, latest_closed_open_time_ms, spread_pct, validate_candle
from nbot.config import CONFIG


class FakeBinance(BinancePublicClient):
    def _get(self, path, params=None):
        if path == "/fapi/v1/klines":
            start = int(params["startTime"])
            interval = CONFIG.candle_interval_ms
            limit = int(params["limit"])
            return [
                [
                    start + i * interval,
                    "100", "102", "99", "101", "10",
                    start + (i + 1) * interval - 1,
                    "1000", 20, "5", "500", "0",
                ]
                for i in range(limit)
            ]
        if path == "/fapi/v1/fundingRate":
            return [
                {"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.0001", "markPrice": "100"},
                {"symbol": "ETHUSDT", "fundingTime": 1000, "fundingRate": "-0.0002", "markPrice": "50"},
            ]
        raise AssertionError(path)


class BinanceHelpersTests(unittest.TestCase):
    def test_latest_closed_candle(self):
        self.assertEqual(latest_closed_open_time_ms(900_001, 300_000), 600_000)

    def test_spread_is_percentage(self):
        self.assertAlmostEqual(spread_pct(99.0, 101.0), 2.0)

    def test_invalid_spread_rejected(self):
        with self.assertRaises(ValueError):
            spread_pct(101.0, 100.0)

    def test_malformed_candle_rejected(self):
        bad = Candle("BTCUSDT", 0, 299_999, 100, 99, 98, 100.5, 1, 1, 1, 1, 1)
        with self.assertRaises(ValueError):
            validate_candle(bad)

    def test_historical_range_is_canonical(self):
        client = FakeBinance(CONFIG)
        rows = client.historical_candles("BTCUSDT", 0, 600_000)
        self.assertEqual(sorted(rows), [0, 300_000, 600_000])
        self.assertEqual(rows[300_000].close_price, 101.0)

    def test_funding_history_is_timestamped(self):
        client = FakeBinance(CONFIG)
        rows = client.funding_history(0, 2000)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].funding_time_ms, 1000)


if __name__ == "__main__":
    unittest.main()
