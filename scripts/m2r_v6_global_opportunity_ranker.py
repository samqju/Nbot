"""NBOT V6 offline research: choose ONE best credible opportunity globally.

Unlike the existing per-setup signal router or broad 8-hour regime-family
selector, this ranks all valid LONG/SHORT trade opportunities from ALL 25
eligible coins AND independently validated candidate strategy families at
one shared 5-minute decision boundary. Research only; NEVER sends orders.

IMPORTANT: Only as-of *predictions*, NEVER realized future returns, can be
selection inputs. Models/targets must be calibrated to identical net-return
fractions and exit-policy/horizon semantics. One strategy with arbitrary
high numeric predictions must not win merely due to inconsistent targets.

A production Freqtrade portfolio adapter, FreqAI parallel inference, exact
native portfolio replay and economic out-of-sample proof are NOT implemented
here. This is a pure, rigorously guarded independent selection primitive.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Iterable, Sequence

FAMILIES=frozenset((
    "breakout", "pullback",
    "ema_cross", "donchian_breakout", "bollinger_reversion",
    "rsi_reversion", "macd_momentum", "stochastic_reversal",
    "atr_breakout", "volume_trend"
))
SIDES=frozenset(("long","short"))
REGIMES=frozenset(("trend_up","trend_down","range","high_volatility"))
FIVE_MINUTES=timedelta(minutes=5)
LABEL_HORIZON=timedelta(minutes=60)

@dataclass(frozen=True)
class Opportunity:
    pair: str
    family: str
    side: str
    regime: str
    signal_candle_closed_utc: str
    prediction_generated_utc: str
    model_training_last_feature_utc: str
    model_fitted_utc: str
    exit_policy: str
    prediction_target: str
    predicted_net_return_fraction: float
    uncertainty_fraction: float
    additional_execution_cost_fraction: float
    downside_risk_fraction: float
    available_market_depth_usdt: float
    intended_stake_usdt: float
    has_valid_signal: bool
    historical_oos_approved: bool
    calibrated_same_target_and_exit: bool
    valid_model_prediction: bool
    historical_market_eligible: bool
    training_label_embargo_verified: bool

    @property
    def identity(self) -> tuple[str,str,str,str]:
        return (self.pair,self.family,self.side,self.exit_policy)

@dataclass(frozen=True)
class RankPolicy:
    # A shared target must express AFTER native expected fee/funding, not a
    # random model score or future true realized profit.
    required_target: str = "net_return_fraction_after_base_costs"
    required_exit_policy: str = "frozen_60m_exit_after_2pct_stop"
    minimum_conservative_edge_fraction: float = 0.002
    maximum_uncertainty_fraction: float = 0.015
    maximum_additional_cost_fraction: float = 0.01
    maximum_downside_risk_fraction: float = 0.025
    minimum_liquidity_multiple: float = 10.0
    downside_penalty_weight: float = 0.5
    max_model_age_hours: float = 24.0 * 8.0

@dataclass(frozen=True)
class RankedDecision:
    action: str
    winner: tuple[str,str,str,str] | None
    winning_risk_adjusted_after_cost_fraction: float | None
    candidates_considered: int
    eligible_candidates: int
    rejected_reasons: tuple[tuple[str,str],...]
    research_only: bool = True

    @property
    def is_no_trade(self) -> bool:
        return self.action=="NO_TRADE"


def _utc(value:str) -> datetime:
    if not isinstance(value,str) or not value:
        raise ValueError("REQUIRE_EXPLICIT_UTC_ISO_TIME")
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset()!=timedelta(0):
        raise ValueError("UTC_OFFSET_REQUIRED")
    return d.astimezone(timezone.utc)

def _policy_valid(p:RankPolicy) -> None:
    floats=(p.minimum_conservative_edge_fraction,p.maximum_uncertainty_fraction,
            p.maximum_additional_cost_fraction,p.maximum_downside_risk_fraction,
            p.minimum_liquidity_multiple,p.downside_penalty_weight,p.max_model_age_hours)
    if not p.required_target or not p.required_exit_policy:
        raise ValueError("POLICY_NEEDS_SAME_TARGET_AND_EXIT")
    if not all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in floats):
        raise ValueError("INVALID_RISK_POLICY")
    if p.max_model_age_hours<=0 or p.minimum_liquidity_multiple<1:
        raise ValueError("UNSAFE_RISK_POLICY")

def choose_global_opportunity(
    candidates:Sequence[Opportunity],
    *, decision_at_utc:str,
    original_25_pairs:Sequence[str],
    portfolio_has_open_position:bool,
    policy:RankPolicy=RankPolicy(),
) -> RankedDecision:
    """Rank ONLY time-causal valid signals globally, or select NO TRADE.

    Models trained on a last feature whose future 60m label is not yet
    observable as-of model fit are rejected (caller must additionally provide
    proof that the actual purged model split / predictor has no lookahead).
    Every coin, strategy and side is eligible for the SAME one-slot contest.
    This function never learns anything from a future realized trade outcome.
    """
    _policy_valid(policy)
    now=_utc(decision_at_utc)
    if now.minute%5 or now.second or now.microsecond:
        raise ValueError("NOT_A_SHARED_5M_DECISION_TIME")
    if type(portfolio_has_open_position) is not bool:
        raise ValueError("EXPLICIT_PORTFOLIO_OCCUPANCY_REQUIRED")
    allowed=tuple(original_25_pairs)
    if (len(allowed)!=25 or len(set(allowed))!=25 or
        any(not isinstance(x,str) or not x.endswith("/USDT:USDT") for x in allowed)):
        raise ValueError("REQUIRES_VERIFIED_FIXED_ORIGINAL_25_PAIRLIST")
    if len(candidates)>5000:
        raise ValueError("UNBOUNDED_FORECAST_BATCH")
    if not isinstance(candidates,(tuple,list)):
        raise ValueError("IMMUTABLE_SNAPSHOT_OF_CANDIDATES_REQUIRED")
    if len({c.identity for c in candidates})!=len(candidates):
        raise ValueError("DUPLICATE_COIN_STRATEGY_SIDE_CANDIDATES")
    if portfolio_has_open_position:
        return RankedDecision("NO_TRADE",None,None,len(candidates),0,
                              (("PORTFOLIO","ONE_GLOBAL_SLOT_ALREADY_OCCUPIED"),))
    chosen=[]
    rejected=[]
    for c in candidates:
        identity="|".join(c.identity)
        reason=""
        if c.pair not in allowed or c.family not in FAMILIES or c.side not in SIDES:
            reason="UNKNOWN_COIN_FAMILY_OR_SIDE"
        elif c.regime not in REGIMES:
            reason="UNKNOWN_REGIME"
        elif c.regime=="high_volatility":
            reason="VOLATILITY_RISK_NO_TRADE"
        elif c.regime=="trend_up" and c.side=="short":
            reason="SIDE_AGAINST_REGIME"
        elif c.regime=="trend_down" and c.side=="long":
            reason="SIDE_AGAINST_REGIME"
        elif not c.has_valid_signal:
            reason="NO_FROZEN_TECHNICAL_ENTRY_SIGNAL"
        elif not c.historical_market_eligible:
            reason="MARKET_NOT_POINT_IN_TIME_ELIGIBLE"
        elif not c.historical_oos_approved:
            reason="STRATEGY_NOT_HISTORICALLY_VALIDATED"
        elif not c.calibrated_same_target_and_exit or \
             c.prediction_target!=policy.required_target or \
             c.exit_policy!=policy.required_exit_policy:
            reason="INCOMPARABLE_FORECAST_TARGET_OR_EXIT"
        elif not c.training_label_embargo_verified or not c.valid_model_prediction:
            reason="UNTRUSTWORTHY_OR_LOOKAHEAD_MODEL"
        else:
            values=(c.predicted_net_return_fraction,c.uncertainty_fraction,
                    c.additional_execution_cost_fraction,c.downside_risk_fraction,
                    c.available_market_depth_usdt,c.intended_stake_usdt)
            if not all(type(x) in (int,float) and math.isfinite(x) for x in values):
                reason="NONFINITE_OR_NONNUMERIC_FORECAST"
            elif (c.uncertainty_fraction<0 or
                  c.uncertainty_fraction>policy.maximum_uncertainty_fraction or
                  c.additional_execution_cost_fraction<0 or
                  c.additional_execution_cost_fraction>policy.maximum_additional_cost_fraction or
                  c.downside_risk_fraction<0 or
                  c.downside_risk_fraction>policy.maximum_downside_risk_fraction or
                  c.intended_stake_usdt<=0 or
                  c.available_market_depth_usdt < c.intended_stake_usdt*policy.minimum_liquidity_multiple):
                reason="UNSAFE_UNCERTAINTY_COST_RISK_OR_LIQUIDITY"
            else:
                try:
                    signal_time=_utc(c.signal_candle_closed_utc)
                    predicted_at=_utc(c.prediction_generated_utc)
                    trained_through=_utc(c.model_training_last_feature_utc)
                    fit_done=_utc(c.model_fitted_utc)
                except (ValueError,TypeError):
                    reason="MALFORMED_CAUSAL_TIME"
                else:
                    if not (now-FIVE_MINUTES<=signal_time<=now and
                            now-FIVE_MINUTES<=predicted_at<=now and
                            trained_through+LABEL_HORIZON<=fit_done<=predicted_at and
                            predicted_at-fit_done<=timedelta(hours=policy.max_model_age_hours)):
                        reason="FUTURE_STALE_OR_UNPURGED_MODEL_TIME"
                    else:
                        conservative=(c.predicted_net_return_fraction
                                      -c.uncertainty_fraction
                                      -c.additional_execution_cost_fraction
                                      -policy.downside_penalty_weight*c.downside_risk_fraction)
                        if conservative<=policy.minimum_conservative_edge_fraction:
                            reason="NO_POSITIVE_RISK_ADJUSTED_EDGE"
                        else:
                            chosen.append((conservative,c.identity))
        if reason:
            rejected.append((identity,reason))
    if not chosen:
        return RankedDecision("NO_TRADE",None,None,len(candidates),0,tuple(rejected))
    # The same score semantics, one timestamp and one shared portfolio slot
    # are what make "best of 25 coins × many strategies" meaningful.
    selected=sorted(chosen,key=lambda x:(-x[0],x[1]))[0]
    return RankedDecision("SELECT",selected[1],round(selected[0],10),
                          len(candidates),len(chosen),tuple(rejected))
