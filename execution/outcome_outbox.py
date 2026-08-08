"""Durable execution-outcome queue owned by the Execution side."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from communication.execution_outcome import ExecutionOutcome


class ExecutionOutcomeOutbox:
    """Store one JSON file per undelivered outcome using atomic replacement."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path, 0o700)
        except OSError:
            pass

    @staticmethod
    def _filename(outcome_id: str) -> str:
        digest = hashlib.sha256(outcome_id.encode("utf-8")).hexdigest()
        return f"{digest}.json"

    def _path_for(self, outcome_id: str) -> Path:
        return self.path / self._filename(outcome_id)

    def _fsync_dir(self) -> None:
        try:
            fd = os.open(self.path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def enqueue(self, outcome: ExecutionOutcome) -> ExecutionOutcome:
        if not isinstance(outcome, ExecutionOutcome):
            raise TypeError("EXECUTION_OUTBOX_OUTCOME_INVALID")

        target = self._path_for(outcome.outcome_id)
        if target.exists():
            existing = ExecutionOutcome.from_dict(
                json.loads(target.read_text(encoding="utf-8"))
            )
            if existing.outcome_id != outcome.outcome_id:
                raise RuntimeError("EXECUTION_OUTBOX_ID_COLLISION")
            return existing

        payload = json.dumps(
            outcome.to_dict(),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        fd, temp_name = tempfile.mkstemp(
            prefix=".outcome-",
            suffix=".tmp",
            dir=self.path,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, target)
            self._fsync_dir()
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

        return outcome

    def pending(self) -> list[ExecutionOutcome]:
        outcomes: list[ExecutionOutcome] = []
        for path in sorted(self.path.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            outcomes.append(ExecutionOutcome.from_dict(payload))
        return outcomes

    def pending_count(self) -> int:
        return sum(1 for _ in self.path.glob("*.json"))

    def acknowledge(self, outcome_id: str) -> bool:
        target = self._path_for(str(outcome_id))
        if not target.exists():
            return False
        target.unlink()
        self._fsync_dir()
        return True
