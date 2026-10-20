"""Offline nine-month experiment: A frozen, B1 more data, B2 contextual challenger.

Proxy economics are NOT native fills, and this is NOT a promotion/paper/live gate.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime,timezone
from itertools import groupby
from math import sqrt
from pathlib import Path
import calendar
import json

from .brain import train,freeze_artifacts
from .lab import con,REVIEW_MS,LABEL_POLICY
from .science import RuleBrain,block_bootstrap_uplift

def month_start(s: str)->int:
    try:
        if len(s)!=7 or s[4]!="-":raise ValueError()
        year,month=map(int,s.split("-"))
        d=datetime(year,month,1,tzinfo=timezone.utc)
    except (ValueError,TypeError) as exc:
        raise ValueError("REQUIRE_YYYY_MM_START_MONTH") from exc
    return int(d.timestamp()*1000)

def add_months(ms:int,count:int)->int:
    d=datetime.fromtimestamp(ms/1000,timezone.utc)
    ix=d.year*12+d.month-1+count
    return int(datetime(ix//12,(ix%12)+1,1,tzinfo=timezone.utc).timestamp()*1000)

def nine_month_bounds(start_month:str)->tuple[int,int,int,int]:
    a=month_start(start_month)
    return a,add_months(a,3),add_months(a,6),add_months(a,9)

def _cohorts(c,table,column,start_ms,end_ms):
    if (table,column) not in (("watch_candidate","review_ms"),("candidate","decision_ms")):
        raise ValueError("UNSUPPORTED_TABLE")
    cursor=c.execute(f"SELECT * FROM {table} WHERE {column}>=? AND {column}<? ORDER BY {column},symbol",
                      (start_ms,end_ms))
    for k,rows in groupby(cursor,key=lambda r:r[column]):
        yield k,list(rows)

def _drawdown(trades,sleeve,stake):
    # Each order commits at most one stake; hypothetical 1x fixed-notional sleeve.
    balance=peak=sleeve
    maxdd=0.0
    for item in sorted(trades,key=lambda x:(x["exit_ms"],x["decision_ms"])):
        balance+=item["net_after_cost"]*stake
        peak=max(peak,balance)
        maxdd=max(maxdd,(peak-balance)/peak)
    return maxdd

def replay(c, brain, start_ms, end_ms, *, stake_usdt=1000.0, sleeve_usdt=10000.0,
           top_n=20, stress_roundtrip=.0025, event_sink=None):
    if stake_usdt<=0 or sleeve_usdt<stake_usdt or not 1<=top_n<=20:
        raise ValueError("UNSAFE_RESEARCH_ACCOUNT")
    if getattr(brain,"cutoff_ms",start_ms)>start_ms:
        raise ValueError("MODEL_FIT_AFTER_EVALUATION_START")
    watches=iter(_cohorts(c,"watch_candidate","review_ms",start_ms,end_ms))
    next_review=next(watches,None)
    selected_symbols=set()
    watch_records=[]
    results=[]
    stats=Counter()
    locked_until=start_ms
    watch_expires=start_ms
    balance=sleeve_usdt
    pending=None
    def emit(event):
        if event_sink is not None:
            event_sink(event)
    for t,candidates in _cohorts(c,"candidate","decision_ms",start_ms,end_ms):
        if pending is not None and t>=pending["exit_ms"]:
            balance+=pending["net_after_cost"]*stake_usdt
            pending=None
        while next_review is not None and next_review[0]<=t:
            review,watch_records=next_review
            watch_expires=review+REVIEW_MS
            # Model can select fewer than 20 and exclude all.
            pred=brain.score(watch_records,"watch")
            ranked=sorted(zip(watch_records,pred),key=lambda x:(-x[1][1],-x[1][0],x[0]["symbol"]))
            selected_symbols={r["symbol"] for r,(net,_) in ranked if net>0} 
            # Set cap only after prioritizing by learned ranking score.
            selected_symbols=set(list(sorted(selected_symbols,
                                  key=lambda s:next(i for i,(r,_) in enumerate(ranked) if r["symbol"]==s)))[:top_n])
            stats["universe_reviews"]+=1
            stats["watch_symbols_total"]+=len(selected_symbols)
            emit({"event":"watch","time_ms":review,"brain":brain.version,
                  "selected_symbols":sorted(selected_symbols),
                  "scores":[{"symbol":r["symbol"],"expected_net":p[0],"rank":p[1]}
                            for r,p in zip(watch_records,pred)]})
            next_review=next(watches,None)
        if t>=watch_expires:
            selected_symbols=set()
        stats["valid_broad_candidates"]+=len(candidates)
        valid=[r for r in candidates if r["symbol"] in selected_symbols]
        stats["eligible_in_watchlist"]+=len(valid)
        stats["universe_excluded"]+=len(candidates)-len(valid)
        if not valid:
            stats["no_candidate_at_decision"]+=1
            emit({"event":"decision","time_ms":t,"reason":"NO_WATCH_CANDIDATE"})
            continue
        if t<locked_until:
            stats["occupied_slot_decisions"]+=1
            emit({"event":"decision","time_ms":t,"reason":"SLOT_OCCUPIED"})
            continue
        if balance<stake_usdt:
            stats["insufficient_capital"]+=1
            emit({"event":"decision","time_ms":t,"reason":"INSUFFICIENT_CAPITAL"})
            continue
        scored=brain.score(valid,"opportunity")
        # LambdaRank determines preference *among* predictions with positive
        # expected after-cost return; regression calibrates abstention.
        viable=[(r,p) for r,p in zip(valid,scored) if p[0]>0.0]
        if not viable:
            stats["brain_abstentions"]+=1
            emit({"event":"decision","time_ms":t,"reason":"BRAIN_ABSTAIN"})
            continue
        winner,(expected,rank_score)=max(viable,key=lambda x:(x[1][1],x[1][0],x[0]["symbol"]))
        identity={k:winner[k] for k in ("decision_ms","symbol","side","family")}
        emit({"event":"decision","time_ms":t,"reason":"SELECTED",**identity,
              "predicted_net":expected,"rank_score":rank_score,
              "candidate_scores":[{"symbol":r["symbol"],"side":r["side"],
                  "family":r["family"],"expected_net":p[0],"rank":p[1]}
                  for r,p in zip(valid,scored)]})
        # Outcome lookup occurs only AFTER the immutable ex-ante choice.
        label=c.execute("SELECT * FROM opportunity WHERE decision_ms=? AND symbol=? AND side=? AND family=?",
                        tuple(identity.values())).fetchone()
        if label is None:
            stats["unresolved_selected_path"]+=1
            # Cannot invent an exit or free capital on a missing path.
            locked_until=end_ms+1
            continue
        winner=label
        locked_until=int(winner["exit_ms"])
        stats["selected"]+=1
        results.append({
            "decision_ms":int(t),"exit_ms":locked_until,"symbol":winner["symbol"],
            "side":winner["side"],"family":winner["family"],"regime":winner["regime"],
            "predicted_net":expected,"rank_score":rank_score,
            "net_after_cost":float(winner["net"]),"mfe_pct":float(winner["mfe_pct"]),
            "mae_pct":float(winner["mae_pct"]),"source_quality":winner["quality"],
            "source_hash":winner["source_hash"],
        })
        pending=results[-1]
    # Credit only trades that actually close before the evaluation period ends.
    closed=[x for x in results if x["exit_ms"]<=end_ms]
    net=sum(x["net_after_cost"] for x in closed)*stake_usdt
    stressed=sum(x["net_after_cost"]-stress_roundtrip for x in closed)*stake_usdt
    maxdd=_drawdown(closed,sleeve_usdt,stake_usdt)
    return {
      "brain":brain.version,
      "period_start_ms":start_ms,"period_end_ms":end_ms,
      "trading_sleeve_usdt":sleeve_usdt,"notional_each_usdt":stake_usdt,
      "selected_trades":len(closed),"unfinished_at_boundary":len(results)-len(closed),
      "net_pnl_usdt":round(net,4),"return_pct_of_sleeve":round(100*net/sleeve_usdt,4),
      "stressed_extra_roundtrip":stress_roundtrip,
      "stressed_pnl_usdt":round(stressed,4),
      "max_drawdown_pct_of_sleeve":round(100*maxdd,4),
      "win_rate":round(sum(1 for x in closed if x["net_after_cost"]>0)/len(closed),4) if closed else None,
      "stats":dict(sorted(stats.items())),
      "unresolved_selected_paths":stats["unresolved_selected_path"],
      "account_complete":stats["unresolved_selected_path"]==0 and len(results)==len(closed),
      "trades":closed,
      "authority":"OFFLINE_5M_PROXY_NOT_ACTUAL_NATIVE_EXECUTION",
    }

def experiment(db:Path,start_month:str,output:Path)->dict:
    a,b,d,e=nine_month_bounds(start_month)
    output.mkdir(parents=True,exist_ok=False)
    c=con(db)
    try:
        meta=dict(c.execute("SELECT k,v FROM meta").fetchall())
        if (meta.get("policy")!=LABEL_POLICY or int(meta["start_ms"])!=a or int(meta["end_ms"])!=e):
            raise ValueError("MISMATCHED_NINE_MONTH_DATASET_OR_POLICY")
        brain_a=train(c,"A_3MONTH_FROZEN",b)
        # B is evaluated with frozen A BEFORE fitting challenger on B outcomes.
        first=replay(c,brain_a,b,d)
        b1=train(c,"B1_SAME_ARCH_MORE_DATA",d)
        b2=train(c,"B2_CONTEXTUAL_CHALLENGER",d,adaptive=True)
        final=[replay(c,brain,d,e) for brain in (brain_a,b1,b2)]
        baselines=[replay(c,RuleBrain(mode),d,e) for mode in ("momentum","liquidity","deterministic_random")]
        pairwise={
          "B2_minus_A":block_bootstrap_uplift(final[2],final[0]),
          "B2_minus_B1":block_bootstrap_uplift(final[2],final[1]),
          "B1_minus_A":block_bootstrap_uplift(final[1],final[0]),
        }
        artifacts={}
        for brain in (brain_a,b1,b2):
            artifacts[brain.version]=freeze_artifacts(brain,output/brain.version)
        summary={
            "experiment":"NBOT_V7_NINE_MONTH_BRAIN_LEARNING_V1",
            "periods":{"A_train":[a,b],"B_frozen_A_exam":[b,d],
                       "B1_B2_train_cutoff":d,"C_unseen_exam":[d,e]},
            "train_cutoffs":{x.version:x.cutoff_ms for x in (brain_a,b1,b2)},
            "stage_b":{k:v for k,v in first.items() if k!="trades"},
            "stage_c":[{k:v for k,v in x.items() if k!="trades"} for x in final],
            "stage_c_simple_baselines":[{k:v for k,v in x.items() if k!="trades"} for x in baselines],
            "stage_c_pairwise_diagnostics":pairwise,
            "model_manifests":artifacts,
            "source_registry_sha256":meta["registry_sha256"],
            "confidence":"ENGINEERING_PROXY_ONLY_NO_NATIVE_FILL_OR_UNTOUCHED_PROOF",
            "economic_approval":"NOT_EVALUATED",
            "no_trade_baseline_usdt":0,
            "owner_live_permission":False,"owner_paper_permission":False,
            "caveat":"Replaying inspected months repeatedly is development, not fresh independent evidence.",
        }
        (output/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
        for key,obj in [("B_A",first),("C_A",final[0]),("C_B1",final[1]),("C_B2",final[2])]+[(x["brain"],x) for x in baselines]:
            with (output/(key+"_trades.jsonl")).open("w") as f:
                for row in obj["trades"]:
                    f.write(json.dumps(row,sort_keys=True)+"\n")
        return summary
    finally:
        c.close()
