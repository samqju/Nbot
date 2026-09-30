"""Fail-closed V3.1.6 Execution reconciliation.

Reconciliation is the bridge between durable local Execution state and current
exchange truth.  It runs before any new capital request and on demand after
position/stop ambiguity.  It never contacts Observation and never invents
missing fills, positions, closes, realized PnL, or protection identities.

Key restart invariants:

* local FLAT + exchange FLAT is not clean until orphan protective stops are
  verified removed;
* local OPEN + matching exchange OPEN must have canonical non-loosened
  protection, with bounded stop-trigger settlement grace before recovery;
* local OPEN + exchange FLAT is finalized only from authoritative close
  accounting;
* entry-inflight recovery uses the exact durable client order identity and
  never submits another market entry;
* contradictory, unmanaged, multiple, hedged, or unprovable exchange truth
  disables new entries and remains fail closed.
"""

from __future__ import annotations

from nbot.common.synchronization import state_transition

import math
import time
import uuid
from dataclasses import dataclass, replace
from typing import Callable, Protocol, runtime_checkable

from nbot.exchange.contracts import (
    CloseFill,
    ExchangePort,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Side,
)
from nbot.execution.models import (
    DailyRisk,
    EntryInflight,
    OpenPosition,
    exchange_entry_price_matches_fill,
)
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.risk import RiskManager, RiskRejected
from nbot.execution.state import ExecutionStateError, RecoveryMetadata


class ReconciliationError(RuntimeError):
    """Exchange/local truth could not be reconciled safely."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ReconciliationCritical(ReconciliationError):
    """A fail-closed condition that blocks all new entries."""


class VerifiedEmergencyPort(Protocol):
    """V3.1.7-compatible emergency boundary.

    Returning means the adapter/handler has independently verified exchange
    flatness.  Close accounting is still recovered separately; a close request
    is never treated as proof of settlement.
    """

    def flatten_verified(self, symbol: str, side: Side, *, reason: str) -> None: ...


@runtime_checkable
class ReconciliationExchangePort(ExchangePort, Protocol):
    """ExchangePort plus restart-only recovery capabilities.

    Paper/Testnet adapters introduced later must implement these two methods.
    They stay out of the hot Entry/Position interface because they are only
    needed when resolving restart/flatness history.
    """

    def cleanup_orphan_protective_stops(self) -> int:
        """Remove and verify all orphan capital-protective stops; return count."""

    def recover_closed_inflight_entry(self, inflight: EntryInflight) -> CloseFill:
        """Recover authoritative close/accounting for a filled inflight entry."""


@dataclass(frozen=True, slots=True)
class ReconciliationConfig:
    """Frozen parity controls for stop-trigger settlement races."""

    stop_trigger_grace_seconds: float = 8.0
    stop_trigger_poll_interval_seconds: float = 0.5

    def __post_init__(self) -> None:
        for name, value, minimum, maximum, inclusive_min in (
            ("STOP_TRIGGER_GRACE_SECONDS", self.stop_trigger_grace_seconds, 0.0, 60.0, True),
            ("STOP_TRIGGER_POLL_INTERVAL_SECONDS", self.stop_trigger_poll_interval_seconds, 0.0, 10.0, False),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name}_INVALID")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"{name}_INVALID")
            if inclusive_min:
                if number < minimum or number > maximum:
                    raise ValueError(f"{name}_INVALID")
            elif number <= minimum or number > maximum:
                raise ValueError(f"{name}_INVALID")


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: str
    symbol: str | None = None
    outcome_id: str | None = None
    recovered_stop: bool = False
    orphans_removed: int = 0


class ReconciliationLifecycle:
    """Reconcile one Execution profile against authoritative exchange truth."""

    def __init__(
        self,
        *,
        exchange: ReconciliationExchangePort,
        durable: ExecutionDurableStore,
        risk: RiskManager,
        emergency: VerifiedEmergencyPort,
        config: ReconciliationConfig | None = None,
        now_ms: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not isinstance(exchange, ReconciliationExchangePort):
            raise TypeError("RECONCILIATION_EXCHANGE_PORT_INCOMPLETE")
        self.exchange = exchange
        self.durable = durable
        self.state = durable.state
        self.risk = risk
        self.emergency = emergency
        self.config = config or ReconciliationConfig()
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._monotonic = monotonic
        self._sleep = sleep

    @state_transition
    def reconcile(self) -> ReconciliationResult:
        """Perform one capital-first reconciliation with no Observation calls."""
        now = self._validated_now_ms()
        self._increment_health("reconciliations", event="RECONCILIATION_STARTED")
        try:
            self.exchange.connect()
            if self.exchange.is_healthy() is not True:
                raise ReconciliationCritical("EXCHANGE_UNHEALTHY")
            self._roll_daily(now)
            exchange_position = self._position_snapshot()
            local = self.state.open_position
            inflight = self.state.entry_inflight
            if local is not None and inflight is not None:
                raise ReconciliationCritical("EXECUTION_STATE_OPEN_AND_INFLIGHT")

            if inflight is not None:
                result = self._recover_inflight(inflight, exchange_position)
            elif local is not None:
                result = self._reconcile_open(local, exchange_position)
            else:
                if exchange_position is not None:
                    raise ReconciliationCritical("UNMANAGED_EXCHANGE_POSITION")
                removed = self._cleanup_orphans()
                result = ReconciliationResult(status="FLAT", orphans_removed=removed)

            self._record_recovery(now, result.status, critical=False)
            self._set_health_event(result.status)
            return result
        except ReconciliationError as exc:
            self._fail_closed(now, exc.reason)
            raise
        except Exception as exc:
            reason = f"RECONCILIATION_UNEXPECTED:{type(exc).__name__}"
            self._fail_closed(now, reason)
            raise ReconciliationCritical(reason) from exc

    def _recover_inflight(
        self,
        inflight: EntryInflight,
        exchange_position: ExchangePosition | None,
    ) -> ReconciliationResult:
        fill = inflight.fill
        if fill is None:
            try:
                fill = self.exchange.recover_inflight_entry(
                    inflight.plan,
                    client_order_id=inflight.client_order_id,
                )
            except Exception as exc:
                raise ReconciliationCritical("ENTRY_INFLIGHT_RECOVERY_FAILED") from exc

        if fill is None:
            if exchange_position is not None:
                raise ReconciliationCritical("ENTRY_INFLIGHT_NOT_FILLED_BUT_POSITION_EXISTS")
            removed = self._cleanup_orphans()
            try:
                self.state.clear_entry_inflight()
            except ExecutionStateError as exc:
                raise ReconciliationCritical("ENTRY_INFLIGHT_CLEAR_FAILED") from exc
            return ReconciliationResult(status="ENTRY_INFLIGHT_PROVEN_UNFILLED", orphans_removed=removed)

        # Recovery performs network I/O; do not use the pre-recovery position snapshot.
        exchange_position = self._position_snapshot()
        self._validate_inflight_fill(inflight, fill)
        if inflight.fill is None:
            try:
                self.state.record_inflight_fill(fill)
            except ExecutionStateError as exc:
                raise ReconciliationCritical("ENTRY_INFLIGHT_FILL_PERSIST_FAILED") from exc
            inflight = self.state.entry_inflight
            assert inflight is not None and inflight.fill is not None

        if exchange_position is None:
            close = self._recover_closed_inflight(inflight)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_inflight_close(inflight, close)
            return ReconciliationResult(
                status="ENTRY_INFLIGHT_CLOSE_RECOVERED",
                symbol=inflight.plan.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        self._assert_inflight_position_match(inflight, exchange_position)
        stop_ref = self._recover_or_verify_inflight_protection(inflight)
        if stop_ref is None:
            close = self._recover_closed_inflight(inflight)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_inflight_close(inflight, close)
            return ReconciliationResult(
                status="ENTRY_INFLIGHT_EMERGENCY_CLOSED",
                symbol=inflight.plan.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )
        violation = self.risk.post_fill_violation(
            plan=inflight.plan,
            fill=inflight.fill,
            stop_ref=stop_ref,
        )
        if violation is not None:
            self._verified_emergency(inflight.plan.symbol, inflight.plan.side, reason=violation)
            close = self._recover_closed_inflight(inflight)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_inflight_close(inflight, close)
            return ReconciliationResult(
                status="ENTRY_INFLIGHT_EMERGENCY_CLOSED",
                symbol=inflight.plan.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        position = self._position_from_inflight(inflight, stop_ref)
        try:
            self.state.promote_inflight_position(position)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("ENTRY_INFLIGHT_PROMOTION_FAILED") from exc
        return ReconciliationResult(
            status="ENTRY_INFLIGHT_RECOVERED_OPEN",
            symbol=position.symbol,
            recovered_stop=True,
        )

    def _reconcile_open(
        self,
        local: OpenPosition,
        exchange_position: ExchangePosition | None,
    ) -> ReconciliationResult:
        if exchange_position is None:
            close = self._recover_closed_position(local)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(local, close)
            return ReconciliationResult(
                status="POSITION_CLOSE_RECOVERED",
                symbol=local.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        self._assert_open_position_match(local, exchange_position)
        active = self._stop_snapshot(local.symbol)
        if active is None:
            return self._restore_missing_stop(local)

        if not self._stop_identity_matches(local.symbol, local.side, local.quantity, active):
            return self._repair_open_protection(local, reason="PROTECTIVE_STOP_IDENTITY_MISMATCH")

        if self._stop_is_looser(local, active):
            return self._repair_open_protection(local, reason="PROTECTIVE_STOP_LOOSENED")

        # A tighter exchange stop is valid protection and becomes the local
        # canonical identity; never loosen it back to an older local stop.
        reconciled = replace(local, protective_stop=active)
        try:
            self.state.update_open_position(reconciled)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("OPEN_POSITION_RECONCILIATION_PERSIST_FAILED") from exc

        if self._stop_already_breached(reconciled):
            settled = self._wait_for_breached_stop_settlement(reconciled)
            if settled is not None:
                return settled
            self._verified_emergency(reconciled.symbol, reconciled.side, reason="LOCAL_STOP_BREACH_UNSETTLED")
            close = self._recover_closed_position(reconciled)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(reconciled, close)
            return ReconciliationResult(
                status="POSITION_EMERGENCY_CLOSED",
                symbol=reconciled.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        return ReconciliationResult(status="POSITION_RECONCILED", symbol=reconciled.symbol)

    def _restore_missing_stop(self, local: OpenPosition) -> ReconciliationResult:
        self._increment_health("stop_missing_events", event="PROTECTIVE_STOP_MISSING")
        settled = self._wait_for_missing_stop_settlement(local)
        if settled is not None:
            return settled

        quote = self._quote(local.symbol)
        if self._price_breached(float(quote.mid), local.side, local.stop_price):
            settled = self._wait_for_breached_stop_settlement(local)
            if settled is not None:
                return settled
            self._verified_emergency(local.symbol, local.side, reason="RECOVERY_BREACHED_STOP")
            close = self._recover_closed_position(local)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(local, close)
            return ReconciliationResult(
                status="POSITION_EMERGENCY_CLOSED",
                symbol=local.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        return self._repair_open_protection(local, reason="PROTECTIVE_STOP_MISSING")

    def _repair_open_protection(self, local: OpenPosition, *, reason: str) -> ReconciliationResult:
        try:
            feasible = self.exchange.validate_protective_stop(
                local.symbol,
                local.side,
                float(local.stop_price),
            )
        except Exception as exc:
            raise ReconciliationCritical("PROTECTIVE_STOP_VALIDATION_FAILED") from exc
        if feasible is not True:
            self._verified_emergency(local.symbol, local.side, reason=f"{reason}_UNRESTORABLE")
            close = self._recover_closed_position(local)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(local, close)
            return ReconciliationResult(
                status="POSITION_EMERGENCY_CLOSED",
                symbol=local.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        try:
            restored = self.exchange.ensure_protective_stop(
                local.symbol,
                local.side,
                float(local.quantity),
                float(local.stop_price),
            )
        except Exception as exc:
            self._verified_emergency(local.symbol, local.side, reason=f"{reason}_RECOVERY_FAILED")
            close = self._recover_closed_position(local)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(local, close)
            return ReconciliationResult(
                status="POSITION_EMERGENCY_CLOSED",
                symbol=local.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )

        try:
            verified = self.exchange.protective_stop_snapshot(local.symbol)
        except Exception as exc:
            raise ReconciliationCritical("PROTECTIVE_STOP_RECOVERY_VERIFY_FAILED") from exc
        if verified is None:
            self._verified_emergency(local.symbol, local.side, reason="PROTECTIVE_STOP_RECOVERY_UNPROTECTED")
            close = self._recover_closed_position(local)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(local, close)
            return ReconciliationResult(
                status="POSITION_EMERGENCY_CLOSED",
                symbol=local.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )
        try:
            self._require_stop_protects(
                local.symbol,
                local.side,
                local.quantity,
                local.stop_price,
                verified,
            )
        except ReconciliationCritical:
            self._verified_emergency(local.symbol, local.side, reason="PROTECTIVE_STOP_RECOVERY_INVALID")
            close = self._recover_closed_position(local)
            removed = self._cleanup_orphans()
            outcome_id = self._finalize_open_close(local, close)
            return ReconciliationResult(
                status="POSITION_EMERGENCY_CLOSED",
                symbol=local.symbol,
                outcome_id=outcome_id,
                orphans_removed=removed,
            )
        updated = replace(local, protective_stop=verified)
        try:
            self.state.update_open_position(updated)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("PROTECTIVE_STOP_RECOVERY_PERSIST_FAILED") from exc
        self._increment_health("stop_recoveries", event="PROTECTIVE_STOP_RECOVERED")
        return ReconciliationResult(
            status="POSITION_RECONCILED",
            symbol=local.symbol,
            recovered_stop=True,
        )

    def _recover_or_verify_inflight_protection(
        self, inflight: EntryInflight
    ) -> ProtectiveStopRef | None:
        assert inflight.fill is not None
        intended_stop = self._stop_for_fill(inflight)
        try:
            active = self.exchange.protective_stop_snapshot(inflight.plan.symbol)
        except Exception as exc:
            raise ReconciliationCritical("ENTRY_INFLIGHT_STOP_TRUTH_FAILED") from exc
        if active is not None:
            try:
                self._require_stop_protects(
                    inflight.plan.symbol,
                    inflight.plan.side,
                    inflight.fill.quantity,
                    intended_stop,
                    active,
                )
            except ReconciliationCritical:
                active = None
            else:
                return active

        try:
            feasible = self.exchange.validate_protective_stop(
                inflight.plan.symbol,
                inflight.plan.side,
                intended_stop,
            )
        except Exception as exc:
            raise ReconciliationCritical("ENTRY_INFLIGHT_STOP_VALIDATION_FAILED") from exc
        if feasible is not True:
            self._verified_emergency(
                inflight.plan.symbol,
                inflight.plan.side,
                reason="ENTRY_INFLIGHT_STOP_UNRESTORABLE",
            )
            return None
        try:
            self.exchange.ensure_protective_stop(
                inflight.plan.symbol,
                inflight.plan.side,
                float(inflight.fill.quantity),
                intended_stop,
            )
        except Exception:
            self._verified_emergency(
                inflight.plan.symbol,
                inflight.plan.side,
                reason="ENTRY_INFLIGHT_PROTECTION_RECOVERY_FAILED",
            )
            return None
        try:
            verified = self.exchange.protective_stop_snapshot(inflight.plan.symbol)
        except Exception as exc:
            raise ReconciliationCritical("ENTRY_INFLIGHT_STOP_VERIFY_FAILED") from exc
        if verified is None:
            self._verified_emergency(
                inflight.plan.symbol,
                inflight.plan.side,
                reason="ENTRY_INFLIGHT_PROTECTION_UNPROVEN",
            )
            return None
        try:
            self._require_stop_protects(
                inflight.plan.symbol,
                inflight.plan.side,
                inflight.fill.quantity,
                intended_stop,
                verified,
            )
        except ReconciliationCritical:
            self._verified_emergency(
                inflight.plan.symbol,
                inflight.plan.side,
                reason="ENTRY_INFLIGHT_PROTECTION_INVALID",
            )
            return None
        self._increment_health("stop_recoveries", event="ENTRY_INFLIGHT_STOP_RECOVERED")
        return verified

    def _wait_for_missing_stop_settlement(self, local: OpenPosition) -> ReconciliationResult | None:
        self._increment_health("stop_settlement_waits", event="STOP_SETTLEMENT_WAIT")
        deadline = self._monotonic() + float(self.config.stop_trigger_grace_seconds)
        while self._monotonic() < deadline:
            self._sleep(float(self.config.stop_trigger_poll_interval_seconds))
            exchange_position = self._position_snapshot()
            if exchange_position is None:
                close = self._recover_closed_position(local)
                removed = self._cleanup_orphans()
                outcome_id = self._finalize_open_close(local, close)
                return ReconciliationResult(
                    status="POSITION_CLOSE_RECOVERED",
                    symbol=local.symbol,
                    outcome_id=outcome_id,
                    orphans_removed=removed,
                )
            self._assert_open_position_match(local, exchange_position)
            active = self._stop_snapshot(local.symbol)
            if active is not None:
                if not self._stop_identity_matches(local.symbol, local.side, local.quantity, active):
                    return self._repair_open_protection(local, reason="PROTECTIVE_STOP_IDENTITY_MISMATCH")
                if self._stop_is_looser(local, active):
                    return self._repair_open_protection(local, reason="PROTECTIVE_STOP_LOOSENED")
                updated = replace(local, protective_stop=active)
                self.state.update_open_position(updated)
                return ReconciliationResult(status="POSITION_RECONCILED", symbol=local.symbol)
        return None

    def _wait_for_breached_stop_settlement(self, local: OpenPosition) -> ReconciliationResult | None:
        self._increment_health("stop_settlement_waits", event="STOP_BREACH_SETTLEMENT_WAIT")
        deadline = self._monotonic() + float(self.config.stop_trigger_grace_seconds)
        while self._monotonic() < deadline:
            self._sleep(float(self.config.stop_trigger_poll_interval_seconds))
            exchange_position = self._position_snapshot()
            if exchange_position is None:
                close = self._recover_closed_position(local)
                removed = self._cleanup_orphans()
                outcome_id = self._finalize_open_close(local, close)
                return ReconciliationResult(
                    status="POSITION_CLOSE_RECOVERED",
                    symbol=local.symbol,
                    outcome_id=outcome_id,
                    orphans_removed=removed,
                )
            self._assert_open_position_match(local, exchange_position)
        return None

    def _stop_already_breached(self, local: OpenPosition) -> bool:
        quote = self._quote(local.symbol)
        return self._price_breached(float(quote.mid), local.side, local.stop_price)

    @staticmethod
    def _price_breached(price: float, side: Side, stop_price: float) -> bool:
        if side == "LONG":
            return price <= float(stop_price) + 1e-12
        return price >= float(stop_price) - 1e-12

    def _position_snapshot(self) -> ExchangePosition | None:
        try:
            return self.exchange.position_snapshot()
        except Exception as exc:
            raise ReconciliationCritical("EXCHANGE_POSITION_SNAPSHOT_FAILED") from exc

    def _stop_snapshot(self, symbol: str) -> ProtectiveStopRef | None:
        try:
            return self.exchange.protective_stop_snapshot(symbol)
        except Exception as exc:
            raise ReconciliationCritical("PROTECTIVE_STOP_SNAPSHOT_FAILED") from exc

    def _quote(self, symbol: str):
        try:
            return self.exchange.quote(symbol)
        except Exception as exc:
            raise ReconciliationCritical("EXECUTION_QUOTE_FAILED") from exc

    def _cleanup_orphans(self) -> int:
        try:
            removed = self.exchange.cleanup_orphan_protective_stops()
        except Exception as exc:
            raise ReconciliationCritical("ORPHAN_STOP_CLEANUP_FAILED") from exc
        if isinstance(removed, bool) or not isinstance(removed, int) or removed < 0:
            raise ReconciliationCritical("ORPHAN_STOP_CLEANUP_RESULT_INVALID")
        return removed

    def _recover_closed_position(self, local: OpenPosition) -> CloseFill:
        try:
            close = self.exchange.recover_closed_position(local)
        except Exception as exc:
            raise ReconciliationCritical("EXTERNAL_CLOSE_RECOVERY_FAILED") from exc
        self._validate_close(close, entry_fill=local.entry_fill)
        return close

    def _recover_closed_inflight(self, inflight: EntryInflight) -> CloseFill:
        assert inflight.fill is not None
        try:
            close = self.exchange.recover_closed_inflight_entry(inflight)
        except Exception as exc:
            raise ReconciliationCritical("ENTRY_INFLIGHT_CLOSE_RECOVERY_FAILED") from exc
        self._validate_close(close, entry_fill=inflight.fill)
        return close

    @staticmethod
    def _validate_close(close: CloseFill, *, entry_fill: Fill) -> None:
        if close.realized_pnl_usd is None:
            raise ReconciliationCritical("CLOSE_ACCOUNTING_UNRESOLVED")
        if int(close.timestamp_ms) < int(entry_fill.timestamp_ms):
            raise ReconciliationCritical("CLOSE_TIMESTAMP_PRECEDES_ENTRY")

    def _finalize_open_close(self, local: OpenPosition, close: CloseFill) -> str:
        outcome_id = self._deterministic_outcome_id(
            proposal_id=local.proposal_id,
            entry_fill=local.entry_fill,
        )
        payload = self._open_close_payload(outcome_id, local, close)
        daily = self._daily_after_close(
            close,
            highest_unrealized_usd=max(0.0, float(self.state.daily_risk.highest_unrealized_usd)),
        )
        try:
            self.durable.finalize_closed_position(outcome_id, payload, daily_risk=daily)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("CLOSE_DURABILITY_FAILED") from exc
        return outcome_id

    def _finalize_inflight_close(self, inflight: EntryInflight, close: CloseFill) -> str:
        assert inflight.fill is not None
        outcome_id = self._deterministic_outcome_id(
            proposal_id=inflight.proposal_id,
            entry_fill=inflight.fill,
        )
        payload = self._inflight_close_payload(outcome_id, inflight, close)
        daily = self._daily_after_close(close, highest_unrealized_usd=0.0)
        try:
            self.durable.finalize_closed_inflight(outcome_id, payload, daily_risk=daily)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("INFLIGHT_CLOSE_DURABILITY_FAILED") from exc
        return outcome_id

    def _daily_after_close(self, close: CloseFill, *, highest_unrealized_usd: float) -> DailyRisk:
        assert close.realized_pnl_usd is not None
        try:
            return self.risk.after_close(
                self.state.daily_risk,
                realized_pnl_usd=float(close.realized_pnl_usd),
                closed_timestamp_ms=int(close.timestamp_ms),
                highest_unrealized_usd=highest_unrealized_usd,
            )
        except RiskRejected as exc:
            raise ReconciliationCritical("DAILY_CLOSE_ACCOUNTING_FAILED") from exc

    def _open_close_payload(
        self,
        outcome_id: str,
        local: OpenPosition,
        close: CloseFill,
    ) -> dict[str, object]:
        assert close.realized_pnl_usd is not None
        pnl = float(close.realized_pnl_usd)
        risk_usd = float(local.initial_risk_usd)
        payload: dict[str, object] = {
            "outcome_id": outcome_id,
            "proposal_id": local.proposal_id,
            "profile": self.state.snapshot.profile,
            "market_environment": self.state.snapshot.market_environment,
            "symbol": local.symbol,
            "side": local.side,
            "entry_price": float(local.entry_price),
            "exit_price": float(close.price),
            "quantity": float(local.quantity),
            "initial_risk_usd": risk_usd,
            "realized_pnl_usd": pnl,
            "r_multiple": pnl / risk_usd,
            "mfe_r": float(local.mfe_r),
            "mae_r": float(local.mae_r),
            "entry_timestamp_ms": int(local.entry_timestamp_ms),
            "closed_timestamp_ms": int(close.timestamp_ms),
            "entry_order_id": local.entry_order_id,
            "entry_client_order_id": local.entry_client_order_id,
            "entry_authority": local.entry_authority,
            "exit_policy_version": local.exit_policy_version,
            "final_stop_price": float(local.stop_price),
            "final_stop_id": local.protective_stop.stop_id,
            "final_client_stop_id": local.protective_stop.client_stop_id,
            "exit_reason": close.reason,
            "close_source": close.source,
            "close_order_ids": list(close.order_ids),
        }
        self._add_close_audit(payload, close)
        return payload

    def _inflight_close_payload(
        self,
        outcome_id: str,
        inflight: EntryInflight,
        close: CloseFill,
    ) -> dict[str, object]:
        assert inflight.fill is not None and close.realized_pnl_usd is not None
        pnl = float(close.realized_pnl_usd)
        risk_usd = float(inflight.plan.initial_risk_usd)
        payload: dict[str, object] = {
            "outcome_id": outcome_id,
            "proposal_id": inflight.proposal_id,
            "profile": self.state.snapshot.profile,
            "market_environment": self.state.snapshot.market_environment,
            "symbol": inflight.plan.symbol,
            "side": inflight.plan.side,
            "entry_price": float(inflight.fill.price),
            "exit_price": float(close.price),
            "quantity": float(inflight.fill.quantity),
            "initial_risk_usd": risk_usd,
            "realized_pnl_usd": pnl,
            "r_multiple": pnl / risk_usd,
            "entry_timestamp_ms": int(inflight.fill.timestamp_ms),
            "closed_timestamp_ms": int(close.timestamp_ms),
            "entry_order_id": inflight.fill.order_id,
            "entry_client_order_id": inflight.fill.client_order_id,
            "entry_authority": inflight.entry_authority,
            "exit_policy_version": inflight.exit_policy_version,
            "exit_reason": close.reason,
            "close_source": close.source,
            "close_order_ids": list(close.order_ids),
            "recovered_from_entry_inflight": True,
        }
        self._add_close_audit(payload, close)
        return payload

    @staticmethod
    def _add_close_audit(payload: dict[str, object], close: CloseFill) -> None:
        if close.theoretical_pnl_usd is not None:
            payload["theoretical_pnl_usd"] = float(close.theoretical_pnl_usd)
        if close.pnl_variance_usd is not None:
            payload["pnl_variance_usd"] = float(close.pnl_variance_usd)

    def _deterministic_outcome_id(self, *, proposal_id: str, entry_fill: Fill) -> str:
        identity = "|".join(
            (
                self.state.snapshot.profile,
                self.state.snapshot.market_environment,
                proposal_id,
                entry_fill.order_id,
                entry_fill.client_order_id,
            )
        )
        digest = uuid.uuid5(uuid.NAMESPACE_URL, "nbot-v3-execution-outcome|" + identity).hex
        return f"OUT-{digest}"

    def _position_from_inflight(
        self,
        inflight: EntryInflight,
        stop_ref: ProtectiveStopRef,
    ) -> OpenPosition:
        assert inflight.fill is not None
        return OpenPosition(
            proposal_id=inflight.proposal_id,
            symbol=inflight.plan.symbol,
            side=inflight.plan.side,
            entry_fill=inflight.fill,
            initial_risk_usd=float(inflight.plan.initial_risk_usd),
            initial_stop_price=self._stop_for_fill(inflight),
            protective_stop=stop_ref,
            entry_authority=inflight.entry_authority,
            exit_policy_version=inflight.exit_policy_version,
        )

    @staticmethod
    def _stop_for_fill(inflight: EntryInflight) -> float:
        assert inflight.fill is not None
        quantity = float(inflight.fill.quantity)
        per_unit = float(inflight.plan.initial_risk_usd) / quantity
        stop = (
            float(inflight.fill.price) - per_unit
            if inflight.plan.side == "LONG"
            else float(inflight.fill.price) + per_unit
        )
        if not math.isfinite(stop) or stop <= 0:
            raise ReconciliationCritical("ENTRY_INFLIGHT_STOP_INVALID")
        return stop

    @staticmethod
    def _validate_inflight_fill(inflight: EntryInflight, fill: Fill) -> None:
        if fill.client_order_id != inflight.client_order_id:
            raise ReconciliationCritical("ENTRY_INFLIGHT_CLIENT_ORDER_ID_MISMATCH")

    @staticmethod
    def _assert_inflight_position_match(
        inflight: EntryInflight,
        exchange_position: ExchangePosition,
    ) -> None:
        assert inflight.fill is not None
        if exchange_position.symbol != inflight.plan.symbol:
            raise ReconciliationCritical("ENTRY_INFLIGHT_POSITION_SYMBOL_MISMATCH")
        if exchange_position.side != inflight.plan.side:
            raise ReconciliationCritical("ENTRY_INFLIGHT_POSITION_SIDE_MISMATCH")
        if not math.isclose(
            float(exchange_position.quantity),
            float(inflight.fill.quantity),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ReconciliationCritical("ENTRY_INFLIGHT_POSITION_QUANTITY_MISMATCH")
        if not exchange_entry_price_matches_fill(
            exchange_position.entry_price,
            inflight.fill.price,
        ):
            raise ReconciliationCritical("ENTRY_INFLIGHT_POSITION_ENTRY_PRICE_MISMATCH")

    @staticmethod
    def _assert_open_position_match(local: OpenPosition, exchange_position: ExchangePosition) -> None:
        if exchange_position.symbol != local.symbol:
            raise ReconciliationCritical("POSITION_SYMBOL_MISMATCH")
        if exchange_position.side != local.side:
            raise ReconciliationCritical("POSITION_SIDE_MISMATCH")
        if not math.isclose(
            float(exchange_position.quantity),
            float(local.quantity),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ReconciliationCritical("POSITION_QUANTITY_MISMATCH")
        if not exchange_entry_price_matches_fill(
            exchange_position.entry_price,
            local.entry_price,
        ):
            raise ReconciliationCritical("POSITION_ENTRY_PRICE_MISMATCH")

    @staticmethod
    def _stop_identity_matches(
        symbol: str,
        side: Side,
        quantity: float,
        stop_ref: ProtectiveStopRef,
    ) -> bool:
        return (
            stop_ref.symbol == symbol
            and stop_ref.side == side
            and math.isclose(float(stop_ref.quantity), float(quantity), rel_tol=1e-9, abs_tol=1e-12)
        )

    @staticmethod
    def _stop_is_looser(local: OpenPosition, stop_ref: ProtectiveStopRef) -> bool:
        observed = float(stop_ref.trigger_price)
        current = float(local.stop_price)
        if local.side == "LONG":
            return observed + 1e-12 < current
        return observed - 1e-12 > current

    @classmethod
    def _require_stop_protects(
        cls,
        symbol: str,
        side: Side,
        quantity: float,
        minimum_stop: float,
        stop_ref: ProtectiveStopRef,
    ) -> None:
        if not cls._stop_identity_matches(symbol, side, quantity, stop_ref):
            raise ReconciliationCritical("PROTECTIVE_STOP_IDENTITY_MISMATCH")
        observed = float(stop_ref.trigger_price)
        if side == "LONG" and observed + 1e-12 < float(minimum_stop):
            raise ReconciliationCritical("PROTECTIVE_STOP_RECOVERY_LOOSENED")
        if side == "SHORT" and observed - 1e-12 > float(minimum_stop):
            raise ReconciliationCritical("PROTECTIVE_STOP_RECOVERY_LOOSENED")

    def _verified_emergency(self, symbol: str, side: Side, *, reason: str) -> None:
        self._increment_health("emergency_exits", event=reason)
        try:
            self.emergency.flatten_verified(symbol, side, reason=reason)
        except Exception as exc:
            raise ReconciliationCritical(f"{reason}_EMERGENCY_FAILED") from exc
        # Verify once more at the reconciliation layer.  V3.1.7 will also verify
        # internally, but duplicate confirmation prevents a weak test double or
        # adapter regression from turning a request into false flatness.
        remaining = self._position_snapshot()
        if remaining is not None:
            raise ReconciliationCritical(f"{reason}_EMERGENCY_NOT_FLAT")

    def _roll_daily(self, now_ms: int) -> None:
        try:
            daily = self.risk.roll_daily(self.state.daily_risk, timestamp_ms=now_ms)
        except RiskRejected as exc:
            raise ReconciliationCritical("DAILY_RISK_ROLLOVER_FAILED") from exc
        if daily != self.state.daily_risk:
            try:
                self.state.set_daily_risk(daily)
            except ExecutionStateError as exc:
                raise ReconciliationCritical("DAILY_RISK_PERSIST_FAILED") from exc

    def _validated_now_ms(self) -> int:
        now = self._now_ms()
        if isinstance(now, bool) or not isinstance(now, int) or now <= 0:
            raise ReconciliationCritical("RECONCILIATION_TIME_INVALID")
        return now

    def _increment_health(self, counter: str, *, event: str) -> None:
        health = self.state.health
        if not hasattr(health, counter):
            raise ReconciliationCritical("EXECUTION_HEALTH_COUNTER_UNKNOWN")
        value = getattr(health, counter)
        updated = replace(health, **{counter: int(value) + 1, "last_event": event})
        try:
            self.state.set_health(updated)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("EXECUTION_HEALTH_PERSIST_FAILED") from exc

    def _set_health_event(self, event: str) -> None:
        health = replace(self.state.health, last_event=event)
        try:
            self.state.set_health(health)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("EXECUTION_HEALTH_PERSIST_FAILED") from exc

    def _record_recovery(self, now_ms: int, event: str, *, critical: bool) -> None:
        recovery = RecoveryMetadata(
            last_reconciliation_ms=now_ms,
            critical=critical,
            critical_reason=event if critical else None,
            last_event=event,
        )
        try:
            self.state.set_recovery(recovery)
        except ExecutionStateError as exc:
            raise ReconciliationCritical("RECOVERY_METADATA_PERSIST_FAILED") from exc

    def _fail_closed(self, now_ms: int, reason: str) -> None:
        # Best effort is intentionally ordered entries-off first.  If the state
        # store itself cannot persist, the raised error still prevents this
        # reconcile call from authorizing new work.
        try:
            self.state.set_entries_enabled(False)
        except Exception:
            pass
        try:
            self._record_recovery(now_ms, reason, critical=True)
        except Exception:
            pass
        try:
            self._set_health_event(reason)
        except Exception:
            pass
