"""Atomic read-only live account snapshots and drift reporting."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LiveSnapshotDrift:
    status: str
    issues: tuple[str, ...]
    balance_delta_usdt: float | None

    @property
    def clean(self) -> bool:
        return not self.issues


class LiveSnapshotStore:
    VERSION = 1

    def __init__(self, path: str):
        self.path = Path(path)

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LIVE_SNAPSHOT_LOAD_FAILED | {exc}") from exc
        if not isinstance(data, dict) or data.get("version") != self.VERSION:
            raise RuntimeError("LIVE_SNAPSHOT_SCHEMA_INVALID")
        return data

    def write(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise RuntimeError("LIVE_SNAPSHOT_PAYLOAD_INVALID")

        document = dict(payload)
        document["version"] = self.VERSION
        document.setdefault("captured_at_ms", int(time.time() * 1000))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise
        return document

    @staticmethod
    def _symbols(rows: Any) -> tuple[str, ...]:
        if not isinstance(rows, list):
            return ()
        return tuple(sorted(str(row.get("symbol", "")).upper() for row in rows))

    def compare(self, previous: dict | None, current: dict) -> LiveSnapshotDrift:
        if previous is None:
            return LiveSnapshotDrift(
                status="BASELINE_CREATED",
                issues=(),
                balance_delta_usdt=None,
            )

        issues: list[str] = []
        previous_balance = float(previous.get("available_balance_usdt", 0.0))
        current_balance = float(current.get("available_balance_usdt", 0.0))
        balance_delta = current_balance - previous_balance

        if self._symbols(previous.get("positions")) != self._symbols(
            current.get("positions")
        ):
            issues.append("POSITION_SET_CHANGED")

        if self._symbols(previous.get("open_orders")) != self._symbols(
            current.get("open_orders")
        ):
            issues.append("OPEN_ORDER_SET_CHANGED")

        if self._symbols(previous.get("protective_stops")) != self._symbols(
            current.get("protective_stops")
        ):
            issues.append("PROTECTIVE_STOP_SET_CHANGED")

        previous_reconciliation = (
            previous.get("reconciliation", {}).get("status")
        )
        current_reconciliation = current.get("reconciliation", {}).get("status")
        if previous_reconciliation and (
            previous_reconciliation != current_reconciliation
        ):
            issues.append("RECONCILIATION_STATUS_CHANGED")

        return LiveSnapshotDrift(
            status="DRIFT_DETECTED" if issues else "NO_STRUCTURAL_DRIFT",
            issues=tuple(issues),
            balance_delta_usdt=balance_delta,
        )
