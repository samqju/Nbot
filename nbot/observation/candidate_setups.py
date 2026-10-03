"""Versioned, causal paper candidate rules. No exchange access or order authority.

Research supports broad families, not these exact intraday parameter choices.
A matched rule is a hypothesis; overlapping matches are not independent trades.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import statistics
from .context_learning import describe

VERSION = "PAPER_CANDIDATE_LIBRARY_V1"
INTERVAL_MS = 300_000
MAX_BARS = 96
MIN_BARS = 49


@dataclass(frozen=True)
class Candidate:
    id: str
    family: str
    evidence: str
    rule: str

    def tag(self):
        return {"id": self.id, "family": self.family, "library": VERSION}


# The precise thresholds below are experimental, even in a researched family.
REGISTRY = (
    Candidate("TREND_CONTINUATION_V1", "MOMENTUM", "FAMILY_RESEARCH", "Existing aligned 4h/15m trend proxy."),
    Candidate("TREND_PULLBACK_V1", "PULLBACK", "EXPERIMENTAL", "Existing 15m pullback against a 4h trend."),
    Candidate("STRETCHED_REVERSAL_V1", "REVERSAL", "EXPERIMENTAL", "Existing recovery after an ATR-normalised opposing move."),
    Candidate("VOLATILITY_EXPANSION_V1", "BREAKOUT", "EXPERIMENTAL", "Existing large-range candle moving in the trade direction."),
    Candidate("RELATIVE_STRENGTH_V1", "RELATIVE_MOMENTUM", "FAMILY_RESEARCH", "Existing side-aligned cross-sectional strength."),
    Candidate("DONCHIAN_BREAKOUT_V1", "BREAKOUT", "FAMILY_RESEARCH", "Close crosses the previous 20-bar high/low."),
    Candidate("BREAKOUT_RETEST_V1", "BREAKOUT", "EXPERIMENTAL", "Previous candle broke a 20-bar level; current wick retests within 0.25 ATR and closes beyond it."),
    Candidate("FAILED_BREAKOUT_V1", "REVERSAL", "EXPERIMENTAL", "Wick sweeps the opposite 20-bar extreme but the close returns inside."),
    Candidate("RANGE_EDGE_REJECTION_V1", "MEAN_REVERSION", "EXPERIMENTAL", "Quiet trend; reject outer 10% of a 20-bar range back through its outer 20%."),
    Candidate("BOLLINGER_REENTRY_V1", "MEAN_REVERSION", "EXPERIMENTAL", "Close returns inside the prior 20-close mean +/- 2 population standard deviations."),
    Candidate("RSI_RECLAIM_V1", "MEAN_REVERSION", "EXPERIMENTAL", "Simple 14-change RSI crosses back above 30/below 70."),
    Candidate("EMA_CROSS_V1", "MOMENTUM", "FAMILY_RESEARCH", "8 EMA crosses 21 EMA on completed closes."),
    Candidate("EMA_PULLBACK_V1", "PULLBACK", "EXPERIMENTAL", "8/21 EMA trend; candle touches the 8 EMA and closes back in trend direction."),
    Candidate("MACD_CROSS_V1", "MOMENTUM", "EXPERIMENTAL", "12/26 EMA MACD crosses its 9 EMA signal."),
    Candidate("SQUEEZE_BREAKOUT_V1", "BREAKOUT", "EXPERIMENTAL", "Previous 10-close deviation below half its prior 30-close deviation, followed by a 10-bar breakout."),
    Candidate("VOLUME_BREAKOUT_V1", "BREAKOUT", "EXPERIMENTAL", "20-bar breakout with base volume above twice the prior 20-bar median."),
    Candidate("VWAP_RECLAIM_V1", "MEAN_REVERSION", "EXPERIMENTAL", "Close crosses a fixed prior 20-bar volume-weighted typical price."),
    Candidate("INSIDE_BAR_BREAKOUT_V1", "BREAKOUT", "EXPERIMENTAL", "Previous candle lies strictly inside its mother candle; close breaks the mother's range."),
    Candidate("OUTSIDE_BAR_REVERSAL_V1", "REVERSAL", "EXPERIMENTAL", "Current candle expands both extremes, then closes beyond the previous close in the opposite candle direction."),
    Candidate("ENGULFING_REVERSAL_V1", "REVERSAL", "EXPERIMENTAL", "Opposing previous body is strictly engulfed in the trade direction."),
    Candidate("PIN_BAR_REJECTION_V1", "REVERSAL", "EXPERIMENTAL", "Rejection wick >=60% of range, body <=30%, close in directional outer 25%."),
    Candidate("MULTITIMEFRAME_TREND_V1", "MOMENTUM", "EXPERIMENTAL", "8/21 five-minute EMA and 3/6 fully closed UTC-aligned 15-minute averages agree."),
    Candidate("CONFIRMED_SWING_CONTINUATION_V1", "STRUCTURE", "EXPERIMENTAL", "Two confirmed two-left/two-right swing lows rise (highs fall); price breaks the previous candle in trend direction."),
    Candidate("BTC_RELATIVE_MOMENTUM_V1", "RELATIVE_MOMENTUM", "EXPERIMENTAL", "Coin's 1h return beats side-aligned BTC by >0.5 ATR, with agreeing 15m move."),
)
BY_ID = {item.id: item for item in REGISTRY}
CATALOG_DIGEST = hashlib.sha256(json.dumps([asdict(item) for item in REGISTRY], sort_keys=True).encode()).hexdigest()
FALLBACK = {"id": "MODEL_ONLY", "family": "MODEL_ONLY", "library": VERSION}


def ema(values, period):
    result = [values[0]]
    alpha = 2/(period+1)
    for value in values[1:]:
        result.append(result[-1] + alpha*(value-result[-1]))
    return result


def rsi(values):
    changes = [b-a for a,b in zip(values[-15:-1],values[-14:])]
    gains = sum(max(0., x) for x in changes)
    losses = sum(max(0., -x) for x in changes)
    if gains+losses == 0: return 50.
    return 100*gains/(gains+losses)


def load_histories(database, symbols, event_ms):
    """One bounded SQL read per event for all symbols; use only closed past bars."""
    symbols = sorted(set(symbols))
    if not symbols: return {}
    if len(symbols) > 500: raise ValueError("CANDIDATE_SYMBOL_LIMIT")
    placeholders = ",".join("?" for _ in symbols)
    with database.connection() as conn:
        rows = conn.execute(f"""
            SELECT symbol,event_open_ms,open_time_ms,close_time_ms,
                   open_price,high_price,low_price,close_price,base_volume
            FROM candles_5m WHERE event_open_ms BETWEEN ? AND ?
              AND symbol IN ({placeholders}) ORDER BY symbol,event_open_ms
            """, [event_ms-(MAX_BARS-1)*INTERVAL_MS,event_ms,*symbols]).fetchall()
    history = {}
    for symbol,t,opened,closed,o,h,l,c,v in rows:
        if (int(opened)!=int(t) or int(closed)!=int(t)+INTERVAL_MS-1
                or not all(math.isfinite(float(x)) for x in (o,h,l,c,v))
                or min(o,h,l,c)<=0 or v<0 or h<max(o,c) or l>min(o,c) or l>h):
            raise ValueError("CANDIDATE_CANDLE_INVALID")
        bars=history.setdefault(symbol,[])
        if bars and t-bars[-1][0]!=INTERVAL_MS:
            bars.clear()  # Only a contiguous suffix may feed an indicator.
        bars.append((int(t),float(o),float(h),float(l),float(c),float(v)))
    return {symbol:bars for symbol,bars in history.items() if bars and bars[-1][0]==event_ms}


def history_digest(bars):
    return hashlib.sha256(json.dumps(bars,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def technical_conditions(bars, side, vector):
    """Evaluate 19 named rules; 49..96 contiguous five-minute candles required."""
    if side not in {"LONG","SHORT"}: raise ValueError("CANDIDATE_SIDE_INVALID")
    if len(bars)<MIN_BARS: return {}
    if len(bars)>MAX_BARS: raise ValueError("CANDIDATE_HISTORY_LIMIT")
    for i,b in enumerate(bars):
        if (len(b)!=6 or not all(math.isfinite(float(x)) for x in b)
                or min(b[1:5])<=0 or b[5]<0 or b[2]<max(b[1],b[4])
                or b[3]>min(b[1],b[4]) or b[3]>b[2]
                or (i and b[0]-bars[i-1][0]!=INTERVAL_MS)):
            raise ValueError("CANDIDATE_HISTORY_INVALID")
    sign=1 if side=="LONG" else -1
    t,o,h,l,c,v=bars[-1]
    _,po,ph,pl,pc,pv=bars[-2]
    closes=[b[4] for b in bars]
    previous=bars[-21:-1]
    hi=max(b[2] for b in previous); lo=min(b[3] for b in previous)
    edge=hi if sign==1 else lo
    opposite=lo if sign==1 else hi
    wick=l if sign==1 else h
    directional=sign*(c-o)>0
    atr=statistics.fmean(max(b[2]-b[3],abs(b[2]-a[4]),abs(b[3]-a[4]))
                         for a,b in zip(bars[-15:-1],bars[-14:]))
    if atr<=0: return {}
    breakout=sign*(c-edge)>0 and sign*(pc-edge)<=0
    old=bars[-22:-2]
    old_edge=max(b[2] for b in old) if sign==1 else min(b[3] for b in old)
    fast=ema(closes,8); slow=ema(closes,21)
    macd=[a-b for a,b in zip(ema(closes,12),ema(closes,26))]
    signal=ema(macd,9)
    mean=statistics.fmean(closes[-21:-1]); sd=statistics.pstdev(closes[-21:-1])
    band=mean-sign*2*sd
    volume_total=sum(b[5] for b in previous)
    vwap=(sum((b[2]+b[3]+b[4])/3*b[5] for b in previous)/volume_total) if volume_total>0 else None
    # Group actual UTC intervals; ignore incomplete 15-minute groups.
    grouped={}
    for b in bars: grouped.setdefault(b[0]//900000,[]).append(b)
    quarters=[items[-1][4] for _,items in sorted(grouped.items())
              if len(items)==3 and items[0][0]%900000==0]
    pivots=[]
    for i in range(2,len(bars)-2):
        value=bars[i][3] if sign==1 else bars[i][2]
        neighbours=[bars[j][3] if sign==1 else bars[j][2] for j in (i-2,i-1,i+1,i+2)]
        if all(sign*(value-other)<0 for other in neighbours): pivots.append(value)
    width=h-l
    rejection=(min(o,c)-l if sign==1 else h-max(o,c))
    previous_direction=sign*(pc-po)<0
    result={
      "DONCHIAN_BREAKOUT_V1": breakout,
      "BREAKOUT_RETEST_V1": sign*(pc-old_edge)>0 and abs(wick-old_edge)<=.25*atr and sign*(c-old_edge)>0 and directional,
      "FAILED_BREAKOUT_V1": sign*(wick-opposite)<0 and sign*(c-opposite)>0 and directional,
      "RANGE_EDGE_REJECTION_V1": hi>lo and abs(closes[-2]-closes[-21])<atr and 0<=sign*(wick-opposite)<=.1*(hi-lo) and sign*(c-opposite)>.2*(hi-lo) and directional,
      "BOLLINGER_REENTRY_V1": sd>0 and sign*(pc-band)<0 and sign*(c-band)>=0 and directional,
      "RSI_RECLAIM_V1": (rsi(closes[:-1])<30<=rsi(closes)) if sign==1 else (rsi(closes[:-1])>70>=rsi(closes)),
      "EMA_CROSS_V1": sign*(fast[-2]-slow[-2])<=0 and sign*(fast[-1]-slow[-1])>0,
      "EMA_PULLBACK_V1": sign*(fast[-2]-slow[-2])>0 and sign*(wick-fast[-2])<=0 and sign*(c-fast[-2])>0 and directional,
      "MACD_CROSS_V1": sign*(macd[-2]-signal[-2])<=0 and sign*(macd[-1]-signal[-1])>0,
      "SQUEEZE_BREAKOUT_V1": statistics.pstdev(closes[-11:-1])<.5*statistics.pstdev(closes[-41:-11]) and sign*(c-(max(b[2] for b in bars[-11:-1]) if sign==1 else min(b[3] for b in bars[-11:-1])))>0,
      "VOLUME_BREAKOUT_V1": breakout and statistics.median(b[5] for b in previous)>0 and v>2*statistics.median(b[5] for b in previous),
      "VWAP_RECLAIM_V1": vwap is not None and sign*(pc-vwap)<=0 and sign*(c-vwap)>0 and directional,
      "INSIDE_BAR_BREAKOUT_V1": ph<bars[-3][2] and pl>bars[-3][3] and sign*(c-(bars[-3][2] if sign==1 else bars[-3][3]))>0,
      "OUTSIDE_BAR_REVERSAL_V1": h>ph and l<pl and directional and previous_direction and sign*(c-pc)>0,
      "ENGULFING_REVERSAL_V1": previous_direction and directional and sign*(o-pc)<=0 and sign*(c-po)>0,
      "PIN_BAR_REJECTION_V1": width>0 and rejection>=.6*width and abs(c-o)<=.3*width and (h-c if sign==1 else c-l)<=.25*width,
      "MULTITIMEFRAME_TREND_V1": len(quarters)>=6 and sign*(fast[-1]-slow[-1])>0 and sign*(statistics.fmean(quarters[-3:])-statistics.fmean(quarters[-6:]))>0,
      "CONFIRMED_SWING_CONTINUATION_V1": len(pivots)>=2 and sign*(pivots[-1]-pivots[-2])>0 and sign*(c-(ph if sign==1 else pl))>0 and sign*(fast[-1]-slow[-1])>0,
      "BTC_RELATIVE_MOMENTUM_V1": vector.get("candidate_btc_available",0)==1 and float(vector.get("ret_1h_side",0))-float(vector.get("btc_ret_1h_side",0))>.5*float(vector.get("atr14_frac",0))>0 and float(vector.get("ret_15m_side",0))>0,
    }
    return result


def matches(vector, side, bars):
    info=describe(vector)
    ids=[]
    legacy=info["setup"]+"_V1"
    if legacy in BY_ID: ids.append(legacy)
    ids.extend(name for name,active in technical_conditions(bars,side,vector).items() if active)
    return [BY_ID[name].tag() for name in sorted(set(ids))]


def tie_key(event_ms,symbol,side,candidate_id):
    """Rotate equally scored overlapping rules without extra trades or random state."""
    return hashlib.sha256(f"{VERSION}|{event_ms}|{symbol}|{side}|{candidate_id}".encode()).hexdigest()
