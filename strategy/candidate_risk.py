"""Advisory candidate risk planning for Phase 3.4."""

from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from config import (
    CANDIDATE_RISK_MAX_STOP_PCT,
    CANDIDATE_RISK_MIN_STOP_PCT,
    CANDIDATE_RISK_RANGE_MULTIPLIER,
    LEVERAGE,
    MAX_NOTIONAL_USD,
    RISK_PER_TRADE_USD,
)

CANDIDATE_RISK_PLAN_SCHEMA_VERSION = 1

@dataclass(frozen=True)
class CandidateRiskPlan:
    risk_budget_usd: float
    reference_price: float
    stop_distance_pct: float
    stop_distance_price: float
    suggested_stop_price: float
    suggested_quantity: float
    suggested_notional_usd: float
    required_margin_usd: float
    risk_efficiency: float
    capped_by: str
    execution_authority: str = "RISK_MANAGER"

    def as_dict(self):
        data = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in asdict(self).items()}
        data["schema_version"] = CANDIDATE_RISK_PLAN_SCHEMA_VERSION
        data["advisory_only"] = True
        return data

class CandidateRiskPlanner:
    def __init__(self, *, risk_budget_usd=RISK_PER_TRADE_USD, max_notional_usd=MAX_NOTIONAL_USD, leverage=LEVERAGE, min_stop_pct=CANDIDATE_RISK_MIN_STOP_PCT, max_stop_pct=CANDIDATE_RISK_MAX_STOP_PCT, range_multiplier=CANDIDATE_RISK_RANGE_MULTIPLIER):
        self.risk_budget_usd=float(risk_budget_usd); self.max_notional_usd=float(max_notional_usd); self.leverage=float(leverage)
        self.min_stop_fraction=float(min_stop_pct)/100.0; self.max_stop_fraction=float(max_stop_pct)/100.0; self.range_multiplier=float(range_multiplier)
        if self.risk_budget_usd<=0: raise ValueError("CANDIDATE_RISK_BUDGET_INVALID")
        if self.max_notional_usd<=0: raise ValueError("CANDIDATE_RISK_NOTIONAL_INVALID")
        if self.leverage<=0: raise ValueError("CANDIDATE_RISK_LEVERAGE_INVALID")
        if not (0<self.min_stop_fraction<=self.max_stop_fraction): raise ValueError("CANDIDATE_RISK_STOP_RANGE_INVALID")

    def plan(self,candidate):
        price=float(candidate.reference_price or 0.0)
        if price<=0: raise ValueError("CANDIDATE_RISK_REFERENCE_PRICE_INVALID")
        raw=float(candidate.features.short_range)*self.range_multiplier
        stop_fraction=max(self.min_stop_fraction,min(self.max_stop_fraction,raw))
        stop_distance=price*stop_fraction
        qty_risk=self.risk_budget_usd/stop_distance
        qty_notional=self.max_notional_usd/price
        qty=min(qty_risk,qty_notional)
        if qty<=0: raise ValueError("CANDIDATE_RISK_QUANTITY_INVALID")
        notional=qty*price
        stop=price-stop_distance if candidate.direction=="LONG" else price+stop_distance
        if stop<=0: raise ValueError("CANDIDATE_RISK_STOP_INVALID")
        plan=CandidateRiskPlan(
            self.risk_budget_usd,price,stop_fraction*100.0,stop_distance,stop,qty,notional,
            notional/self.leverage,min(1.0,(qty*stop_distance)/self.risk_budget_usd),
            "NOTIONAL" if qty_notional<=qty_risk else "RISK"
        )
        return replace(candidate,risk_plan=plan)

    def plan_all(self,candidates):
        return [self.plan(c) for c in candidates]
