"""Standalone Binance Testnet mechanical-canary helpers for NBOT V3.2.

This module is deliberately execution-only.  It provides a one-shot manual
proposal source and a local outcome sink so V3 Execution mechanics can be
physically exercised before Observation V3 or the V3.5 communication protocol
exists.

Nothing here is research authority.  Every proposal and locally ACKed outcome
is explicitly bound to ``TESTNET_MECHANICAL_ONLY``.
"""

from __future__ import annotations

import resource
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from nbot.common.ids import new_id
from nbot.exchange.binance_testnet import BinanceTestnetExchange, TestnetExchangeConfig
from nbot.exchange.contracts import Quote, Side
from nbot.execution.emergency import EmergencyFlattener
from nbot.execution.entry import EntryLifecycle, EntryProposal, EntryRejected
from nbot.execution.outcomes import ExecutionHistoryStore
from nbot.execution.position import INTEGER_R_STEP_CONTROL
from nbot.execution.reconciliation import ReconciliationLifecycle

TESTNET_MECHANICAL_AUTHORITY = "TESTNET_MECHANICAL_ONLY"
TESTNET_MECHANICAL_EVIDENCE_CLASS = "TESTNET_MECHANICAL_ONLY"
TESTNET_MECHANICAL_PROFILE = "testnet-trade"
TESTNET_MECHANICAL_ENVIRONMENT = "TESTNET"
TESTNET_MECHANICAL_PROPOSAL_TTL_MS = 30_000


class MechanicalCanaryError(RuntimeError):
    """The standalone V3.2 canary boundary was used unsafely."""


class MechanicalCanaryTelemetry:
    """Best-effort operational telemetry for one standalone V3.2 action.

    Telemetry is deliberately segregated from execution outcomes and research
    evidence.  A telemetry write failure never interrupts capital management;
    the in-memory ``write_failures`` counter makes that degradation visible.
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        action: str,
        run_id: str | None = None,
        monotonic: Callable[[], float] = time.perf_counter,
        process_time: Callable[[], float] = time.process_time,
    ) -> None:
        if not isinstance(action, str) or not action or action != action.strip():
            raise MechanicalCanaryError("TESTNET_MECHANICAL_TELEMETRY_ACTION_INVALID")
        self.action = action
        self.run_id = run_id or new_id("TESTNET_TLM")
        self._monotonic = monotonic
        self._process_time = process_time
        self._last_wall = float(monotonic())
        self._last_cpu = float(process_time())
        self._store = ExecutionHistoryStore(mechanical_telemetry_path(repo_root, self.run_id))
        self._latency_last: dict[str, float] = {}
        self._latency_max: dict[str, float] = {}
        self._counters: dict[str, int] = {}
        self.max_cpu_percent = 0.0
        self.max_rss_mb = 0.0
        self.write_failures = 0
        self._finished = False
        self.record("RUN_STARTED")
        self.sample_resources()

    @property
    def path(self) -> Path:
        return self._store.path

    @property
    def finished(self) -> bool:
        return self._finished

    def _safe_append(self, event: str, payload: Mapping[str, Any]) -> None:
        row = {
            "telemetry_id": new_id("TLM_EVENT"),
            "run_id": self.run_id,
            "action": self.action,
            "event": event,
            "recorded_at_ms": int(time.time() * 1000),
            "authority": TESTNET_MECHANICAL_AUTHORITY,
            "evidence_class": TESTNET_MECHANICAL_EVIDENCE_CLASS,
            "research_evidence": False,
            **dict(payload),
        }
        try:
            self._store.append(row["telemetry_id"], row)
        except Exception:
            # Operator visibility must never interfere with protection/flattening.
            self.write_failures += 1

    def record(self, event: str, **fields: Any) -> None:
        if not isinstance(event, str) or not event or event != event.strip():
            raise MechanicalCanaryError("TESTNET_MECHANICAL_TELEMETRY_EVENT_INVALID")
        self._safe_append(event, fields)

    def increment(self, name: str, amount: int = 1, **fields: Any) -> None:
        if not isinstance(name, str) or not name or name != name.strip():
            raise MechanicalCanaryError("TESTNET_MECHANICAL_TELEMETRY_COUNTER_INVALID")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_TELEMETRY_COUNTER_INVALID")
        self._counters[name] = self._counters.get(name, 0) + amount
        self.record("COUNTER", counter=name, value=self._counters[name], **fields)

    def observe_latency(self, name: str, elapsed_ms: float, *, status: str, **fields: Any) -> None:
        value = float(elapsed_ms)
        if value < 0:
            value = 0.0
        self._latency_last[name] = value
        self._latency_max[name] = max(self._latency_max.get(name, 0.0), value)
        self.record(
            "LATENCY",
            metric=name,
            elapsed_ms=value,
            max_ms=self._latency_max[name],
            status=status,
            **fields,
        )

    def timed_call(self, name: str, call: Callable[[], Any], **fields: Any) -> Any:
        started = float(self._monotonic())
        try:
            result = call()
        except Exception as exc:
            elapsed = (float(self._monotonic()) - started) * 1000.0
            self.observe_latency(
                name, elapsed, status="ERROR", error=f"{type(exc).__name__}:{exc}", **fields
            )
            raise
        elapsed = (float(self._monotonic()) - started) * 1000.0
        self.observe_latency(name, elapsed, status="PASS", **fields)
        return result

    def sample_resources(self) -> dict[str, float]:
        now_wall = float(self._monotonic())
        now_cpu = float(self._process_time())
        wall_delta = max(0.0, now_wall - self._last_wall)
        cpu_delta = max(0.0, now_cpu - self._last_cpu)
        cpu_pct = 0.0 if wall_delta <= 0 else (cpu_delta / wall_delta) * 100.0
        rss_raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB.  V3 Execution VPS is Ubuntu; retain a simple
        # fallback for platforms that report bytes.
        rss_mb = rss_raw / (1024.0 * 1024.0) if rss_raw > 10_000_000 else rss_raw / 1024.0
        self.max_cpu_percent = max(self.max_cpu_percent, cpu_pct)
        self.max_rss_mb = max(self.max_rss_mb, rss_mb)
        self._last_wall = now_wall
        self._last_cpu = now_cpu
        self.record(
            "RESOURCE_SAMPLE",
            cpu_percent=cpu_pct,
            rss_mb=rss_mb,
            max_cpu_percent=self.max_cpu_percent,
            max_rss_mb=self.max_rss_mb,
        )
        return {"cpu_percent": cpu_pct, "rss_mb": rss_mb}

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "action": self.action,
            "authority": TESTNET_MECHANICAL_AUTHORITY,
            "evidence_class": TESTNET_MECHANICAL_EVIDENCE_CLASS,
            "research_evidence": False,
            "latency_last_ms": dict(sorted(self._latency_last.items())),
            "latency_max_ms": dict(sorted(self._latency_max.items())),
            "counters": dict(sorted(self._counters.items())),
            "max_cpu_percent": self.max_cpu_percent,
            "max_rss_mb": self.max_rss_mb,
            "write_failures": self.write_failures,
            "telemetry_file": str(self.path),
        }

    def finish(self, status: str) -> dict[str, Any]:
        if not self._finished:
            self.sample_resources()
            self.record("RUN_FINISHED", status=status, summary=self.summary())
            self._finished = True
        return self.summary()


class MechanicalCanaryTestnetExchange(BinanceTestnetExchange):
    """Binance Testnet adapter with V3.2 operational-only timing hooks."""

    def __init__(self, config: TestnetExchangeConfig, telemetry: MechanicalCanaryTelemetry):
        super().__init__(config)
        self.telemetry = telemetry
        self._initial_stop_depth = 0

    def open_market(self, plan, *, client_order_id: str):
        return self.telemetry.timed_call(
            "order_request_fill_ms",
            lambda: super(MechanicalCanaryTestnetExchange, self).open_market(
                plan, client_order_id=client_order_id
            ),
            symbol=plan.symbol,
            side=plan.side,
        )

    def recover_inflight_entry(self, plan, *, client_order_id: str):
        self.telemetry.increment("recovery_attempts", recovery_type="ENTRY_INFLIGHT")
        try:
            result = super().recover_inflight_entry(plan, client_order_id=client_order_id)
        except Exception:
            self.telemetry.increment("recovery_failures", recovery_type="ENTRY_INFLIGHT")
            raise
        self.telemetry.increment("recovery_results", recovery_type="ENTRY_INFLIGHT")
        return result

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        self._initial_stop_depth += 1
        try:
            return self.telemetry.timed_call(
                "initial_stop_place_verify_ms",
                lambda: super(MechanicalCanaryTestnetExchange, self).ensure_protective_stop(
                    symbol, side, quantity, stop_price
                ),
                symbol=symbol,
                side=side,
            )
        finally:
            self._initial_stop_depth -= 1

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        if self._initial_stop_depth:
            return super().replace_protective_stop(symbol, side, quantity, stop_price)
        return self.telemetry.timed_call(
            "stop_replacement_ms",
            lambda: super(MechanicalCanaryTestnetExchange, self).replace_protective_stop(
                symbol, side, quantity, stop_price
            ),
            symbol=symbol,
            side=side,
        )

    def _best_effort_active_stop_count(self, symbol: str) -> int | None:
        try:
            return len(self._active_stops(symbol))
        except Exception as exc:
            self.telemetry.record(
                "TELEMETRY_PROBE_FAILED",
                probe="active_stop_count",
                symbol=symbol,
                error=str(exc),
            )
            return None

    def _record_recovery_stop_prune(
        self,
        symbol: str,
        before: int | None,
        *,
        recovery_type: str,
    ) -> None:
        if before is None:
            return
        after = self._best_effort_active_stop_count(symbol)
        if after is None or after >= before:
            return
        removed = before - after
        self.telemetry.increment(
            "orphan_stops_removed",
            removed,
            recovery_type=recovery_type,
            removal_path="CLOSE_RECOVERY",
        )

    def recover_closed_position(self, local_position):
        recovery_type = "CLOSED_POSITION"
        before_stops = self._best_effort_active_stop_count(local_position.symbol)
        self.telemetry.increment("recovery_attempts", recovery_type=recovery_type)
        try:
            result = super().recover_closed_position(local_position)
        except Exception:
            self.telemetry.increment("recovery_failures", recovery_type=recovery_type)
            raise
        self.telemetry.increment("recovery_results", recovery_type=recovery_type)
        self._record_recovery_stop_prune(
            local_position.symbol, before_stops, recovery_type=recovery_type
        )
        return result

    def recover_closed_inflight_entry(self, inflight):
        recovery_type = "CLOSED_INFLIGHT"
        symbol = inflight.plan.symbol
        before_stops = self._best_effort_active_stop_count(symbol)
        self.telemetry.increment("recovery_attempts", recovery_type=recovery_type)
        try:
            result = super().recover_closed_inflight_entry(inflight)
        except Exception:
            self.telemetry.increment("recovery_failures", recovery_type=recovery_type)
            raise
        self.telemetry.increment("recovery_results", recovery_type=recovery_type)
        self._record_recovery_stop_prune(symbol, before_stops, recovery_type=recovery_type)
        return result

    def cleanup_orphan_protective_stops(self) -> int:
        result = super().cleanup_orphan_protective_stops()
        if result:
            self.telemetry.increment("orphan_stops_removed", result)
        return result

    def close_position(self, symbol, side, *, reason: str):
        event = (
            "operator_force_close_attempts"
            if reason == "OPERATOR_TESTNET_FORCE_CLOSE"
            else "emergency_close_attempts"
        )
        self.telemetry.increment(event, symbol=symbol, side=side, reason=reason)
        return self.telemetry.timed_call(
            "close_request_settlement_ms",
            lambda: super(MechanicalCanaryTestnetExchange, self).close_position(
                symbol, side, reason=reason
            ),
            symbol=symbol,
            side=side,
            reason=reason,
        )


class MechanicalCanaryEmergencyFlattener(EmergencyFlattener):
    """Verified flattener that reports attempts/results without changing safety."""

    def __init__(self, *, telemetry: MechanicalCanaryTelemetry, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.telemetry = telemetry

    def flatten_verified(self, symbol: str, side: Side, *, reason: str) -> None:
        operator = reason == "OPERATOR_TESTNET_FORCE_CLOSE"
        prefix = "OPERATOR_FORCE_CLOSE" if operator else "EMERGENCY"
        self.telemetry.increment(f"{prefix.lower()}_requests", symbol=symbol, side=side, reason=reason)
        try:
            super().flatten_verified(symbol, side, reason=reason)
        except Exception as exc:
            self.telemetry.increment(f"{prefix.lower()}_failures", error=f"{type(exc).__name__}:{exc}")
            self.telemetry.record(f"{prefix}_RESULT", status="FAIL", reason=reason)
            raise
        self.telemetry.increment(f"{prefix.lower()}_successes")
        self.telemetry.record(f"{prefix}_RESULT", status="PASS", reason=reason)


class MechanicalCanaryEntryLifecycle(EntryLifecycle):
    """EntryLifecycle that exposes duplicate prevention to V3.2 telemetry."""

    def __init__(self, *, telemetry: MechanicalCanaryTelemetry, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.telemetry = telemetry

    def execute(self, proposal: EntryProposal, *, now_ms: int):
        try:
            return super().execute(proposal, now_ms=now_ms)
        except EntryRejected as exc:
            if exc.reason == "DUPLICATE_PROPOSAL":
                self.telemetry.increment("duplicate_preventions", proposal_id=proposal.proposal_id)
            raise


class MechanicalCanaryReconciliationLifecycle(ReconciliationLifecycle):
    """ReconciliationLifecycle with exact wall-clock and recovery telemetry."""

    def __init__(self, *, telemetry: MechanicalCanaryTelemetry, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.telemetry = telemetry

    def reconcile(self):
        started = float(self._monotonic())
        try:
            result = super().reconcile()
        except Exception as exc:
            self.telemetry.observe_latency(
                "reconciliation_ms",
                (float(self._monotonic()) - started) * 1000.0,
                status="ERROR",
                error=f"{type(exc).__name__}:{exc}",
            )
            self.telemetry.increment("reconciliation_failures")
            raise
        self.telemetry.observe_latency(
            "reconciliation_ms",
            (float(self._monotonic()) - started) * 1000.0,
            status="PASS",
            result=result.status,
        )
        if result.status not in {"FLAT", "POSITION_OPEN"}:
            self.telemetry.increment("recovery_events", recovery_status=result.status)
        if result.recovered_stop:
            self.telemetry.increment("stop_recoveries")
        if result.orphans_removed:
            self.telemetry.increment("orphan_stops_removed", result.orphans_removed)
        self.telemetry.sample_resources()
        return result


class OneShotMechanicalProposalClient:
    """Manual proposal source that can yield at most one proposal.

    Consumption happens before the proposal is returned.  Therefore an entry
    rejection or caller retry cannot cause the same manual invocation to be
    offered a second time.  Durable duplicate protection remains enforced by
    the normal EntryLifecycle as an independent safety layer.
    """

    def __init__(self, telemetry: MechanicalCanaryTelemetry | None = None) -> None:
        self._proposal: EntryProposal | None = None
        self._consumed = False
        self._telemetry = telemetry

    def offer(self, proposal: EntryProposal) -> None:
        if not isinstance(proposal, EntryProposal):
            raise MechanicalCanaryError("TESTNET_MECHANICAL_PROPOSAL_INVALID")
        if self._proposal is not None or self._consumed:
            if self._telemetry is not None:
                self._telemetry.increment("duplicate_preventions", boundary="ONE_SHOT_PROPOSAL")
            raise MechanicalCanaryError("TESTNET_MECHANICAL_PROPOSAL_ALREADY_OFFERED")
        if proposal.profile != TESTNET_MECHANICAL_PROFILE:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_PROFILE_MISMATCH")
        if proposal.market_environment != TESTNET_MECHANICAL_ENVIRONMENT:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_ENVIRONMENT_MISMATCH")
        if proposal.entry_authority != TESTNET_MECHANICAL_AUTHORITY:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_AUTHORITY_MISMATCH")
        self._proposal = proposal

    def request_proposal(
        self,
        *,
        profile: str,
        market_environment: str,
        execution_instance_id: str,
        requested_at_ms: int,
    ) -> EntryProposal | None:
        # Validate the call boundary even though EntryLifecycle independently
        # validates the proposal itself.
        if profile != TESTNET_MECHANICAL_PROFILE:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_REQUEST_PROFILE_MISMATCH")
        if market_environment != TESTNET_MECHANICAL_ENVIRONMENT:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_REQUEST_ENVIRONMENT_MISMATCH")
        if not isinstance(execution_instance_id, str) or not execution_instance_id.strip():
            raise MechanicalCanaryError("TESTNET_MECHANICAL_EXECUTION_INSTANCE_INVALID")
        if isinstance(requested_at_ms, bool) or not isinstance(requested_at_ms, int) or requested_at_ms <= 0:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_REQUEST_TIME_INVALID")
        if self._proposal is None or self._consumed:
            return None
        self._consumed = True
        return self._proposal


class MechanicalCanaryOutcomeClient:
    """Local idempotent Testnet-only outcome sink used before Observation V3.

    The normal Execution outbox remains the source record.  This client ACKs an
    outcome only after an idempotent durable local history write succeeds, so a
    completed mechanical canary does not permanently block later standalone
    canaries merely because V3.5's Observation outcome receiver does not exist.
    """

    def __init__(self, path: str | Path):
        self.store = ExecutionHistoryStore(path)

    def send_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> str:
        if not isinstance(payload, Mapping):
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_INVALID")
        row = dict(payload)
        if row.get("outcome_id") != outcome_id:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_ID_MISMATCH")
        if row.get("profile") != TESTNET_MECHANICAL_PROFILE:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_PROFILE_MISMATCH")
        if row.get("market_environment") != TESTNET_MECHANICAL_ENVIRONMENT:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_ENVIRONMENT_MISMATCH")
        if row.get("entry_authority") != TESTNET_MECHANICAL_AUTHORITY:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_AUTHORITY_MISMATCH")
        row["evidence_class"] = TESTNET_MECHANICAL_EVIDENCE_CLASS
        row["research_evidence"] = False
        self.store.append(outcome_id, row)
        return outcome_id


def mechanical_outcome_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / "data/execution/testnet/mechanical_canary_outcomes.jsonl"


def mechanical_telemetry_path(repo_root: str | Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or not run_id or run_id != run_id.strip():
        raise MechanicalCanaryError("TESTNET_MECHANICAL_TELEMETRY_RUN_ID_INVALID")
    return (
        Path(repo_root)
        / "data/execution/testnet/mechanical_canary_telemetry"
        / f"{run_id}.jsonl"
    )


def make_mechanical_proposal(
    quote: Quote,
    *,
    side: Side,
    now_ms: Callable[[], int] | None = None,
) -> EntryProposal:
    """Create one short-lived manual Testnet proposal from Execution quote truth."""
    if not isinstance(quote, Quote):
        raise MechanicalCanaryError("TESTNET_MECHANICAL_QUOTE_INVALID")
    if side not in {"LONG", "SHORT"}:
        raise MechanicalCanaryError("TESTNET_MECHANICAL_SIDE_INVALID")
    clock = now_ms or (lambda: int(time.time() * 1000))
    generated = clock()
    if isinstance(generated, bool) or not isinstance(generated, int) or generated <= 0:
        raise MechanicalCanaryError("TESTNET_MECHANICAL_TIME_INVALID")
    reference = quote.ask if side == "LONG" else quote.bid
    return EntryProposal(
        proposal_id=new_id("TESTNET_CANARY"),
        generated_at_ms=generated,
        expires_at_ms=generated + TESTNET_MECHANICAL_PROPOSAL_TTL_MS,
        profile=TESTNET_MECHANICAL_PROFILE,
        market_environment=TESTNET_MECHANICAL_ENVIRONMENT,
        symbol=quote.symbol,
        side=side,
        reference_price=reference,
        entry_authority=TESTNET_MECHANICAL_AUTHORITY,
        exit_policy_version=INTEGER_R_STEP_CONTROL,
    )
