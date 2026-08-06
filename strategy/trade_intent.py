# ==========================================================
# TradeIntent Contract
# ==========================================================
# Strategy → Engine proposal.
#
# Properties:
# - Immutable
# - Stateless
# - Disposable
# - Never persisted
#
# Contract:
# - Engine is sole authority for validation
# - This object contains NO trading guarantees
# ==========================================================

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from typing import Dict, Any

@dataclass(frozen=True)
class TradeIntent:
    """
    Strategy proposal to open a trade.

    This is a PROPOSAL, not a command.
    Engine may accept or reject it.
    """

    symbol: str                    # e.g. "BTCUSDT"
    direction: str                 # "LONG" or "SHORT"
    pattern: str                   # Strategy identifier
    entry_price: Optional[float]   # Advisory only (engine uses market truth)
    generated_at: datetime         # UTC timestamp
    structure_fingerprint: Optional[Dict[str, Any]] = None
    advisory_risk_plan: Optional[Dict[str, Any]] = None
    candidate_observation_id: Optional[str] = None
    decision_batch_id: Optional[str] = None
    market_event_id: Optional[str] = None
    strategy_version: Optional[str] = None
    strategy_variant_id: Optional[str] = None
    model_version: Optional[str] = None
    experiment_context: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.direction not in ("LONG", "SHORT"):
            raise ValueError(
                f"INVALID_INTENT_DIRECTION: {self.direction}"
            )
