"""Append-only labels linked to candidate observation IDs."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


CANDIDATE_OUTCOME_SCHEMA_VERSION = 1


class CandidateOutcomeWriter:
    def __init__(
        self,
        path: str,
        system_log=None,
        *,
        environment: str | None = None,
        execution_mode: str | None = None,
    ):
        self.path = Path(path)
        self.system_log = system_log
        self.environment = (
            str(environment).strip().upper() if environment else None
        )
        self.execution_mode = (
            str(execution_mode).strip().upper() if execution_mode else None
        )
        self._lock = threading.Lock()

    def append(
        self,
        *,
        observation_id: str,
        outcome_type: str,
        symbol: str,
        direction: str,
        payload: dict,
    ) -> None:
        observation_id = str(observation_id or "").strip()
        if not observation_id:
            raise ValueError("CANDIDATE_OUTCOME_OBSERVATION_ID_INVALID")

        row = {
            "schema_version": CANDIDATE_OUTCOME_SCHEMA_VERSION,
            "observation_type": "CANDIDATE_OUTCOME",
            "recorded_at_ms": int(time.time() * 1000),
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "candidate_observation_id": observation_id,
            "outcome_type": str(outcome_type).strip().upper(),
            "symbol": str(symbol).strip().upper(),
            "direction": str(direction).strip().upper(),
            "payload": dict(payload),
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str)

        with self._lock:
            fd = os.open(
                self.path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(fd, (line + "\n").encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)

        if self.system_log:
            getattr(self.system_log, "debug", lambda *_args, **_kwargs: None)(
                "CANDIDATE_OUTCOME_WRITTEN | "
                f"id={observation_id} | "
                f"type={row['outcome_type']} | "
                f"symbol={row['symbol']}"
            )
