"""G4 USD-M public REST historically settled funding receipt validation.

A markPrice@1s indicative r is NOT a settled funding cost. A public
settlement is also NOT proof that a particular position paid funding.
Scientific position-cost allocation is a separate G6 obligation.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

SCHEMA="NBOT_V5_1_G4_SETTLED_PUBLIC_FUNDING_V1"

class FundingHold(ValueError):pass

@dataclass(frozen=True)
class FundingRow:
    symbol:str
    settled_at_ms:int
    rate:str

@dataclass(frozen=True)
class FundingEvidence:
    schema:str
    symbol:str
    received_at_ms:int
    source_path:str
    source_sha256:str
    settlements:tuple[FundingRow,...]
    grade:str="PUBLIC_REST_SETTLED_HISTORY_NOT_POSITION_COST"
    financial_authority:str="NONE"
    qualified_virtual_costs:int=0

def verify_settled(*,symbol:str,raw:bytes,received_at_ms:int,path:str)->FundingEvidence:
    if type(symbol) is not str or not re.fullmatch(r"[A-Z0-9]{3,24}",symbol) or not symbol.endswith("USDT"):
        raise FundingHold("G4_FUNDING_SYMBOL_INVALID")
    if type(received_at_ms) is not int or received_at_ms<=0:
        raise FundingHold("G4_FUNDING_RECEIPT_TIME_INVALID")
    if path!=f"/fapi/v1/fundingRate?symbol={symbol}&limit=2":
        raise FundingHold("G4_FUNDING_ENDPOINT_NOT_PUBLIC_WHITELISTED")
    if type(raw) is not bytes or not 0<len(raw)<=256*1024:
        raise FundingHold("G4_FUNDING_BODY_TOO_LARGE")
    try:
        values=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(
            FundingHold("G4_FUNDING_NONFINITE_JSON")))
    except (ValueError,UnicodeError,TypeError) as exc:
        raise FundingHold("G4_FUNDING_JSON_INVALID") from exc
    if type(values) is not list or not 1<=len(values)<=2:
        raise FundingHold("G4_FUNDING_ROWS_INVALID")
    rows=[];prev=-1
    for r in values:
        if type(r) is not dict or r.get("symbol")!=symbol:
            raise FundingHold("G4_FUNDING_WRONG_SYMBOL")
        ts=r.get("fundingTime")
        if type(ts) is not int or ts<=prev or ts>received_at_ms or ts<=0:
            raise FundingHold("G4_FUNDING_MISSING_FUTURE_OR_UNSORTED_SETTLEMENT")
        rate=r.get("fundingRate")
        if type(rate) is not str or len(rate)>80:
            raise FundingHold("G4_FUNDING_RATE_FORMAT")
        try:v=Decimal(rate)
        except InvalidOperation as exc:
            raise FundingHold("G4_FUNDING_RATE_INVALID") from exc
        if not v.is_finite() or abs(v)>Decimal("0.10"):
            raise FundingHold("G4_FUNDING_RATE_NONFINITE_OR_IMPLAUSIBLE")
        rows.append(FundingRow(symbol,ts,rate));prev=ts
    return FundingEvidence(SCHEMA,symbol,received_at_ms,path,
                hashlib.sha256(raw).hexdigest(),tuple(rows))
