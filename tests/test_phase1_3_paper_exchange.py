import tempfile
import unittest
from pathlib import Path

from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange


class FakeMarketClient:
    def __init__(self):
        self.price = 100.0
        self.connected = False

    def connect(self): self.connected = True
    def disconnect(self): self.connected = False
    def preflight(self, *, symbol, candle_limit):
        return {"environment": "LIVE", "auth": "NONE", "symbol": symbol, "last_price": self.price, "spread_pct": 0.01, "completed_candles": candle_limit, "tick_size": 0.01}
    def price_stream(self): return iter(())
    def get_historical_candles(self, *, symbol, interval, limit): return []
    def get_current_spread_pct(self, *, symbol): return 0.01
    def get_last_price(self, symbol): return self.price
    def quantize_price(self, symbol, price): return round(float(price), 2)


class NullLog:
    def __getattr__(self, name): return lambda *args, **kwargs: None


class Phase13PaperExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.account = PaperAccount(
            starting_balance_usd=10000.0,
            state_path=str(root / "state.json"),
            trades_path=str(root / "trades.jsonl"),
            source="PAPER_LIVE",
        )
        self.market = FakeMarketClient()
        self.exchange = PaperExchange(
            market_client=self.market,
            account=self.account,
            system_log=NullLog(),
        )
        self.exchange.connect()

    def tearDown(self): self.tmp.cleanup()

    def test_market_operations_are_delegated(self):
        self.assertTrue(self.market.connected)
        self.assertEqual(self.exchange.get_last_price("BTCUSDT"), 100.0)
        self.assertEqual(self.exchange.get_current_spread_pct(symbol="BTCUSDT"), 0.01)
        self.assertEqual(self.exchange.quantize_price("BTCUSDT", 99.876), 99.88)

    def test_entry_is_pending_until_stop_is_installed(self):
        ack = self.exchange.place_entry(
            symbol="BTCUSDT", side="LONG", quantity=2.0,
            price=100.0, client_order_id="client-1",
        )
        self.assertIsNone(self.exchange.get_position())
        self.assertGreater(ack.avg_price, 100.0)
        sl = self.exchange.place_initial_sl(
            symbol="BTCUSDT", side="LONG", qty=2.0, stop_price=95.0,
        )
        self.assertIsInstance(sl["algo_id"], int)
        self.assertGreater(sl["algo_id"], 0)
        position = self.exchange.get_position()
        self.assertEqual(position.symbol, "BTCUSDT")
        self.assertEqual(position.stop_loss, 95.0)

    def test_ambiguous_entry_resolution_is_idempotent(self):
        ack = self.exchange.place_entry(
            symbol="ETHUSDT", side="SHORT", quantity=1.0,
            price=100.0, client_order_id="client-2",
        )
        result = self.exchange.resolve_ambiguous_entry(
            symbol="ETHUSDT", client_order_id="client-2",
            requested_qty=1.0, fallback_price=100.0,
        )
        self.assertEqual(result["outcome"], "FILLED")
        self.assertEqual(result["ack"], ack)

    def test_emergency_exit_closes_locally_with_costs(self):
        self.exchange.place_entry(
            symbol="BTCUSDT", side="LONG", quantity=2.0,
            price=100.0, client_order_id="client-3",
        )
        self.exchange.place_initial_sl(
            symbol="BTCUSDT", side="LONG", qty=2.0, stop_price=95.0,
        )
        self.market.price = 110.0
        trade = self.exchange.emergency_exit()
        self.assertIsNone(self.exchange.get_position())
        self.assertGreater(trade.net_pnl_usd, 0.0)
        details = self.exchange.get_trade_realized_pnl(symbol="BTCUSDT")
        self.assertEqual(details["exit_price"], trade.exit_price)
        self.assertEqual(details["pnl"], trade.net_pnl_usd)

    def test_no_private_user_stream_is_required(self):
        self.assertTrue(self.exchange.is_user_stream_healthy())
        self.assertTrue(self.exchange.wait_for_user_stream_ready())


if __name__ == "__main__":
    unittest.main()
