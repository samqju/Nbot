"""Offline checks for M2 time-aligned execution and AI decision audits."""
from __future__ import annotations

import io
import importlib.util
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

depth = load("m2_bookdepth_audit")
decision = load("m2_decision_audit")
context = load("m2_context_repro")


class M2ExtendedTests(unittest.TestCase):
    def test_depth_snapshot_never_uses_future(self):
        series = {"times": [1000, 2000], "amounts": [5000.0, 10000.0],
                  "looks_frozen": False}
        self.assertEqual(depth.snapshot_at(series, 1500)["visible_notional_within_20bps_usdt"], 5000)
        self.assertEqual(depth.snapshot_at(series, 999)["state"], "NO_PRIOR_SNAPSHOT")
        self.assertEqual(depth.snapshot_at(series, 47001)["state"], "STALE")

    def test_depth_flags_frozen_quotes_instead_of_concluding_liquidity(self):
        series = {"times": [1000], "amounts": [999999.0], "looks_frozen": True}
        self.assertEqual(depth.snapshot_at(series, 1100)["state"], "ARCHIVE_SUSPECT_FROZEN")

    def test_zip_csv_snapshots_loaded_in_utc_with_band_notional(self):
        raw = io.BytesIO()
        with ZipFile(raw, "w") as z:
            z.writestr("BTCUSDT-bookDepth-2026-10-01.csv",
                       "timestamp,percentage,depth,notional\n"
                       "2026-10-01 00:00:01,-0.20,200,5000\n"
                       "2026-10-01 00:00:01,0.20,300,9000\n"
                       "2026-10-01 00:00:31,-0.20,250,6000\n"
                       "2026-10-01 00:00:31,0.20,400,11000\n")
        parsed = depth.read_depth(raw.getvalue())
        self.assertEqual(parsed[-0.2]["count"], 2)
        self.assertEqual(parsed[0.2]["amounts"], [9000,11000])
        self.assertEqual(parsed[-0.2]["looks_frozen"], False)

    def test_zero_minute_trade_occupies_zero_time(self):
        from m2_exposure_audit import exposure
        from m2_funding_reconcile import timestamp_ms
        tick = "2026-09-10T00:30:00+00:00"
        row = {"open_date": tick, "close_date": tick,
               "pair": "BTC/USDT:USDT", "is_short": False}
        got = exposure([row],
            timestamp_ms("2026-09-01T00:00:00+00:00"),
            timestamp_ms("2026-10-01T00:00:00+00:00"))
        self.assertEqual(got["position_hours"], 0.0)
        self.assertEqual(got["trades"], 1)
        self.assertEqual(got["overlapping_global_positions"], 0)

    def test_untrusted_archive_url_inputs_rejected(self):
        with self.assertRaises(ValueError):
            depth.archive_url("BTCUSDT/../../", "2026-10-01")
        with self.assertRaises(ValueError):
            depth.archive_url("BTCUSDT", "yesterday")

    def test_model_decisions_are_aligned_and_label_threshold_matters(self):
        n=230
        date=pd.date_range("2026-10-01", periods=n, freq="5min", tz="UTC")
        price=np.linspace(100,130,n)
        candles=pd.DataFrame({"date":date, "close":price, "open":price-0.1,
                              "high":price+0.02, "low":price-0.02,
                              "volume":np.ones(n)*10})
        preds=pd.DataFrame({"date":date, "&-forward_return":np.full(n,0.01),
                            "do_predict":np.ones(n)})
        a=decision.model_decisions(candles,preds)
        self.assertGreater(a["technical_setups"],0)
        self.assertEqual(a["technical_setups"],a["eligible_AI_candidate_signal_rows"])
        preds.loc[150,"do_predict"]=0
        b=decision.model_decisions(candles,preds)
        self.assertGreaterEqual(b["technical_setup_but_model_not_ready"],0)
        preds["&-forward_return"]=0.0001
        c=decision.model_decisions(candles,preds)
        self.assertEqual(c["eligible_AI_candidate_signal_rows"],0)

    def test_pair_context_comparison_detects_prediction_difference(self):
        dt=pd.date_range("2026-10-01",periods=3,freq="5min",tz="UTC")
        a=pd.DataFrame({"date":dt, "&-forward_return":[0.1,0.2,0.3],
                        "&-forward_return_mean":[0.0]*3, "&-forward_return_std":[0.1]*3,
                        "do_predict":[1,1,1], "DI_values":[0.1]*3})
        b=a.copy()
        self.assertEqual(context.compare(a,b)["&-forward_return"]["changed_values_over_tolerance_1e-9"],0)
        b.loc[1,"&-forward_return"]=0.5
        self.assertEqual(context.compare(a,b)["&-forward_return"]["changed_values_over_tolerance_1e-9"],1)


if __name__=="__main__":
    unittest.main()
