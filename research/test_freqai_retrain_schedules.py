"""Monthly/daily causal schedule and input ordering, isolated FreqAI research."""
import json
from pathlib import Path
import tempfile
import unittest

from nbot_v7.experiment import month_start
from research.freqai_v7_monthly_180d import training_bounds, concat_month_files, DAY
from research.freqai_v7_daily_180d import daily_dates, START, END


class RetrainingScheduleContracts(unittest.TestCase):
    def test_monthly_180_days_and_14_day_separate_calibration(self):
        for d in ("2026-07","2026-08","2026-09"):
            cutoff=month_start(d)
            first,cal,actual=training_bounds(cutoff)
            self.assertEqual(actual,cutoff)
            self.assertEqual(first,cutoff-180*DAY)
            self.assertEqual(cal,cutoff-14*DAY)
            self.assertLess(first,cal)
            self.assertLess(cal,cutoff)

    def test_expanding_keeps_january_start_without_future(self):
        a=training_bounds(month_start("2026-07"),expanding=True)
        b=training_bounds(month_start("2026-09"),expanding=True)
        self.assertEqual(a[0],month_start("2026-01"))
        self.assertEqual(b[0],month_start("2026-01"))
        self.assertLess(a[1],a[2])
        self.assertLess(b[1],b[2])

    def test_daily_dates_are_exactly_92_and_bound_to_month_ends(self):
        times=list(daily_dates())
        self.assertEqual(len(times),92)
        self.assertEqual(times[0],START)
        self.assertEqual(times[-1]+DAY,END)
        self.assertEqual(len(set(times)),92)
        self.assertTrue(all(b-a==DAY for a,b in zip(times,times[1:])))

    def test_daily_concat_refuses_disordered_forecasts(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            aa=root/"a.jsonl"
            bb=root/"b.jsonl"
            aa.write_text(json.dumps({"decision_ms":1000})+"\n")
            bb.write_text(json.dumps({"decision_ms":900})+"\n")
            with self.assertRaisesRegex(ValueError,"OUT_OF_ORDER"):
                concat_month_files([aa,bb],root/"bad.jsonl")

    def test_research_source_no_live_order_entrypoints(self):
        path=Path(__file__).parent/"freqai_v7_daily_180d.py"
        s=path.read_text()
        for banned in ("create_order(", "create_market_order(", "freqtrade trade",
                       "binance.client", "ccxt.create_order"):
            self.assertNotIn(banned,s)


if __name__=="__main__":
    unittest.main()
