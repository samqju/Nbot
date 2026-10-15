"""G7 2,000-row synthetic-only dependence/uncertainty/abstention benchmark.

2000 gross laboratory outcomes from 100 BTC-correlated 20-side event blocks:
scientifically qualified 0, no data-learned model, NO TRADE, no service.
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
from nbot_v5_1.learning_science import evaluate_lab,quality_report
from nbot_v5_1.learning_snapshots import save_lab_snapshot,verify_lab_snapshot

ROWS=2000
EVENTS=100
PER_EVENT=20
MAX_P99_MS=1500
MAX_RSS_KIB=256000
MAX_DISK_BYTES=4*1024*1024


def percentile(items,q):
    a=sorted(items)
    return a[min(len(a)-1,int((len(a)-1)*q))]


def bench():
    beginning=time.perf_counter();cpu=time.process_time()
    rows=[]
    per_event_latency=[]
    for event in range(EVENTS):
        before=time.perf_counter()
        decision=BASE+event*600000
        for j in range(PER_EVENT):
            idx=event*PER_EVENT+j
            sym="BTCUSDT" if j==0 else f"TEST{j:02d}USDT"
            value="0.3" if (idx%4) else "-0.8"
            rows.append(fixture(idx,decision=decision,symbol=sym,
                side="LONG" if j%2 else "SHORT",
                market="RANGE" if event%3 else "TRANSITION",
                btc="UP" if event%2 else "DOWN",
                net=value))
        per_event_latency.append((time.perf_counter()-before)*1000)
    rows=tuple(rows)
    if len(rows)!=ROWS:
        raise RuntimeError("G7_SYNTHETIC_POPULATION_INCOMPLETE")
    dataset=assemble_lab(rows,cutoff_ms=BASE+(EVENTS+1)*600000)
    quality=quality_report(dataset)
    evaluation=evaluate_lab(dataset,split_at_ms=BASE+50*600000,
                           bootstrap=150,embargo_ms=600000)
    if (quality.total!=ROWS or quality.synthetic_modeled!=ROWS
         or quality.effective_independent_blocks!=EVENTS
         or quality.scientifically_qualified!=0 or
         verified_learning_count(dataset)!=0 or
         evaluation.model_status!="NO_MODEL" or
         evaluation.recommendation!="NO_TRADE"):
        raise RuntimeError("G7_FALSE_SCIENTIFIC_OR_INDEPENDENT_COUNT")
    with tempfile.TemporaryDirectory(prefix="nbot-g7-lab-evidence-") as tmp:
        root=Path(tmp)
        snap=save_lab_snapshot(root,dataset,evaluation)
        repeat=save_lab_snapshot(root,dataset,evaluation)
        opened=verify_lab_snapshot(root,snap["name"],snap["sha256"])
        if (repeat["status"]!="IDEMPOTENT_VERIFIED" or opened["rows"]!=ROWS):
            raise RuntimeError("G7_SNAPSHOT_NOT_REPLAYED")
        disk=sum(x.stat().st_size for x in root.iterdir())
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={"schema":"NBOT_V5_1_G7_2000_SYNTHETIC_LAB_BENCH_V1",
       "synthetic_only":True,"raw_outcomes":ROWS,
       "unique_btc_market_event_blocks":quality.effective_independent_blocks,
       "independent_original_source_outcomes":0,
       "scientifically_qualified_outcomes":0,
       "num_context_findings":len(evaluation.findings),
       "purged_blocks":evaluation.purged_blocks,
       "train_blocks_lab_only":evaluation.train_blocks,
       "holdout_blocks_lab_only":evaluation.holdout_blocks,
       "model_status":evaluation.model_status,
       "recommendation":evaluation.recommendation,
       "snapshot_replay":"VERIFIED_LAB_NO_MODEL",
       "snapshot_bytes":disk,
       "p50_generator_ms":round(percentile(per_event_latency,.50),3),
       "p95_generator_ms":round(percentile(per_event_latency,.95),3),
       "p99_generator_ms":round(percentile(per_event_latency,.99),3),
       "rss_kib":rss,
       "cpu_seconds":round(time.process_time()-cpu,3),
       "wall_seconds":round(time.perf_counter()-beginning,3),
       "no_services_or_orders":True,
       "limits":{"p99_ms":MAX_P99_MS,"rss_kib":MAX_RSS_KIB,
                 "disk_bytes":MAX_DISK_BYTES}}
    result["passed"]=(result["p99_generator_ms"]<MAX_P99_MS
          and rss<MAX_RSS_KIB and disk<MAX_DISK_BYTES)
    return result

if __name__=="__main__":
    result=bench()
    print(json.dumps(result,sort_keys=True),flush=True)
    sys.exit(0 if result["passed"] else 2)
