"""V5-03 strict no-hindsight BTC and coin context regression fixtures."""
import copy
import math
import unittest

from nbot.v5.g3_market_context import (
    FEATURE_VERSION, BARS, REGIMES, STRUCTURES, _swings, classify_event,
)
from nbot.v5.observation_contract import INTERVAL_MS

EVENT = INTERVAL_MS * 1_000_000
COMMIT = EVENT + INTERVAL_MS + 32_000
SAMPLE = EVENT + INTERVAL_MS + 1_000
SYMBOLS = tuple(sorted(("BTCUSDT",) + tuple(f"COIN{k:02d}USDT" for k in range(11))))


def candles(*, drift=.0005, shock=0., event=EVENT):
    rows=[]
    prev=100.
    for i in range(96):
        close=100.*((1.+drift)**i)
        if i==95:
            close*=1.+shock
        opening=prev if i else 100.
        high=max(opening,close)*1.001
        low=min(opening,close)*.999
        rows.append((event-(95-i)*INTERVAL_MS,
                     float(opening),float(high),float(low),float(close),float(100+i)))
        prev=close
    return rows


def witness(*, sample=SAMPLE, quote_age=100, trade_age=200):
    return {"sampled_at_ms":sample,
            "source":{"market_connected":True,"public_connected":True,
                      "market_epoch":1,"public_epoch":1,
                      "quote_received_ms":sample-quote_age,
                      "trade_received_ms":sample-trade_age,
                      "bid":100.0,"ask":100.08}}


class G3RegimeStructureTests(unittest.TestCase):
    def setUp(self):
        self.prices={s:candles(drift=.0005) for s in SYMBOLS}
        self.receipts={s:witness() for s in SYMBOLS}

    def result(self):
        return classify_event(event_open_ms=EVENT,decision_at_ms=COMMIT,
                              selected_symbols=SYMBOLS,
                              candles=self.prices,witnesses=self.receipts)

    def test_frozen_schema_identity_and_all_coin_denominators(self):
        x=self.result()
        self.assertEqual(x["version"],FEATURE_VERSION)
        self.assertEqual(x["candidate_cohort_size"],len(SYMBOLS))
        self.assertEqual(x["unknown_coin_count"],0)
        self.assertEqual(x["available_coin_count"],len(SYMBOLS))
        self.assertEqual(x["valid_from_ms"],COMMIT)
        self.assertTrue(x["btc"]["valid"])
        self.assertIn(x["btc"]["regime"],REGIMES)
        self.assertTrue(x["breadth_available"])
        self.assertTrue(x["breadth_excludes_btc"])
        self.assertEqual(x["breadth_sample"],len(SYMBOLS)-1)
        self.assertEqual(x["breadth_population_size"],len(SYMBOLS)-1)
        self.assertEqual(set(x["coins"]),set(SYMBOLS))
        self.assertTrue(all(v["structure"] in STRUCTURES for v in x["coins"].values()))
        self.assertEqual(x["recommendation_authority"],"NONE")
        self.assertEqual(x["order_authority"],"NONE")
        self.assertEqual(x["learning_labels_created"],0)

    def test_identical_input_reproducible_and_no_training(self):
        a=self.result()
        b=self.result()
        self.assertEqual(a,b)
        self.assertEqual(a["feature_sha256"],b["feature_sha256"])
        self.assertEqual(a["research_outcomes"],0)

    def test_btc_upward_shock_is_not_ordinary_trend(self):
        self.prices["BTCUSDT"]=candles(drift=.0004,shock=.12)
        self.assertEqual(self.result()["btc"]["regime"],"SHOCK_UP")

    def test_btc_downward_shock_is_not_neutral_or_zero(self):
        self.prices["BTCUSDT"]=candles(drift=.0004,shock=-.12)
        self.assertEqual(self.result()["btc"]["regime"],"SHOCK_DOWN")

    def test_btc_trending_up_and_down(self):
        self.prices["BTCUSDT"]=candles(drift=.001)
        self.assertEqual(self.result()["btc"]["regime"],"TREND_UP")
        self.prices["BTCUSDT"]=candles(drift=-.001)
        self.assertEqual(self.result()["btc"]["regime"],"TREND_DOWN")

    def test_btc_missing_is_unknown_and_all_coin_patterns_unavailable(self):
        self.prices.pop("BTCUSDT")
        x=self.result()
        self.assertEqual(x["btc"]["regime"],"UNKNOWN")
        self.assertIsNone(x["btc"]["features"])
        self.assertFalse(x["breadth_available"])
        self.assertEqual(x["unknown_coin_count"],len(SYMBOLS))
        self.assertTrue(all(v["btc_relative_pattern_long"]=="UNAVAILABLE"
                            for v in x["coins"].values()))
        self.assertTrue(all(v["relative_momentum_1h"] is None
                            for v in x["coins"].values()))

    def test_btc_stale_quote_must_not_infer_btc_return_zero(self):
        self.receipts["BTCUSDT"]=witness(quote_age=5_001)
        x=self.result()
        self.assertEqual(x["btc"]["regime"],"UNKNOWN")
        self.assertIn("QUOTE_RECEIPT_NOT_ASOF",x["btc"]["reasons"])
        self.assertEqual(x["unknown_coin_count"],len(SYMBOLS))

    def test_source_trade_clock_future_or_stale_holds_target(self):
        self.receipts["COIN00USDT"]=witness(trade_age=15_001)
        x=self.result()
        self.assertEqual(x["coins"]["COIN00USDT"]["state"],"UNKNOWN")
        self.assertIn("TRADE_RECEIPT_NOT_ASOF",x["coins"]["COIN00USDT"]["reasons"])
        self.assertEqual(x["coins"]["COIN01USDT"]["state"],"AVAILABLE")
        self.receipts["COIN00USDT"]=witness(trade_age=-1)
        self.assertEqual(self.result()["coins"]["COIN00USDT"]["state"],"UNKNOWN")

    def test_feed_generation_and_disconnection_holds(self):
        self.receipts["COIN00USDT"]["source"]["market_epoch"]=0
        self.receipts["COIN00USDT"]["source"]["public_connected"]=False
        x=self.result()
        self.assertIn("SOURCE_MARKET_EPOCH_UNKNOWN",x["coins"]["COIN00USDT"]["reasons"])
        self.assertIn("SOURCE_PUBLIC_DISCONNECTED",x["coins"]["COIN00USDT"]["reasons"])

    def test_quote_cross_and_out_of_range_spread_hold(self):
        self.receipts["COIN00USDT"]["source"]["ask"]=90.
        x=self.result()
        self.assertEqual(x["coins"]["COIN00USDT"]["state"],"UNKNOWN")
        self.receipts["COIN00USDT"]["source"]["ask"]=103.
        self.assertEqual(self.result()["coins"]["COIN00USDT"]["state"],"UNKNOWN")

    def test_same_event_clock_requires_closed_not_future(self):
        later=candles(event=EVENT+INTERVAL_MS)
        self.prices["COIN00USDT"]=later
        x=self.result()
        self.assertIn("CLOSED_CANDLE_HISTORY_NOT_CAUSAL",x["coins"]["COIN00USDT"]["reasons"])
        self.prices["COIN00USDT"]=candles() + [later[-1]]
        self.assertEqual(self.result()["coins"]["COIN00USDT"]["state"],"UNKNOWN")

    def test_short_candle_gap_invalid(self):
        self.prices["COIN00USDT"][25]=self.prices["COIN00USDT"][24]
        self.assertEqual(self.result()["coins"]["COIN00USDT"]["state"],"UNKNOWN")

    def test_breadth_requires_eighty_percent_and_at_least_ten(self):
        for s in SYMBOLS[1:5]:
            self.receipts[s]["source"]["market_epoch"]=0
        x=self.result()
        self.assertTrue(x["btc"]["valid"])
        self.assertFalse(x["breadth_available"])
        self.assertIsNone(x["breadth_1h"])
        self.assertEqual(x["unknown_coin_count"],len(SYMBOLS))

    def test_breadth_positive_and_negative_both_directional(self):
        for s in SYMBOLS:
            self.prices[s]=candles(drift=.001)
        self.assertGreater(self.result()["breadth_1h"],.8)
        for s in SYMBOLS:
            self.prices[s]=candles(drift=-.001)
        self.assertLess(self.result()["breadth_1h"],-.8)

    def test_breadth_reflects_altcoins_even_if_btc_trends_opposite(self):
        self.prices["BTCUSDT"]=candles(drift=-.001)
        for s in SYMBOLS:
            if s!="BTCUSDT":
                self.prices[s]=candles(drift=.001)
        out=self.result()
        self.assertEqual(out["btc"]["regime"],"TREND_DOWN")
        self.assertEqual(out["breadth_1h"],1.0)

    def test_btc_relative_positive_long_and_negative_short_reachable(self):
        self.prices["BTCUSDT"]=candles(drift=.0001)
        self.prices["COIN00USDT"]=candles(drift=.002)
        self.prices["COIN01USDT"]=candles(drift=-.002)
        x=self.result()
        self.assertEqual(x["coins"]["COIN00USDT"]["btc_relative_pattern_long"],"MATCH")
        self.assertEqual(x["coins"]["COIN00USDT"]["btc_relative_pattern_short"],"NO_MATCH")
        self.assertEqual(x["coins"]["COIN01USDT"]["btc_relative_pattern_short"],"MATCH")
        self.assertEqual(x["coins"]["COIN01USDT"]["btc_relative_pattern_long"],"NO_MATCH")
        self.assertGreater(x["coins"]["COIN00USDT"]["relative_momentum_1h"],0)
        self.assertLess(x["coins"]["COIN01USDT"]["relative_momentum_1h"],0)

    def test_two_right_hand_bars_required_for_confirmed_pivot(self):
        rows=candles(drift=0)
        # The pivot six bars back has two closed right-hand neighbours.
        p=list(rows[-6])
        p[2]=140.
        rows[-6]=tuple(p)
        # Event-close-near spike is NOT a confirmed swing at this decision.
        p=list(rows[-2])
        p[2]=150.
        rows[-2]=tuple(p)
        top,lo,hi_at,lo_at=_swings(tuple(rows))
        self.assertEqual(top,140.)
        self.assertEqual(hi_at,EVENT-5*INTERVAL_MS)
        self.assertLessEqual(hi_at,EVENT-2*INTERVAL_MS)

    def test_unconfirmed_future_swing_cannot_be_used_in_breakout(self):
        rows=candles(drift=0)
        spike=list(rows[-2]);spike[2]=160.
        rows[-2]=tuple(spike)
        self.prices["COIN00USDT"]=rows
        x=self.result()
        self.assertNotEqual(x["coins"]["COIN00USDT"]["structure"],"BREAKOUT_UP")

    def test_wrong_cohort_and_misaligned_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"FROZEN_COHORT"):
            classify_event(event_open_ms=EVENT,decision_at_ms=COMMIT,
                selected_symbols=tuple(reversed(SYMBOLS)),
                candles=self.prices,witnesses=self.receipts)
        with self.assertRaisesRegex(ValueError,"EVENT_CLOCK"):
            classify_event(event_open_ms=EVENT+1,decision_at_ms=COMMIT,
                selected_symbols=SYMBOLS,candles=self.prices,witnesses=self.receipts)

    def test_source_sample_must_precede_decision_and_follow_close(self):
        self.receipts["BTCUSDT"]=witness(sample=COMMIT+1)
        self.assertEqual(self.result()["btc"]["regime"],"UNKNOWN")
        self.receipts["BTCUSDT"]=witness(sample=EVENT+INTERVAL_MS-1)
        self.assertEqual(self.result()["btc"]["regime"],"UNKNOWN")

    def test_no_data_fault_may_be_rendered_as_ordinary_range(self):
        self.prices["BTCUSDT"] = candles(drift=0,shock=0)
        x=self.result()
        self.assertIn(x["btc"]["regime"],REGIMES)
        # Pure flat candles still have a small high-low range and ATR,
        # thus legitimate RANGE differs from missing-data UNKNOWN.
        self.assertEqual(x["btc"]["regime"],"RANGE")
        self.receipts.pop("BTCUSDT")
        self.assertEqual(self.result()["btc"]["regime"],"UNKNOWN")


if __name__=="__main__":
    unittest.main()
