"""G2 public source identity, timestamp skew and manifest audit binding."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.public_market import (
    PublicResponse, PublicUsdMClient, PublicMarketHold,
    select_from_public_responses,
)
from nbot_v5_1.observation_store import CompactObservationStore
from test_v5_1_g2 import market_fixture, END_OPEN


def pack(kind: str, path: str, obj, received: int = END_OPEN,
         *, formatting: int = 0) -> PublicResponse:
    raw = json.dumps(obj, sort_keys=True,
                     separators=(",",":") if formatting == 0 else (", ",": ")).encode()
    return PublicResponse(kind, path, received, hashlib.sha256(raw).hexdigest(),
                          obj, 1, raw)


def responses():
    e,t,b,h,s = market_fixture()
    return (pack("EXCHANGE_INFO","/fapi/v1/exchangeInfo",e),
            pack("TICKER_24HR","/fapi/v1/ticker/24hr",t,END_OPEN+100),
            pack("BOOK_TICKER","/fapi/v1/ticker/bookTicker",b,END_OPEN+200),
            h,s)


class PublicReceiptContract(unittest.TestCase):
    def test_R01_three_exact_source_hashes_bound_to_100_cohort(self):
        ex,tick,book,h,s=responses()
        m=select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+1000)
        self.assertEqual(len(m.symbols),100)
        self.assertIn("BTCUSDT",m.symbols)
        self.assertEqual(len(m.public_receipts),3)
        self.assertEqual(m.source_received_at_ms,END_OPEN)
        self.assertEqual({x[0] for x in m.public_receipts},
                         {"EXCHANGE_INFO","TICKER_24HR","BOOK_TICKER"})

    def test_R02_older_quote_snapshot_is_not_fresh_by_recent_book(self):
        ex,tick,book,h,s=responses()
        tick=replace(tick,received_at_ms=END_OPEN-60_100)
        with self.assertRaises(PublicMarketHold):
            select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+1000)

    def test_R03_independent_sources_clock_skew_blocks(self):
        ex,tick,book,h,s=responses()
        book=replace(book,received_at_ms=END_OPEN+16_100)
        with self.assertRaises(PublicMarketHold):
            select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+17_000)

    def test_R04_wrong_endpoint_kind_and_schema_are_rejected(self):
        ex,tick,book,h,s=responses()
        for wrong in (replace(ex,kind="KLINES"), replace(ex,path="/fapi/v1/order"),
                      replace(ex,body=[])):
            with self.subTest(kind=wrong.kind), self.assertRaises(PublicMarketHold):
                select_from_public_responses(wrong,tick,book,h,s,selected_at_ms=END_OPEN+1000)

    def test_R05_missing_raw_bytes_cannot_claim_public_source(self):
        ex,tick,book,h,s=responses()
        ex=replace(ex,raw_bytes=b"")
        with self.assertRaises(PublicMarketHold):
            select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+1000)

    def test_R06_raw_body_and_reported_decoded_body_must_agree(self):
        ex,tick,book,h,s=responses()
        forged=dict(ex.body)
        forged["symbols"]=list(forged["symbols"])
        forged["symbols"][0]={**forged["symbols"][0], "status":"BREAK"}
        ex=replace(ex,body=forged)  # raw bytes/sha still original
        with self.assertRaises(PublicMarketHold):
            select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+1000)

    def test_R07_byte_different_same_economics_changes_source_root(self):
        ex,tick,book,h,s=responses()
        alternate=pack(ex.kind,ex.path,ex.body,formatting=1)
        a=select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+1000)
        b=select_from_public_responses(alternate,tick,book,h,s,selected_at_ms=END_OPEN+1000)
        self.assertEqual(a.symbols,b.symbols)
        self.assertNotEqual(a.source_digest,b.source_digest)
        self.assertNotEqual(a.selection_digest,b.selection_digest)

    def test_R08_store_replays_three_source_digest_witnesses(self):
        ex,tick,book,h,s=responses()
        m=select_from_public_responses(ex,tick,book,h,s,selected_at_ms=END_OPEN+1000)
        with tempfile.TemporaryDirectory(prefix="nbot-g2-receipt-") as d:
            store=CompactObservationStore(Path(d))
            store.put_manifest(m)
            values=store.replay()
            self.assertEqual(len(values),1)
            self.assertEqual(len(values[0]["public_receipts"]),3)

    def test_R09_get_private_path_forbidden_even_internal_seam(self):
        client=PublicUsdMClient(allow_public_network=True,
             transport=lambda _: b"{}",now=lambda: 1_000_000)
        with self.assertRaises(PublicMarketHold):
            client._request("EXCHANGE_INFO","/fapi/v1/order",{},1)

    def test_R10_invalid_no_argument_not_get_private_account(self):
        c=PublicUsdMClient()
        self.assertFalse(hasattr(c,"api_key"))
        self.assertFalse(hasattr(c,"user_data"))
        self.assertFalse(hasattr(c,"create_order"))
        self.assertFalse(hasattr(c,"cancel_order"))


if __name__=="__main__":
    unittest.main()
