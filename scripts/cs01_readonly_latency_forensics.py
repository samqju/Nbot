#!/usr/bin/env python3
"""Read-only CS01 saved-source latency forensics. ZERO market connectivity.

Read archived owner-owned public WSS segment-*.gz files (not live daemon),
calculate event E -> on-receipt latency distribution per kind/symbol,
compare chronological early vs late slices and compact skipped-stale log.
Never print raw ticks, prices, keys, trade IDs or user account data.
This measures lag at pipeline receipt, not necessarily actual socket ingress.
"""
from __future__ import annotations
import argparse
import base64
from collections import defaultdict
import gzip
import json
from pathlib import Path
import re
import statistics
import sys

def percentile(xs,p):
    if not xs:return None
    seq=sorted(xs);return seq[min(len(seq)-1,round((len(seq)-1)*p))]

def bucket(rows):
    if not rows:return None
    a=[v for _t,v in sorted(rows)]
    m=max(1,len(a)//5)
    return {
        "samples":len(a),"min_ms":min(a),"median_ms":percentile(a,.5),
        "p90_ms":percentile(a,.90),"p99_ms":percentile(a,.99),
        "max_ms":max(a),"first_fifth_median_ms":percentile(a[:m],.5),
        "last_fifth_median_ms":percentile(a[-m:],.5),
        "received_over_1000ms":sum(v>1000 for v in a),
        "received_over_3000ms":sum(v>3000 for v in a),
        "received_over_5000ms":sum(v>5000 for v in a),
        "negative_clock_delta":sum(v<0 for v in a)
    }

def inspect(root:Path):
    seg=root/"evidence"
    if not seg.is_dir() or seg.is_symlink():
        raise ValueError("READ_ONLY_EVIDENCE_DIRECTORY_REQUIRED")
    files=sorted(seg.glob("segment-*.gz"))
    if not files or len(files)>1000:
        raise ValueError("MISSING_OR_EXCESSIVE_SEGMENTS")
    lag=defaultdict(list)
    per_symbol=defaultdict(list)
    counts=defaultdict(int)
    earliest=latest=None
    for file in files:
        if file.is_symlink() or file.stat().st_size>2*1024*1024:
            raise ValueError("UNSAFE_SEGMENT")
        with gzip.open(file,"rb") as f:
            raw=f.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:
            raise ValueError("LARGE_SEGMENT_EXPANSION_DENIED")
        array=json.loads(raw)
        if type(array) is not list:raise ValueError("NON_ARRAY_SEGMENT")
        for item in array:
            if type(item) is not dict:raise ValueError("NON_DICT_FRAME")
            received=item.get("received_at_ms")
            wire=base64.b64decode(item["raw_b64"],validate=True)
            if type(received) is not int or len(wire)>65536:
                raise ValueError("RAW_RECEIPT_INVALID")
            payload=json.loads(wire)
            symbol=payload["data"]["s"]
            kind=item["kind"]
            event=payload["data"].get("E")
            if type(event) is not int:continue
            if kind not in ("QUOTE","TRADE","MARK") or not re.fullmatch("[A-Z0-9]{3,24}",symbol):
                raise ValueError("SOURCE_KIND_OR_SYMBOL_INVALID")
            age=received-event
            lag[(kind,"ALL")].append((received,age))
            lag[(kind,"BTCUSDT" if symbol=="BTCUSDT" else "OTHER")].append((received,age))
            per_symbol[(kind,symbol)].append((received,age))
            counts[kind]+=1
            earliest=received if earliest is None else min(earliest,received)
            latest=received if latest is None else max(latest,received)
    anomaly=root/"research"/"source_anomalies.jsonl"
    reasons=defaultdict(int)
    if anomaly.exists():
        for line in anomaly.read_text().splitlines():
            if line:
                o=json.loads(line)
                reasons[(o.get("kind"),o.get("symbol"),o.get("reason"))]+=1
    worst=[]
    for key,values in per_symbol.items():
        summary=bucket(values)
        worst.append({"kind":key[0],"symbol":key[1],
                      "max_ms":summary["max_ms"],
                      "p99_ms":summary["p99_ms"],
                      "n":summary["samples"]})
    worst.sort(key=lambda x:x["p99_ms"],reverse=True)
    return {"root":str(root),"segments":len(files),
            "sample_window_ms":(latest-earliest) if latest and earliest else None,
            "count_by_feed":dict(counts),
            "lag_by_feed_and_btc_vs_others":{
                kind:{sub:bucket(lag[(kind,sub)]) for sub in ("ALL","BTCUSDT","OTHER")}
                for kind in ("QUOTE","TRADE","MARK")},
            "slowest_symbols_by_p99":worst[:12],
            "excluded_soft_stale_anomalies":[
                {"feed":k[0],"symbol":k[1],"reason":k[2],"n":v}
                for k,v in sorted(reasons.items())],
            "rejected_stale_raw_event_E_archived":False,
            "source_grade":"FORENSIC_PARTIAL_ORIGINAL_NO_TRADE_OR_OUTCOME",
            "order_authority":"NONE"}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("roots",nargs="+",type=Path)
    args=p.parse_args()
    try:
        for root in args.roots:
            print(json.dumps(inspect(root),sort_keys=True,separators=(",",":")),flush=True)
    except Exception as exc:
        print("FORENSIC_READ_ONLY_HOLD:"+type(exc).__name__+":"+str(exc)[:160],file=sys.stderr)
        raise SystemExit(2)
