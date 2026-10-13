"""Synthetic-only WSS routing and fail-closed feed safety tests."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.ws_contract import (
    FeedStatus, UnsafeStream, decode_frame, stream_urls,
)

EVENT = INTERVAL_MS * 1_000_000
RECEIVED = EVENT + INTERVAL_MS + 2_000
SYMBOLS = ("BTCUSDT", "ETHUSDT")


def wrap(kind, data, *, symbol="BTCUSDT"):
    return json.dumps({"stream": symbol.lower() + "@" + kind, "data": data})


def ticker(symbol="BTCUSDT", *, updated=1, bid="100", ask="101"):
    return wrap("bookTicker", {"e": "bookTicker", "E": RECEIVED - 15, "s": symbol,
                              "u": updated, "b": bid, "B": "5", "a": ask, "A": "6"},
                symbol=symbol)


def trade(symbol="BTCUSDT", *, agg=20):
    return wrap("aggTrade", {"e": "aggTrade", "E": RECEIVED - 10, "T": RECEIVED - 20,
                             "s": symbol, "a": agg, "p": "100", "q": "1"},
                symbol=symbol)


def kline(*, closed=True, opened=EVENT):
    return wrap("kline_5m", {
        "e": "kline", "E": RECEIVED - 5, "s": "BTCUSDT",
        "k": {"t": opened, "T": opened + INTERVAL_MS - 1,
              "s": "BTCUSDT", "i": "5m", "x": closed,
              "o": "100", "h": "102", "l": "99", "c": "101", "v": "20"}
    })


def parse(route, msg):
    return decode_frame(route, msg, received_ms=RECEIVED,
                        subscribed_symbols=SYMBOLS)


class V5WSSSafetyTests(unittest.TestCase):
    def test_wss_routes_split_market_from_public(self):
        plan = stream_urls(("ETHUSDT",))
        self.assertEqual(set(plan), {"market", "public"})
        self.assertTrue(plan["market"].startswith(
            "wss://fstream.binance.com/market/stream?streams="))
        self.assertTrue(plan["public"].startswith(
            "wss://fstream.binance.com/public/stream?streams="))
        self.assertIn("btcusdt@aggTrade", plan["market"])
        self.assertIn("btcusdt@bookTicker", plan["public"])
        self.assertNotIn("bookTicker", plan["market"])
        self.assertNotIn("aggTrade", plan["public"])
        self.assertNotIn("/private/", str(plan))

    def test_50_coin_universe_includes_btc_without_keys(self):
        symbols = tuple(f"COIN{i:02d}USDT" for i in range(50))
        plan = stream_urls(symbols)
        self.assertEqual(plan["market"].count("kline_5m"), 51)
        self.assertEqual(plan["public"].count("bookTicker"), 51)
        for invalid in ((), ("BTCUSDT", "BTCUSDT"), ("btcUSDT",),
                        tuple(f"X{i}USDT" for i in range(51))):
            with self.assertRaises(UnsafeStream):
                stream_urls(invalid)

    def test_aggregate_trade_and_book_have_separate_routes(self):
        book = parse("public", ticker())
        agg = parse("market", trade())
        self.assertEqual((book["bid"], book["ask"]), (100.0, 101.0))
        self.assertEqual(agg["aggregate_id"], 20)
        self.assertEqual(book["order_authority"], "NONE")
        for kind, message in (("market", ticker()), ("public", trade())):
            with self.assertRaisesRegex(UnsafeStream, "MISMATCH"):
                parse(kind, message)

    def test_unclosed_kline_not_usable_as_matured_candle(self):
        first = parse("market", kline(closed=False))
        self.assertFalse(first["closed"])
        final = parse("market", kline(closed=True))
        self.assertTrue(final["closed"])
        self.assertEqual(final["candle"][0], EVENT)
        with self.assertRaisesRegex(UnsafeStream, "NOT_YET_CLOSED"):
            parse("market", kline(closed=True, opened=EVENT + INTERVAL_MS))

    def test_foreign_symbol_wrong_stream_and_bad_candles_rejected(self):
        for route, message in (
            ("market", trade("SOLUSDT")),
            ("public", ticker(bid="105", ask="100")),
            ("market", kline(opened=EVENT + 1)),
            ("public", wrap("bookTicker", {"e": "bookTicker", "E": RECEIVED - 10,
                     "s": "BTCUSDT", "u": 1, "b": "nan", "B": "1",
                     "a": "101", "A": "1"})),
        ):
            with self.subTest(route=route), self.assertRaises(UnsafeStream):
                parse(route, message)

    def test_stale_frames_and_invalid_json_rejected(self):
        bad = json.loads(trade())
        bad["data"]["E"] = RECEIVED - 100_000
        with self.assertRaisesRegex(UnsafeStream, "STALE_OR_FUTURE"):
            parse("market", json.dumps(bad))
        for frame in ("not-json", "[]", "x" * 70_000):
            with self.assertRaises(UnsafeStream):
                parse("market", frame)

    def test_health_remains_fail_closed_until_new_cohort_verified(self):
        state = FeedStatus()
        ok, reasons = state.gate(symbol="BTCUSDT", now_ms=RECEIVED)
        self.assertFalse(ok)
        self.assertIn("QUOTE_DISCONNECTED", reasons)
        state.connect("market")
        state.connect("public")
        state.accept(parse("market", trade(agg=50)))
        state.accept(parse("public", ticker()))
        state.accept(parse("market", kline(closed=True)))
        ok, reasons = state.gate(symbol="BTCUSDT", now_ms=RECEIVED)
        self.assertFalse(ok)
        self.assertEqual(reasons, ("COHORT_NOT_VERIFIED",))

    def test_trade_gap_is_sticky_and_independent_of_quote_health(self):
        state = FeedStatus()
        state.connect("market")
        state.connect("public")
        state.accept(parse("market", trade(agg=100)))
        state.accept(parse("market", trade(agg=102)))
        state.accept(parse("market", trade(agg=103)))
        state.accept(parse("public", ticker()))
        self.assertIn("BTCUSDT", state.trade_gaps)
        _, reasons = state.gate(symbol="BTCUSDT", now_ms=RECEIVED)
        self.assertIn("TRADE_SEQUENCE_GAP", reasons)
        self.assertNotIn("QUOTE_STALE_OR_MISSING", reasons)
        state.disconnect("public")
        _, reasons = state.gate(symbol="BTCUSDT", now_ms=RECEIVED)
        self.assertIn("QUOTE_DISCONNECTED", reasons)
        self.assertIn("TRADE_SEQUENCE_GAP", reasons)
        state.connect("public")
        self.assertNotIn("BTCUSDT", state.last_quote_ms)
        self.assertIn("BTCUSDT", state.trade_gaps)

    def test_unordered_trade_ids_not_counted_as_new_evidence(self):
        state = FeedStatus()
        state.connect("market")
        state.accept(parse("market", trade(agg=50)))
        old = state.last_trade_ms["BTCUSDT"]
        state.accept(parse("market", trade(agg=50)))
        state.accept(parse("market", trade(agg=49)))
        self.assertEqual(state.last_trade_ms["BTCUSDT"], old)
        self.assertEqual(state.last_agg_id["BTCUSDT"], 50)

    def test_closed_kline_cursor_never_rewinds(self):
        state = FeedStatus()
        state.connect("market")
        state.accept(parse("market", kline(closed=True)))
        state.accept(parse("market", kline(closed=True)))
        self.assertEqual(state.last_closed_ms["BTCUSDT"], EVENT)
        state.disconnect("market")
        self.assertNotIn("BTCUSDT", state.last_closed_ms)
        with self.assertRaisesRegex(UnsafeStream, "DISCONNECTED_EVENT"):
            state.accept(parse("market", trade()))

    def test_one_shot_probe_gates_both_routes_without_real_sockets(self):
        from nbot.v5.ws_probe import run_probe
        async def sample(route, url, symbols, *, seconds):
            self.assertTrue(url.startswith("wss://fstream.binance.com/"))
            self.assertEqual(seconds, 12)
            return {"route": route, "connected": True, "received_frames": 4,
                    "accepted_events": {"aggTrade": 3} if route == "market"
                        else {"bookTicker": 4},
                    "rejected_frames": {}}
        with patch("nbot.v5.ws_probe._sample", side_effect=sample):
            report = asyncio.run(run_probe(symbols=SYMBOLS, seconds=12))
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["paper_trades"], 0)
        self.assertFalse(report["service_started"])

    def test_one_shot_probe_rejects_unhealthy_route(self):
        from nbot.v5.ws_probe import run_probe
        async def sample(route, url, symbols, *, seconds):
            return {"route": route, "connected": True,
                    "accepted_events": {} if route == "public"
                        else {"aggTrade": 1}, "rejected_frames": {}}
        with patch("nbot.v5.ws_probe._sample", side_effect=sample):
            report = asyncio.run(run_probe(symbols=SYMBOLS, seconds=12))
        self.assertEqual(report["result"], "HOLD")
        with self.assertRaises(ValueError):
            asyncio.run(run_probe(symbols=SYMBOLS, seconds=60))


    def test_500ms_depth_mode_uses_lower_frequency_public_stream(self):
        plan = stream_urls(("BTCUSDT", "ETHUSDT"), quote_mode="depth5@500ms")
        self.assertIn("btcusdt@depth5@500ms", plan["public"])
        self.assertNotIn("bookTicker", plan["public"])
        self.assertIn("btcusdt@aggTrade", plan["market"])
        with self.assertRaisesRegex(UnsafeStream, "QUOTE_MODE_INVALID"):
            stream_urls(("BTCUSDT",), quote_mode="unknown")

    def test_500ms_depth_snapshots_validate_real_bid_ask(self):
        data = {"e": "depthUpdate", "E": RECEIVED - 10, "T": RECEIVED - 15,
                "s": "BTCUSDT", "U": 80, "u": 85, "pu": 79,
                "b": [["100", "2"], ["99", "3"]],
                "a": [["101", "4"], ["102", "5"]], "st": 1, "ps": "BTCUSDT"}
        msg = wrap("depth5@500ms", data)
        parsed = parse("public", msg)
        self.assertEqual(parsed["kind"], "depth5@500ms")
        self.assertEqual((parsed["bid"], parsed["ask"]), (100.0, 101.0))
        self.assertEqual(parsed["quote_source"], "PARTIAL_DEPTH_500MS")
        self.assertEqual(parsed["order_authority"], "NONE")
        state = FeedStatus()
        state.connect("public")
        state.accept(parsed)
        self.assertEqual(state.last_quote_ms["BTCUSDT"], RECEIVED)

    def test_500ms_depth_invalid_snapshots_refused(self):
        base = {"e": "depthUpdate", "E": RECEIVED - 10,
                "s": "BTCUSDT", "U": 80, "u": 85,
                "b": [["100", "2"]], "a": [["101", "4"]]}
        samples = (
            dict(base, st=2),
            dict(base, ps="ETHUSDT"),
            dict(base, b=[["102", "2"]]),
            dict(base, b=[]),
            dict(base, b=[["100", "0"]]),
            dict(base, u=79),
            dict(base, a=[["nan", "4"]]),
            dict(base, b=[["99", "1"], ["100", "2"]]),
        )
        for candidate in samples:
            with self.subTest(candidate=candidate), self.assertRaises(UnsafeStream):
                parse("public", wrap("depth5@500ms", candidate))



if __name__ == "__main__":
    unittest.main()
