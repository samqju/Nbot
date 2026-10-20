"""Temporal rules of the 1%-distance ALWAYS-PROTECTED research trailing stop."""
import unittest
from nbot_v7.data import Bar,BAR_MS
from nbot_v7.runtime.risk import RiskPolicy
from research.v7_trailingstop1_broker import PreviousBarTrailingOnePercentBroker


class TrailingOnePctContracts(unittest.TestCase):
    def setUp(self):
        self.b=PreviousBarTrailingOnePercentBroker()
        self.pol=RiskPolicy(stop_fraction=.01,slippage_each=0,fee_each=0)
        self.ms=1750000000000 - 1750000000000%BAR_MS

    def open(self,side):
        return self.b.submit({"id":"x","side":side,"symbol":"TEST",
            "time_ms":self.ms,"quote":100.0},self.pol)

    def step(self,pos,i,op,hi,lo,cl):
        bar=Bar(self.ms+i*BAR_MS,op,hi,lo,cl,100)
        return self.b.on_bar(pos,bar,bar.t+BAR_MS,self.pol)

    def test_long_05pct_favorable_tightens_next_bar_stop_by_half_pct(self):
        p=self.open("LONG")
        self.assertAlmostEqual(p["stop"],99)
        fill,p=self.step(p,0,100,100.5,99.4,100.4)
        self.assertIsNone(fill)
        self.assertAlmostEqual(p["stop"],99.5)
        fill,p=self.step(p,1,100.2,100.3,99.45,99.9)
        self.assertIsNotNone(fill)
        self.assertAlmostEqual(fill["exit_price"],99.5)

    def test_long_1pct_favorable_sets_next_bar_breakeven(self):
        p=self.open("LONG")
        _,p=self.step(p,0,100,101,99.3,100.9)
        self.assertAlmostEqual(p["stop"],100)
        fill,p=self.step(p,1,100.9,100.9,99.9,100)
        self.assertIsNotNone(fill)
        self.assertAlmostEqual(fill["exit_price"],100)

    def test_no_same_bar_ratchet_from_unknown_high_low_order(self):
        p=self.open("LONG")
        fill,p=self.step(p,0,100,101,99.4,99.7)
        # Within first bar price touched 99.4, which would hit
        # an invalid intrabar-ratcheted 100. We DO NOT assume
        # that high happened before low on OHLC candle.
        self.assertIsNone(fill)
        self.assertAlmostEqual(p["stop"],100)

    def test_short_05pct_favorable_moves_plus1_to_plus05(self):
        p=self.open("SHORT")
        self.assertAlmostEqual(p["stop"],101)
        fill,p=self.step(p,0,100,100.6,99.5,99.6)
        self.assertIsNone(fill)
        self.assertAlmostEqual(p["stop"],100.5)
        fill,p=self.step(p,1,99.7,100.55,99.6,100.4)
        self.assertIsNotNone(fill)
        self.assertAlmostEqual(fill["exit_price"],100.5)

    def test_trailing_can_never_loosen(self):
        p=self.open("LONG")
        fill,p=self.step(p,0,100,100.9,99.9,100.6)
        self.assertIsNone(fill)
        first=p["stop"]
        fill,p=self.step(p,1,100.3,100.4,100.1,100.2)
        self.assertIsNone(fill)
        self.assertGreaterEqual(p["stop"],first)

    def test_preexisting_initial_stop_or_target_wins_over_ratchet(self):
        p=self.open("LONG")
        fill,p=self.step(p,0,100,103.2,98.8,102)
        self.assertIsNotNone(fill)
        self.assertEqual(fill["reason"],"STOP_AMBIGUOUS")
        self.assertAlmostEqual(fill["exit_price"],99)

    def test_wrong_policy_fails_closed(self):
        with self.assertRaises(ValueError):
            self.b.submit({"id":"x","side":"LONG","symbol":"TEST",
               "time_ms":self.ms,"quote":100},RiskPolicy(stop_fraction=.02))


if __name__=="__main__":
    unittest.main()
