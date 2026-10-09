"""Chronological paths with identical OHLC can have opposite stop outcomes."""
import unittest

from nbot.observation.chronological_replay import (
    PathQuality, TradeEvent, replay_integer_r_tick_policy,
)


def events(prices):
    return [TradeEvent("METUSDT", i, 1000 + i, p) for i, p in enumerate(prices)]


class ChronologicalReplayTests(unittest.TestCase):
    def run_path(self, prices, side="LONG"):
        return replay_integer_r_tick_policy(
            events(prices), symbol="METUSDT", side=side,
            entry_price=100, one_r_price=1, entry_time_ms=1000,
        )

    def test_stop_before_rally(self):
        result = self.run_path([100, 99, 103, 102])
        self.assertEqual(result.exit_reason, "STOP")
        self.assertEqual(result.gross_r, -1)

    def test_rally_before_stop(self):
        result = self.run_path([100, 101, 102, 103, 102, 99])
        self.assertEqual(result.exit_reason, "STOP")
        self.assertEqual(result.gross_r, 2)
        self.assertEqual(result.stop_r, 2)

    def test_short_path(self):
        result = self.run_path([100, 99, 98, 99], "SHORT")
        self.assertEqual(result.gross_r, 1)

    def test_out_of_order_is_not_labelled_resolved(self):
        result = self.run_path([100, 101])
        self.assertEqual(result.quality, PathQuality.AGGTRADE_RESOLVED)
        bad = [TradeEvent("METUSDT", 2, 1002, 100),
               TradeEvent("METUSDT", 1, 1001, 101)]
        result = replay_integer_r_tick_policy(
            bad, symbol="METUSDT", side="LONG",
            entry_price=100, one_r_price=1, entry_time_ms=1000,
        )
        self.assertEqual(result.quality, PathQuality.GAP_UNRESOLVED)
        self.assertIsNone(result.gross_r)

    def test_bad_price(self):
        with self.assertRaises(ValueError):
            TradeEvent("METUSDT", 1, 1000, 0)


if __name__ == "__main__":
    unittest.main()
