"""Pure V5 research-only fill accounting; no exchange access or order authority.

Fee policy: 0.05% taker per entry/exit, 1 bp modeled slippage per side.
Fills already include spread (LONG buy ask/sell bid, SHORT sell bid/buy ask);
do not subtract the spread a second time.
Actual funding settlement records are required, with evidence of complete coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

VERSION = "NBOT_V5_ACCOUNTING_V1"
ORDER_AUTHORITY = "NONE"
ENTRY_FEE_RATE = 0.0005
EXIT_FEE_RATE = 0.0005
ENTRY_SLIPPAGE_RATE = 0.0001
EXIT_SLIPPAGE_RATE = 0.0001


def _finite(value: float, *, positive: bool = False) -> float:
    number = float(value)
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError("V5_ACCOUNTING_NUMBER_INVALID")
    return number


@dataclass(frozen=True)
class FundingSettlement:
    """Confirmed symbol-specific event; rate >0 means LONG pays SHORT."""
    time_ms: int
    rate: float
    mark_price: float

    def __post_init__(self) -> None:
        if type(self.time_ms) is not int or self.time_ms < 0:
            raise ValueError("V5_FUNDING_TIME_INVALID")
        _finite(self.rate)
        _finite(self.mark_price, positive=True)


@dataclass(frozen=True)
class CostPolicy:
    version: str = VERSION
    entry_fee_rate: float = ENTRY_FEE_RATE
    exit_fee_rate: float = EXIT_FEE_RATE
    entry_slippage_rate: float = ENTRY_SLIPPAGE_RATE
    exit_slippage_rate: float = EXIT_SLIPPAGE_RATE

    def __post_init__(self) -> None:
        if self.version != VERSION:
            raise ValueError("V5_ACCOUNTING_VERSION_INVALID")
        for rate in (self.entry_fee_rate, self.exit_fee_rate,
                     self.entry_slippage_rate, self.exit_slippage_rate):
            if not 0 <= _finite(rate) < 0.1:
                raise ValueError("V5_ACCOUNTING_COST_RATE_INVALID")


@dataclass(frozen=True)
class TradeAccounting:
    policy_version: str
    side: str
    quantity: float
    one_r_quote: float
    gross_quote: float
    fees_quote: float
    slippage_quote: float
    funding_quote: float
    net_quote: float
    gross_r: float
    cost_r: float
    funding_r: float
    net_r: float
    funding_events_used: int


def score_trade(
    *,
    side: str,
    quantity: float,
    entry_fill_price: float,
    exit_fill_price: float,
    initial_stop_price: float,
    entry_time_ms: int,
    exit_time_ms: int,
    funding_events: Iterable[FundingSettlement],
    funding_coverage_confirmed: bool,
    policy: CostPolicy = CostPolicy(),
) -> TradeAccounting:
    """Score one closed virtual path with a frozen -1R initial price stop.

    This does NOT simulate an exit. The caller must provide a proven chronological
    entry/exit path and bid/ask-side fill prices, plus complete funding coverage.

    Settlement boundary policy: events strictly AFTER entry and BEFORE exit are
    counted. A settlement exactly on an entry or exit needs an explicit event-order
    decision upstream; this contract fails closed on such boundary events.
    """
    if side not in {"LONG", "SHORT"}:
        raise ValueError("V5_ACCOUNTING_SIDE_INVALID")
    if type(entry_time_ms) is not int or type(exit_time_ms) is not int or (
        entry_time_ms < 0 or exit_time_ms <= entry_time_ms
    ):
        raise ValueError("V5_ACCOUNTING_CHRONOLOGY_INVALID")
    if not funding_coverage_confirmed:
        raise ValueError("V5_FUNDING_COVERAGE_REQUIRED")
    qty = _finite(quantity, positive=True)
    entry = _finite(entry_fill_price, positive=True)
    exit_price = _finite(exit_fill_price, positive=True)
    stop = _finite(initial_stop_price, positive=True)
    if (side == "LONG" and stop >= entry) or (side == "SHORT" and stop <= entry):
        raise ValueError("V5_INITIAL_STOP_NOT_MINUS_1R")
    direction = 1 if side == "LONG" else -1
    risk_quote = abs(entry - stop) * qty
    if not math.isfinite(risk_quote) or risk_quote <= 0:
        raise ValueError("V5_RISK_INVALID")

    settlements = tuple(funding_events)
    previous_time = -1
    funding = 0.0
    used = 0
    for event in settlements:
        if not isinstance(event, FundingSettlement):
            raise ValueError("V5_FUNDING_EVENT_INVALID")
        if event.time_ms <= previous_time:
            raise ValueError("V5_FUNDING_NOT_STRICTLY_ORDERED")
        previous_time = event.time_ms
        if event.time_ms in (entry_time_ms, exit_time_ms):
            raise ValueError("V5_FUNDING_BOUNDARY_AMBIGUOUS")
        if entry_time_ms < event.time_ms < exit_time_ms:
            funding -= direction * event.rate * event.mark_price * qty
            used += 1

    gross = direction * (exit_price - entry) * qty
    fees = qty * (entry * policy.entry_fee_rate + exit_price * policy.exit_fee_rate)
    slippage = qty * (entry * policy.entry_slippage_rate + exit_price * policy.exit_slippage_rate)
    net = gross - fees - slippage + funding
    values = (risk_quote, gross, fees, slippage, funding, net)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("V5_ACCOUNTING_OVERFLOW")
    return TradeAccounting(
        policy.version, side, qty, risk_quote, gross, fees, slippage,
        funding, net, gross / risk_quote, (fees + slippage) / risk_quote,
        funding / risk_quote, net / risk_quote, used,
    )


def submit_order(*_args, **_kwargs):
    raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
