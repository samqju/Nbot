"""Mocked live top-50 WSS capacity selection; never contacts Binance."""
import asyncio
import unittest
from unittest.mock import patch

from nbot.v5.public_market import PublicMarketDataError
from nbot.v5.ws_capacity_probe import run_probe, select_live_universe
from tests.test_v5_public_market import (
    SERVER, DONE, SYMBOLS, exchange, ticker,
)


def public_stub(path, params=None):
    assert params is None
    if path == "/fapi/v1/time":
        return {"serverTime": SERVER}
    if path == "/fapi/v1/exchangeInfo":
        return exchange()
    if path == "/fapi/v1/ticker/24hr":
        return ticker()
    raise AssertionError("Unexpected route: " + path)


class WSSLiveUniverseTests(unittest.TestCase):
    def test_current_top50_is_reproducible_and_contains_no_contracts(self):
        urls = []
        def getter(path, params=None):
            urls.append(path)
            return public_stub(path, params)
        result = select_live_universe(
            top=50, getter=getter, clock_ms=lambda: DONE
        )
        self.assertEqual(len(result["eligible_symbols"]), 50)
        self.assertIn("BTCUSDT", result["eligible_symbols"])
        self.assertEqual(result["eligible_symbols"][0], "BTCUSDT")
        self.assertNotIn(SYMBOLS[-1], result["eligible_symbols"])
        self.assertEqual(len(result["universe_digest"]), 64)
        self.assertFalse(result["historical_eligibility_asserted"])
        self.assertEqual(urls, [
            "/fapi/v1/time", "/fapi/v1/exchangeInfo",
            "/fapi/v1/ticker/24hr",
        ])
        self.assertEqual(result, select_live_universe(
            top=50, getter=public_stub, clock_ms=lambda: DONE
        ))

    def test_invalid_counts_and_server_clock_fail_before_network(self):
        for top in (0, 51, True, -1, 1.5):
            with self.subTest(top=top), self.assertRaises(PublicMarketDataError):
                select_live_universe(
                    top=top, getter=lambda path: self.fail("NO API CALL")
                )
        for local in (SERVER - 100_000, SERVER + 100_000):
            with self.subTest(clock=local), self.assertRaisesRegex(
                PublicMarketDataError, "CLOCK_SKEW"
            ):
                select_live_universe(
                    top=50, getter=public_stub, clock_ms=lambda: local
                )

    def test_stale_request_and_missing_top50_fail_closed(self):
        times = iter([SERVER, SERVER + 91_000])
        with self.assertRaisesRegex(PublicMarketDataError, "TOO_OLD"):
            select_live_universe(
                top=50, getter=public_stub, clock_ms=lambda: next(times)
            )
        def few(path, params=None):
            if path == "/fapi/v1/ticker/24hr":
                return ticker()[:12]
            return public_stub(path, params)
        with self.assertRaisesRegex(PublicMarketDataError, "INCOMPLETE"):
            select_live_universe(
                top=50, getter=few, clock_ms=lambda: DONE
            )

    def test_50_symbol_sample_is_always_unready_without_full_feeds(self):
        symbols = select_live_universe(
            top=50, getter=public_stub, clock_ms=lambda: DONE
        )["eligible_symbols"]

        async def sample(route, url, store, *, seconds):
            self.assertEqual(seconds, 10)
            self.assertLess(len(url), 6000)
            store.connect(route)
            if route == "public":
                store.totals["quote"] = 1000
                store.coins[symbols[0]].last_quote = {
                    "quote_source": "PARTIAL_DEPTH_500MS"
                }
            else:
                store.totals["trade"] = 1000
            return {"route": route, "connected": True,
                    "frames": 1000, "rejected": {}, "frame_cap_hit": False,
                    "duration_seconds": 10}

        with patch("nbot.v5.ws_capacity_probe._sample", side_effect=sample):
            result = asyncio.run(run_probe(
                symbols=symbols, seconds=10, quote_mode="depth5@500ms"
            ))
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["eligibility_count"], 50)
        self.assertEqual(result["total_symbols_including_btc"], 50)
        self.assertEqual(result["buffer"]["symbol_count"], 50)
        self.assertEqual(result["buffer"]["latest_quotes_retained"], 1)
        self.assertFalse(result["research_ready"])
        self.assertEqual(result["order_authority"], "NONE")
        self.assertFalse(result["database_written"])
        self.assertFalse(result["persistent_service_started"])


if __name__ == "__main__":
    unittest.main()
