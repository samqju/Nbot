"""Mock-only modern USD-M forward market/public WSS frame contract tests."""
import json
import unittest

from nbot.v5.g4_forward_stream_contract import (
    forward_stream_endpoints,verify_frame,
)
NOW=1800000000000
SYMS=["BTCUSDT","QNTUSDT"]


def mk(stream_kind="agg", change=None):
    if stream_kind=="agg":
        p={"stream":"qntusdt@aggTrade",
           "data":{"e":"aggTrade","E":NOW-100,"s":"QNTUSDT",
                   "a":100,"f":500,"l":502,"T":NOW-110,
                   "p":"200.25","q":"10.5","m":False,"st":1}}
        route="market_aggtrade"
    elif stream_kind=="quote":
        p={"stream":"qntusdt@bookTicker",
           "data":{"e":"bookTicker","E":NOW-200,"s":"QNTUSDT",
                   "b":"200.1","B":"2.0","a":"200.2","A":"5.0","st":1}}
        route="public_bookticker"
    elif stream_kind=="mark":
        p={"stream":"qntusdt@markPrice@1s",
           "data":{"e":"markPriceUpdate","E":NOW-100,"s":"QNTUSDT",
                   "p":"200.3","i":"200.25","P":"200.20",
                   "r":"-0.0002","T":NOW+28800000,"st":1}}
        route="market_markprice"
    else:
        raise AssertionError("bad fixture")
    if change:change(p)
    return route,json.dumps(p,separators=(",",":")).encode()


def run(kind="agg", change=None, **kw):
    route,raw=mk(kind,change)
    return verify_frame(route=route,raw=raw,received_at_ms=NOW,
                        source_epoch=1,selected_symbols=SYMS,**kw)


class G4ForwardContracts(unittest.TestCase):
    def test_urls_have_2026_correct_routing(self):
        r=forward_stream_endpoints(SYMS)
        self.assertIn("/public/stream?streams=",r["public_bookticker"])
        self.assertIn("qntusdt@bookTicker",r["public_bookticker"])
        self.assertIn("/market/stream?streams=",r["market_aggtrade"])
        self.assertIn("qntusdt@aggTrade",r["market_aggtrade"])
        self.assertIn("qntusdt@markPrice@1s",r["market_markprice"])
        self.assertIn("/market/stream?streams=",r["market_markprice"])
        self.assertNotIn("/private/",r["market_aggtrade"])

    def test_normalizes_cohort_without_mutation(self):
        r=forward_stream_endpoints(list(reversed(SYMS)))
        self.assertEqual(r["cohort_symbols"],tuple(sorted(SYMS)))

    def test_duplicate_or_foreign_symbols_not_allowed(self):
        for syms in [["BTCUSDT","BTCUSDT"],["btcUSDT"],["../abc"],[]]:
            with self.assertRaises(ValueError):forward_stream_endpoints(syms)

    def test_agg_trade_proof_is_not_executable_trade_fill(self):
        x=run()
        self.assertEqual(x.state,"SOURCE_RECORDED")
        self.assertEqual(x.agg_id,100)
        self.assertEqual(x.underlying_last_trade_id,502)
        self.assertEqual(x.scored_outcomes,0)
        self.assertEqual(x.financial_authority,"NONE")

    def test_book_quote_source_not_fill(self):
        x=run("quote")
        self.assertEqual(x.state,"SOURCE_RECORDED")
        self.assertEqual(x.agg_id,None)
        self.assertEqual(x.scored_outcomes,0)

    def test_agg_continuity_is_checked(self):
        self.assertEqual(run(prior_agg_id=99,prior_last_trade_id=499).state,"SOURCE_RECORDED")

    def test_agg_gap_is_hold(self):
        x=run(prior_agg_id=98,prior_last_trade_id=499)
        self.assertIn("AGGTRADE_ID_GAP_OR_REPLAY",x.reasons)

    def test_underlying_trade_gap_is_hold(self):
        x=run(prior_agg_id=99,prior_last_trade_id=498)
        self.assertIn("UNDERLYING_TRADE_ID_GAP_OR_REPLAY",x.reasons)

    def test_replay_is_hold(self):
        x=run(prior_agg_id=100)
        self.assertIn("AGGTRADE_ID_GAP_OR_REPLAY",x.reasons)

    def test_future_event_clock_is_hold(self):
        x=run(change=lambda p:p["data"].update(E=NOW+1))
        self.assertIn("EVENT_CLOCK_MISSING_FUTURE_OR_STALE",x.reasons)

    def test_stale_trade_clock_is_hold(self):
        x=run(change=lambda p:p["data"].update(T=NOW-5001))
        self.assertIn("TRADE_CLOCK_MISSING_FUTURE_OR_STALE",x.reasons)

    def test_book_without_engine_clock_holds(self):
        x=run("quote",change=lambda p:p["data"].pop("E"))
        self.assertIn("EVENT_CLOCK_MISSING_FUTURE_OR_STALE",x.reasons)

    def test_crossed_book_holds(self):
        x=run("quote",change=lambda p:p["data"].update(b="210"))
        self.assertIn("BOOK_CROSSED",x.reasons)

    def test_invalid_bid_qty_holds(self):
        x=run("quote",change=lambda p:p["data"].update(B="NaN"))
        self.assertIn("BOOK_QUOTE_INVALID",x.reasons)

    def test_wrong_public_stream_route_holds(self):
        x=run("quote",change=lambda p:p.update(stream="qntusdt@aggTrade"))
        self.assertIn("STREAM_SYMBOL_OR_TYPE_MISMATCH",x.reasons)

    def test_spot_or_coin_migration_wrong_st_holds(self):
        x=run(change=lambda p:p["data"].update(st=2))
        self.assertIn("NOT_USDM_FUTURE",x.reasons)

    def test_foreign_coin_denominator_holds(self):
        x=run(change=lambda p:p["data"].update(s="XRPUSDT"))
        self.assertIn("FOREIGN_SYMBOL",x.reasons)

    def test_bad_decimal_price_holds(self):
        x=run(change=lambda p:p["data"].update(p="-1"))
        self.assertIn("AGGTRADE_ROW_INVALID",x.reasons)

    def test_bad_maker_flag_holds(self):
        x=run(change=lambda p:p["data"].update(m=1))
        self.assertIn("AGGTRADE_ROW_INVALID",x.reasons)

    def test_mark_funding_rate_stream_is_indicative_source_only(self):
        x=run("mark")
        self.assertEqual(x.state,"SOURCE_RECORDED")
        self.assertEqual(x.route,"market_markprice")
        self.assertEqual(x.scored_outcomes,0)
        self.assertEqual(x.financial_authority,"NONE")

    def test_mark_funding_invalid_signed_rate_is_held(self):
        x=run("mark",change=lambda p:p["data"].update(r="NaN"))
        self.assertIn("MARK_PRICE_OR_INDICATIVE_FUNDING_INVALID",x.reasons)

    def test_mark_funding_next_time_must_be_future(self):
        x=run("mark",change=lambda p:p["data"].update(T=NOW-1000))
        self.assertIn("MARK_PRICE_OR_INDICATIVE_FUNDING_INVALID",x.reasons)

    def test_mark_price_cross_route_rejected(self):
        x=run("mark",change=lambda p:p.update(stream="qntusdt@aggTrade"))
        self.assertIn("STREAM_SYMBOL_OR_TYPE_MISMATCH",x.reasons)

    def test_frame_is_bounded(self):
        route,_=mk()
        with self.assertRaisesRegex(ValueError,"G4_FORWARD_FRAME_BOUNDS_INVALID"):
            verify_frame(route=route,raw=b" "*40000,received_at_ms=NOW,
                         source_epoch=1,selected_symbols=SYMS)

    def test_source_epoch_must_be_positive(self):
        route,raw=mk()
        with self.assertRaisesRegex(ValueError,"G4_FORWARD_CLOCK_OR_EPOCH_INVALID"):
            verify_frame(route=route,raw=raw,received_at_ms=NOW,
                         source_epoch=0,selected_symbols=SYMS)

    def test_malformed_json_and_route_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"G4_FORWARD_FRAME_JSON_INVALID"):
            verify_frame(route="market_aggtrade",raw=b"not json",received_at_ms=NOW,
                         source_epoch=1,selected_symbols=SYMS)
        with self.assertRaisesRegex(ValueError,"G4_FORWARD_ROUTE_INVALID"):
            verify_frame(route="private_orders",raw=b"{}",received_at_ms=NOW,
                         source_epoch=1,selected_symbols=SYMS)


if __name__=="__main__":
    unittest.main()
