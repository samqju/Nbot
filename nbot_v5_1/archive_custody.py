"""G6 finite sealed G4 source snapshot with SHA, no silent deletion.

The archive can be transported out-of-band to an independent VPS and
rechecked using verify_archive(...). A local snapshot test is NOT proof
that any remote transport, power-loss recovery or independent source
origin has occurred.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import re
import stat

from .deep_segments import DeepSegmentRecorder,DeepSegmentHold

VERSION="NBOT_V5_1_G6_ARCHIVE_V1"
_FILES=re.compile(r"segment-[0-9]{8}\.(gz|json)\Z")
MAX_TOTAL=256*1024*1024


class ArchiveHold(ValueError):pass


def _sha(b):return hashlib.sha256(b).hexdigest()
def _canon(o):return json.dumps(o,sort_keys=True,separators=(",",":"),
                            ensure_ascii=True,allow_nan=False).encode()


def _safe_dir(p):
    if (not isinstance(p,Path) or not p.is_absolute() or
         p.is_symlink() or not p.is_dir()):
        raise ArchiveHold("G6_ARCHIVE_DIRECTORY_MISSING_OR_SYMLINK")
    s=p.stat()
    if s.st_uid!=os.getuid() or s.st_mode&0o077:
        raise ArchiveHold("G6_ARCHIVE_DIR_OWNER_PERMISSIONS")


def _read_file(p,limit):
    fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1
                or st.st_uid!=os.getuid() or st.st_mode&0o077
                or st.st_size>limit):
            raise ArchiveHold("G6_ARCHIVE_FILE_UNSAFE_OR_OVER_LIMIT")
        buf=bytearray()
        while len(buf)<=limit:
            piece=os.read(fd,min(65536,limit+1-len(buf)))
            if not piece:break
            buf.extend(piece)
        if len(buf)!=st.st_size or len(buf)>limit:
            raise ArchiveHold("G6_ARCHIVE_BAD_FILE_READ")
        return bytes(buf)
    finally:os.close(fd)


def _write_once(p,body):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        view=memoryview(body)
        while view:
            written=os.write(fd,view)
            if written<=0:raise OSError("G6_ARCHIVE_SHORT_WRITE")
            view=view[written:]
        os.fsync(fd)
    finally:os.close(fd)
    dirfd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(dirfd)
    finally:os.close(dirfd)


def seal_archive(*,source:Path,destination:Path,
         symbols:tuple[str,...],quota:int=MAX_TOTAL)->dict:
    _safe_dir(source);_safe_dir(destination)
    if (type(symbols) is not tuple or not 1<=len(symbols)<=20 or
           "BTCUSDT" not in symbols or len(symbols)!=len(set(symbols)) or
           type(quota) is not int or not 1024*1024<=quota<=MAX_TOTAL or
           source.resolve()==destination.resolve() or
           list(destination.iterdir())):
        raise ArchiveHold("G6_SEAL_CONFIG_OR_NOT_EMPTY")
    reader=DeepSegmentRecorder(source,symbols=symbols,quota_bytes=MAX_TOTAL)
    try:
        frames,head,n=reader.replay()
    except (ValueError,DeepSegmentHold) as e:
        raise ArchiveHold("G6_SOURCE_SEGMENTS_NOT_VERIFIED") from e
    names=sorted(x.name for x in source.iterdir())
    if n<1 or len(names)!=2*n or any(not _FILES.fullmatch(k) for k in names):
        raise ArchiveHold("G6_SOURCE_SEGMENTS_INCOMPLETE")
    bodies={}
    current=0
    for name in names:
        p=source/name
        body=_read_file(p,2*1024*1024)
        current+=len(body)
        if current>quota:
            raise ArchiveHold("G6_ARCHIVE_QUOTA_EXHAUSTED")
        bodies[name]=body
    manifest={"schema":VERSION,"symbols":list(symbols),
        "segments":n,"frames":len(frames),"last_source_sha256":head,
        "files":{name:{"sha256":_sha(body),"size":len(body)}
                  for name,body in bodies.items()},
        "grade":"COPY_OF_PUBLIC_SOURCE_NOT_INDEPENDENT_EXCHANGE_SIGNED",
        "financial_authority":"NONE"}
    payload=_canon(manifest)
    if current+len(payload)>quota:
        raise ArchiveHold("G6_ARCHIVE_MANIFEST_QUOTA")
    # No silent cleanup after partial copy; next attempt requires separate
    # inspection or fresh approved destination, not overwrite.
    for name,body in bodies.items():
        _write_once(destination/name,body)
    _write_once(destination/"custody.json",payload)
    return {"manifest_sha256":_sha(payload),"segment_count":n,
            "frame_count":len(frames),"bytes":current+len(payload),
            "status":"SEALED_LOCAL_COPY_NOT_OFFHOST_ATTESTED"}


def verify_archive(*,root:Path,symbols:tuple[str,...],quota:int=MAX_TOTAL)->dict:
    _safe_dir(root)
    if not 1024*1024<=quota<=MAX_TOTAL:
        raise ArchiveHold("G6_ARCHIVE_QUOTA")
    p=root/"custody.json"
    payload=_read_file(p,1024*1024)
    try:
        meta=json.loads(payload)
    except (ValueError,UnicodeError) as e:
        raise ArchiveHold("G6_ARCHIVE_META_CORRUPT") from e
    if (not isinstance(meta,dict) or _canon(meta)!=payload
            or meta.get("schema")!=VERSION
            or meta.get("symbols")!=list(symbols)
            or meta.get("financial_authority")!="NONE"
            or meta.get("grade")!="COPY_OF_PUBLIC_SOURCE_NOT_INDEPENDENT_EXCHANGE_SIGNED"):
        raise ArchiveHold("G6_ARCHIVE_META_INVALID")
    files=meta.get("files")
    if not isinstance(files,dict) or not files:
        raise ArchiveHold("G6_ARCHIVE_FILE_LIST_INVALID")
    actual={x.name for x in root.iterdir()}
    if actual!={"custody.json",*files}:
        raise ArchiveHold("G6_ARCHIVE_UNEXPECTED_FILE_OR_MISSING")
    total=len(payload)
    for name,checks in files.items():
        if not _FILES.fullmatch(name) or type(checks) is not dict:
            raise ArchiveHold("G6_ARCHIVE_FILE_NOT_RECOGNIZED")
        raw=_read_file(root/name,2*1024*1024)
        total+=len(raw)
        if total>quota or checks!={"sha256":_sha(raw),"size":len(raw)}:
            raise ArchiveHold("G6_ARCHIVE_FILE_HASH_OR_QUOTA")
    # Original G4 replay cannot traverse a dir containing custody.json.
    # Independently verify exact raw bytes/segments in owner-private temp
    # checkout without silently permitting extra media/file names.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="nbot-g6-verify-") as d:
        target=Path(d)
        for name in sorted(files):
            _write_once(target/name,_read_file(root/name,2*1024*1024))
        reader=DeepSegmentRecorder(target,symbols=symbols,quota_bytes=MAX_TOTAL)
        try:frames,head,n=reader.replay()
        except (ValueError,DeepSegmentHold) as e:
            raise ArchiveHold("G6_ARCHIVE_INDEPENDENT_REPLAY_FAILED") from e
    if (head!=meta.get("last_source_sha256") or
            n!=meta.get("segments") or len(frames)!=meta.get("frames")):
        raise ArchiveHold("G6_ARCHIVE_SEGMENT_HEAD_OR_FRAME_COUNT_MISMATCH")
    return {"status":"VERIFIED_COPY_NOT_PROOF_OF_OFFHOST_OR_AUTHENTICITY",
            "manifest_sha256":_sha(payload),"segments":n,"frames":len(frames),
            "bytes":total}
