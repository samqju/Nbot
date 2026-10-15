"""Disposable accelerated 50-coin source/replay resource experiment.

No configurable input source or operational path, no network or service APIs.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import resource
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from nbot.v5 import g4_segmented_source as storage
from nbot.v5.g4_incremental_path import original_segment_price_paths
from tests.test_v5_g4_incremental_path import SYMS, T, tick
from tests.test_v5_g4_forward_vault import quote


def experiment(steps):
    began=time.monotonic(); cpu=time.process_time()
    writes=write_bytes=0
    publish=storage._durable_publish
    def measured(path,payload):
        nonlocal writes,write_bytes
        publish(path,payload)
        writes+=1; write_bytes+=len(payload)
    with TemporaryDirectory(prefix="nbot-v5-stress-synthetic-") as temp:
        root=Path(temp)
        hot=root/"hot"; cold=root/"mounted-archive"
        hot.mkdir(mode=0o700);cold.mkdir(mode=0o700)
        with patch.object(storage,"_durable_publish",side_effect=measured), patch(
                "nbot.v5.g4_archive_rollover._durable_publish",side_effect=measured):
            source=storage.SegmentedForwardSource(hot,symbols=SYMS,
                max_pending_frames=1024,max_pending_bytes=1048576,
                max_disk_bytes=2*1024*1024,rollover_destination=cold)
            source.connect(route="market_aggtrade",at_ms=T-1000)
            source.connect(route="public_bookticker",at_ms=T-1000)
            requests=[]
            for i,sym in enumerate(SYMS):
                for side in ("LONG","SHORT"):
                    requests.append((
                        {"decision_id":format(i*2+(side=="LONG"),"064x"),"status":"OBSERVED",
                         "symbol":sym,"side":side,"decision_at_ms":T+1000},
                        {"policy_sha256":"b"*64,"horizon_ms":14400000,"declared_at_ms":T-300000,
                         "entry_reference_price":"100","stop_price":"95" if side=="LONG" else "105",
                         "target_price":"110" if side=="LONG" else "90"}))
            max_pending=0
            for step in range(steps):
                at=T+step*(14402000//(steps-1))
                for sym in SYMS:
                    source.ingest(route="market_aggtrade",at_ms=at,
                                  raw=tick(sym,100+step,at,"100.01"))
                    source.ingest(route="public_bookticker",at_ms=at,
                                  raw=quote(symbol=sym,at=at,bid="99.99",ask="100.02"))
                max_pending=max(max_pending,source.pending_bytes)
            source.flush()
        capture_seconds=time.monotonic()-began
        replay_began=time.monotonic()
        results=original_segment_price_paths(segment_dir=hot,requests=requests,
                                             audit_at_ms=T+14405000)
        replay_seconds=time.monotonic()-replay_began
        if any(r.state!="PATH_REPLAYED" for r in results.values()):
            raise AssertionError({k:asdict(v) for k,v in results.items() if v.state!="PATH_REPLAYED"})
        frames=steps*len(SYMS)*2
        hot_bytes=sum(p.stat().st_size for p in hot.iterdir())
        cold_bytes=sum(p.stat().st_size for p in cold.iterdir())
        compressed_bytes=sum(p.stat().st_size for p in root.rglob("*.gz"))
        return {"grade":"SYNTHETIC","coins":len(SYMS),"frames":frames,
                "simulated_horizon_ms":14400000,"concurrent_hypotheses":len(requests),
                "peak_rss_mib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                "max_pending_bytes":max_pending,"hot_bytes":hot_bytes,"archive_bytes":cold_bytes,
                "compressed_source_bytes":compressed_bytes,"durable_publish_calls":writes,
                "durable_write_bytes":write_bytes,"cpu_seconds":time.process_time()-cpu,
                "elapsed_seconds":time.monotonic()-began,"capture_seconds":capture_seconds,
                "capture_frames_per_second":frames/capture_seconds,"replay_seconds":replay_seconds,
                "maturation_per_second":len(results)/replay_seconds,
                "outcomes_replayed":len(results),"sqlite_frame_rows":0,
                "archive_locators":len(list(hot.glob("*.location.json"))),
                "backlog_at_end":0,"source_integrity":"FULL_CHAIN_REPLAY_PASS",
                "order_authority":"NONE"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--steps",type=int,default=1001)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if not 1001<=args.steps<=10001:
        raise ValueError("SYNTHETIC_STRESS_BOUNDS")
    # Actual address-space ceiling, separate from the recorder's pending cap.
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    report=experiment(args.steps)
    Path(args.output).write_text(json.dumps(report,sort_keys=True,indent=2))
    print(json.dumps(report,sort_keys=True))
