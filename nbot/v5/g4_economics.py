"""G4 offline quote-constrained economic counterfactual accounting.

A reconstructed quote-constrained cost scenario is NEVER an exchange fill.
All inputs are versioned independently witnessed *original* quotes and fee,
slippage, and funding sources. Defaults are deliberately absent; fail closed.
No live feeds, no sockets, no SQLite and no order submission.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re
from typing import Mapping

from nbot.v5.g4_price_path import PathReplay

ECONOMIC_CONTRACT_VERSION = "NBOT_V5_G4_ECONOMIC_V1"
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class EconomicReplay:
    state: str                 # HOLD or COST_REPLAYED; neither means live trade
    reasons: tuple[str, ...]
    candidate_id: str
    source_grade: str | None = None
    entry_sim_price: str | None = None
    exit_sim_price: str | None = None
    modeled_fee_quote: str | None = None
    modeled_funding_quote: str | None = None
    modeled_gross_r: str | None = None
    modeled_net_r: str | None = None
    filled_orders: int = 0
    financial_authority: str = "NONE"
    contract_version: str = ECONOMIC_CONTRACT_VERSION


def _sha(v: object) -> bool:
    return isinstance(v,str) and bool(_HEX64.fullmatch(v))


def _d(v: object, *, positive=False) -> Decimal | None:
    if not isinstance(v,str) or len(v)>80:
        return None
    try:
        d=Decimal(v)
        if not d.is_finite() or (positive and d<=0):
            return None
        return d
    except InvalidOperation:
        return None


def _valid_quote(w: Mapping | None, *, symbol: str, when: int,
                 earliest: int, latest: int, freshness_ms: int) -> bool:
    if not isinstance(w,Mapping):
        return False
    bid,ask=_d(w.get("bid"),positive=True),_d(w.get("ask"),positive=True)
    at=w.get("sampled_at_ms")
    return bool(
        w.get("symbol")==symbol and _sha(w.get("receipt_sha256"))
        and w.get("source_verified") is True
        and type(at) is int and earliest<=at<=latest
        and (when-at)<=freshness_ms and at<=when
        and bid is not None and ask is not None and bid<ask
        and ((ask-bid)/bid)<=Decimal("0.01")
    )


def assess_quote_constrained_net(
    *, path: PathReplay, candidate: Mapping, policy: Mapping,
    entry_quote: Mapping | None, exit_quote: Mapping | None,
    economic_witness: Mapping | None, audit_at_ms: int,
) -> EconomicReplay:
    if not isinstance(path,PathReplay) or not isinstance(candidate,Mapping) or not isinstance(policy,Mapping):
        raise ValueError("G4_ECONOMIC_INPUT_INVALID")
    did=path.candidate_id
    reasons=[]
    if path.state!="PATH_REPLAYED" or path.scored_outcomes or path.net_r is not None:
        reasons.append("PRICE_PATH_NOT_INDEPENDENTLY_REPLAYED")
    if candidate.get("decision_id")!=did or candidate.get("side") not in ("LONG","SHORT"):
        reasons.append("CANDIDATE_IDENTITY_MISMATCH")
    decision=candidate.get("decision_at_ms")
    exit_at=path.exit_at_ms
    symbol=candidate.get("symbol")
    if (type(decision) is not int or type(exit_at) is not int
            or exit_at<decision or type(audit_at_ms) is not int or audit_at_ms<exit_at):
        reasons.append("EXIT_DECISION_CLOCK_INVALID")
    if not isinstance(economic_witness,Mapping):
        reasons.append("ORIGINAL_ECONOMIC_WITNESS_MISSING")
        economic_witness={}
    if economic_witness.get("source_grade")!="ORIGINAL_QUOTE_FEE_FUNDING_WITNESSES":
        reasons.append("ECONOMIC_SOURCE_GRADE_INVALID")
    for field in ("quote_source_sha256","fee_source_sha256",
                  "slippage_policy_sha256","funding_source_sha256"):
        if not _sha(economic_witness.get(field)):
            reasons.append(field.upper()+"_MISSING")
    if economic_witness.get("independently_source_verified") is not True:
        reasons.append("ECONOMIC_SOURCE_NOT_INDEPENDENTLY_VERIFIED")
    if not reasons:
        max_age = economic_witness.get("max_quote_age_ms")
        if type(max_age) is not int or not 0<=max_age<=5000:
            reasons.append("QUOTE_AGE_POLICY_INVALID")
        elif not _valid_quote(entry_quote,symbol=symbol,when=decision,
                              earliest=decision-max_age,latest=decision,
                              freshness_ms=max_age):
            reasons.append("ENTRY_ORIGINAL_QUOTE_INVALID")
        elif not _valid_quote(exit_quote,symbol=symbol,when=exit_at+max_age,
                              earliest=exit_at,latest=exit_at+max_age,
                              freshness_ms=max_age):
            reasons.append("EXIT_ORIGINAL_QUOTE_INVALID")
    fee=_d(economic_witness.get("taker_fee_rate"))
    slip=_d(economic_witness.get("slippage_rate"))
    funding=_d(economic_witness.get("funding_quote_per_unit"))
    stop=_d(policy.get("stop_price"),positive=True)
    if (fee is None or not Decimal("0")<=fee<=Decimal("0.01")
            or slip is None or not Decimal("0")<=slip<=Decimal("0.01")
            or funding is None or stop is None):
        reasons.append("MODELED_FEE_SLIPPAGE_FUNDING_RISK_INVALID")
    # Funding_quote_per_unit is a signed, ORIGINAL-source-verified cash flow:
    # positive means a modeled charge; negative means credit. Never infer 0.
    if economic_witness.get("funding_coverage_through_ms") is None or (
            type(economic_witness["funding_coverage_through_ms"]) is not int
            or (exit_at is not None and economic_witness["funding_coverage_through_ms"]<exit_at)):
        reasons.append("FUNDING_INTERVALS_NOT_COVERED")
    if reasons:
        return EconomicReplay("HOLD",tuple(sorted(set(reasons))),did)

    sign=Decimal(1) if candidate["side"]=="LONG" else Decimal(-1)
    entry_bid,entry_ask=Decimal(entry_quote["bid"]),Decimal(entry_quote["ask"])
    exit_bid,exit_ask=Decimal(exit_quote["bid"]),Decimal(exit_quote["ask"])
    with localcontext() as ctx:
        ctx.prec=34
        if sign==1:
            entry=entry_ask*(1+slip)
            final=exit_bid*(1-slip)
        else:
            entry=entry_bid*(1-slip)
            final=exit_ask*(1+slip)
        risk=sign*(entry-stop)
        if risk<=0:
            return EconomicReplay("HOLD",("MODELED_RISK_GEOMETRY_INVALID",),did)
        fee_quote=fee*(entry+final)
        gross=sign*(final-entry)/risk
        net=(sign*(final-entry)-fee_quote-funding)/risk
    return EconomicReplay(
        "COST_REPLAYED",(),did,source_grade="QUOTE_CONSTRAINED_SIMULATION",
        entry_sim_price=str(entry),exit_sim_price=str(final),
        modeled_fee_quote=str(fee_quote),modeled_funding_quote=str(funding),
        modeled_gross_r=str(gross),modeled_net_r=str(net),
    )
