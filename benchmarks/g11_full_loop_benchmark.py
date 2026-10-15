"""G11 offline whole-loop measured two-host workload. NO order/network services.

G1-G10 actual contract seams; source frames, fees, quotes, net R and models
are synthetic fixtures. Archive copied within a test host only: OFF-HOST
custody of authentic source explicitly NOT proven.
"""
from __future__ import annotations
import json
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_v5_1_g2 import manifest, history, bar, END_OPEN, END_DECISION
from test_v5_1_g4_source import frame, NOW
from test_v5_1_g8_training import dataset, policy as training_policy
from test_v5_1_g10_challenger import (
    cohort, protocol, market, KEY, K2)
from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.deep_selection import choose_deep
from nbot_v5_1.deep_segments import DeepSegmentRecorder
from nbot_v5_1.archive_custody import seal_archive, verify_archive
from nbot_v5_1.research_intent import freeze_intent
from nbot_v5_1.research_book import VirtualResearchBook, SyntheticTick
from nbot_v5_1.research_journal import ResearchJournal
from nbot_v5_1.challenger_lab import (
    DualBookCompetition, CHAMPION, CHALLENGER)
from nbot_v5_1.paper_contract import PaperPolicy
from nbot_v5_1.g11_integration import OfflineIntegratedPipeline

P99_LIMIT_MS = 1500
RSS_LIMIT_KIB = 256000
MAX_TEST_STORAGE = 32 * 1024 * 1024
FRAMES_PER_ROUND = 60
ROUNDS = 6
COMMON_LAB_EVENTS = 200


def p99(items):
    x = sorted(items)
    return x[int((len(x)-1)*.99)]


def bench():
    t0 = time.perf_counter()
    cpu0 = time.process_time()
    timings = {}
    with tempfile.TemporaryDirectory(prefix="nbot-g11-benchmark-") as folder:
        root = Path(folder)
        virtual = ResearchJournal(root / "virtual.jsonl")
        book = VirtualResearchBook(virtual)
        universe = manifest()
        observation = ObservationBook(universe)
        t1 = time.perf_counter()
        for symbol in universe.symbols:
            if not observation.bootstrap(
                    symbol, history(symbol), as_of_ms=END_DECISION):
                raise RuntimeError("G11_BROAD_CANDLE_BOOTSTRAP_INCOMPLETE")
        timings["g2_bootstrap_ms"] = (time.perf_counter() - t1) * 1000
        event = FiveMinuteEvent(END_OPEN, END_DECISION)
        trial = explore_event(observation, event, capacity_slots=40)
        deep = choose_deep(universe, trial)
        if len(deep.symbols) != 20 or len(trial.rows) != 200:
            raise RuntimeError("G11_NO_100_TO_20_SELECTION")
        plans = tuple(freeze_intent(
            symbol=s, side=side, event_open_ms=END_OPEN,
            declared_at_ms=END_DECISION, activates_at_ms=END_DECISION+1,
            horizon_ms=INTERVAL_MS, entry_reference="100",
            stop="95" if side == "LONG" else "105",
            target="105" if side == "LONG" else "95",
            cohort_sha=deep.manifest_sha, observation_sha="a"*64,
            source_epoch=1, source_grade="SYNTHETIC_OFFLINE_TEST_ONLY")
            for s in deep.symbols for side in ("LONG", "SHORT"))
        if len(plans) != 40:
            raise RuntimeError("G11_WRONG_VIRTUAL_ADMISSION_COHORT")

        policy = PaperPolicy()
        extra = cohort()
        contract = protocol(policy, extra)
        paper_paths = [root / "champion.jsonl",
                       root / "challenger.jsonl", root / "shared.jsonl"]
        comparison = DualBookCompetition(
            champion_journal=ResearchJournal(paper_paths[0]),
            challenger_journal=ResearchJournal(paper_paths[1]),
            review_journal=ResearchJournal(paper_paths[2]),
            policy=policy, cohort=extra, protocol=contract,
            champion_key=KEY, challenger_key=K2)
        pipe = OfflineIntegratedPipeline(observation, book, comparison)
        before = time.perf_counter()
        witness = pipe.on_five_minute(event, supplier=lambda: plans)
        timings["g2_g5_boundary_ms"] = (time.perf_counter()-before) * 1000
        if ((witness.universe_count,witness.direction_count,
             witness.deep_count,witness.admitted,
             witness.capacity_after) != (100,200,20,40,40)):
            raise RuntimeError("G11_ACTUAL_BOUNDARY_SEAMS_FAILED")

        # The G4 actual segment/cryptographic replay code receives original-
        # SHAPED synthetic fixtures for exactly the SAME 20 deep markets.
        raw = root / "raw"
        archive = root / "copied_archive"
        raw.mkdir(mode=0o700)
        archive.mkdir(mode=0o700)
        recorder = DeepSegmentRecorder(raw, symbols=deep.symbols)
        seal_times = []
        for cycle in range(ROUNDS):
            start = time.perf_counter()
            at = NOW + cycle * 2000
            for symbol in deep.symbols:
                for kind in ("TRADE","QUOTE","MARK"):
                    item = recorder.append(
                        kind=kind,
                        raw=frame(kind, symbol=symbol, id=cycle+8,
                                  received=at),
                        received_at_ms=at, epoch=1)
                    if item.state == "HOLD":
                        raise RuntimeError("G11_SYNTHETIC_SOURCE_FORMAT_HOLD")
            recorder.flush()
            seal_times.append((time.perf_counter()-start)*1000)
        sealed = seal_archive(source=raw, destination=archive,
                              symbols=deep.symbols)
        replay = verify_archive(root=archive, symbols=deep.symbols)
        if (replay["frames"] != ROUNDS*FRAMES_PER_ROUND
                or replay["segments"] != ROUNDS):
            raise RuntimeError("G11_SEALED_ARCHIVE_REPLAY_MISMATCH")

        # Forty virtual experiments, shared 20-symbol original-shaped ticks,
        # exits at true intra-candle event-time, not next candle-close.
        terminals = []
        first_touch_ms = []
        for i, symbol in enumerate(deep.symbols):
            at = END_DECISION + 120000
            t = time.perf_counter()
            exits = pipe.on_synthetic_tick(SyntheticTick(
                symbol, at, "105", 1, 1, END_DECISION))
            terminals.extend(exits)
            first_touch_ms.append((time.perf_counter()-t)*1000)
        if len(terminals) != 40 or book.occupied != 0:
            raise RuntimeError("G11_MAX_40_FIRST_TOUCH_FAILED")
        for terminal in terminals:
            row = pipe.record_synthetic_outcome(terminal)
            if row.net_r is not None or row.economic_state != "COST_PENDING":
                raise RuntimeError("G11_UNVERIFIED_ECONOMIC_OUTCOME")
        science = pipe.review_science(cutoff_ms=END_DECISION+120000)
        if (science.pending_rows != 40
                or science.genuine_original_rows != 0):
            raise RuntimeError("G11_G7_FALSE_ECONOMIC_SCIENCE")

        # Authentic G8 training code with separately labeled synthetic
        # benchmark outcomes. Not the preceding COST_PENDING research results.
        d = dataset(60, net="1.1")
        pipe.learning_rows = list(d.rows)
        trained = pipe.review_science(
            cutoff_ms=d.cutoff_ms, protocol=training_policy())
        if (not trained.lab_model_sha or
                trained.genuine_original_rows != 0 or
                trained.release_action != "HOLD"):
            raise RuntimeError("G11_G8_FALSE_MODEL_RELEASE")

        # Continue actual G2/G3/G4/G5 seam at next candle close; no forced
        # openings. Existing lightweight 100-market subscriptions are not
        # restarted at this boundary.
        open2 = END_OPEN + INTERVAL_MS
        decision2 = END_DECISION + INTERVAL_MS
        for symbol in universe.symbols:
            observation.ingest(
                bar(symbol, open2, received=decision2),
                decision_at_ms=decision2)
        review2 = pipe.on_five_minute(
            FiveMinuteEvent(open2,decision2), supplier=lambda: ())
        if review2.admitted or review2.universe_count != 100:
            raise RuntimeError("G11_SECOND_BOUNDARY_FORCED_ENTRIES")

        dual_latencies=[]
        for i in range(COMMON_LAB_EVENTS):
            start=time.perf_counter()
            result=pipe.on_lab_paper_event(market(i))
            dual_latencies.append((time.perf_counter()-start)*1000)
            if result.authority != "NONE":
                raise RuntimeError("G11_G10_LAB_UNAUTHORIZED")
        verdict=pipe.review_competition()
        if (verdict.common_events != 200
                or verdict.champion_settled_lab != 100
                or verdict.challenger_settled_lab != 100
                or verdict.action != "HOLD"
                or verdict.genuine_paper_settlements != 0):
            raise RuntimeError("G11_SHARED_BOOK_ACCEPTANCE_FAILED")

        # Reopen independently; no AUTO resume, model switch or false science.
        restart=VirtualResearchBook(ResearchJournal(root/"virtual.jsonl"))
        revived=DualBookCompetition(
            champion_journal=ResearchJournal(paper_paths[0]),
            challenger_journal=ResearchJournal(paper_paths[1]),
            review_journal=ResearchJournal(paper_paths[2]),
            policy=policy, cohort=extra, protocol=contract,
            champion_key=KEY, challenger_key=K2)
        if (restart.occupied != 0 or
                not revived.restarted or
                revived.books[CHAMPION].state.settled != 100 or
                revived.books[CHALLENGER].state.settled != 100):
            raise RuntimeError("G11_RESTART_RECONCILIATION_FAILED")

        raw_bytes = sum(p.stat().st_size for p in raw.iterdir())
        archive_bytes = sum(p.stat().st_size for p in archive.iterdir())
        lab_journal_bytes = sum(p.stat().st_size for p in paper_paths)
        research_bytes = (root/"virtual.jsonl").stat().st_size
        total_bytes = raw_bytes+archive_bytes+lab_journal_bytes+research_bytes

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    source_one_round = raw_bytes / ROUNDS
    projected_three_day_bytes = int(source_one_round * 288 * 3)
    result = {
        "schema":"NBOT_V5_1_G11_WHOLE_LOOP_SYNTHETIC_BENCH_V1",
        "source_grade":"SYNTHETIC_OFFLINE_TEST_ONLY",
        "read_only_public_market_network_used":False,
        "nbot_services_started":False,
        "exchange_orders":0,
        "true_qualified_learning_outcomes":0,
        "true_paper_settlements":0,
        "routing_decision":verdict.action,
        "broad_symbols":witness.universe_count,
        "direction_records":witness.direction_count,
        "deep_symbols":witness.deep_count,
        "virtual_max_active":40,
        "virtual_terminals_cost_pending":len(terminals),
        "synthetic_g8_training_rows":trained.synthetic_rows,
        "dual_common_events":verdict.common_events,
        "champion_lab_settlements":verdict.champion_settled_lab,
        "challenger_lab_settlements":verdict.challenger_settled_lab,
        "sealed_synthetic_source_frames":replay["frames"],
        "sealed_source_segments":replay["segments"],
        "source_copy_kind":"SAME_HOST_SYNTHETIC_REPLAY_NOT_OFFHOST",
        "actual_offhost_original_proven":False,
        "p99_lightweight_shared_tick_ms":round(p99(first_touch_ms),3),
        "p99_20_market_source_seal_ms":round(p99(seal_times),3),
        "p99_dual_book_event_ms":round(p99(dual_latencies),3),
        "g2_bootstrap_ms":round(timings["g2_bootstrap_ms"],3),
        "g2_g5_boundary_ms":round(timings["g2_g5_boundary_ms"],3),
        "raw_source_bytes":raw_bytes,
        "archive_source_bytes":archive_bytes,
        "three_paper_journals_bytes":lab_journal_bytes,
        "virtual_research_journal_bytes":research_bytes,
        "total_test_storage_bytes":total_bytes,
        "projected_72h_raw_source_bytes_at_synthetic_fixture_rate":projected_three_day_bytes,
        "projection_is_real_endurance_evidence":False,
        "rss_kib":rss,
        "cpu_seconds":round(time.process_time()-cpu0,3),
        "wall_seconds":round(time.perf_counter()-t0,3),
        "budgets":{
            "p99_ms":P99_LIMIT_MS,
            "rss_kib":RSS_LIMIT_KIB,
            "total_test_disk_bytes":MAX_TEST_STORAGE
        }
    }
    result["passed"] = (
        max(result["p99_lightweight_shared_tick_ms"],
            result["p99_20_market_source_seal_ms"],
            result["p99_dual_book_event_ms"]) < P99_LIMIT_MS
        and rss < RSS_LIMIT_KIB
        and total_bytes < MAX_TEST_STORAGE
        and verdict.action == "HOLD")
    return result


if __name__ == "__main__":
    output = bench()
    print(json.dumps(output, sort_keys=True), flush=True)
    sys.exit(0 if output["passed"] else 2)
