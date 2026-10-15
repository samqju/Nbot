"""G5 finite crash-conscious append-only event journal, explicit I/O only.

Only a TEST laboratory's virtual research lifecycle is persisted. NO orders,
credentials, economic scoring or claims of original source custody.
On unclean restart ACTIVE paths are conservatively held, never backfilled.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import threading

VERSION="NBOT_V5_1_G5_JOURNAL_V1"
ZERO="0"*64
LIMIT=16*1024*1024
MAX_LINE=65536
OPS=frozenset({"ADMIT","TRAIL_CHECKPOINT","TERMINAL","PATH_HOLD","REVIEW","CENSOR","SOURCE_EPOCH_HOLD"})
_MUTEX=threading.RLock()

class JournalHold(ValueError):pass


def canon(row):
    return json.dumps(row,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")


class ResearchJournal:
    def __init__(self,path:Path,*,limit_bytes:int=LIMIT):
        if (not isinstance(path,Path) or not path.is_absolute() or path.is_symlink()
                or type(limit_bytes) is not int or not 1024*1024<=limit_bytes<=64*1024*1024):
            raise ValueError("G5_JOURNAL_CONFIG")
        self.path=path
        self.limit=limit_bytes

    def _open(self):
        parent=self.path.parent
        if (not parent.is_dir() or parent.is_symlink()
                or parent.stat().st_uid!=os.getuid()
                or parent.stat().st_mode&0o077):
            raise JournalHold("G5_PARENT_DIR_UNSAFE")
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_APPEND|
                   getattr(os,"O_NOFOLLOW",0),0o600)
        s=os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_nlink!=1
                or s.st_uid!=os.getuid() or s.st_mode&0o077):
            os.close(fd);raise JournalHold("G5_JOURNAL_FILE_UNSAFE")
        return fd

    def _read_fd(self,fd):
        s=os.fstat(fd)
        if s.st_size>self.limit:
            raise JournalHold("G5_JOURNAL_QUOTA")
        os.lseek(fd,0,os.SEEK_SET)
        data=bytearray()
        while len(data)<=self.limit:
            part=os.read(fd,min(65536,self.limit+1-len(data)))
            if not part:break
            data.extend(part)
        if len(data)!=s.st_size or len(data)>self.limit:
            raise JournalHold("G5_JOURNAL_SHORT_READ")
        rows=[];head=ZERO
        if data and not data.endswith(b"\n"):
            raise JournalHold("G5_JOURNAL_TORN_LINE")
        for raw in data.splitlines():
            if not raw or len(raw)>MAX_LINE:
                raise JournalHold("G5_JOURNAL_LINE_INVALID")
            try:
                value=json.loads(raw,object_pairs_hook=self._no_duplicate,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                           JournalHold("G5_NONFINITE_JSON")))
            except (ValueError,UnicodeError,TypeError) as exc:
                if isinstance(exc,JournalHold):raise
                raise JournalHold("G5_JOURNAL_JSON_INVALID") from exc
            if (type(value) is not dict or canon(value)!=raw
                    or set(value)!={"v","seq","previous","action","at_ms","payload","sha"}
                    or value["v"]!=VERSION or value["seq"]!=len(rows)+1
                    or value["previous"]!=head or value["action"] not in OPS
                    or type(value["at_ms"]) is not int or value["at_ms"]<0
                    or type(value["payload"]) is not dict):
                raise JournalHold("G5_JOURNAL_CHAIN_OR_SCHEMA_INVALID")
            copy={k:v for k,v in value.items() if k!="sha"}
            if value["sha"]!=hashlib.sha256(canon(copy)).hexdigest():
                raise JournalHold("G5_JOURNAL_DIGEST_INVALID")
            head=value["sha"];rows.append(value)
        return tuple(rows),head,len(data)

    @staticmethod
    def _no_duplicate(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise JournalHold("G5_JOURNAL_DUPLICATE_FIELD")
            d[k]=v
        return d

    def replay(self):
        with _MUTEX:
            fd=self._open()
            try:
                fcntl.flock(fd,fcntl.LOCK_EX)
                rows,head,_=self._read_fd(fd)
                return rows,head
            finally:os.close(fd)

    def append(self,action:str,at_ms:int,payload:dict,*,expected_head:str):
        if (action not in OPS or type(at_ms) is not int or at_ms<0
                or type(payload) is not dict or type(expected_head) is not str):
            raise JournalHold("G5_JOURNAL_APPEND_ARGUMENTS")
        with _MUTEX:
            fd=self._open()
            try:
                fcntl.flock(fd,fcntl.LOCK_EX)
                rows,head,used=self._read_fd(fd)
                if expected_head!=head:
                    raise JournalHold("G5_JOURNAL_CONCURRENT_HEAD_CONFLICT")
                record={"v":VERSION,"seq":len(rows)+1,"previous":head,
                        "action":action,"at_ms":at_ms,"payload":payload}
                record["sha"]=hashlib.sha256(canon(record)).hexdigest()
                body=canon(record)+b"\n"
                if len(body)>MAX_LINE or used+len(body)>self.limit:
                    raise JournalHold("G5_JOURNAL_QUOTA")
                os.lseek(fd,0,os.SEEK_END)
                data=memoryview(body)
                while data:
                    written=os.write(fd,data)
                    if written<=0:raise OSError("G5_JOURNAL_PARTIAL_WRITE")
                    data=data[written:]
                os.fsync(fd)
                dfd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(dfd)
                finally:os.close(dfd)
                return record["sha"]
            finally:os.close(fd)
