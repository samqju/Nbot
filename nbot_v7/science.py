"""Economic diagnostics and simple non-learned comparators for OFFLINE research.

Matched calendar/symbol/capital policies do not automatically match trade count;
do not claim statistical significance without dependency-aware uncertainty.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import random
from math import ceil
from .decision import choose

class RuleBrain:
    def __init__(self, mode:str):
        if mode not in ("momentum","liquidity","deterministic_random","v6_signal_control"):
            raise ValueError("INVALID_SIMPLE_COMPARATOR")
        self.mode=mode
        self.version="BASELINE_"+mode.upper()

    def score(self,rows,kind):
        scores=[]
        for r in rows:
            x=json.loads(r["features"])
            side=1 if kind=="watch" or r["side"]=="LONG" else -1
            if self.mode=="v6_signal_control":
                expected=.001 if kind=="watch" or r["family"].startswith("V6_") else -.001
                rank=abs(x["r12"])
            elif self.mode=="momentum":
                strength=side*x["r12"]
                # Trade when momentum and current volume quality clear simple bars.
                expected=.001 if strength>.003 and x["volume_ratio"]>.75 else -.001
                rank=strength
            elif self.mode=="liquidity":
                expected=.001 if x["volume_ratio"]>1.0 else -.001
                rank=x["volume_ratio"]
            else:
                t=(r["review_ms"] if kind=="watch" else r["decision_ms"])
                digest=sha256((r["symbol"]+"|"+str(t)+"|"+kind).encode()).digest()
                rank=int.from_bytes(digest[:8],"big")/2**64
                expected=.001
            scores.append((expected,rank))
        return scores

def daily_pnl(report:dict) -> dict[int,float]:
    bucket=defaultdict(float)
    stake=report["notional_each_usdt"]
    for r in report["trades"]:
        day=(int(r["exit_ms"])//86_400_000)
        bucket[day]+=float(r["net_after_cost"])*stake
    return dict(bucket)

def block_bootstrap_uplift(challenger:dict,incumbent:dict,*,blocks_days:int=7,
                           iterations:int=1000,seed:int=72026)->dict:
    if challenger["period_start_ms"]!=incumbent["period_start_ms"] or challenger["period_end_ms"]!=incumbent["period_end_ms"]:
        raise ValueError("UNMATCHED_EVALUATION_PERIODS")
    if challenger["trading_sleeve_usdt"]!=incumbent["trading_sleeve_usdt"]:
        raise ValueError("UNMATCHED_PORTFOLIO_CAPITAL")
    start=challenger["period_start_ms"]//86_400_000
    end=challenger["period_end_ms"]//86_400_000
    if end-start<blocks_days*3:
        return {"status":"TOO_FEW_DEPENDENCE_BLOCKS"}
    ch=daily_pnl(challenger); incumbent_daily=daily_pnl(incumbent)
    differences=[(ch.get(d,0)-incumbent_daily.get(d,0))
                 /challenger["trading_sleeve_usdt"]*100 for d in range(start,end)]
    n=len(differences)
    rng=random.Random(seed)
    draws=[]
    for _ in range(iterations):
        sampled=[]
        while len(sampled)<n:
            pos=rng.randrange(0,n-blocks_days+1)
            sampled.extend(differences[pos:pos+blocks_days])
        draws.append(sum(sampled[:n]))
    draws.sort()
    estimate=sum(differences)
    lo=draws[int(.025*iterations)]
    hi=draws[min(iterations-1,int(.975*iterations))]
    return {
        "status":"DIAGNOSTIC_NOT_ECONOMIC_APPROVAL",
        "uplift_pct_of_sleeve":round(estimate,5),
        "bootstrap_95pct_interval_pct":[round(lo,5),round(hi,5)],
        "interval_lower_above_zero":lo>0,
        "time_block_days":blocks_days,"resamples":iterations,
        "matched_evaluation_days":n,
        "warning":"5m proxy and non-independent market days; bootstrap does not certify edge",
    }


def ranking_diagnostics(conn,brain,start_ms,end_ms,max_groups=1000):
    """Time-thinned full cohorts; hindsight only scores forecasts after selection."""
    times=[r[0] for r in conn.execute("SELECT DISTINCT decision_ms FROM candidate WHERE decision_ms>=? AND decision_ms<? ORDER BY decision_ms",(start_ms,end_ms))]
    stride=max(1,ceil(len(times)/max_groups))
    count=groups=0
    squared=absolute=regret=selected_net=best_net=0.0
    families=defaultdict(int)
    for t in times[::stride]:
        rows=conn.execute("SELECT * FROM candidate WHERE decision_ms=? ORDER BY symbol,side,family",(t,)).fetchall()
        choice,predictions=choose(brain,rows)
        labels={(r[0],r[1],r[2]):r[3] for r in conn.execute("SELECT symbol,side,family,net FROM opportunity WHERE decision_ms=?",(t,))}
        actual=[]
        for row,prediction in zip(rows,predictions):
            key=(row["symbol"],row["side"],row["family"])
            if key not in labels:continue
            error=prediction[0]-labels[key]
            squared+=error*error;absolute+=abs(error);count+=1
            actual.append(labels[key])
        if not actual:continue
        best=max(0,max(actual))
        got=0.0
        if choice is not None:
            row,_=choice
            key=(row["symbol"],row["side"],row["family"])
            if key not in labels:continue
            got=labels[key];families[row["family"]]+=1
        groups+=1;regret+=best-got;selected_net+=got;best_net+=best
    return {"authority":"SAMPLED_RANKING_DIAGNOSTIC_NOT_WALLET_PNL","sample_stride_events":stride,
            "labeled_predictions":count,"evaluated_groups":groups,
            "net_prediction_rmse":math.sqrt(squared/count) if count else None,
            "net_prediction_mae":absolute/count if count else None,
            "mean_top1_conditional_net":selected_net/groups if groups else None,
            "mean_hindsight_regret":regret/groups if groups else None,
            "selected_family_counts":dict(sorted(families.items())),
            "warning":"Cross-sectional conditional outcomes are not jointly executable portfolio returns."}
