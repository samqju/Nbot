"""CS-00 host-local OFFLINE synthetic rehearsal; no public network or service.

Tests G2/G3/G4 100→200→20 against an injected closed-bar fixture, 20×3
raw-shaped synthetic segments, immutable local evidence, alert HOLD and
same-host seal/replay. It intentionally does NOT test real provider access.
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

from test_v5_1_g2 import manifest,history,END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.cs00_commissioning import (
    CommissioningPolicy,ArchivePlan,OfflineObservationRunner,
    write_immutable_offline_report)

ROUNDS=12
BUDGET_P99_FRAME_MS=1500
RSS_BUDGET_KIB=256000
LIMIT_TEST_BYTES=32*1024*1024


def p99(a):
    data=sorted(a)
    return data[int((len(data)-1)*.99)]


def run():
    wall=time.perf_counter()
    cpu=time.process_time()
    with tempfile.TemporaryDirectory(prefix="nbot-cs00-benchmark-") as d:
        folder=Path(d)
        raw=folder/"raw"
        copied=folder/"archive_local_only"
        raw.mkdir(mode=0o700)
        copied.mkdir(mode=0o700)
        universe=manifest()
        book=ObservationBook(universe)
        for symbol in universe.symbols:
            if not book.bootstrap(
                symbol,history(symbol),as_of_ms=END_DECISION):
                raise RuntimeError("CS00_SOURCE_BOOTSTRAP_INVALID")
        runner=OfflineObservationRunner(book,CommissioningPolicy())
        started=time.perf_counter()
        result=runner.on_five_minute(
            FiveMinuteEvent(END_OPEN,END_DECISION))
        boundary_ms=(time.perf_counter()-started)*1000
        if (result.broad,result.directions,result.deep,result.metadata_ready
             )!=(100,200,20,100):
            raise RuntimeError("CS00_BROAD_DEEP_CENSUS_BROKEN")
        runner.bind_synthetic_raw_recorder(raw)
        lat=[]
        for n in range(ROUNDS):
            begin=time.perf_counter()
            received=NOW+2000*n
            for symbol in runner.deep.symbols:
                for kind in ("TRADE","QUOTE","MARK"):
                    if not runner.accept_synthetic_raw(
                        kind=kind,
                        raw=frame(kind,symbol=symbol,
                                  id=8+n,received=received),
                        received_at_ms=received,epoch=1):
                        raise RuntimeError("CS00_SYNTHETIC_FRAME_HOLD")
            runner.flush_synthetic()
            lat.append((time.perf_counter()-begin)*1000)
        replay=runner.archive_locally_for_offline_test(copied)
        if replay["frames"]!=ROUNDS*20*3 or replay["segments"]!=ROUNDS:
            raise RuntimeError("CS00_SYNTHETIC_ARCHIVE_REPLAY_FALSE")
        simulated_failure=runner.status(
            free_disk_bytes=0,source_queue_depth=5000)
        if (simulated_failure["decision"]!="HOLD" or
            "FREE_DISK_RESERVE_HOLD" not in simulated_failure["alerts"] or
            "SOURCE_BACKPRESSURE_HOLD" not in simulated_failure["alerts"]):
            raise RuntimeError("CS00_RESOURCE_HOLD_NOT_OBSERVED")
        safe=runner.status()
        immutable=write_immutable_offline_report(
            folder,"offline-evidence.json",safe)
        profile=ArchivePlan().planning_status()
        if (profile["actual_offhost_archival_verified"]
                or safe["public_network"]
                or safe["actual_exchange_orders"]
                or safe["archive_offhost_verified"]
                or safe["deletion_allowed"]
                or immutable["payload_sha256"]==""):
            raise RuntimeError("CS00_FALSE_START_OR_ORIGINAL_CLAIM")
        evidence_bytes=sum(p.stat().st_size for p in
                           list(raw.iterdir())+list(copied.iterdir())
                           +[folder/"offline-evidence.json"])
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out={"schema":"NBOT_V5_1_CS00_OFFLINE_HOST_REHEARSAL_V1",
         "grade":"SYNTHETIC_OFFLINE_TEST_ONLY",
         "owner_archive_choice":"EXISTING_PROVIDER_PENDING_DETAILS",
         "retention_target_days":30,
         "archive_automatic_deletion_allowed":False,
         "archive_actual_offhost_verified":False,
         "source_public_network_used":False,
         "production_service_started":False,
         "real_virtual_paper_testnet_orders":0,
         "broad_observed":result.broad,"directions":result.directions,
         "deep_selected":result.deep,
         "closed_metadata_ready":result.metadata_ready,
         "genuine_original_frames_qualified":0,
         "synthetic_frames":replay["frames"],
         "synthetic_segments":replay["segments"],
         "source_copy":"SAME_HOST_OFFLINE_ONLY",
         "tamper_evidence_sha256":immutable["payload_sha256"],
         "simulated_resource_HOLD":"PASS",
         "five_minute_boundary_ms":round(boundary_ms,3),
         "p99_20market_source_fsync_batch_ms":round(p99(lat),3),
         "rss_kib":rss,
         "disk_bytes":evidence_bytes,
         "cpu_seconds":round(time.process_time()-cpu,3),
         "wall_seconds":round(time.perf_counter()-wall,3),
         "budget":{"p99_ms":BUDGET_P99_FRAME_MS,
                   "rss_kib":RSS_BUDGET_KIB,
                   "disk_bytes":LIMIT_TEST_BYTES}}
    out["passed"]=(out["five_minute_boundary_ms"]<BUDGET_P99_FRAME_MS
                   and out["p99_20market_source_fsync_batch_ms"]<
                        BUDGET_P99_FRAME_MS and rss<RSS_BUDGET_KIB
                   and evidence_bytes<LIMIT_TEST_BYTES)
    return out


if __name__=="__main__":
    x=run()
    print(json.dumps(x,sort_keys=True),flush=True)
    sys.exit(0 if x["passed"] else 2)
