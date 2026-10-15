"""CS-00 explicitly non-starting Observation entry point.

Usage:
  python3 -B scripts/cs00_observation_entry.py
  python3 -B scripts/cs00_observation_entry.py --offline-rehearsal

This deliberately has NO --start, --public-network, --serve, --paper,
--testnet or --real option. CS-01 needs a separate reviewed entry point.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nbot_v5_1.cs00_commissioning import ArchivePlan, CommissioningPolicy


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="NBOT V5.1 CS-00 OFFLINE-ONLY, NO live source or order client",
        allow_abbrev=False)
    parser.add_argument("--offline-rehearsal",action="store_true",
                        help="Run synthetic 100/20 harness in a temporary directory")
    ns=parser.parse_args(argv)
    policy=CommissioningPolicy()
    policy.validate()
    if ns.offline_rehearsal:
        sys.path.insert(0,str(ROOT/"benchmarks"))
        from cs00_offline_readiness_benchmark import run
        proof=run()
        print(json.dumps(proof,sort_keys=True),flush=True)
        return 0 if proof["passed"] else 2
    print(json.dumps({
        "schema":"NBOT_V5_1_CS00_ENTRY_LOCK_V1",
        "state":"STOPPED_OFFLINE_ONLY",
        "production_start_authorized":False,
        "public_network_allowed":False,
        "order_authority":"NONE",
        "archive":ArchivePlan().planning_status(),
        "policy_sha256":policy.digest(),
        "message":"CS-00 is build-and-verify only. CS-01 start requires new owner approval."
    },sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
