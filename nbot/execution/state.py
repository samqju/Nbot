"""Durable execution state for NBOT V3.1.

The state store is intentionally execution-only and fail-closed.  It persists
capital-bearing facts with fsync + atomic replacement and refuses to silently
repair incompatible/corrupt state.
"""

from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import threading
from nbot.common.synchronization import state_transition
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from nbot.exchange.contracts import EntryPlan, Fill, ProtectiveStopRef
from nbot.execution.models import DailyRisk, EntryInflight, ExecutionHealth, OpenPosition

EXECUTION_STATE_VERSION = "NBOT_V3_EXECUTION_STATE_V1"
MAX_PROCESSED_PROPOSALS = 10_000

_PROFILE_LAYOUT = {
    "testnet-trade": ("testnet", "TESTNET"),
    "live-paper": ("paper", "LIVE"),
    "live-trade": ("real", "LIVE"),
}


class ExecutionStateError(RuntimeError):
    """Raised when durable Execution state cannot be trusted."""


def _require_text(name: str, value: object, *, max_length: int = 200) -> str:
    if not isinstance(value, str):
        raise ExecutionStateError(f"{name}_INVALID")
    if not value or value != value.strip() or len(value) > max_length:
        raise ExecutionStateError(f"{name}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ExecutionStateError(f"{name}_INVALID")
    return value


def _require_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ExecutionStateError(f"{name}_INVALID")
    return value


def _require_bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ExecutionStateError(f"{name}_INVALID")
    return value


def _require_exact_keys(name: str, payload: Mapping[str, Any], keys: set[str]) -> None:
    actual = set(payload)
    if actual != keys:
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        detail = []
        if missing:
            detail.append("MISSING=" + ",".join(missing))
        if unknown:
            detail.append("UNKNOWN=" + ",".join(unknown))
        raise ExecutionStateError(f"{name}_SCHEMA_INVALID:" + ";".join(detail))


def _as_mapping(name: str, value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExecutionStateError(f"{name}_INVALID")
    if any(not isinstance(key, str) for key in value):
        raise ExecutionStateError(f"{name}_KEY_INVALID")
    return dict(value)


def _safe_construct(name: str, factory, **kwargs):
    try:
        return factory(**kwargs)
    except (TypeError, ValueError) as exc:
        raise ExecutionStateError(f"{name}_INVALID:{exc}") from exc


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        raise ExecutionStateError(f"EXECUTION_DIRECTORY_PERMISSION_FAILED:{path}") from exc


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _secure_dir(path.parent)
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ExecutionStateError("EXECUTION_STATE_NOT_JSON_SAFE") from exc

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
        _fsync_dir(path.parent)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


@dataclass(frozen=True, slots=True)
class ExecutionStatePaths:
    """Canonical profile-separated Execution persistence paths."""

    base_dir: Path
    state_file: Path
    history_file: Path
    pending_outcomes_dir: Path
    profile: str
    market_environment: str

    @classmethod
    def for_profile(cls, repo_root: str | Path, profile: str) -> "ExecutionStatePaths":
        if profile not in _PROFILE_LAYOUT:
            raise ExecutionStateError("EXECUTION_PROFILE_UNSUPPORTED")
        leaf, market_environment = _PROFILE_LAYOUT[profile]
        root = Path(repo_root)
        base = root / "data" / "execution" / leaf
        return cls(
            base_dir=base,
            state_file=base / "execution_state.json",
            history_file=base / "execution_history.jsonl",
            pending_outcomes_dir=base / "pending_outcomes",
            profile=profile,
            market_environment=market_environment,
        )


@dataclass(frozen=True, slots=True)
class RecoveryMetadata:
    """Small durable recovery/critical-condition status."""

    last_reconciliation_ms: int = 0
    critical: bool = False
    critical_reason: str | None = None
    last_event: str | None = None

    def __post_init__(self) -> None:
        _require_nonnegative_int("RECOVERY_LAST_RECONCILIATION_MS", self.last_reconciliation_ms)
        _require_bool("RECOVERY_CRITICAL", self.critical)
        if self.critical:
            if self.critical_reason is None:
                raise ExecutionStateError("RECOVERY_CRITICAL_REASON_REQUIRED")
            _require_text("RECOVERY_CRITICAL_REASON", self.critical_reason)
        elif self.critical_reason is not None:
            raise ExecutionStateError("RECOVERY_CRITICAL_REASON_WITHOUT_CRITICAL")
        if self.last_event is not None:
            _require_text("RECOVERY_LAST_EVENT", self.last_event)


@dataclass(frozen=True, slots=True)
class ExecutionStateSnapshot:
    state_version: str
    profile: str
    market_environment: str
    execution_instance_id: str
    entries_enabled: bool
    open_position: OpenPosition | None
    entry_inflight: EntryInflight | None
    processed_proposal_ids: tuple[str, ...]
    daily_risk: DailyRisk
    health: ExecutionHealth
    recovery: RecoveryMetadata

    def __post_init__(self) -> None:
        if self.state_version != EXECUTION_STATE_VERSION:
            raise ExecutionStateError("EXECUTION_STATE_VERSION_MISMATCH")
        if self.profile not in _PROFILE_LAYOUT:
            raise ExecutionStateError("EXECUTION_STATE_PROFILE_INVALID")
        expected_environment = _PROFILE_LAYOUT[self.profile][1]
        if self.market_environment != expected_environment:
            raise ExecutionStateError("EXECUTION_STATE_ENVIRONMENT_MISMATCH")
        try:
            parsed = uuid.UUID(hex=self.execution_instance_id)
        except (ValueError, AttributeError) as exc:
            raise ExecutionStateError("EXECUTION_INSTANCE_ID_INVALID") from exc
        if parsed.hex != self.execution_instance_id:
            raise ExecutionStateError("EXECUTION_INSTANCE_ID_INVALID")
        _require_bool("EXECUTION_ENTRIES_ENABLED", self.entries_enabled)
        if self.open_position is not None and self.entry_inflight is not None:
            raise ExecutionStateError("EXECUTION_STATE_OPEN_AND_INFLIGHT")
        if len(self.processed_proposal_ids) > MAX_PROCESSED_PROPOSALS:
            raise ExecutionStateError("EXECUTION_PROPOSAL_HISTORY_TOO_LARGE")
        if len(set(self.processed_proposal_ids)) != len(self.processed_proposal_ids):
            raise ExecutionStateError("EXECUTION_PROPOSAL_HISTORY_DUPLICATE")
        for proposal_id in self.processed_proposal_ids:
            _require_text("EXECUTION_PROCESSED_PROPOSAL_ID", proposal_id)


def _fill_to_dict(fill: Fill) -> dict[str, Any]:
    return asdict(fill)


def _fill_from_dict(payload: object) -> Fill:
    raw = _as_mapping("FILL", payload)
    _require_exact_keys("FILL", raw, {"price", "quantity", "order_id", "client_order_id", "timestamp_ms"})
    return _safe_construct("FILL", Fill, **raw)


def _plan_to_dict(plan: EntryPlan) -> dict[str, Any]:
    return asdict(plan)


def _plan_from_dict(payload: object) -> EntryPlan:
    raw = _as_mapping("ENTRY_PLAN", payload)
    _require_exact_keys(
        "ENTRY_PLAN",
        raw,
        {
            "symbol", "side", "quantity", "expected_entry_price",
            "initial_stop_price", "initial_risk_usd", "notional_usd", "leverage",
        },
    )
    return _safe_construct("ENTRY_PLAN", EntryPlan, **raw)


def _stop_to_dict(stop: ProtectiveStopRef) -> dict[str, Any]:
    return asdict(stop)


def _stop_from_dict(payload: object) -> ProtectiveStopRef:
    raw = _as_mapping("PROTECTIVE_STOP", payload)
    _require_exact_keys(
        "PROTECTIVE_STOP",
        raw,
        {"symbol", "side", "quantity", "trigger_price", "stop_id", "client_stop_id"},
    )
    return _safe_construct("PROTECTIVE_STOP", ProtectiveStopRef, **raw)


def _open_to_dict(position: OpenPosition) -> dict[str, Any]:
    return {
        "proposal_id": position.proposal_id,
        "symbol": position.symbol,
        "side": position.side,
        "entry_fill": _fill_to_dict(position.entry_fill),
        "initial_risk_usd": position.initial_risk_usd,
        "initial_stop_price": position.initial_stop_price,
        "protective_stop": _stop_to_dict(position.protective_stop),
        "entry_authority": position.entry_authority,
        "exit_policy_version": position.exit_policy_version,
        "mfe_r": position.mfe_r,
        "mae_r": position.mae_r,
    }


def _open_from_dict(payload: object) -> OpenPosition:
    raw = _as_mapping("OPEN_POSITION", payload)
    _require_exact_keys(
        "OPEN_POSITION",
        raw,
        {
            "proposal_id", "symbol", "side", "entry_fill", "initial_risk_usd",
            "initial_stop_price", "protective_stop", "entry_authority",
            "exit_policy_version", "mfe_r", "mae_r",
        },
    )
    raw["entry_fill"] = _fill_from_dict(raw["entry_fill"])
    raw["protective_stop"] = _stop_from_dict(raw["protective_stop"])
    return _safe_construct("OPEN_POSITION", OpenPosition, **raw)


def _inflight_to_dict(inflight: EntryInflight) -> dict[str, Any]:
    return {
        "proposal_id": inflight.proposal_id,
        "entry_authority": inflight.entry_authority,
        "exit_policy_version": inflight.exit_policy_version,
        "plan": _plan_to_dict(inflight.plan),
        "client_order_id": inflight.client_order_id,
        "started_at_ms": inflight.started_at_ms,
        "fill": None if inflight.fill is None else _fill_to_dict(inflight.fill),
    }


def _inflight_from_dict(payload: object) -> EntryInflight:
    raw = _as_mapping("ENTRY_INFLIGHT", payload)
    _require_exact_keys(
        "ENTRY_INFLIGHT",
        raw,
        {
            "proposal_id", "entry_authority", "exit_policy_version", "plan",
            "client_order_id", "started_at_ms", "fill",
        },
    )
    raw["plan"] = _plan_from_dict(raw["plan"])
    raw["fill"] = None if raw["fill"] is None else _fill_from_dict(raw["fill"])
    return _safe_construct("ENTRY_INFLIGHT", EntryInflight, **raw)


def _daily_to_dict(daily: DailyRisk) -> dict[str, Any]:
    return asdict(daily)


def _daily_from_dict(payload: object) -> DailyRisk:
    raw = _as_mapping("DAILY_RISK", payload)
    _require_exact_keys("DAILY_RISK", raw, set(asdict(DailyRisk())))
    return _safe_construct("DAILY_RISK", DailyRisk, **raw)


def _health_to_dict(health: ExecutionHealth) -> dict[str, Any]:
    return asdict(health)


def _health_from_dict(payload: object) -> ExecutionHealth:
    raw = _as_mapping("EXECUTION_HEALTH", payload)
    _require_exact_keys("EXECUTION_HEALTH", raw, set(asdict(ExecutionHealth())))
    return _safe_construct("EXECUTION_HEALTH", ExecutionHealth, **raw)


def _recovery_to_dict(recovery: RecoveryMetadata) -> dict[str, Any]:
    return asdict(recovery)


def _recovery_from_dict(payload: object) -> RecoveryMetadata:
    raw = _as_mapping("RECOVERY", payload)
    _require_exact_keys("RECOVERY", raw, set(asdict(RecoveryMetadata())))
    return _safe_construct("RECOVERY", RecoveryMetadata, **raw)


def _snapshot_to_dict(snapshot: ExecutionStateSnapshot) -> dict[str, Any]:
    return {
        "state_version": snapshot.state_version,
        "profile": snapshot.profile,
        "market_environment": snapshot.market_environment,
        "execution_instance_id": snapshot.execution_instance_id,
        "entries_enabled": snapshot.entries_enabled,
        "open_position": None if snapshot.open_position is None else _open_to_dict(snapshot.open_position),
        "entry_inflight": None if snapshot.entry_inflight is None else _inflight_to_dict(snapshot.entry_inflight),
        "processed_proposal_ids": list(snapshot.processed_proposal_ids),
        "daily_risk": _daily_to_dict(snapshot.daily_risk),
        "health": _health_to_dict(snapshot.health),
        "recovery": _recovery_to_dict(snapshot.recovery),
    }


def _snapshot_from_dict(payload: object) -> ExecutionStateSnapshot:
    raw = _as_mapping("EXECUTION_STATE", payload)
    _require_exact_keys(
        "EXECUTION_STATE",
        raw,
        {
            "state_version", "profile", "market_environment", "execution_instance_id",
            "entries_enabled", "open_position", "entry_inflight", "processed_proposal_ids",
            "daily_risk", "health", "recovery",
        },
    )
    if not isinstance(raw["processed_proposal_ids"], list):
        raise ExecutionStateError("EXECUTION_PROPOSAL_HISTORY_INVALID")
    return ExecutionStateSnapshot(
        state_version=raw["state_version"],
        profile=raw["profile"],
        market_environment=raw["market_environment"],
        execution_instance_id=raw["execution_instance_id"],
        entries_enabled=raw["entries_enabled"],
        open_position=None if raw["open_position"] is None else _open_from_dict(raw["open_position"]),
        entry_inflight=None if raw["entry_inflight"] is None else _inflight_from_dict(raw["entry_inflight"]),
        processed_proposal_ids=tuple(raw["processed_proposal_ids"]),
        daily_risk=_daily_from_dict(raw["daily_risk"]),
        health=_health_from_dict(raw["health"]),
        recovery=_recovery_from_dict(raw["recovery"]),
    )


class ExecutionStateStore:
    """Atomic typed state store for one Execution capital profile."""

    def __init__(self, path: str | Path, *, profile: str, market_environment: str):
        self.mutation_lock = threading.RLock()
        self.path = Path(path)
        self.profile = profile
        self.market_environment = market_environment
        if profile not in _PROFILE_LAYOUT:
            raise ExecutionStateError("EXECUTION_PROFILE_UNSUPPORTED")
        if _PROFILE_LAYOUT[profile][1] != market_environment:
            raise ExecutionStateError("EXECUTION_PROFILE_ENVIRONMENT_MISMATCH")
        _secure_dir(self.path.parent)
        if self.path.exists():
            self._snapshot = self._load_existing()
        else:
            self._snapshot = ExecutionStateSnapshot(
                state_version=EXECUTION_STATE_VERSION,
                profile=profile,
                market_environment=market_environment,
                execution_instance_id=uuid.uuid4().hex,
                entries_enabled=False,
                open_position=None,
                entry_inflight=None,
                processed_proposal_ids=(),
                daily_risk=DailyRisk(),
                health=ExecutionHealth(),
                recovery=RecoveryMetadata(),
            )
            self._persist(self._snapshot)

    def _load_existing(self) -> ExecutionStateSnapshot:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ExecutionStateError(f"EXECUTION_STATE_CORRUPT:{type(exc).__name__}") from exc
        try:
            snapshot = _snapshot_from_dict(raw)
        except ExecutionStateError:
            raise
        except Exception as exc:
            raise ExecutionStateError(f"EXECUTION_STATE_CORRUPT:{type(exc).__name__}") from exc
        if snapshot.profile != self.profile:
            raise ExecutionStateError("EXECUTION_STATE_PROFILE_MISMATCH")
        if snapshot.market_environment != self.market_environment:
            raise ExecutionStateError("EXECUTION_STATE_ENVIRONMENT_MISMATCH")
        return snapshot

    def _persist(self, snapshot: ExecutionStateSnapshot) -> None:
        _atomic_write_json(self.path, _snapshot_to_dict(snapshot))

    @state_transition
    def reload_after_runtime_lock(self) -> None:
        """Refresh a startup snapshot after exclusive runtime ownership."""
        self._snapshot = self._load_existing()

    def _commit(self, snapshot: ExecutionStateSnapshot) -> None:
        # Reconstruct from encoded form before disk write so no mutation can place
        # a shape on disk that our own restart path would reject.
        canonical = _snapshot_from_dict(_snapshot_to_dict(snapshot))
        self._persist(canonical)
        self._snapshot = canonical

    @property
    def snapshot(self) -> ExecutionStateSnapshot:
        return self._snapshot

    @property
    def open_position(self) -> OpenPosition | None:
        return self._snapshot.open_position

    @property
    def entry_inflight(self) -> EntryInflight | None:
        return self._snapshot.entry_inflight

    @property
    def daily_risk(self) -> DailyRisk:
        return self._snapshot.daily_risk

    @property
    def health(self) -> ExecutionHealth:
        return self._snapshot.health

    @property
    def recovery(self) -> RecoveryMetadata:
        return self._snapshot.recovery

    @state_transition
    def set_entries_enabled(self, enabled: bool) -> None:
        _require_bool("EXECUTION_ENTRIES_ENABLED", enabled)
        self._commit(replace(self._snapshot, entries_enabled=enabled))

    def has_processed_proposal(self, proposal_id: str) -> bool:
        proposal_id = _require_text("EXECUTION_PROCESSED_PROPOSAL_ID", proposal_id)
        return proposal_id in self._snapshot.processed_proposal_ids

    @state_transition
    def reserve_proposal(self, proposal_id: str) -> bool:
        proposal_id = _require_text("EXECUTION_PROCESSED_PROPOSAL_ID", proposal_id)
        ids = list(self._snapshot.processed_proposal_ids)
        if proposal_id in ids:
            return False
        ids.append(proposal_id)
        if len(ids) > MAX_PROCESSED_PROPOSALS:
            ids = ids[-MAX_PROCESSED_PROPOSALS:]
        self._commit(replace(self._snapshot, processed_proposal_ids=tuple(ids)))
        return True

    @state_transition
    def begin_entry(self, inflight: EntryInflight) -> None:
        if not isinstance(inflight, EntryInflight):
            raise ExecutionStateError("EXECUTION_ENTRY_INFLIGHT_INVALID")
        if self._snapshot.open_position is not None:
            raise ExecutionStateError("EXECUTION_BEGIN_ENTRY_WHILE_OPEN")
        if self._snapshot.entry_inflight is not None:
            raise ExecutionStateError("EXECUTION_ENTRY_ALREADY_INFLIGHT")
        if inflight.proposal_id not in self._snapshot.processed_proposal_ids:
            raise ExecutionStateError("EXECUTION_PROPOSAL_NOT_RESERVED")
        self._commit(replace(self._snapshot, entry_inflight=inflight))

    @state_transition
    def record_inflight_fill(self, fill: Fill) -> None:
        inflight = self._snapshot.entry_inflight
        if inflight is None:
            raise ExecutionStateError("EXECUTION_ENTRY_INFLIGHT_MISSING")
        if not isinstance(fill, Fill):
            raise ExecutionStateError("EXECUTION_FILL_INVALID")
        updated = EntryInflight(
            proposal_id=inflight.proposal_id,
            entry_authority=inflight.entry_authority,
            exit_policy_version=inflight.exit_policy_version,
            plan=inflight.plan,
            client_order_id=inflight.client_order_id,
            started_at_ms=inflight.started_at_ms,
            fill=fill,
        )
        self._commit(replace(self._snapshot, entry_inflight=updated))

    @state_transition
    def promote_inflight_position(self, position: OpenPosition) -> None:
        inflight = self._snapshot.entry_inflight
        if inflight is None:
            raise ExecutionStateError("EXECUTION_ENTRY_INFLIGHT_MISSING")
        if inflight.fill is None:
            raise ExecutionStateError("EXECUTION_ENTRY_FILL_MISSING")
        if not isinstance(position, OpenPosition):
            raise ExecutionStateError("EXECUTION_OPEN_POSITION_INVALID")
        if position.proposal_id != inflight.proposal_id:
            raise ExecutionStateError("EXECUTION_OPEN_PROPOSAL_MISMATCH")
        if position.entry_fill != inflight.fill:
            raise ExecutionStateError("EXECUTION_OPEN_FILL_MISMATCH")
        if position.symbol != inflight.plan.symbol or position.side != inflight.plan.side:
            raise ExecutionStateError("EXECUTION_OPEN_PLAN_MISMATCH")
        if position.entry_authority != inflight.entry_authority:
            raise ExecutionStateError("EXECUTION_OPEN_AUTHORITY_MISMATCH")
        if position.exit_policy_version != inflight.exit_policy_version:
            raise ExecutionStateError("EXECUTION_OPEN_POLICY_MISMATCH")
        self._commit(replace(self._snapshot, open_position=position, entry_inflight=None))

    @state_transition
    def clear_entry_inflight(self) -> None:
        if self._snapshot.entry_inflight is None:
            raise ExecutionStateError("EXECUTION_ENTRY_INFLIGHT_MISSING")
        self._commit(replace(self._snapshot, entry_inflight=None))

    @state_transition
    def update_open_position(self, position: OpenPosition) -> None:
        current = self._snapshot.open_position
        if current is None:
            raise ExecutionStateError("EXECUTION_OPEN_POSITION_MISSING")
        if not isinstance(position, OpenPosition):
            raise ExecutionStateError("EXECUTION_OPEN_POSITION_INVALID")
        if (
            position.proposal_id != current.proposal_id
            or position.symbol != current.symbol
            or position.side != current.side
            or position.entry_fill != current.entry_fill
            or not math.isclose(position.initial_risk_usd, current.initial_risk_usd, rel_tol=0.0, abs_tol=1e-12)
            or not math.isclose(position.initial_stop_price, current.initial_stop_price, rel_tol=0.0, abs_tol=1e-12)
            or position.entry_authority != current.entry_authority
            or position.exit_policy_version != current.exit_policy_version
        ):
            raise ExecutionStateError("EXECUTION_OPEN_POSITION_IDENTITY_CHANGED")
        self._commit(replace(self._snapshot, open_position=position))

    @state_transition
    def set_daily_risk(self, daily_risk: DailyRisk) -> None:
        if not isinstance(daily_risk, DailyRisk):
            raise ExecutionStateError("EXECUTION_DAILY_RISK_INVALID")
        self._commit(replace(self._snapshot, daily_risk=daily_risk))

    @state_transition
    def set_health(self, health: ExecutionHealth) -> None:
        if not isinstance(health, ExecutionHealth):
            raise ExecutionStateError("EXECUTION_HEALTH_INVALID")
        self._commit(replace(self._snapshot, health=health))

    @state_transition
    def set_recovery(self, recovery: RecoveryMetadata) -> None:
        if not isinstance(recovery, RecoveryMetadata):
            raise ExecutionStateError("EXECUTION_RECOVERY_INVALID")
        self._commit(replace(self._snapshot, recovery=recovery))

    @state_transition
    def _clear_open_after_durable_close(self, *, daily_risk: DailyRisk | None = None) -> None:
        """Atomically clear OPEN state after outcome/history durability is proven.

        ``daily_risk`` is committed in the same state replacement as the clear so
        a crash cannot settle the position while losing or double-applying the
        daily accounting update.  The method is intentionally internal: callers
        must first make the completed outcome durable.
        """
        if self._snapshot.open_position is None:
            return
        next_daily = self._snapshot.daily_risk if daily_risk is None else daily_risk
        if not isinstance(next_daily, DailyRisk):
            raise ExecutionStateError("EXECUTION_DAILY_RISK_INVALID")
        self._commit(
            replace(
                self._snapshot,
                open_position=None,
                daily_risk=next_daily,
            )
        )

    @state_transition
    def _clear_inflight_after_durable_close(self, *, daily_risk: DailyRisk | None = None) -> None:
        """Atomically settle a proven entry-inflight close after durable outcome writes."""
        if self._snapshot.entry_inflight is None:
            return
        next_daily = self._snapshot.daily_risk if daily_risk is None else daily_risk
        if not isinstance(next_daily, DailyRisk):
            raise ExecutionStateError("EXECUTION_DAILY_RISK_INVALID")
        self._commit(
            replace(
                self._snapshot,
                entry_inflight=None,
                daily_risk=next_daily,
            )
        )

    def export_dict(self) -> dict[str, Any]:
        return copy.deepcopy(_snapshot_to_dict(self._snapshot))
