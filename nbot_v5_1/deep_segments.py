"""G4 bounded no-SQLite original public WSS byte segment custody.

Not exchange-signed, not independently continuous fill-path evidence.
Unflushed RAM is untrusted across restarts, and a dirty/incomplete segment
HOLDs the entire replay. Explicit write only, owner-private, finite quota.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zlib

from .deep_source import verify_frame, DeepSourceHold

SCHEMA="NBOT_V5_1_G4_SEGMENT_V1"
ZERO="0"*64
MAX_BYTES=1024*1024
MAX_FRAME=65536
_ALLOWED=re.compile(r"segment-([0-9]{8})\.(json|gz)\Z")

class DeepSegmentHold(ValueError):
    pass

def _canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")
def _sha(raw):return hashlib.sha256(raw).hexdigest()

def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise DeepSegmentHold("G4_REPLAY_JSON_DUPLICATE")
        out[k]=v
    return out

class DeepSegmentRecorder:
    """Durably publish only complete gzip+metadata two-file segments.

    All authenticated source/network assumptions are supplied by an
    independently audited WSS receiver. This class verifies raw syntax,
    cursors and byte SHA, but cannot sign exchange-origin traffic.
    """
    def __init__(self,root:Path,*,symbols:tuple[str,...],quota_bytes:int=64*1024*1024):
        if (not isinstance(root, Path) or not root.is_absolute() or root.is_symlink()
                or type(symbols) is not tuple or not 1<=len(symbols)<=20
                or len(symbols)!=len(set(symbols)) or "BTCUSDT" not in symbols
                or type(quota_bytes) is not int or not 1024*1024<=quota_bytes<=1024*1024*1024):
            raise ValueError("G4_SEGMENT_CONFIG_INVALID")
        self.root=root;self.symbols=symbols;self.quota_bytes=quota_bytes
        self.queue=[];self.queued_bytes=0
        self.cursors={}
        self.epoch_holds=set()
        self.last_receipt=ZERO;self.next_id=1

    def _guard(self):
        if not self.root.is_dir() or self.root.is_symlink():
            raise DeepSegmentHold("G4_SEGMENT_ROOT_MISSING")
        mode=self.root.stat()
        if mode.st_uid!=os.getuid() or mode.st_mode&0o077:
            raise DeepSegmentHold("G4_SEGMENT_ROOT_UNSAFE")

    def _scan(self):
        self._guard()
        pairs={}
        for p in self.root.iterdir():
            if not _ALLOWED.fullmatch(p.name):
                raise DeepSegmentHold("G4_SEGMENT_UNKNOWN_OR_ORPHAN")
            st=p.lstat()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid()
                    or st.st_nlink!=1 or st.st_mode&0o077):
                raise DeepSegmentHold("G4_SEGMENT_FILE_UNSAFE")
            pairs[p.name]=st.st_size
        ids=sorted({int(p.split("-")[1].split(".")[0]) for p in pairs})
        if ids != list(range(1,len(ids)+1)):
            raise DeepSegmentHold("G4_SEGMENT_NUMBER_GAP")
        for n in ids:
            if f"segment-{n:08d}.gz" not in pairs or f"segment-{n:08d}.json" not in pairs:
                raise DeepSegmentHold("G4_SEGMENT_PARTIAL_PUBLISH")
        if sum(pairs.values())>self.quota_bytes:
            raise DeepSegmentHold("G4_SEGMENT_DISK_QUOTA")
        return pairs,ids

    def _read(self,p:Path,max_bytes:int)->bytes:
        fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        try:
            s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid() or s.st_mode&0o077 or s.st_size>max_bytes:
                raise DeepSegmentHold("G4_SEGMENT_FILE_TOO_BIG_OR_UNSAFE")
            chunks=[]
            n=0
            while n<=max_bytes:
                b=os.read(fd,min(65536,max_bytes+1-n))
                if not b:break
                n+=len(b);chunks.append(b)
            if n!=s.st_size or n>max_bytes:
                raise DeepSegmentHold("G4_SEGMENT_SHORT_OR_OVERSIZE_READ")
            return b"".join(chunks)
        finally:os.close(fd)

    def replay(self):
        files,ids=self._scan()
        old=ZERO
        output=[]
        replay_cursors={}
        for idx in ids:
            stem=f"segment-{idx:08d}"
            packed=self._read(self.root/(stem+".gz"),MAX_BYTES)
            meta=self._read(self.root/(stem+".json"),16384)
            try:
                record=json.loads(meta,object_pairs_hook=_unique)
            except (ValueError,UnicodeError,TypeError) as exc:
                raise DeepSegmentHold("G4_SEGMENT_META_CORRUPT") from exc
            if (_canon(record)!=meta or record.get("schema")!=SCHEMA
                    or record.get("id")!=idx or record.get("previous")!=old
                    or record.get("compressed_sha256")!=_sha(packed)):
                raise DeepSegmentHold("G4_SEGMENT_META_OR_CHAIN")
            obj=zlib.decompressobj(16+zlib.MAX_WBITS)
            try:
                decoded=obj.decompress(packed,MAX_BYTES+1)
            except zlib.error as exc:
                raise DeepSegmentHold("G4_SEGMENT_ZLIB_INVALID") from exc
            if not obj.eof or obj.unused_data or len(decoded)>MAX_BYTES or record.get("body_sha256")!=_sha(decoded):
                raise DeepSegmentHold("G4_SEGMENT_BODY_CORRUPT")
            try:
                payload=json.loads(decoded,object_pairs_hook=_unique)
            except (ValueError,UnicodeError) as exc:
                raise DeepSegmentHold("G4_SEGMENT_ROWS_INVALID") from exc
            if _canon(payload)!=decoded or type(payload)!=list or not 1<=len(payload)<=5000:
                raise DeepSegmentHold("G4_SEGMENT_ROWS_INVALID")
            if record.get("rows")!=len(payload):
                raise DeepSegmentHold("G4_SEGMENT_COUNT_MISMATCH")
            for item in payload:
                if type(item)!=dict or set(item)!={"kind","raw_b64","raw_sha256","received_at_ms","epoch"}:
                    raise DeepSegmentHold("G4_SEGMENT_ROW_FIELDS")
                try:raw=base64.b64decode(item["raw_b64"],validate=True)
                except (ValueError,TypeError) as exc:
                    raise DeepSegmentHold("G4_SEGMENT_BASE64_CORRUPT") from exc
                if len(raw)>MAX_FRAME or _sha(raw)!=item["raw_sha256"]:
                    raise DeepSegmentHold("G4_SEGMENT_FRAME_HASH")
                ev=verify_frame(kind=item["kind"],raw=raw,received_at_ms=item["received_at_ms"],
                                source_epoch=item["epoch"],selected_symbols=self.symbols)
                if ev.state=="HOLD":
                    raise DeepSegmentHold("G4_SEGMENT_FRAME_INVALID")
                if ev.kind=="TRADE":
                    key=(ev.kind,ev.symbol,ev.epoch)
                    prior=replay_cursors.get(key,(None,None))
                    check=verify_frame(kind=item["kind"],raw=raw,
                         received_at_ms=item["received_at_ms"],
                         source_epoch=item["epoch"],selected_symbols=self.symbols,
                         prior_agg_id=prior[0],prior_last_trade_id=prior[1])
                    if check.state=="HOLD":
                        raise DeepSegmentHold("G4_SEGMENT_TRADE_CONTINUITY")
                    replay_cursors[key]=(ev.agg_id,ev.last_trade_id)
                output.append((ev,raw))
            old=_sha(meta)
        return tuple(output),old,len(ids)

    def attach(self):
        """Recover committed files and start a NEW untrusted source epoch.

        Do not automatically resume authenticated stream continuity. Current
        owner must reconnect and warm all routes before new trusted evidence.
        """
        frames,old,num=self.replay()
        self.next_id=num+1;self.last_receipt=old
        self.cursors={}
        self.epoch_holds=set(self.symbols)
        return len(frames)

    def append(self,*,kind:str,raw:bytes,received_at_ms:int,epoch:int):
        # Never fill in source continuity from a REST candle or older segment.
        # The route carries interleaved coins: each coin has its OWN trade IDs.
        # Verify basic raw fields before accessing its frozen source cursor.
        initial=verify_frame(kind=kind,raw=raw,received_at_ms=received_at_ms,
              source_epoch=epoch,selected_symbols=self.symbols)
        if initial.state=="HOLD":
            self.epoch_holds.add(initial.symbol)
            raise DeepSegmentHold(initial.reason or "G4_SEGMENT_SOURCE_HOLD")
        oldid,lastid=self.cursors.get((kind,initial.symbol,epoch), (None,None))
        ev=verify_frame(kind=kind,raw=raw,received_at_ms=received_at_ms,
              source_epoch=epoch,selected_symbols=self.symbols,
              prior_agg_id=oldid,prior_last_trade_id=lastid)
        if ev.state=="HOLD":
            self.epoch_holds.add(ev.symbol)
            raise DeepSegmentHold(ev.reason or "G4_SEGMENT_SOURCE_HOLD")
        if len(raw)>MAX_FRAME or self.queued_bytes+len(raw)>MAX_BYTES//2:
            raise DeepSegmentHold("G4_SEGMENT_MEMORY_FULL_FLUSH_FIRST")
        self.queue.append({"kind":kind,"raw_b64":base64.b64encode(raw).decode(),
           "raw_sha256":ev.sha256,"received_at_ms":received_at_ms,"epoch":epoch})
        self.queued_bytes+=len(raw)
        if kind=="TRADE":
            self.cursors[(kind,ev.symbol,epoch)]=(ev.agg_id,ev.last_trade_id)
        return ev

    def flush(self):
        if not self.queue:return None
        files,ids=self._scan()
        if ids and ids[-1]>=self.next_id:
            raise DeepSegmentHold("G4_SEGMENT_RESTART_NOT_ATTACHED")
        body=_canon(self.queue)
        if len(body)>MAX_BYTES:
            raise DeepSegmentHold("G4_SEGMENT_BODY_LIMIT")
        packed=gzip.compress(body,compresslevel=6,mtime=0)
        stem=f"segment-{self.next_id:08d}"
        meta=_canon({"schema":SCHEMA,"id":self.next_id,"previous":self.last_receipt,
               "body_sha256":_sha(body),"compressed_sha256":_sha(packed),
               "rows":len(self.queue)})
        if sum(files.values())+len(meta)+len(packed)>self.quota_bytes:
            raise DeepSegmentHold("G4_SEGMENT_DISK_FULL_NO_DELETE")
        self._guard()
        # Parent fsync after each file, and orphan rejection on partial write.
        for ext,payload in ((".gz",packed),(".json",meta)):
            fd=os.open(self.root/(stem+ext),os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                       getattr(os,"O_NOFOLLOW",0),0o600)
            try:
                buf=memoryview(payload)
                while buf:
                    n=os.write(fd,buf)
                    if n<=0:raise OSError("G4_SEGMENT_PARTIAL_WRITE")
                    buf=buf[n:]
                os.fsync(fd)
            finally:os.close(fd)
            dirfd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(dirfd)
            finally:os.close(dirfd)
        self.last_receipt=_sha(meta);self.next_id+=1
        self.queue.clear();self.queued_bytes=0
        return stem
