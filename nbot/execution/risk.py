"""Pure fail-closed execution risk policy for NBOT V3.1.3.

This module owns only capital-risk calculation and veto decisions.  It performs
no exchange writes, no state persistence, no Observation calls, and no position
management.  Later lifecycles orchestrate these checks around durable state and
ExchangePort operations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from nbot.exchange.contracts import AccountSnapshot, EntryPlan, Fill, ProtectiveStopRef, Quote, Side
from nbot.execution.models import DailyRisk, EntryInflight, OpenPosition


class RiskConfigError(ValueError):
    """Raised when a release risk policy is internally unsafe or malformed."""


class RiskRejected(RuntimeError):
    """Fail-closed veto carrying a stable machine-readable reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskConfigError(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number):
        raise RiskConfigError(f"{name}_INVALID")
    return number


def _positive(name: str, value: object) -> float:
    number = _finite(name, value)
    if number <= 0:
        raise RiskConfigError(f"{name}_INVALID")
    return number


def _nonnegative(name: str, value: object) -> float:
    number = _finite(name, value)
    if number < 0:
        raise RiskConfigError(f"{name}_INVALID")
    return number


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RiskConfigError(f"{name}_INVALID")
    return value


def _timestamp_ms(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RiskRejected(f"{name}_INVALID")
    return value


def _runtime_positive(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskRejected(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise RiskRejected(f"{name}_INVALID")
    return number


def _runtime_nonnegative(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskRejected(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise RiskRejected(f"{name}_INVALID")
    return number


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Frozen V1/V2.8.5 parity defaults for the V3 architecture rebuild.

    These are safety-policy defaults, not an economic optimization.  Any later
    change must be an explicit reviewed config/release decision.
    """

    risk_per_trade_usd: float = 10.0
    max_notional_usd: float = 1000.0
    leverage: int = 5
    max_spread_pct: float = 0.25
    max_quote_age_ms: int = 5_000
    max_reference_price_drift_pct: float = 0.25
    post_fill_notional_tolerance_pct: float = 1.0
    post_fill_risk_tolerance_pct: float = 10.0
    max_entry_slippage_pct: float = 1.0
    daily_profit_lock_trigger_r: float = 100.0
    daily_normal_giveback_r: float = 95.0
    daily_profit_giveback_r: float = 3.0
    max_capital_positions: int = 1

    def __post_init__(self) -> None:
        risk = _positive("RISK_PER_TRADE_USD", self.risk_per_trade_usd)
        notional = _positive("MAX_NOTIONAL_USD", self.max_notional_usd)
        _positive_int("LEVERAGE", self.leverage)
        spread = _positive("MAX_SPREAD_PCT", self.max_spread_pct)
        if spread > 5.0:
            raise RiskConfigError("MAX_SPREAD_PCT_INVALID")
        if isinstance(self.max_quote_age_ms, bool) or not isinstance(self.max_quote_age_ms, int) or self.max_quote_age_ms <= 0:
            raise RiskConfigError("MAX_QUOTE_AGE_MS_INVALID")
        drift = _nonnegative("MAX_REFERENCE_PRICE_DRIFT_PCT", self.max_reference_price_drift_pct)
        if drift > 10.0:
            raise RiskConfigError("MAX_REFERENCE_PRICE_DRIFT_PCT_INVALID")
        notional_tol = _nonnegative("POST_FILL_NOTIONAL_TOLERANCE_PCT", self.post_fill_notional_tolerance_pct)
        if notional_tol > 5.0:
            raise RiskConfigError("POST_FILL_NOTIONAL_TOLERANCE_PCT_INVALID")
        risk_tol = _nonnegative("POST_FILL_RISK_TOLERANCE_PCT", self.post_fill_risk_tolerance_pct)
        if risk_tol > 20.0:
            raise RiskConfigError("POST_FILL_RISK_TOLERANCE_PCT_INVALID")
        slippage = _nonnegative("MAX_ENTRY_SLIPPAGE_PCT", self.max_entry_slippage_pct)
        if slippage > 10.0:
            raise RiskConfigError("MAX_ENTRY_SLIPPAGE_PCT_INVALID")
        _positive("DAILY_PROFIT_LOCK_TRIGGER_R", self.daily_profit_lock_trigger_r)
        _positive("DAILY_NORMAL_GIVEBACK_R", self.daily_normal_giveback_r)
        _positive("DAILY_PROFIT_GIVEBACK_R", self.daily_profit_giveback_r)
        if self.max_capital_positions != 1:
            raise RiskConfigError("MAX_CAPITAL_POSITIONS_MUST_BE_ONE")
        # A LONG 1R stop generated from the maximum notional must remain above 0.
        if risk >= notional:
            raise RiskConfigError("RISK_MUST_BE_BELOW_MAX_NOTIONAL")


class RiskManager:
    """Deterministic execution-only risk calculator and veto authority."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    @staticmethod
    def _require_side(side: object) -> Side:
        if side not in {"LONG", "SHORT"}:
            raise RiskRejected("SIDE_INVALID")
        return side  # type: ignore[return-value]

    def check_entry_capacity(
        self,
        *,
        open_position: OpenPosition | None,
        entry_inflight: EntryInflight | None,
    ) -> None:
        if open_position is not None:
            raise RiskRejected("POSITION_ALREADY_OPEN")
        if entry_inflight is not None:
            raise RiskRejected("ENTRY_ALREADY_IN_PROGRESS")

    def check_quote(self, quote: Quote, *, now_ms: int) -> None:
        now = _timestamp_ms("NOW_MS", now_ms)
        # Preserve the V2 parity clock-skew allowance: a quote may be only as
        # far in the future as the same bounded freshness window.
        if quote.timestamp_ms > now + self.config.max_quote_age_ms:
            raise RiskRejected("QUOTE_FUTURE")
        if now - quote.timestamp_ms > self.config.max_quote_age_ms:
            raise RiskRejected("QUOTE_STALE")
        if quote.spread_pct > self.config.max_spread_pct + 1e-12:
            raise RiskRejected("SPREAD_TOO_WIDE")

    def entry_price(self, quote: Quote, side: Side) -> float:
        direction = self._require_side(side)
        return float(quote.ask if direction == "LONG" else quote.bid)

    def reference_drift_pct(self, *, entry_price: float, reference_price: float) -> float:
        entry = _runtime_positive("ENTRY_PRICE", entry_price)
        reference = _runtime_positive("REFERENCE_PRICE", reference_price)
        return abs(entry - reference) / reference * 100.0

    def check_reference_drift(self, *, entry_price: float, reference_price: float) -> float:
        drift = self.reference_drift_pct(entry_price=entry_price, reference_price=reference_price)
        if drift > self.config.max_reference_price_drift_pct + 1e-12:
            raise RiskRejected("REFERENCE_PRICE_DRIFT")
        return drift

    def build_entry_plan(self, *, symbol: str, side: Side, entry_price: float) -> EntryPlan:
        direction = self._require_side(side)
        entry = _runtime_positive("ENTRY_PRICE", entry_price)
        quantity = self.config.max_notional_usd / entry
        risk_per_unit = self.config.risk_per_trade_usd / quantity
        stop = entry - risk_per_unit if direction == "LONG" else entry + risk_per_unit
        if not math.isfinite(stop) or stop <= 0:
            raise RiskRejected("INITIAL_STOP_INVALID")
        return EntryPlan(
            symbol=symbol,
            side=direction,
            quantity=quantity,
            expected_entry_price=entry,
            initial_stop_price=stop,
            initial_risk_usd=self.config.risk_per_trade_usd,
            notional_usd=self.config.max_notional_usd,
            leverage=self.config.leverage,
        )

    def check_account_margin(self, account: AccountSnapshot, plan: EntryPlan) -> float:
        required_margin = float(plan.notional_usd) / float(plan.leverage)
        if float(account.available_balance_usd) + 1e-9 < required_margin:
            raise RiskRejected("INSUFFICIENT_MARGIN")
        return required_margin

    def post_fill_violation(
        self,
        *,
        plan: EntryPlan,
        fill: Fill,
        stop_ref: ProtectiveStopRef,
    ) -> str | None:
        executed_notional = float(fill.price) * float(fill.quantity)
        tolerance = self.config.post_fill_notional_tolerance_pct / 100.0
        min_notional = float(plan.notional_usd) * (1.0 - tolerance)
        max_notional = float(plan.notional_usd) * (1.0 + tolerance)
        if not (min_notional - 1e-9 <= executed_notional <= max_notional + 1e-9):
            return "POST_FILL_NOTIONAL_BREACH"

        slippage_pct = (
            abs(float(fill.price) - float(plan.expected_entry_price))
            / float(plan.expected_entry_price)
            * 100.0
        )
        if slippage_pct > self.config.max_entry_slippage_pct + 1e-12:
            return "POST_FILL_SLIPPAGE_BREACH"

        if (
            stop_ref.symbol != plan.symbol
            or stop_ref.side != plan.side
            or not math.isclose(float(stop_ref.quantity), float(fill.quantity), rel_tol=1e-12, abs_tol=1e-12)
        ):
            return "POST_FILL_STOP_IDENTITY_MISMATCH"

        actual_risk = abs(float(fill.price) - float(stop_ref.trigger_price)) * float(fill.quantity)
        max_risk = float(plan.initial_risk_usd) * (
            1.0 + self.config.post_fill_risk_tolerance_pct / 100.0
        )
        if actual_risk > max_risk + 1e-9:
            return "POST_FILL_RISK_BREACH"
        return None

    def require_post_fill_safe(
        self,
        *,
        plan: EntryPlan,
        fill: Fill,
        stop_ref: ProtectiveStopRef,
    ) -> None:
        violation = self.post_fill_violation(plan=plan, fill=fill, stop_ref=stop_ref)
        if violation is not None:
            raise RiskRejected(violation)

    def daily_floor_usd(self, peak_realized_pnl_usd: float) -> float:
        peak = _runtime_nonnegative("DAILY_PEAK_REALIZED_PNL_USD", peak_realized_pnl_usd)
        peak_r = peak / self.config.risk_per_trade_usd
        giveback_r = (
            self.config.daily_profit_giveback_r
            if peak_r >= self.config.daily_profit_lock_trigger_r
            else self.config.daily_normal_giveback_r
        )
        return (peak_r - giveback_r) * self.config.risk_per_trade_usd

    @staticmethod
    def utc_day(timestamp_ms: int) -> str:
        ts = _timestamp_ms("TIMESTAMP_MS", timestamp_ms)
        return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).date().isoformat()

    def roll_daily(self, daily: DailyRisk, *, timestamp_ms: int) -> DailyRisk:
        target_day = self.utc_day(timestamp_ms)
        if daily.utc_day == target_day:
            return self.evaluate_daily(daily)
        return self.evaluate_daily(DailyRisk(utc_day=target_day))

    def evaluate_daily(self, daily: DailyRisk) -> DailyRisk:
        floor = self.daily_floor_usd(daily.peak_realized_pnl_usd)
        if daily.halted:
            # A daily halt is sticky until UTC rollover.  Restart/evaluation must
            # never silently clear an already-persisted capital block.
            return replace(daily, loss_floor_usd=floor)
        halted = float(daily.realized_pnl_usd) < floor
        return replace(
            daily,
            loss_floor_usd=floor,
            halted=halted,
            halt_reason="DAILY_LOSS_FLOOR_BREACH" if halted else None,
        )

    def check_daily_entry(self, daily: DailyRisk, *, now_ms: int) -> DailyRisk:
        current = self.roll_daily(daily, timestamp_ms=now_ms)
        if current.halted:
            raise RiskRejected(current.halt_reason or "DAILY_HALT")
        return current

    def after_close(
        self,
        daily: DailyRisk,
        *,
        realized_pnl_usd: float,
        closed_timestamp_ms: int,
        highest_unrealized_usd: float = 0.0,
    ) -> DailyRisk:
        unrealized_high = _runtime_nonnegative("DAILY_CLOSE_HIGHEST_UNREALIZED_USD", highest_unrealized_usd)
        if isinstance(realized_pnl_usd, bool) or not isinstance(realized_pnl_usd, (int, float)):
            raise RiskRejected("REALIZED_PNL_USD_INVALID")
        pnl = float(realized_pnl_usd)
        if not math.isfinite(pnl):
            raise RiskRejected("REALIZED_PNL_USD_INVALID")
        current = self.roll_daily(daily, timestamp_ms=closed_timestamp_ms)
        realized = float(current.realized_pnl_usd) + pnl
        peak = max(float(current.peak_realized_pnl_usd), realized, 0.0)
        updated = replace(
            current,
            realized_pnl_usd=realized,
            peak_realized_pnl_usd=peak,
            highest_unrealized_usd=max(float(current.highest_unrealized_usd), unrealized_high),
            trades_closed=current.trades_closed + 1,
        )
        return self.evaluate_daily(updated)
