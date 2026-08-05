"""Deterministic, explainable candidate scoring for Phase 3.3."""
from __future__ import annotations
from dataclasses import dataclass, replace
from config import (CANDIDATE_SCORE_CANDLE_WEIGHT,CANDIDATE_SCORE_CONSISTENCY_WEIGHT,CANDIDATE_SCORE_LOCATION_WEIGHT,CANDIDATE_SCORE_RULE_WEIGHT,CANDIDATE_SCORE_TREND_WEIGHT,CANDIDATE_SCORE_VOLATILITY_WEIGHT)
def _clamp(value,low=0.0,high=1.0): return max(low,min(high,float(value)))
@dataclass(frozen=True)
class CandidateScoreBreakdown:
    rule_score: float
    rule_quality: float
    trend_alignment: float
    volatility_quality: float
    candle_quality: float
    location_quality: float
    directional_consistency: float
    final_score: float
    def as_dict(self):
        return {"rule_score":self.rule_score,"rule_quality":self.rule_quality,"trend_alignment":self.trend_alignment,"volatility_quality":self.volatility_quality,"candle_quality":self.candle_quality,"location_quality":self.location_quality,"directional_consistency":self.directional_consistency,"final_score":self.final_score}
class CandidateScorer:
    def __init__(self,*,rule_weight=CANDIDATE_SCORE_RULE_WEIGHT,trend_weight=CANDIDATE_SCORE_TREND_WEIGHT,volatility_weight=CANDIDATE_SCORE_VOLATILITY_WEIGHT,candle_weight=CANDIDATE_SCORE_CANDLE_WEIGHT,location_weight=CANDIDATE_SCORE_LOCATION_WEIGHT,consistency_weight=CANDIDATE_SCORE_CONSISTENCY_WEIGHT):
        self.weights={"rule":float(rule_weight),"trend":float(trend_weight),"volatility":float(volatility_weight),"candle":float(candle_weight),"location":float(location_weight),"consistency":float(consistency_weight)}
        if any(v<0 for v in self.weights.values()): raise ValueError("CANDIDATE_SCORER_WEIGHT_NEGATIVE")
        if abs(sum(self.weights.values())-1.0)>1e-9: raise ValueError("CANDIDATE_SCORER_WEIGHTS_SUM")
    def score(self,candidate):
        f=candidate.features; rule_score=float(candidate.score); rule_quality=_clamp(rule_score); trend_alignment=_clamp(abs(f.trend_score)/10.0); base_volatility=_clamp(f.short_range/0.01); expansion_penalty=_clamp(1.0-max(0.0,f.range_acceleration-2.0)/2.0); volatility_quality=base_volatility*expansion_penalty; candle_quality=_clamp(f.body_ratio_recent); relevant_distance=abs(f.dist_high) if candidate.direction=="LONG" else abs(f.dist_low); location_quality=_clamp(1.0-relevant_distance/0.02); directional_consistency=_clamp(f.directional_consistency/5.0); final_score=_clamp(self.weights["rule"]*rule_quality+self.weights["trend"]*trend_alignment+self.weights["volatility"]*volatility_quality+self.weights["candle"]*candle_quality+self.weights["location"]*location_quality+self.weights["consistency"]*directional_consistency); breakdown=CandidateScoreBreakdown(rule_score,rule_quality,trend_alignment,volatility_quality,candle_quality,location_quality,directional_consistency,final_score); return replace(candidate,score=final_score,score_breakdown=breakdown)
    def score_all(self,candidates): return [self.score(c) for c in candidates]
