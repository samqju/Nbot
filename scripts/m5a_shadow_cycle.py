#!/usr/bin/env python3
"""One-shot M5A 8h PUBLIC-ONLY shadow review; no active universe edits/orders.

If a review runs late, the collector stores a diagnostic but will NEVER backdate
the observation to the prior 8h boundary. NO readiness manifest = HOLD.
Intentional fail-closed default protects untrained new pairs. This is *not*
a FreqAI dynamic-pairlist adapter or trade activation service.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from datetime import datetime,timezone
import json
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from m5a_snapshot_binance import capture
from m5a_universe_selector import (
    incumbent_symbols,select,sha_obj,require
)

def write_new(path:Path,content:dict):
    # atomic exclusive creation; never overwrite audit snapshots
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:
        json.dump(content,f,indent=2,sort_keys=True)
        f.write("\n")
        f.flush();os.fsync(f.fileno())

def run_cycle(config:dict,observation:dict, readiness:dict|None=None,
              pinned:set[str]|None=None,known_since_ms:dict[str,int]|None=None)->dict:
    old=incumbent_symbols(config)
    data={
        "schema":"m5a-shadow-cycle-v1",
        "snapshot_sha256":sha_obj(observation),
        "captured_at_ms":observation["captured_at_ms"],
        "review_aligned":observation.get("review_boundary_aligned") is True,
        "initial_25":old,
        "readiness_attestation_supplied":bool(readiness),
        "actual_freqai_watchlist_changed":False,
        "orders_submitted":False,
        "live_paper_enabled":False}
    if not observation.get("review_boundary_aligned"):
        data.update(status="DIAGNOSTIC_ONLY_OUTSIDE_REVIEW_WINDOW",
                    reason="A current quote cannot retroactively represent 00/08/16 UTC")
        return data
    # If operator supplies no actual model/history receipt, this MUST HOLD
    # and never propose activating an unknown pair.
    result=select(observation,old,readiness or {},pinned=pinned,
                  previous_since_ms=known_since_ms or {})
    data.update(status=result["status"],selector=result)
    return data

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--readiness",type=Path,
                   help="Optional INDEPENDENT verified model/history evidence, not fabricated readiness")
    p.add_argument("--pinned",action="append",default=[])
    p.add_argument("--known-since",type=Path,
                   help="Existing 25 symbol-to-millisecond-since map, as-of historical evidence")
    args=p.parse_args()
    config=json.loads(args.config.read_text())
    require(config.get("dry_run") is True
            and config.get("exchange",{}).get("name")=="binance"
            and config.get("trading_mode")=="futures",
            "RESEARCH_CONFIG_MUST_REMAIN_DRY_RUN_BINANCE_FUTURES")
    snapshot=capture()
    stamp=datetime.fromtimestamp(snapshot["captured_at_ms"]/1000,timezone.utc)
    key=stamp.strftime("%Y%m%dT%H%M%S_%fZ")
    root=args.output_dir/key
    require(not root.exists(),"REFUSE_OVERWRITE_SHADOW_CYCLE")
    ready=json.loads(args.readiness.read_text()) if args.readiness else None
    since=json.loads(args.known_since.read_text()) if args.known_since else None
    report=run_cycle(config,snapshot,ready,set(args.pinned),since)
    write_new(root/"public-snapshot.json",snapshot)
    write_new(root/"universe-shadow-decision.json",report)
    print(json.dumps({"path":str(root),"status":report["status"],
                      "public_market_contracts":len(snapshot["contracts"]),
                      "proposed_replacements":report.get("selector",{}).get("turnover",0),
                      "current_watchlist_unchanged":True,
                      "paper_live_off":True},indent=2))
if __name__=="__main__":
    main()
