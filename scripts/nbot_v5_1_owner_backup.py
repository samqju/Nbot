#!/usr/bin/env python3
"""NBOT V5.1 — one-command, manual-only, records-only, WinSCP backup.

Standalone Ubuntu executable, no imports from the NBOT trading code,
network calls, credential discovery, service startup, destructive cleanup
or offhost transfer. Back up ONLY a private, approved V5.1 state root.

No state files => NO BACKUP, never a fake success. Every unknown/symlinked/
unsafe file => HOLD rather than a silently incomplete copy. SQLite online
backup includes committed WAL writes. Other files are read with in-run
change detection; backup is a best-effort cross-file snapshot, NOT an
atomic live-service checkpoint without the future writer lock integration.
"""
from __future__ import annotations
import hashlib
import gzip
import zlib
import fcntl
import time
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote

VERSION="NBOT_V5_1_MANUAL_OWNER_RECORDS_BACKUP_V1"
HOME=Path.home()
STATE_ROOT=HOME/"nbot-v5.1-state"
BACKUP_ROOT=HOME/"NBOT_Backups"
CATEGORIES=frozenset(("observations","exploration","research","learning",
                      "models","evidence","journals","paper"))
EXTENSIONS=frozenset((".jsonl",".json",".db",".sqlite",".sqlite3",".csv",".txt",
                      ".sha256",".gz",".parquet",".onnx",".pkl",".joblib",
                      ".npz",".npy",".yaml",".yml"))
_NAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")
_SHA=re.compile(r"[a-f0-9]{64}\Z")
SENSITIVE=("secret","private","api_key","apikey","credential",
           "password","token","session","id_rsa","id_ed25519",
           "wallet","seedphrase","access_key","putty",".env")
MAX_FILE_BYTES=512*1024*1024
MAX_TOTAL_BYTES=2*1024*1024*1024
MAX_FILES=3000
MIN_FREE_AFTER_BYTES=512*1024*1024

class BackupHold(ValueError):
    pass

def _private_dir(p:Path):
    if (not isinstance(p,Path) or not p.is_absolute()
            or p.is_symlink() or not p.is_dir()):
        raise BackupHold("PRIVATE_DIRECTORY_MISSING")
    st=p.stat()
    if (st.st_uid!=os.getuid() or st.st_mode & 0o077):
        raise BackupHold("PRIVATE_DIRECTORY_OWNER_OR_PERMISSIONS")

def _allowed_path(rel:Path):
    parts=rel.parts
    if len(parts)>5 or not 1<=len(parts) or any(not _NAME.fullmatch(x) for x in parts):
        raise BackupHold("UNRECOGNIZED_RECORD_PATH")
    if len(parts)>1 and parts[0] not in CATEGORIES:
        raise BackupHold("RECORD_CATEGORY_NOT_CONFIGURED")
    name=parts[-1]
    if any(x in name.lower() for x in SENSITIVE):
        raise BackupHold("POSSIBLE_SECRET_IN_RECORD_PATH")
    if not any(name.endswith(s) for s in EXTENSIONS):
        raise BackupHold("UNSUPPORTED_RECORD_TYPE")
    return rel.as_posix()

def _ignored_sqlite_companion(rel:Path,root:Path):
    if not rel.name.endswith(("-wal","-shm","-journal")):
        return False
    main=rel.with_name(rel.name.rsplit("-",1)[0])
    return (main.suffix.lower() in (".db",".sqlite",".sqlite3")
            and (root/main).is_file())

def _walk_files(root:Path):
    _private_dir(root)
    records=[]
    for current, dirs, files in os.walk(root,topdown=True,followlinks=False):
        current=Path(current)
        relative=current.relative_to(root)
        if len(relative.parts)>4:
            raise BackupHold("NESTING_TOO_DEEP")
        for name in dirs:
            rel=relative/name
            if (not _NAME.fullmatch(name) or
                    len(rel.parts)==1 and name not in CATEGORIES):
                raise BackupHold("UNEXPECTED_DIRECTORY_OR_CATEGORY")
            p=root/rel
            if p.is_symlink():
                raise BackupHold("SYMLINK_DIRECTORY_DENIED")
            _private_dir(p)
        for name in files:
            rel=relative/name
            p=root/rel
            if p.is_symlink():
                raise BackupHold("SYMLINK_FILE_DENIED")
            if _ignored_sqlite_companion(rel,root):
                continue
            _allowed_path(rel)
            st=p.stat()
            if (not stat.S_ISREG(st.st_mode)
                    or st.st_uid!=os.getuid() or st.st_nlink!=1
                    or st.st_mode & 0o077 or st.st_size>MAX_FILE_BYTES):
                raise BackupHold("RECORD_NOT_PRIVATE_REGULAR_OR_TOO_LARGE")
            records.append((rel,p,st.st_size))
            if len(records)>MAX_FILES:
                raise BackupHold("TOO_MANY_RECORD_FILES")
    records.sort(key=lambda x:x[0].as_posix())
    if sum(x[2] for x in records)>MAX_TOTAL_BYTES:
        raise BackupHold("TOTAL_RECORDS_OVER_BUDGET")
    return records

def _copy_regular(src:Path,dst:Path,initial_size:int):
    before=src.stat()
    if before.st_size!=initial_size:
        raise BackupHold("RECORD_CHANGED_DURING_ENUMERATION")
    fd=os.open(src,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1
                or st.st_uid!=os.getuid() or st.st_mode&0o077
                or st.st_size!=initial_size):
            raise BackupHold("RECORD_SOURCE_REPLACED_OR_PERMISSIONS")
        hashv=hashlib.sha256();n=0
        with open(dst,"xb") as out:
            os.chmod(dst,0o600)
            while True:
                buf=os.read(fd,1024*1024)
                if not buf:break
                n+=len(buf)
                if n>MAX_FILE_BYTES:raise BackupHold("RECORD_GREW_TOO_LARGE")
                hashv.update(buf);out.write(buf)
            out.flush();os.fsync(out.fileno())
        after=os.fstat(fd)
        path_after=src.stat()
        if (n!=initial_size or after.st_ino!=path_after.st_ino
                or after.st_size!=initial_size
                or after.st_mtime_ns!=st.st_mtime_ns
                or after.st_ctime_ns!=st.st_ctime_ns
                or path_after.st_mtime_ns!=st.st_mtime_ns
                or path_after.st_ctime_ns!=st.st_ctime_ns):
            raise BackupHold("RECORD_CHANGED_DURING_COPY_RETRY_LATER")
        return hashv.hexdigest(),n
    finally:os.close(fd)

def _copy_sqlite(src:Path,dst:Path):
    if src.is_symlink():
        raise BackupHold("SQLITE_SYMLINK_DENIED")
    try:
        inp=sqlite3.connect("file:"+quote(str(src))+"?mode=ro",uri=True,timeout=5)
        try:
            out=sqlite3.connect(dst,timeout=5)
            try:
                inp.backup(out,pages=128,sleep=0.05)
                # Output must be a standalone consistent file, no WAL needed.
                out.execute("PRAGMA journal_mode=DELETE")
            finally:out.close()
        finally:inp.close()
        os.chmod(dst,0o600)
        check=sqlite3.connect("file:"+quote(str(dst))+"?mode=ro",uri=True)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise BackupHold("SQLITE_INTEGRITY_CHECK_FAILED")
        finally:check.close()
    except (OSError,sqlite3.Error) as exc:
        raise BackupHold("SQLITE_CANNOT_CHECKPOINT_SAFELY") from exc
    h=hashlib.sha256();count=0
    with open(dst,"rb") as f:
        while True:
            piece=f.read(1024*1024)
            if not piece:break
            count+=len(piece)
            if count>MAX_FILE_BYTES:raise BackupHold("SQLITE_BACKUP_TOO_LARGE")
            h.update(piece)
    return h.hexdigest(),count

def _add(tar:tarfile.TarFile,name:str,path:Path):
    info=tarfile.TarInfo(name)
    info.size=path.stat().st_size
    info.mode=0o600
    info.uid=info.gid=0
    info.uname=info.gname=""
    info.mtime=0
    with open(path,"rb") as src:tar.addfile(info,src)

def _verify_archive(path:Path):
    with tarfile.open(path,"r:gz") as t:
        names=t.getnames()
        if (not names or names[-1]!="MANIFEST.json" or
                len(names)!=len(set(names)) or
                any(not m.isfile() for m in t.getmembers())):
            raise BackupHold("ARCHIVE_LAYOUT_INVALID")
        obj=t.extractfile("MANIFEST.json")
        if obj is None:raise BackupHold("MANIFEST_MISSING")
        manifest=json.loads(obj.read(2*1024*1024))
        if (manifest.get("schema")!=VERSION or
                manifest.get("data_grade")!="RECORDS_BACKUP_NOT_SOURCE_QUALIFICATION"
                or manifest.get("trading_authority")!="NONE"):
            raise BackupHold("MANIFEST_GRADE_INVALID")
        entries=manifest["files"]
        if names[:-1]!=[x["path"] for x in entries]:
            raise BackupHold("ARCHIVE_MANIFEST_ENTRIES_MISMATCH")
        for item in entries:
            if (not _SHA.fullmatch(item["sha256"])
                    or type(item["bytes"]) is not int):
                raise BackupHold("ARCHIVE_MANIFEST_FILE_INVALID")
            f=t.extractfile(item["path"])
            if f is None:raise BackupHold("ARCHIVE_ENTRY_MISSING")
            h=hashlib.sha256();n=0
            while True:
                chunk=f.read(1024*1024)
                if not chunk:break
                h.update(chunk);n+=len(chunk)
                if n>MAX_FILE_BYTES:raise BackupHold("ARCHIVE_EXPANSION_LIMIT")
            if h.hexdigest()!=item["sha256"] or n!=item["bytes"]:
                raise BackupHold("ARCHIVE_MEMBER_HASH_MISMATCH")
        return manifest


@contextmanager
def _exclusive_state_backup_gate(state:Path):
    """Writer and backup share one OS cross-process lock; no half-boundaries."""
    _private_dir(state)
    path=state.parent/".nbot-v5.1-state.lock"
    if path.is_symlink():
        raise BackupHold("STATE_LOCK_SYMLINK_DENIED")
    fd=os.open(path,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid()
                or st.st_nlink!=1 or st.st_mode&0o077):
            raise BackupHold("STATE_LOCK_UNSAFE")
        expiry=time.monotonic()+8
        while True:
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=expiry:
                    raise BackupHold("STATE_IS_BUSY_BACKUP_RETRY")
                time.sleep(0.05)
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

def _verify_checkpoint_tree(root:Path):
    """Standalone integrity check, no NBOT imports or network."""
    g2=root/"observations";g3=root/"exploration";journal=root/"journals"
    if not any(x.exists() for x in (g2,g3,journal)):
        return
    for x in (g2,g3,journal):
        _private_dir(x)
    ev={p.name for p in g2.glob("event_*.json")}
    exp={p.name for p in g3.glob("g3_*.json.gz")}
    commits={p.name for p in journal.glob("checkpoint_*.json")}
    if bool(ev)!=bool(exp) or bool(exp)!=bool(commits):
        raise BackupHold("STATE_CHECKPOINT_INCOMPLETE_G2_G3")
    if not ev and not exp and not commits:
        # Manifest-only data would be neither complete nor a real outcome.
        if any(g2.iterdir()) or any(g3.iterdir()) or any(journal.iterdir()):
            raise BackupHold("STATE_MANIFEST_WITHOUT_COMPLETED_BOUNDARY")
        return
    seen_events=set()
    seen_paths=set()
    for p in sorted(journal.iterdir()):
        if not re.fullmatch(r"checkpoint_[0-9]{16}\.json",p.name):
            raise BackupHold("STATE_UNKNOWN_JOURNAL_RECEIPT")
        raw=p.read_bytes()
        if len(raw)>16384:
            raise BackupHold("STATE_CHECKPOINT_SIZE")
        try:
            item=json.loads(raw)
            event=item["event_ms"]
            files=item["files"]
            if (type(event) is not int or
                    p.name!=f"checkpoint_{event:016d}.json" or
                    item["schema"]!="NBOT_V5_1_CS00_STATE_CHECKPOINT_V1" or
                    item["financial_authority"]!="NONE" or
                    item["state"]!="COMMITTED_SOURCE_ONLY_UNQUALIFIED" or
                    type(files) is not list or len(files)!=3 or
                    event in seen_events or
                    raw!=json.dumps(item,sort_keys=True,separators=(",",":"),
                                    allow_nan=False).encode("ascii")):
                raise ValueError("format")
            seen_events.add(event)
            for rec in files:
                name=rec["path"]
                if (type(name) is not str or
                    not re.fullmatch(r"(observations/(event|manifest)_[0-9a-f]{64}\.json|exploration/g3_[0-9]{16}_[0-9a-f]{64}\.json\.gz)",name)
                    or type(rec["sha256"]) is not str or
                    not _SHA.fullmatch(rec["sha256"])):
                    raise ValueError("unsafe checkpoint path")
                q=root/name
                if q.is_symlink() or not q.is_file():
                    raise ValueError("missing receipt")
                if hashlib.sha256(q.read_bytes()).hexdigest()!=rec["sha256"]:
                    raise ValueError("receipt changed")
                seen_paths.add(name)
        except (KeyError,ValueError,TypeError,UnicodeError,OSError) as exc:
            raise BackupHold("STATE_CHECKPOINT_INVALID_OR_TAMPER") from exc
    if ({"observations/"+p for p in ev}|{"exploration/"+p for p in exp})-seen_paths:
        raise BackupHold("STATE_PARTIAL_BOUNDARY_NOT_COMMITTED")
    if len(commits)!=len(ev) or len(commits)!=len(exp):
        raise BackupHold("STATE_G2_G3_MISSING_CHECKPOINT")


def _verify_original_segment_pairs(root:Path):
    """Fail closed on torn or altered G4 zipped source receipts."""
    folder=root/"evidence"
    if not folder.exists():return
    _private_dir(folder)
    files=sorted(folder.iterdir())
    if not files:return
    pairs={}
    for p in files:
        m=re.fullmatch(r"segment-([0-9]{8})\.(json|gz)",p.name)
        if not m or p.is_symlink() or not p.is_file():
            raise BackupHold("STATE_EVIDENCE_UNKNOWN_OR_UNSAFE")
        st=p.stat()
        if st.st_uid!=os.getuid() or st.st_mode&0o077 or st.st_nlink!=1:
            raise BackupHold("STATE_EVIDENCE_FILE_UNSAFE")
        pairs.setdefault(int(m.group(1)),set()).add(m.group(2))
    ids=sorted(pairs)
    if ids!=list(range(1,len(ids)+1)):
        raise BackupHold("STATE_EVIDENCE_SEQUENCE_MISSING")
    last="0"*64
    for i in ids:
        if pairs[i]!={"json","gz"}:
            raise BackupHold("STATE_EVIDENCE_SEGMENT_UNCOMMITTED_PAIR")
        stem=f"segment-{i:08d}"
        packed=(folder/(stem+".gz")).read_bytes()
        receipt=(folder/(stem+".json")).read_bytes()
        try:
            data=json.loads(receipt)
            if (data.get("schema")!="NBOT_V5_1_G4_SEGMENT_V1" or
                    data.get("id")!=i or data.get("previous")!=last or
                    data.get("compressed_sha256")!=hashlib.sha256(packed).hexdigest() or
                    receipt!=json.dumps(data,sort_keys=True,separators=(",",":"),
                                        ensure_ascii=True,allow_nan=False).encode("ascii")
                    or len(packed)>1024*1024):
                raise ValueError("segment hash chain")
            obj=zlib.decompressobj(16+zlib.MAX_WBITS)
            body=obj.decompress(packed,1024*1024+1)
            if (len(body)>1024*1024 or not obj.eof or obj.unused_data or
                    data.get("body_sha256")!=hashlib.sha256(body).hexdigest()):
                raise ValueError("segment body")
        except (ValueError,TypeError,OSError,EOFError) as exc:
            raise BackupHold("STATE_EVIDENCE_SEGMENT_CORRUPT") from exc
        last=hashlib.sha256(receipt).hexdigest()

def create_backup(*,state:Path=STATE_ROOT,destination:Path=BACKUP_ROOT):
    with _exclusive_state_backup_gate(state):
        _verify_checkpoint_tree(state)
        _verify_original_segment_pairs(state)
        return _create_backup_locked(state=state,destination=destination)

def _create_backup_locked(*,state:Path,destination:Path):
    _private_dir(state)
    _private_dir(destination)
    records=_walk_files(state)
    if not records:
        raise BackupHold("NO_V5_1_RECORDS_YET__NO_FALSE_BACKUP_CREATED")
    if os.statvfs(destination).f_bavail*os.statvfs(destination).f_frsize < (
            MIN_FREE_AFTER_BYTES+sum(r[2] for r in records)):
        raise BackupHold("VPS_FREE_DISK_RESERVE_HOLD")
    dt=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name=f"NBOT_V5.1_records_{dt}_{secrets.token_hex(4)}.tar.gz"
    final=destination/name
    tmp=destination/("."+name+".incomplete")
    # Stage cleartext snapshots in a private temporary directory on the VPS.
    # Never leaves partial successful archive; never auto-deletes a backup.
    try:
        with tempfile.TemporaryDirectory(prefix=".nbot-owner-snapshot-",dir=destination) as work:
            w=Path(work);entries=[]
            for idx,(rel,path,sz) in enumerate(records):
                staging=w/f"record-{idx:04d}"
                if rel.suffix in (".sqlite",".sqlite3",".db"):
                    digest,n=_copy_sqlite(path,staging)
                else:digest,n=_copy_regular(path,staging,sz)
                entries.append({"path":rel.as_posix(),"sha256":digest,"bytes":n})
            manifest={"schema":VERSION,"created_utc":datetime.now(timezone.utc).isoformat(),
                      "source_root":str(state),"data_grade":"RECORDS_BACKUP_NOT_SOURCE_QUALIFICATION",
                      "consistency":"PER_FILE_STABLE_AND_SQLITE_ONLINE_BACKUP_NOT_GLOBAL_TRANSACTION",
                      "trading_authority":"NONE","files":entries}
            man=w/"manifest"
            man.write_bytes(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode("ascii"))
            man.chmod(0o600)
            with open(tmp,"xb") as raw:
                os.fchmod(raw.fileno(),0o600)
                with tarfile.open(fileobj=raw,mode="w:gz",compresslevel=6) as tar:
                    for i,item in enumerate(entries):
                        _add(tar,item["path"],w/f"record-{i:04d}")
                    _add(tar,"MANIFEST.json",man)
                raw.flush();os.fsync(raw.fileno())
        verified=_verify_archive(tmp)
        raw_sha=hashlib.sha256()
        with open(tmp,"rb") as f:
            for piece in iter(lambda:f.read(1024*1024),b""):
                raw_sha.update(piece)
        digest=raw_sha.hexdigest()
        # Hard-link publish is atomic and refuses to overwrite another backup.
        os.link(tmp,final,follow_symlinks=False)
        os.unlink(tmp)
        sidecar=destination/(name+".sha256")
        with open(sidecar,"x",encoding="ascii") as out:
            os.chmod(sidecar,0o600)
            out.write(f"{digest}  {name}\n")
            out.flush();os.fsync(out.fileno())
        root_fd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(root_fd)
        finally:os.close(root_fd)
        return {"status":"BACKUP_CREATED_AND_LOCALLY_VERIFIED",
                "backup":str(final),"sha256_file":str(sidecar),
                "sha256":digest,"files":len(verified["files"]),
                "archive_bytes":final.stat().st_size,
                "transfer":"MANUAL_WINSCP_ONLY",
                "offhost_saved":False,"nbot_service_started":False}
    except Exception:
        try:tmp.unlink(missing_ok=True)
        except OSError:pass
        raise

def main():
    if len(sys.argv)!=1:
        print("Usage: ~/nbot-backup (no arguments required)",file=sys.stderr)
        return 2
    try:
        result=create_backup()
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0
    except (BackupHold,OSError,sqlite3.Error,tarfile.TarError) as exc:
        print("NBOT BACKUP HOLD — "+str(exc),file=sys.stderr)
        print("No verified successful backup was claimed. NBOT was not started.",
              file=sys.stderr)
        return 3

if __name__=="__main__":
    raise SystemExit(main())
