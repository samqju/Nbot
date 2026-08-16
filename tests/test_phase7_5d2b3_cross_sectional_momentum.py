import unittest

from strategy.cross_sectional_momentum import (
    AUTHORITY,
    DIRECTION,
    STRATEGY_ID,
    build_liquid_winner_signals,
    is_stablecoin_symbol,
    measure_symbol,
)


DAY = 86_400_000


def history(*, days=190, start_close=100.0, daily_growth=0.001, volume=1_000_000.0, as_of=None):
    if as_of is None:
        as_of = (days + 2) * DAY
    rows = []
    close = float(start_close)
    for index in range(days):
        open_ms = index * DAY + 1
        close_ms = (index + 1) * DAY - 1
        close *= (1.0 + float(daily_growth))
        rows.append({
            "open_time_ms": open_ms,
            "close_time_ms": close_ms,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "base_volume": 10.0,
            "quote_volume": float(volume),
            "trade_count": 100,
        })
    return rows


class Phase75D2B3CrossSectionalMomentumTests(unittest.TestCase):
    def test_measure_uses_14d_return_and_amihud_formula(self):
        rows = history(daily_growth=0.01, volume=2_000_000.0)
        as_of = 500 * DAY

        result = measure_symbol(
            symbol="BTCUSDT",
            daily_bars=rows,
            as_of_ms=as_of,
        )

        expected_momentum = (1.01 ** 14) - 1.0
        expected_amihud = 0.01 / 2_000_000.0

        self.assertAlmostEqual(result.momentum_14d, expected_momentum, places=12)
        self.assertAlmostEqual(result.amihud_14d, expected_amihud, places=18)

    def test_26_week_history_minimum_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "HISTORY_INSUFFICIENT"):
            measure_symbol(
                symbol="NEWUSDT",
                daily_bars=history(days=100),
                as_of_ms=500 * DAY,
            )

    def test_future_or_open_bar_is_rejected(self):
        rows = history()
        rows[-1] = {
            **rows[-1],
            "close_time_ms": 500 * DAY,
        }
        with self.assertRaisesRegex(ValueError, "BOUNDARY_INVALID"):
            measure_symbol(
                symbol="BTCUSDT",
                daily_bars=rows,
                as_of_ms=500 * DAY,
            )

    def test_top_30pct_winners_intersect_bottom_30pct_illiquidity(self):
        as_of = 500 * DAY
        histories = {}
        # Higher growth and higher traded value move together. With 10 symbols,
        # the top 3 momentum names are also the 3 lowest-Amihud names.
        for index in range(10):
            symbol = f"C{index}USDT"
            histories[symbol] = history(
                daily_growth=0.001 + index * 0.001,
                volume=1_000_000.0 + index * 2_000_000.0,
            )

        result = build_liquid_winner_signals(
            daily_history_by_symbol=histories,
            as_of_ms=as_of,
        )

        self.assertEqual(result.measured_symbols, 10)
        self.assertEqual(len(result.winner_symbols), 3)
        self.assertEqual(len(result.liquid_symbols), 3)
        self.assertEqual(
            [signal.symbol for signal in result.signals],
            ["C9USDT", "C8USDT", "C7USDT"],
        )

        for signal in result.signals:
            self.assertEqual(signal.direction, DIRECTION)
            self.assertEqual(signal.strategy_id, STRATEGY_ID)
            self.assertEqual(signal.authority, AUTHORITY)
            self.assertEqual(signal.runtime_activation, "DISABLED")

    def test_stablecoin_symbols_are_excluded_by_default(self):
        as_of = 500 * DAY
        histories = {
            "USDCUSDT": history(daily_growth=0.02, volume=100_000_000.0),
            "BTCUSDT": history(daily_growth=0.010, volume=50_000_000.0),
            "ETHUSDT": history(daily_growth=0.009, volume=40_000_000.0),
            "BNBUSDT": history(daily_growth=0.008, volume=30_000_000.0),
            "SOLUSDT": history(daily_growth=0.007, volume=20_000_000.0),
        }

        result = build_liquid_winner_signals(
            daily_history_by_symbol=histories,
            as_of_ms=as_of,
        )

        self.assertTrue(is_stablecoin_symbol("USDCUSDT"))
        self.assertNotIn("USDCUSDT", result.winner_symbols)
        self.assertIn(("USDCUSDT", "STABLECOIN_EXCLUDED"), result.excluded)

    def test_invalid_fraction_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "WINNER_FRACTION_INVALID"):
            build_liquid_winner_signals(
                daily_history_by_symbol={
                    "BTCUSDT": history(),
                    "ETHUSDT": history(),
                    "BNBUSDT": history(),
                    "SOLUSDT": history(),
                },
                as_of_ms=500 * DAY,
                winner_fraction=0.80,
            )


if __name__ == "__main__":
    unittest.main()
