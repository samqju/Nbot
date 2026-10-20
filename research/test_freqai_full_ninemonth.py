"""Causal and immutable-research scope tests for Jan-Sep 2026 FreqAI replay."""
import unittest
from pathlib import Path
from nbot_v7.experiment import month_start
from research.freqai_v7_monthly_180d import training_bounds, DAY
from research.freqai_v7_full_nine_month_daily import (
    START,END,CUTS,DAY_COUNT,daystr,first_day_model_key,
)
from research.freqai_v7_ninemonth_sources import source_key,OLD_MONTHS,NEW_MONTHS


class NineMonthSourceBoundaries(unittest.TestCase):
    def test_nine_months_are_all_trade_months_and_273_daily_cutoffs(self):
        self.assertEqual(START,month_start("2026-01"))
        self.assertEqual(END,month_start("2026-10"))
        self.assertEqual(DAY_COUNT,273)
        self.assertEqual(len(CUTS),9)
        self.assertEqual([daystr(t) for t in CUTS],
            ["2026-%02d-01"%m for m in range(1,10)])

    def test_january_1_lookback_is_2025_and_does_not_require_future(self):
        begin,cal,cutoff=training_bounds(START)
        self.assertEqual(begin,START-180*DAY)
        self.assertGreaterEqual(begin,month_start("2025-07"))
        self.assertEqual(cal,START-14*DAY)
        self.assertLess(cal,START)
        self.assertEqual(cutoff,START)

    def test_each_month_frozen_model_is_that_month_first_of_day(self):
        self.assertEqual(first_day_model_key(month_start("2026-01")+15*DAY),
                         "2026-01-01")
        self.assertEqual(first_day_model_key(month_start("2026-06")+19*DAY),
                         "2026-06-01")
        self.assertEqual(first_day_model_key(month_start("2026-09")+29*DAY),
                         "2026-09-01")

    def test_archives_exactly_three_coins_fifteen_months(self):
        self.assertEqual(len(OLD_MONTHS),6)
        self.assertEqual(len(NEW_MONTHS),9)
        self.assertEqual(
            source_key("BTCUSDT","5m","2025-07"),
            "data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2025-07.zip")
        self.assertEqual(
            source_key("SOLUSDT","fundingRate","2026-09"),
            "data/futures/um/monthly/fundingRate/SOLUSDT/SOLUSDT-fundingRate-2026-09.zip")

    def test_research_entrypoint_contains_no_order_commands(self):
        s=(Path(__file__).parent/"freqai_v7_full_nine_month_daily.py").read_text()
        for bad in ("create_order(", "create_market_order(",
                    "freqtrade trade","ccxt.create_order","binance.private"):
            self.assertNotIn(bad,s)


if __name__=="__main__":
    unittest.main()
