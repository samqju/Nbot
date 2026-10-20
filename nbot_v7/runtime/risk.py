"""Independent immutable risk envelope. Models have no mutation authority."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RiskPolicy:
    notional_usdt:float=1000
    initial_equity_usdt:float=10000
    max_daily_loss_usdt:float=200
    max_drawdown_fraction:float=.10
    max_age_ms:int=300000
    stop_fraction:float=.02
    take_fraction:float=.03
    max_hold_ms:int=3600000
    fee_each:float=.0005
    slippage_each:float=.0001

    def __post_init__(self):
        values=(self.notional_usdt,self.initial_equity_usdt,self.max_daily_loss_usdt,
                self.max_drawdown_fraction,self.stop_fraction,self.take_fraction,self.fee_each,self.slippage_each)
        if (not all(isfinite(x) for x in values) or not 0<self.notional_usdt<=self.initial_equity_usdt
            or self.max_daily_loss_usdt<=0 or not 0<self.max_drawdown_fraction<1
            or not 0<self.stop_fraction<1 or self.take_fraction<=0
            or self.max_hold_ms<=0 or self.max_age_ms<=0 or min(self.fee_each,self.slippage_each)<0):
            raise ValueError("INVALID_RISK_ENVELOPE")

    def check(self,state,decision_ms,now_ms,source_ready=True):
        if state["kill"]:return "KILL_SWITCH"
        if not source_ready:return "SOURCE_HOLD"
        if decision_ms>now_ms or now_ms-decision_ms>self.max_age_ms:return "STALE_OR_FUTURE_INPUT"
        if state["position"] is not None:return "ONE_SLOT_OCCUPIED"
        if state["pending"] is not None:return "UNRECONCILED_ORDER"
        if state["equity"]<self.notional_usdt:return "INSUFFICIENT_CAPITAL"
        if state["daily_net"]<=-self.max_daily_loss_usdt:return "DAILY_LOSS_LIMIT"
        if (state["peak"]-state["equity"])/state["peak"]>=self.max_drawdown_fraction:return "DRAWDOWN_LIMIT"
        return None
