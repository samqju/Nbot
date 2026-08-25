"""V3.6/V3.7 two-VPS integration boundary.

The V3.6 dry helper deliberately contains no exchange adapter and no
EntryLifecycle.  V3.7 reuses the same authenticated remote client behind a
small health-gated adapter that still contains no capital mechanics; the
Execution Worker remains the only owner of exchange/risk/entry/position state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping

from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, profile_is_armed
from nbot.execution.outcomes import ExecutionDurableStore

from .authorities import (
    LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
    TESTNET_OPERATIONAL_CANARY_AUTHORITY,
)
from .client import ObservationClientError, RemoteObservationClient
from .config import control_link_config_for_profile
from .validation import PROTOCOL_VERSION


V36_DISARMED_VETO_REASON = "V3_6_INTEGRATED_ORDER_GATE_DISARMED"


class V37IntegratedObservationClient:
    """Health-gated remote client for the V3.7 flat capital boundary.

    The wrapper deliberately performs its remote health validation only when
    Execution is already using ProposalClient/OutcomeClient work.  The
    ExecutionWorker never calls either interface from the OPEN-position hot
    path, so Observation/network loss cannot become a position-management
    dependency.
    """

    def __init__(
        self,
        *,
        remote: RemoteObservationClient,
        profile_name: str,
        release_sha: str,
    ) -> None:
        self.remote = remote
        self.profile_name = get_profile(profile_name).name
        self.release_sha = release_sha

    def _validate_remote(self) -> dict[str, Any]:
        health = self.remote.health()
        _validate_health(
            health=health,
            profile_name=self.profile_name,
            release_sha=self.release_sha,
        )
        return health

    def health(self) -> dict[str, Any]:
        return self._validate_remote()

    def operator_status(self, view: str) -> dict[str, Any]:
        return self.remote.operator_status(view)

    def record_entry_context(self, **kwargs: Any) -> None:
        self.remote.receipts.record_entry_context(**kwargs)

    def request_proposal(
        self,
        *,
        profile: str,
        market_environment: str,
        execution_instance_id: str,
        requested_at_ms: int,
    ):
        self._validate_remote()
        return self.remote.request_proposal(
            profile=profile,
            market_environment=market_environment,
            execution_instance_id=execution_instance_id,
            requested_at_ms=requested_at_ms,
        )

    def send_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> str:
        self._validate_remote()
        return self.remote.send_outcome(outcome_id=outcome_id, payload=payload)

    def record_veto(self, *, proposal_id: str, reason: str, rejected_at_ms: int) -> None:
        self.remote.record_veto(
            proposal_id=proposal_id,
            reason=reason,
            rejected_at_ms=rejected_at_ms,
        )


class V38LivePaperOperationalClient:
    """LIVE/PAPER adapter that captures Execution-owned quote truth pre-entry.

    Quote capture happens only while FLAT, immediately after a proposal is
    durably received.  Failure to capture/persist this audit context raises and
    therefore leaves capital flat.  No Observation call is introduced into the
    OPEN-position hot path.
    """

    def __init__(self, *, base: V37IntegratedObservationClient, exchange: Any) -> None:
        if base.profile_name != "live-paper":
            raise ValueError("NBOT_V38_LIVE_PAPER_CLIENT_PROFILE_REQUIRED")
        self.base = base
        self.exchange = exchange

    def health(self) -> dict[str, Any]:
        return self.base.health()

    def operator_status(self, view: str) -> dict[str, Any]:
        return self.base.operator_status(view)

    def request_proposal(self, **kwargs: Any):
        proposal = self.base.request_proposal(**kwargs)
        if proposal is None:
            return None
        if proposal.entry_authority != LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY:
            raise ObservationClientError("LIVE_PAPER_OPERATIONAL_AUTHORITY_MISMATCH")
        quote = self.exchange.quote(proposal.symbol)
        if getattr(quote, "symbol", None) != proposal.symbol:
            raise ObservationClientError("LIVE_PAPER_OPERATIONAL_QUOTE_SYMBOL_MISMATCH")
        observed_at_ms = int(time.time() * 1000)
        expected_entry_price = float(quote.ask if proposal.side == "LONG" else quote.bid)
        self.base.record_entry_context(
            proposal_id=proposal.proposal_id,
            observed_at_ms=observed_at_ms,
            quote_timestamp_ms=int(quote.timestamp_ms),
            bid=float(quote.bid),
            ask=float(quote.ask),
            mid=float(quote.mid),
            spread_pct=float(quote.spread_pct),
            expected_entry_price=expected_entry_price,
        )
        return proposal

    def send_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> str:
        return self.base.send_outcome(outcome_id=outcome_id, payload=payload)

    def record_veto(self, *, proposal_id: str, reason: str, rejected_at_ms: int) -> None:
        self.base.record_veto(
            proposal_id=proposal_id, reason=reason, rejected_at_ms=rejected_at_ms
        )




@dataclass(frozen=True)
class DryIntegrationResult:
    status: str
    health_status: str | None
    pending_before: int
    pending_after: int
    proposal_id: str | None = None
    proposal_authority: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git_sha(repo_root: Path) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as exc:
        raise ValueError("NBOT_V36_RELEASE_SHA_UNAVAILABLE") from exc
    if len(value) != 40:
        raise ValueError("NBOT_V36_RELEASE_SHA_UNAVAILABLE")
    return value


def _append_event(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        os.chmod(path, 0o600)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def _validate_health(
    *,
    health: Mapping[str, Any],
    profile_name: str,
    release_sha: str,
) -> None:
    profile = get_profile(profile_name)
    required = {
        "protocol_version": PROTOCOL_VERSION,
        "profile": profile.name,
        "market_environment": profile.market_environment,
        "evidence_lineage": profile.evidence_lineage,
        "release_sha": release_sha,
        "order_authority": "NONE",
    }
    for key, expected in required.items():
        if health.get(key) != expected:
            raise ObservationClientError(f"OBSERVATION_HEALTH_{key.upper()}_MISMATCH")
    if health.get("status") not in {"READY", "NOT_READY"}:
        raise ObservationClientError("OBSERVATION_HEALTH_STATUS_INVALID")
    authority = health.get("recommendation_authority")
    expected_authority = {
        "testnet-trade": TESTNET_OPERATIONAL_CANARY_AUTHORITY,
        "live-paper": LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
    }.get(profile.name)
    if authority not in {None, expected_authority}:
        raise ObservationClientError("OBSERVATION_HEALTH_RECOMMENDATION_AUTHORITY_INVALID")
    if health.get("status") == "READY" and authority != expected_authority:
        raise ObservationClientError("OBSERVATION_HEALTH_READY_AUTHORITY_REQUIRED")


def build_integrated_observation_client(
    *,
    repo_root: str | Path,
    profile_name: str,
    environ: Mapping[str, str] | None = None,
) -> V37IntegratedObservationClient:
    """Build the authenticated flat-boundary client for Testnet or LIVE_PAPER.

    Construction performs no network request.  This preserves restart safety:
    Execution can reconcile and manage an already-open position even while
    Observation or the control link is unavailable.
    """

    root = Path(repo_root)
    role = detect_role(root)
    if role is not MachineRole.EXECUTION:
        raise ValueError("NBOT_INTEGRATED_CLIENT_EXECUTION_ROLE_REQUIRED")
    profile = get_profile(profile_name)
    if profile.name not in {"testnet-trade", "live-paper"}:
        raise ValueError("NBOT_INTEGRATED_CLIENT_PROFILE_UNSUPPORTED")

    release_sha = _git_sha(root)
    link = control_link_config_for_profile(root, profile, environ=environ)
    leaf = "testnet" if profile.name == "testnet-trade" else "paper"
    remote = RemoteObservationClient(
        base_url=link.base_url,
        profile=profile.name,
        auth_token=link.auth_token,
        receipt_directory=root / f"runtime/execution/{leaf}/observation_receipts",
        execution_release_sha=release_sha,
        timeout_seconds=link.timeout_seconds,
        ca_file=link.ca_file,
    )
    return V37IntegratedObservationClient(
        remote=remote,
        profile_name=profile.name,
        release_sha=release_sha,
    )


def build_integrated_control_client(
    *,
    repo_root: str | Path,
    profile_name: str,
    environ: Mapping[str, str] | None = None,
) -> V37IntegratedObservationClient:
    """Neutral Execution-side factory for the authenticated control boundary."""
    return build_integrated_observation_client(
        repo_root=repo_root,
        profile_name=profile_name,
        environ=environ,
    )


def build_v37_testnet_client(
    *,
    repo_root: str | Path,
    profile_name: str,
    environ: Mapping[str, str] | None = None,
) -> V37IntegratedObservationClient:
    """Compatibility builder retaining the proven V3.7 Testnet contract."""
    if get_profile(profile_name).name != "testnet-trade":
        raise ValueError("NBOT_V37_TESTNET_PROFILE_ONLY")
    return build_integrated_observation_client(
        repo_root=repo_root,
        profile_name=profile_name,
        environ=environ,
    )


def run_v36_disarmed_cycle(
    *,
    repo_root: str | Path,
    profile_name: str,
    environ: Mapping[str, str] | None = None,
    now_ms: int | None = None,
) -> DryIntegrationResult:
    root = Path(repo_root)
    role = detect_role(root)
    if role is not MachineRole.EXECUTION:
        raise ValueError("NBOT_V36_DRY_EXECUTION_ROLE_REQUIRED")

    profile = get_profile(profile_name)
    if profile.name != "testnet-trade":
        raise ValueError("NBOT_V36_DRY_TESTNET_PROFILE_ONLY")
    if profile_is_armed(root, profile):
        raise ValueError("NBOT_V36_DRY_REQUIRES_TESTNET_DISARMED")

    durable = ExecutionDurableStore(root, profile=profile.name)
    snapshot = durable.state.snapshot
    if snapshot.open_position is not None:
        raise ValueError("NBOT_V36_DRY_REQUIRES_FLAT_STATE")
    if snapshot.entry_inflight is not None:
        raise ValueError("NBOT_V36_DRY_ENTRY_INFLIGHT_FORBIDDEN")
    if snapshot.recovery.critical:
        raise ValueError("NBOT_V36_DRY_RECOVERY_CRITICAL")
    if snapshot.entries_enabled:
        raise ValueError("NBOT_V36_DRY_ENTRIES_MUST_BE_DISABLED")

    release_sha = _git_sha(root)
    link = control_link_config_for_profile(root, profile, environ=environ)
    receipts = root / "runtime/execution/testnet/observation_receipts"
    client = RemoteObservationClient(
        base_url=link.base_url,
        profile=profile.name,
        auth_token=link.auth_token,
        receipt_directory=receipts,
        execution_release_sha=release_sha,
        timeout_seconds=link.timeout_seconds,
        ca_file=link.ca_file,
    )
    journal = root / "logs/execution/testnet/v36-dry-integration.jsonl"
    pending_before = durable.outbox.pending_count()

    try:
        health = client.health()
        _validate_health(health=health, profile_name=profile.name, release_sha=release_sha)
    except Exception as exc:
        result = DryIntegrationResult(
            status="OBSERVATION_UNAVAILABLE",
            health_status=None,
            pending_before=pending_before,
            pending_after=durable.outbox.pending_count(),
            reason=f"{type(exc).__name__}:{exc}",
        )
        _append_event(journal, {"event": "V36_DRY_CYCLE", **result.to_dict()})
        return result

    for row in durable.outbox.pending():
        outcome_id = row["record_id"]
        try:
            ack = client.send_outcome(outcome_id=outcome_id, payload=row["payload"])
        except Exception as exc:
            result = DryIntegrationResult(
                status="PENDING_OUTCOME",
                health_status=str(health.get("status")),
                pending_before=pending_before,
                pending_after=durable.outbox.pending_count(),
                reason=f"{type(exc).__name__}:{exc}",
            )
            _append_event(journal, {"event": "V36_DRY_CYCLE", **result.to_dict()})
            return result
        if ack != outcome_id:
            result = DryIntegrationResult(
                status="PENDING_OUTCOME",
                health_status=str(health.get("status")),
                pending_before=pending_before,
                pending_after=durable.outbox.pending_count(),
                reason="INVALID_OUTCOME_ACK",
            )
            _append_event(journal, {"event": "V36_DRY_CYCLE", **result.to_dict()})
            return result
        if not durable.outbox.acknowledge(outcome_id):
            raise ValueError("NBOT_V36_OUTCOME_ACK_LOCAL_RECORD_MISSING")

    request_time = int(time.time() * 1000) if now_ms is None else int(now_ms)
    try:
        proposal = client.request_proposal(
            profile=profile.name,
            market_environment=profile.market_environment,
            execution_instance_id=snapshot.execution_instance_id,
            requested_at_ms=request_time,
        )
    except Exception as exc:
        result = DryIntegrationResult(
            status="PROPOSAL_UNAVAILABLE",
            health_status=str(health.get("status")),
            pending_before=pending_before,
            pending_after=durable.outbox.pending_count(),
            reason=f"{type(exc).__name__}:{exc}",
        )
        _append_event(journal, {"event": "V36_DRY_CYCLE", **result.to_dict()})
        return result

    if proposal is None:
        result = DryIntegrationResult(
            status="NO_TRADE",
            health_status=str(health.get("status")),
            pending_before=pending_before,
            pending_after=durable.outbox.pending_count(),
            reason=(None if health.get("status") == "READY" else str(health.get("reason"))),
        )
        _append_event(journal, {"event": "V36_DRY_CYCLE", **result.to_dict()})
        return result

    if proposal.entry_authority != TESTNET_OPERATIONAL_CANARY_AUTHORITY:
        raise ObservationClientError("OBSERVATION_V36_PROPOSAL_AUTHORITY_INVALID")

    # V3.6 deliberately consumes no execution permission.  Persist veto
    # feedback so the next flat request tells Observation exactly what happened.
    client.record_veto(
        proposal_id=proposal.proposal_id,
        reason=V36_DISARMED_VETO_REASON,
        rejected_at_ms=request_time,
    )
    result = DryIntegrationResult(
        status="DRY_PROPOSAL",
        health_status=str(health.get("status")),
        pending_before=pending_before,
        pending_after=durable.outbox.pending_count(),
        proposal_id=proposal.proposal_id,
        proposal_authority=proposal.entry_authority,
        reason=V36_DISARMED_VETO_REASON,
    )
    _append_event(journal, {"event": "V36_DRY_CYCLE", **result.to_dict()})
    return result
