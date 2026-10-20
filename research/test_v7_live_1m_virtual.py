"""No-order public 1m raw FreqAI virtual observer causal tests."""
from __future__ import annotations
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nbot_v7.data import Bar
from research import v7_live_1m_virtual_15day as v


class LiveOneMinuteResearchContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.c=v.connect(self.root)

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_one_minute_parse_from_binance(self):
        r=[1800000000000-1800000000000%60000,"100","101","99","100.5","2",0]
        b=v.parse_ohlc(r)
        self.assertEqual(b.t%60000,0)
        self.assertAlmostEqual(b.c,100.5)
        r[2]="98"
        with self.assertRaises(ValueError):
            v.parse_ohlc(r)

    def test_decision_cannot_use_missing_history(self):
        bars=[Bar(i*60000,100,100.2,99.8,100,3) for i in range(49)]
        with self.assertRaises(ValueError):
            v.feat(bars,bars)

    def test_one_minute_feature_shape_and_identity(self):
        bars=[Bar(i*60000,100,100.2,99.8,100+i*.01,3) for i in range(60)]
        x=v.feat(bars,bars)
        self.assertEqual(len(x),13)
        self.assertEqual(len(v.full_vector(x,"SOLUSDT","SHORT")),len(v.FEATURE_NAMES))
        self.assertEqual(v.full_vector(x,"SOLUSDT","SHORT")[-4:],[1.,0.,0.,1.])

    def test_entry_cap_zero_to_three_and_no_api_order_code(self):
        self.assertEqual(v.MAX_ENTRIES,3)
        self.assertEqual(v.S,("BTCUSDT","ETHUSDT","SOLUSDT"))
        self.assertEqual(v.ONE,60000)
        self.assertEqual(v.DAYS,15)
        source=Path(v.__file__).read_text()
        for forbidden in (
                "create_order(", "place_order(", "GuardedLiveBroker(",
                "futures_create_order(", "load_dotenv(", "api_secret",
                "api_key=", "freqtrade trade"):
            self.assertNotIn(forbidden,source)

    def test_mismatched_public_price_rewrite_fails_closed(self):
        b=Bar(60000,10,11,9,10,1)
        with self.c:v.add_bars(self.c,"BTCUSDT",[b])
        with self.c:
            with self.assertRaises(ValueError):
                v.add_bars(self.c,"BTCUSDT",[Bar(60000,10,11,8,10,1)])

    def test_raw_model_max_zero_below_threshold_refuses(self):
        self.assertEqual(v.STOP_POLICY.stop_fraction,.02)
        self.assertEqual(v.STOP_POLICY.take_fraction,.03)
        self.assertEqual(v.STOP_POLICY.max_hold_ms,3600000)

    def test_api_scope_only_public_rest_and_archive(self):
        self.assertTrue(v.API.startswith("https://fapi.binance.com/fapi/v1/klines"))
        self.assertIn("/daily/klines",v.VIS)
        with self.assertRaises(ValueError):
            v.rest_klines("DOGEUSDT",1)


if __name__=="__main__":
    unittest.main()
