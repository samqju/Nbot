"""G11 prospective 60-event TRUE CODE-SEAM G2->G5->G7->G8->G9/G10 lab.

Distinct from scripted G8 fixtures: every training row here originated from an
actual G5 virtual experiment, target first-touch, versioned G3/G4 references,
and explicitly artificial after-cost net R. Financial/source grade NEVER real.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
from test_v5_1_g2 import (
    manifest, market_fixture, history, bar, END_OPEN, END_DECISION)
from test_v5_1_g10_challenger import (
    base_policy,cohort,protocol,market,signed,KEY,K2,OTHER)
from nbot_v5_1.core import FiveMinuteEvent,INTERVAL_MS
from nbot_v5_1.universe import select_universe
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.research_intent import freeze_intent
from nbot_v5_1.research_book import VirtualResearchBook,SyntheticTick
from nbot_v5_1.research_journal import ResearchJournal
from nbot_v5_1.training_lab import LabProtocol
from nbot_v5_1.challenger_lab import (
    DualBookCompetition,CHAMPION,CHALLENGER)
from nbot_v5_1.g11_integration import OfflineIntegratedPipeline

STEPS=60
EVENTS=200


def p99(seq):
    x=sorted(seq)
    return x[int((len(x)-1)*.99)]


def run():
    wall=time.perf_counter()
    cpu=time.process_time()
    universe=manifest()
    observation=ObservationBook(universe)
    for symbol in universe.symbols:
        if not observation.bootstrap(symbol,history(symbol),
                                     as_of_ms=END_DECISION):
            raise RuntimeError("G11_G2_INITIAL_SOURCE_HOLD")
    with tempfile.TemporaryDirectory(prefix="nbot-g11-causal-") as tmp:
        root=Path(tmp)
        research=VirtualResearchBook(ResearchJournal(root/"research.jsonl"))
        pipe=OfflineIntegratedPipeline(observation,research)
        prev_universe_reselect=0
        latency=[]
        grade_counts=[]
        for n in range(STEPS):
            opening=END_OPEN+n*INTERVAL_MS
            decision=opening+INTERVAL_MS
            if n and n%16==0:
                # Source metadata itself must be re-frozen prospectively;
                # G3's 90-minute initial-universe lifetime is never ignored.
                e,t,b,h,health=market_fixture()
                universe=select_universe(
                    e,t,b,h,health,source_received_at_ms=decision-1500,
                    selected_at_ms=decision-1000)
                observation=ObservationBook(universe)
                for symbol in universe.symbols:
                    bars=[bar(symbol,opening-(95-i)*INTERVAL_MS,
                              received=decision) for i in range(96)]
                    if not observation.bootstrap(symbol,bars,as_of_ms=decision):
                        raise RuntimeError("G11_BROAD_UNIVERSE_REFRESH_INVALID")
                pipe.observation=observation
                prev_universe_reselect+=1
            elif n:
                for symbol in universe.symbols:
                    if not observation.ingest(
                        bar(symbol,opening,received=decision),
                        decision_at_ms=decision):
                        raise RuntimeError("G11_BROAD_SOURCE_GAP")
            event=FiveMinuteEvent(opening,decision)
            def freeze(deep,batch):
                # G11 passed actual frozen G3 and G4 objects; never
                # duplicate detection or invent an entry in another cohort.
                if not any(x.symbol=="BTCUSDT" and x.side=="LONG"
                           and x.status=="OBSERVED" for x in batch.rows):
                    raise RuntimeError("G11_SOURCE_NOT_ELIGIBLE")
                return (freeze_intent(
                    symbol="BTCUSDT",side="LONG",
                    event_open_ms=opening,declared_at_ms=decision,
                    activates_at_ms=decision+1,
                    horizon_ms=INTERVAL_MS,entry_reference="100",
                    stop="95",target="105",
                    cohort_sha=deep.manifest_sha,
                    observation_sha=batch.batch_id,source_epoch=1,
                    source_grade="SYNTHETIC_OFFLINE_TEST_ONLY"),)
            start=time.perf_counter()
            proof=pipe.on_five_minute(event,plan_factory=freeze)
            latency.append((time.perf_counter()-start)*1000)
            if (proof.universe_count!=100 or proof.direction_count!=200 or
                proof.deep_count!=20 or proof.admitted!=1 or
                proof.capacity_after!=1 or proof.financial_authority!="NONE"):
                raise RuntimeError("G11_60_EVENT_CHAIN_CAPACITY_OR_CLOCK")
            terminal=pipe.on_synthetic_tick(
                SyntheticTick("BTCUSDT",decision+120000,"105",1,
                              n+1,END_DECISION))
            if len(terminal)!=1 or terminal[0].reason!="TARGET":
                raise RuntimeError("G11_SYNTHETIC_FIRST_TOUCH_MISSING")
            row=pipe.record_synthetic_outcome(
                terminal[0],modeled_net_r="1.1")
            grade_counts.append(row.source_grade)
        protocol_train=LabProtocol(
            declared_at_ms=END_OPEN-INTERVAL_MS,
            train_cutoff_ms=END_DECISION+29*INTERVAL_MS+180000,
            holdout_start_ms=END_DECISION+33*INTERVAL_MS,
            holdout_end_ms=END_DECISION+61*INTERVAL_MS,
            embargo_ms=INTERVAL_MS,min_train_blocks=8,
            min_test_blocks=5,min_context_blocks=5,
            cost_buffer_r="0.10",random_search_attempts=1)
        proof=pipe.review_science(
            cutoff_ms=END_DECISION+(STEPS+3)*INTERVAL_MS,
            protocol=protocol_train)
        if (proof.synthetic_rows!=STEPS or proof.genuine_original_rows!=0
                or not proof.lab_model_sha or proof.release_action!="HOLD"):
            raise RuntimeError("G11_REAL_G5_TO_G8_SEAM_NOT_COMPLETE")
        p=base_policy()
        co=cohort()
        pr=protocol(p,co,champion_sha256=proof.lab_model_sha)
        paths=[root/"champion.jsonl",root/"challenger.jsonl",
               root/"shared.jsonl"]
        pipe.competition=DualBookCompetition(
            champion_journal=ResearchJournal(paths[0]),
            challenger_journal=ResearchJournal(paths[1]),
            review_journal=ResearchJournal(paths[2]),policy=p,
            cohort=co,protocol=pr,champion_key=KEY,challenger_key=K2)
        dual_lat=[]
        for n in range(EVENTS):
            e=market(n)
            if n%2==0:
                # A frozen synthetic G8 model SHA, not an arbitrary
                # unrelated fixture model, is routed into G9/G10 LAB book.
                e=replace(e,champion=signed(CHAMPION,n,e.at_ms,
                                            p=p,model=proof.lab_model_sha))
            start=time.perf_counter()
            audit=pipe.on_lab_paper_event(e)
            dual_lat.append((time.perf_counter()-start)*1000)
            if audit.authority!="NONE":
                raise RuntimeError("G11_G8_TO_G10_PAPER_RELEASE_FORGERY")
        review=pipe.review_competition()
        if (review.action!="HOLD" or review.common_events!=EVENTS or
                review.champion_settled_lab!=100 or
                review.challenger_settled_lab!=100 or
                review.active_champion_sha256!=proof.lab_model_sha or
                review.genuine_paper_settlements or
                review.independent_original_outcomes):
            raise RuntimeError("G11_G8_G10_REAL_MODEL_SHA_LINK_INVALID")
        restarted=VirtualResearchBook(ResearchJournal(root/"research.jsonl"))
        if restarted.occupied or restarted.status()["qualified_after_cost"]:
            raise RuntimeError("G11_RESEARCH_RESTART_FALSE_ORIGINAL")
        journal_bytes=sum(x.stat().st_size for x in paths+[root/"research.jsonl"])
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result={
        "schema":"NBOT_V5_1_G11_G5_TO_G10_CAUSAL_LAB_V1",
        "synthetic_only":True,"market_observation_events":STEPS,
        "observed_symbols_each":100,"direction_rows_each":200,
        "deep_symbols_each":20,"rolling_virtual_intents_settled":STEPS,
        "virtual_qualified_original_after_cost":0,
        "new_source_universe_reselections":prev_universe_reselect,
        "g5_to_g7_origin_verified_rows":proof.synthetic_rows,
        "source_grade_count_synthetic":sum(
            x=="SYNTHETIC_OFFLINE_TEST_ONLY" for x in grade_counts),
        "lab_model_sha256":proof.lab_model_sha,
        "lab_frozen_champion_routed_by_sha":True,
        "paper_common_events":review.common_events,
        "champion_lab_settlements":review.champion_settled_lab,
        "challenger_lab_settlements":review.challenger_settled_lab,
        "genuine_paper_settlements":review.genuine_paper_settlements,
        "promoter_actual_decision":review.action,
        "p99_100_to_40_boundary_ms":round(p99(latency),3),
        "p99_guardian_two_books_ms":round(p99(dual_lat),3),
        "all_journals_bytes":journal_bytes,
        "rss_kib":rss,"cpu_seconds":round(time.process_time()-cpu,3),
        "wall_seconds":round(time.perf_counter()-wall,3),
        "nbot_services_started":False,"exchange_order_count":0,
        "real_or_paper_model_release_authority":"NONE",
        "genuine_market_feed_or_72h_endurance_proven":False,
        "budgets":{"boundary_p99_ms":1500,"guardian_p99_ms":1500,
                   "rss_kib":256000,"disk_bytes":32*1024*1024}
    }
    result["passed"]=(result["p99_100_to_40_boundary_ms"]<1500 and
          result["p99_guardian_two_books_ms"]<1500 and
          rss<256000 and journal_bytes<32*1024*1024)
    return result


if __name__=="__main__":
    x=run()
    print(json.dumps(x,sort_keys=True),flush=True)
    sys.exit(0 if x["passed"] else 2)
