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
    selection_authority: str = "RULES"
    paper_canary_model_id: Optional[str] = None
    paper_risk_multiplier: float = 1.0
    paper_allocation_id: Optional[str] = None

    def __post_init__(self):
        if self.direction not in ("LONG", "SHORT"):
            raise ValueError(
                f"INVALID_INTENT_DIRECTION: {self.direction}"
            )
        authority = str(self.selection_authority or "").strip().upper()
        if authority not in {"RULES", "PAPER_CANARY", "PAPER_CHAMPION"}:
            raise ValueError(
                f"INVALID_INTENT_SELECTION_AUTHORITY: {authority}"
            )
        object.__setattr__(self, "selection_authority", authority)
        multiplier = float(self.paper_risk_multiplier)
        if not (0.0 < multiplier <= 1.0):
            raise ValueError("INVALID_INTENT_PAPER_RISK_MULTIPLIER")
        object.__setattr__(self, "paper_risk_multiplier", multiplier)
        if authority in {"PAPER_CANARY", "PAPER_CHAMPION"}:
            if abs(multiplier - 1.0) > 1e-12:
                raise ValueError("INVALID_INTENT_MODEL_RISK_MUST_EQUAL_ONE")
            model_id = str(self.paper_canary_model_id or "").strip()
            if not model_id:
                raise ValueError("INVALID_INTENT_PAPER_MODEL_ID")
            object.__setattr__(self, "paper_canary_model_id", model_id)
            if authority == "PAPER_CANARY":
                allocation_id = str(self.paper_allocation_id or "").strip()
                if not allocation_id:
                    raise ValueError("INVALID_INTENT_PAPER_ALLOCATION_ID")
                object.__setattr__(self, "paper_allocation_id", allocation_id)
