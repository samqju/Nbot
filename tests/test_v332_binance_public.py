from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import patch

from nbot.config.profiles import get_profile
from nbot.observation.binance_public import (
    BinancePublicMarketError,
    BinanceUsdMPublicClient,
    USER_AGENT,
)
from nbot.observation.config import observation_config_for_profile
from nbot.observation.public_market import PublicMarketClient


INTERVAL = 300_000


def kline(symbol: str, open_ms: int, close: float = 100.5):
    del symbol
    return [
        open_ms,
        "100.0",
        "101.0",
        "99.0",
        str(close),
        "10.0",
        open_ms + INTERVAL - 1,
        "1000.0",
        20,
        "5.0",
        "500.0",
        "0",
    ]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


class Router:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def __call__(self, request, timeout):
        parsed = urlparse(request.full_url)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        self.calls.append((request, timeout, parsed.path, query))
        payload = self.handler(parsed.path, query)
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(payload)


class TickClock:
    def __init__(self, start=1_000):
        self.value = start

    def __call__(self):
        value = self.value
        self.value += 1
        return value


class V332BinancePublicTests(unittest.TestCase):
    def cfg(self):
        return observation_config_for_profile(get_profile("live-paper"))

    def client(self, handler, *, clock=None):
        router = Router(handler)
        client = BinanceUsdMPublicClient(
            self.cfg(), urlopen_fn=router, local_time_ms_fn=clock or TickClock()
        )
        return client, router

    def test_server_time_is_public_credential_free_and_pinned_to_configured_host(self):
        client, router = self.client(lambda path, query: {"serverTime": 123456789})
        self.assertEqual(client.server_time_ms(), 123456789)
        request, timeout, path, query = router.calls[0]
        self.assertEqual(path, "/fapi/v1/time")
        self.assertEqual(query, {})
        self.assertEqual(urlparse(request.full_url).netloc, "fapi.binance.com")
        self.assertEqual(request.get_header("User-agent"), USER_AGENT)
        self.assertIsNone(request.get_header("X-mbx-apikey"))
        self.assertEqual(timeout, self.cfg().request_timeout_seconds)

    def test_testnet_public_profile_uses_demo_fapi_without_credentials(self):
        router = Router(lambda path, query: {"serverTime": 42})
        client = BinanceUsdMPublicClient(
            observation_config_for_profile(get_profile("testnet-trade")),
            urlopen_fn=router,
        )
        self.assertEqual(client.server_time_ms(), 42)
        request = router.calls[0][0]
        self.assertEqual(urlparse(request.full_url).netloc, "demo-fapi.binance.com")
        self.assertIsNone(request.get_header("X-mbx-apikey"))

    def test_client_satisfies_public_market_contract(self):
        client, _ = self.client(lambda path, query: {"serverTime": 1})
        self.assertIsInstance(client, PublicMarketClient)

    def test_universe_is_usdt_perpetual_filtered_thresholded_and_deterministically_ranked(self):
        def handler(path, query):
            if path == "/fapi/v1/exchangeInfo":
                return {"symbols": [
                    {"symbol": "BTCUSDT", "status": "TRADING", "contractType": "PERPETUAL", "quoteAsset": "USDT"},
                    {"symbol": "ETHUSDT", "status": "TRADING", "contractType": "PERPETUAL", "quoteAsset": "USDT"},
                    {"symbol": "LOWUSDT", "status": "TRADING", "contractType": "PERPETUAL", "quoteAsset": "USDT"},
                    {"symbol": "WIDEUSDT", "status": "TRADING", "contractType": "PERPETUAL", "quoteAsset": "USDT"},
                    {"symbol": "OLDUSDT", "status": "BREAK", "contractType": "PERPETUAL", "quoteAsset": "USDT"},
                    {"symbol": "DELIVERYUSDT", "status": "TRADING", "contractType": "CURRENT_QUARTER", "quoteAsset": "USDT"},
                    {"symbol": "BTCUSDC", "status": "TRADING", "contractType": "PERPETUAL", "quoteAsset": "USDC"},
                ]}
            if path == "/fapi/v1/ticker/24hr":
                return [
                    {"symbol": "BTCUSDT", "quoteVolume": "20000000"},
                    {"symbol": "ETHUSDT", "quoteVolume": "30000000"},
                    {"symbol": "LOWUSDT", "quoteVolume": "1"},
                    {"symbol": "WIDEUSDT", "quoteVolume": "9000000"},
                ]
            if path == "/fapi/v1/ticker/bookTicker":
                return [
                    {"symbol": "BTCUSDT", "bidPrice": "100", "askPrice": "100.1"},
                    {"symbol": "ETHUSDT", "bidPrice": "50", "askPrice": "50.05"},
                    {"symbol": "LOWUSDT", "bidPrice": "1", "askPrice": "1.001"},
                    {"symbol": "WIDEUSDT", "bidPrice": "1", "askPrice": "2"},
                ]
            if path == "/fapi/v1/premiumIndex":
                return [
                    {"symbol": "BTCUSDT", "markPrice": "100.05", "indexPrice": "100.04", "lastFundingRate": "0.0001", "nextFundingTime": 9999},
                    {"symbol": "ETHUSDT", "markPrice": "50.02", "indexPrice": "50.01", "lastFundingRate": "-0.0002", "nextFundingTime": 9999},
                ]
            raise AssertionError(path)

        client, _ = self.client(handler)
        capture = client.eligible_universe_capture()
        self.assertEqual([row.symbol for row in capture.rows], ["ETHUSDT", "BTCUSDT"])
        self.assertEqual([row.universe_rank for row in capture.rows], [1, 2])
        self.assertEqual(capture.rows[0].funding_rate, -0.0002)
        self.assertEqual(
            [source.source for source in capture.source_captures],
            ["exchange_info", "ticker_24h", "book_ticker", "premium_index"],
        )

    def test_universe_source_capture_times_cover_each_http_request(self):
        def handler(path, query):
            if path == "/fapi/v1/exchangeInfo":
                return {"symbols": []}
            return []

        client, _ = self.client(handler, clock=TickClock(100))
        captures = client.eligible_universe_capture().source_captures
        self.assertEqual(
            [(row.started_at_ms, row.finished_at_ms) for row in captures],
            [(100, 101), (102, 103), (104, 105), (106, 107)],
        )

    def test_universe_rejects_malformed_required_payload(self):
        def handler(path, query):
            if path == "/fapi/v1/exchangeInfo":
                return []
            return []

        client, _ = self.client(handler)
        with self.assertRaisesRegex(BinancePublicMarketError, "EXCHANGE_INFO_PAYLOAD_INVALID"):
            client.eligible_universe_capture()

    def test_closed_candles_return_successes_and_explicit_symbol_errors(self):
        def handler(path, query):
            self.assertEqual(path, "/fapi/v1/klines")
            if query["symbol"] == "BTCUSDT":
                return [kline("BTCUSDT", 600_000)]
            return []

        client, _ = self.client(handler)
        candles, errors = client.closed_candles(["ETHUSDT", "BTCUSDT"], 600_000)
        self.assertEqual(list(candles), ["BTCUSDT"])
        self.assertEqual(candles["BTCUSDT"].open_time_ms, 600_000)
        self.assertEqual(list(errors), ["ETHUSDT"])
        self.assertIn("CANONICAL_CANDLE_MISSING", errors["ETHUSDT"])

    def test_closed_candle_rejects_wrong_binance_open_time(self):
        client, _ = self.client(
            lambda path, query: [kline(query["symbol"], 900_000)]
            if path == "/fapi/v1/klines" else None
        )
        candles, errors = client.closed_candles(["BTCUSDT"], 600_000)
        self.assertEqual(candles, {})
        self.assertIn("CANONICAL_CANDLE_WRONG_OPEN", errors["BTCUSDT"])

    def test_historical_candles_return_only_requested_times_and_require_full_coverage(self):
        def handler(path, query):
            if path != "/fapi/v1/klines":
                raise AssertionError(path)
            symbol = query["symbol"]
            start = int(query["startTime"])
            if symbol == "BTCUSDT":
                return [
                    row for row in (
                        kline(symbol, 600_000),
                        kline(symbol, 900_000),
                        kline(symbol, 1_200_000),
                    )
                    if row[0] >= start
                ]
            return [kline(symbol, 600_000)] if start <= 600_000 else []

        client, _ = self.client(handler)
        output, errors = client.historical_candles_for_symbols(
            ["BTCUSDT", "ETHUSDT"], [600_000, 1_200_000]
        )
        self.assertEqual(list(output), ["BTCUSDT"])
        self.assertEqual(list(output["BTCUSDT"]), [600_000, 1_200_000])
        self.assertEqual(list(errors), ["ETHUSDT"])
        self.assertIn("HISTORICAL_CANDLES_MISSING", errors["ETHUSDT"])

    def test_historical_candle_bounds_must_align_to_five_minute_clock(self):
        client, _ = self.client(lambda path, query: [])
        with self.assertRaisesRegex(ValueError, "HISTORICAL_CANDLE_ALIGNMENT_INVALID"):
            client.historical_candles_for_symbols(["BTCUSDT"], [600_001])

    def test_funding_history_is_deduplicated_sorted_and_range_filtered(self):
        def handler(path, query):
            self.assertEqual(path, "/fapi/v1/fundingRate")
            return [
                {"symbol": "ETHUSDT", "fundingTime": 2000, "fundingRate": "-0.0002", "markPrice": "50"},
                {"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.0001", "markPrice": "100"},
                {"symbol": "BTCUSDT", "fundingTime": 1000, "fundingRate": "0.0001", "markPrice": "100"},
                {"symbol": "BTCUSDT", "fundingTime": 9999, "fundingRate": "0.1", "markPrice": "100"},
            ]

        client, _ = self.client(handler)
        rows = tuple(client.funding_history(500, 3000))
        self.assertEqual([(row.symbol, row.funding_time_ms) for row in rows], [
            ("BTCUSDT", 1000), ("ETHUSDT", 2000)
        ])

    def test_funding_full_page_is_time_bisected_instead_of_skipping_boundary_rows(self):
        def handler(path, query):
            self.assertEqual(path, "/fapi/v1/fundingRate")
            start = int(query["startTime"])
            end = int(query["endTime"])
            if start == 0 and end == 9:
                return [
                    {"symbol": "BTCUSDT", "fundingTime": 2, "fundingRate": "0.1", "markPrice": "100"},
                    {"symbol": "ETHUSDT", "fundingTime": 7, "fundingRate": "0.2", "markPrice": "50"},
                ]
            if end <= 4:
                return [{"symbol": "BTCUSDT", "fundingTime": 2, "fundingRate": "0.1", "markPrice": "100"}]
            return [{"symbol": "ETHUSDT", "fundingTime": 7, "fundingRate": "0.2", "markPrice": "50"}]

        client, router = self.client(handler)
        with patch("nbot.observation.binance_public.MAX_FUNDING_ROWS", 2):
            rows = tuple(client.funding_history(0, 9))
        self.assertEqual([(row.symbol, row.funding_time_ms) for row in rows], [
            ("BTCUSDT", 2), ("ETHUSDT", 7)
        ])
        funding_calls = [call for call in router.calls if call[2] == "/fapi/v1/fundingRate"]
        self.assertEqual(len(funding_calls), 3)

    def test_network_error_fails_explicitly(self):
        client, _ = self.client(lambda path, query: URLError("offline"))
        with self.assertRaisesRegex(BinancePublicMarketError, "PUBLIC_NETWORK_ERROR"):
            client.server_time_ms()

    def test_invalid_json_fails_explicitly(self):
        router = Router(lambda path, query: b"not-json")
        client = BinanceUsdMPublicClient(self.cfg(), urlopen_fn=router)
        with self.assertRaisesRegex(BinancePublicMarketError, "PUBLIC_JSON_INVALID"):
            client.server_time_ms()

    def test_client_source_contains_no_private_or_order_endpoint_contract(self):
        source = Path(__file__).resolve().parents[1] / "nbot/observation/binance_public.py"
        text = source.read_text(encoding="utf-8").lower()
        forbidden = (
            "x-mbx-apikey",
            "/fapi/v1/order",
            "/fapi/v1/account",
            "/fapi/v2/account",
            "api_secret",
            "api_key",
        )
        for token in forbidden:
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
