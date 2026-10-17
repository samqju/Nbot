#!/usr/bin/env python3
"""Print recent official Freqtrade ZIPs and their declared strategy (read-only)."""
from pathlib import Path
from zipfile import ZipFile
import json
import sys

folder=Path(sys.argv[1])
for path in sorted(folder.glob("backtest-result-*.zip"),reverse=True)[:30]:
    try:
        with ZipFile(path) as z:
            members=[m for m in z.namelist() if m.endswith(".json")
                     and not m.endswith("_config.json")
                     and not m.endswith(".meta.json")]
            if len(members)!=1: continue
            stats=json.loads(z.read(members[0])).get("strategy",{})
            for name, row in stats.items():
                print(path.name,name,len(row.get("trades",[])),
                      round(float(row.get("profit_total_abs",0)),3))
    except (ValueError,KeyError,TypeError):
        pass
