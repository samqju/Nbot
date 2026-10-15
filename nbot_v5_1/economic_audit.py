"""G6 offline bid/ask after-cost scenario verifier, no actual fills/labels.

The path MUST be corroborated separately by G4 original source; until
that passes, this adapter intentionally accepts only SYNTHETIC LAB paths,
returns MODEL_ONLY and never qualifies a Learning return. Numeric strings
are Decimal; no default-free fees, funding, spread or slippage assumptions.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal,localcontext
import hashlib
import json
from .research_intent import FrozenIntent,ResearchHold,number
from .research_book import VirtualTerminal

VERSION="NBOT_V5_1_G6_ECONOMICS_V1"
LAB_GRADE="SYNTHETIC_OFFLINE_TEST_ONLY"
ZERO=Decimal(0)


class EconomicHold(ValueError):pass


@dataclass(frozen=True)
class QuoteWitness:
    symbol:str
    at_ms:int
    bid:str
    ask:str
    source_sha256:str
    grade:str="SYNTHETIC_OFFLINE_TEST_ONLY"


@dataclass(frozen=True)
class CostWitness:
    maker_or_taker_fee_rate:str
    slippage_rate:str
    funding_cash_quote_per_unit:str
    funding_interval_covered_through_ms:int
    fee_receipt_sha256:str
    slippage_policy_sha256:str
    funding_receipt_sha256:str
    grade:str="SYNTHETIC_OFFLINE_TEST_ONLY"


@dataclass(frozen=True)
class EconomicAssessment:
    schema:str
    intent_id:str
    state:str
    reasons:tuple[str,...]
    modeled_gross_r:str|None
    modeled_net_r:str|None
    modeled_entry:str|None
    modeled_exit:str|None
    fee_quote:str|None
    funding_quote:str|None
    path_grade:str
    research_qualified_count:int=0
    filled_exchange_orders:int=0
    financial_authority:str="NONE"


def _is_sha(s):
    return type(s) is str and len(s)==64 and all(c in "0123456789abcdef" for c in s)


def assess_model_only(*,intent:FrozenIntent,terminal:VirtualTerminal,
    entry_quote:QuoteWitness|None,exit_quote:QuoteWitness|None,
    costs:CostWitness|None,audit_at_ms:int,max_quote_age_ms:int=5000
)->EconomicAssessment:
    if type(intent) is not FrozenIntent or type(terminal) is not VirtualTerminal:
        raise EconomicHold("G6_ECONOMIC_TYPES")
    if (type(audit_at_ms) is not int or audit_at_ms<=0 or
            type(max_quote_age_ms) is not int or not 0<=max_quote_age_ms<=5000):
        raise EconomicHold("G6_ECONOMIC_AUDIT_CLOCK")
    reasons=[]
    if (intent.intent_id!=terminal.intent_id or intent.symbol!=terminal.symbol
            or intent.side!=terminal.side):
        reasons.append("INTENT_TERMINAL_MISMATCH")
    if (terminal.financial_authority!="NONE" or
         terminal.qualified_net_return is not None or
         terminal.path_grade!="SYNTHETIC_PATH_ONLY_NOT_EXECUTABLE" or
         terminal.economic_state!="COST_PENDING_UNQUALIFIED" or
         intent.financial_authority!="NONE"):
        reasons.append("UNSUPPORTED_SCIENTIFIC_OR_ORDER_AUTHORITY")
    if intent.source_grade!=LAB_GRADE:
        reasons.append("G4_NOT_ACCEPTED_ONLY_SYNTHETIC_ECONOMICS_ALLOWED")
    if (terminal.at_ms<intent.activates_at_ms or
        terminal.at_ms>intent.expires_at_ms or
        audit_at_ms<terminal.at_ms):
        reasons.append("PATH_CHRONOLOGY_UNVERIFIED")

    quotes=[]
    for q,when,name in ((entry_quote,intent.activates_at_ms,"ENTRY"),
                        (exit_quote,terminal.at_ms,"EXIT")):
        if type(q) is not QuoteWitness or q.symbol!=intent.symbol or q.grade!=LAB_GRADE:
            reasons.append(name+"_QUOTE_MISSING_OR_UNTRUSTED")
            quotes.append(None);continue
        if (type(q.at_ms) is not int or not when-max_quote_age_ms<=q.at_ms<=when
                or not _is_sha(q.source_sha256)):
            reasons.append(name+"_QUOTE_NOT_CAUSAL_OR_HASHED")
            quotes.append(None);continue
        try:
            b=number(q.bid);a=number(q.ask)
        except ResearchHold:
            reasons.append(name+"_QUOTE_PRICE_INVALID");quotes.append(None);continue
        if b>=a or (a-b)/b>Decimal(".01"):
            reasons.append(name+"_QUOTE_SPREAD_INVALID")
            quotes.append(None);continue
        quotes.append((b,a))
    if type(costs) is not CostWitness or costs.grade!=LAB_GRADE:
        reasons.append("COST_SOURCE_UNQUALIFIED")
        costs=None
    fee=slip=funding=None
    if costs is not None:
        try:
            fee=number(costs.maker_or_taker_fee_rate,strictly_positive=False)
            slip=number(costs.slippage_rate,strictly_positive=False)
            funding=number(costs.funding_cash_quote_per_unit,strictly_positive=False)
        except ResearchHold:
            reasons.append("COST_DECIMALS_INVALID")
        if (fee is not None and not ZERO<=fee<=Decimal(".01")
                or slip is not None and not ZERO<=slip<=Decimal(".01")
                or funding is not None and abs(funding)>Decimal("10000000")):
            reasons.append("COST_OUTSIDE_DECLARED_BOUND")
        if (type(costs.funding_interval_covered_through_ms) is not int
                or costs.funding_interval_covered_through_ms<terminal.at_ms):
            reasons.append("FUNDING_INTERVAL_MISSING")
        if not all(_is_sha(x) for x in (costs.fee_receipt_sha256,
                                      costs.slippage_policy_sha256,
                                      costs.funding_receipt_sha256)):
            reasons.append("COST_RECEIPT_ID_MISSING")
    if reasons:
        return EconomicAssessment(VERSION,intent.intent_id,"HOLD",
               tuple(sorted(set(reasons))),None,None,None,None,None,None,
               intent.source_grade)
    assert costs is not None and fee is not None and slip is not None and funding is not None
    entry_bid,entry_ask=quotes[0]
    exit_bid,exit_ask=quotes[1]
    side=Decimal(1) if intent.side=="LONG" else Decimal(-1)
    with localcontext() as ctx:
        ctx.prec=38
        if side==1:
            entry=entry_ask*(1+slip)
            close=exit_bid*(1-slip)
        else:
            entry=entry_bid*(1-slip)
            close=exit_ask*(1+slip)
        initial_r=abs(number(intent.entry_reference)-number(intent.stop))
        if initial_r<=ZERO:return EconomicAssessment(VERSION,intent.intent_id,
             "HOLD",("INITIAL_R_INVALID",),None,None,None,None,None,None,
             intent.source_grade)
        fee_cash=fee*(entry+close)
        # Signed funding: positive is modeled expense, negative credit.
        gross_r=side*(close-entry)/initial_r
        net_r=(side*(close-entry)-fee_cash-funding)/initial_r
        return EconomicAssessment(VERSION,intent.intent_id,
            "MODELED_SYNTHETIC_ONLY_NOT_QUALIFIED",(),
            str(gross_r),str(net_r),str(entry),str(close),str(fee_cash),
            str(funding),intent.source_grade)


def qualified_learning_label_count(outcomes:tuple[EconomicAssessment,...])->int:
    if type(outcomes) is not tuple or any(type(v) is not EconomicAssessment for v in outcomes):
        raise EconomicHold("G6_OUTCOME_TYPE")
    # G4 original source, execution/quote custody, effective fees,
    # interval-specific funding and independent G6-science release are
    # NOT available. There is deliberately no promotion function here.
    return 0
