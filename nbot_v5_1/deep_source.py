"""G4 pure original PUBLIC USD-M WebSocket frame and source-epoch checks.

Official Binance routed WSS market/public stream docs verified 15 Oct 2026.
Raw TLS WebSocket bytes must be captured and independently replayed through
a source recorder. This parser alone CANNOT prove network TLS provenance,
continuous losslessness, fill prices or settled funding.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

SOURCE_SCHEMA="NBOT_V5_1_G4_PUBLIC_FRAME_V1"
ROUTES={"QUOTE":("/public","bookTicker"),
        "TRADE":("/market","aggTrade"),
        "MARK":("/market","markPrice@1s")}
MAX_FRAME=65536
MAX_AGE_MS=5000
_SYMBOL=re.compile(r"[A-Z0-9]{3,24}\Z")


class DeepSourceHold(ValueError):
    pass


def stream_urls(symbols: tuple[str,...]) -> dict[str,str]:
    if (type(symbols) is not tuple or not 1<=len(symbols)<=20
            or len(symbols)!=len(set(symbols)) or "BTCUSDT" not in symbols
            or any(type(s) is not str or not _SYMBOL.fullmatch(s)
                   or not s.endswith("USDT") for s in symbols)):
        raise DeepSourceHold("G4_SUBSCRIPTION_COHORT_INVALID")
    return {kind:"wss://fstream.binance.com"+route+"/stream?streams="+
             "/".join(f"{s.lower()}@{suffix}" for s in sorted(symbols))
            for kind,(route,suffix) in ROUTES.items()}


def _positive(x: object) -> Decimal:
    if type(x) is not str or len(x)>80:
        raise DeepSourceHold("G4_NUMERIC_FORMAT")
    try:
        num=Decimal(x)
    except InvalidOperation as exc:
        raise DeepSourceHold("G4_NUMERIC_INVALID") from exc
    if not num.is_finite() or num<=0:
        raise DeepSourceHold("G4_NONPOSITIVE_OR_NONFINITE")
    return num


@dataclass(frozen=True)
class DeepFrame:
    kind: str
    symbol: str
    route: str
    epoch: int
    received_at_ms: int
    event_at_ms: int
    sha256: str
    state: str
    reason: str | None
    agg_id: int | None
    first_trade_id: int | None
    last_trade_id: int | None
    source_grade: str = "PUBLIC_TLS_WSS_LOCAL_RAW_NOT_EXCHANGE_SIGNED"
    qualified_outcomes: int = 0
    order_authority: str = "NONE"


def verify_frame(
    *,kind:str,raw:bytes,received_at_ms:int,source_epoch:int,
    selected_symbols:tuple[str,...],
    prior_agg_id:int|None=None,prior_last_trade_id:int|None=None
) -> DeepFrame:
    if kind not in ROUTES:
        raise DeepSourceHold("G4_ROUTE_NOT_PUBLIC")
    if type(received_at_ms) is not int or received_at_ms<=0 or type(source_epoch) is not int or source_epoch<=0:
        raise DeepSourceHold("G4_EPOCH_OR_CLOCK")
    if type(raw) is not bytes or not 0<len(raw)<=MAX_FRAME:
        raise DeepSourceHold("G4_FRAME_BOUNDS")
    if type(selected_symbols) is not tuple or not selected_symbols or len(set(selected_symbols))!=len(selected_symbols) or len(selected_symbols)>20:
        raise DeepSourceHold("G4_SELECTED_INVALID")
    try:
        frame=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(DeepSourceHold("G4_NONFINITE_JSON")))
    except (ValueError,TypeError,UnicodeError) as exc:
        raise DeepSourceHold("G4_FRAME_JSON_INVALID") from exc
    if (type(frame) is not dict or type(frame.get("data")) is not dict
            or type(frame.get("stream")) is not str):
        raise DeepSourceHold("G4_COMBINED_PAYLOAD_REQUIRED")
    data=frame["data"]
    sym=data.get("s")
    issues=[]
    if type(sym) is not str or sym not in selected_symbols:
        issues.append("UNSUBSCRIBED_SYMBOL")
    expected=sym.lower()+"@"+ROUTES[kind][1] if type(sym) is str else ""
    if frame["stream"]!=expected:
        issues.append("ROUTE_SYMBOL_MISMATCH")
    event=data.get("E")
    if type(event) is not int or event<=0 or event>received_at_ms or received_at_ms-event>MAX_AGE_MS:
        issues.append("EVENT_FUTURE_OR_STALE")
    if data.get("st",1)!=1:
        issues.append("NOT_USDM_STREAM")
    agg=first=last=None
    if kind=="QUOTE":
        if prior_agg_id is not None or prior_last_trade_id is not None:
            issues.append("WRONG_STREAM_CURSOR")
        try:
            bid,ask,bqty,aqty=map(_positive,(data.get("b"),data.get("a"),data.get("B"),data.get("A")))
            if bid>=ask:
                issues.append("CROSSED_BOOK")
        except DeepSourceHold:
            issues.append("BAD_QUOTE")
    elif kind=="TRADE":
        agg,first,last,trade_at=(data.get(k) for k in ("a","f","l","T"))
        if (data.get("e")!="aggTrade" or
            any(type(x) is not int or x<0 for x in (agg,first,last,trade_at)) or
            (type(first) is int and type(last) is int and first>last) or
            type(data.get("m")) is not bool or
            type(event) is int and type(trade_at) is int and trade_at>received_at_ms):
            issues.append("BAD_AGGTRADE")
        try:
            _positive(data.get("p"));_positive(data.get("q"))
        except DeepSourceHold:
            issues.append("BAD_TRADE_PRICE_OR_QTY")
        if type(agg) is int and prior_agg_id is not None:
            if agg<=prior_agg_id:
                issues.append("AGG_ID_DUPLICATE_OR_REORDER")
            elif agg!=prior_agg_id+1:
                issues.append("AGG_ID_GAP")
        if type(first) is int and prior_last_trade_id is not None:
            if first>prior_last_trade_id+1:
                issues.append("TRADE_ID_GAP")
            if first<=prior_last_trade_id:
                issues.append("TRADE_ID_REORDER")
    else:
        if prior_agg_id is not None or prior_last_trade_id is not None:
            issues.append("WRONG_STREAM_CURSOR")
        if data.get("e")!="markPriceUpdate":
            issues.append("WRONG_MARK_EVENT")
        try:
            _positive(data.get("p"));_positive(data.get("i"))
            fund=data.get("r")
            if type(fund) is not str or abs(Decimal(fund))>Decimal(".1") or not Decimal(fund).is_finite():
                issues.append("INDICATIVE_FUNDING_INVALID")
        except (InvalidOperation,DeepSourceHold):
            issues.append("MARK_VALUE_INVALID")
        next_funding=data.get("T")
        if type(next_funding) is not int or type(event) is not int or next_funding<event or next_funding>received_at_ms+172800000:
            issues.append("FUNDING_CLOCK_INVALID")
    return DeepFrame(kind,sym if type(sym) is str else "",ROUTES[kind][0],source_epoch,
        received_at_ms,event if type(event) is int else -1,hashlib.sha256(raw).hexdigest(),
        "HOLD" if issues else "RECEIVED_UNQUALIFIED_LOCAL_WSS", "|".join(issues) or None,
        agg if type(agg) is int else None,
        first if type(first) is int else None,last if type(last) is int else None)
