"""Owner CS01 trade-price-only architecture regression. No network or orders."""
from __future__ import annotations
import hashlib
import json
import unittest
from pathlib import Path

from nbot_v5_1.cs00_source_runtime import public_routes,CollectorHold
from nbot_v5_1.cs00_public_service import FuturePublicObservationService
from nbot_v5_1.public_market import PublicResponse,select_from_public_responses
from nbot_v5_1.universe import select_universe,UniverseHold


def fixture(n=115):
    symbols=["BTCUSDT"]+[f"T{i:03d}USDT" for i in range(n-1)]
    exchange={"symbols":[{"symbol":s,"status":"TRADING","contractType":"PERPETUAL",
                "quoteAsset":"USDT","marginAsset":"USDT"} for s in symbols]}
    tickers=[{"symbol":s,"quoteVolume":str(5000000+i*10000),
              "priceChangePercent":str(i%9-4)} for i,s in enumerate(symbols)]
    hist={s:96 for s in symbols}
    healthy={s:True for s in symbols}
    return symbols,exchange,tickers,hist,healthy


def receipt(kind,path,value,at=1792079000000):
    raw=json.dumps(value,separators=(",",":")).encode("utf8")
    return PublicResponse(kind,path,at,hashlib.sha256(raw).hexdigest(),value,1,raw)


class TradeOnlyCs01Test(unittest.TestCase):
    def test_two_public_routes_never_include_quote(self):
        symbols=("BTCUSDT",)+tuple(f"T{i:03d}USDT" for i in range(19))
        routes=public_routes(symbols,trade_only=True)
        self.assertEqual([r.kind for r in routes],["TRADE","MARK"])
        self.assertTrue(all("bookTicker" not in r.uri and "/private" not in r.uri for r in routes))
        self.assertTrue(all(len(r.deep_symbols)==20 for r in routes))

    def test_old_three_routes_cannot_be_implicitly_confused(self):
        symbols=("BTCUSDT",)+tuple(f"T{i:03d}USDT" for i in range(19))
        self.assertEqual(len(public_routes(symbols)),3)
        with self.assertRaises(CollectorHold):
            public_routes(symbols[:-1],trade_only=True)
        with self.assertRaises(CollectorHold):
            public_routes(symbols,trade_only="yes")

    def test_trade_only_service_does_not_start_network(self):
        app=FuturePublicObservationService(source_root=Path("/tmp/nonexistent-trade-only"),
                                           code_sha="b"*40)
        self.assertTrue(app.trade_only)
        self.assertFalse(app.started)
        self.assertFalse(app.status()["exchange_order_capability"])

    def test_universe_no_quotes_has_100_and_btc(self):
        symbols,ex,ticker,h,hv=fixture()
        m=select_universe(ex,ticker,None,h,hv,
                          source_received_at_ms=1792079000000,
                          selected_at_ms=1792079000002)
        self.assertEqual(len(m.symbols),100)
        self.assertIn("BTCUSDT",m.symbols)
        self.assertNotIn("BOOK_TICKER",str(m.public_receipts))

    def test_two_independent_public_metadata_receipts(self):
        symbols,ex,ticker,h,hv=fixture()
        a=receipt("EXCHANGE_INFO","/fapi/v1/exchangeInfo",ex)
        b=receipt("TICKER_24HR","/fapi/v1/ticker/24hr",ticker,1792079000020)
        m=select_from_public_responses(a,b,None,h,hv,selected_at_ms=1792079000200)
        self.assertEqual(len(m.symbols),100)
        self.assertEqual({k for k,*_ in m.public_receipts},{"EXCHANGE_INFO","TICKER_24HR"})
        self.assertNotIn("BOOK_TICKER",str(m.public_receipts))

    def test_same_market_old_book_policy_not_confused_with_new_policy(self):
        symbols,ex,ticker,h,hv=fixture()
        m=select_universe(ex,ticker,None,h,hv,
                          source_received_at_ms=1792079000000,
                          selected_at_ms=1792079000002)
        bad_books=[{"symbol":s,"bidPrice":"0","askPrice":"0"} for s in symbols]
        with self.assertRaises(UniverseHold):
            select_universe(ex,ticker,bad_books,h,hv,
                          source_received_at_ms=1792079000000,
                          selected_at_ms=1792079000002)

    def test_two_receipts_cannot_claim_three_source_book_validation(self):
        symbols,ex,ticker,h,hv=fixture()
        a=receipt("EXCHANGE_INFO","/fapi/v1/exchangeInfo",ex)
        b=receipt("TICKER_24HR","/fapi/v1/ticker/24hr",ticker)
        with self.assertRaises((ValueError,UniverseHold)):
            select_universe(ex,ticker,None,h,hv,
               source_received_at_ms=1792079000000,
               selected_at_ms=1792079000002,
               public_receipts=(("EXCHANGE_INFO",a.body_sha256,a.received_at_ms),
                                ("BOOK_TICKER",b.body_sha256,b.received_at_ms)))


if __name__=="__main__":
    unittest.main()
