"""Formal runtime contract for Execution exchange adapters.

The split Execution Worker validates the capabilities it may need for entry,
position management, reconciliation, and emergency handling. Observation owns
its separate all-market stream; Execution requires a dedicated position-symbol
stream while capital is open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


CONNECTION_METHODS = (
    "connect",
    "disconnect",
)

POSITION_FEED_METHODS = (
    "position_price_stream",
)

MARKET_DATA_METHODS = (
    "get_historical_candles",
    "get_current_spread_pct",
    "get_last_price",
    "quantize_price",
)

STREAM_HEALTH_METHODS = (
    "is_user_stream_healthy",
    "wait_for_user_stream_ready",
)

ACCOUNT_STATE_METHODS = (
    "get_available_balance",
    "get_position",
    "get_realized_pnl",
    "get_trade_realized_pnl",
    "get_active_sl_order_id",
    "recover_active_stop_loss",
)

ORDER_PREPARATION_METHODS = (
    "set_leverage",
    "enforce_leverage_for_universe",
)

ENTRY_METHODS = (
    "place_entry",
    "query_order_by_client_id",
    "resolve_ambiguous_entry",
)

PROTECTION_METHODS = (
    "place_initial_sl",
    "update_sl",
)

CANCELLATION_METHODS = (
    "cancel_pending_entries",
    "emergency_exit",
)

REQUIRED_EXCHANGE_METHODS = (
    CONNECTION_METHODS
    + POSITION_FEED_METHODS
    + MARKET_DATA_METHODS
    + STREAM_HEALTH_METHODS
    + ACCOUNT_STATE_METHODS
    + ORDER_PREPARATION_METHODS
    + ENTRY_METHODS
    + PROTECTION_METHODS
    + CANCELLATION_METHODS
)


@dataclass(frozen=True)
class ExchangeContractReport:
    adapter_class: str
    required_count: int
    missing_methods: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.missing_methods


@runtime_checkable
class ExchangeAdapter(Protocol):
    """Static typing surface for engine-compatible exchange adapters."""

    def connect(self) -> Any: ...
    def disconnect(self) -> Any: ...
    def position_price_stream(self, symbol: str) -> Any: ...

    def get_historical_candles(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_current_spread_pct(self, *args: Any, **kwargs: Any) -> Any: ...
    def get_last_price(self, symbol: str) -> float: ...
    def quantize_price(self, symbol: str, price: float) -> float: ...

    def is_user_stream_healthy(self) -> bool: ...
    def wait_for_user_stream_ready(self, timeout: Any = None) -> bool: ...

    def get_available_balance(self) -> float: ...
    def get_position(self) -> Any: ...
    def get_realized_pnl(self, utc_day: Any = None) -> float: ...
    def get_trade_realized_pnl(self, *args: Any, **kwargs: Any) -> float: ...
    def get_active_sl_order_id(self) -> Any: ...
    def recover_active_stop_loss(self, symbol: str) -> Any: ...

    def set_leverage(self, *args: Any, **kwargs: Any) -> Any: ...
    def enforce_leverage_for_universe(self, symbols: Any) -> Any: ...

    def place_entry(self, *args: Any, **kwargs: Any) -> Any: ...
    def query_order_by_client_id(self, *args: Any, **kwargs: Any) -> Any: ...
    def resolve_ambiguous_entry(self, *args: Any, **kwargs: Any) -> Any: ...

    def place_initial_sl(self, *args: Any, **kwargs: Any) -> Any: ...
    def update_sl(self, *args: Any, **kwargs: Any) -> Any: ...

    def cancel_pending_entries(self, *args: Any, **kwargs: Any) -> Any: ...
    def emergency_exit(self, *args: Any, **kwargs: Any) -> Any: ...


def inspect_exchange_adapter(exchange: Any) -> ExchangeContractReport:
    """Return a deterministic contract report without mutating the adapter."""
    missing = tuple(
        method
        for method in REQUIRED_EXCHANGE_METHODS
        if not callable(getattr(exchange, method, None))
    )
    return ExchangeContractReport(
        adapter_class=type(exchange).__name__,
        required_count=len(REQUIRED_EXCHANGE_METHODS),
        missing_methods=missing,
    )


def validate_exchange_adapter(exchange: Any) -> ExchangeContractReport:
    """Fail fast when an adapter lacks the split Execution contract."""
    report = inspect_exchange_adapter(exchange)
    if not report.valid:
        raise RuntimeError(
            "EXCHANGE_ADAPTER_CONTRACT_INVALID | "
            f"adapter={report.adapter_class} | "
            f"missing={','.join(report.missing_methods)}"
        )
    return report
