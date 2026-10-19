#!/usr/bin/env python3
"""M5A chronological 8-hour snapshot replay, pure shadow / NO ORDERS.

Replay saved, point-in-time source snapshots and independent model-readiness
receipts. Fixed-25, liquidity-only 25 and quality-selected 25 each hold their
OWN simulated universe. Comparison reports ONLY screen/quality/churn/coverage,
NOT trading PnL, model alpha, actual FreqAI model readiness or executable fills.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from datetime import datetime,timezone
import json
from statistics import mean
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from m5a_universe_selector import (
    HOUR_MS,CONTRACTS, evaluate, incumbent_symbols, select,sha_obj,require
)

def quality(snapshot:dict,symbols:list[str])->dict:
    asof=snapshot["asof_ms"]
    by={r.symbol:r for r in (evaluate(x,asof,set()) for x in snapshot["contracts"])}
    available=[r.score for sym in symbols if (r:=by.get(sym)) and r.eligible]
    return {
        "eligible_count":len(available),
        "mean_public_market_quality":round(mean(available),6) if available else None,
        "never_represent_as_aftercost_trading_pnl":True
    }

def replay(events:list[dict],old:list[str],initial_since_ms:dict[str,int])->dict:
    require(len(events)>0,"NO_ASOF_SNAPSHOTS")
    require(len(old)==CONTRACTS and len(set(old))==CONTRACTS,"BAD_FIXED_BASELINE")
    policies={
        "fixed25":{"current":list(old),"since":dict(initial_since_ms)},
        "liquidity25":{"current":list(old),"since":dict(initial_since_ms)},
        "quality25":{"current":list(old),"since":dict(initial_since_ms)}
    }
    ledger=[]
    last=-1
    for e in events:
        snapshot=e["snapshot"]
        asof=snapshot["asof_ms"]
        require(asof>last,"UNSORTED_OR_DUPLICATE_REPLAY_TIMESTAMP")
        require(last<0 or asof-last>=8*HOUR_MS,"MORE_THAN_ONE_REVIEW_PER_EIGHT_HOURS")
        last=asof
        attest=e.get("readiness",{})
        pinned=set(e.get("pinned",[]))
        current_fixed=policies["fixed25"]["current"]
        observation={"review_utc":datetime.fromtimestamp(asof/1000,timezone.utc).isoformat(),
                     "snapshot_sha256":sha_obj(snapshot),
                     "fixed25":{**quality(snapshot,current_fixed),"turnover":0,
                                "status":"UNMODIFIED_REFERENCE"}}
        for name,policy in (("liquidity25","liquidity"),("quality25","quality")):
            state=policies[name]
            res=select(snapshot,state["current"],attest,pinned=pinned,
                       previous_since_ms=state["since"],policy=policy)
            candidate=res["proposed_25"]
            observation[name]={**quality(snapshot,candidate),
                "status":res["status"],"turnover":res["turnover"],
                "hold_reasons":res["hold_reasons"],"proposed_25":candidate,
                "independent_verified_readiness":res["model_ready_eligible_contracts"],
                "replacements":res["replacements"]}
            if res["status"]=="PROPOSAL_ONLY":
                # SHADOW COUNTERFACTUAL: NEVER apply a real FreqAI whitelist.
                prior=set(state["current"])
                state["current"]=list(candidate)
                for gone in prior-set(candidate):state["since"].pop(gone,None)
                for added in set(candidate)-prior:state["since"][added]=asof
            require(len(state["current"])==25 and len(set(state["current"]))==25
                    and "BTCUSDT" in state["current"],
                    "SHADOW_UNIVERSE_STATE_CORRUPTED")
        ledger.append(observation)
    out={
        "schema":"m5a-asof-shadow-replay-v1",
        "snapshot_events_replayed":len(ledger),
        "initial_25":old,
        "synthetic_or_real_market_provenance":sorted(set(
            e["snapshot"]["source"] for e in events)),
        "policies":{},
        "ledger":ledger,
        "conclusions_limited_to_market_quality_and_universe_churn":True,
        "no_trading_pnl_or_prediction_quality_evidence":True,
        "shadow_only_never_changes_actual_pairlist":True,
        "no_live_or_paper_orders":True}
    for name in policies:
        records=[x[name] for x in ledger]
        out["policies"][name]={
            "total_virtual_replacements":sum(x["turnover"] for x in records),
            "reviews_with_changes":sum(x["turnover"]>0 for x in records),
            "reviews_blocked":sum(x["status"]=="HOLD" for x in records),
            "reviews_fully_25_eligible":sum(x["eligible_count"]==25 for x in records),
            "mean_qualified_market_quality":(
                round(mean(x["mean_public_market_quality"] for x in records
                           if x["mean_public_market_quality"] is not None),6)
                if any(x["mean_public_market_quality"] is not None for x in records)
                else None),
            "end_shadow_25":policies[name]["current"]
        }
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--events",type=Path,required=True,
                   help="JSON array of timestamped snapshots/readiness (must truly be as-of)")
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--start-known-since-ms",type=int,required=True,
                   help="Grounded date when all original 25 became active; unknown -> no swaps")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    require(not a.out.exists(),"REFUSE_OVERWRITE_REPLAY")
    ev=json.loads(a.events.read_text())
    old=incumbent_symbols(json.loads(a.config.read_text()))
    summary=replay(ev,old,{x:a.start_known_since_ms for x in old})
    a.out.write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="ledger"},indent=2))
if __name__=="__main__":main()
