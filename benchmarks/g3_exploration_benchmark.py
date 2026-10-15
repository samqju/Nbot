"""G3 100 markets x 2 sides x 24 V4 detectors offline benchmark.

Only synthetic finished candle histories and simulated research capacity.
No exchange network, original tick/quote custody, funding or trade orders.
"""
from __future__ import annotations

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

from test_v5_1_g2 import manifest, history, bar, END_OPEN, END_DECISION
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS
from nbot_v5_1.exploration import explore_event, PATTERN_IDS
from nbot_v5_1.exploration_store import ExplorationStore

MARKETS=100
SIDES=2
DETECTORS=24
EVENTS=12
MAX_P99_MS=1500
MAX_RSS_KIB=250*1024
MAX_DISK_BYTES=32*1024*1024


def percentile(values, pct):
    s=sorted(values)
    return s[min(len(s)-1,int((len(s)-1)*pct))]


def run():
    begin=time.perf_counter()
    cpu=time.process_time()
    univ=manifest(145)
    book=ObservationBook(univ)
    if len(univ.symbols)!=MARKETS:
        raise AssertionError("G3_WRONG_COHORT")
    for sym in univ.symbols:
        if not book.bootstrap(sym,history(sym),as_of_ms=END_DECISION):
            raise AssertionError("G3_BOOTSTRAP_NOT_READY")
    delays=[]
    counters={"observed":0,"source":0,"capacity":0}
    paths=[]
    with tempfile.TemporaryDirectory(prefix="nbot-g3-bench-") as directory:
        store=ExplorationStore(Path(directory))
        for index in range(EVENTS):
            event=FiveMinuteEvent(END_OPEN+index*INTERVAL_MS,
                                  END_DECISION+index*INTERVAL_MS)
            if index:
                for sym in univ.symbols:
                    if index==5 and sym in univ.symbols[1:11]:
                        book.mark_gap(sym,reason="SIMULATED_SOURCE_GAP")
                    book.ingest(bar(sym,event.event_open_ms,
                             received=event.decision_at_ms),
                             decision_at_ms=event.decision_at_ms)
            slots=0 if index%4==0 else 2
            limit=40 if index%3==0 else 200
            start=time.perf_counter()
            batch=explore_event(book,event,
                    capacity_slots=slots,evaluation_limit=limit)
            if len(batch.rows)!=MARKETS*SIDES:
                raise AssertionError("G3_LOST_DIRECTION_DENOMINATOR")
            if any(len(r.detector_states)!=DETECTORS for r in batch.rows):
                raise AssertionError("G3_DETECTOR_MISSING")
            if any(r.authority.value!="NONE" or r.disposition.value!="NO_TRADE"
                   for r in batch.rows):
                raise AssertionError("G3_ORDER_AUTHORITY_LEAK")
            if index>=5 and batch.source_skipped_pairs!=20:
                raise AssertionError("G3_DID_NOT_HOLD_SOURCE_GAP")
            if index<5 and batch.source_skipped_pairs:
                raise AssertionError("G3_FALSE_SOURCE_GAP")
            file_name=store.append(batch)
            paths.append(file_name)
            counters["observed"]+=batch.evaluated_pairs
            counters["source"]+=batch.source_skipped_pairs
            counters["capacity"]+=batch.capacity_skipped_pairs
            delays.append((time.perf_counter()-start)*1000)
        recovered=store.replay()
        if len(recovered)!=EVENTS:
            raise AssertionError("G3_REPLAY_INCOMPLETE")
        if len({r["id"] for r in recovered})!=EVENTS:
            raise AssertionError("G3_DUPLICATE_OR_LOST_EVENT")
        disk=sum(p.stat().st_size for p in Path(directory).iterdir())
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    record={"schema":"NBOT_V5_1_G3_BENCHMARK_V1",
            "synthetic_only":True,
            "market_count":MARKETS,"directions_per_market":SIDES,
            "detectors_per_direction":DETECTORS,"event_count":EVENTS,
            "expected_direction_records":MARKETS*SIDES*EVENTS,
            "observed_pairs":counters["observed"],
            "source_skipped_pairs":counters["source"],
            "capacity_skipped_pairs":counters["capacity"],
            "latency_p50_ms":round(percentile(delays,.50),3),
            "latency_p95_ms":round(percentile(delays,.95),3),
            "latency_p99_ms":round(percentile(delays,.99),3),
            "max_latency_ms":round(max(delays),3),
            "max_rss_kib":rss,"cpu_seconds":round(time.process_time()-cpu,3),
            "wall_seconds":round(time.perf_counter()-begin,3),
            "receipt_disk_bytes":disk,
            "receipts_replayed":EVENTS,"temporary_data_removed":True,
            "limits":{"p99_ms":MAX_P99_MS,
                      "rss_kib":MAX_RSS_KIB,"disk_bytes":MAX_DISK_BYTES}}
    record["passed"]=(record["latency_p99_ms"]<MAX_P99_MS
          and rss<MAX_RSS_KIB and disk<MAX_DISK_BYTES
          and sum(counters.values())==MARKETS*SIDES*EVENTS)
    return record


if __name__=="__main__":
    r=run()
    print(json.dumps(r,sort_keys=True),flush=True)
    sys.exit(0 if r["passed"] else 2)
