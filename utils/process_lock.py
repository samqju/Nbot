"""Single-process guard for the trading runtime."""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import TextIO


class BotAlreadyRunningError(RuntimeError):
    """Raised when another trading runtime already owns the process lock."""


class SingleInstanceLock:
    """Advisory OS lock that is released automatically when the process exits."""

    def __init__(self, path: str = "runtime/BOT_INSTANCE.lock"):
        self.path = Path(path)
        self._handle: TextIO | None = None

    def acquire(self, *, environment: str, execution_mode: str) -> None:
        if self._handle is not None:
            raise RuntimeError("BOT_INSTANCE_LOCK_ALREADY_ACQUIRED")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip() or "UNKNOWN"
            handle.close()
            raise BotAlreadyRunningError(
                f"BOT_ALREADY_RUNNING | lock={self.path} | owner={owner}"
            ) from exc

        metadata = {
            "pid": os.getpid(),
            "environment": str(environment).strip().upper(),
            "execution_mode": str(execution_mode).strip().upper(),
            "acquired_at_ms": int(time.time() * 1000),
        }
        handle.seek(0)
        handle.truncate()
        json.dump(metadata, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self):
        if self._handle is None:
            raise RuntimeError("BOT_INSTANCE_LOCK_NOT_ACQUIRED")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()
        return False
