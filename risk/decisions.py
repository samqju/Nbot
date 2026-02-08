# risk/decisions.py
# ==========================================================
# Risk Decision Contracts
# ==========================================================
# Pure data structures.
# NO logic. NO side effects.
# These are shared contracts between RiskManager and Engine.
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


# ----------------------------------------------------------
# Position Decision
# ----------------------------------------------------------

@dataclass(frozen=True)
class PositionDecision:
    violation: bool
    normal_exit: bool
    updated_stop_loss: Optional[float]
    highest_profit_usd: Optional[float]
    reason: Optional[str]


# ----------------------------------------------------------
# Daily Risk Decision
# ----------------------------------------------------------

@dataclass(frozen=True)
class DailyDecision:
    halt: bool
    reason: Optional[str]
    daily_loss_floor: float
