"""Create a one-time WAL-consistent READ-ONLY review COPY of original G1/G2/G3.

Source connection is sqlite mode=ro. Destination is a new standalone private
G4 evidence review file; existing G1 service, WAL and history remain untouched.
The copy is not a G4 trade label or permission to join future sources.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3

REQUIRED=frozenset(("g1f_universe_snapshots","g1f_event_manifest",
                    "g1f_candidate_events","g2_cohort_witness",
                    "g2_quote_witness","g3_event_context"))


def snapshot_integrated_source(*,source_db:str|Path,output_db:str|Path) -> dict:
    source=Path(source_db)
    out=Path(output_db)
    root=out.parent
    if (source.is_symlink() or not source.is_file()
            or source.name!="g1g2g3.sqlite" or source.resolve()==out.resolve()
            or root.is_symlink() or not root.is_dir()
            or not root.name.startswith("g4-forward-")
            or root.stat().st_mode & 0o077
            or out.is_symlink() or out.exists()
            or out.name!="g4_g1g2g3_review_copy.sqlite"):
        raise ValueError("G4_G1_SNAPSHOT_UNSAFE_SOURCE_OR_DESTINATION")
    with sqlite3.connect(source.resolve().as_uri()+"?mode=ro",
                         uri=True,timeout=12) as live:
        if live.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("G4_G1_ORIGINAL_SOURCE_INTEGRITY_HOLD")
        tables={row[0] for row in live.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED.issubset(tables):
            raise ValueError("G4_G1_ORIGINAL_SCHEMA_INCOMPLETE")
        # Opening mode=ro guarantees no source writes and online-backup copies
        # source *plus* active WAL in an internally consistent DB transaction.
        fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.close(fd)
        with sqlite3.connect(out) as copied:
            live.backup(copied,pages=64,sleep=.05)
            if copied.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise ValueError("G4_G1_BACKUP_CORRUPT")
            count=copied.execute(
                "SELECT COUNT(*) FROM g1f_event_manifest").fetchone()[0]
            candidates=copied.execute(
                "SELECT COUNT(*) FROM g1f_candidate_events").fetchone()[0]
            witnesses=copied.execute(
                "SELECT COUNT(*) FROM g2_quote_witness").fetchone()[0]
            contexts=copied.execute(
                "SELECT COUNT(*) FROM g3_event_context").fetchone()[0]
    with open(out,"rb") as reader:
        file_sha=hashlib.file_digest(reader,"sha256").hexdigest()
    return {"state":"ORIGINAL_G1_WAL_REVIEW_COPY_VERIFIED",
            "copied_path":str(out),
            "source_db_access":"READ_ONLY",
            "source_mutations":0,
            "file_sha256":file_sha,
            "events":count,
            "directional_candidates":candidates,
            "g2_witnesses":witnesses,
            "g3_contexts":contexts,
            "trading_labels":0,
            "order_authority":"NONE"}


def main():
    import argparse
    p=argparse.ArgumentParser(description="one-time original G1/G2/G3 isolated online review snapshot")
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    try:
        print(json.dumps(snapshot_integrated_source(source_db=a.source,
                                                   output_db=a.output),sort_keys=True))
        return 0
    except (ValueError,sqlite3.DatabaseError,OSError) as exc:
        print(json.dumps({"state":"HOLD","reason":str(exc),
                          "order_authority":"NONE"},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
