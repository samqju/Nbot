"""Verified emergency flattening for NBOT V3.1.7.

This module owns only the mechanical capital-safety boundary:

* issue a bounded number of close requests for one known capital position;
* treat a write exception as ambiguous and verify exchange truth anyway;
* return only after ``position_snapshot()`` proves the exchange is flat;
* never clear local Execution state or invent close/PnL accounting;
* fail closed when flatness cannot be proven.

Authoritative close accounting and durable local settlement remain the job of
V3.1.6 reconciliation.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

from nbot.exchange.contracts import ExchangePort, ExchangePosition, Side

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,40}$")


class EmergencyFlattenError(RuntimeError):
    """Emergency close could not safely prove the requested position flat."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class EmergencyConfig:
    """Frozen V1/V2-parity mechanics for verified emergency flattening."""

    max_attempts: int = 2
    verify_delay_seconds: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise ValueError("EMERGENCY_ATTEMPTS_INVALID")
        if self.max_attempts < 1 or self.max_attempts > 10:
            raise ValueError("EMERGENCY_ATTEMPTS_INVALID")
        if isinstance(self.verify_delay_seconds, bool) or not isinstance(
            self.verify_delay_seconds, (int, float)
        ):
            raise ValueError("EMERGENCY_VERIFY_DELAY_INVALID")
        delay = float(self.verify_delay_seconds)
        if not math.isfinite(delay) or delay < 0 or delay > 10:
            raise ValueError("EMERGENCY_VERIFY_DELAY_INVALID")


class EmergencyFlattener:
    """Concrete V3.1.7 implementation of the ``VerifiedEmergencyPort`` boundary.

    ``flatten_verified`` has deliberately narrow semantics: success means only
    that current exchange position truth is FLAT.  It does not mean authoritative
    close accounting is already available, and it never mutates Execution state.
    """

    def __init__(
        self,
        *,
        exchange: ExchangePort,
        config: EmergencyConfig | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.exchange = exchange
        self.config = config or EmergencyConfig()
        if not callable(sleep):
            raise ValueError("EMERGENCY_SLEEP_INVALID")
        self._sleep = sleep
        self._active = threading.Lock()

    def flatten_verified(self, symbol: str, side: Side, *, reason: str) -> None:
        """Flatten one known position and return only after exchange FLAT proof.

        A close exception is treated as ambiguous because the request may have
        reached the exchange.  Every attempt is therefore followed by an
        independent ``position_snapshot`` verification.  If flatness cannot be
        proven within the configured bound, ``EmergencyFlattenError`` is raised.
        """

        symbol = self._require_symbol(symbol)
        side = self._require_side(side)
        reason = self._require_reason(reason)

        if not self._active.acquire(blocking=False):
            raise EmergencyFlattenError("EMERGENCY_EXIT_ALREADY_IN_PROGRESS")

        try:
            last_error: Exception | None = None

            # If current truth is already flat (for example a stop settled just
            # before emergency handling), no extra close write is necessary.
            # Snapshot failure is not treated as proof of exposure or flatness;
            # continue with the bounded close/verify sequence instead.
            try:
                initial = self.exchange.position_snapshot()
            except Exception as exc:
                last_error = exc
            else:
                if initial is None:
                    return
                self._require_expected_position(initial, symbol, side)

            for attempt in range(1, self.config.max_attempts + 1):
                try:
                    self.exchange.close_position(symbol, side, reason=reason)
                except Exception as exc:
                    # Ambiguous write: verify truth before deciding whether a
                    # retry is needed.  Never assume the close failed.
                    last_error = exc

                delay = float(self.config.verify_delay_seconds)
                if delay:
                    try:
                        self._sleep(delay)
                    except Exception as exc:
                        raise EmergencyFlattenError("EMERGENCY_VERIFY_DELAY_FAILED") from exc

                try:
                    remaining = self.exchange.position_snapshot()
                except Exception as exc:
                    last_error = exc
                    continue

                if remaining is None:
                    return

                # ExchangePort is one-position/one-way.  A different position
                # appearing during emergency handling is contradictory capital
                # truth and must not be silently closed under the wrong identity.
                self._require_expected_position(remaining, symbol, side)

                if attempt < self.config.max_attempts:
                    continue

            error = EmergencyFlattenError("EMERGENCY_EXIT_FAILED_NOT_FLAT")
            if last_error is None:
                raise error
            raise error from last_error
        finally:
            self._active.release()

    @staticmethod
    def _require_symbol(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("EMERGENCY_SYMBOL_INVALID")
        if not value or value != value.strip() or _SYMBOL_RE.fullmatch(value) is None:
            raise ValueError("EMERGENCY_SYMBOL_INVALID")
        return value

    @staticmethod
    def _require_side(value: object) -> Side:
        if value not in {"LONG", "SHORT"}:
            raise ValueError("EMERGENCY_SIDE_INVALID")
        return value  # type: ignore[return-value]

    @staticmethod
    def _require_reason(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("EMERGENCY_REASON_INVALID")
        if not value or value != value.strip() or len(value) > 200:
            raise ValueError("EMERGENCY_REASON_INVALID")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("EMERGENCY_REASON_INVALID")
        return value

    @staticmethod
    def _require_expected_position(
        position: ExchangePosition,
        symbol: str,
        side: Side,
    ) -> None:
        if position.symbol != symbol:
            raise EmergencyFlattenError("EMERGENCY_POSITION_SYMBOL_MISMATCH")
        if position.side != side:
            raise EmergencyFlattenError("EMERGENCY_POSITION_SIDE_MISMATCH")
