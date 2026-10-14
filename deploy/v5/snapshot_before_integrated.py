"""One-time read-only V5 observation SQLite online backup before G1-G3 cutover.

Creates a NEW isolated snapshot with SQLite backup API, integrity_check,
strict no-overwrite, and SHA256. Never stops or mutates the active collector.
"""
from pathlib import Path
import hashlib
import os
import sqlite3

SOURCE=Path("/home/ubuntu/nbot_v5_data/g1f_observe.sqlite")
DEST=Path("/home/ubuntu/nbot_v5_data/g1f_pre_integrated_20261014.sqlite")

def main() -> int:
    if SOURCE.is_symlink() or DEST.is_symlink() or not SOURCE.is_file() or DEST.exists():
        print("SNAPSHOT_HOLD source missing/link or destination already exists")
        return 2
    if SOURCE.parent != DEST.parent:
        print("SNAPSHOT_HOLD unsupported snapshot folder")
        return 2
    try:
        dest_fd=os.open(str(DEST),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.close(dest_fd)
        with sqlite3.connect(SOURCE.resolve().as_uri()+"?mode=ro",uri=True,timeout=15) as source:
            with sqlite3.connect(str(DEST),timeout=15) as target:
                source.backup(target,pages=200,sleep=.1)
                if target.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise ValueError("SNAPSHOT_INTEGRITY_FAILED")
        sha=hashlib.sha256(DEST.read_bytes()).hexdigest()
        print("SNAPSHOT_PASS",DEST,DEST.stat().st_size,"SHA256",sha)
        return 0
    except (sqlite3.DatabaseError,ValueError,OSError) as exc:
        print("SNAPSHOT_HOLD",type(exc).__name__,str(exc))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
