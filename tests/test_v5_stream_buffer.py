"""Synthetic resource caps, candle continuity and quote coalescing tests."""
import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
