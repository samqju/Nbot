#!/usr/bin/env python3
"""M2: quantify historical time in position for each one-slot strategy.

Official trade ZIP timestamps only. Counts total exposure in the exact seven
days, long/short breakdown, entry/exit collision and overlapping positions.
No trades, no model fitting, and no connected accounts.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from m2_funding_reconcile import archive_strategy, timestamp_ms

START = timestamp_ms("2026-10-01T00:00:00+00:00")
END = timestamp_ms("2026-10-08T00:00:00+00:00")


def exposure(trades: list[dict]) -> dict:
    intervals = []
    for t in trades:
        a,b=timestamp_ms(t["open_date"]),timestamp_ms(t["close_date"])
        if not START <= a < b <= END:
            raise ValueError("Trade outside the selected complete 7-day test")
        intervals.append((a,b,bool(t.get("is_short")),t["pair"]))
    intervals.sort()
    overlapping=0
    for i in range(1,len(intervals)):
        overlapping+=int(intervals[i][0] < intervals[i-1][1])
    held = sum(b-a for a,b,*_ in intervals)
    held_long = sum(b-a for a,b,short,_ in intervals if not short)
    held_short = held-held_long
    summary = {
        "trades":len(trades), "overlapping_global_positions":overlapping,
        "position_hours":round(held/3_600_000,3),
        "one_global_slot_utilization_pct":round(held/(END-START)*100,3),
        "long_position_hours":round(held_long/3_600_000,3),
        "short_position_hours":round(held_short/3_600_000,3),
        "flat_hours":round((END-START-held)/3_600_000,3),
        "max_individual_holding_hours":round(max((b-a for a,b,*_ in intervals),default=0)/3_600_000,3)
    }
    if overlapping:
        raise ValueError("More than one open trade overlapped")
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ai",required=True,type=Path)
    p.add_argument("--baseline",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    data={
        "AI_V6":exposure(archive_strategy(a.ai,"NbotV6")["trades"]),
        "NO_ML":exposure(archive_strategy(a.baseline,"NbotV6NoML")["trades"])
    }
    out={"window":"2026-10-01 to 2026-10-08 UTC", "duration_hours":168,
         "one_slot_historical_only":True,"results":data,
         "interpretation":"Actual time-in-position; NOT number of all eligible signals or capacity of 20-slot future paper research"}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(data,indent=2))


if __name__=="__main__":
    main()
