"""Network-free contract regression tests for bounded public HTTPS receipts."""
import hashlib
import json
import unittest

from nbot.v5.g4_https_capture import acquire_public_artifact

NOW=1_800_000_000_000


class Response:
    def __init__(self, url, data, status=200):
        self.url=url; self.body=data; self.status=status
    def geturl(self): return self.url
    def read(self, n): return self.body[:n]
    def __enter__(self): return self
    def __exit__(self, *args): return False


def call(kind, data, *, url_override=None, status=200, date="2026-10-12",
         from_ms=NOW-20_000, to_ms=NOW-10_000, start=NOW):
    clocks=iter((start,start+250))
    def opener(request, timeout):
        assert timeout == 15
        assert request.full_url.startswith("https://")
        return Response(url_override or request.full_url,data,status)
    return acquire_public_artifact(
        kind=kind,symbol="XRPUSDT",on_date=date,since_ms=from_ms,
        until_ms=to_ms,clock=lambda:next(clocks),opener=opener)


class CaptureContractTests(unittest.TestCase):
    def test_binance_original_archive_receipt_not_signed(self):
        r,p=call("DAILY_AGGTRADES_ZIP",b"synthetic archive bytes")
        self.assertEqual(r.content_sha256,hashlib.sha256(p).hexdigest())
        self.assertEqual(r.http_status,200)
        self.assertEqual(r.transport_hostname,"data.binance.vision")
        self.assertFalse(r.independently_exchange_signed)
        self.assertEqual(r.economic_label_authority,"NONE")
        self.assertIn("INJECTED_TEST",r.source_capture_mode)

    def test_checksum_source_location_is_exact(self):
        r,_=call("DAILY_AGGTRADES_CHECKSUM",b"a"*64+b"  XRPUSDT-aggTrades-2026-10-12.zip\n")
        self.assertTrue(r.request_url.endswith(".zip.CHECKSUM"))

    def test_same_url_and_bytes_deterministic_receipt(self):
        self.assertEqual(call("DAILY_AGGTRADES_ZIP",b"abc"),
                         call("DAILY_AGGTRADES_ZIP",b"abc"))

    def test_https_bookticker_has_prospective_receipt_only(self):
        value={"symbol":"XRPUSDT","bidPrice":"2.10","askPrice":"2.11",
               "time":NOW-100}
        r,_=call("BOOK_TICKER_AT_CAPTURE",json.dumps(value).encode())
        self.assertEqual(r.transport_hostname,"fapi.binance.com")
        self.assertIn("BOOK_TICKER",r.kind)
        self.assertFalse(r.independently_exchange_signed)

    def test_bookticker_crossed_rejected(self):
        obj={"symbol":"XRPUSDT","bidPrice":"3","askPrice":"2"}
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_BOOK_PRICE_INVALID"):
            call("BOOK_TICKER_AT_CAPTURE",json.dumps(obj).encode())

    def test_bookticker_wrong_symbol_rejected(self):
        obj={"symbol":"ETHUSDT","bidPrice":"2","askPrice":"3"}
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_BOOK_SYMBOL_INVALID"):
            call("BOOK_TICKER_AT_CAPTURE",json.dumps(obj).encode())

    def test_bookticker_future_server_clock_rejected(self):
        obj={"symbol":"XRPUSDT","bidPrice":"2","askPrice":"3","time":NOW+2_000}
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_BOOK_TIME_INVALID"):
            call("BOOK_TICKER_AT_CAPTURE",json.dumps(obj).encode())

    def test_aggtrade_recent_source_payload(self):
        obj=[{"a":9,"f":10,"l":10,"T":NOW-15_000,"p":"2","q":"3","m":True}]
        r,p=call("RECENT_AGGTRADES",json.dumps(obj).encode())
        self.assertIn("startTime",r.request_url)
        self.assertIn("endTime",r.request_url)
        self.assertEqual(r.content_sha256,hashlib.sha256(p).hexdigest())

    def test_funding_source_payload(self):
        obj=[{"symbol":"XRPUSDT","fundingTime":NOW-15_000,"fundingRate":"0.0001"}]
        r,_=call("FUNDING_HISTORY",json.dumps(obj).encode())
        self.assertIn("fundingRate",r.request_url)

    def test_no_arbitrary_hostname_redirect(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_REDIRECT_OR_HTTP_UNTRUSTED"):
            call("DAILY_AGGTRADES_ZIP",b"abc",
                 url_override="https://evil.example/data.zip")

    def test_same_hostname_redirect_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_REDIRECT_OR_HTTP_UNTRUSTED"):
            call("DAILY_AGGTRADES_ZIP",b"abc",
                 url_override="https://data.binance.vision/another.zip")

    def test_http_429_rate_limit_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_REDIRECT_OR_HTTP_UNTRUSTED"):
            call("DAILY_AGGTRADES_CHECKSUM",b"busy",status=429)

    def test_empty_response_is_hold(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_RESPONSE_EMPTY_OR_TOO_LARGE"):
            call("DAILY_AGGTRADES_ZIP",b"")

    def test_large_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_RESPONSE_EMPTY_OR_TOO_LARGE"):
            call("DAILY_AGGTRADES_CHECKSUM",b"x"*1025)

    def test_oversized_time_window_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_AGGTRADES_WINDOW_TOO_LARGE"):
            call("RECENT_AGGTRADES",b"[]",from_ms=NOW-3_600_000,to_ms=NOW)

    def test_bad_archive_date_and_symbol_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_ARCHIVE_DATE_INVALID"):
            call("DAILY_AGGTRADES_ZIP",b"abc",date="2026-02-30")
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_SYMBOL_INVALID"):
            acquire_public_artifact(kind="BOOK_TICKER_AT_CAPTURE",
                                    symbol="../BTCUSDT")

    def test_unknown_kind_cannot_call_network(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_KIND_UNSUPPORTED"):
            call("SECRET_ORDER",b"{}")

    def test_negative_body_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_CLOCK_INVALID"):
            call("DAILY_AGGTRADES_ZIP",b"abc",start=-1)

    def test_malformed_json_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_RESPONSE_JSON_INVALID"):
            call("RECENT_AGGTRADES",b"not json")

    def test_funding_symbol_mismatch_rejected(self):
        obj=[{"symbol":"ETHUSDT","fundingTime":NOW-15000,"fundingRate":"0.0002"}]
        with self.assertRaisesRegex(ValueError,"G4_HTTPS_FUNDING_SHAPE_INVALID"):
            call("FUNDING_HISTORY",json.dumps(obj).encode())


if __name__ == "__main__":
    unittest.main()
