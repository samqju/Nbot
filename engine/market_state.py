# ==========================================================
# MARKET STATE
# ==========================================================
# Authoritative in-memory market data cache.
#
# Responsibilities:
# - Store last known price per symbol
# - Store last known timestamp per symbol
#
# NON-responsibilities:
# - No trading logic
# - No strategy logic
# - No risk logic
# ==========================================================

from typing import Dict


class MarketState:
    """
    In-memory cache of latest market prices.
    """

    def __init__(self):
        self.last_price: Dict[str, float] = {}
        self.last_timestamp: Dict[str, int] = {}

    # --------------------------------------------------
    # Update
    # --------------------------------------------------

    def update(self, *, symbol: str, price: float, timestamp: int) -> None:
        self.last_price[symbol] = price
        self.last_timestamp[symbol] = timestamp

    # --------------------------------------------------
    # Accessors
    # --------------------------------------------------

    def has_price(self, symbol: str) -> bool:
        return symbol in self.last_price

    def get_price(self, symbol: str) -> float:
        return self.last_price[symbol]

    def get_timestamp(self, symbol: str) -> int:
        return self.last_timestamp[symbol]
