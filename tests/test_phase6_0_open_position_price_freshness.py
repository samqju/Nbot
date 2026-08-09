import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange


class Log:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)


class Market:
    def __init__(self, ticks):
        self.ticks = list(ticks)
        self.requested_symbols = []
        self.last_price_calls = []

    def position_price_stream(self, symbol):
        self.requested_symbols.append(symbol)
        return iter(self.ticks)

    def get_last_price(self, symbol):
        self.last_price_calls.append(symbol)
        raise AssertionError("paper layer must not run its own stale REST watchdog")


class Phase60OpenPositionPriceFreshnessTests(unittest.TestCase):
    def _account(self, root):
        return PaperAccount(
            starting_balance_usd=10000,
            state_path=str(root / "paper_state.json"),
            trades_path=str(root / "paper_trades.jsonl"),
            source="PAPER_LIVE",
        )

    def _open_short(self, account, *, stop_loss=110.0):
        account.load_or_create()
        account.open_position(
            symbol="DODOXUSDT",
            side="SHORT",
            qty=1.0,
            entry_price=100.0,
            stop_loss=stop_loss,
            opened_at_ms=1,
            initial_risk_usd=10.0,
            entry_fee_usd=0.0,
            trade_id="phase6-price-watchdog",
        )

    @staticmethod
    def _tick(price, timestamp=100_000):
        return SimpleNamespace(
            symbol="DODOXUSDT",
            price=float(price),
            timestamp=int(timestamp),
        )

    def test_position_stream_delegates_only_owned_symbol_without_stale_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self._account(Path(tmp))
            self._open_short(account)
            market = Market([self._tick(99.0), self._tick(99.0, 102_000)])
            log = Log()
            exchange = PaperExchange(
                market_client=market,
                account=account,
                system_log=log,
            )

            ticks = list(exchange.position_price_stream("DODOXUSDT"))

            self.assertEqual(market.requested_symbols, ["DODOXUSDT"])
            self.assertEqual([tick.symbol for tick in ticks], ["DODOXUSDT"] * 2)
            self.assertEqual(market.last_price_calls, [])
            self.assertFalse(
                any("PAPER_POSITION_PRICE_STALE" in x for x in log.warnings)
            )
            self.assertFalse(
                any("PAPER_POSITION_REST_REFRESH" in x for x in log.infos)
            )

    def test_recovery_tick_uses_same_path_and_can_fill_simulated_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self._account(Path(tmp))
            self._open_short(account, stop_loss=105.0)
            market = Market([self._tick(106.0)])
            log = Log()
            exchange = PaperExchange(
                market_client=market,
                account=account,
                system_log=log,
            )

            ticks = list(exchange.position_price_stream("DODOXUSDT"))

            self.assertEqual(len(ticks), 1)
            self.assertIsNone(account.get_open_position())
            self.assertTrue(any("PAPER_STOP_FILLED" in x for x in log.infos))

    def test_legacy_stale_refresh_hook_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            exchange = PaperExchange(
                market_client=Market([]),
                account=self._account(Path(tmp)),
                system_log=Log(),
            )
            self.assertFalse(
                hasattr(exchange, "_refresh_open_position_price_if_stale")
            )


if __name__ == "__main__":
    unittest.main()
