"""G9 single-Champion-FIRST paper contract and separate locked authority.

No actual paper release exists in G9: G4-G8 genuine original/qualified
Champion and independent owner signed authorization are missing. All positive
cases below are *LAB_SIMULATION_ONLY*, never PAPER order authority.
On import: no network/disk/key/account operations.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import hmac
import re

from .learning_contract import canonical

VERSION="NBOT_V5_1_G9_PAPER_CONTRACT_V1"
LAB_GRADE="SYNTHETIC_OFFLINE_TEST_ONLY"
SHA=re.compile(r"[a-f0-9]{64}\Z")
SYMBOL=re.compile(r"[A-Z0-9]{3,24}\Z")
NO_AUTHORITY="NONE"

class PaperHold(ValueError):pass


def dec(raw,positive=False):
    if type(raw) is not str or len(raw)>80:
        raise PaperHold("G9_DECIMAL_FORMAT")
    try:v=Decimal(raw)
    except (ValueError,ArithmeticError) as e:raise PaperHold("G9_DECIMAL_INVALID") from e
    if not v.is_finite() or (positive and v<=0):
        raise PaperHold("G9_DECIMAL_NONFINITE")
    return v


def sha(text):
    return type(text) is str and bool(SHA.fullmatch(text))


@dataclass(frozen=True)
class PaperPolicy:
    capital:str="1000"
    risk_fraction:str="0.005"
    max_open_risk:str="0.01"
    max_exposure_multiple:str="1"
    max_drawdown_fraction:str="0.05"
    max_quote_age_ms:int=1000
    max_message_age_ms:int=5000
    max_spread_fraction:str="0.01"
    min_lower_net_r:str="0.10"
    max_duration_ms:int=14400000
    max_positions:int=1
    mode:str="LAB_SIMULATION_ONLY"

    def validate(self):
        p={k:dec(getattr(self,k),True) for k in
           ("capital","risk_fraction","max_open_risk","max_exposure_multiple",
            "max_drawdown_fraction","max_spread_fraction","min_lower_net_r")}
        if (p["capital"]>Decimal("100000000") or
            not 0<p["risk_fraction"]<=p["max_open_risk"]<=Decimal(".02") or
            not 0<p["max_exposure_multiple"]<=Decimal("1") or
            not 0<p["max_drawdown_fraction"]<=Decimal(".10") or
            not 0<p["max_spread_fraction"]<=Decimal(".01") or
            not 0<p["min_lower_net_r"]<=Decimal("10") or
            type(self.max_positions) is not int or self.max_positions!=1 or
            type(self.max_quote_age_ms) is not int or not 1<=self.max_quote_age_ms<=1000 or
            type(self.max_message_age_ms) is not int or not 1<=self.max_message_age_ms<=5000 or
            type(self.max_duration_ms) is not int or not 300000<=self.max_duration_ms<=24*3600000 or
            self.mode!="LAB_SIMULATION_ONLY"):
            raise PaperHold("G9_POLICY_UNSAFE_OR_PAPER_MODE_LOCKED")
        return self

    def digest(self):
        self.validate()
        return sha256(canonical({"version":VERSION,"policy":self.__dict__})).hexdigest()


@dataclass(frozen=True)
class SignedLabProposal:
    decision_id:str
    model_sha256:str
    at_ms:int
    expires_ms:int
    symbol:str
    side:str
    stop:str
    target:str
    lower_net_r:str
    source_sha256:str
    policy_sha256:str
    idempotency_sha256:str
    signature:str
    book:str="CHAMPION_LAB_ONLY"
    grade:str=LAB_GRADE
    authority:str=NO_AUTHORITY


@dataclass(frozen=True)
class PaperQuote:
    symbol:str
    at_ms:int
    bid:str
    ask:str
    sha256:str
    grade:str=LAB_GRADE
    original_verified:bool=False


@dataclass(frozen=True)
class PaperCosts:
    fee_rate:str
    slippage_rate:str
    funding_cash_quote:str
    settled_through_ms:int
    fee_sha256:str
    slippage_sha256:str
    funding_sha256:str
    grade:str=LAB_GRADE
    original_verified:bool=False


@dataclass(frozen=True)
class PaperVeto:
    reasons:tuple[str,...]
    status:str="LAB_REJECTED"
    authority:str=NO_AUTHORITY
    exchange_orders:int=0


def proposal_body(x:SignedLabProposal):
    return {k:getattr(x,k) for k in x.__dataclass_fields__ if k!="signature"}


def sign_lab_proposal(body:dict,lab_key:bytes):
    if (type(lab_key) is not bytes or len(lab_key)<32 or
            type(body) is not dict or body.get("authority")!="NONE"
            or body.get("grade")!=LAB_GRADE or
            body.get("book")!="CHAMPION_LAB_ONLY"):
        raise PaperHold("G9_SIGNING_ONLY_FOR_LAB_NOT_PAPER")
    return hmac.new(lab_key,b"NBOT-G9-LAB-PROPOSAL-V1\n"+canonical(body),
                    "sha256").hexdigest()


def assess_lab_proposal(*,proposal:SignedLabProposal|None,quote:PaperQuote|None,
                        costs:PaperCosts|None,policy:PaperPolicy,
                        known_model_sha256:str,lab_key:bytes,now_ms:int,
                        occupied:bool=False,halted:bool=False)->PaperVeto:
    reasons=set()
    try:policy.validate()
    except (PaperHold,ValueError,TypeError):reasons.add("POLICY_INVALID")
    if type(now_ms) is not int or now_ms<0:reasons.add("CLOCK_INVALID")
    if type(proposal) is not SignedLabProposal:
        reasons.add("PROPOSAL_MISSING_OR_MALFORMED")
        proposal=None
    if proposal is not None:
        if (proposal.book!="CHAMPION_LAB_ONLY" or proposal.grade!=LAB_GRADE
                or proposal.authority!="NONE"):
            reasons.add("PAPER_OR_REAL_AUTHORITY_UNAVAILABLE")
        if not sha(known_model_sha256) or proposal.model_sha256!=known_model_sha256:
            reasons.add("UNAPPROVED_OR_CHANGED_MODEL")
        if not all(sha(x) for x in (proposal.decision_id,proposal.source_sha256,
                proposal.policy_sha256,proposal.idempotency_sha256)):
            reasons.add("PROPOSAL_HASH_OR_SOURCE_UNVERIFIED")
        elif proposal.policy_sha256!=policy.digest():
            reasons.add("POLICY_DIGEST_MISMATCH")
        try:
            if not hmac.compare_digest(proposal.signature,
                   sign_lab_proposal(proposal_body(proposal),lab_key)):
                reasons.add("PROPOSAL_SIGNATURE_INVALID")
        except (TypeError,ValueError,PaperHold):
            reasons.add("PROPOSAL_SIGNATURE_INVALID")
        if (type(proposal.at_ms) is not int or type(proposal.expires_ms) is not int
                or type(now_ms) is not int or
                not proposal.at_ms<=now_ms<proposal.expires_ms or
                now_ms-proposal.at_ms>policy.max_message_age_ms):
            reasons.add("PROPOSAL_STALE_OR_EXPIRED")
        if proposal.side not in ("LONG","SHORT") or not isinstance(proposal.symbol,str) or not SYMBOL.fullmatch(proposal.symbol):
            reasons.add("SIDE_OR_SYMBOL_INVALID")
        try:
            if dec(proposal.lower_net_r)<=dec(policy.min_lower_net_r):
                reasons.add("INSUFFICIENT_LOWER_NET_R")
        except PaperHold:reasons.add("LOWER_NET_R_INVALID")
    if type(quote) is not PaperQuote or proposal is None:
        reasons.add("QUOTE_MISSING")
    else:
        if (quote.symbol!=proposal.symbol or quote.grade!=LAB_GRADE
                or quote.original_verified or not sha(quote.sha256)
                or type(quote.at_ms) is not int or type(now_ms) is not int
                or not 0<=now_ms-quote.at_ms<=policy.max_quote_age_ms):
            reasons.add("QUOTE_STALE_OR_UNVERIFIED")
        try:
            bid,ask=dec(quote.bid,True),dec(quote.ask,True)
            if bid>=ask or (ask-bid)/bid>dec(policy.max_spread_fraction):
                reasons.add("QUOTE_CROSSED_OR_WIDE")
        except PaperHold:reasons.add("QUOTE_NUMERIC_INVALID")
    if type(costs) is not PaperCosts:
        reasons.add("COST_WITNESS_MISSING")
    else:
        if (costs.grade!=LAB_GRADE or costs.original_verified or
                not all(sha(x) for x in (costs.fee_sha256,costs.slippage_sha256,
                         costs.funding_sha256)) or
                type(costs.settled_through_ms) is not int or
                type(now_ms) is not int or costs.settled_through_ms<now_ms):
            reasons.add("FEE_SLIPPAGE_FUNDING_UNVERIFIED")
        try:
            if (not 0<=dec(costs.fee_rate)<=Decimal(".01") or
                not 0<=dec(costs.slippage_rate)<=Decimal(".01") or
                abs(dec(costs.funding_cash_quote))>Decimal("100000")):
                reasons.add("COST_NUMERIC_BOUNDS")
        except PaperHold:reasons.add("COST_NUMERIC_INVALID")
    if proposal is not None and quote is not None:
        try:
            entry=(dec(quote.ask,True)*(1+dec(costs.slippage_rate))
                   if proposal.side=="LONG" else
                   dec(quote.bid,True)*(1-dec(costs.slippage_rate)))
            stop,target=dec(proposal.stop,True),dec(proposal.target,True)
            direction=1 if proposal.side=="LONG" else -1
            if (entry-stop)*direction<=0 or (target-entry)*direction<=0:
                reasons.add("STOP_TARGET_RISK_GEOMETRY")
        except (PaperHold,AttributeError):reasons.add("STOP_TARGET_RISK_GEOMETRY")
    if occupied:reasons.add("ONE_POSITION_ALREADY_OCCUPIED")
    if halted:reasons.add("RESTART_OR_DRAWDOWN_HOLD")
    return PaperVeto(tuple(sorted(reasons)),
            "LAB_ELIGIBLE_BUT_PAPER_LOCKED" if not reasons else "LAB_REJECTED")


def authorize_real_paper_release(*args,**kwargs):
    raise PaperHold("G9_OWNER_PAPER_RELEASE_AND_G8_ORIGINAL_CHAMPION_NOT_AVAILABLE")
