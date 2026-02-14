# ==========================================================
# Risk Decision Contracts
# ==========================================================
# Pure data structures.
# NO logic. NO side effects.
#
# These are shared contracts between RiskManager and Engine.
#
# Invariants:
# - Violation decisions must include reason
# - Halt decisions must include reason
# - Stop-loss values must be positive if provided
# ==========================================================

from dataclasses import dataclass
from typing import Optional


# ----------------------------------------------------------
# Entry Decision
# ----------------------------------------------------------

@dataclass(frozen=True)
class EntryDecision:
    allowed: bool
    stop_loss: Optional[float]
    reason: Optional[str]
    daily_loss_floor: float

    def __post_init__(self):
        if not self.allowed and not self.reason:
            raise ValueError("ENTRY_DENIED_REQUIRES_REASON")

        if self.stop_loss is not None and self.stop_loss <= 0:
            raise ValueError("INVALID_STOP_LOSS_VALUE")


# ----------------------------------------------------------
# Position Decision
# ----------------------------------------------------------

@dataclass(frozen=True)
class PositionDecision:
    violation: bool
    normal_exit: bool
    updated_stop_loss: Optional[float]
    highest_profit_usd: Optional[float]
    next_integer_R: Optional[int]
    reason: Optional[str]

    def __post_init__(self):
        if self.violation and not self.reason:
            raise ValueError("VIOLATION_REQUIRES_REASON")

        if self.updated_stop_loss is not None:
            if self.updated_stop_loss <= 0:
                raise ValueError("INVALID_UPDATED_STOP_LOSS")


# ----------------------------------------------------------
# Daily Risk Decision
# ----------------------------------------------------------

@dataclass(frozen=True)
class DailyDecision:
    halt: bool
    reason: Optional[str]
    daily_loss_floor: float

    def __post_init__(self):
        if self.halt and not self.reason:
            raise ValueError("HALT_REQUIRES_REASON")
