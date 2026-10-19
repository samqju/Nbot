#!/usr/bin/env python3
"""M5A: deterministic, fail-closed, OFFLINE/shadow 8-hour universe selector.

Considers as-of public Binance USD-M perpetual quotes, but it NEVER changes
a Freqtrade whitelist, places an order, starts training or restarts a bot.
A coin must pass a separately verified, timestamped history+model readiness
attestation before the selector may PROPOSE it as a replacement. An uncertified
market may appear on the discovery shortlist, never the proposed active set.
No claims that technical market-quality score predicts profitable trades.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite, log10
import hashlib
import json
import re
from typing import Any

BTC="BTCUSDT"
PAIR_PATTERN=re.compile(r"^[A-Z0-9]{2,20}USDT$")
CONTRACTS=25
MAX_REPLACEMENTS=10
HOUR_MS=3_600_000
MAX_SNAPSHOT_AGE_MS=180_000
MAX_BOOK_SPREAD_BPS=20.0
MIN_QUOTE_24H_USDT=20_000_000.0
MIN_BEST_LEVEL_NOTIONAL=1000.0
MAX_ABS_FUNDING=0.0015
MIN_AGE_DAYS=45
MIN_DAY_RANGE_PCT=0.6
MAX_DAY_RANGE_PCT=30.0
MIN_ADVANTAGE=0.15
MIN_TENURE_HOURS=24
LIQUIDITY_TARGET_USDT=200_000_000
BPS=10_000

def require(condition:bool,why:str):
    if not condition:raise ValueError(why)

def safe_number(value:Any,field:str)->float:
    try:n=float(value)
    except (TypeError,ValueError,OverflowError):raise ValueError("INVALID_"+field) from None
    require(isfinite(n),"NONFINITE_"+field)
    return n

def canonical_symbol(token:str)->str:
    require(isinstance(token,str) and bool(PAIR_PATTERN.fullmatch(token)),
            "INVALID_USDT_PERPETUAL_SYMBOL")
    return token

def pair(symbol:str)->str:
    return canonical_symbol(symbol)[:-4]+"/USDT:USDT"

def symbol_from_pair(t:str)->str:
    require(isinstance(t,str) and t.endswith("/USDT:USDT"),
            "INVALID_PAIR_FORMAT")
    return canonical_symbol(t[:-10]+"USDT")

def sha_obj(data:object)->str:
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),
        allow_nan=False).encode()).hexdigest()

@dataclass(frozen=True)
class Evaluation:
    symbol:str
    score:float|None
    liquidity_score:float|None
    reasons:tuple[str,...]
    spread_bps:float|None
    quote_volume_usdt:float|None
    ready:bool
    eligible:bool

def validate_ready(readiness:dict,asof_ms:int)->set[str]:
    """Explicit independent eligibility receipt. No inferred model readiness."""
    if not readiness:
        return set()
    require(readiness.get("schema")=="m5a-readiness-attestation-v1",
            "BAD_READINESS_SCHEMA")
    require(isinstance(readiness.get("asof_ms"),int)
            and 0 <= asof_ms-readiness["asof_ms"] <= MAX_SNAPSHOT_AGE_MS,
            "STALE_OR_FUTURE_READINESS")
    require(readiness.get("verified_by")=="independent_offline_verifier",
            "UNVERIFIED_MODEL_READINESS")
    require(readiness.get("no_live_activation") is True,
            "READINESS_MUST_BE_OFFLINE")
    rows=readiness.get("pairs")
    require(isinstance(rows,list),"BAD_READINESS_ROWS")
    good=set()
    for r in rows:
        s=canonical_symbol(r.get("symbol"))
        require(s not in good,"DUPLICATE_READINESS_PAIR")
        flags=("five_minute_continuity","one_hour_continuity","btc_context",
               "funding_and_mark_history","labels_mature","model_trained",
               "purged_validation_passed","schema_compatible","prediction_fresh")
        if all(r.get(k) is True for k in flags):
            # Every attested piece must have existed by the review instant.
            require(isinstance(r.get("evidence_latest_ms"),int)
                    and r["evidence_latest_ms"]<=asof_ms,
                    "FUTURE_READINESS_EVIDENCE")
            good.add(s)
    return good

def evaluate(contract:dict, asof_ms:int, ready:set[str])->Evaluation:
    reasons=[]
    symbol=contract.get("symbol","?")
    if not isinstance(symbol,str) or not PAIR_PATTERN.fullmatch(symbol):
        return Evaluation(str(symbol),None,None,("INVALID_SYMBOL",),None,None,False,False)
    if contract.get("contractType")!="PERPETUAL" or contract.get("quoteAsset")!="USDT" or contract.get("marginAsset")!="USDT":
        reasons.append("WRONG_CONTRACT")
    if contract.get("status")!="TRADING":
        reasons.append("NOT_TRADING")
    onboard=contract.get("onboardDate")
    if not isinstance(onboard,int) or onboard<=0 or onboard>asof_ms or asof_ms-onboard<MIN_AGE_DAYS*24*HOUR_MS:
        reasons.append("INSUFFICIENT_VERIFIED_AGE")
    # Book/top-of-book, funding and 24h ticker are separate endpoints.
    # Each must have been collected in a bounded, as-of-compatible snapshot.
    for key in ("book_at_ms","ticker_at_ms","funding_at_ms"):
        stamp=contract.get(key)
        if not isinstance(stamp,int) or not 0<=asof_ms-stamp<=MAX_SNAPSHOT_AGE_MS:
            reasons.append("STALE_OR_FUTURE_"+key)
    try:
        bid=safe_number(contract.get("bidPrice"),"bid")
        ask=safe_number(contract.get("askPrice"),"ask")
        bidqty=safe_number(contract.get("bidQty"),"bidqty")
        askqty=safe_number(contract.get("askQty"),"askqty")
        vol=safe_number(contract.get("quoteVolume"),"quote_volume")
        high=safe_number(contract.get("highPrice"),"high")
        low=safe_number(contract.get("lowPrice"),"low")
        fund=safe_number(contract.get("lastFundingRate"),"funding")
        require(bid>0 and ask>bid and bidqty>0 and askqty>0 and vol>0
                and 0<low<=high,"INVALID_QUOTE_PRICE_OR_VOLUME")
    except ValueError:
        return Evaluation(symbol,None,None,tuple(sorted(set(reasons+["INVALID_MARKET_VALUES"]))),
                          None,None,symbol in ready,False)
    mid=(bid+ask)/2
    spread=BPS*(ask-bid)/mid
    rng=100*(high-low)/low
    if spread>MAX_BOOK_SPREAD_BPS:reasons.append("SPREAD_TOO_WIDE")
    if vol<MIN_QUOTE_24H_USDT:reasons.append("INSUFFICIENT_24H_TURNOVER")
    if min(bidqty*bid,askqty*ask)<MIN_BEST_LEVEL_NOTIONAL:
        reasons.append("WEAK_BEST_LEVEL_DEPTH")
    if abs(fund)>MAX_ABS_FUNDING:reasons.append("EXCESS_FUNDING")
    if rng<MIN_DAY_RANGE_PCT or rng>MAX_DAY_RANGE_PCT:
        reasons.append("RANGE_OUTSIDE_EXPLORATORY_BOUNDS")
    # Scores use only as-of public data; observed market quality != alpha.
    liq=max(0,min(1,log10(max(1,vol)/MIN_QUOTE_24H_USDT)/
                         log10(LIQUIDITY_TARGET_USDT/MIN_QUOTE_24H_USDT)))
    spread_quality=max(0,1-spread/MAX_BOOK_SPREAD_BPS)
    depth=min(1,min(bidqty*bid,askqty*ask)/10_000)
    # Intermediate intraday movement needed, but extremes are risky.
    range_quality=max(0,1-abs(rng-5.0)/15)
    fund_quality=max(0,1-abs(fund)/MAX_ABS_FUNDING)
    quality=round(.40*liq+.25*spread_quality+.15*depth+
                  .10*range_quality+.10*fund_quality,6)
    liq_score=round(.75*liq+.25*spread_quality,6)
    return Evaluation(symbol,quality,liq_score,tuple(sorted(set(reasons))),
                      round(spread,4),vol,symbol in ready,len(reasons)==0)

def select(snapshot:dict, incumbents:list[str], readiness:dict|None=None,
           pinned:set[str]|None=None, previous_since_ms:dict[str,int]|None=None,
           policy:str="quality")->dict:
    """Proposal only. HOLD is fail-closed: original list always retained."""
    require(policy in ("quality","liquidity"),"UNSUPPORTED_POLICY")
    require(snapshot.get("schema")=="m5a-snapshot-v1","BAD_SNAPSHOT_SCHEMA")
    asof=snapshot.get("asof_ms")
    require(isinstance(asof,int) and asof>0,"BAD_ASOF")
    review=snapshot.get("review_start_ms")
    require(isinstance(review,int) and review%(8*HOUR_MS)==0
            and 0<=asof-review<=MAX_SNAPSHOT_AGE_MS,
            "SNAPSHOT_OUTSIDE_EIGHT_HOUR_REVIEW_WINDOW")
    captured=snapshot.get("captured_at_ms")
    require(isinstance(captured,int) and 0<=captured-asof<=1000,
            "SNAPSHOT_CAPTURED_AFTER_DECISION")
    require(snapshot.get("review_boundary_aligned") is True,
            "NOT_VALID_REVIEW_BOUNDARY")
    require(snapshot.get("source") in ("binance_public_rest","historical_verified_asof"),
            "UNVERIFIED_SNAPSHOT_SOURCE")
    require(isinstance(incumbents,list) and len(incumbents)==CONTRACTS
            and len(set(incumbents))==CONTRACTS,"REQUIRE_25_UNIQUE_INCUMBENTS")
    incumbents=[canonical_symbol(x) for x in incumbents]
    require(BTC in incumbents,"BTC_PIN_REQUIREMENT")
    pinned=set(pinned or set())|{BTC}
    require(pinned.issubset(set(incumbents)),"PINNED_COIN_NOT_INCUMBENT")
    since=previous_since_ms or {}
    require(all(k in incumbents and isinstance(v,int) and v<=asof for k,v in since.items()),
            "FUTURE_OR_NONINCUMBENT_TENURE")
    market=snapshot.get("contracts")
    require(isinstance(market,list) and len(market)>=CONTRACTS,
            "INCOMPLETE_MARKET_SNAPSHOT")
    symbols=[x.get("symbol") for x in market if isinstance(x,dict)]
    require(len(set(symbols))==len(symbols),"DUPLICATE_EXCHANGE_CONTRACT")
    ready=validate_ready(readiness or {},asof)
    values={r.symbol:r for r in (evaluate(x,asof,ready) for x in market)}
    eligible={s:r for s,r in values.items() if r.eligible}
    score=lambda r:r.score if policy=="quality" else r.liquidity_score
    ranked=sorted(eligible.values(),key=lambda r:(-score(r),r.symbol))
    shortlist=[{"symbol":r.symbol,"score":score(r),
                "ready":r.ready,"spread_bps":r.spread_bps,
                "volume_usdt":round(r.quote_volume_usdt or 0,2)} for r in ranked[:50]]
    rejections={s:list(r.reasons) for s,r in values.items() if r.reasons}
    ready_symbols={s:r for s,r in eligible.items() if r.ready}
    # An unsafe incumbent may be replaced ONLY if an independently
    # ready, eligible substitute exists. Never silently retain an unsafe
    # trading candidate in a proposed new active universe.
    hold=[]
    if len(eligible)<CONTRACTS:hold.append("INSUFFICIENT_LIQUID_MARKETS")
    if len(ready_symbols)<CONTRACTS:hold.append("INSUFFICIENT_MODEL_READY_COINS")
    if any(s not in ready_symbols for s in pinned):
        hold.append("PINNED_COIN_UNSAFE_OR_UNREADY")
    unsafe=[s for s in incumbents if s not in ready_symbols]
    if len(unsafe)>MAX_REPLACEMENTS:
        hold.append("TOO_MANY_UNSAFE_INCUMBENTS_TO_ROTATE")
    proposal=list(incumbents)
    replacements=[]
    if not hold:
        newcomers=[r for r in ranked if r.symbol not in incumbents and r.symbol in ready_symbols]
        # Mandatory replacement of unsafe *unprotected* markets precedes
        # opportunistic upgrades; both consume the same max-10 quota.
        if len(newcomers)<len(unsafe):
            hold.append("INSUFFICIENT_READY_ALTERNATIVES_FOR_UNSAFE_INCUMBENTS")
        else:
            for old,new in zip(sorted(unsafe),newcomers[:len(unsafe)]):
                require(old not in pinned,"UNSAFE_PROTECTED_PAIR")
                proposal[proposal.index(old)]=new.symbol
                replacements.append({"out":old,"in":new.symbol,
                                     "old_score":None,"new_score":score(new),
                                     "reason":"REPLACE_UNSAFE"})
            newcomers=newcomers[len(unsafe):]
            outgoing=sorted((ready_symbols[s] for s in incumbents
                             if s not in pinned and s not in unsafe
                             and asof-since.get(s,asof)>=MIN_TENURE_HOURS*HOUR_MS),
                            key=lambda r:(score(r),r.symbol))
            used=set()
            for newcomer in newcomers:
                if len(replacements)>=MAX_REPLACEMENTS:break
                for old in outgoing:
                    if old.symbol in used:continue
                    if score(newcomer)<score(old)+MIN_ADVANTAGE:continue
                    proposal[proposal.index(old.symbol)]=newcomer.symbol
                    used.add(old.symbol)
                    replacements.append({"out":old.symbol,"in":newcomer.symbol,
                                         "old_score":score(old),"new_score":score(newcomer),
                                         "reason":"MATERIAL_QUALITY_UPGRADE"})
                    break
            require(len(proposal)==25 and len(set(proposal))==25
                    and len(replacements)<=MAX_REPLACEMENTS
                    and pinned.issubset(set(proposal))
                    and len(set(proposal)&set(incumbents))>=15
                    and all(s in ready_symbols for s in proposal),
                    "POST_SELECTION_CONTRACT_VIOLATED")
    if hold:
        # Even partial replacement plans must be discarded on any block.
        proposal=list(incumbents)
        replacements=[]
    result={
        "schema":"m5a-proposal-v1","asof_ms":asof,"policy":policy,
        "snapshot_sha256":sha_obj(snapshot),
        "readiness_sha256":sha_obj(readiness or {}),
        "status":"HOLD" if hold else "PROPOSAL_ONLY",
        "hold_reasons":sorted(hold),
        "original_25":incumbents,"proposed_25":proposal,
        "replacements":replacements,
        "turnover":len(replacements),
        "screened_contracts":len(market),
        "eligible_contracts":len(eligible),
        "model_ready_eligible_contracts":len(ready_symbols),
        "top_50_screened":shortlist,
        "rejections":rejections,
        "pinned":sorted(pinned),
        "never_auto_activate":True,
        "never_place_orders":True,
        "no_claim_of_profitable_trading":True,
        "no_historical_liquidity_or_listing_certification":snapshot["source"]=="binance_public_rest",
    }
    result["proposal_sha256"]=sha_obj(result)
    return result

def incumbent_symbols(config:dict)->list[str]:
    raw=config["exchange"]["pair_whitelist"]
    require(len(raw)==25,"INCUMBENT_CONFIG_NOT_25")
    return [symbol_from_pair(x) for x in raw]
