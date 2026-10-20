"""Capital-first NBOT V3.1 Execution Worker orchestration.

This module deliberately contains no Observation, strategy, research, learning,
or training imports.  It composes the already-proven V3.1 capital components
behind small transport-neutral ProposalClient and OutcomeClient interfaces.

Safety ordering:

* startup/flat-side work reconciles exchange truth before any proposal request;
* durable pending outcomes are ACKed before another proposal is requested;
* an OPEN position is managed without ProposalClient/OutcomeClient calls;
* PaperExchange receives the same Execution-owned quote before position
  management so local stop settlement follows bid/ask truth;
* reconciliation ambiguity/failure remains fail-closed and propagates.
"""

from __future__ import annotations

from nbot.common.synchronization import state_transition

import time
from dataclasses import replace
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from nbot.exchange.contracts import ExchangePort, Quote
from nbot.execution.entry import EntryLifecycle, EntryProposal, EntryRejected
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.position import (
    PositionLifecycle,
    PositionManageResult,
    PositionReconciliationRequired,
)
from nbot.execution.reconciliation import ReconciliationLifecycle, ReconciliationResult
from nbot.execution.risk import RiskManager, RiskRejected


class ExecutionWorkerError(RuntimeError):
    """Execution orchestration invariant or durable-delivery failure."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@runtime_checkable
class ProposalClient(Protocol):
    """Transport-neutral V3.1 proposal source.

    V3.5 will replace the local/synthetic implementation with the real remote
    protocol client.  Returning ``None`` means no currently usable proposal.
    Raising means the source is unavailable; Execution stays flat.
    """

    def request_proposal(
        self,
        *,
        profile: str,
        market_environment: str,
        execution_instance_id: str,
        requested_at_ms: int,
    ) -> EntryProposal | None: ...


@runtime_checkable
class OutcomeClient(Protocol):
    """Transport-neutral durable outcome delivery boundary.

    The client must return the exact ``outcome_id`` it durably ACKed.  Any
    missing/mismatched acknowledgement leaves the local outbox record intact.
    """

    def send_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> str: ...


class ExecutionWorker:
    """Compose V3.1 execution components into one capital-first state machine."""

    def __init__(
        self,
        *,
        exchange: ExchangePort,
        durable: ExecutionDurableStore,
        risk: RiskManager,
        entry: EntryLifecycle,
        position: PositionLifecycle,
        reconciliation: ReconciliationLifecycle,
        proposal_client: ProposalClient | None = None,
        outcome_client: OutcomeClient | None = None,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.exchange = exchange
        self.durable = durable
        self.state = durable.state
        self.risk = risk
        self.entry = entry
        self.position = position
        self.reconciliation = reconciliation
        self.proposal_client = proposal_client
        self.outcome_client = outcome_client
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._prepared = False
        self._quote_times: dict[str, int] = {}

        # Prevent accidentally composing lifecycles against different capital
        # stores/exchange objects.  One worker must have one canonical truth.
        if entry.state is not self.state or position.state is not self.state or reconciliation.state is not self.state:
            raise ValueError("EXECUTION_WORKER_STATE_IDENTITY_MISMATCH")
        if entry.exchange is not exchange or position.exchange is not exchange or reconciliation.exchange is not exchange:
            raise ValueError("EXECUTION_WORKER_EXCHANGE_IDENTITY_MISMATCH")
        if entry.risk is not risk or position.risk is not risk or reconciliation.risk is not risk:
            raise ValueError("EXECUTION_WORKER_RISK_IDENTITY_MISMATCH")

    @property
    def prepared(self) -> bool:
        return self._prepared

    @state_transition
    def prepare(self) -> ReconciliationResult:
        """Capital-first startup preparation; never contacts remote clients."""
        try:
            # Testnet connect acquires the process lock. PAPER callers hold
            # their runtime lock around prepare. A pre-lock snapshot may be old.
            self.exchange.connect()
            self.state.reload_after_runtime_lock()
            self._health_event("EXECUTION_PREPARE_STARTED", counter="prepare_calls")
            result = self.reconciliation.reconcile()
        except Exception:
            self._prepared = False
            raise
        self._prepared = True
        self._health_event(f"EXECUTION_PREPARED_{result.status}")
        return result

    @state_transition
    def enable_new_entries(self) -> ReconciliationResult:
        """Reconcile and pass current daily risk before opening the entry gate."""
        result = self._reconcile_now()
        now = self._validated_now_ms()
        try:
            daily = self.risk.check_daily_entry(self.state.daily_risk, now_ms=now)
        except RiskRejected as exc:
            self._health_event(f"ENTRY_ENABLE_BLOCKED_{exc.reason}")
            raise ExecutionWorkerError(exc.reason) from exc
        if daily != self.state.daily_risk:
            self.state.set_daily_risk(daily)
        self.state.set_entries_enabled(True)
        self._health_event("EXECUTION_NEW_ENTRIES_ENABLED")
        return result

    @state_transition
    def disable_new_entries(self) -> None:
        """Disable future entries without disturbing an already-open position."""
        self.state.set_entries_enabled(False)
        self._health_event("EXECUTION_NEW_ENTRIES_DISABLED")

    @state_transition
    def force_close_open_position(self, *, reason: str) -> ReconciliationResult:
        """Verified operator close followed by authoritative reconciliation.

        This is deliberately capital-only.  It disables new entries first, uses
        the same verified-flat emergency boundary as safety handling, and then
        requires reconciliation to recover authoritative close accounting.
        Returning never means that a close request alone was trusted.
        """
        if not isinstance(reason, str) or not reason or reason != reason.strip():
            raise ExecutionWorkerError("FORCE_CLOSE_REASON_INVALID")
        if not self._prepared:
            self.prepare()
        self.disable_new_entries()
        local = self.state.open_position
        if local is None:
            return ReconciliationResult(status="FLAT")
        try:
            self.position.emergency.flatten_verified(local.symbol, local.side, reason=reason)
        except Exception as exc:
            self._health_event("FORCE_CLOSE_FAILED")
            raise ExecutionWorkerError("FORCE_CLOSE_FAILED") from exc
        result = self._reconcile_now()
        if self.state.open_position is not None or self.state.entry_inflight is not None:
            self._health_event("FORCE_CLOSE_RECONCILIATION_NOT_FLAT")
            raise ExecutionWorkerError("FORCE_CLOSE_RECONCILIATION_NOT_FLAT")
        self._health_event("FORCE_CLOSE_CONFIRMED_FLAT")
        return result

    @state_transition
    def process_flat_cycle(self) -> str:
        """Perform one flat-side cycle in strict capital-first order.

        Exchange reconciliation runs before any proposal request.  A durable
        pending outcome blocks the next proposal until exact ACK identity is
        returned and the local outbox file is safely removed.
        """
        self._health_event("FLAT_CYCLE_STARTED", counter="flat_cycles")
        result = self._reconcile_now()
        if self.state.open_position is not None:
            self._health_event("POSITION_OPEN")
            return "POSITION_OPEN"
        if self.state.entry_inflight is not None:
            # Successful reconciliation is not allowed to leave ambiguous
            # inflight capital state and then request another proposal.
            raise ExecutionWorkerError("ENTRY_INFLIGHT_REMAINS_AFTER_RECONCILIATION")

        if not self._deliver_pending_outcomes():
            self._health_event("PENDING_OUTCOME")
            return "PENDING_OUTCOME"

        if not self.state.snapshot.entries_enabled:
            self._health_event("ENTRY_DISABLED")
            return "ENTRY_DISABLED"

        now = self._validated_now_ms()
        try:
            daily = self.risk.check_daily_entry(self.state.daily_risk, now_ms=now)
        except RiskRejected as exc:
            self._health_event(f"DAILY_BLOCKED_{exc.reason}")
            return "DAILY_BLOCKED"
        if daily != self.state.daily_risk:
            self.state.set_daily_risk(daily)

        if self.proposal_client is None:
            self._health_event("PROPOSAL_UNAVAILABLE")
            return "PROPOSAL_UNAVAILABLE"

        try:
            proposal = self.proposal_client.request_proposal(
                profile=self.state.snapshot.profile,
                market_environment=self.state.snapshot.market_environment,
                execution_instance_id=self.state.snapshot.execution_instance_id,
                requested_at_ms=now,
            )
        except Exception:
            self._health_event("PROPOSAL_UNAVAILABLE")
            return "PROPOSAL_UNAVAILABLE"

        if proposal is None:
            self._health_event("NO_TRADE")
            return "NO_TRADE"

        try:
            self.entry.execute(proposal, now_ms=self._validated_now_ms())
        except EntryRejected as exc:
            self._health_event(
                f"PROPOSAL_REJECTED_{exc.reason}",
                counter="proposal_rejections",
            )
            # V3.5 transport adapters may expose a local durable veto-feedback
            # hook.  It must never turn a rejected proposal into an entry and
            # is deliberately not part of the OPEN-position hot path.
            feedback = getattr(self.proposal_client, "record_veto", None)
            if callable(feedback):
                try:
                    feedback(
                        proposal_id=proposal.proposal_id,
                        reason=exc.reason,
                        rejected_at_ms=now,
                    )
                except Exception:
                    self._health_event("PROPOSAL_VETO_FEEDBACK_FAILED")
            return f"PROPOSAL_REJECTED:{exc.reason}"

        if self.state.open_position is None or self.state.entry_inflight is not None:
            raise ExecutionWorkerError("ENTRY_RETURNED_WITHOUT_OPEN_STATE")
        self._health_event("ENTRY_OPENED")
        return "ENTRY_OPENED"

    @state_transition
    def process_open_quote(self, quote: Quote) -> PositionManageResult | ReconciliationResult:
        """Process one Execution-owned quote for the capital-bearing position.

        This hot path never calls ProposalClient or OutcomeClient.  When the
        position lifecycle detects exchange-close/stop ambiguity, reconciliation
        resolves it locally; any resulting outcome stays durable in the outbox
        until a later FLAT cycle.
        """
        if not isinstance(quote, Quote):
            raise ExecutionWorkerError("EXECUTION_QUOTE_CONTRACT_INVALID")
        if not self._prepared:
            self.prepare()

        local = self.state.open_position
        if local is None:
            return PositionManageResult(status="FLAT")
        if quote.symbol != local.symbol:
            return PositionManageResult(status="IGNORED_OTHER_SYMBOL", symbol=local.symbol)

        now = self._validated_now_ms()
        try:
            self.risk.check_quote(quote, now_ms=now)
        except RiskRejected as exc:
            self._health_event(f"OPEN_QUOTE_REJECTED_{exc.reason}")
            # Reconcile exchange protection; never simulate a stale paper fill.
            return self._reconcile_now()
        previous = self._quote_times.get(quote.symbol, local.entry_timestamp_ms)
        if quote.timestamp_ms < previous:
            self._health_event("OPEN_QUOTE_OUT_OF_ORDER")
            return PositionManageResult(status="IGNORED_OUT_OF_ORDER", symbol=local.symbol)
        self._quote_times[quote.symbol] = quote.timestamp_ms

        paper_tick = getattr(self.exchange, "on_market_tick", None)
        if callable(paper_tick):
            try:
                paper_tick(
                    symbol=quote.symbol,
                    bid=quote.bid,
                    ask=quote.ask,
                    timestamp_ms=quote.timestamp_ms,
                )
            except Exception as exc:
                raise ExecutionWorkerError("EXCHANGE_MARKET_TICK_FAILED") from exc

        try:
            return self.position.manage_tick(
                quote.symbol,
                quote.mid,
                quote.timestamp_ms,
            )
        except PositionReconciliationRequired:
            # Reconciliation is execution-local.  Do not deliver a newly-created
            # outcome from this OPEN tick; that is intentionally deferred to the
            # next flat cycle so Observation/network failure cannot enter the
            # capital hot path.
            return self._reconcile_now()

    @state_transition
    def reconcile(self) -> ReconciliationResult:
        """Explicit execution-only reconciliation with no proposal/outcome I/O."""
        return self._reconcile_now()

    def _reconcile_now(self) -> ReconciliationResult:
        try:
            result = self.reconciliation.reconcile()
        except Exception:
            self._prepared = False
            raise
        self._prepared = True
        return result

    def _deliver_pending_outcomes(self) -> bool:
        pending = self.durable.outbox.pending()
        if not pending:
            return True
        if self.outcome_client is None:
            return False

        for row in pending:
            outcome_id = row["record_id"]
            payload = row["payload"]
            try:
                ack = self.outcome_client.send_outcome(
                    outcome_id=outcome_id,
                    payload=payload,
                )
            except Exception:
                return False
            if ack != outcome_id:
                return False
            if not self.durable.outbox.acknowledge(outcome_id):
                raise ExecutionWorkerError("OUTCOME_ACK_LOCAL_RECORD_MISSING")
        return True

    def _validated_now_ms(self) -> int:
        value = self._now_ms()
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ExecutionWorkerError("EXECUTION_NOW_MS_INVALID")
        return value

    def _health_event(self, event: str, *, counter: str | None = None) -> None:
        health = self.state.health
        changes: dict[str, object] = {"last_event": event}
        if counter is not None:
            if counter not in {
                "prepare_calls",
                "flat_cycles",
                "proposal_rejections",
            }:
                raise ExecutionWorkerError("EXECUTION_HEALTH_COUNTER_INVALID")
            changes[counter] = getattr(health, counter) + 1
        self.state.set_health(replace(health, **changes))
