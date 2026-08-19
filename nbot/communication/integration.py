"""V3.6 disarmed two-VPS integration boundary.

This module deliberately contains no exchange adapter and no EntryLifecycle.
It may deliver already-durable completed outcomes and ask Observation what it
would recommend while the integrated order gate is physically disarmed.
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

from .client import ObservationClientError, RemoteObservationClient
from .config import control_link_config_for_profile
from .validation import PROTOCOL_VERSION


TESTNET_OPERATIONAL_CANARY_AUTHORITY = "TESTNET_OPERATIONAL_CANARY_V1"
V36_DISARMED_VETO_REASON = "V3_6_INTEGRATED_ORDER_GATE_DISARMED"


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
    if profile.name == "testnet-trade":
        if authority not in {None, TESTNET_OPERATIONAL_CANARY_AUTHORITY}:
            raise ObservationClientError("OBSERVATION_HEALTH_RECOMMENDATION_AUTHORITY_INVALID")


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
