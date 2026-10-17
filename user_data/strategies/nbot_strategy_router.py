"""Offline NBOT V6 fixed-strategy research router. NEVER sends trades.

Compare predicted net (already after costs) across FROZEN candidate setups,
require model/data/cost sanity, then select at most one or NO TRADE.
"""
from dataclasses import dataclass
import math
from typing import Iterable
from nbot_trade_outcome import KINDS

@dataclass(frozen=True)
class CandidateScore:
    kind: str
    predicted_net: float
    uncertainty: float
    model_ready: bool
    age_hours: float
    depth_usdt: float
    expected_stake_usdt: float
    adverse_extra_cost: float = 0.0

@dataclass(frozen=True)
class RouterPolicy:
    minimum_predicted_net: float = 0.004
    max_uncertainty: float = 0.01
    max_model_age_hours: float = 24.0
    min_depth_multiple: float = 10.0
    max_adverse_extra_cost: float = 0.02

@dataclass(frozen=True)
class ResearchDecision:
    action: str
    selected_score_after_reserve: float | None
    reason: str
    for_research_only: bool = True

def choose_candidate(candidates: Iterable[CandidateScore],
                     policy: RouterPolicy = RouterPolicy()) -> ResearchDecision:
    """Single theoretical choice, never an order entry.

    Predicted net must come from as-of model forecasts that already include
    base execution costs. Adverse-extra-cost is a user-declared stress,
    never a claim about measured fill prices.
    """
    if any(not math.isfinite(v) or v < 0 for v in (
        policy.minimum_predicted_net, policy.max_uncertainty,
        policy.max_model_age_hours, policy.min_depth_multiple,
        policy.max_adverse_extra_cost
    )):
        raise ValueError("INVALID_ROUTER_POLICY")
    finalists = []
    for score in candidates:
        if score.kind not in KINDS or not score.model_ready:
            continue
        vals = (score.predicted_net, score.uncertainty, score.age_hours,
                score.depth_usdt, score.expected_stake_usdt,
                score.adverse_extra_cost)
        if not all(math.isfinite(x) for x in vals):
            continue
        if (score.age_hours < 0 or score.age_hours > policy.max_model_age_hours
                or score.uncertainty < 0 or score.uncertainty > policy.max_uncertainty
                or score.expected_stake_usdt <= 0 or score.depth_usdt < 0
                or score.depth_usdt < policy.min_depth_multiple * score.expected_stake_usdt
                or not 0 <= score.adverse_extra_cost <= policy.max_adverse_extra_cost):
            continue
        conservative = score.predicted_net - score.adverse_extra_cost - score.uncertainty
        if conservative > policy.minimum_predicted_net:
            finalists.append((conservative, score.kind))
    if not finalists:
        return ResearchDecision("NO_TRADE", None, "No candidate clears costs, uncertainty and risk")
    finalists.sort(key=lambda item: (-item[0], item[1]))
    net, kind = finalists[0]
    return ResearchDecision(kind, net, "One eligible frozen candidate; research only")
