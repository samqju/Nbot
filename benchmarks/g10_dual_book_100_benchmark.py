"""G10 two independent paper-LAB book benchmark. Never actual PAPER.

200 shared market events, 100 separately settled synthetic trials EACH book,
plus abstentions and audit/replay under bounded CPU/RSS/storage. Qualified
original additional Research=0; all outcomes LAB only and routing always HOLD.
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
from test_v5_1_g10_challenger import (
    base_policy,cohort,protocol,market,KEY,K2,T)
from nbot_v5_1.challenger_lab import (
    DualBookCompetition,CHAMPION,CHALLENGER)
from nbot_v5_1.research_journal import ResearchJournal

EVENTS=200
P99_BUDGET_MS=1500
RSS_BUDGET_KIB=256000
DISK_BUDGET_BYTES=16*1024*1024

def p99(items):
    s=sorted(items)
    return s[min(len(s)-1,int((len(s)-1)*.99))]


def run():
    beginning=time.perf_counter()
    cpu=time.process_time()
    with tempfile.TemporaryDirectory(prefix="nbot-g10-benchmark-") as root:
        folder=Path(root)
        policy=base_policy()
        evidence=cohort()
        contract=protocol(policy,evidence)
        paths=[folder/"champion.sha.jsonl",folder/"challenger.sha.jsonl",
               folder/"common.sha.jsonl"]
        books=DualBookCompetition(champion_journal=ResearchJournal(paths[0]),
                  challenger_journal=ResearchJournal(paths[1]),
                  review_journal=ResearchJournal(paths[2]),policy=policy,
                  cohort=evidence,protocol=contract,
                  champion_key=KEY,challenger_key=K2)
        lat=[]
        for i in range(EVENTS):
            before=time.perf_counter()
            item=books.step(market(i))
            if item.authority!="NONE":
                raise RuntimeError("G10_SIMULATED_EVENT_GRANTED_AUTHORITY")
            lat.append((time.perf_counter()-before)*1000)
        result=books.review()
        if (result.common_events!=EVENTS or
            result.champion_settled_lab!=100 or
            result.challenger_settled_lab!=100 or
            result.regimes<2 or
            result.genuine_paper_settlements!=0 or
            result.independent_original_outcomes!=0 or
            result.scientific_challenger_approved or
            result.fair_real_paper_comparison or
            result.action!="HOLD" or
            result.financial_authority!="NONE" or
            result.active_champion_sha256!=contract.champion_sha256 or
            result.champion_occupied or result.challenger_occupied):
            raise RuntimeError("G10_FALSE_COMPARISON_OR_PAPER_PROMOTION")
        # Evidence survives a second read of all three independently
        # journaled files; no automatic restart of the contest is authorized.
        reopened=DualBookCompetition(
            champion_journal=ResearchJournal(paths[0]),
            challenger_journal=ResearchJournal(paths[1]),
            review_journal=ResearchJournal(paths[2]),policy=policy,
            cohort=evidence,protocol=contract,champion_key=KEY,
            challenger_key=K2)
        if (not reopened.restarted or
            reopened.books[CHAMPION].state.settled!=100 or
            reopened.books[CHALLENGER].state.settled!=100):
            raise RuntimeError("G10_RESTART_REPLAY_LOST_SETTLEMENT")
        disk=sum(x.stat().st_size for x in paths)
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out={"schema":"NBOT_V5_1_G10_DUAL_BOOK_SYNTHETIC_BENCH_V1",
         "grade":"SYNTHETIC_OFFLINE_TEST_ONLY",
         "cohort_rows_synthetic":2000,
         "cohort_btc_dependence_blocks":100,
         "independent_original_new_challenger_rows":0,
         "common_market_events":EVENTS,
         "market_regimes":result.regimes,
         "champion_lab_settlements":result.champion_settled_lab,
         "challenger_lab_settlements":result.challenger_settled_lab,
         "champion_lab_abstentions":result.champion_abstained,
         "challenger_lab_abstentions":result.challenger_abstained,
         "champion_lab_net_cash_return":result.champion_net_cash_return,
         "challenger_lab_net_cash_return":result.challenger_net_cash_return,
         "replay_status":"ALL_THREE_SEALED_JOURNALS_VERIFIED_RESTART_LOCKED",
         "lab_diagnostic":result.laboratory_diagnostic,
         "routing_action":result.action,
         "paper_authority":"NONE","real_order_authority":"NONE",
         "genuine_paper_settlements":0,
         "p99_shared_event_ms":round(p99(lat),3),
         "journal_total_bytes":disk,
         "max_rss_kib":rss,
         "cpu_seconds":round(time.process_time()-cpu,3),
         "wall_seconds":round(time.perf_counter()-beginning,3),
         "limits":{"p99_ms":P99_BUDGET_MS,"rss_kib":RSS_BUDGET_KIB,
                   "total_disk_bytes":DISK_BUDGET_BYTES},
         "nbot_services_started":False}
    out["passed"]=(out["p99_shared_event_ms"]<P99_BUDGET_MS and
                   rss<RSS_BUDGET_KIB and disk<DISK_BUDGET_BYTES)
    return out

if __name__=="__main__":
    x=run()
    print(json.dumps(x,sort_keys=True),flush=True)
    sys.exit(0 if x["passed"] else 2)
