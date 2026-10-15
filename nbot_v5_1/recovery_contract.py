"""G6 conservative USD-M public recovery: candles ≠ original tick/quote path.

USD-M /fapi/v1/klines current listed intervals start at 1m; no verified
1s history on this endpoint. Exact immutable 5m bars may repair a closed
context clock only; aggregate-trades from /fapi/v1/aggTrades within its
48-hour availability may repair an *id-numbered trade chronology* but
NOT past bid/ask/mark/cost or G4 lost unsynced tail. No network on import.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from decimal import Decimal
import json
import re
from .core import INTERVAL_MS
from .observation import rest_closed_bar
from .research_intent import number

VERSION="NBOT_V5_1_G6_RECOVERY_V1"
ONE_SECOND_USDM_KLINES_VERIFIED=False
MAX_ROWS=1000
_SYMBOL=re.compile(r"[A-Z0-9]{3,24}\Z")


class RecoveryHold(ValueError):pass


def _json(raw:bytes, cap=2*1024*1024):
    if type(raw) is not bytes or not 0<len(raw)<=cap:
        raise RecoveryHold("G6_BODY_BOUNDS")
    try:
        return json.loads(raw,object_pairs_hook=_unique,
            parse_constant=lambda x: (_ for _ in ()).throw(
                 RecoveryHold("G6_NONFINITE_JSON")))
    except (ValueError,UnicodeError,TypeError) as e:
        if isinstance(e,RecoveryHold):raise
        raise RecoveryHold("G6_JSON_INVALID") from e

def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise RecoveryHold("G6_JSON_DUPLICATE_KEY")
        result[key]=value
    return result


@dataclass(frozen=True)
class RecoveryAssessment:
    schema:str
    symbol:str
    state:str
    reasons:tuple[str,...]
    rows:int
    first_ms:int|None
    last_ms:int|None
    body_sha256:str|None
    source_grade:str
    qualifies_original_first_touch:bool=False
    qualifies_quote_or_funding:bool=False
    financial_authority:str="NONE"


def completed_five_minute_bars(*,symbol:str,raw:bytes,
         received_at_ms:int,source_epoch:int,
         start_open_ms:int,end_open_ms:int)->RecoveryAssessment:
    if (type(symbol) is not str or not _SYMBOL.fullmatch(symbol) or
        type(received_at_ms) is not int or received_at_ms<=0 or
        type(source_epoch) is not int or source_epoch<0 or
        type(start_open_ms) is not int or type(end_open_ms) is not int or
        start_open_ms<0 or end_open_ms<start_open_ms or
        start_open_ms%INTERVAL_MS or end_open_ms%INTERVAL_MS or
        (end_open_ms-start_open_ms)//INTERVAL_MS+1>MAX_ROWS):
        raise RecoveryHold("G6_CANDLE_REQUEST_INVALID")
    data=_json(raw)
    if type(data) is not list or not 0<len(data)<=MAX_ROWS:
        raise RecoveryHold("G6_CANDLE_ROWS_INVALID")
    try:
        rows=[rest_closed_bar(symbol,x,known_at_ms=received_at_ms,
                   epoch=source_epoch,route="public_rest") for x in data]
    except (ValueError,TypeError) as e:
        raise RecoveryHold("G6_CANDLE_NOT_FINAL_OR_VALID") from e
    expected=list(range(start_open_ms,end_open_ms+1,INTERVAL_MS))
    opens=[x.open_ms for x in rows]
    reasons=[]
    if opens!=expected:reasons.append("G6_MISSING_DUPLICATE_OR_EXTRA_CANDLE")
    if any(x.received_at_ms<=x.close_ms for x in rows):
        reasons.append("G6_CANDLE_WAS_NOT_CLOSED")
    return RecoveryAssessment(VERSION,symbol,"CANDLE_CONTEXT_ONLY" if not reasons else "HOLD",
        tuple(reasons),len(rows),opens[0],opens[-1],sha256(raw).hexdigest(),
        "PUBLIC_FINALIZED_5M_CANDLE_NOT_TICK_OR_QUOTE")


def plan_public_aggtrade_gap(*,symbol:str,first_missing_agg_id:int,
                            until_at_ms:int,now_ms:int,limit:int=1000)->str:
    if (type(symbol) is not str or not _SYMBOL.fullmatch(symbol) or
        type(first_missing_agg_id) is not int or first_missing_agg_id<0 or
        type(until_at_ms) is not int or until_at_ms<1 or
        type(now_ms) is not int or now_ms<until_at_ms or
        now_ms-until_at_ms>48*3600*1000 or
        type(limit) is not int or not 1<=limit<=1000):
        raise RecoveryHold("G6_AGGTRADE_OUTSIDE_48H_OR_BAD_CURSOR")
    return f"/fapi/v1/aggTrades?symbol={symbol}&fromId={first_missing_agg_id}&limit={limit}"


def verify_aggtrade_gap(*,symbol:str,raw:bytes,from_agg_id:int,
            expected_last_agg_id:int,known_at_ms:int)->RecoveryAssessment:
    if (type(symbol) is not str or not _SYMBOL.fullmatch(symbol) or
        type(from_agg_id) is not int or from_agg_id<0 or
        type(expected_last_agg_id) is not int or expected_last_agg_id<from_agg_id or
        type(known_at_ms) is not int or known_at_ms<=0):
        raise RecoveryHold("G6_TRADE_GAP_RANGE_INVALID")
    values=_json(raw)
    if type(values) is not list or not 0<len(values)<=MAX_ROWS:
        raise RecoveryHold("G6_TRADE_GAP_ROWS_INVALID")
    if expected_last_agg_id-from_agg_id+1!=len(values):
        return RecoveryAssessment(VERSION,symbol,"HOLD",("G6_TRADES_NOT_COMPLETE",),
                   len(values),None,None,sha256(raw).hexdigest(),
                   "PUBLIC_AGGTRADES_PARTIAL_NEVER_QUOTES")
    t_first=t_last=None
    last_underlying=None
    reasons=[]
    for i,row in enumerate(values):
        if type(row) is not dict:raise RecoveryHold("G6_TRADE_ROW_TYPE")
        agg=row.get("a"); first=row.get("f"); last=row.get("l");at=row.get("T")
        if (type(agg) is not int or agg!=from_agg_id+i or
            any(type(x) is not int or x<0 for x in (first,last,at)) or
            first>last or at>known_at_ms or
            type(row.get("m")) is not bool):
            reasons.append("G6_BAD_TRADE_ID_TIME_OR_SIDE");break
        try:
            number(row.get("p"));number(row.get("q"))
        except ValueError:
            reasons.append("G6_INVALID_TRADE_PRICE_QTY");break
        if last_underlying is not None and first!=last_underlying+1:
            reasons.append("G6_UNDERLYING_TRADE_ID_GAP");break
        if t_last is not None and at<t_last:
            reasons.append("G6_TRADE_TIME_REVERSED");break
        if t_first is None:t_first=at
        t_last=at
        last_underlying=last
    return RecoveryAssessment(VERSION,symbol,"TRADE_CHRONOLOGY_ONLY" if not reasons else "HOLD",
        tuple(reasons),len(values),t_first,t_last,sha256(raw).hexdigest(),
        "PUBLIC_AGGTRADES_NOT_ORIGINAL_QUOTE_PATH")


def ambiguous_bar_first_touch(*,side:str,stop:str,target:str,
                    low:str,high:str,source_is_complete:bool)->tuple[str,...]:
    if side not in ("LONG","SHORT") or type(source_is_complete) is not bool:
        raise RecoveryHold("G6_BAR_SIDE_OR_SOURCE")
    s=number(stop);t=number(target);lo=number(low);hi=number(high)
    if lo>hi:raise RecoveryHold("G6_BAR_LOW_GT_HIGH")
    if not source_is_complete:
        return ("G6_INCOMPLETE_BAR_OR_UNKNOWN_INTERVAL",)
    stop_hit=(lo<=s if side=="LONG" else hi>=s)
    target_hit=(hi>=t if side=="LONG" else lo<=t)
    if stop_hit and target_hit:
        return ("G6_STOP_TARGET_ORDER_UNKNOWABLE_WITHIN_BAR",)
    if stop_hit or target_hit:
        return ("G6_BAR_TOUCH_ONLY_NO_EVENT_TIME_OR_QUOTE",)
    return ("G6_BAR_CONTEXT_NO_TOUCH",)


def one_second_usdm_recovery(*,interval:str)->None:
    # Explicitly block unsupported/unverified endpoint assumptions.
    raise RecoveryHold("G6_USDM_1S_KLINE_NOT_VERIFIED_USE_AGGTRADES_WITH_LIMITS")
