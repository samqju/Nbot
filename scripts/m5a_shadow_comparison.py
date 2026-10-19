#!/usr/bin/env python3
"""Read-only shadow quality comparison on a saved actual public market snapshot.

Does not call select() outside an 8h review boundary or certify models ready.
NEVER translates highest market quality into an actual trade or historical P&L.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from m5a_universe_selector import evaluate, incumbent_symbols

DEFAULT_ROOT=Path("/root/nbot-v6-m1-20261016/global-next-source")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True,type=Path)
    p.add_argument("--config",type=Path,default=DEFAULT_ROOT/"user_data/config.json")
    a=p.parse_args()
    d=json.loads(a.snapshot.read_text())
    cfg=json.loads(a.config.read_text())
    old=incumbent_symbols(cfg)
    stamp=d["captured_at_ms"]
    evaluations={r.symbol:r for r in
                 (evaluate(x,stamp,set()) for x in d["contracts"])}
    eligible=sorted((x for x in evaluations.values() if x.eligible),
                    key=lambda x:(-x.score,x.symbol))
    selected={x.symbol for x in eligible[:25]}
    safe_old=[x for x in old if x in evaluations and evaluations[x].eligible]
    missing=[x for x in old if x not in safe_old]
    def average(symbols):
        rows=[evaluations[x] for x in symbols if x in evaluations and evaluations[x].eligible]
        return round(sum(x.score for x in rows)/len(rows),6) if rows else None
    reasons=Counter(k for r in evaluations.values() for k in r.reasons)
    report={
        "schema":"m5a-current-live-shadow-comparison-v1",
        "capture_utc":datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat(),
        "asof_schedule_aligned":d.get("review_boundary_aligned",False),
        "market_contracts_screened":len(evaluations),
        "public_quality_eligible_count":len(eligible),
        "original_25_count":len(old),
        "original_25_public_quality_eligible_count":len(safe_old),
        "original_25_public_quality_ineligible":missing,
        "ineligible_incumbent_reasons":{x:list(evaluations[x].reasons)
            if x in evaluations else ["MISSING_IN_EXCHANGE"] for x in missing},
        "public_quality_top_25":[x.symbol for x in eligible[:25]],
        "quality_top25_not_in_original":sorted(selected-set(old)),
        "original_not_in_public_quality_top25":sorted(set(old)-selected),
        "average_quality_of_eligible_original":average(safe_old),
        "average_quality_top25":average(selected),
        "exclusion_reason_counts":dict(reasons),
        "readiness_model_certifications":0,
        "selector_activation_permitted":False,
        "market_quality_is_not_positive_expected_trade_return":True,
        "historical_listing_or_bidask_replay_is_not_proven":True,
        "no_orders_config_edits_or_training":True
    }
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=="__main__":
    main()
