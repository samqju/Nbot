"""G1 source/route identity contracts; no source access or authenticity claims.

A syntactically valid cursor is only a *reported* envelope. Actual original
exchange custody, replay and qualified economics are separate future gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .core import FiveMinuteEvent, INTERVAL_MS

SOURCE_CONTRACT_VERSION = "NBOT_V5_1_SOURCE_V1"
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class RouteHealth(str, Enum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    GAP = "GAP"
    DISCONNECTED = "DISCONNECTED"


@dataclass(frozen=True)
class SourceCursor:
    """Reported source envelope. This class cannot authenticate a market feed."""
    symbol: str
    route: str
    source_epoch: int
    sequence: int
    last_bar_open_ms: int
    received_at_ms: int
    origin_digest: str | None
    health: RouteHealth
    has_gap: bool = False

    def __post_init__(self) -> None:
        if type(self.symbol) is not str or not _SYMBOL.fullmatch(self.symbol):
            raise ValueError("G1_SOURCE_SYMBOL_INVALID")
        if type(self.route) is not str or not 1 <= len(self.route) <= 40 or not re.fullmatch(r"[a-z0-9_-]+", self.route):
            raise ValueError("G1_SOURCE_ROUTE_INVALID")
        for v in (self.source_epoch, self.sequence, self.last_bar_open_ms, self.received_at_ms):
            if type(v) is not int or v < 0:
                raise ValueError("G1_SOURCE_CLOCK_INVALID")
        if self.last_bar_open_ms % INTERVAL_MS:
            raise ValueError("G1_SOURCE_BAR_INVALID")
        if type(self.health) is not RouteHealth or type(self.has_gap) is not bool:
            raise ValueError("G1_SOURCE_HEALTH_INVALID")
        if self.origin_digest is not None and (type(self.origin_digest) is not str or
                                               not _SHA.fullmatch(self.origin_digest)):
            raise ValueError("G1_SOURCE_DIGEST_INVALID")


def source_hold_reasons(event: FiveMinuteEvent, cursor: SourceCursor | None, *, expected_symbol: str) -> tuple[str, ...]:
    """Return stable reasons and ALWAYS HOLD until actual external custody exists."""
    if type(event) is not FiveMinuteEvent:
        raise ValueError("G1_SOURCE_EVENT_INVALID")
    if type(expected_symbol) is not str or not _SYMBOL.fullmatch(expected_symbol):
        raise ValueError("G1_EXPECTED_SYMBOL_INVALID")
    reasons = {"SOURCE_UNAUTHENTICATED_G1"}
    if cursor is None:
        return tuple(sorted(reasons | {"SOURCE_MISSING"}))
    if type(cursor) is not SourceCursor:
        return tuple(sorted(reasons | {"SOURCE_INVALID"}))
    if cursor.symbol != expected_symbol:
        reasons.add("SOURCE_SYMBOL_MISMATCH")
    if cursor.health is not RouteHealth.HEALTHY or cursor.has_gap:
        reasons.add("SOURCE_ROUTE_HOLD")
    if cursor.last_bar_open_ms != event.event_open_ms:
        reasons.add("SOURCE_NOT_ASOF_EVENT")
    if not event.event_close_ms <= cursor.received_at_ms <= event.decision_at_ms:
        reasons.add("SOURCE_RECEIPT_TIME_INVALID")
    if cursor.origin_digest is None:
        reasons.add("SOURCE_ORIGIN_DIGEST_MISSING")
    return tuple(sorted(reasons))
