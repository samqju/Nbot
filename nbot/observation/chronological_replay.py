"""Research-only chronological market-path replay primitives (no order authority).

This is a foundation, not a replacement for the deployed exit-policy engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable


class PathQuality(str, Enum):
    AGGTRADE_RESOLVED = "AGGTRADE_RESOLVED"
    GAP_UNRESOLVED = "GAP_UNRESOLVED"


@dataclass(frozen=True)
class TradeEvent:
    symbol: str
    trade_id: int
    trade_time_ms: int
    price: float

    def __post_init__(self) -> None:
        if not self.symbol or self.trade_id < 0 or self.trade_time_ms < 0:
            raise ValueError("INVALID_TRADE_EVENT")
        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("INVALID_TRADE_PRICE")


@dataclass(frozen=True)
class ReplayResult:
    symbol: str
    side: str
    exit_time_ms: int | None
    exit_price: float | None
    exit_reason: str
    gross_r: float | None
    mfe_r: float
    mae_r: float
    stop_r: int
    quality: PathQuality
    events_seen: int


def replay_integer_r_tick_policy(
    events: Iterable[TradeEvent],
    *,
    symbol: str,
    side: str,
    entry_price: float,
    one_r_price: float,
    entry_time_ms: int,
    horizon_ms: int = 4 * 60 * 60 * 1000,
    expected_first_trade_id: int | None = None,
) -> ReplayResult:
    """Replay a *tick-tightening* hypothetical policy; NOT the legacy 5m-close policy.

    Stops start at -1R, then trail by whole R: reaching +1R protects 0R,
    reaching +2R protects +1R, etc. Events are processed in their input order.
    Any trade-ID discontinuity is marked unresolved; no precise result is issued.
    Historical aggregate-trade IDs may skip; only use the continuity check when
    the upstream adapter guarantees a contiguous sequence.
    """
    if side not in ("LONG", "SHORT"):
        raise ValueError("INVALID_SIDE")
    if not (isfinite(entry_price) and entry_price > 0 and isfinite(one_r_price) and one_r_price > 0):
        raise ValueError("INVALID_RISK")
    if horizon_ms <= 0:
        raise ValueError("INVALID_HORIZON")
    direction = 1 if side == "LONG" else -1
    stop_r = -1
    peak = 0.0
    trough = 0.0
    seen = 0
    previous_id = None
    previous_time = None
    quality = PathQuality.AGGTRADE_RESOLVED
    exit_time = None
    exit_price = None
    reason = "HORIZON_UNRESOLVED"
    for event in events:
        if event.symbol != symbol:
            raise ValueError("SYMBOL_MISMATCH")
        if previous_time is not None and event.trade_time_ms < previous_time:
            quality = PathQuality.GAP_UNRESOLVED
            break
        if previous_id is not None and event.trade_id <= previous_id:
            quality = PathQuality.GAP_UNRESOLVED
            break
        if previous_id is None and expected_first_trade_id is not None and event.trade_id != expected_first_trade_id:
            quality = PathQuality.GAP_UNRESOLVED
            break
        previous_time, previous_id = event.trade_time_ms, event.trade_id
        if event.trade_time_ms < entry_time_ms:
            continue
        if event.trade_time_ms > entry_time_ms + horizon_ms:
            break
        seen += 1
        r = direction * (event.price - entry_price) / one_r_price
        peak, trough = max(peak, r), min(trough, r)
        if r <= stop_r:
            exit_time, exit_price, reason = event.trade_time_ms, event.price, "STOP"
            break
        # Tick tightening is explicitly different from completed-5m-bar control.
        stop_r = max(stop_r, int(peak // 1) - 1) if peak >= 1 else stop_r
    if quality is PathQuality.GAP_UNRESOLVED:
        exit_time, exit_price, reason = None, None, "GAP_UNRESOLVED"
    gross_r = None if exit_price is None else direction * (exit_price - entry_price) / one_r_price
    return ReplayResult(symbol, side, exit_time, exit_price, reason, gross_r,
                        peak, trough, stop_r, quality, seen)
