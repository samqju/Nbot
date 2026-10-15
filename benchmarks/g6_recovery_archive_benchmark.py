"""G6 bounded synthetic 20×3-source custody, closed-bar recovery, cost review.

No original Binance session, no provider-signed quote/fill, no 1-second
futures claim, no true off-host archived receipt: all stay HOLD at startup.
"""
from __future__ import annotations
import json,resource,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))

from test_v5_1_g2 import manifest,END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW
from test_v5_1_g6_recovery import lab_case,kline
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.deep_segments import DeepSegmentRecorder
from nbot_v5_1.archive_custody import seal_archive,verify_archive
from nbot_v5_1.recovery_contract import completed_five_minute_bars,verify_aggtrade_gap
from nbot_v5_1.economic_audit import assess_model_only,qualified_learning_label_count

ROUNDS=24
P99_LIMIT_MS=1500
RSS_LIMIT_KIB=256000
DISK_LIMIT=32*1024*1024

def percentile(xs,p):
    a=sorted(xs)
    return a[int((len(a)-1)*p)]

def bench():
    start=time.perf_counter();cpu=time.process_time()
    broad=manifest(20)
    book=ObservationBook(broad)
    g3=explore_event(book,FiveMinuteEvent(END_OPEN,END_DECISION),capacity_slots=0)
    deep=choose_deep(broad,g3,count=20)
    symbols=deep.symbols
    if len(symbols)!=20 or "BTCUSDT" not in symbols:raise RuntimeError("G6_BAD_COHORT")
    latency=[];rows=0;contexts=0;models=0
    with tempfile.TemporaryDirectory(prefix="nbot-g6-lab-") as d:
        base=Path(d)
        source=base/"raw";archive=base/"sealed"
        source.mkdir(mode=0o700);archive.mkdir(mode=0o700)
        rec=DeepSegmentRecorder(source,symbols=symbols)
        for i in range(ROUNDS):
            start_loop=time.perf_counter()
            t=NOW+1000*i
            for s in symbols:
                for kind in ("TRADE","QUOTE","MARK"):
                    e=rec.append(kind=kind,
                       raw=frame(kind,symbol=s,id=5+i,received=t),
                       received_at_ms=t,epoch=1)
                    if e.state=="HOLD":raise RuntimeError("G6_RAW_SOURCE_REJECTED")
                    rows+=1
            rec.flush()
            c=completed_five_minute_bars(symbol="BTCUSDT",
                raw=json.dumps([kline(END_OPEN)]).encode(),
                received_at_ms=END_DECISION,source_epoch=1,
                start_open_ms=END_OPEN,end_open_ms=END_OPEN)
            if c.state!="CANDLE_CONTEXT_ONLY" or c.qualifies_original_first_touch:
                raise RuntimeError("G6_CANDLE_FALSE_ORIGINAL_GRADE")
            contexts+=1
            intent,terminal,entry,exit,costs=lab_case()
            a=assess_model_only(intent=intent,terminal=terminal,
                entry_quote=entry,exit_quote=exit,costs=costs,
                audit_at_ms=END_DECISION+1001)
            if a.state!="MODELED_SYNTHETIC_ONLY_NOT_QUALIFIED" or a.research_qualified_count:
                raise RuntimeError("G6_FALSE_ECONOMIC_LABEL")
            models+=1
            latency.append((time.perf_counter()-start_loop)*1000)
        snap=seal_archive(source=source,destination=archive,symbols=symbols)
        checked=verify_archive(root=archive,symbols=symbols)
        if checked["frames"]!=rows or checked["segments"]!=ROUNDS:
            raise RuntimeError("G6_ARCHIVE_REPLAY_LOST_FRAMES")
        if qualified_learning_label_count(())!=0:raise RuntimeError("G6_FAKE_SCIENCE")
        disk=sum(p.stat().st_size for p in source.iterdir())
        disk+=sum(p.stat().st_size for p in archive.iterdir())
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={"schema":"NBOT_V5_1_G6_SYNTHETIC_BENCH_V1",
      "synthetic_only":True,"markets":len(symbols),"routes":3,
      "rounds":ROUNDS,"raw_frames":rows,"replayed_frames":checked["frames"],
      "segments":ROUNDS,"closed_bar_contexts":contexts,
      "modeled_cost_scenarios":models,
      "qualifying_original_first_touches":0,"qualified_after_cost":0,
      "offhost_copy_proven":False,"continuous_capture_proven":False,
      "p50_round_ms":round(percentile(latency,.5),3),
      "p95_round_ms":round(percentile(latency,.95),3),
      "p99_round_ms":round(percentile(latency,.99),3),
      "rss_kib":rss,"disk_bytes":disk,
      "cpu_seconds":round(time.process_time()-cpu,3),
      "wall_seconds":round(time.perf_counter()-start,3),
      "no_trades":True,"temp_files_removed":True,
      "limits":{"p99_ms":P99_LIMIT_MS,"rss_kib":RSS_LIMIT_KIB,
                "disk_bytes":DISK_LIMIT}}
    result["passed"]=(result["p99_round_ms"]<P99_LIMIT_MS
                    and rss<RSS_LIMIT_KIB and disk<DISK_LIMIT)
    return result

if __name__=="__main__":
    r=bench()
    print(json.dumps(r,sort_keys=True),flush=True)
    sys.exit(0 if r["passed"] else 2)
