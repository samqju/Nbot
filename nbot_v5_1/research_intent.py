"""G5 immutable, offline/synthetic-only prospective virtual-research plan.

NOT a Binance order, accepted fill, PnL, research economic label, G4
source-quality elevation or account authority. When G4 source gate is HOLD,
only explicit synthetic laboratory planning is permitted; the real source
admission seam deliberately returns HOLD until separately reviewed in G4.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from .core import INTERVAL_MS

VERSION="NBOT_V5_1_G5_INTENT_V1"
MAX_ACTIVE=40
MAX_DEEP=20
SIDES=frozenset(("LONG","SHORT"))
_DIGEST=re.compile(r"[a-f0-9]{64}\Z")
_SYMBOL=re.compile(r"[A-Z0-9]{3,24}\Z")


class ResearchHold(ValueError):pass


def number(s:str, *, strictly_positive:bool=True)->Decimal:
    if type(s) is not str or len(s)>64:
        raise ResearchHold("G5_DECIMAL_FORMAT")
    try:
        d=Decimal(s)
    except (InvalidOperation,ValueError) as exc:
        raise ResearchHold("G5_DECIMAL_INVALID") from exc
    if not d.is_finite() or (strictly_positive and d<=0):
        raise ResearchHold("G5_DECIMAL_NONPOSITIVE_OR_INFINITE")
    return d


def digest(value:object)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
           ensure_ascii=True,allow_nan=False).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class FrozenIntent:
    version:str
    symbol:str
    side:str
    event_open_ms:int
    declared_at_ms:int
    activates_at_ms:int
    expires_at_ms:int
    entry_reference:str
    stop:str
    target:str
    trail_activation_r:str
    trail_distance_r:str
    risk_r:str
    cohort_sha:str
    observation_sha:str
    source_epoch:int
    source_grade:str
    entry_convention:str
    fee_policy:str
    slippage_policy:str
    funding_policy:str
    intent_id:str
    research_only:bool=True
    financial_authority:str="NONE"

    def to_dict(self)->dict:
        return self.__dict__.copy()


def freeze_intent(
    *,symbol:str,side:str,event_open_ms:int,declared_at_ms:int,
    activates_at_ms:int,entry_reference:str,stop:str,target:str,
    horizon_ms:int,cohort_sha:str,observation_sha:str,
    source_epoch:int,source_grade:str,
    trail_activation_r:str="1.0",trail_distance_r:str="1.0",
    fee_policy:str="REQUIRE_VERIFIED_ENTRY_AND_EXIT_FEES",
    slippage_policy:str="REQUIRE_INDEPENDENT_QUOTES_AND_SLIPPAGE",
    funding_policy:str="REQUIRE_SETTLED_POSITION_SPECIFIC_FUNDING",
)->FrozenIntent:
    if (type(symbol) is not str or not _SYMBOL.fullmatch(symbol)
            or not symbol.endswith("USDT") or side not in SIDES
            or type(event_open_ms) is not int or event_open_ms<0
            or event_open_ms%INTERVAL_MS
            or type(declared_at_ms) is not int
            or not event_open_ms+INTERVAL_MS<=declared_at_ms
            or type(activates_at_ms) is not int
            or activates_at_ms<=declared_at_ms
            or type(horizon_ms) is not int
            or horizon_ms<INTERVAL_MS or horizon_ms>24*60*60*1000
            or type(source_epoch) is not int or source_epoch<=0):
        raise ResearchHold("G5_INTENT_CLOCK_OR_SIDE_INVALID")
    if any(type(s) is not str or not _DIGEST.fullmatch(s)
           for s in (cohort_sha,observation_sha)):
        raise ResearchHold("G5_PROVENANCE_DIGEST_INVALID")
    # Deliberately refuse real/mixed source authority while G4 parent HOLD.
    if source_grade!="SYNTHETIC_OFFLINE_TEST_ONLY":
        raise ResearchHold("G5_G4_ORIGINAL_SOURCE_GATE_NOT_QUALIFIED")
    if (fee_policy!="REQUIRE_VERIFIED_ENTRY_AND_EXIT_FEES" or
        slippage_policy!="REQUIRE_INDEPENDENT_QUOTES_AND_SLIPPAGE" or
        funding_policy!="REQUIRE_SETTLED_POSITION_SPECIFIC_FUNDING"):
        raise ResearchHold("G5_COST_DEFAULT_ZERO_FORBIDDEN")
    e=number(entry_reference);s=number(stop);t=number(target)
    activation=number(trail_activation_r)
    distance=number(trail_distance_r)
    if distance>Decimal("10") or activation>Decimal("10"):
        raise ResearchHold("G5_TRAIL_UNBOUNDED")
    if side=="LONG" and not s<e<t:
        raise ResearchHold("G5_LONG_GEOMETRY_INVALID")
    if side=="SHORT" and not t<e<s:
        raise ResearchHold("G5_SHORT_GEOMETRY_INVALID")
    risk=abs(e-s)
    if risk/e<Decimal("0.0001") or risk/e>Decimal(".15"):
        raise ResearchHold("G5_RISK_FRACTION_INVALID")
    expires=activates_at_ms+horizon_ms
    body={"version":VERSION,"symbol":symbol,"side":side,
          "event_open_ms":event_open_ms,"declared_at_ms":declared_at_ms,
          "activates_at_ms":activates_at_ms,"expires_at_ms":expires,
          "entry_reference":entry_reference,"stop":stop,"target":target,
          "trail_activation_r":trail_activation_r,
          "trail_distance_r":trail_distance_r,"risk_r":str(risk),
          "cohort_sha":cohort_sha,"observation_sha":observation_sha,
          "source_epoch":source_epoch,"source_grade":source_grade,
          "entry_convention":"HYPOTHETICAL_PRICE_REFERENCE_NO_FILL",
          "fee_policy":fee_policy,"slippage_policy":slippage_policy,
          "funding_policy":funding_policy}
    return FrozenIntent(**body,intent_id=digest(body))


def from_record(row:dict)->FrozenIntent:
    if type(row) is not dict or set(row)!=set(FrozenIntent.__dataclass_fields__):
        raise ResearchHold("G5_INTENT_RECORD_SCHEMA")
    try:
        result=FrozenIntent(**row)
        recreated=freeze_intent(symbol=result.symbol,side=result.side,
            event_open_ms=result.event_open_ms,declared_at_ms=result.declared_at_ms,
            activates_at_ms=result.activates_at_ms,
            horizon_ms=result.expires_at_ms-result.activates_at_ms,
            entry_reference=result.entry_reference,stop=result.stop,
            target=result.target,source_grade=result.source_grade,
            source_epoch=result.source_epoch,cohort_sha=result.cohort_sha,
            observation_sha=result.observation_sha,
            trail_activation_r=result.trail_activation_r,
            trail_distance_r=result.trail_distance_r,
            fee_policy=result.fee_policy,slippage_policy=result.slippage_policy,
            funding_policy=result.funding_policy)
    except (TypeError,ValueError) as exc:
        raise ResearchHold("G5_INTENT_TAMPER_OR_INVALID") from exc
    if result!=recreated:
        raise ResearchHold("G5_INTENT_IMMUTABILITY_MISMATCH")
    return result
