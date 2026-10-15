"""Strict read-only G4 collector bootstrap from original G1 frozen cohort.

No source files written, no exchange network, no systemd action, no trading.
The owner-approved capture unit uses this as ExecStartPre before any WSS.
"""
import json
from pathlib import Path
import sqlite3
from contextlib import closing

from nbot.v5.g4_forward_capture_runner import source_cohort_file
from nbot.v5.g4_segmented_source import read_segments


def audit_g4_capture_preflight(*,g1_db,cohort_manifest,source_root):
    root=Path(source_root)
    source=Path(g1_db)
    frozen=Path(cohort_manifest)
    if (source.is_symlink() or not source.is_file()
            or source.name!="g1g2g3.sqlite"
            or frozen.is_symlink() or not frozen.is_file()
            or not root.is_dir() or root.is_symlink()
            or not root.name.startswith("g4-forward-")
            or root.stat().st_mode & 0o077
            or frozen.parent.resolve()!=root.resolve()
            or source.resolve().parent==root.resolve()):
        raise ValueError("G4_BOOTSTRAP_SOURCE_ROOT_OR_FILE_HOLD")
    selected=source_cohort_file(frozen.read_bytes())
    with closing(sqlite3.connect(source.resolve().as_uri()+"?mode=ro",
                                 uri=True,timeout=12)) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("G4_BOOTSTRAP_G1_DB_INTEGRITY_HOLD")
        rows=db.execute(
            "SELECT symbols_json,cohort_digest "
            "FROM g1f_universe_snapshots").fetchall()
        if len(rows)!=1:
            raise ValueError("G4_BOOTSTRAP_G1_FROZEN_COHORT_MISSING")
        symbols=json.loads(rows[0][0])
        digest=rows[0][1]
        if (symbols!=list(selected) or
                digest!=json.loads(frozen.read_bytes())["cohort_digest"]):
            raise ValueError("G4_BOOTSTRAP_COHORT_G1_DIGEST_CONFLICT")
    segment_dir=root/"segments"
    if segment_dir.exists():
        if segment_dir.is_symlink() or not segment_dir.is_dir():
            raise ValueError("G4_BOOTSTRAP_SEGMENT_PATH_UNSAFE")
        for _,_raw in read_segments(segment_dir,selected):
            pass
    if any(p.is_symlink() for p in root.iterdir()):
        raise ValueError("G4_BOOTSTRAP_UNEXPECTED_SYMLINK")
    return {
        "audit":"PASS","symbols":len(selected),
        "original_frozen_cohort_digest":digest,
        "g1_db_access":"READ_ONLY",
        "g4_segment_archive":"EXISTING_AUDITED" if segment_dir.exists()
                               else "NEW_ARCHIVE_ALLOWED",
        "financial_authority":"NONE","order_authority":"NONE",
    }


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description="G4 public source capture bootstrap audit")
    p.add_argument("--g1-db",required=True)
    p.add_argument("--cohort-manifest",required=True)
    p.add_argument("--source-root",required=True)
    args=p.parse_args(argv)
    try:
        report=audit_g4_capture_preflight(
            g1_db=args.g1_db,cohort_manifest=args.cohort_manifest,
            source_root=args.source_root)
        print(json.dumps(report,sort_keys=True))
        return 0
    except (OSError,ValueError,sqlite3.DatabaseError,KeyError,TypeError) as exc:
        print(json.dumps({"audit":"HOLD","reason":str(exc),
                          "order_authority":"NONE"},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
