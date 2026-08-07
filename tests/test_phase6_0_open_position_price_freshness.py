import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execution.exceptions import OperationalExchangeError
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
    def __init__(self, *, last_price=95.0, error=None):
        self.last_price = float(last_price)
        self.error = error
        self.last_price_calls = []

    def get_last_price(self, symbol):
        self.last_price_calls.append(symbol)
        if self.error is not None:
            raise self.error
        return self.last_price


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

    def test_fresh_open_position_tick_does_not_call_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self._account(Path(tmp))
            self._open_short(account)
            market = Market(last_price=95.0)
            exchange = PaperExchange(
                market_client=market,
                account=account,
                system_log=Log(),
            )
            exchange.on_market_tick(
                symbol="DODOXUSDT",
                price=96.0,
                timestamp=99_000,
            )
            with patch("execution.paper_exchange.time.time", return_value=100.0):
                exchange._refresh_open_position_price_if_stale()
            self.assertEqual(market.last_price_calls, [])
            self.assertEqual(
                exchange._latest_price_by_symbol["DODOXUSDT"],
                96.0,
            )

    def test_stale_open_position_tick_refreshes_through_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self._account(Path(tmp))
            self._open_short(account)
            market = Market(last_price=95.0)
            log = Log()
            exchange = PaperExchange(
                market_client=market,
                account=account,
                system_log=log,
            )
            exchange.on_market_tick(
                symbol="DODOXUSDT",
                price=99.0,
                timestamp=90_000,
            )
            with patch("execution.paper_exchange.time.time", return_value=100.0), \
                 patch(
                     "execution.paper_exchange.time.monotonic",
                     return_value=50.0,
                 ):
                exchange._refresh_open_position_price_if_stale()
            self.assertEqual(market.last_price_calls, ["DODOXUSDT"])
            self.assertEqual(
                exchange._latest_price_by_symbol["DODOXUSDT"],
                95.0,
            )
            self.assertTrue(
                any("PAPER_POSITION_PRICE_STALE" in x for x in log.warnings)
            )
            self.assertTrue(
                any("PAPER_POSITION_REST_REFRESH" in x for x in log.infos)
            )

    def test_rest_refresh_can_fill_simulated_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self._account(Path(tmp))
            self._open_short(account, stop_loss=105.0)
            market = Market(last_price=106.0)
            log = Log()
            exchange = PaperExchange(
                market_client=market,
                account=account,
                system_log=log,
            )
            exchange.on_market_tick(
                symbol="DODOXUSDT",
                price=100.0,
                timestamp=90_000,
            )
            with patch("execution.paper_exchange.time.time", return_value=100.0), \
                 patch(
                     "execution.paper_exchange.time.monotonic",
                     return_value=50.0,
                 ):
                exchange._refresh_open_position_price_if_stale()
            self.assertIsNone(account.get_open_position())
            self.assertTrue(
                any("PAPER_STOP_FILLED" in x for x in log.infos)
            )

    def test_rest_failure_is_rate_limited_and_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = self._account(Path(tmp))
            self._open_short(account)
            market = Market(
                error=OperationalExchangeError("synthetic timeout")
            )
            log = Log()
            exchange = PaperExchange(
                market_client=market,
                account=account,
                system_log=log,
            )
            exchange.on_market_tick(
                symbol="DODOXUSDT",
                price=99.0,
                timestamp=90_000,
            )
            with patch("execution.paper_exchange.time.time", return_value=100.0), \
                 patch(
                     "execution.paper_exchange.time.monotonic",
                     side_effect=[50.0, 51.0],
                 ):
                self.assertIsNone(
                    exchange._refresh_open_position_price_if_stale()
                )
                self.assertIsNone(
                    exchange._refresh_open_position_price_if_stale()
                )
            self.assertEqual(market.last_price_calls, ["DODOXUSDT"])
            self.assertIsNotNone(account.get_open_position())
            self.assertTrue(
                any(
                    "PAPER_POSITION_REST_REFRESH_FAILED" in x
                    for x in log.warnings
                )
            )


if __name__ == "__main__":
    unittest.main()
