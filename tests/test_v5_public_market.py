"""Offline mocked tests for the public, credential-free Binance market probe."""
import unittest

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import (
    PublicMarketDataError, closed_event_from_server_time, collect_once,
    decode_klines, public_get, select_universe,
)

EVENT = INTERVAL_MS * 1_000_000
SERVER = EVENT + INTERVAL_MS + 20_000
DONE = SERVER + 6_000
SYMBOLS = tuple(f"COIN{i:02d}USDT" for i in range(55))


def klines(event=EVENT):
    start = event - 95 * INTERVAL_MS
    return [[start + i * INTERVAL_MS, "100", "101", "99", "100", "10",
             start + (i + 1) * INTERVAL_MS - 1, "1000", 1, "5", "500", "0"]
            for i in range(96)]


def exchange():
    syms = ["BTCUSDT", *SYMBOLS]
    return {
        "symbols": [
            {"symbol": s, "contractType": "PERPETUAL",
             "quoteAsset": "USDT", "marginAsset": "USDT",
             "status": "TRADING"}
            for s in syms
        ] + [
            {"symbol": "COINBADUSDT", "contractType": "CURRENT_QUARTER",
             "quoteAsset": "USDT", "marginAsset": "USDT", "status": "TRADING"}
        ],
    }


def ticker():
    return [{"symbol": s, "quoteVolume": str(10_000_000 - i * 500)}
            for i, s in enumerate(["BTCUSDT", *SYMBOLS])]


def stub(*, bad=None, log=None, ret=None):
    def get(path, params=None):
        if log is not None:
            log.append((path, params))
        if path == "/fapi/v1/time":
            return {"serverTime": SERVER}
        if path == "/fapi/v1/exchangeInfo":
            return exchange()
        if path == "/fapi/v1/ticker/24hr":
            return ticker()
        if path == "/fapi/v1/klines":
            assert params is not None
            assert params["interval"] == "5m"
            assert params["limit"] == "96"
            assert int(params["startTime"]) == EVENT - 95 * INTERVAL_MS
            assert int(params["endTime"]) == EVENT + INTERVAL_MS - 1
            if params["symbol"] == bad:
                if ret is None:
                    raise PublicMarketDataError("TEST_BAD_FEED")
                return ret
            return klines()
        raise AssertionError("Unexpected endpoint")
    return get


class PublicMarketTests(unittest.TestCase):
    def test_server_time_excludes_unclosed_candle(self):
        self.assertEqual(closed_event_from_server_time(
            {"serverTime": SERVER})[0], EVENT)
        for v in ({}, {"serverTime": "123"}, {"serverTime": -1}):
            with self.assertRaises(PublicMarketDataError):
                closed_event_from_server_time(v)

    def test_top_50_uses_only_trading_usdt_perpetual_volume(self):
        universe = select_universe(exchange(), ticker(), limit=50)
        self.assertEqual(len(universe), 50)
        self.assertEqual(universe[0], "BTCUSDT")
        self.assertNotIn("COINBADUSDT", universe)
        self.assertNotIn(SYMBOLS[-1], universe)

    def test_invalid_volumes_and_duplicate_records_fail_closed(self):
        bad = ticker()
        bad[0]["quoteVolume"] = "-99"
        with self.assertRaisesRegex(PublicMarketDataError, "VOLUME_INVALID"):
            select_universe(exchange(), bad, limit=12)
        with self.assertRaisesRegex(PublicMarketDataError, "TICKER_DUPLICATE"):
            select_universe(exchange(), ticker() + ticker()[:1], limit=12)
        with self.assertRaisesRegex(PublicMarketDataError, "LIMIT_INVALID"):
            select_universe(exchange(), ticker(), limit=51)

    def test_bars_are_exact_contiguous_96_with_exchange_close_time(self):
        result = decode_klines(klines(), event_open_ms=EVENT)
        self.assertEqual(len(result), 96)
        self.assertEqual(result[-1][0], EVENT)
        self.assertEqual(len(result[-1]), 6)

    def test_unclosed_and_future_bars_rejected(self):
        for bad in (
            klines()[:-1],
            klines()[:-1] + [
                [EVENT + INTERVAL_MS, "100", "101", "99", "100", "10",
                 EVENT + 2 * INTERVAL_MS - 1]
            ],
            klines()[:-1] + [
                [EVENT, "100", "101", "99", "100", "10",
                 EVENT + 2 * INTERVAL_MS - 1]
            ],
            klines()[:50] + klines()[51:],
        ):
            with self.subTest(length=len(bad)):
                with self.assertRaises(PublicMarketDataError):
                    decode_klines(bad, event_open_ms=EVENT)

    def test_invalid_ohlcv_rejected(self):
        for index, value in ((1, "nan"), (2, "98"), (3, "103"),
                             (4, "0"), (5, "-1")):
            data = klines()
            data[-1][index] = value
            with self.subTest(index=index), self.assertRaises(PublicMarketDataError):
                decode_klines(data, event_open_ms=EVENT)

    def test_bounded_public_get_disallows_private_or_order_urls(self):
        for endpoint in ("/fapi/v1/order", "/fapi/v2/account", "https://evil.test/",
                         "/fapi/v1/klines/../../order"):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(
                PublicMarketDataError, "ENDPOINT_NOT_ALLOWED"
            ):
                public_get(endpoint)

    def test_complete_12_market_public_snapshot_observes_both_sides(self):
        calls = []
        result = collect_once(limit=12, getter=stub(log=calls), clock_ms=lambda: DONE)
        self.assertEqual(result["observations"], 24)
        self.assertEqual(result["observed"], 24)
        self.assertEqual(result["unscorable"], 0)
        self.assertEqual(result["paper_trades"], 0)
        self.assertEqual(result["order_authority"], "NONE")
        self.assertEqual(len(result["eligible_symbols"]), 12)
        self.assertEqual(len([p for p, _ in calls if p == "/fapi/v1/klines"]), 12)
        self.assertTrue(all(x[0] in (
            "/fapi/v1/time", "/fapi/v1/exchangeInfo",
            "/fapi/v1/ticker/24hr", "/fapi/v1/klines"
        ) for x in calls))

    def test_context_only_btc_is_always_fetched(self):
        data = ticker()
        for i, row in enumerate(data):
            if row["symbol"] == "BTCUSDT":
                row["quoteVolume"] = "1"
        def get(path, params=None):
            if path == "/fapi/v1/ticker/24hr":
                return data
            return stub()(path, params)
        # BTC is outside the top-12, but remains mandatory context.
        probe = collect_once(limit=12, getter=get, clock_ms=lambda: DONE)
        self.assertNotIn("BTCUSDT", probe["eligible_symbols"])
        self.assertTrue(probe["btc_context_available"])
        self.assertEqual(probe["observed"], 24)

    def test_one_missing_symbol_remains_recorded(self):
        bad = "COIN00USDT"
        result = collect_once(limit=12, getter=stub(bad=bad), clock_ms=lambda: DONE)
        self.assertEqual(result["observations"], 24)
        self.assertEqual(result["observed"], 22)
        self.assertEqual(result["unscorable"], 2)
        self.assertEqual(result["candle_failures"][bad], "TEST_BAD_FEED")

    def test_missing_btc_abstains_all(self):
        result = collect_once(limit=12, getter=stub(bad="BTCUSDT"),
                              clock_ms=lambda: DONE)
        self.assertFalse(result["btc_context_available"])
        self.assertEqual(result["unscorable"], 24)

    def test_bad_kline_response_is_declared_not_silently_trimmed(self):
        result = collect_once(limit=12, getter=stub(bad="COIN00USDT", ret=klines()[:-1]),
                              clock_ms=lambda: DONE)
        self.assertEqual(result["unscorable"], 2)
        self.assertEqual(result["candle_failures"]["COIN00USDT"],
                         "V5_CANDLE_HISTORY_INCOMPLETE")

    def test_stale_or_skewed_clock_forbids_snapshot(self):
        for ms in (SERVER - 100_000, SERVER + 100_000):
            with self.assertRaises(PublicMarketDataError):
                collect_once(limit=12, getter=stub(), clock_ms=lambda: ms)

    def test_cross_boundary_prohibits_stale_outcome(self):
        values = iter([SERVER, EVENT + 2 * INTERVAL_MS])
        with self.assertRaisesRegex(PublicMarketDataError, "BECAME_STALE"):
            collect_once(limit=12, getter=stub(),
                         clock_ms=lambda: next(values))


if __name__ == "__main__":
    unittest.main()
