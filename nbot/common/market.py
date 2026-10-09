"""Shared immutable public-market event models.

This module is intentionally under nbot.common so Observation may consume
validated public-market events without importing the Execution/exchange layer.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,40}$")


@dataclass(frozen=True, slots=True)
class AggTrade:
    """One chronological Binance USD-M aggregate-trade event."""

    symbol: str
    price: float
    quantity: float
    event_time_ms: int
    trade_time_ms: int
    aggregate_trade_id: int
    first_trade_id: int
    last_trade_id: int
    buyer_is_maker: bool

    def __post_init__(self) -> None:
        if _SYMBOL_RE.fullmatch(self.symbol) is None:
            raise ValueError("AGGTRADE_SYMBOL_INVALID")
        for name, value in (("price", self.price), ("quantity", self.quantity)):
            if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"AGGTRADE_{name.upper()}_INVALID")
        for name, value in (
            ("event_time_ms", self.event_time_ms),
            ("trade_time_ms", self.trade_time_ms),
            ("aggregate_trade_id", self.aggregate_trade_id),
            ("first_trade_id", self.first_trade_id),
            ("last_trade_id", self.last_trade_id),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"AGGTRADE_{name.upper()}_INVALID")
        if self.last_trade_id < self.first_trade_id:
            raise ValueError("AGGTRADE_TRADE_ID_RANGE_INVALID")
