from __future__ import annotations

from datetime import datetime, timezone
import time as _time

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def utc_now_ms() -> int:
    return int(_time.time() * 1000)


def utc_iso() -> str:
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


def monotonic_seconds() -> float:
    return _time.monotonic()
