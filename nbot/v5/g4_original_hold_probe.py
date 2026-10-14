"""Read-only independent original G1/G2/G3 event HOLD forensic report.

The collector intentionally persists held events; never reinterpret them as
research economic losses or erase them from the 24-hour continuity denominator.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3

def find_explicit_g1_holds(db_path:str|Path):
    p=Path(db_path)
    if not p.is_file() or p.is_symlink():
        raise ValueError("G1_HOLD_PROBE_SOURCE_INVALID")
    out=[]
    with sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True,timeout=10) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("G1_HOLD_PROBE_DB_INTEGRITY_INVALID")
        total=db.execute("SELECT count(*) FROM g1f_event_manifest").fetchone()[0]
        events=db.execute(
            "SELECT event_open_ms,committed_ms,verification_json "
            "FROM g1f_event_manifest WHERE state='HOLD' ORDER BY event_open_ms").fetchall()
        for event,committed,raw in events:
            manifest=json.loads(raw)
            reasons=Counter()
            symbols=set()
            for sym,raw_c in db.execute(
                "SELECT symbol,record_json FROM g1f_candidate_events "
                "WHERE event_open_ms=?",(event,)):
                c=json.loads(raw_c)
                if c.get("reason_codes"):
                    reasons.update(c["reason_codes"])
                    symbols.add(sym)
            g2_hold=db.execute(
                "SELECT count(*) FROM g2_quote_witness "
                "WHERE event_open_ms=? AND payload_json LIKE '%\\\"status\\\":\\\"HOLD\\\"%'",
                (event,)).fetchone()[0]
            ctx=db.execute(
                "SELECT payload_json FROM g3_event_context "
                "WHERE event_open_ms=?",(event,)).fetchone()
            g3=json.loads(ctx[0]) if ctx else {}
            out.append({
                "event_open_ms":event,
                "event_open_utc":datetime.fromtimestamp(event/1000,timezone.utc).isoformat(),
                "committed_ms":committed,
                "manifest":manifest,
                "held_unique_symbols":len(symbols),
                "candidate_reason_counts":dict(sorted(reasons.items())),
                "g2_witness_hold_rows":g2_hold,
                "g3_context_status":g3.get("status"),
                "g3_reasons":g3.get("reasons"),
            })
    return {"total_event_manifests":total,
            "explicit_hold_events":len(events),
            "holds":out,
            "original_source_mutations":0,
            "order_authority":"NONE"}


def main():
    import argparse
    a=argparse.ArgumentParser()
    a.add_argument("--db",required=True)
    opts=a.parse_args()
    try:
        result=find_explicit_g1_holds(opts.db)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,OSError,sqlite3.DatabaseError) as exc:
        print(json.dumps({"state":"HOLD","reason":str(exc),
                          "order_authority":"NONE"},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
