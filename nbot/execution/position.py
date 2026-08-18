"""Fail-closed V3.1.5 open-position lifecycle.

This module owns only the capital hot path for an already-open, already-proven
protected position.  It consumes Execution's own price tick and exchange truth,
updates MAE/MFE and health, enforces the immutable risk contract, and advances
the initial ``INTEGER_R_STEP_CONTROL`` protective-stop policy.

It deliberately does not finalize closes or repair contradictory exchange
state.  Those conditions are surfaced as ``PositionReconciliationRequired``
for V3.1.6.  It contains no ProposalClient, OutcomeClient, Observation,
strategy, research, learning, or training dependency.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from typing import Callable, Protocol

from nbot.exchange.contracts import ExchangePort, ExchangePosition, ProtectiveStopRef, Side
from nbot.execution.models import DailyRisk, ExecutionHealth, OpenPosition
from nbot.execution.risk import RiskManager, RiskRejected
from nbot.execution.state import ExecutionStateError, ExecutionStateStore

INTEGER_R_STEP_CONTROL = "INTEGER_R_STEP_CONTROL"


class PositionSafetyError(RuntimeError):
    """Capital-safety failure while a locally open position still matters."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class PositionReconciliationRequired(PositionSafetyError):
    """Exchange/local truth needs V3.1.6 reconciliation before management continues."""


class VerifiedEmergencyPort(Protocol):
    """V3.1.7-compatible verified emergency flatten boundary."""

    def flatten_verified(self, symbol: str, side: Side, *, reason: str) -> None: ...


@dataclass(frozen=True, slots=True)
class PositionManageResult:
    """Point-in-time result of one relevant open-position tick."""

    status: str
    symbol: str | None = None
    unrealized_pnl_usd: float | None = None
    current_r: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    stop_price: float | None = None
    stop_updated: bool = False


class ExecutionHealthMonitor:
    """Small mutable producer for the durable ``ExecutionHealth`` snapshot."""

    _COUNTERS = (
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
    )

    def __init__(self, initial: ExecutionHealth | None = None):
        initial = initial or ExecutionHealth()
        self._counters = {name: int(getattr(initial, name)) for name in self._COUNTERS}
        self.last_position_manage_ms = float(initial.last_position_manage_ms)
        self.max_position_manage_ms = float(initial.max_position_manage_ms)
        self.last_event = initial.last_event

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._counters:
            raise ValueError("EXECUTION_HEALTH_COUNTER_UNKNOWN")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("EXECUTION_HEALTH_INCREMENT_INVALID")
        self._counters[name] += amount

    def observe_manage_ms(self, value_ms: float) -> None:
        if isinstance(value_ms, bool) or not isinstance(value_ms, (int, float)):
            raise ValueError("EXECUTION_HEALTH_LATENCY_INVALID")
        value = float(value_ms)
        if not math.isfinite(value) or value < 0:
            raise ValueError("EXECUTION_HEALTH_LATENCY_INVALID")
        self.last_position_manage_ms = value
        self.max_position_manage_ms = max(self.max_position_manage_ms, value)

    def event(self, name: str) -> None:
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError("EXECUTION_HEALTH_EVENT_INVALID")
        self.last_event = name

    def snapshot(self) -> ExecutionHealth:
        return ExecutionHealth(
            **self._counters,
            last_position_manage_ms=self.last_position_manage_ms,
            max_position_manage_ms=self.max_position_manage_ms,
            last_event=self.last_event,
        )


class PositionLifecycle:
    """Manage exactly one proven-protected position from Execution's own ticks."""

    def __init__(
        self,
        *,
        exchange: ExchangePort,
        state: ExecutionStateStore,
        risk: RiskManager,
        emergency: VerifiedEmergencyPort,
        monotonic_ns: Callable[[], int] = time.perf_counter_ns,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.emergency = emergency
        self._monotonic_ns = monotonic_ns
        self.health = ExecutionHealthMonitor(state.health)

    def manage_tick(self, symbol: str, price: float, timestamp_ms: int) -> PositionManageResult:
        """Process one market tick for the currently open symbol only.

        Other symbols are returned before any exchange call or state write.  A
        proven exchange close, missing protection, stop settlement condition, or
        contradictory identity is left durable and raised for V3.1.6 rather
        than guessed/finalized here.
        """
        position = self.state.open_position
        if position is None:
            return PositionManageResult(status="FLAT")
        if symbol != position.symbol:
            return PositionManageResult(status="IGNORED_OTHER_SYMBOL", symbol=position.symbol)

        started_ns = self._monotonic_ns()
        failed = False
        self.health.increment("open_position_ticks")
        try:
            mark = self._require_mark(price=price, timestamp_ms=timestamp_ms)
            self._roll_daily(timestamp_ms)

            exchange_position = self._position_snapshot(position)
            stop_ref = self._stop_snapshot(position)
            self._require_stop_not_looser(position, stop_ref)

            pnl = self._unrealized(position, mark)
            current_r = pnl / float(position.initial_risk_usd)
            mfe_r = max(float(position.mfe_r), current_r, 0.0)
            mae_r = min(float(position.mae_r), current_r, 0.0)
            updated = replace(position, mfe_r=mfe_r, mae_r=mae_r, protective_stop=stop_ref)

            self._update_daily_highest_unrealized(pnl)

            max_loss = float(position.initial_risk_usd) * (
                1.0 + self.risk.config.post_fill_risk_tolerance_pct / 100.0
            )
            if pnl < -max_loss - 1e-9:
                self._emergency(
                    position,
                    reason="RISK_CONTRACT_BREACH",
                )

            if self._price_breached_stop(updated, mark):
                self.health.increment("stop_settlement_waits")
                self.health.event("STOP_BREACH_SETTLEMENT_REQUIRED")
                self._persist_position_metrics(updated)
                raise PositionReconciliationRequired("STOP_BREACH_SETTLEMENT_REQUIRED")

            next_stop = self._integer_r_next_stop(updated)
            stop_updated = False
            if next_stop is not None:
                updated, stop_updated = self._advance_stop(updated, next_stop)
                # A recovered/quantized replacement may itself already be at or
                # beyond the current mark (for example after a rapid retrace).
                # Do not report normal management while exchange stop settlement
                # may already be in flight.
                if self._price_breached_stop(updated, mark):
                    self.health.increment("stop_settlement_waits")
                    self.health.event("STOP_BREACH_SETTLEMENT_REQUIRED")
                    self._persist_position_metrics(updated)
                    raise PositionReconciliationRequired("STOP_BREACH_SETTLEMENT_REQUIRED")

            self._persist_position_metrics(updated)
            self.health.event("POSITION_MANAGED")
            return PositionManageResult(
                status="POSITION_MANAGED",
                symbol=updated.symbol,
                unrealized_pnl_usd=pnl,
                current_r=current_r,
                mfe_r=updated.mfe_r,
                mae_r=updated.mae_r,
                stop_price=updated.stop_price,
                stop_updated=stop_updated,
            )
        except Exception:
            failed = True
            raise
        finally:
            elapsed_ms = max(0.0, (self._monotonic_ns() - started_ns) / 1_000_000.0)
            self.health.observe_manage_ms(elapsed_ms)
            try:
                self.state.set_health(self.health.snapshot())
            except Exception as exc:
                if not failed:
                    raise PositionSafetyError("EXECUTION_HEALTH_PERSIST_FAILED") from exc

    @staticmethod
    def _require_mark(*, price: float, timestamp_ms: int) -> float:
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise PositionSafetyError("OPEN_POSITION_PRICE_INVALID")
        mark = float(price)
        if not math.isfinite(mark) or mark <= 0:
            raise PositionSafetyError("OPEN_POSITION_PRICE_INVALID")
        if isinstance(timestamp_ms, bool) or not isinstance(timestamp_ms, int) or timestamp_ms <= 0:
            raise PositionSafetyError("OPEN_POSITION_TIMESTAMP_INVALID")
        return mark

    def _roll_daily(self, timestamp_ms: int) -> None:
        try:
            daily = self.risk.roll_daily(self.state.daily_risk, timestamp_ms=timestamp_ms)
        except RiskRejected as exc:
            raise PositionSafetyError(exc.reason) from exc
        if daily != self.state.daily_risk:
            try:
                self.state.set_daily_risk(daily)
            except ExecutionStateError as exc:
                raise PositionSafetyError("DAILY_RISK_PERSIST_FAILED") from exc

    def _position_snapshot(self, local: OpenPosition) -> ExchangePosition:
        try:
            exchange_position = self.exchange.position_snapshot()
        except Exception as exc:
            self.health.event("POSITION_SNAPSHOT_FAILED")
            raise PositionReconciliationRequired("POSITION_SNAPSHOT_FAILED") from exc
        if exchange_position is None:
            self.health.event("EXCHANGE_POSITION_CLOSED")
            raise PositionReconciliationRequired("EXCHANGE_POSITION_CLOSED")
        if exchange_position.symbol != local.symbol:
            raise PositionReconciliationRequired("POSITION_SYMBOL_MISMATCH")
        if exchange_position.side != local.side:
            raise PositionReconciliationRequired("POSITION_SIDE_MISMATCH")
        if not math.isclose(
            float(exchange_position.quantity),
            float(local.quantity),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise PositionReconciliationRequired("POSITION_QUANTITY_MISMATCH")
        if not math.isclose(
            float(exchange_position.entry_price),
            float(local.entry_price),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise PositionReconciliationRequired("POSITION_ENTRY_PRICE_MISMATCH")
        return exchange_position

    def _stop_snapshot(self, local: OpenPosition) -> ProtectiveStopRef:
        try:
            stop_ref = self.exchange.protective_stop_snapshot(local.symbol)
        except Exception as exc:
            self.health.increment("stop_missing_events")
            self._emergency(local, reason="PROTECTION_TRUTH_UNAVAILABLE", cause=exc)
            raise AssertionError("unreachable")
        if stop_ref is None:
            self.health.increment("stop_missing_events")
            self.health.event("PROTECTIVE_STOP_MISSING")
            raise PositionReconciliationRequired("PROTECTIVE_STOP_MISSING")
        self._require_stop_identity(local, stop_ref)
        return stop_ref

    @staticmethod
    def _require_stop_identity(local: OpenPosition, stop_ref: ProtectiveStopRef) -> None:
        if stop_ref.symbol != local.symbol:
            raise PositionReconciliationRequired("PROTECTIVE_STOP_SYMBOL_MISMATCH")
        if stop_ref.side != local.side:
            raise PositionReconciliationRequired("PROTECTIVE_STOP_SIDE_MISMATCH")
        if not math.isclose(
            float(stop_ref.quantity), float(local.quantity), rel_tol=1e-9, abs_tol=1e-12
        ):
            raise PositionReconciliationRequired("PROTECTIVE_STOP_QUANTITY_MISMATCH")

    def _require_stop_not_looser(self, local: OpenPosition, stop_ref: ProtectiveStopRef) -> None:
        current = float(local.stop_price)
        observed = float(stop_ref.trigger_price)
        if local.side == "LONG" and observed + 1e-12 < current:
            self._emergency(local, reason="PROTECTIVE_STOP_LOOSENED")
        if local.side == "SHORT" and observed - 1e-12 > current:
            self._emergency(local, reason="PROTECTIVE_STOP_LOOSENED")

    @staticmethod
    def _unrealized(position: OpenPosition, price: float) -> float:
        if position.side == "LONG":
            return (price - float(position.entry_price)) * float(position.quantity)
        return (float(position.entry_price) - price) * float(position.quantity)

    def _update_daily_highest_unrealized(self, pnl: float) -> None:
        daily = self.state.daily_risk
        high = max(float(daily.highest_unrealized_usd), pnl, 0.0)
        if high <= float(daily.highest_unrealized_usd) + 1e-12:
            return
        updated = replace(daily, highest_unrealized_usd=high)
        try:
            self.state.set_daily_risk(updated)
        except ExecutionStateError as exc:
            raise PositionSafetyError("DAILY_UNREALIZED_PERSIST_FAILED") from exc

    @staticmethod
    def _price_breached_stop(position: OpenPosition, price: float) -> bool:
        if position.side == "LONG":
            return price <= float(position.stop_price) + 1e-12
        return price >= float(position.stop_price) - 1e-12

    @staticmethod
    def _integer_r_next_stop(position: OpenPosition) -> float | None:
        if position.exit_policy_version != INTEGER_R_STEP_CONTROL:
            raise PositionSafetyError("UNSUPPORTED_EXIT_POLICY")
        if float(position.mfe_r) < 1.0:
            return None
        locked_r = math.floor(float(position.mfe_r)) - 1
        per_r = float(position.initial_risk_usd) / float(position.quantity)
        if position.side == "LONG":
            candidate = float(position.entry_price) + locked_r * per_r
            return candidate if candidate > float(position.stop_price) + 1e-12 else None
        candidate = float(position.entry_price) - locked_r * per_r
        return candidate if candidate < float(position.stop_price) - 1e-12 else None

    def _advance_stop(self, position: OpenPosition, target: float) -> tuple[OpenPosition, bool]:
        try:
            returned = self.exchange.replace_protective_stop(
                position.symbol,
                position.side,
                float(position.quantity),
                target,
            )
        except Exception as replace_error:
            return self._recover_replacement_truth(position, target, replace_error)

        self._require_stop_identity(position, returned)
        try:
            observed = self.exchange.protective_stop_snapshot(position.symbol)
        except Exception as exc:
            self._emergency(position, reason="STOP_REPLACEMENT_VERIFICATION_FAILED", cause=exc)
            raise AssertionError("unreachable")
        if observed is None:
            self._emergency(position, reason="STOP_REPLACEMENT_UNPROTECTED")
        assert observed is not None
        self._require_stop_identity(position, observed)
        return self._accept_observed_stop(position, target, observed)

    def _recover_replacement_truth(
        self,
        position: OpenPosition,
        target: float,
        cause: Exception,
    ) -> tuple[OpenPosition, bool]:
        try:
            observed = self.exchange.protective_stop_snapshot(position.symbol)
        except Exception as verify_error:
            self._emergency(
                position,
                reason="STOP_REPLACEMENT_OUTCOME_UNKNOWN",
                cause=verify_error,
            )
            raise AssertionError("unreachable")
        if observed is None:
            self._emergency(position, reason="STOP_REPLACEMENT_UNPROTECTED", cause=cause)
        assert observed is not None
        self._require_stop_identity(position, observed)
        return self._accept_observed_stop(position, target, observed)

    def _accept_observed_stop(
        self,
        position: OpenPosition,
        target: float,
        observed: ProtectiveStopRef,
    ) -> tuple[OpenPosition, bool]:
        current = float(position.stop_price)
        actual = float(observed.trigger_price)
        if position.side == "LONG":
            if actual + 1e-12 < current:
                self._emergency(position, reason="STOP_REPLACEMENT_LOOSENED")
            reached_target = actual + 1e-12 >= target
            improved = actual > current + 1e-12
        else:
            if actual - 1e-12 > current:
                self._emergency(position, reason="STOP_REPLACEMENT_LOOSENED")
            reached_target = actual - 1e-12 <= target
            improved = actual < current - 1e-12

        # If the write was ambiguous but exchange truth still proves the old
        # protection, keep managing safely and retry the target on a future tick.
        if not reached_target:
            return replace(position, protective_stop=observed), False

        updated = replace(position, protective_stop=observed)
        if improved:
            self.health.increment("stop_updates")
        return updated, improved

    def _persist_position_metrics(self, position: OpenPosition) -> None:
        try:
            self.state.update_open_position(position)
        except ExecutionStateError as exc:
            raise PositionSafetyError("OPEN_POSITION_PERSIST_FAILED") from exc

    def _emergency(
        self,
        position: OpenPosition,
        *,
        reason: str,
        cause: Exception | None = None,
    ) -> None:
        self.health.increment("emergency_exits")
        self.health.event(reason)
        try:
            self.emergency.flatten_verified(position.symbol, position.side, reason=reason)
        except Exception as exc:
            raise PositionSafetyError(f"{reason}_EMERGENCY_FAILED") from exc
        # Preserve local OPEN until V3.1.6 proves/settles authoritative close
        # evidence. Verified flatness is not enough to invent exit accounting.
        error = PositionSafetyError(f"{reason}_EMERGENCY_FLAT")
        if cause is None:
            raise error
        raise error from cause
