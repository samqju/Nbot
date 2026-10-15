"""CS-00 compact Research/Observation synthetic backup fixture.

RUN ONLY in an isolated temporary checkout. No market network, secrets,
service start, account or code checkout changes. Writes immutable small
journal/SQLite fixture and self-verified compact backup for off-host trial.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
from hashlib import sha256
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nbot_v5_1.cs00_compact_backup import (
    create_compact_backup,verify_compact_backup)

def build(root:Path):
    src=root/"evidence";archive=root/"archive"
    if root.is_symlink() or not root.is_absolute():
        raise ValueError("CS00_FIXTURE_ROOT_REQUIRED")
    src.mkdir(mode=0o700)
    archive.mkdir(mode=0o700)
    for name,row in (
        ("research.jsonl",{"experiment":"a"*64,"status":"UNRECOVERABLE_EXCLUDED",
                           "net_return":None,"source_grade":"SYNTHETIC_OFFLINE_TEST_ONLY"}),
        ("observation.jsonl",{"event":1792048000000,"markets":100,
                              "sides":200,"status":"OFFLINE_NO_TRADING"}),
        ("source-recovery.jsonl",{"source":"public-aggTrades","scope":"TRADE_PATH_ONLY",
                                  "original_quote_verified":False})):
        p=src/name
        p.write_text(json.dumps(row,sort_keys=True)+"\n",encoding="ascii")
        p.chmod(0o600)
    db=sqlite3.connect(src/"learning.sqlite")
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE lineage(id TEXT PRIMARY KEY,state TEXT,net_r TEXT)")
        db.execute("INSERT INTO lineage VALUES (?,?,?)",
                   ("a"*64,"UNRECOVERABLE_EXCLUDED",None))
        db.commit()
    finally:db.close()
    (src/"learning.sqlite").chmod(0o600)
    result=create_compact_backup(source=src,destination=archive,
        filenames=("research.jsonl","observation.jsonl",
                   "source-recovery.jsonl","learning.sqlite"))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("create","verify"))
    p.add_argument("root",type=Path)
    args=p.parse_args()
    proof=build(args.root) if args.action=="create" else verify_compact_backup(
        args.root/"archive")
    print(json.dumps(proof,sort_keys=True),flush=True)
