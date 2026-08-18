"""Durable execution-state models for NBOT V3.1.

These are intentionally small, typed, and fail-closed.  They contain no
Observation, strategy, research, candidate, learning, or training dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from nbot.exchange.contracts import EntryPlan, Fill, ProtectiveStopRef, Side


def _require_text(name: str, value: object, *, max_length: int = 160) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}_INVALID")
    if not value or value != value.strip() or len(value) > max_length:
        raise ValueError(f"{name}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name}_INVALID")
    return value


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


def _require_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name}_INVALID")
    return value


def _require_positive_timestamp(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name}_INVALID")
    return value


def _require_side(value: object) -> Side:
    if value not in {"LONG", "SHORT"}:
        raise ValueError("SIDE_INVALID")
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """A capital-bearing position that is already proven protected.

    Construction itself enforces the V3 invariant that OPEN means there is a
    canonical protective stop identity and that current protection has not been
    loosened beyond the original accepted stop.
    """

    proposal_id: str
    symbol: str
    side: Side
    entry_fill: Fill
    initial_risk_usd: float
    initial_stop_price: float
    protective_stop: ProtectiveStopRef
    entry_authority: str
    exit_policy_version: str
    mfe_r: float = 0.0
    mae_r: float = 0.0

    def __post_init__(self) -> None:
        _require_text("OPEN_POSITION_PROPOSAL_ID", self.proposal_id)
        _require_text("OPEN_POSITION_SYMBOL", self.symbol, max_length=40)
        side = _require_side(self.side)
        _require_number("OPEN_POSITION_INITIAL_RISK_USD", self.initial_risk_usd, positive=True)
        initial_stop = _require_number(
            "OPEN_POSITION_INITIAL_STOP_PRICE",
            self.initial_stop_price,
            positive=True,
        )
        _require_text("OPEN_POSITION_ENTRY_AUTHORITY", self.entry_authority)
        _require_text("OPEN_POSITION_EXIT_POLICY_VERSION", self.exit_policy_version)
        mfe = _require_number("OPEN_POSITION_MFE_R", self.mfe_r, nonnegative=True)
        mae = _require_number("OPEN_POSITION_MAE_R", self.mae_r)
        if mae > 0:
            raise ValueError("OPEN_POSITION_MAE_R_INVALID")
        if self.protective_stop.symbol != self.symbol:
            raise ValueError("OPEN_POSITION_STOP_SYMBOL_MISMATCH")
        if self.protective_stop.side != side:
            raise ValueError("OPEN_POSITION_STOP_SIDE_MISMATCH")
        if not math.isclose(
            float(self.protective_stop.quantity),
            float(self.entry_fill.quantity),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("OPEN_POSITION_STOP_QUANTITY_MISMATCH")
        entry = float(self.entry_fill.price)
        current_stop = float(self.protective_stop.trigger_price)
        if side == "LONG":
            if initial_stop >= entry:
                raise ValueError("OPEN_POSITION_LONG_INITIAL_STOP_INVALID")
            if current_stop + 1e-12 < initial_stop:
                raise ValueError("OPEN_POSITION_PROTECTION_LOOSENED")
        else:
            if initial_stop <= entry:
                raise ValueError("OPEN_POSITION_SHORT_INITIAL_STOP_INVALID")
            if current_stop - 1e-12 > initial_stop:
                raise ValueError("OPEN_POSITION_PROTECTION_LOOSENED")
        # Touch values so static analyzers and future refactors cannot accidentally
        # remove their validation as "unused".
        _ = (mfe, mae)

    @property
    def entry_price(self) -> float:
        return float(self.entry_fill.price)

    @property
    def quantity(self) -> float:
        return float(self.entry_fill.quantity)

    @property
    def entry_timestamp_ms(self) -> int:
        return int(self.entry_fill.timestamp_ms)

    @property
    def entry_order_id(self) -> str:
        return self.entry_fill.order_id

    @property
    def entry_client_order_id(self) -> str:
        return self.entry_fill.client_order_id

    @property
    def stop_price(self) -> float:
        return float(self.protective_stop.trigger_price)


@dataclass(frozen=True, slots=True)
class EntryInflight:
    """Durable crash-recovery journal written before one market entry request."""

    proposal_id: str
    entry_authority: str
    exit_policy_version: str
    plan: EntryPlan
    client_order_id: str
    started_at_ms: int
    fill: Fill | None = None

    def __post_init__(self) -> None:
        _require_text("ENTRY_INFLIGHT_PROPOSAL_ID", self.proposal_id)
        _require_text("ENTRY_INFLIGHT_ENTRY_AUTHORITY", self.entry_authority)
        _require_text("ENTRY_INFLIGHT_EXIT_POLICY_VERSION", self.exit_policy_version)
        _require_text("ENTRY_INFLIGHT_CLIENT_ORDER_ID", self.client_order_id)
        _require_positive_timestamp("ENTRY_INFLIGHT_STARTED_AT_MS", self.started_at_ms)
        if self.fill is not None and self.fill.client_order_id != self.client_order_id:
            raise ValueError("ENTRY_INFLIGHT_FILL_CLIENT_ORDER_ID_MISMATCH")


@dataclass(frozen=True, slots=True)
class DailyRisk:
    """Persisted UTC-day execution risk accounting."""

    utc_day: str | None = None
    realized_pnl_usd: float = 0.0
    peak_realized_pnl_usd: float = 0.0
    loss_floor_usd: float | None = None
    highest_unrealized_usd: float = 0.0
    halted: bool = False
    halt_reason: str | None = None
    trades_closed: int = 0

    def __post_init__(self) -> None:
        if self.utc_day is not None:
            _require_text("DAILY_RISK_UTC_DAY", self.utc_day, max_length=10)
            try:
                parsed = date.fromisoformat(self.utc_day)
            except ValueError as exc:
                raise ValueError("DAILY_RISK_UTC_DAY_INVALID") from exc
            if parsed.isoformat() != self.utc_day:
                raise ValueError("DAILY_RISK_UTC_DAY_INVALID")
        realized = _require_number("DAILY_RISK_REALIZED_PNL_USD", self.realized_pnl_usd)
        peak = _require_number(
            "DAILY_RISK_PEAK_REALIZED_PNL_USD",
            self.peak_realized_pnl_usd,
            nonnegative=True,
        )
        if peak + 1e-12 < max(0.0, realized):
            raise ValueError("DAILY_RISK_PEAK_BELOW_REALIZED")
        if self.loss_floor_usd is not None:
            _require_number("DAILY_RISK_LOSS_FLOOR_USD", self.loss_floor_usd)
        _require_number(
            "DAILY_RISK_HIGHEST_UNREALIZED_USD",
            self.highest_unrealized_usd,
            nonnegative=True,
        )
        if not isinstance(self.halted, bool):
            raise ValueError("DAILY_RISK_HALTED_INVALID")
        if self.halted:
            if self.halt_reason is None:
                raise ValueError("DAILY_RISK_HALT_REASON_REQUIRED")
            _require_text("DAILY_RISK_HALT_REASON", self.halt_reason)
        elif self.halt_reason is not None:
            raise ValueError("DAILY_RISK_HALT_REASON_WITHOUT_HALT")
        _require_nonnegative_int("DAILY_RISK_TRADES_CLOSED", self.trades_closed)


@dataclass(frozen=True, slots=True)
class ExecutionHealth:
    """Low-overhead execution-only health snapshot contract.

    The mutable monitor that produces this snapshot belongs in V3.1.5; this
    phase only freezes the data shape and validity rules.
    """

    prepare_calls: int = 0
    flat_cycles: int = 0
    open_position_ticks: int = 0
    stop_updates: int = 0
    stop_missing_events: int = 0
    stop_settlement_waits: int = 0
    stop_recoveries: int = 0
    emergency_exits: int = 0
    reconciliations: int = 0
    proposal_rejections: int = 0
    last_position_manage_ms: float = 0.0
    max_position_manage_ms: float = 0.0
    last_event: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "prepare_calls",
            "flat_cycles",
            "open_position_ticks",
            "stop_updates",
            "stop_missing_events",
            "stop_settlement_waits",
            "stop_recoveries",
            "emergency_exits",
            "reconciliations",
            "proposal_rejections",
        ):
            _require_nonnegative_int(f"EXECUTION_HEALTH_{name.upper()}", getattr(self, name))
        last_ms = _require_number(
            "EXECUTION_HEALTH_LAST_POSITION_MANAGE_MS",
            self.last_position_manage_ms,
            nonnegative=True,
        )
        max_ms = _require_number(
            "EXECUTION_HEALTH_MAX_POSITION_MANAGE_MS",
            self.max_position_manage_ms,
            nonnegative=True,
        )
        if max_ms + 1e-12 < last_ms:
            raise ValueError("EXECUTION_HEALTH_MAX_BELOW_LAST")
        if self.last_event is not None:
            _require_text("EXECUTION_HEALTH_LAST_EVENT", self.last_event)
