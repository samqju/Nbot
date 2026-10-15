"""G5 offline synthetic 20 markets x 2 sides x 40 virtual-slot acceptance.

No actual Binance path, original source warmup, fill or economic grade. All
simulation stops/targets are STATUS=COST_PENDING_UNQUALIFIED. Actual G4
source continuity, live quote witness and G6 economics remain separately HOLD.
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

from test_v5_1_g2 import manifest,END_OPEN,END_DECISION
from nbot_v5_1.core import FiveMinuteEvent,INTERVAL_MS
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.research_intent import freeze_intent
from nbot_v5_1.research_book import VirtualResearchBook,SyntheticTick
from nbot_v5_1.research_journal import ResearchJournal

ROUNDS=24
CAP=40
BUDGET_LATENCY_P99_MS=1500
BUDGET_RSS_KIB=256000
BUDGET_DISK_BYTES=32*1024*1024


def percentile(data,q):
    s=sorted(data)
    return s[min(len(s)-1,int((len(s)-1)*q))]


def benchmark():
    wall=time.perf_counter();cpu=time.process_time()
    broad=manifest(20)
    gb=ObservationBook(broad)
    g3=explore_event(gb,FiveMinuteEvent(END_OPEN,END_DECISION),capacity_slots=0)
    deep=choose_deep(broad,g3,count=20)
    all_pairs=tuple((s,side) for s in deep.symbols for side in ("LONG","SHORT"))
    if len(all_pairs)!=40 or "BTCUSDT" not in deep.symbols:
        raise RuntimeError("G5_INCORRECT_20X2_COHORT")
    latencies=[];frame_count=0; max_active=0; reviews=0
    counts={"admitted":0,"rejected_capacity":0,"ineligible":0,"terminals":0}
    ids={s:0 for s in deep.symbols}
    with tempfile.TemporaryDirectory(prefix="nbot-g5-40-bench-") as root:
        journal=ResearchJournal(Path(root)/"g5.jsonl")
        book=VirtualResearchBook(journal)
        for n in range(ROUNDS):
            begin=time.perf_counter()
            ev=FiveMinuteEvent(END_OPEN+n*INTERVAL_MS,END_DECISION+n*INTERVAL_MS)
            # First reconcile existing price paths at real clock positions.
            if n:
                for s in deep.symbols:
                    ids[s]+=1
                    result=book.ingest(SyntheticTick(s,ev.decision_at_ms,
                       "100",1,ids[s],END_DECISION))
                    counts["terminals"]+=len(result);frame_count+=1
            def supplier():
                proposals=[]
                for sym,side in all_pairs:
                    proposals.append(freeze_intent(symbol=sym,side=side,
                        event_open_ms=ev.event_open_ms,
                        declared_at_ms=ev.decision_at_ms,
                        activates_at_ms=ev.decision_at_ms+1,
                        horizon_ms=INTERVAL_MS,
                        entry_reference="100",stop="95" if side=="LONG" else "105",
                        target="105" if side=="LONG" else "95",
                        cohort_sha=deep.manifest_sha,
                        observation_sha="a"*64,source_epoch=1,
                        source_grade="SYNTHETIC_OFFLINE_TEST_ONLY"))
                return tuple(proposals)
            result=book.review(ev,deep,supplier)
            reviews+=1
            if len(result.decision_rows)!=40:
                raise RuntimeError("G5_FULL_40_DENOMINATOR_LOST")
            if book.occupied>40 or len(book.by_pair)!=book.occupied:
                raise RuntimeError("G5_OCCUPANCY_BOUND_BROKEN")
            max_active=max(book.occupied,max_active)
            counts["admitted"]+=result.openings
            counts["rejected_capacity"]+=result.skipped_capacity
            counts["ineligible"]+=result.skipped_ineligible
            # Two observations per coin, one shared source stream.
            for s in deep.symbols:
                ids[s]+=1
                r=book.ingest(SyntheticTick(s,ev.decision_at_ms+2,
                   "100",1,ids[s],END_DECISION))
                counts["terminals"]+=len(r);frame_count+=1
            # Intra-candle stop/target before next boundary on a quarter
            # of the coin cohort, in BOTH directions using the same tick.
            for s in deep.symbols[:5]:
                ids[s]+=1
                r=book.ingest(SyntheticTick(s,ev.decision_at_ms+120000,
                   "106",1,ids[s],END_DECISION))
                counts["terminals"]+=len(r);frame_count+=1
            book.checkpoint(ev.decision_at_ms+120001)
            latencies.append((time.perf_counter()-begin)*1000)
        rows,head=journal.replay()
        used=(Path(root)/"g5.jsonl").stat().st_size
        if len(rows)<ROUNDS or book.status()["qualified_after_cost"]:
            raise RuntimeError("G5_JOURNAL_OR_ECONOMICS_FALSE_PASS")
        # New process MUST quarantine every remaining active path and never
        # retroactively claim missed stop/target after lost RAM/epoch.
        restarted=VirtualResearchBook(journal)
        if restarted.occupied!=book.occupied or restarted.status()["held"]!=restarted.occupied:
            raise RuntimeError("G5_RESTART_INVENTED_CLOSURE")
        recovered_head=restarted.head
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output={"schema":"NBOT_V5_1_G5_SYNTHETIC_BENCH_V1",
       "synthetic_only":True,"markets":20,"directions":40,
       "five_minute_reviews":reviews,"source_frames_shared":frame_count,
       "journal_rows":len(rows),"max_concurrent_virtual":max_active,
       "opens":counts["admitted"],"capacity_skips":counts["rejected_capacity"],
       "ineligible_skips":counts["ineligible"],
       "closed_to_cost_pending":counts["terminals"],
       "held_on_restart":restarted.status()["held"],
       "qualified_after_cost":0,
       "p50_review_ms":round(percentile(latencies,.5),3),
       "p95_review_ms":round(percentile(latencies,.95),3),
       "p99_review_ms":round(percentile(latencies,.99),3),
       "max_review_ms":round(max(latencies),3),
       "peak_rss_kib":rss,"cpu_seconds":round(time.process_time()-cpu,3),
       "wall_seconds":round(time.perf_counter()-wall,3),
       "journal_bytes":used,"last_replayed_sha":head,
       "last_restarted_sha":recovered_head,
       "limits":{"p99_ms":BUDGET_LATENCY_P99_MS,
           "rss_kib":BUDGET_RSS_KIB,"disk_bytes":BUDGET_DISK_BYTES},
       "no_orders":True,"source_original_qualified":False,
       "temp_files_deleted":True}
    output["passed"]=(max_active<=CAP
      and output["p99_review_ms"]<BUDGET_LATENCY_P99_MS
      and rss<BUDGET_RSS_KIB and used<BUDGET_DISK_BYTES)
    return output

if __name__=="__main__":
    res=benchmark()
    print(json.dumps(res,sort_keys=True),flush=True)
    sys.exit(0 if res["passed"] else 2)
