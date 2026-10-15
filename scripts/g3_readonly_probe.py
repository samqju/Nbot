"""One-shot, explicitly authorized public G3 no-order source/denominator probe.

Without --public-network, absolutely no network. Uses G2's strict public
100-market REST source probe, full G2 input/known-at checks, temporary byte-
exact source archive, and G3 read-only 200-direction capacity-zero masks.

There is NO G5 verified virtual vacancy, so live G3 deliberately does NOT
evaluate expensive detector hypotheses under synthetic slot authority. The
separate 100 x 200 x 24 offline stress and V4 golden tests exercise them.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))

from g2_readonly_probe import probe
from nbot_v5_1.exploration import explore_event
from nbot_v5_1.exploration_store import ExplorationStore
from nbot_v5_1.source_archive import PublicSourceArchive


def run(*, public_network: bool) -> dict:
    if type(public_network) is not bool or not public_network:
        raise ValueError("G3_PUBLIC_NETWORK_EXPLICIT_OPT_IN_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="nbot-g3-public-audit-") as root:
        d=Path(root)
        source=PublicSourceArchive(d/"source",budget_bytes=64*1024*1024)
        g3store=ExplorationStore(d/"exploration",budget_bytes=64*1024*1024)
        # New code never silently makes filesystem directories; this explicit
        # test-only setup creates private paths before any file writes.
        for p in (source.root,g3store.directory):
            p.mkdir(mode=0o700)
        def inspect(book,event):
            batch=explore_event(book,event,capacity_slots=0)
            if len(batch.rows)!=2*len(book.manifest.symbols):
                raise ValueError("G3_PUBLIC_PAIR_DENOMINATOR_MISMATCH")
            if batch.evaluated_pairs or batch.capacity_skipped_pairs+batch.source_skipped_pairs!=len(batch.rows):
                raise ValueError("G3_PUBLIC_UNAUTHORIZED_EVALUATION")
            name=g3store.append(batch)
            recovered=g3store.replay()
            if len(recovered)!=1 or recovered[0]!=batch.as_record():
                raise ValueError("G3_PUBLIC_RECEIPT_REPLAY_MISMATCH")
            return {
                "g3_schema":"NBOT_V5_1_EXPLORATION_V1",
                "g3_detector_ids":len(batch.rows[0].detector_states),
                "g3_capped_market_count":len(book.manifest.symbols),
                "g3_direction_denominator":len(batch.rows),
                "g3_source_skipped":batch.source_skipped_pairs,
                "g3_capacity_skipped":batch.capacity_skipped_pairs,
                "g3_evaluated":batch.evaluated_pairs,
                "g3_no_verified_research_vacancy":True,
                "g3_all_no_trade":all(r.authority.value=="NONE"
                      and r.disposition.value=="NO_TRADE" for r in batch.rows),
                "g3_receipt_name":name,
                "g3_receipt_sha":batch.batch_id,
                "g3_receipt_disk_bytes":sum(x.stat().st_size
                                           for x in g3store.directory.iterdir()),
            }
        result=probe(enabled=True,max_history_requests=130,
                     archive=source,on_event=inspect)
        if result["selected_symbols"]!=100 or result["event_hold_count"]!=0:
            raise ValueError("G3_PUBLIC_100_COHORT_HOLD")
        g3=result["g3_explicit_diagnostic"]
        if (g3["g3_direction_denominator"]!=200 or
                g3["g3_detector_ids"]!=24 or
                g3["g3_capacity_skipped"]!=200 or
                not g3["g3_all_no_trade"]):
            raise ValueError("G3_PUBLIC_MASK_INTEGRITY_FAIL")
        # After the summary is returned, BOTH source and exploration replay
        # directories are intentionally removed; no operational source
        # retention or unattended service is being claimed.
        return result


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--public-network",action="store_true",
        help="One-shot public GET-only 100-coin probe; no secrets/orders")
    args=ap.parse_args()
    try:
        result=run(public_network=args.public_network)
        print(json.dumps(result,sort_keys=True),flush=True)
        print("G3_PUBLIC_TEMP_SOURCE_AND_EXPLORATION_REPLAY_REMOVED",flush=True)
    except Exception as exc:
        print(json.dumps({"status":"G3_PUBLIC_HOLD","reason":type(exc).__name__+":"+str(exc),
                          "no_orders":True}),flush=True)
        sys.exit(2)
