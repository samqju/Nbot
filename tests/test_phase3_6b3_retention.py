import unittest

from strategy.strategy import Strategy


class FakeVirtualEngine:
    def active_symbols(self):
        return {"ETHUSDT", "SOLUSDT"}


class Phase36B3RetentionTests(unittest.TestCase):
    def test_retained_symbols_include_pending_and_virtual(self):
        strategy = Strategy()
        strategy._virtual_trade_engine = FakeVirtualEngine()
        strategy._pending_simulations = [
            {"symbol": "BTCUSDT"},
            {"symbol": "ETHUSDT"},
            {"symbol": None},
        ]

        self.assertEqual(
            strategy.get_retained_observation_symbols(),
            {"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        )


if __name__ == "__main__":
    unittest.main()
