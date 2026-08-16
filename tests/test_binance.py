import unittest

from nbot.binance import latest_closed_open_time_ms, spread_pct


class BinanceHelpersTests(unittest.TestCase):
    def test_latest_closed_candle(self):
        self.assertEqual(latest_closed_open_time_ms(900_001, 300_000), 600_000)

    def test_spread_is_percentage(self):
        self.assertAlmostEqual(spread_pct(99.0, 101.0), 2.0)

    def test_invalid_spread_rejected(self):
        with self.assertRaises(ValueError):
            spread_pct(101.0, 100.0)


if __name__ == "__main__":
    unittest.main()
