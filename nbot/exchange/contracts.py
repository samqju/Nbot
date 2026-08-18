"""Execution-facing exchange contracts for NBOT V3.

This module contains only capital-boundary facts and the abstract exchange port.
It intentionally contains no Binance transport code and no Observation/research
imports.  Concrete PAPER and Testnet adapters arrive later in V3.1.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nbot.execution.models import OpenPosition

Side = Literal["LONG", "SHORT"]

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,40}$")


def _require_text(name: str, value: object, *, max_length: int = 128) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}_INVALID")
    if not value or value != value.strip() or len(value) > max_length:
        raise ValueError(f"{name}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name}_INVALID")
    return value


def _require_symbol(value: object) -> str:
    symbol = _require_text("SYMBOL", value, max_length=40)
    if _SYMBOL_RE.fullmatch(symbol) is None:
        raise ValueError("SYMBOL_INVALID")
    return symbol


def _require_side(value: object) -> Side:
    if value not in {"LONG", "SHORT"}:
        raise ValueError("SIDE_INVALID")
    return value  # type: ignore[return-value]


def _require_number(
    name: str,
    value: object,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name}_INVALID")
    if positive and number <= 0:
        raise ValueError(f"{name}_INVALID")
    if nonnegative and number < 0:
        raise ValueError(f"{name}_INVALID")
    return number


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name}_INVALID")
    return value


def _require_timestamp_ms(name: str, value: object) -> int:
    return _require_positive_int(name, value)


@dataclass(frozen=True, slots=True)
class Quote:
    """Executable bid/ask truth captured by the Execution worker."""

    symbol: str
    bid: float
    ask: float
    timestamp_ms: int

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        bid = _require_number("QUOTE_BID", self.bid, positive=True)
        ask = _require_number("QUOTE_ASK", self.ask, positive=True)
        _require_timestamp_ms("QUOTE_TIMESTAMP_MS", self.timestamp_ms)
        if ask < bid:
            raise ValueError("QUOTE_CROSSED_BOOK")

    @property
    def mid(self) -> float:
        return (float(self.bid) + float(self.ask)) / 2.0

    @property
    def spread_pct(self) -> float:
        return (float(self.ask) - float(self.bid)) / self.mid * 100.0


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Minimum account truth needed by the local risk/entry gate."""

    available_balance_usd: float

    def __post_init__(self) -> None:
        _require_number(
            "ACCOUNT_AVAILABLE_BALANCE_USD",
            self.available_balance_usd,
            nonnegative=True,
        )


@dataclass(frozen=True, slots=True)
class ExchangePosition:
    """Canonical one-way exchange position truth.

    Concrete adapters must refuse ambiguous/multiple/hedged position state rather
    than squeezing it into this single-position model.
    """

    symbol: str
    side: Side
    quantity: float
    entry_price: float

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_side(self.side)
        _require_number("POSITION_QUANTITY", self.quantity, positive=True)
        _require_number("POSITION_ENTRY_PRICE", self.entry_price, positive=True)


@dataclass(frozen=True, slots=True)
class Fill:
    """Proven aggregate entry fill for one deterministic client order identity."""

    price: float
    quantity: float
    order_id: str
    client_order_id: str
    timestamp_ms: int

    def __post_init__(self) -> None:
        _require_number("FILL_PRICE", self.price, positive=True)
        _require_number("FILL_QUANTITY", self.quantity, positive=True)
        _require_text("FILL_ORDER_ID", self.order_id)
        _require_text("FILL_CLIENT_ORDER_ID", self.client_order_id)
        _require_timestamp_ms("FILL_TIMESTAMP_MS", self.timestamp_ms)


@dataclass(frozen=True, slots=True)
class CloseFill:
    """Authoritative close evidence returned by an execution adapter.

    ``realized_pnl_usd`` may be ``None`` while accounting is still unresolved.
    Later reconciliation must not invent zero PnL merely to finalize local state.
    ``theoretical_pnl_usd`` and ``pnl_variance_usd`` are audit-only diagnostics;
    they never replace proven exchange accounting.
    """

    price: float
    timestamp_ms: int
    reason: str
    realized_pnl_usd: float | None = None
    order_ids: tuple[str, ...] = ()
    source: str = "ORDER_RESULT"
    theoretical_pnl_usd: float | None = None
    pnl_variance_usd: float | None = None

    def __post_init__(self) -> None:
        _require_number("CLOSE_PRICE", self.price, positive=True)
        _require_timestamp_ms("CLOSE_TIMESTAMP_MS", self.timestamp_ms)
        _require_text("CLOSE_REASON", self.reason)
        _require_text("CLOSE_SOURCE", self.source)
        if not isinstance(self.order_ids, tuple):
            raise ValueError("CLOSE_ORDER_IDS_INVALID")
        for order_id in self.order_ids:
            _require_text("CLOSE_ORDER_ID", order_id)
        for name, value in (
            ("CLOSE_REALIZED_PNL_USD", self.realized_pnl_usd),
            ("CLOSE_THEORETICAL_PNL_USD", self.theoretical_pnl_usd),
            ("CLOSE_PNL_VARIANCE_USD", self.pnl_variance_usd),
        ):
            if value is not None:
                _require_number(name, value)


@dataclass(frozen=True, slots=True)
class ProtectiveStopRef:
    """Proven active protective stop identity.

    At least one exchange/local identity is mandatory.  A bare price is not
    sufficient proof of protection for restart/reconciliation purposes.
    """

    symbol: str
    side: Side
    quantity: float
    trigger_price: float
    stop_id: str | None = None
    client_stop_id: str | None = None

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_side(self.side)
        _require_number("STOP_QUANTITY", self.quantity, positive=True)
        _require_number("STOP_TRIGGER_PRICE", self.trigger_price, positive=True)
        if self.stop_id is not None:
            _require_text("STOP_ID", self.stop_id)
        if self.client_stop_id is not None:
            _require_text("STOP_CLIENT_ID", self.client_stop_id)
        if self.stop_id is None and self.client_stop_id is None:
            raise ValueError("STOP_IDENTITY_MISSING")


@dataclass(frozen=True, slots=True)
class EntryPlan:
    """Execution-local risk plan built from current Execution market truth."""

    symbol: str
    side: Side
    quantity: float
    expected_entry_price: float
    initial_stop_price: float
    initial_risk_usd: float
    notional_usd: float
    leverage: int

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        side = _require_side(self.side)
        _require_number("ENTRY_PLAN_QUANTITY", self.quantity, positive=True)
        entry = _require_number(
            "ENTRY_PLAN_EXPECTED_ENTRY_PRICE",
            self.expected_entry_price,
            positive=True,
        )
        stop = _require_number(
            "ENTRY_PLAN_INITIAL_STOP_PRICE",
            self.initial_stop_price,
            positive=True,
        )
        _require_number("ENTRY_PLAN_INITIAL_RISK_USD", self.initial_risk_usd, positive=True)
        _require_number("ENTRY_PLAN_NOTIONAL_USD", self.notional_usd, positive=True)
        _require_positive_int("ENTRY_PLAN_LEVERAGE", self.leverage)
        if side == "LONG" and stop >= entry:
            raise ValueError("ENTRY_PLAN_LONG_STOP_NOT_BELOW_ENTRY")
        if side == "SHORT" and stop <= entry:
            raise ValueError("ENTRY_PLAN_SHORT_STOP_NOT_ABOVE_ENTRY")


@runtime_checkable
class ExchangePort(Protocol):
    """Minimal capital-facing exchange boundary for V3.1.

    Semantics are deliberately fail-closed:

    * ``position_snapshot`` represents at most one one-way capital position;
      adapters must raise on multiple/hedged/ambiguous exchange truth.
    * ``protective_stop_snapshot`` returns one canonical active protective stop;
      adapters must raise when active protection is ambiguous or contradictory.
    * ambiguous entry writes are recovered only through the same
      ``client_order_id`` via ``recover_inflight_entry``; callers must not blindly
      submit another market order.
    * stop replacement implementations must prove the new stop before pruning
      old known protection.
    * close requests are not proof of flatness; callers verify position truth.
    """

    def connect(self) -> None: ...

    def is_healthy(self) -> bool: ...

    def quote(self, symbol: str) -> Quote: ...

    def account_snapshot(self) -> AccountSnapshot: ...

    def position_snapshot(self) -> ExchangePosition | None: ...

    def protective_stop_snapshot(self, symbol: str) -> ProtectiveStopRef | None: ...

    def validate_protective_stop(
        self,
        symbol: str,
        side: Side,
        stop_price: float,
    ) -> bool: ...

    def set_leverage(self, symbol: str, leverage: int) -> None: ...

    def open_market(self, plan: EntryPlan, *, client_order_id: str) -> Fill: ...

    def recover_inflight_entry(
        self,
        plan: EntryPlan,
        *,
        client_order_id: str,
    ) -> Fill | None: ...

    def ensure_protective_stop(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        stop_price: float,
    ) -> ProtectiveStopRef: ...

    def replace_protective_stop(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        stop_price: float,
    ) -> ProtectiveStopRef: ...

    def close_position(self, symbol: str, side: Side, *, reason: str) -> CloseFill: ...

    def recover_closed_position(self, local_position: OpenPosition) -> CloseFill: ...
