"""G9 synthetic single-Champion LAB lifecycle capacity and crash benchmark.

Nothing in this script is a PAPER trading release. All proposals, simulated
paper-like accounting and filled positions have AUTHORITY NONE and cannot be
used in any real or approved paper service.
"""
from __future__ import annotations
import json
import resource
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
from test_v5_1_g9_paper import policy,proposal,quote,costs,KEY,MODEL,AT
from nbot_v5_1.paper_lab import ChampionLabPaperBook
from nbot_v5_1.paper_contract import PaperHold,authorize_real_paper_release
from nbot_v5_1.research_journal import ResearchJournal

TRIALS=100
P99_MS=1500
RSS_LIMIT=256000
LEDGER_LIMIT=16*1024*1024

def p99(values):
    ordered=sorted(values)
    return ordered[int((len(ordered)-1)*.99)]

def bench():
    started=time.perf_counter();cpu=time.process_time()
    with tempfile.TemporaryDirectory(prefix="nbot-g9-lab-bench-") as d:
        dest=Path(d)/"g9-lab.jsonl"
        engine=ChampionLabPaperBook(ResearchJournal(dest),policy=policy(),
                                    model_sha256=MODEL,lab_key=KEY)
        delays=[]
        for i in range(1,TRIALS+1):
            t=AT+i*300000
            before=time.perf_counter()
            admission=engine.simulate_entry(proposal(i=i,at=t),
                                            quote(at=t),costs(at=t),now_ms=t)
            if admission["status"]!="SYNTHETIC_LAB_OPEN_NOT_PAPER":
                raise RuntimeError("G9_BENCH_FAILED_TO_ADMIT_LAB")
            occupied=engine.simulate_entry(proposal(i=200+i,at=t),
                                           quote(at=t),costs(at=t),now_ms=t)
            if "ONE_POSITION_ALREADY_OCCUPIED" not in occupied["reasons"]:
                raise RuntimeError("G9_SECOND_POSITION_NOT_VETOED")
            end=engine.simulate_mark_or_exit(
                 quote(at=t+1000,bid="105.3",ask="105.4"),
                 costs(at=t+1000),now_ms=t+1000)
            if (end["status"]!="LAB_SIMULATED_SETTLEMENT_NOT_PAPER"
                    or engine.state.occupied or engine.state.paper_authority!="NONE"):
                raise RuntimeError("G9_BENCH_SETTLEMENT_FALSE_PASS")
            delays.append((time.perf_counter()-before)*1000)
        if engine.state.settled!=TRIALS:
            raise RuntimeError("G9_WRONG_COUNT")
        # Crash with exactly one active; must remain counted HELD.
        t=AT+(TRIALS+1)*300000
        engine.simulate_entry(proposal(i=TRIALS+1,at=t),
                              quote(at=t),costs(at=t),now_ms=t)
        recovered=ChampionLabPaperBook(ResearchJournal(dest),policy=policy(),
                                       model_sha256=MODEL,lab_key=KEY)
        if (not recovered.state.occupied or not recovered.state.held
             or not recovered.restart_hold or recovered.state.settled!=TRIALS):
            raise RuntimeError("G9_RESTART_FREED_HYPOTHETICAL_POSITION")
        refused=False
        try:
            authorize_real_paper_release()
        except PaperHold:
            refused=True
        if not refused:raise RuntimeError("G9_LAB_UNAUTHORIZED_PAPER_RELEASE")
        recovered.censor_held_lab(now_ms=t+1000,reason="UNCLEAN_RESTART")
        again=ChampionLabPaperBook(ResearchJournal(dest),policy=policy(),
                                   model_sha256=MODEL,lab_key=KEY)
        if (again.state.occupied or again.state.censored!=1 or
            again.state.settled!=TRIALS or again.state.paper_authority!="NONE"):
            raise RuntimeError("G9_CENSORED_RESTART_RECONCILIATION_FAIL")
        bytes_used=dest.stat().st_size
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out={"schema":"NBOT_V5_1_G9_SYNTHETIC_CHAMPION_LAB_BENCH_V1",
         "trials":TRIALS,"book":"CHAMPION_LAB_ONLY",
         "independent_challenger_required":False,
         "simulated_settlements":TRIALS,"maximum_simultaneous_positions":1,
         "vetoed_second_positions":TRIALS,
         "restart_occupied_hold":1,
         "censored_on_recovery":1,
         "qualified_original_champions":0,
         "paper_authority":"NONE","exchange_orders":0,
         "p99_lab_transition_ms":round(p99(delays),3),
         "ledger_bytes":bytes_used,"rss_kib":rss,
         "cpu_seconds":round(time.process_time()-cpu,3),
         "wall_seconds":round(time.perf_counter()-started,3),
         "limits":{"p99_ms":P99_MS,"rss_kib":RSS_LIMIT,
                   "journal_bytes":LEDGER_LIMIT},
         "no_running_services":True}
    out["passed"]=(out["p99_lab_transition_ms"]<P99_MS and
                   rss<RSS_LIMIT and bytes_used<LEDGER_LIMIT)
    return out

if __name__=="__main__":
    outcome=bench()
    print(json.dumps(outcome,sort_keys=True),flush=True)
    sys.exit(0 if outcome["passed"] else 2)
