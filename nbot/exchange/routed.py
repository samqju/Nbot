"""Route market reads to WSS while preserving the capital adapter boundary."""
from __future__ import annotations

from nbot.exchange.contracts import ExchangePort


class MarketRoutedExchange:
    """ExchangePort facade: WSS market truth, existing adapter for capital writes."""

    def __init__(self, *, capital: ExchangePort, market) -> None:
        self.capital = capital
        self.market = market

    def connect(self) -> None:
        self.capital.connect()
        try:
            self.market.connect()
        except Exception:
            try:
                self.capital.disconnect()
            finally:
                raise

    def disconnect(self) -> None:
        try:
            self.market.disconnect()
        finally:
            self.capital.disconnect()

    def is_healthy(self) -> bool:
        return bool(self.capital.is_healthy() and self.market.is_healthy())

    def quote(self, symbol: str):
        return self.market.quote(symbol)

    def wait_quote(self, symbol: str, *, after_sequence: int = 0, timeout_seconds: float | None = None):
        return self.market.wait_quote(
            symbol, after_sequence=after_sequence, timeout_seconds=timeout_seconds
        )

    def recovery_quote(self, symbol: str):
        return self.market.recovery_quote(symbol)

    def account_snapshot(self):
        return self.capital.account_snapshot()

    def position_snapshot(self):
        return self.capital.position_snapshot()

    def protective_stop_snapshot(self, symbol):
        return self.capital.protective_stop_snapshot(symbol)

    def validate_protective_stop(self, symbol, side, stop_price):
        return self.capital.validate_protective_stop(symbol, side, stop_price)

    def set_leverage(self, symbol, leverage):
        return self.capital.set_leverage(symbol, leverage)

    def open_market(self, plan, *, client_order_id):
        return self.capital.open_market(plan, client_order_id=client_order_id)

    def recover_inflight_entry(self, plan, *, client_order_id):
        return self.capital.recover_inflight_entry(plan, client_order_id=client_order_id)

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        return self.capital.ensure_protective_stop(symbol, side, quantity, stop_price)

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        return self.capital.replace_protective_stop(symbol, side, quantity, stop_price)

    def close_position(self, symbol, side, *, reason):
        return self.capital.close_position(symbol, side, reason=reason)

    def recover_closed_position(self, local_position):
        return self.capital.recover_closed_position(local_position)

    def recover_closed_inflight_entry(self, inflight):
        return self.capital.recover_closed_inflight_entry(inflight)

    def cleanup_orphan_protective_stops(self):
        return self.capital.cleanup_orphan_protective_stops()
