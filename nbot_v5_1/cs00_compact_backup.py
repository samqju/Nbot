"""CS-00 compact durable records: immutable small backup with strict restore.

Designed for V4-style journal/SQLite Research, Observation and model receipts,
not full tick-stream replication. No network, no source deletion, no symlinks.
Restores only to fresh private directory; a second host can independently
verify the exact copied bundle. SQLite uses online backup, not WAL file copying.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import sqlite3
import stat
from urllib.parse import quote

VERSION="NBOT_V5_1_CS00_COMPACT_BACKUP_V1"
MAX_FILE_BYTES=16*1024*1024
MAX_TOTAL_BYTES=64*1024*1024
_ALLOWED=re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,70}\.(jsonl|json|sqlite|db|sha256|txt)\Z")

class CompactBackupHold(ValueError):pass

def _secure_dir(p:Path):
    if not isinstance(p,Path) or not p.is_absolute() or p.is_symlink() or not p.is_dir():
        raise CompactBackupHold("CS00_BACKUP_PRIVATE_DIRECTORY_REQUIRED")
    s=p.stat()
    if s.st_uid!=os.getuid() or s.st_mode&0o077:
        raise CompactBackupHold("CS00_BACKUP_DIRECTORY_UNSAFE")

def _read(p:Path):
    if p.is_symlink():
        raise CompactBackupHold("CS00_BACKUP_SYMLINK_DENIED")
    fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_size>MAX_FILE_BYTES:
            raise CompactBackupHold("CS00_BACKUP_FILE_UNSAFE")
        raw=os.read(fd,MAX_FILE_BYTES+1)
        if len(raw)!=s.st_size:
            raise CompactBackupHold("CS00_BACKUP_SHORT_READ")
        return raw
    finally:os.close(fd)

def _write(p:Path,data:bytes):
    if not isinstance(data,bytes) or len(data)>MAX_FILE_BYTES:
        raise CompactBackupHold("CS00_BACKUP_PAYLOAD_BOUNDS")
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        view=memoryview(data)
        while view:
            n=os.write(fd,view)
            if n<=0:raise CompactBackupHold("CS00_BACKUP_SHORT_WRITE")
            view=view[n:]
        os.fsync(fd)
    finally:os.close(fd)
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def _canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

def create_compact_backup(*,source:Path,destination:Path,filenames:tuple[str,...]):
    _secure_dir(source);_secure_dir(destination)
    if (not isinstance(filenames,tuple) or not 1<=len(filenames)<=40
            or len(set(filenames))!=len(filenames)
            or any(type(n) is not str or not _ALLOWED.fullmatch(n)
                   or n=="manifest.json" for n in filenames)):
        raise CompactBackupHold("CS00_BACKUP_UNSAFE_SCOPE")
    if tuple(destination.iterdir()):
        raise CompactBackupHold("CS00_BACKUP_DESTINATION_NOT_EMPTY")
    items=[];used=0
    for name in filenames:
        path=source/name
        if name.endswith((".sqlite",".db")):
            # Coherent online backup includes committed WAL changes; do not
            # preserve a raw potentially stale SQLite base file.
            if path.is_symlink() or not path.is_file():
                raise CompactBackupHold("CS00_BACKUP_SQLITE_SOURCE_UNSAFE")
            st=path.stat()
            if st.st_uid!=os.getuid() or st.st_mode&0o077 or st.st_size>MAX_FILE_BYTES:
                raise CompactBackupHold("CS00_BACKUP_SQLITE_PERMISSION_OR_SIZE")
            try:
                src=sqlite3.connect("file:"+quote(str(path))+"?mode=ro",uri=True)
                try:
                    target=destination/name
                    tmp=sqlite3.connect(target)
                    try:src.backup(tmp,pages=32)
                    finally:tmp.close()
                finally:src.close()
                os.chmod(target,0o600)
                if sqlite3.connect(target).execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise CompactBackupHold("CS00_BACKUP_SQLITE_INTEGRITY_BAD")
                raw=_read(target)
                with open(target,"rb") as f:os.fsync(f.fileno())
            except (sqlite3.Error,OSError) as exc:
                raise CompactBackupHold("CS00_BACKUP_SQLITE_FAILED") from exc
        else:
            raw=_read(path)
            _write(destination/name,raw)
        used+=len(raw)
        if used>MAX_TOTAL_BYTES:
            raise CompactBackupHold("CS00_BACKUP_TOTAL_CAPACITY_HOLD")
        items.append({"name":name,"bytes":len(raw),"sha256":sha256(raw).hexdigest()})
    manifest={"schema":VERSION,"files":items,"total_bytes":used,
              "source_grade":"COMPACT_LEDGER_BACKUP_NOT_ORIGINAL_MARKET_CERTIFICATION",
              "order_authority":"NONE"}
    _write(destination/"manifest.json",_canon(manifest))
    return verify_compact_backup(destination)

def verify_compact_backup(root:Path):
    _secure_dir(root)
    data=_read(root/"manifest.json")
    if _canon(json.loads(data))!=data:
        raise CompactBackupHold("CS00_BACKUP_MANIFEST_NONCANONICAL")
    body=json.loads(data)
    if (type(body) is not dict or body.get("schema")!=VERSION
            or body.get("order_authority")!="NONE"
            or type(body.get("files")) is not list or not 1<=len(body["files"])<=40):
        raise CompactBackupHold("CS00_BACKUP_MANIFEST_INVALID")
    items=body["files"]
    names=[]
    total=0
    for e in items:
        if (type(e) is not dict or set(e)!={"name","bytes","sha256"}
                or type(e["name"]) is not str or not _ALLOWED.fullmatch(e["name"])
                or e["name"]=="manifest.json"
                or type(e["bytes"]) is not int or not 0<=e["bytes"]<=MAX_FILE_BYTES
                or type(e["sha256"]) is not str or not re.fullmatch("[a-f0-9]{64}",e["sha256"])):
            raise CompactBackupHold("CS00_BACKUP_RECEIPT_INVALID")
        names.append(e["name"])
        raw=_read(root/e["name"])
        if len(raw)!=e["bytes"] or sha256(raw).hexdigest()!=e["sha256"]:
            raise CompactBackupHold("CS00_BACKUP_TAMPER_OR_MISSING")
        total+=len(raw)
    if (len(set(names))!=len(names) or
            {p.name for p in root.iterdir()}!=set(names)|{"manifest.json"}
            or total!=body.get("total_bytes") or total>MAX_TOTAL_BYTES):
        raise CompactBackupHold("CS00_BACKUP_SCOPE_OR_TOTAL_INVALID")
    return {"schema":VERSION,"files":len(names),"total_bytes":total,
            "manifest_sha256":sha256(data).hexdigest(),
            "scientifically_qualified_original":False,
            "offhost_independently_verified":False,
            "order_authority":"NONE"}
