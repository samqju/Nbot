"""G4 FORWARD source route and frame quality contract, OFFLINE ONLY.

The 2026 Binance futures WSS split routes bookTicker high-frequency frames over
/public and regular aggTrade and mark/funding frames over /market. This pure
module designs subscriptions and verifies caller-received raw frame provenance.
It does NOT connect, persist, create labels, simulate fills or change G1 services.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from urllib.parse import quote

FORWARD_VERSION="NBOT_V5_G4_FORWARD_SOURCE_CONTRACT_V1"
MAX_MARKETS=50
MAX_FRAME=32768
AGE_LIMIT_MS=5000


def forward_stream_endpoints(symbols):
    if (not isinstance(symbols,(tuple,list)) or
            not 1<=len(symbols)<=MAX_MARKETS or
            len(set(symbols))!=len(symbols) or
            any(not isinstance(s,str) or not s.endswith("USDT")
                or not s.isalnum() or s!=s.upper() for s in symbols)):
        raise ValueError("G4_FORWARD_UNIVERSE_INVALID")
    selected=tuple(sorted(symbols))
    return {
        "public_bookticker": (
            "wss://fstream.binance.com/public/stream?streams=" +
            "/".join(f"{s.lower()}@bookTicker" for s in selected)),
        "market_aggtrade": (
            "wss://fstream.binance.com/market/stream?streams=" +
            "/".join(f"{s.lower()}@aggTrade" for s in selected)),
        "cohort_symbols":selected,
        "source_version":FORWARD_VERSION,
    }


@dataclass(frozen=True)
class FrameEvidence:
    state: str                  # SOURCE_RECORDED / HOLD
    route: str
    symbol: str
    source_epoch: int
    received_at_ms: int
    body_sha256: str
    reasons: tuple[str,...]
    agg_id: int|None = None
    underlying_first_trade_id: int|None = None
    underlying_last_trade_id: int|None = None
    event_time_ms: int|None = None
    source_grade: str = "PUBLIC_WSS_LOCAL_RECEPTION_NOT_EXECUTABLE_FILL"
    scored_outcomes: int = 0
    financial_authority: str = "NONE"


def _positive(v):
    if not isinstance(v,str) or len(v)>80:
        return False
    try:
        d=Decimal(v)
    except InvalidOperation:
        return False
    return d.is_finite() and d>0


def verify_frame(*, route:str, raw:bytes, received_at_ms:int,
                 source_epoch:int, selected_symbols,
                 prior_agg_id:int|None=None,
                 prior_last_trade_id:int|None=None) -> FrameEvidence:
    """Treat every epoch/disconnection/gap as independent evidence, no backfill.

    The caller must chronologically append raw frame and SHA in a protected
    receipt file; this pure function does not authenticate on-wire WSS TLS.
    """
    if route not in ("public_bookticker","market_aggtrade"):
        raise ValueError("G4_FORWARD_ROUTE_INVALID")
    if (type(received_at_ms) is not int or received_at_ms<=0 or
            type(source_epoch) is not int or source_epoch<=0):
        raise ValueError("G4_FORWARD_CLOCK_OR_EPOCH_INVALID")
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_FRAME:
        raise ValueError("G4_FORWARD_FRAME_BOUNDS_INVALID")
    source_sha=hashlib.sha256(raw).hexdigest()
    try:
        item=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise ValueError("G4_FORWARD_FRAME_JSON_INVALID") from exc
    if (not isinstance(item,dict) or not isinstance(item.get("data"),dict)
            or not isinstance(item.get("stream"),str)):
        raise ValueError("G4_FORWARD_COMBINED_SHAPE_INVALID")
    data=item["data"]
    symbol=data.get("s")
    selected=set(selected_symbols)
    issues=[]
    if symbol not in selected:
        issues.append("FOREIGN_SYMBOL")
    stream_expected=(symbol.lower()+"@bookTicker" if route=="public_bookticker"
                     else symbol.lower()+"@aggTrade") if isinstance(symbol,str) else None
    if item["stream"]!=stream_expected:
        issues.append("STREAM_SYMBOL_OR_TYPE_MISMATCH")
    event_time=data.get("E")
    if type(event_time) is not int or event_time>received_at_ms or received_at_ms-event_time>AGE_LIMIT_MS:
        issues.append("EVENT_CLOCK_MISSING_FUTURE_OR_STALE")
    if "st" in data and data["st"]!=1:
        issues.append("NOT_USDM_FUTURE")
    agg=first=last=None
    if route=="public_bookticker":
        if not (_positive(data.get("b")) and _positive(data.get("a"))
                and _positive(data.get("B")) and _positive(data.get("A"))):
            issues.append("BOOK_QUOTE_INVALID")
        else:
            if Decimal(data["b"])>=Decimal(data["a"]):
                issues.append("BOOK_CROSSED")
        if (prior_agg_id is not None or prior_last_trade_id is not None):
            issues.append("WRONG_STREAM_CURSOR")
    else:
        agg,first,last,at=(data.get(k) for k in ("a","f","l","T"))
        if (data.get("e")!="aggTrade" or
                any(type(v) is not int or v<0 for v in (agg,first,last,at)) or
                first>last or not _positive(data.get("p")) or
                not _positive(data.get("q")) or
                type(data.get("m")) is not bool):
            issues.append("AGGTRADE_ROW_INVALID")
        else:
            if at>received_at_ms or received_at_ms-at>AGE_LIMIT_MS:
                issues.append("TRADE_CLOCK_MISSING_FUTURE_OR_STALE")
            if prior_agg_id is not None:
                if type(prior_agg_id) is not int or agg!=prior_agg_id+1:
                    issues.append("AGGTRADE_ID_GAP_OR_REPLAY")
            if prior_last_trade_id is not None:
                if type(prior_last_trade_id) is not int or first!=prior_last_trade_id+1:
                    issues.append("UNDERLYING_TRADE_ID_GAP_OR_REPLAY")
    return FrameEvidence(
        state="HOLD" if issues else "SOURCE_RECORDED",
        route=route,symbol=str(symbol),source_epoch=source_epoch,
        received_at_ms=received_at_ms,body_sha256=source_sha,
        reasons=tuple(sorted(set(issues))),
        agg_id=agg,underlying_first_trade_id=first,
        underlying_last_trade_id=last,event_time_ms=event_time)
