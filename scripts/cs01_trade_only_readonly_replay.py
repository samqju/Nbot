#!/usr/bin/env python3
"""Read-only integrity replay for the owner-approved trade+mark CS01.
Does not connect to any API, alter checkpoints or initiate a live feed.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import sys
from nbot_v5_1.deep_segments import DeepSegmentRecorder,DeepSegmentHold


def inspect(root:Path)->dict:
    root=root.resolve()
    folder=root/"evidence"
    files=sorted(folder.glob("segment-*.gz"))
    if not files or len(files)>10000:
        raise DeepSegmentHold("READ_ONLY_REPLAY_MISSING_OR_EXCESSIVE_SEGMENTS")
    kinds=Counter()
    symbols=set()
    for p in files:
        if p.is_symlink():raise DeepSegmentHold("READ_ONLY_REPLAY_SYMLINK")
        if p.stat().st_size>1024*1024:raise DeepSegmentHold("READ_ONLY_REPLAY_OVERSIZE")
        with gzip.open(p,"rb") as f:
            rows=json.load(f)
        if not isinstance(rows,list):raise DeepSegmentHold("READ_ONLY_REPLAY_NON_ARRAY")
        for r in rows:
            if not isinstance(r,dict):raise DeepSegmentHold("READ_ONLY_REPLAY_BAD_ROW")
            kind=r.get("kind")
            if kind not in ("TRADE","MARK"):
                raise DeepSegmentHold("READ_ONLY_REPLAY_FORBIDDEN_QUOTE_OR_KIND")
            raw=base64.b64decode(r["raw_b64"],validate=True)
            obj=json.loads(raw)
            symbols.add(obj["data"]["s"]);kinds[kind]+=1
    if len(symbols)!=20 or "BTCUSDT" not in symbols:
        raise DeepSegmentHold("READ_ONLY_REPLAY_EXPECT_EXACT_20_BTC")
    recorder=DeepSegmentRecorder(folder,symbols=tuple(sorted(symbols)))
    frames,head,segments=recorder.replay()
    check_kinds=Counter(f.kind for f,_ in frames)
    each=defaultdict(set)
    ages=defaultdict(list)
    for f,raw in frames:
        each[f.kind].add(f.symbol)
        ages[f.kind].append(f.received_at_ms-f.event_at_ms)
    if len(frames)!=sum(kinds.values()) or check_kinds!=kinds:
        raise DeepSegmentHold("READ_ONLY_REPLAY_COUNT_MISMATCH")
    if any(len(each[k])!=20 for k in ("TRADE","MARK")):
        raise DeepSegmentHold("READ_ONLY_REPLAY_MISSING_KIND_SYMBOL")
    return {"state_root":str(root),"source_archived_segments":segments,
        "source_archived_frames":len(frames),
        "by_kind":dict(kinds),
        "symbols_by_kind":{k:len(v) for k,v in each.items()},
        "max_accepted_event_age_ms":{k:max(v) for k,v in ages.items()},
        "last_segment_chain_sha256":head,
        "reviewable_underlying_id_skips":recorder.last_replay_underlying_id_gap_reviews,
        "no_bid_ask_frames":True,
        "independent_exchange_signature_proven":False,
        "scientifically_qualified_virtual_outcomes":0,
        "financial_authority":"NONE"}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("state_root",type=Path)
    args=p.parse_args()
    try:
        print(json.dumps(inspect(args.state_root),sort_keys=True),flush=True)
    except Exception as e:
        print("G4_TRADE_ONLY_ARCHIVE_REPLAY_HOLD:"+type(e).__name__+":"+str(e)[:140],
              file=sys.stderr,flush=True)
        raise SystemExit(2)
