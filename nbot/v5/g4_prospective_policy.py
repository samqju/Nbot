"""G4 prospective, predeclared counterfactual entry/risk geometry contract.

A template must have been frozen before the five-minute event. Per-candidate
price, ATR, and quotes must be SOURCE AVAILABLE AT DECISION, never later.
Output is an unexecuted research policy intent, NOT a virtual fill or PnL.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re
from typing import Mapping

from nbot.v5.observation_contract import INTERVAL_MS

TEMPLATE_VERSION="NBOT_V5_G4_PROSPECTIVE_RISK_TEMPLATE_V1"
_HEX=re.compile(r"[a-f0-9]{64}\Z")
ENTRY_CONVENTION="ASOF_DECISION_BID_ASK_NO_FILL"
EXIT_POLICY_ID="FIRST_STOP_OR_TARGET_ELSE_HORIZON_PESSIMISTIC"
RISK_POLICY_ID="FROZEN_SOURCE_ATR_AND_MIN_FRACTION"
COST_POLICY_ID="REQUIRE_ORIGINAL_FEE_SPREAD_SLIPPAGE_FUNDING"
_RANGE={
    "atr_risk_multiple":(Decimal("0.1"),Decimal("10")),
    "target_r_multiple":(Decimal("0.1"),Decimal("10")),
    "min_risk_fraction":(Decimal("0.0001"),Decimal("0.10")),
}
_REQUIRED=frozenset((
    "declared_at_ms","activates_at_ms","horizon_ms","max_quote_age_ms",
    "atr_risk_multiple","target_r_multiple","min_risk_fraction",
    "entry_convention","exit_policy_id","risk_policy_id","cost_policy_id",
    "research_authority",
))


def _clock(x):
    return type(x) is int and x>=0


def _d(x, *, positive=False):
    if not isinstance(x,str) or len(x)>80:
        return None
    try:
        d=Decimal(x)
        return d if d.is_finite() and (not positive or d>0) else None
    except InvalidOperation:
        return None


def _sha(x):
    return isinstance(x,str) and bool(_HEX.fullmatch(x))


def _canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)


def _hash(x):
    return hashlib.sha256(_canonical(x).encode()).hexdigest()


@dataclass(frozen=True)
class FrozenResearchTemplate:
    version: str
    policy_sha256: str
    spec: dict
    order_authority: str = "NONE"
    training_authority: str = "NONE"


@dataclass(frozen=True)
class ResearchGeometry:
    state: str                  # GEOMETRY_RECORDED / HOLD
    reasons: tuple[str,...]
    decision_id: str
    template_sha256: str
    frozen_policy: dict | None = None
    order_authority: str = "NONE"
    training_authority: str = "NONE"
    scored_outcomes: int = 0


def freeze_template(spec: Mapping) -> FrozenResearchTemplate:
    if not isinstance(spec,Mapping) or set(spec)!=_REQUIRED:
        raise ValueError("G4_RISK_TEMPLATE_SHAPE_INVALID")
    declared,activate,horizon,age=(
        spec[k] for k in ("declared_at_ms","activates_at_ms",
                          "horizon_ms","max_quote_age_ms"))
    if (not _clock(declared) or not _clock(activate)
            or activate<declared+INTERVAL_MS
            or activate%INTERVAL_MS or
            not _clock(horizon) or
            not 3_600_000<=horizon<=24*3_600_000
            or horizon%INTERVAL_MS or
            type(age) is not int or not 0<=age<=5000):
        raise ValueError("G4_RISK_TEMPLATE_FUTURE_OR_HORIZON_INVALID")
    for field,(floor,ceiling) in _RANGE.items():
        value=_d(spec[field],positive=True)
        if value is None or not floor<=value<=ceiling:
            raise ValueError("G4_RISK_TEMPLATE_NUMERIC_INVALID")
    expected={
        "entry_convention":ENTRY_CONVENTION,
        "exit_policy_id":EXIT_POLICY_ID,
        "risk_policy_id":RISK_POLICY_ID,
        "cost_policy_id":COST_POLICY_ID,
        "research_authority":"OBSERVE_ONLY",
    }
    if any(spec.get(k)!=v for k,v in expected.items()):
        raise ValueError("G4_RISK_TEMPLATE_AUTHORITY_OR_RULES_INVALID")
    body={"version":TEMPLATE_VERSION,"spec":dict(spec)}
    return FrozenResearchTemplate(TEMPLATE_VERSION,_hash(body),dict(spec))


def bind_at_decision(*, template: FrozenResearchTemplate,
                     candidate: Mapping, g3_coin: Mapping,
                     quote: Mapping) -> ResearchGeometry:
    """Fail closed on all future/held source and as-of-event risk geometry.

    The candidate decision must post-date a frozen template's activation.
    Quotes at a later arbitrary exit may NOT be used to choose initial risk.
    """
    if (not isinstance(template,FrozenResearchTemplate) or
            not isinstance(candidate,Mapping) or
            not isinstance(g3_coin,Mapping) or
            not isinstance(quote,Mapping)):
        raise ValueError("G4_RISK_BIND_INPUT_INVALID")
    did=candidate.get("decision_id")
    if not _sha(did):
        raise ValueError("G4_RISK_DECISION_ID_INVALID")
    reasons=[]
    spec=template.spec
    if template.version!=TEMPLATE_VERSION or (
        _hash({"version":TEMPLATE_VERSION,"spec":spec})!=template.policy_sha256):
        reasons.append("TEMPLATE_TAMPERED")
    decision=candidate.get("decision_at_ms")
    event=candidate.get("event_open_ms")
    if (not _clock(decision) or not _clock(event)
            or event%INTERVAL_MS or decision<event+INTERVAL_MS
            or event<spec["activates_at_ms"] or decision<spec["activates_at_ms"]):
        reasons.append("CANDIDATE_BEFORE_POLICY_ACTIVATION_OR_EVENT_FINAL")
    side=candidate.get("side")
    symbol=candidate.get("symbol")
    if (candidate.get("status")!="OBSERVED" or
            candidate.get("reason_codes") or
            candidate.get("order_authority")!="NONE" or
            side not in ("LONG","SHORT") or
            not isinstance(symbol,str) or not symbol.endswith("USDT") or
            not _sha(candidate.get("source_digest"))):
        reasons.append("CANDIDATE_SOURCE_OR_IDENTITY_UNQUALIFIED")
    if (g3_coin.get("state")!="AVAILABLE"
            or g3_coin.get("reasons")
            or not _clock(g3_coin.get("valid_from_ms"))
            or (decision is not None and g3_coin.get("valid_from_ms")>decision)
            or not _sha(g3_coin.get("feature_sha256"))):
        reasons.append("G3_FEATURE_NOT_CAUSAL")
    atr=_d(g3_coin.get("atr14_fraction"),positive=True)
    if atr is None or atr>Decimal("0.2"):
        reasons.append("ATR_NOT_SOURCE_QUALIFIED")
    seen=quote.get("sampled_at_ms")
    if (quote.get("symbol")!=symbol or
            not _sha(quote.get("receipt_sha256"))
            or quote.get("source_verified") is not True
            or not _clock(seen) or not _clock(decision)
            or (not _clock(seen) or not 0<=decision-seen<=spec["max_quote_age_ms"])):
        reasons.append("ENTRY_QUOTE_STALE_FUTURE_OR_UNPROVEN")
    bid=_d(quote.get("bid"),positive=True)
    ask=_d(quote.get("ask"),positive=True)
    if bid is None or ask is None or bid>=ask:
        reasons.append("ENTRY_QUOTE_INVALID")
    if reasons:
        return ResearchGeometry("HOLD",tuple(sorted(set(reasons))),
                                did,template.policy_sha256)
    with localcontext() as ctx:
        ctx.prec=34
        spread=(ask-bid)/bid
        if spread>Decimal("0.01"):
            return ResearchGeometry("HOLD",("ENTRY_SPREAD_TOO_LARGE",),
                                    did,template.policy_sha256)
        entry=ask if side=="LONG" else bid
        risk_fraction=max(Decimal(spec["min_risk_fraction"]),
                          atr*Decimal(spec["atr_risk_multiple"]))
        risk=entry*risk_fraction
        target=Decimal(spec["target_r_multiple"])*risk
        stop=entry-risk if side=="LONG" else entry+risk
        take=entry+target if side=="LONG" else entry-target
        if stop<=0 or take<=0:
            return ResearchGeometry("HOLD",("UNEXECUTABLE_RISK_GEOMETRY",),
                                    did,template.policy_sha256)
        body={
            "template_sha256":template.policy_sha256,
            "candidate_id":did,"event_open_ms":event,"side":side,"symbol":symbol,
            "entry_quote_sha256":quote["receipt_sha256"],
            "g3_feature_sha256":g3_coin["feature_sha256"],
            "risk_fraction":str(risk_fraction),
            "entry_reference_price":str(entry),
            "stop_price":str(stop),"target_price":str(take),
            "declared_at_ms":decision,"horizon_ms":spec["horizon_ms"],
            "entry_convention":ENTRY_CONVENTION,
            "exit_policy_id":EXIT_POLICY_ID,
            "risk_policy_id":RISK_POLICY_ID,
            "cost_policy_id":COST_POLICY_ID,
            "quote_sampling_ms":seen,
            "order_authority":"NONE",
        }
        frozen={**body,"policy_sha256":_hash(body)}
    return ResearchGeometry("GEOMETRY_RECORDED",(),did,
                            template.policy_sha256,frozen)
