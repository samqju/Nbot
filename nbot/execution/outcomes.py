"""Durable Execution history and pending-outcome storage for V3.1.

This module stores JSON-safe outcome payloads without depending on the future
V3.5 communication schema.  Later, ExecutionOutcome.to_dict() can be placed in
this storage without changing its durability semantics.
"""

from __future__ import annotations

from nbot.common.synchronization import state_transition

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from nbot.execution.models import DailyRisk
from nbot.execution.state import ExecutionStateError, _fsync_dir, _secure_dir


def _require_record_id(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 200:
        raise ExecutionStateError("EXECUTION_OUTCOME_ID_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ExecutionStateError("EXECUTION_OUTCOME_ID_INVALID")
    return value


def _json_safe(value: Any, *, path: str = "payload") -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ExecutionStateError(f"EXECUTION_OUTCOME_JSON_INVALID:{path}")
        return value
    if isinstance(value, list):
        return [_json_safe(item, path=f"{path}[]") for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item, path=f"{path}[]") for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ExecutionStateError(f"EXECUTION_OUTCOME_JSON_INVALID:{path}.key")
            result[key] = _json_safe(item, path=f"{path}.{key}")
        return result
    raise ExecutionStateError(f"EXECUTION_OUTCOME_JSON_INVALID:{path}")


def _canonical_payload(record_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    record_id = _require_record_id(record_id)
    if not isinstance(payload, Mapping):
        raise ExecutionStateError("EXECUTION_OUTCOME_PAYLOAD_INVALID")
    normalized = _json_safe(dict(payload))
    if not isinstance(normalized, dict):
        raise ExecutionStateError("EXECUTION_OUTCOME_PAYLOAD_INVALID")
    embedded = normalized.get("outcome_id")
    if embedded is not None and embedded != record_id:
        raise ExecutionStateError("EXECUTION_OUTCOME_ID_MISMATCH")
    return {"record_id": record_id, "payload": normalized}


def _encode_json(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ExecutionStateError("EXECUTION_OUTCOME_JSON_INVALID") from exc


def _atomic_write_text(path: Path, text: str) -> None:
    _secure_dir(path.parent)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
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


class ExecutionHistoryStore:
    """Idempotent JSONL history rewritten atomically per completed trade."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        _secure_dir(self.path.parent)
        if self.path.exists():
            self._read_all()  # fail closed immediately on corruption

    def _read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        seen: dict[str, str] = {}
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            raise ExecutionStateError(f"EXECUTION_HISTORY_CORRUPT:{type(exc).__name__}") from exc
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                raise ExecutionStateError(f"EXECUTION_HISTORY_CORRUPT:EMPTY_LINE:{index}")
            try:
                row = json.loads(line)
            except Exception as exc:
                raise ExecutionStateError(f"EXECUTION_HISTORY_CORRUPT:JSON:{index}") from exc
            if not isinstance(row, dict) or set(row) != {"record_id", "payload"}:
                raise ExecutionStateError(f"EXECUTION_HISTORY_CORRUPT:SCHEMA:{index}")
            canonical = _canonical_payload(row["record_id"], row["payload"])
            encoded = _encode_json(canonical)
            prior = seen.get(canonical["record_id"])
            if prior is not None:
                if prior != encoded:
                    raise ExecutionStateError("EXECUTION_HISTORY_ID_COLLISION")
                raise ExecutionStateError("EXECUTION_HISTORY_DUPLICATE_ID")
            seen[canonical["record_id"]] = encoded
            rows.append(canonical)
        return rows

    def records(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._read_all()]

    def append(self, record_id: str, payload: Mapping[str, Any]) -> bool:
        canonical = _canonical_payload(record_id, payload)
        rows = self._read_all()
        encoded_new = _encode_json(canonical)
        for row in rows:
            if row["record_id"] == canonical["record_id"]:
                if _encode_json(row) != encoded_new:
                    raise ExecutionStateError("EXECUTION_HISTORY_ID_COLLISION")
                return False
        rows.append(canonical)
        text = "".join(_encode_json(row) + "\n" for row in rows)
        _atomic_write_text(self.path, text)
        return True


class PendingOutcomeOutbox:
    """One-file-per-outcome durable outbox with idempotent enqueue/ACK."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        _secure_dir(self.path)
        self.pending()  # fail closed immediately on corrupt files

    @staticmethod
    def _filename(record_id: str) -> str:
        record_id = _require_record_id(record_id)
        return hashlib.sha256(record_id.encode("utf-8")).hexdigest() + ".json"

    def _path_for(self, record_id: str) -> Path:
        return self.path / self._filename(record_id)

    def enqueue(self, record_id: str, payload: Mapping[str, Any]) -> bool:
        canonical = _canonical_payload(record_id, payload)
        target = self._path_for(record_id)
        encoded = _encode_json(canonical) + "\n"
        if target.exists():
            existing = self._read_file(target)
            if _encode_json(existing) != _encode_json(canonical):
                raise ExecutionStateError("EXECUTION_OUTBOX_ID_COLLISION")
            return False
        _atomic_write_text(target, encoded)
        return True

    def _read_file(self, path: Path) -> dict[str, Any]:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ExecutionStateError(f"EXECUTION_OUTBOX_CORRUPT:{path.name}") from exc
        if not isinstance(row, dict) or set(row) != {"record_id", "payload"}:
            raise ExecutionStateError(f"EXECUTION_OUTBOX_CORRUPT:{path.name}")
        canonical = _canonical_payload(row["record_id"], row["payload"])
        if self._filename(canonical["record_id"]) != path.name:
            raise ExecutionStateError("EXECUTION_OUTBOX_FILENAME_ID_MISMATCH")
        return canonical

    def pending(self) -> list[dict[str, Any]]:
        rows = []
        for path in sorted(self.path.glob("*.json")):
            rows.append(self._read_file(path))
        return rows

    def pending_count(self) -> int:
        return len(self.pending())

    def acknowledge(self, record_id: str) -> bool:
        target = self._path_for(record_id)
        if not target.exists():
            return False
        # Validate before deletion; a corrupt/colliding file is never silently dropped.
        self._read_file(target)
        target.unlink()
        _fsync_dir(self.path)
        return True


class ExecutionDurableStore:
    """Profile-scoped state/history/outbox coordinator.

    Close finalization ordering is intentionally:

        pending outbox -> completed history -> clear open position

    Therefore a crash can leave redundant durable evidence, but cannot leave the
    process flat with both the completed history and pending outcome missing.
    """

    def __init__(self, repo_root: str | Path, *, profile: str):
        # Local import avoids making state.py depend on outcome storage.
        from nbot.execution.state import ExecutionStatePaths, ExecutionStateStore

        self.paths = ExecutionStatePaths.for_profile(repo_root, profile)
        _secure_dir(self.paths.base_dir)
        self.state = ExecutionStateStore(
            self.paths.state_file,
            profile=profile,
            market_environment=self.paths.market_environment,
        )
        self.history = ExecutionHistoryStore(self.paths.history_file)
        self.outbox = PendingOutcomeOutbox(self.paths.pending_outcomes_dir)

    @state_transition
    def finalize_closed_position(
        self,
        outcome_id: str,
        payload: Mapping[str, Any],
        *,
        daily_risk: DailyRisk | None = None,
    ) -> None:
        if self.state.open_position is None:
            raise ExecutionStateError("EXECUTION_FINALIZE_WITHOUT_OPEN_POSITION")
        canonical = _canonical_payload(outcome_id, payload)
        body = canonical["payload"]
        required_identity = {"outcome_id", "proposal_id", "symbol", "side"}
        if not required_identity.issubset(body):
            raise ExecutionStateError("EXECUTION_OUTCOME_IDENTITY_INCOMPLETE")
        if body["proposal_id"] != self.state.open_position.proposal_id:
            raise ExecutionStateError("EXECUTION_OUTCOME_PROPOSAL_MISMATCH")
        if body["symbol"] != self.state.open_position.symbol:
            raise ExecutionStateError("EXECUTION_OUTCOME_SYMBOL_MISMATCH")
        if body["side"] != self.state.open_position.side:
            raise ExecutionStateError("EXECUTION_OUTCOME_SIDE_MISMATCH")
        if daily_risk is not None and not isinstance(daily_risk, DailyRisk):
            raise ExecutionStateError("EXECUTION_DAILY_RISK_INVALID")

        # The sequence is the safety contract. Each earlier step is idempotent,
        # so a restart may safely retry if state clearing was not reached.  The
        # final state commit clears OPEN and updates daily risk atomically.
        self.outbox.enqueue(outcome_id, body)
        self.history.append(outcome_id, body)
        self.state._clear_open_after_durable_close(daily_risk=daily_risk)

    @state_transition
    def finalize_closed_inflight(
        self,
        outcome_id: str,
        payload: Mapping[str, Any],
        *,
        daily_risk: DailyRisk | None = None,
    ) -> None:
        """Durably settle an entry that filled and closed before OPEN promotion.

        This is the V3.1.6 crash-window counterpart to ``finalize_closed_position``.
        The exact proposal/order identity remains in ``entry_inflight`` until
        outbox and history writes are durable; only then are the inflight journal
        and daily-risk update committed together.
        """
        inflight = self.state.entry_inflight
        if inflight is None or inflight.fill is None:
            raise ExecutionStateError("EXECUTION_FINALIZE_WITHOUT_FILLED_INFLIGHT")
        canonical = _canonical_payload(outcome_id, payload)
        body = canonical["payload"]
        required_identity = {"outcome_id", "proposal_id", "symbol", "side"}
        if not required_identity.issubset(body):
            raise ExecutionStateError("EXECUTION_OUTCOME_IDENTITY_INCOMPLETE")
        if body["proposal_id"] != inflight.proposal_id:
            raise ExecutionStateError("EXECUTION_OUTCOME_PROPOSAL_MISMATCH")
        if body["symbol"] != inflight.plan.symbol:
            raise ExecutionStateError("EXECUTION_OUTCOME_SYMBOL_MISMATCH")
        if body["side"] != inflight.plan.side:
            raise ExecutionStateError("EXECUTION_OUTCOME_SIDE_MISMATCH")
        if daily_risk is not None and not isinstance(daily_risk, DailyRisk):
            raise ExecutionStateError("EXECUTION_DAILY_RISK_INVALID")

        self.outbox.enqueue(outcome_id, body)
        self.history.append(outcome_id, body)
        self.state._clear_inflight_after_durable_close(daily_risk=daily_risk)
