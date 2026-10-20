#!/usr/bin/env python3
"""Read-only public Binance 1m REST vs stored verified candle discrepancy inspector."""
from pathlib import Path
from research.v7_live_1m_virtual_15day import connect,rest_klines,S,now_ms,meta_get
r=Path("/opt/nbot-v7-20261020/runs/live-1m-15days-20261020-v1")
c=connect(r)
print("last_processed",meta_get(c,"last_processed_open_ms"),"now",now_ms())
for s in S:
    b=rest_klines(s,limit=15)
    for x in b:
        q=c.execute("SELECT o,h,l,c,v FROM bars WHERE symbol=? AND t=?",(s,x.t)).fetchone()
        if q is not None:
            diffs={k:[q[k],getattr(x,k)] for k in ("o","h","l","c","v")
                   if abs(q[k]-getattr(x,k))>max(1e-6,abs(getattr(x,k))*1e-10)}
            if diffs:
                print("CONFLICT",s,x.t,"closed_ago_seconds",round((now_ms()-x.t-60000)/1000,1),
                      "diffs",diffs)
print("INSPECT_COMPLETE")
