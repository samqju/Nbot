"""Strict past-only candle features and independent proposal families."""
from __future__ import annotations
from bisect import bisect_right
from statistics import fmean
from .data import Bar, BAR_MS

FAMILIES = (
    "momentum_3", "momentum_12", "breakout_12", "breakout_48",
    "reversal_3", "reversal_12", "volume_surge", "range_reject",
    "pullback", "trend_accel", "structure_generic", "neutral_grid",
    "V6_ema_cross","V6_donchian_breakout","V6_bollinger_reversion","V6_rsi_reversion",
    "V6_macd_momentum","V6_stochastic_reversal","V6_atr_breakout","V6_volume_trend",
)
HISTORY = 50

def _safe(x: float) -> float:
    return float(max(-1000, min(1000, x)))

def market_features(bars: list[Bar], i: int, btc: list[Bar], btc_times: list[int]) -> dict[str,float]:
    if i < HISTORY or i >= len(bars):
        raise ValueError("INSUFFICIENT_CAUSAL_HISTORY")
    v=bars
    p=v[i].c
    pct=lambda k: p / v[i-k].c - 1
    tr=fmean((v[j].h-v[j].l)/v[j].c for j in range(i-13,i+1))
    volbase=fmean(v[j].v for j in range(i-20,i))
    # BTC bar whose CLOSE is known at this candle's closing decision instant.
    bidx=bisect_right(btc_times, v[i].t)-1
    if bidx < 48 or btc[bidx].t != v[i].t or btc[bidx-48].t != btc[bidx].t-48*BAR_MS:
        raise ValueError("BTC_CONTEXT_NOT_READY")
    b=btc
    btc_r3=b[bidx].c/b[bidx-3].c-1
    btc_r12=b[bidx].c/b[bidx-12].c-1
    btc_r48=b[bidx].c/b[bidx-48].c-1
    btc_atr=fmean((b[j].h-b[j].l)/b[j].c for j in range(bidx-13,bidx+1))
    return {
        "r3":_safe(pct(3)),"r12":_safe(pct(12)),"r48":_safe(pct(48)),
        "atr":_safe(tr),"volume_ratio":_safe(v[i].v/max(volbase,1e-12)),
        "range_12":_safe((max(v[j].h for j in range(i-11,i+1))-
                          min(v[j].l for j in range(i-11,i+1)))/p),
        "body":_safe((v[i].c-v[i].o)/p),
        "btc_r3":_safe(btc_r3),"btc_r12":_safe(btc_r12),"btc_r48":_safe(btc_r48),
        "btc_atr":_safe(btc_atr),"vs_btc":_safe(pct(12)-btc_r12),
        "utc_hour":float((v[i].t//3_600_000)%24),
    }

def btc_regime(x:dict) -> str:
    return "up" if x["btc_r48"] > .008 else "down" if x["btc_r48"] < -.008 else "range"

def proposals(bars: list[Bar],i:int,x:dict) -> list[tuple[str,str]]:
    """Concurrently generate research candidate hypotheses; never order instructions."""
    r3,r12,r48=x["r3"],x["r12"],x["r48"]
    s=[]
    def add(name,side,cond):
        if cond:s.append((name,side))
    add("momentum_3","LONG",r3>.006 and r12>0)
    add("momentum_3","SHORT",r3<-.006 and r12<0)
    add("momentum_12","LONG",r12>.012)
    add("momentum_12","SHORT",r12<-.012)
    old12=bars[i-12:i]
    old48=bars[i-48:i]
    add("breakout_12","LONG",bars[i].c>max(b.h for b in old12))
    add("breakout_12","SHORT",bars[i].c<min(b.l for b in old12))
    add("breakout_48","LONG",bars[i].c>max(b.h for b in old48))
    add("breakout_48","SHORT",bars[i].c<min(b.l for b in old48))
    add("reversal_3","LONG",r3<-.008 and x["body"]>.002)
    add("reversal_3","SHORT",r3>.008 and x["body"]<-.002)
    add("reversal_12","LONG",r12<-.025 and r3>.001)
    add("reversal_12","SHORT",r12>.025 and r3<-.001)
    add("volume_surge","LONG",x["volume_ratio"]>2.2 and x["body"]>.003)
    add("volume_surge","SHORT",x["volume_ratio"]>2.2 and x["body"]<-.003)
    add("range_reject","LONG",r12<-.005 and x["body"]>.003)
    add("range_reject","SHORT",r12>.005 and x["body"]<-.003)
    add("pullback","LONG",r48>.015 and r3<-.003 and x["body"]>0)
    add("pullback","SHORT",r48<-.015 and r3>.003 and x["body"]<0)
    add("trend_accel","LONG",r48>.012 and r12>.008 and r3>.003)
    add("trend_accel","SHORT",r48<-.012 and r12<-.008 and r3<-.003)
    # Independent broad structure/discovery head: not gated on legacy strategy names.
    add("structure_generic","LONG",x["body"]>.002 and x["volume_ratio"]>1.05)
    add("structure_generic","SHORT",x["body"]<-.002 and x["volume_ratio"]>1.05)
    # Frozen hourly long/short exploration, independent of family signal rules.
    # Shadow hypotheses only; ranking and abstention retain decision authority.
    if (bars[i].t + BAR_MS) % 3_600_000 == 0:
        s.extend((("neutral_grid", "LONG"), ("neutral_grid", "SHORT")))
    return s


def legacy_proposals(bars):
    """Exact V6 pure functions, reset on every gap, no framework/order imports."""
    import pandas as pd
    import numpy as np
    from .legacy_v6_signals import FAMILIES,library_indicators,library_signals
    result={}
    start=0
    for end in range(1,len(bars)+1):
        if end<len(bars) and bars[end].t==bars[end-1].t+BAR_MS:continue
        if end-start>=101:
            segment=bars[start:end]
            frame=pd.DataFrame({"open":[b.o for b in segment],"high":[b.h for b in segment],
                "low":[b.l for b in segment],"close":[b.c for b in segment],"volume":[b.v for b in segment]})
            indicators=library_indicators(frame)
            for family in FAMILIES:
                signals=library_signals(indicators,family)
                for side in ("long","short"):
                    for index in np.flatnonzero(signals[side].to_numpy(dtype=bool)):
                        result.setdefault(start+int(index),[]).append(("V6_"+family,side.upper()))
        start=end
    return result
