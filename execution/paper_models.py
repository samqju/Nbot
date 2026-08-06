"""Typed records used by the local paper-trading account."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PaperPosition:
    trade_id: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    stop_loss: float
    opened_at_ms: int
    initial_risk_usd: float
    entry_fee_usd: float = 0.0
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    structure_fingerprint: Optional[str] = None
    pattern: Optional[str] = None
    strategy_version: Optional[str] = None
    model_version: Optional[str] = None
    candidate_observation_id: Optional[str] = None
    decision_batch_id: Optional[str] = None
    market_event_id: Optional[str] = None
    strategy_variant_id: Optional[str] = None
    experiment_context: Optional[Dict[str, Any]] = None
    selection_authority: str = "RULES"
    paper_canary_model_id: Optional[str] = None
    paper_risk_multiplier: float = 1.0
    paper_allocation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "PaperPosition":
        return cls(**raw)


@dataclass(frozen=True)
class PaperTrade:
    trade_id: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    exit_price: float
    opened_at_ms: int
    closed_at_ms: int
    initial_risk_usd: float
    gross_pnl_usd: float
    entry_fee_usd: float
    exit_fee_usd: float
    net_pnl_usd: float
    net_r: float
    exit_reason: str
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    structure_fingerprint: Optional[str] = None
    pattern: Optional[str] = None
    strategy_version: Optional[str] = None
    model_version: Optional[str] = None
    candidate_observation_id: Optional[str] = None
    decision_batch_id: Optional[str] = None
    market_event_id: Optional[str] = None
    strategy_variant_id: Optional[str] = None
    experiment_context: Optional[Dict[str, Any]] = None
    selection_authority: str = "RULES"
    paper_canary_model_id: Optional[str] = None
    paper_risk_multiplier: float = 1.0
    paper_allocation_id: Optional[str] = None
    source: str = "PAPER"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
