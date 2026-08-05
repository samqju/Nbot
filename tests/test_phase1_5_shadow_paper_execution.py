import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import time

from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange


class SilentLog:
    def info(self, message):
        pass


class FakeMarketClient:
    def __init__(self, ticks=None):
        self.ticks = list(ticks or [])

    def price_stream(self):
        yield from self.ticks

    def quantize_price(self, symbol, price):
        return float(price)

    def get_last_price(self, symbol):
        return 100.0


class Phase15ShadowPaperExecutionTests(unittest.TestCase):
    def make_exchange(self, ticks=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        account = PaperAccount(
            state_path=str(root / "state.json"),
            trades_path=str(root / "trades.jsonl"),
            starting_balance_usd=10000.0,
            source="PAPER_LIVE",
        )
        account.load_or_create()
        exchange = PaperExchange(
            market_client=FakeMarketClient(ticks=ticks),
            account=account,
            system_log=SilentLog(),
        )
        return exchange

    def open_long(self, exchange):
        exchange.place_entry(
            symbol="BTCUSDT",
            side="LONG",
            quantity=1.0,
            price=100.0,
            client_order_id="paper-test-long",
        )
        exchange.place_initial_sl(
            symbol="BTCUSDT",
            side="LONG",
            qty=1.0,
            stop_price=95.0,
        )

    def test_market_tick_updates_position_extremes(self):
        exchange = self.make_exchange()
        self.open_long(exchange)
        exchange.on_market_tick(
            symbol="BTCUSDT",
            price=110.0,
            timestamp=int(time.time() * 1000) + 1000,
        )
        position = exchange.account.get_open_position()
        self.assertIsNotNone(position)
        self.assertEqual(position.highest_price, 110.0)

    def test_long_stop_closes_local_position(self):
        exchange = self.make_exchange()
        self.open_long(exchange)
        trade = exchange.on_market_tick(
            symbol="BTCUSDT",
            price=94.0,
            timestamp=int(time.time() * 1000) + 2000,
        )
        self.assertIsNotNone(trade)
        self.assertEqual(trade.exit_reason, "STOP_LOSS")
        self.assertIsNone(exchange.get_position())
        realized = exchange.get_trade_realized_pnl(symbol="BTCUSDT")
        self.assertEqual(realized["exit_price"], trade.exit_price)

    def test_price_stream_applies_ticks_before_yielding(self):
        tick = SimpleNamespace(
            symbol="BTCUSDT",
            price=94.0,
            timestamp=int(time.time() * 1000) + 3000,
        )
        exchange = self.make_exchange(ticks=[tick])
        self.open_long(exchange)
        yielded = list(exchange.price_stream())
        self.assertEqual(yielded, [tick])
        self.assertIsNone(exchange.get_position())

    def test_engine_no_longer_contains_shadow_intent_discard(self):
        core = (Path(__file__).resolve().parents[1] / "engine" / "core.py").read_text()
        self.assertNotIn("SHADOW_INTENT_BLOCKED", core)
        self.assertIn("SHADOW_PAPER_EXECUTION_ACTIVE", core)


if __name__ == "__main__":
    unittest.main()
