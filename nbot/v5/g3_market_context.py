"""V5-03 deterministic, causal BTC/coin regime and structure CLASSIFIER.

No orders, models, paper portfolios, return labels, live sockets or network.
Consumes only 96 already-closed five-minute candles and ORIGINAL G2 witnessed
quote/trade receipts. The BTC feed is a mandatory conditioning variable:
unavailable BTC NEVER turns into a fabricated neutral/zero-return feature.
Thresholds are frozen hypotheses, NOT estimated edge or strategy advice.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from typing import Mapping, Sequence

from nbot.v5.observation_contract import INTERVAL_MS

FEATURE_VERSION = "NBOT_V5_G3_BTC_COIN_CONTEXT_V1"
BARS = 96
MAX_SYMBOLS = 50
MAX_QUOTE_AGE = 5_000
MAX_TRADE_AGE = 15_000
SPREAD_LIMIT = 0.01
REGIMES = ("SHOCK_UP", "SHOCK_DOWN", "TREND_UP", "TREND_DOWN",
           "RANGE", "TRANSITION", "UNKNOWN")
STRUCTURES = ("BREAKOUT_UP", "BREAKOUT_DOWN", "TREND_UP", "TREND_DOWN",
              "COMPRESSION", "RANGE", "TRANSITION", "UNKNOWN")
DIRECTIONS = ("LONG", "SHORT")


def _digest(v: object) -> str:
    body=json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)
    return hashlib.sha256(body.encode()).hexdigest()


def _valid_bars(rows: Sequence[Sequence] | None, event_ms: int) -> tuple[tuple, ...] | None:
    if not isinstance(rows,(tuple,list)) or len(rows)!=BARS:
        return None
    history=[]
    for i,bar in enumerate(rows):
        if not isinstance(bar,(tuple,list)) or len(bar)!=6:
            return None
        clock,*raw=bar
        if (type(clock) is not int or
                clock != event_ms-(BARS-1-i)*INTERVAL_MS or
                any(type(n) not in (int,float) for n in raw)):
            return None
        try:
            o,h,l,c,v=map(float,raw)
        except (ValueError,OverflowError,TypeError):
            return None
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
                min(o,h,l,c)<=0 or v<0 or h<max(o,c) or
                l>min(o,c) or l>h):
            return None
        history.append((clock,o,h,l,c,v))
    return tuple(history)


def _valid_feed(sample: Mapping | None, *, event_ms: int,
                decision_ms: int) -> tuple[str,...]:
    if not isinstance(sample,Mapping):
        return ("SOURCE_WITNESS_MISSING",)
    try:
        at=sample["sampled_at_ms"]
        src=sample["source"]
        if not isinstance(src,Mapping):
            return ("SOURCE_WITNESS_INVALID",)
        if (type(at) is not int or
                not event_ms+INTERVAL_MS <= at <= decision_ms or
                at >= event_ms+2*INTERVAL_MS):
            return ("SOURCE_SAMPLE_CLOCK_INVALID",)
        reasons=[]
        for route in ("market","public"):
            if type(src.get(route+"_connected")) is not bool or not src[route+"_connected"]:
                reasons.append("SOURCE_"+route.upper()+"_DISCONNECTED")
            if type(src.get(route+"_epoch")) is not int or src[route+"_epoch"]<1:
                reasons.append("SOURCE_"+route.upper()+"_EPOCH_UNKNOWN")
        for name,limit in (("quote",MAX_QUOTE_AGE),("trade",MAX_TRADE_AGE)):
            when=src.get(name+"_received_ms")
            if type(when) is not int or not 0<=at-when<=limit:
                reasons.append(name.upper()+"_RECEIPT_NOT_ASOF")
        bid,ask=src.get("bid"),src.get("ask")
        if (type(bid) not in (int,float) or type(ask) not in (int,float)
                or not math.isfinite(bid) or not math.isfinite(ask)
                or bid<=0 or ask<=bid or (ask-bid)/bid>SPREAD_LIMIT):
            reasons.append("QUOTE_SPREAD_INVALID")
        return tuple(sorted(set(reasons)))
    except (KeyError,TypeError,ValueError):
        return ("SOURCE_WITNESS_INVALID",)


def _features(rows: tuple[tuple, ...]) -> dict[str,float]:
    closes=[x[4] for x in rows]
    last=closes[-1]
    true_ranges=[
        max(row[2]-row[3],abs(row[2]-prev[4]),abs(row[3]-prev[4]))
        for prev,row in zip(rows[-15:-1],rows[-14:])
    ]
    atr=sum(true_ranges)/len(true_ranges)/last
    rets={
        "return_5m": last/closes[-2]-1,
        "return_15m": last/closes[-4]-1,
        "return_1h": last/closes[-13]-1,
        "return_4h": last/closes[-49]-1,
        "atr14_fraction": atr,
        "sma12_fraction": sum(closes[-12:])/12/last-1,
        "sma48_fraction": sum(closes[-48:])/48/last-1,
        "range12_fraction":(max(r[2] for r in rows[-12:])-
                             min(r[3] for r in rows[-12:]))/last,
        "range48_fraction":(max(r[2] for r in rows[-48:])-
                             min(r[3] for r in rows[-48:]))/last,
    }
    return rets


def _btc_regime(v: Mapping[str,float]) -> tuple[str,float]:
    atr=v["atr14_fraction"]
    if atr<=0:
        return ("UNKNOWN",0.0)
    r5,r1,r4=v["return_5m"],v["return_1h"],v["return_4h"]
    shock_cut=max(0.0075,2.0*atr)
    if abs(r5)>=shock_cut:
        label="SHOCK_UP" if r5>0 else "SHOCK_DOWN"
        strength=min(1.,abs(r5)/shock_cut)
        return (label,round(.60+.38*strength,4))
    hour_cut=max(0.0025,.65*atr)
    four_cut=max(0.005,1.2*atr)
    hour_dir=1 if r1>hour_cut else -1 if r1 < -hour_cut else 0
    four_dir=1 if r4>four_cut else -1 if r4 < -four_cut else 0
    if hour_dir and four_dir and hour_dir!=four_dir:
        return ("TRANSITION",.5)
    if hour_dir and four_dir==hour_dir:
        confirm=(v["sma12_fraction"]-v["sma48_fraction"])*hour_dir
        if confirm>0:
            strength=min(1.,abs(r1)/max(hour_cut,1e-9)/4)
            return ("TREND_UP" if hour_dir==1 else "TREND_DOWN",
                    round(.60+.35*strength,4))
        return ("TRANSITION",.5)
    if abs(r4)<four_cut and abs(r1)<hour_cut:
        return ("RANGE",.6)
    return ("TRANSITION",.4)


def _swings(rows: tuple[tuple,...]) -> tuple[float|None,float|None,int|None,int|None]:
    """Pivot confirmed using two future-neighbour bars that ALREADY closed.

    Never look past event bar; a swing on the last two candles is unconfirmed.
    """
    high=low=None
    hi_at=lo_at=None
    for i in range(2,len(rows)-2):
        top=rows[i][2]
        bottom=rows[i][3]
        if all(top>rows[j][2] for j in (i-2,i-1,i+1,i+2)):
            high,hi_at=top,rows[i][0]
        if all(bottom<rows[j][3] for j in (i-2,i-1,i+1,i+2)):
            low,lo_at=bottom,rows[i][0]
    return high,low,hi_at,lo_at


def _coin_structure(rows:tuple[tuple,...],v:Mapping[str,float]) -> dict:
    high,low,hi_at,lo_at=_swings(rows)
    now=rows[-1][4]
    prev=rows[-2][4]
    r1,r4=v["return_1h"],v["return_4h"]
    atr=v["atr14_fraction"]
    top=high is not None and prev<=high and now>high
    down=low is not None and prev>=low and now<low
    if top:
        label="BREAKOUT_UP"
    elif down:
        label="BREAKOUT_DOWN"
    elif v["range12_fraction"] < max(.004,.55*v["range48_fraction"]):
        label="COMPRESSION"
    elif r1>max(.0025,.65*atr) and r4>max(.005,1.2*atr):
        label="TREND_UP"
    elif r1< -max(.0025,.65*atr) and r4< -max(.005,1.2*atr):
        label="TREND_DOWN"
    elif abs(r1) < max(.0025,.65*atr) and abs(r4)<max(.005,1.2*atr):
        label="RANGE"
    else:
        label="TRANSITION"
    return {
        "structure":label,
        "last_confirmed_swing_high":high,
        "last_confirmed_swing_low":low,
        "swing_high_at_ms":hi_at,
        "swing_low_at_ms":lo_at,
        "swing_confirmation_right_bars":2,
    }


def classify_event(*, event_open_ms:int, decision_at_ms:int,
                   selected_symbols: Sequence[str],
                   candles:Mapping[str,Sequence[Sequence] | None],
                   witnesses:Mapping[str,Mapping]) -> dict:
    """Return one G3 context per frozen selected coin; all fail closed."""
    if (type(event_open_ms) is not int or event_open_ms<0
            or event_open_ms%INTERVAL_MS or
            type(decision_at_ms) is not int or
            decision_at_ms<event_open_ms+INTERVAL_MS or
            decision_at_ms>=event_open_ms+2*INTERVAL_MS):
        raise ValueError("G3_EVENT_CLOCK_INVALID")
    if (not isinstance(selected_symbols,(tuple,list))
            or not 2<=len(selected_symbols)<=MAX_SYMBOLS
            or tuple(sorted(set(selected_symbols)))!=tuple(selected_symbols)
            or "BTCUSDT" not in selected_symbols
            or any(not isinstance(s,str) or not s.endswith("USDT") for s in selected_symbols)):
        raise ValueError("G3_FROZEN_COHORT_INVALID")
    symbols=tuple(selected_symbols)
    if set(candles)-set(symbols) or set(witnesses)-set(symbols):
        raise ValueError("G3_FOREIGN_SOURCE_SYMBOL")
    validated={}
    reasons={}
    for s in symbols:
        bars=_valid_bars(candles.get(s),event_open_ms)
        bad=list(_valid_feed(witnesses.get(s),event_ms=event_open_ms,
                             decision_ms=decision_at_ms))
        if bars is None:
            bad.append("CLOSED_CANDLE_HISTORY_NOT_CAUSAL")
        elif _features(bars)["atr14_fraction"]<=0:
            bad.append("VOLATILITY_ZERO")
        validated[s]=bars
        reasons[s]=tuple(sorted(set(bad)))
    btc=validated["BTCUSDT"]
    btc_good=not reasons["BTCUSDT"]
    btc_v=_features(btc) if btc_good else None
    btc_regime,confidence=_btc_regime(btc_v) if btc_good else ("UNKNOWN",0.0)
    btc_good=btc_good and btc_regime!="UNKNOWN"
    raw_returns={
        s:_features(validated[s])["return_1h"]
        for s in symbols if not reasons[s]
    }
    required=max(10,math.ceil(.8*len(symbols)))
    breadth_ok=len(raw_returns)>=required and btc_good
    breadth=(sum((r>0)-(r<0) for r in raw_returns.values())/len(raw_returns)
             if breadth_ok else None)
    selected_result={}
    for symbol in symbols:
        hold=list(reasons[symbol])
        if not btc_good:
            hold.append("BTC_CONTEXT_UNAVAILABLE")
        if not breadth_ok:
            hold.append("BREADTH_SOURCE_INCOMPLETE")
        if hold:
            selected_result[symbol]={
                "state":"UNKNOWN","structure":"UNKNOWN",
                "confidence_score":0.0,
                "feature_availability":"UNAVAILABLE",
                "reasons":sorted(set(hold)),
                "relative_momentum_1h":None,
                "btc_relative_pattern_long":"UNAVAILABLE",
                "btc_relative_pattern_short":"UNAVAILABLE",
                "features":None,"confirmed_swings":None,
            }
            continue
        f=_features(validated[symbol])
        structure=_coin_structure(validated[symbol],f)
        rel=f["return_1h"]-btc_v["return_1h"]
        # Repaired conceptual BTC-relative contract: explicit comparison is
        # possible only with valid BTC and coin source, never '0 if missing'.
        threshold=max(.001,.25*btc_v["atr14_fraction"])
        long_state="MATCH" if rel>threshold else "NO_MATCH"
        short_state="MATCH" if rel< -threshold else "NO_MATCH"
        selected_result[symbol]={
            "state":"AVAILABLE","structure":structure["structure"],
            "confidence_score":round(.6+.3*min(1.,len(raw_returns)/len(symbols)),4),
            "feature_availability":"AVAILABLE",
            "reasons":[],
            "relative_momentum_1h":round(rel,10),
            "btc_relative_pattern_long":long_state,
            "btc_relative_pattern_short":short_state,
            "features":{k:round(v,10) for k,v in f.items()},
            "confirmed_swings":{k:v for k,v in structure.items() if k!="structure"},
        }
    payload={
        "version":FEATURE_VERSION,
        "event_open_ms":event_open_ms,
        "valid_from_ms":decision_at_ms,
        "source_grade":"G2_LOCAL_PUBLIC_WSS_REST_WITNESS_NOT_SIGNED",
        "cohort_digest":_digest({"symbols":symbols}),
        "btc":{"regime":btc_regime if btc_good else "UNKNOWN",
               "confidence_score":confidence if btc_good else 0.,
               "valid":btc_good,
               "reasons":list(reasons["BTCUSDT"]),
               "features":{k:round(v,10) for k,v in btc_v.items()} if btc_good else None},
        "breadth_1h":round(breadth,10) if breadth_ok else None,
        "breadth_sample":len(raw_returns),
        "breadth_minimum":required,
        "breadth_available":breadth_ok,
        "coins":selected_result,
        "candidate_cohort_size":len(symbols),
        "available_coin_count":sum(r["state"]=="AVAILABLE" for r in selected_result.values()),
        "unknown_coin_count":sum(r["state"]=="UNKNOWN" for r in selected_result.values()),
        "research_outcomes":0,
        "learning_labels_created":0,
        "recommendation_authority":"NONE",
        "order_authority":"NONE",
    }
    payload["feature_sha256"]=_digest(payload)
    return payload
