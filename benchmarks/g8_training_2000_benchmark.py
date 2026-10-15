"""G8 bounded, deterministic 2,000 synthetic rows / 100 BTC block trainer.

Produces one frozen non-executable laboratory card and untouched chronological
synthetic backtest. This is NOT a genuine Champion, qualified market edge,
source-authenticated model, paper approval, or exchange API application.
"""
from __future__ import annotations
import json
from pathlib import Path
import resource
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
from test_v5_1_g7_learning import fixture,BASE
from nbot_v5_1.learning_contract import assemble_lab,verified_learning_count
from nbot_v5_1.training_lab import (LabProtocol,train_lab,
       evaluate_frozen_lab,verify_model,require_authorized_champion,TrainingHold)
from nbot_v5_1.training_freeze import seal_lab_model,verify_lab_model

N=2000
MARKET_EVENTS=100
STEP=600000
P99_BUDGET_MS=1500
RSS_BUDGET_KIB=256000
STORAGE_BUDGET=4*1024*1024

def pct(v,q):
    s=sorted(v)
    return s[min(len(s)-1,int((len(s)-1)*q))]


def bench():
    start=time.perf_counter();cpu=time.process_time()
    t=[]
    generation=[]
    for block in range(MARKET_EVENTS):
        tick=time.perf_counter()
        for side in range(20):
            i=block*20+side
            symbol=("BTCUSDT" if side==0 else f"TEST{side:02d}USDT")
            outcome="1.00" if (block+side)%5 else "-0.40"
            t.append(fixture(i,decision=BASE+STEP*block,
                 symbol=symbol,side="LONG" if side%2 else "SHORT",
                 btc="UP" if block%2 else "DOWN",
                 market="RANGE" if block%3 else "TRANSITION",net=outcome))
        generation.append((time.perf_counter()-tick)*1000)
    d=assemble_lab(tuple(t),cutoff_ms=BASE+101*STEP)
    policy=LabProtocol(declared_at_ms=BASE-STEP,
        train_cutoff_ms=BASE+49*STEP,
        holdout_start_ms=BASE+51*STEP,
        holdout_end_ms=BASE+99*STEP+200000,
        embargo_ms=300000,min_train_blocks=8,
        min_test_blocks=5,min_context_blocks=5)
    model=train_lab(d,policy)
    rerun=train_lab(d,policy)
    review=evaluate_frozen_lab(model,d)
    second=evaluate_frozen_lab(rerun,d)
    if (model!=rerun or review!=second or
        len(t)!=N or len(d.rows)!=N or
        model.state!="LAB_ONLY_NOT_SCIENTIFIC" or
        model.order_authority!="NONE" or review.release_authority!="NONE"
        or verified_learning_count(d)!=0 or
        review.qualified_original!=0 or
        review.scientific_advantage_proved or
        review.train_blocks>=N or review.test_blocks>=N):
        raise RuntimeError("G8_LAB_OUTPUT_MUST_NOT_BE_SCIENTIFIC")
    try:
        require_authorized_champion(model)
        raise RuntimeError("G8_FALSE_CHAMPION")
    except TrainingHold:
        pass
    with tempfile.TemporaryDirectory(prefix="nbot-g8-bench-") as temp:
        path=Path(temp)
        a=seal_lab_model(path,model,review,d)
        b=seal_lab_model(path,model,review,d)
        verify=verify_lab_model(path,a["name"],a["sha256"],d)
        if (b["status"]!="IDEMPOTENT_VERIFIED_LAB_ONLY" or
            verify["status"]!="VERIFIED_IMMUTABLE_LAB_ONLY" or
            verify["orders_allowed"]):
            raise RuntimeError("G8_FROZEN_REPLAY_FAILED")
        used=sum(p.stat().st_size for p in path.iterdir())
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={"schema":"NBOT_V5_1_G8_OFFLINE_LAB_BENCH_V1",
       "synthetic_only":True,"rows":N,
       "market_event_dependency_blocks":MARKET_EVENTS,
       "train_market_blocks":review.train_blocks,
       "untouched_holdout_blocks":review.test_blocks,
       "purged_blocks":review.purged_blocks,
       "frozen_contexts":len(model.estimates),
       "selected_lab_events":review.selected_events,
       "abstained_lab_events":review.abstained_events,
       "model_net_r_synthetic_only":review.model_net_r,
       "no_trade_net_r":"0",
       "model_state":model.state,
       "qualified_original":0,
       "scientific_advantage_proved":False,
       "paper_or_real_authority":"NONE",
       "independent_model_replay":verify["status"],
       "frozen_card_bytes":used,
       "model_sha256":model.model_sha256,
       "p50_fixture_event_ms":round(pct(generation,.50),3),
       "p95_fixture_event_ms":round(pct(generation,.95),3),
       "p99_fixture_event_ms":round(pct(generation,.99),3),
       "rss_kib":rss,
       "cpu_seconds":round(time.process_time()-cpu,3),
       "wall_seconds":round(time.perf_counter()-start,3),
       "nbot_services_started":False,"orders_sent":0,
       "limits":{"p99_ms":P99_BUDGET_MS,"rss_kib":RSS_BUDGET_KIB,
                 "card_disk_bytes":STORAGE_BUDGET}}
    result["passed"]=(result["p99_fixture_event_ms"]<P99_BUDGET_MS
       and rss<RSS_BUDGET_KIB and used<STORAGE_BUDGET)
    return result


if __name__=="__main__":
    results=bench()
    print(json.dumps(results,sort_keys=True),flush=True)
    sys.exit(0 if results["passed"] else 2)
