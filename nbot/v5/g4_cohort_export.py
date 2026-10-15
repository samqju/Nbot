"""Export a frozen G1/G2 cohort for an independently isolated G4 pilot.

Read-only on active G1/G2/G3 WAL SQLite, write-only a new private G4 manifest.
Never updates SQLite, source health services, trading or outcome labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from nbot.v5.g1f_journal import canonical, digest


def export_frozen_cohort(*, db_path: str|Path, output: str|Path) -> dict:
    dbpath=Path(db_path)
    out=Path(output)
    if dbpath.is_symlink() or not dbpath.is_file():
        raise ValueError("G4_COHORT_INPUT_NOT_REGULAR_DB")
    parent=out.parent
    if (parent.is_symlink() or not parent.is_dir()
            or not parent.name.startswith("g4-forward-")
            or parent.stat().st_mode & 0o077 or out.is_symlink()):
        raise ValueError("G4_COHORT_ISOLATED_OUTPUT_DIR_INVALID")
    if out.name not in ("frozen_cohort.json","cohort.json") or out.exists():
        raise ValueError("G4_COHORT_OUTPUT_NAME_OR_EXISTENCE_INVALID")
    with sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro",uri=True) as db:
        rows=db.execute("SELECT cohort_digest,symbols_json,selection_version "
                        "FROM g1f_universe_snapshots").fetchall()
        if len(rows)!=1:
            raise ValueError("G4_COHORT_UNIQUE_ORIGINAL_G1_REQUIRED")
        identity,raw,version=rows[0]
        symbols=json.loads(raw)
        if (version!="USDM_PERPETUAL_24H_QUOTE_VOLUME_V1"
                or not isinstance(symbols,list) or len(symbols)!=50
                or symbols!=sorted(set(symbols)) or "BTCUSDT" not in symbols
                or raw!=canonical(symbols)
                or identity!=digest({"selection_version":version,"symbols":tuple(symbols)})):
            raise ValueError("G4_COHORT_FROZEN_G1_SOURCE_INVALID")
        original=db.execute(
            "SELECT payload_json,payload_sha FROM g2_cohort_witness "
            "WHERE cohort_digest=?", (identity,)).fetchall()
        if (len(original)!=1
                or hashlib.sha256(original[0][0].encode()).hexdigest()!=original[0][1]):
            raise ValueError("G4_COHORT_G2_WITNESS_NOT_VERIFIED")
        evidence=json.loads(original[0][0])
        if evidence.get("cohort_digest")!=identity or sorted(evidence.get("ranked_selected",[]))!=symbols:
            raise ValueError("G4_COHORT_ORIGINAL_G2_MEMBERS_NOT_MATCHED")
    body=canonical({"cohort_digest":identity,"symbols":symbols})
    # O_EXCL plus restrictive mode: never rewrite an already frozen manifest.
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as stream:
            stream.write(body+"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        raise
    return {"status":"FROZEN_COHORT_COPIED_ONLY",
            "output":str(out),
            "sha256":hashlib.sha256((body+"\n").encode()).hexdigest(),
            "source_cohort_digest":identity,"symbols":len(symbols),
            "source_db_mutations":0,"model_labels_created":0,
            "order_authority":"NONE"}


def main():
    p=argparse.ArgumentParser(description="One-time read-only G1/G2 50-symbol manifest export")
    p.add_argument("--source-db",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    try:
        print(json.dumps(export_frozen_cohort(db_path=args.source_db,
                                             output=args.output),sort_keys=True))
        return 0
    except (OSError,ValueError,sqlite3.DatabaseError) as exc:
        print(json.dumps({"status":"HOLD","reason":str(exc),"order_authority":"NONE"},
                         sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
