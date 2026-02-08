# ==========================================================
# TradeIntent Contract
# ==========================================================
# This is the ONLY interface from Strategy → Engine.
#
# - Immutable
# - Stateless
# - Disposable
# - Never persisted
# ==========================================================

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TradeIntent:
    """
    Strategy proposal to open a trade.

    This is a PROPOSAL, not a command.
    Engine may accept or reject it.
    """

    symbol: str                    # e.g. "BTCUSDT"
    direction: str                 # "LONG" or "SHORT"
    pattern: str                   # e.g. "BREAKOUT_5M"
    entry_price: Optional[float]   # advisory only
    generated_at: datetime         # UTC timestamp
