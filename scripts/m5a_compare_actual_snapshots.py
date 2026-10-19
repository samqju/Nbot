#!/usr/bin/env python3
"""M5A compare two ACTUAL public snapshots without hindsight P&L claims."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from m5a_universe_selector import evaluate,incumbent_symbols,sha_obj

def analyze(path:Path,incumbents:list[str])->dict:
    d=json.loads(path.read_text())
    now=d["captured_at_ms"]
    rows={r.symbol:r for r in (evaluate(x,now,set()) for x in d["contracts"])}
    eligible=sorted((r for r in rows.values() if r.eligible),key=lambda r:(-r.score,r.symbol))
    qualified={r.symbol for r in eligible}
    chosen=[r.symbol for r in eligible[:25]]
    return {"utc":datetime.fromtimestamp(now/1000,timezone.utc).isoformat(),
            "snapshot_sha256":sha_obj(d),
            "market_records":len(rows),
            "eligible":len(qualified),
            "existing_eligible":sorted(set(incumbents)&qualified),
            "existing_rejected":{s:list(rows[s].reasons) if s in rows else ["MISSING_PUBLIC_CONTRACT"]
                                 for s in incumbents if s not in qualified},
            "top25":chosen,
            "top25_new_vs_static":sorted(set(chosen)-set(incumbents)),
            "score_by_symbol":{r.symbol:r.score for r in eligible}}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--earlier",type=Path,required=True)
    p.add_argument("--later",type=Path,required=True)
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    old=incumbent_symbols(json.loads(a.config.read_text()))
    x=analyze(a.earlier,old)
    y=analyze(a.later,old)
    diff={
        "schema":"m5a-live-snapshot-drift-diagnostic-v1",
        "first_utc":x["utc"],"second_utc":y["utc"],
        "hours_apart":round((datetime.fromisoformat(y["utc"])-datetime.fromisoformat(x["utc"])).total_seconds()/3600,3),
        "first_contracts":x["market_records"],"second_contracts":y["market_records"],
        "first_public_quality_eligible":x["eligible"],
        "second_public_quality_eligible":y["eligible"],
        "first_existing25_passing":len(x["existing_eligible"]),
        "second_existing25_passing":len(y["existing_eligible"]),
        "existing_gained_eligibility":sorted(set(y["existing_eligible"])-set(x["existing_eligible"])),
        "existing_lost_eligibility":sorted(set(x["existing_eligible"])-set(y["existing_eligible"])),
        "first_top25":x["top25"],"second_top25":y["top25"],
        "top25_common_count":len(set(x["top25"])&set(y["top25"])),
        "top25_added_in_later":sorted(set(y["top25"])-set(x["top25"])),
        "top25_removed_in_later":sorted(set(x["top25"])-set(y["top25"])),
        "first_top25_new_vs_original":x["top25_new_vs_static"],
        "second_top25_new_vs_original":y["top25_new_vs_static"],
        "first_original_rejection_reasons":x["existing_rejected"],
        "second_original_rejection_reasons":y["existing_rejected"],
        "public_quality_not_model_ready":True,
        "no_valid_asof_eight_hour_review_observation":True,
        "not_historical_25coin_portfolio_pnl":True,
        "no_order_no_active_pair_update":True,
        "no_trading_alpha_claim":True
    }
    if a.out:
        if a.out.exists():raise SystemExit("REFUSE_OVERWRITE_SAVED_COMPARISON")
        a.out.write_text(json.dumps(diff,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:v for k,v in diff.items()
                      if not k.endswith("_rejection_reasons") and not k.endswith("_top25")},indent=2))
if __name__=="__main__":main()
