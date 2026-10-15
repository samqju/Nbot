"""G4 synthetic 20 deep sources × quote/trade/mark, independent gzip replay.

One small-VPS engineering performance estimate, NOT continuous Binance
original quote/trade/funding authenticity or remote archive qualification.
"""
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.deep_segments import DeepSegmentRecorder,DeepSegmentHold
from test_v5_1_g2 import manifest,history,END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW

ROUNDS=60
DEEP=20
MAX_P99_MS=1000
MAX_RSS_KIB=256000
MAX_DISK_BYTES=32*1024*1024

def pct(values,p):
    a=sorted(values)
    return a[min(len(a)-1,int((len(a)-1)*p))]

def run():
    start=time.perf_counter()
    cpu=time.process_time()
    m=manifest()
    book=ObservationBook(m)
    for s in m.symbols:
        if not book.bootstrap(s,history(s),as_of_ms=END_DECISION):
            raise RuntimeError("G4_BAD_BROAD_BOOTSTRAP")
    g3=explore_event(book,FiveMinuteEvent(END_OPEN,END_DECISION),capacity_slots=0)
    deep=choose_deep(m,g3)
    assert len(deep.symbols)==DEEP and "BTCUSDT" in deep.symbols
    with tempfile.TemporaryDirectory(prefix="nbot-g4-20-bench-") as d:
        root=Path(d)
        recorder=DeepSegmentRecorder(root,symbols=deep.symbols)
        counts={"QUOTE":0,"TRADE":0,"MARK":0}
        delays=[]
        for cycle in range(ROUNDS):
            begun=time.perf_counter()
            when=NOW+cycle*1000
            for i,s in enumerate(deep.symbols):
                for kind in ("QUOTE","TRADE","MARK"):
                    record=frame(kind,symbol=s,id=cycle+5,received=when)
                    ev=recorder.append(kind=kind,raw=record,
                              received_at_ms=when,epoch=1)
                    if ev.state!="RECEIVED_UNQUALIFIED_LOCAL_WSS":
                        raise RuntimeError("G4_SOURCE_HOLD")
                    counts[kind]+=1
            recorder.flush()
            delays.append((time.perf_counter()-begun)*1000)
        replay,sha,segments=recorder.replay()
        if len(replay)!=3*DEEP*ROUNDS or segments!=ROUNDS:
            raise RuntimeError("G4_SOURCE_REPLAY_INCOMPLETE")
        used=sum(p.stat().st_size for p in root.iterdir())
        # Recover from a simulated process crash: never infer WSS live epoch.
        restarted=DeepSegmentRecorder(root,symbols=deep.symbols)
        recovered=restarted.attach()
        if recovered!=len(replay) or restarted.epoch_holds!=set(deep.symbols):
            raise RuntimeError("G4_RESTART_CONTINUITY_FABRICATED")
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={"schema":"NBOT_V5_1_G4_DEEP20_SYNTHETIC_BENCH_V1",
      "synthetic_only":True,"deep_symbols":DEEP,"btc_included":True,
      "five_minute_events_equivalent":ROUNDS,
      "quote_frames":counts["QUOTE"],"trade_frames":counts["TRADE"],
      "mark_frames":counts["MARK"],"total_frames":len(replay),
      "receipt_segments":segments,"replayed_frames":recovered,
      "new_source_epoch_holds_after_restart":len(restarted.epoch_holds),
      "latency_p50_ms":round(pct(delays,.5),3),
      "latency_p95_ms":round(pct(delays,.95),3),
      "latency_p99_ms":round(pct(delays,.99),3),
      "max_latency_ms":round(max(delays),3),
      "rss_kib":rss,"cpu_seconds":round(time.process_time()-cpu,3),
      "wall_seconds":round(time.perf_counter()-start,3),
      "segment_disk_bytes":used,
      "latency_limit_ms":MAX_P99_MS,"rss_limit_kib":MAX_RSS_KIB,
      "disk_limit_bytes":MAX_DISK_BYTES,
      "no_orders":True,"original_source_qualified":False,
      "after_cost_qualified":False,"temporary_segments_removed":True}
    result["passed"]=(result["latency_p99_ms"]<MAX_P99_MS
      and rss<MAX_RSS_KIB and used<MAX_DISK_BYTES)
    return result

if __name__=="__main__":
    result=run()
    print(json.dumps(result,sort_keys=True),flush=True)
    sys.exit(0 if result["passed"] else 2)
