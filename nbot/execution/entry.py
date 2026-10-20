"""Fail-closed V3.1.4 entry lifecycle.

This module orchestrates only the capital-entry boundary.  It consumes an
execution-local proposal, current Execution exchange truth, the V3 risk manager,
and the durable state store.  It has no Observation, strategy, research,
learning, or training dependency.

The future V3.5 wire protocol may adapt its validated proposal into
``EntryProposal``; this module intentionally does not define network semantics.
"""

from __future__ import annotations

from nbot.common.synchronization import state_transition

import hashlib
import math
import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from nbot.exchange.contracts import EntryNotSubmitted, ExchangePort, Fill, Side
from nbot.execution.models import EntryInflight, OpenPosition
from nbot.execution.risk import RiskManager, RiskRejected
from nbot.execution.state import ExecutionStateError, ExecutionStateStore

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,40}$")
_PROFILE_ENVIRONMENT = {
    "testnet-trade": "TESTNET",
    "live-paper": "LIVE",
    "live-trade": "LIVE",
}


class EntryRejected(RuntimeError):
    """Safe pre-order veto. No market entry request has been submitted."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class EntrySafetyError(RuntimeError):
    """Capital-safety failure after durable reservation/journaling may exist."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class VerifiedEmergencyPort(Protocol):
    """V3.1.7-compatible emergency boundary used after a proven fill.

    A concrete implementation may return only after exchange truth proves the
    requested capital position is flat.  Raising means flatness was not proven.
    """

    def flatten_verified(self, symbol: str, side: Side, *, reason: str) -> None: ...


def _text(name: str, value: object, *, max_length: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}_INVALID")
    if not value or value != value.strip() or len(value) > max_length:
        raise ValueError(f"{name}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name}_INVALID")
    return value


def _timestamp(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name}_INVALID")
    return value


def _positive(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name}_INVALID")
    return number


def _side(value: object) -> Side:
    if value not in {"LONG", "SHORT"}:
        raise ValueError("ENTRY_PROPOSAL_SIDE_INVALID")
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class EntryProposal:
    """Execution-local advisory proposal contract for V3.1 tests/canaries."""

    proposal_id: str
    generated_at_ms: int
    expires_at_ms: int
    profile: str
    market_environment: str
    symbol: str
    side: Side
    reference_price: float
    entry_authority: str
    exit_policy_version: str

    def __post_init__(self) -> None:
        _text("ENTRY_PROPOSAL_ID", self.proposal_id)
        generated = _timestamp("ENTRY_PROPOSAL_GENERATED_AT_MS", self.generated_at_ms)
        expires = _timestamp("ENTRY_PROPOSAL_EXPIRES_AT_MS", self.expires_at_ms)
        if expires <= generated:
            raise ValueError("ENTRY_PROPOSAL_EXPIRY_INVALID")
        if self.profile not in _PROFILE_ENVIRONMENT:
            raise ValueError("ENTRY_PROPOSAL_PROFILE_INVALID")
        if self.market_environment not in {"LIVE", "TESTNET"}:
            raise ValueError("ENTRY_PROPOSAL_ENVIRONMENT_INVALID")
        if not isinstance(self.symbol, str) or not _SYMBOL_RE.fullmatch(self.symbol):
            raise ValueError("ENTRY_PROPOSAL_SYMBOL_INVALID")
        _side(self.side)
        _positive("ENTRY_PROPOSAL_REFERENCE_PRICE", self.reference_price)
        _text("ENTRY_PROPOSAL_AUTHORITY", self.entry_authority)
        _text("ENTRY_PROPOSAL_EXIT_POLICY", self.exit_policy_version)


@dataclass(frozen=True, slots=True)
class EntryLifecycleConfig:
    """Release/profile authority boundary around the entry lifecycle."""

    profile: str
    market_environment: str
    allowed_entry_authorities: frozenset[str]
    allowed_exit_policies: frozenset[str]
    max_future_proposal_skew_ms: int = 5_000

    def __post_init__(self) -> None:
        expected = _PROFILE_ENVIRONMENT.get(self.profile)
        if expected is None:
            raise ValueError("ENTRY_CONFIG_PROFILE_INVALID")
        if self.market_environment != expected:
            raise ValueError("ENTRY_CONFIG_ENVIRONMENT_MISMATCH")
        if not isinstance(self.allowed_entry_authorities, frozenset) or not self.allowed_entry_authorities:
            raise ValueError("ENTRY_CONFIG_AUTHORITIES_INVALID")
        if not isinstance(self.allowed_exit_policies, frozenset) or not self.allowed_exit_policies:
            raise ValueError("ENTRY_CONFIG_POLICIES_INVALID")
        for authority in self.allowed_entry_authorities:
            _text("ENTRY_CONFIG_AUTHORITY", authority)
        for policy in self.allowed_exit_policies:
            _text("ENTRY_CONFIG_POLICY", policy)
        if (
            isinstance(self.max_future_proposal_skew_ms, bool)
            or not isinstance(self.max_future_proposal_skew_ms, int)
            or self.max_future_proposal_skew_ms < 0
        ):
            raise ValueError("ENTRY_CONFIG_FUTURE_SKEW_INVALID")


class EntryLifecycle:
    """One-shot safe entry orchestration for a flat Execution worker."""

    def __init__(
        self,
        *,
        exchange: ExchangePort,
        state: ExecutionStateStore,
        risk: RiskManager,
        emergency: VerifiedEmergencyPort,
        config: EntryLifecycleConfig,
        now_ms: Callable[[], int] | None = None,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.emergency = emergency
        self.config = config
        self._now_ms = now_ms
        if state.snapshot.profile != config.profile:
            raise ValueError("ENTRY_STATE_PROFILE_MISMATCH")
        if state.snapshot.market_environment != config.market_environment:
            raise ValueError("ENTRY_STATE_ENVIRONMENT_MISMATCH")

    @staticmethod
    def client_order_id(*, profile: str, market_environment: str, proposal_id: str) -> str:
        """Deterministic, compact identity for ambiguous-order recovery."""
        material = f"{profile}\0{market_environment}\0{proposal_id}".encode("utf-8")
        digest = hashlib.sha256(material).hexdigest()[:24]
        return f"NBV3E-{digest}"

    @state_transition
    def execute(self, proposal: EntryProposal, *, now_ms: int) -> OpenPosition:
        started = time.monotonic()
        def current_time() -> int:
            value = self._now_ms() if self._now_ms else now_ms + int((time.monotonic() - started) * 1000)
            return _timestamp("ENTRY_NOW_MS", value)
        if not isinstance(proposal, EntryProposal):
            raise EntryRejected("PROPOSAL_CONTRACT_INVALID")
        try:
            now = _timestamp("ENTRY_NOW_MS", now_ms)
        except ValueError as exc:
            raise EntryRejected("NOW_MS_INVALID") from exc

        self._validate_proposal_context(proposal, now_ms=now)
        self._validate_local_entry_gate(proposal, now_ms=now)

        try:
            healthy = self.exchange.is_healthy()
        except Exception as exc:
            raise EntryRejected("EXCHANGE_HEALTH_CHECK_FAILED") from exc
        if healthy is not True:
            raise EntryRejected("EXCHANGE_UNHEALTHY")

        try:
            exchange_position = self.exchange.position_snapshot()
        except Exception as exc:
            raise EntryRejected("EXCHANGE_POSITION_CHECK_FAILED") from exc
        if exchange_position is not None:
            raise EntryRejected("POSITION_ALREADY_OPEN")

        try:
            quote = self.exchange.quote(proposal.symbol)
        except Exception as exc:
            raise EntryRejected("QUOTE_UNAVAILABLE") from exc
        if quote.symbol != proposal.symbol:
            raise EntryRejected("QUOTE_SYMBOL_MISMATCH")
        try:
            self.risk.check_quote(quote, now_ms=current_time())
            entry_price = self.risk.entry_price(quote, proposal.side)
            self.risk.check_reference_drift(
                entry_price=entry_price,
                reference_price=proposal.reference_price,
            )
            plan = self.risk.build_entry_plan(
                symbol=proposal.symbol,
                side=proposal.side,
                entry_price=entry_price,
            )
        except RiskRejected as exc:
            raise EntryRejected(exc.reason) from exc

        try:
            account = self.exchange.account_snapshot()
        except Exception as exc:
            raise EntryRejected("ACCOUNT_UNAVAILABLE") from exc
        try:
            self.risk.check_account_margin(account, plan)
        except RiskRejected as exc:
            raise EntryRejected(exc.reason) from exc

        try:
            stop_feasible = self.exchange.validate_protective_stop(
                plan.symbol,
                plan.side,
                plan.initial_stop_price,
            )
        except Exception as exc:
            raise EntryRejected("PROTECTIVE_STOP_VALIDATION_FAILED") from exc
        if stop_feasible is not True:
            raise EntryRejected("PROTECTIVE_STOP_INFEASIBLE")

        try:
            self.exchange.set_leverage(plan.symbol, plan.leverage)
        except Exception as exc:
            raise EntryRejected("LEVERAGE_SET_FAILED") from exc

        now = current_time()
        self._validate_proposal_context(proposal, now_ms=now)
        self._validate_local_entry_gate(proposal, now_ms=now)
        try:
            final_quote = self.exchange.quote(proposal.symbol)
            if final_quote.symbol != proposal.symbol:
                raise EntryRejected("QUOTE_SYMBOL_MISMATCH")
            self.risk.check_quote(final_quote, now_ms=current_time())
            self.risk.check_reference_drift(
                entry_price=self.risk.entry_price(final_quote, proposal.side),
                reference_price=plan.expected_entry_price,
            )
        except RiskRejected as exc:
            raise EntryRejected(exc.reason) from exc

        # Durable duplicate reservation and complete recoverable entry identity
        # are written before the first market-order-capable call.
        try:
            if not self.state.reserve_proposal(proposal.proposal_id):
                raise EntryRejected("DUPLICATE_PROPOSAL")
        except EntryRejected:
            raise
        except ExecutionStateError as exc:
            raise EntrySafetyError("PROPOSAL_RESERVATION_FAILED") from exc

        client_order_id = self.client_order_id(
            profile=proposal.profile,
            market_environment=proposal.market_environment,
            proposal_id=proposal.proposal_id,
        )
        inflight = EntryInflight(
            proposal_id=proposal.proposal_id,
            entry_authority=proposal.entry_authority,
            exit_policy_version=proposal.exit_policy_version,
            plan=plan,
            client_order_id=client_order_id,
            started_at_ms=now,
        )
        try:
            self.state.begin_entry(inflight)
        except Exception as exc:
            raise EntrySafetyError("ENTRY_JOURNAL_PERSIST_FAILED") from exc

        try:
            self._validate_proposal_context(proposal, now_ms=current_time())
            self.risk.check_quote(final_quote, now_ms=current_time())
        except (EntryRejected, RiskRejected) as exc:
            self.state.clear_entry_inflight()  # No order-capable call has occurred.
            raise EntryRejected(exc.reason) from exc
        fill = self._submit_or_recover(plan, client_order_id=client_order_id)
        return self._protect_and_promote(proposal, fill=fill)

    def _validate_proposal_context(self, proposal: EntryProposal, *, now_ms: int) -> None:
        if proposal.profile != self.config.profile:
            raise EntryRejected("PROFILE_MISMATCH")
        if proposal.market_environment != self.config.market_environment:
            raise EntryRejected("ENVIRONMENT_MISMATCH")
        if proposal.generated_at_ms > now_ms + self.config.max_future_proposal_skew_ms:
            raise EntryRejected("FUTURE_TIMESTAMP")
        if now_ms >= proposal.expires_at_ms:
            raise EntryRejected("EXPIRED")
        if proposal.entry_authority not in self.config.allowed_entry_authorities:
            raise EntryRejected("ENTRY_AUTHORITY_NOT_APPROVED")
        if proposal.exit_policy_version not in self.config.allowed_exit_policies:
            raise EntryRejected("EXIT_POLICY_NOT_APPROVED")

    def _validate_local_entry_gate(self, proposal: EntryProposal, *, now_ms: int) -> None:
        if not self.state.snapshot.entries_enabled:
            raise EntryRejected("ENTRY_DISABLED")
        if self.state.has_processed_proposal(proposal.proposal_id):
            raise EntryRejected("DUPLICATE_PROPOSAL")
        try:
            self.risk.check_entry_capacity(
                open_position=self.state.open_position,
                entry_inflight=self.state.entry_inflight,
            )
        except RiskRejected as exc:
            raise EntryRejected(exc.reason) from exc

        # Daily risk is rolled and persisted before any capital-bearing call.
        try:
            daily = self.risk.roll_daily(self.state.daily_risk, timestamp_ms=now_ms)
        except RiskRejected as exc:
            raise EntryRejected(exc.reason) from exc
        if daily != self.state.daily_risk:
            try:
                self.state.set_daily_risk(daily)
            except ExecutionStateError as exc:
                raise EntrySafetyError("DAILY_RISK_PERSIST_FAILED") from exc
        if daily.halted:
            raise EntryRejected(daily.halt_reason or "DAILY_HALT")

    def _submit_or_recover(self, plan, *, client_order_id: str) -> Fill:
        try:
            fill = self.exchange.open_market(plan, client_order_id=client_order_id)
        except EntryNotSubmitted as open_error:
            # The adapter has proven that no capital-bearing market-order write
            # was attempted. The durable journal can therefore be cleared
            # without ambiguous-order recovery. The proposal reservation stays
            # durable so the same proposal can never be retried as a new entry.
            try:
                self.state.clear_entry_inflight()
            except ExecutionStateError as exc:
                raise EntrySafetyError("ENTRY_NOT_SUBMITTED_CLEAR_FAILED") from exc
            raise EntryRejected(open_error.reason) from open_error
        except Exception as open_error:
            # Never issue a second market order. Query the exact durable client
            # identity through the adapter's recovery boundary.
            try:
                recovered = self.exchange.recover_inflight_entry(
                    plan,
                    client_order_id=client_order_id,
                )
            except Exception as recovery_error:
                raise EntrySafetyError("ENTRY_AMBIGUOUS_RECOVERY_FAILED") from recovery_error
            if recovered is None:
                # None is not enough evidence here to erase the journal. V3.1.6
                # reconciliation will decide whether the exact order was absent,
                # filled, or closed while Execution was unavailable.
                raise EntrySafetyError("ENTRY_OUTCOME_UNRESOLVED") from open_error
            fill = recovered

        if fill.client_order_id != client_order_id:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason="ENTRY_FILL_IDENTITY_MISMATCH",
            )

        try:
            self.state.record_inflight_fill(fill)
        except Exception as exc:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason="ENTRY_FILL_PERSIST_FAILED",
                cause=exc,
            )
        return fill

    def _protect_and_promote(self, proposal: EntryProposal, *, fill: Fill) -> OpenPosition:
        inflight = self.state.entry_inflight
        if inflight is None or inflight.fill is None:
            self._emergency_after_fill(
                proposal.symbol,
                proposal.side,
                reason="ENTRY_FILL_JOURNAL_MISSING",
            )
        assert inflight is not None  # narrowed by emergency path above
        plan = inflight.plan
        actual_stop = self._stop_for_fill(
            side=plan.side,
            price=float(fill.price),
            quantity=float(fill.quantity),
            risk_usd=float(plan.initial_risk_usd),
        )

        try:
            stop_ref = self.exchange.ensure_protective_stop(
                plan.symbol,
                plan.side,
                float(fill.quantity),
                actual_stop,
            )
        except Exception as exc:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason="PROTECTION_FAILED",
                cause=exc,
            )
            raise AssertionError("unreachable")

        try:
            verified = self.exchange.validate_protective_stop(
                plan.symbol,
                plan.side,
                float(stop_ref.trigger_price),
            )
        except Exception as exc:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason="PROTECTION_VERIFICATION_FAILED",
                cause=exc,
            )
            raise AssertionError("unreachable")
        if verified is not True:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason="PROTECTION_NOT_VERIFIED",
            )

        violation = self.risk.post_fill_violation(
            plan=plan,
            fill=fill,
            stop_ref=stop_ref,
        )
        if violation is not None:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason=violation,
            )

        try:
            position = OpenPosition(
                proposal_id=proposal.proposal_id,
                symbol=plan.symbol,
                side=plan.side,
                entry_fill=fill,
                initial_risk_usd=float(plan.initial_risk_usd),
                initial_stop_price=actual_stop,
                protective_stop=stop_ref,
                entry_authority=proposal.entry_authority,
                exit_policy_version=proposal.exit_policy_version,
            )
            self.state.promote_inflight_position(position)
        except Exception as exc:
            self._emergency_after_fill(
                plan.symbol,
                plan.side,
                reason="OPEN_POSITION_PERSIST_FAILED",
                cause=exc,
            )
            raise AssertionError("unreachable")
        return position

    def _emergency_after_fill(
        self,
        symbol: str,
        side: Side,
        *,
        reason: str,
        cause: Exception | None = None,
    ) -> None:
        """Verified flatten after a confirmed/recovered fill.

        The durable inflight journal is deliberately preserved even after a
        confirmed flatten.  V3.1.6 reconciliation can then recover authoritative
        close/accounting evidence instead of losing the entry record.
        """
        try:
            self.emergency.flatten_verified(symbol, side, reason=reason)
        except Exception as emergency_error:
            raise EntrySafetyError(f"{reason}_EMERGENCY_FAILED") from emergency_error
        error = EntrySafetyError(f"{reason}_EMERGENCY_FLAT")
        if cause is None:
            raise error
        raise error from cause

    @staticmethod
    def _stop_for_fill(*, side: Side, price: float, quantity: float, risk_usd: float) -> float:
        if not math.isfinite(price) or price <= 0 or not math.isfinite(quantity) or quantity <= 0:
            raise EntrySafetyError("ENTRY_FILL_INVALID")
        risk = float(risk_usd)
        if not math.isfinite(risk) or risk <= 0:
            raise EntrySafetyError("ENTRY_RISK_INVALID")
        per_unit = risk / quantity
        stop = price - per_unit if side == "LONG" else price + per_unit
        if not math.isfinite(stop) or stop <= 0:
            raise EntrySafetyError("ENTRY_CORRECTED_STOP_INVALID")
        return stop
