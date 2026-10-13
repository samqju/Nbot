"""Synthetic resource caps, candle continuity and quote coalescing tests."""
import asyncio
import json
import unittest
from unittest.mock import patch

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.stream_buffer import BoundedObservationBuffer
from nbot.v5.ws_contract import UnsafeStream
from tests.test_v5_ws_contract import (
    EVENT, RECEIVED, kline, ticker, trade,
)
from tests.test_v5_public_market import klines


def quote_with_update(update):
    return ticker(updated=update)


def closed_for(open_ms: int, *, price="101"):
    payload = json.loads(kline(closed=True, opened=open_ms))
    payload["data"]["E"] = open_ms + INTERVAL_MS + 1
    payload["data"]["k"]["c"] = price
    payload["data"]["k"]["h"] = "105"
    return json.dumps(payload)


class V5BoundedStreamTests(unittest.TestCase):
    def setUp(self):
        self.buffer = BoundedObservationBuffer(("BTCUSDT", "ETHUSDT"))
        self.buffer.connect("market")
        self.buffer.connect("public")

    def test_2000_book_messages_consume_one_last_quote_slot(self):
        for i in range(1, 2001):
            self.assertEqual(
                self.buffer.consume("public", quote_with_update(i), received_ms=RECEIVED),
                "QUOTE_LATEST_REPLACED",
            )
        status = self.buffer.describe()
        self.assertEqual(status["latest_quotes_retained"], 1)
        self.assertEqual(status["event_counts"]["quote"], 2000)
        self.assertEqual(len(self.buffer.coins), 2)
        self.assertEqual(self.buffer.coins["BTCUSDT"].last_quote_update_id, 2000)
        self.assertEqual(status["total_candles_retained"], 0)

    def test_out_of_order_quotes_cannot_refresh_quote_freshness(self):
        self.buffer.consume("public", quote_with_update(12), received_ms=RECEIVED)
        self.assertEqual(
            self.buffer.consume("public", quote_with_update(11), received_ms=RECEIVED + 1),
            "OUT_OF_ORDER_QUOTE",
        )
        self.assertEqual(self.buffer.health.last_quote_ms["BTCUSDT"], RECEIVED)
        self.assertEqual(self.buffer.coins["BTCUSDT"].last_quote_update_id, 12)

    def test_only_closed_5min_candles_are_stored(self):
        self.assertEqual(
            self.buffer.consume("market", kline(closed=False), received_ms=RECEIVED),
            "UNFINISHED_CANDLE_IGNORED",
        )
        self.assertEqual(self.buffer.describe()["total_candles_retained"], 0)
        self.assertEqual(
            self.buffer.consume("market", kline(closed=True), received_ms=RECEIVED),
            "CLOSED_CANDLE_ACCEPTED",
        )
        self.assertEqual(self.buffer.describe()["total_candles_retained"], 1)

    def test_rest_seeds_96_bars_and_wss_rolls_forward_exactly_once(self):
        self.buffer.seed_closed_candles("BTCUSDT", klines(), event_open_ms=EVENT)
        self.assertEqual(
            self.buffer.candle_readiness(
                symbol="BTCUSDT", event_open_ms=EVENT, now_ms=RECEIVED
            ), (True, ()),
        )
        self.assertEqual(
            self.buffer.consume("market", closed_for(EVENT + INTERVAL_MS),
                                received_ms=EVENT + 2 * INTERVAL_MS + 2),
            "CLOSED_CANDLE_ACCEPTED",
        )
        self.assertEqual(len(self.buffer.coins["BTCUSDT"].closed_candles), 96)
        self.assertEqual(
            self.buffer.coins["BTCUSDT"].closed_candles[-1][0], EVENT + INTERVAL_MS
        )
        self.assertEqual(
            self.buffer.candle_readiness(
                symbol="BTCUSDT", event_open_ms=EVENT + INTERVAL_MS,
                now_ms=EVENT + 2 * INTERVAL_MS + 2
            ), (True, ()),
        )

    def test_gap_holds_and_cannot_silently_move_ledger_cursor(self):
        self.buffer.seed_closed_candles("BTCUSDT", klines(), event_open_ms=EVENT)
        old_cursor = self.buffer.coins["BTCUSDT"].closed_candles[-1][0]
        self.assertEqual(
            self.buffer.consume("market", closed_for(EVENT + 2 * INTERVAL_MS),
                                received_ms=EVENT + 3 * INTERVAL_MS + 2),
            "CANDLE_GAP_HOLD",
        )
        coin = self.buffer.coins["BTCUSDT"]
        self.assertEqual(coin.closed_candles[-1][0], old_cursor)
        self.assertTrue(coin.candle_gap)
        valid, reasons = self.buffer.candle_readiness(
            symbol="BTCUSDT", event_open_ms=EVENT + 2 * INTERVAL_MS,
            now_ms=EVENT + 3 * INTERVAL_MS + 2
        )
        self.assertFalse(valid)
        self.assertIn("CANDLE_GAP_UNRESOLVED", reasons)
        with self.assertRaisesRegex(UnsafeStream, "MANUAL_REPAIR"):
            self.buffer.seed_closed_candles(
                "BTCUSDT", klines(EVENT + 2 * INTERVAL_MS),
                event_open_ms=EVENT + 2 * INTERVAL_MS
            )

    def test_conflicting_final_close_cannot_override_record(self):
        self.buffer.consume("market", kline(closed=True), received_ms=RECEIVED)
        original = self.buffer.coins["BTCUSDT"].closed_candles[-1]
        with self.assertRaisesRegex(UnsafeStream, "CONFLICTING_FINAL_CANDLE"):
            self.buffer.consume(
                "market", closed_for(EVENT, price="102"), received_ms=RECEIVED
            )
        self.assertEqual(self.buffer.coins["BTCUSDT"].closed_candles[-1], original)
        self.assertTrue(self.buffer.coins["BTCUSDT"].candle_conflict)

    def test_market_reconnect_revokes_history_readiness(self):
        self.buffer.seed_closed_candles("BTCUSDT", klines(), event_open_ms=EVENT)
        self.buffer.disconnect("market")
        valid, reasons = self.buffer.candle_readiness(
            symbol="BTCUSDT", event_open_ms=EVENT, now_ms=RECEIVED
        )
        self.assertFalse(valid)
        self.assertIn("MARKET_DISCONNECTED", reasons)
        self.buffer.connect("market")
        valid, reasons = self.buffer.candle_readiness(
            symbol="BTCUSDT", event_open_ms=EVENT, now_ms=RECEIVED
        )
        self.assertFalse(valid)
        self.assertIn("HISTORY_NOT_ANCHORED", reasons)

    def test_trade_gap_survives_market_reconnect_without_rest_repair(self):
        self.buffer.consume("market", trade(agg=100), received_ms=RECEIVED)
        self.buffer.consume("market", trade(agg=102), received_ms=RECEIVED)
        self.assertIn("BTCUSDT", self.buffer.health.trade_gaps)
        self.buffer.disconnect("market")
        self.buffer.connect("market")
        self.assertIn("BTCUSDT", self.buffer.health.trade_gaps)
        self.assertIsNone(self.buffer.coins["BTCUSDT"].last_trade)

    def test_seed_missing_bar_or_conflicting_rest_and_wss_refused(self):
        with self.assertRaisesRegex(UnsafeStream, "BOOTSTRAP_INVALID"):
            self.buffer.seed_closed_candles(
                "BTCUSDT", klines()[:-1], event_open_ms=EVENT
            )
        self.buffer.seed_closed_candles("BTCUSDT", klines(), event_open_ms=EVENT)
        manipulated = klines()
        manipulated[-1][4] = "100.5"
        with self.assertRaisesRegex(UnsafeStream, "REST_WSS_CONFLICT"):
            self.buffer.seed_closed_candles(
                "BTCUSDT", manipulated, event_open_ms=EVENT
            )

    def test_unknown_market_and_oversized_universe_rejected(self):
        many = tuple(f"COIN{i:02d}USDT" for i in range(50))
        max_buffer = BoundedObservationBuffer(many)
        self.assertEqual(max_buffer.describe()["symbol_count"], 51)
        with self.assertRaises(UnsafeStream):
            BoundedObservationBuffer(many + ("EXTRAUSDT",))
        with self.assertRaises(UnsafeStream):
            self.buffer.seed_closed_candles("SOLUSDT", klines(),
                                            event_open_ms=EVENT)


    def test_load_probe_reports_bounded_latest_state_with_no_authority(self):
        from nbot.v5.ws_capacity_probe import run_probe

        async def sample(route, url, store, *, seconds):
            self.assertEqual(seconds, 10)
            self.assertTrue(url.startswith("wss://fstream.binance.com/"))
            store.connect(route)
            if route == "public":
                for i in range(100):
                    store.consume("public", ticker(updated=i + 1), received_ms=RECEIVED)
            else:
                store.consume("market", trade(agg=1), received_ms=RECEIVED)
            return {"route": route, "connected": True, "frames": 100,
                    "rejected": {}, "frame_cap_hit": False,
                    "duration_seconds": 10.0}

        with patch("nbot.v5.ws_capacity_probe._sample", side_effect=sample):
            result = asyncio.run(run_probe(symbols=("BTCUSDT", "ETHUSDT"), seconds=10))
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["buffer"]["latest_quotes_retained"], 1)
        self.assertEqual(result["buffer"]["event_counts"]["quote"], 100)
        self.assertFalse(result["research_ready"])
        self.assertEqual(result["order_authority"], "NONE")

    def test_load_probe_fails_closed_on_frame_limit(self):
        from nbot.v5.ws_capacity_probe import run_probe

        async def sample(route, url, store, *, seconds):
            store.connect(route)
            store.totals["quote"] += 1
            store.totals["trade"] += 1
            return {"route": route, "connected": True, "frames": 50000,
                    "rejected": {}, "frame_cap_hit": route == "public",
                    "duration_seconds": 2.0}

        with patch("nbot.v5.ws_capacity_probe._sample", side_effect=sample):
            result = asyncio.run(run_probe(symbols=("BTCUSDT",), seconds=10))
        self.assertEqual(result["result"], "HOLD")
        self.assertIn("PUBLIC_FRAME_CAP", result["reasons"])
        with self.assertRaises(ValueError):
            asyncio.run(run_probe(symbols=("BTCUSDT",), seconds=25))

    def test_500ms_depth_reduces_quote_work_without_claiming_tick_execution(self):
        store = BoundedObservationBuffer(("BTCUSDT", "ETHUSDT"),
                                         quote_mode="depth5@500ms")
        store.connect("public")
        frame = {
            "stream": "btcusdt@depth5@500ms",
            "data": {"e": "depthUpdate", "E": RECEIVED - 8,
                     "s": "BTCUSDT", "U": 90, "u": 91,
                     "b": [["100", "3"]], "a": [["101", "4"]],
                     "st": 1}
        }
        kind = store.consume("public", json.dumps(frame), received_ms=RECEIVED)
        self.assertEqual(kind, "QUOTE_LATEST_REPLACED")
        self.assertEqual(store.describe()["latest_quotes_retained"], 1)
        self.assertEqual(store.describe()["quote_mode"], "depth5@500ms")
        self.assertEqual(store.coins["BTCUSDT"].last_quote["quote_source"],
                         "PARTIAL_DEPTH_500MS")
        with self.assertRaisesRegex(UnsafeStream, "WRONG_QUOTE_SOURCE"):
            store.consume("public", ticker(), received_ms=RECEIVED)

    def test_500ms_depth_stale_update_id_does_not_refresh(self):
        store = BoundedObservationBuffer(("BTCUSDT",), quote_mode="depth5@500ms")
        store.connect("public")
        def frame(update, event):
            return json.dumps({
                "stream": "btcusdt@depth5@500ms",
                "data": {"e": "depthUpdate", "E": event, "s": "BTCUSDT",
                         "U": update - 1, "u": update,
                         "b": [["100", "2"]], "a": [["101", "3"]]}
            })
        store.consume("public", frame(100, RECEIVED - 15), received_ms=RECEIVED)
        self.assertEqual(store.consume("public", frame(99, RECEIVED - 5),
                                       received_ms=RECEIVED + 1),
                         "OUT_OF_ORDER_QUOTE")
        self.assertEqual(store.health.last_quote_ms["BTCUSDT"], RECEIVED)



if __name__ == "__main__":
    unittest.main()
