"""G4 one-time WAL-aware raw source backup + independent replay restore proof.

ONLY isolated G4 source-root files. Never backs up or modifies the currently
active G1/G2/G3 WAL/SQLite, no schema migration, no trading/label writes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3

from nbot.v5.g4_forward_independent_audit import audit_forward_source_copy


def backup_and_verify(*,source_db:str|Path,restore_copy:str|Path) -> dict:
    source=Path(source_db)
    restore=Path(restore_copy)
    parent=source.parent
    if (parent.is_symlink() or not parent.is_dir()
            or not parent.name.startswith("g4-forward-")
            or parent.stat().st_mode & 0o077
            or source.name!="g4_raw_source.sqlite" or not source.is_file()
            or source.is_symlink() or restore.parent.resolve()!=parent.resolve()
            or restore.name!="g4_source_restored.sqlite"
            or restore.exists() or restore.is_symlink()):
        raise ValueError("G4_SNAPSHOT_DESTINATION_NOT_ISOLATED_OR_FRESH")
    original=audit_forward_source_copy(db_path=source)
    fd=os.open(restore,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True) as db:
            with sqlite3.connect(restore) as target:
                db.backup(target,pages=128,sleep=.02)
                target.execute("PRAGMA foreign_keys=ON")
                if target.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                    raise ValueError("G4_SNAPSHOT_SQLITE_COPY_INVALID")
        restored=audit_forward_source_copy(db_path=restore)
        if (original["head_sha256"]!=restored["head_sha256"]
                or original["records_verified"]!=restored["records_verified"]
                or original["source_recorded_frames"]!=restored["source_recorded_frames"]
                or original["held_frames"]!=restored["held_frames"]):
            raise ValueError("G4_SNAPSHOT_RESTORE_REPLAY_CONFLICT")
        # The backup itself is standalone, no missing WAL replay required.
        with open(restore,"rb") as f:
            sha=hashlib.file_digest(f,"sha256").hexdigest()
        return {"status":"G4_ISOLATED_SOURCE_SQLITE_BACKUP_RESTORED_AND_VERIFIED",
                "source_head_sha256":original["head_sha256"],
                "restored_head_sha256":restored["head_sha256"],
                "backup_file_sha256":sha,
                "restored_records":restored["records_verified"],
                "source_scientific_accepted":False,
                "training_labels_created":0,"order_authority":"NONE"}
    except BaseException:
        # Do not remove uncertain partially materialized evidence; an operator
        # must inspect it as a failed backup and use a new approved destination.
        raise


def main():
    import argparse
    p=argparse.ArgumentParser(description="G4 isolated WAL-consistent SQLite restore proof")
    p.add_argument("--source",required=True)
    p.add_argument("--restore",required=True)
    a=p.parse_args()
    try:
        print(json.dumps(backup_and_verify(source_db=a.source,
                                           restore_copy=a.restore),sort_keys=True))
        return 0
    except (ValueError,OSError,sqlite3.DatabaseError) as exc:
        print(json.dumps({"status":"HOLD","reason":str(exc),
                          "order_authority":"NONE"},sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
