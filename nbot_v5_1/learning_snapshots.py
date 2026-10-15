"""G7 append-only finite laboratory Learning snapshot manifests.

Stores ONLY row checksums/status counts and NO secret/source raw data.
No original-grade evidence, training authority or automatic promotions.
Writes are explicit; normal imports perform zero I/O.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat
from .learning_contract import LearningDataset,LearningHold,canonical,verified_learning_count
from .learning_science import LearningReview

VERSION="NBOT_V5_1_G7_LAB_SNAPSHOT_V1"
MAX_BYTES=4*1024*1024


class SnapshotHold(ValueError):pass


def _safe(root):
    if (not isinstance(root,Path) or not root.is_absolute() or root.is_symlink()
         or not root.is_dir() or root.stat().st_uid!=os.getuid()
         or root.stat().st_mode&0o077):
        raise SnapshotHold("G7_PRIVATE_SNAPSHOT_ROOT_REQUIRED")


def _read(file,limit=MAX_BYTES):
    fd=os.open(file,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        s=os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid()
            or s.st_nlink!=1 or s.st_mode&0o077 or s.st_size>limit):
            raise SnapshotHold("G7_SNAPSHOT_FILE_PERMISSIONS_OR_QUOTA")
        buf=bytearray()
        while len(buf)<=limit:
            part=os.read(fd,min(65536,limit+1-len(buf)))
            if not part:break
            buf.extend(part)
        if len(buf)!=s.st_size or len(buf)>limit:
            raise SnapshotHold("G7_SNAPSHOT_SHORT_OR_OVERSIZE_READ")
        return bytes(buf)
    finally:os.close(fd)


def _sha(b):return hashlib.sha256(b).hexdigest()


def save_lab_snapshot(root:Path,dataset:LearningDataset,
                      review:LearningReview,*,max_bytes:int=MAX_BYTES)->dict:
    _safe(root)
    if (type(dataset) is not LearningDataset or type(review) is not LearningReview
        or dataset.dataset_sha256!=review.dataset_sha256 or
        verified_learning_count(dataset)!=0 or review.quality.scientifically_qualified!=0
        or review.model_status!="NO_MODEL" or review.financial_authority!="NONE"
        or type(max_bytes) is not int or not 1024<=max_bytes<=MAX_BYTES):
        raise SnapshotHold("G7_LAB_SNAPSHOT_NOT_VALID_OR_PROMOTION")
    rowhash=[x.row_sha256 for x in dataset.rows]
    manifest={"v":VERSION,"dataset":dataset.dataset_sha256,
       "cutoff_ms":dataset.cutoff_ms,"row_hashes":rowhash,
       "review":{"total":review.quality.total,
           "held":review.quality.held,"pending":review.quality.pending,
           "censored":review.quality.censored,
           "synthetic":review.quality.synthetic_modeled,
           "independent_blocks":review.quality.effective_independent_blocks},
       "source_grade":"OFFLINE_LAB_NONSCIENTIFIC",
       "scientifically_qualified":0,"model_status":"NO_MODEL",
       "financial_authority":"NONE"}
    raw=canonical(manifest)
    if len(raw)>max_bytes:
        raise SnapshotHold("G7_SNAPSHOT_EXCEEDS_QUOTA")
    name="lab-"+_sha(raw)[:32]+".json"
    if any(x.is_symlink() for x in root.iterdir()):
        raise SnapshotHold("G7_SNAPSHOT_ROOT_SYMLINK_CONTENT")
    p=root/name
    if p.exists():
        if _read(p)!=raw:
            raise SnapshotHold("G7_SNAPSHOT_SAME_ID_DIFFERENT_CONTENT")
        return {"status":"IDEMPOTENT_VERIFIED","name":name,"sha256":_sha(raw),
                "bytes":len(raw)}
    used=sum(x.stat().st_size for x in root.iterdir() if x.is_file())
    if used+len(raw)>max_bytes:
        raise SnapshotHold("G7_SNAPSHOT_TOTAL_FINITE_QUOTA")
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
               getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        remaining=memoryview(raw)
        while remaining:
            n=os.write(fd,remaining)
            if n<=0:raise OSError("G7_SNAPSHOT_SHORT_WRITE")
            remaining=remaining[n:]
        os.fsync(fd)
    finally:os.close(fd)
    dfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(dfd)
    finally:os.close(dfd)
    return {"status":"SEALED_LAB_ONLY","name":name,"sha256":_sha(raw),
            "bytes":len(raw)}


def verify_lab_snapshot(root:Path,name:str,expected_sha256:str)->dict:
    _safe(root)
    if (type(name) is not str or not name.startswith("lab-")
        or len(name)!=41 or not name.endswith(".json") or
        type(expected_sha256) is not str or len(expected_sha256)!=64 or
        name[4:36]!=expected_sha256[:32]):
        raise SnapshotHold("G7_SNAPSHOT_NAME_OR_HASH")
    raw=_read(root/name)
    if _sha(raw)!=expected_sha256:
        raise SnapshotHold("G7_SNAPSHOT_DIGEST_CHANGED")
    try:meta=json.loads(raw)
    except (ValueError,UnicodeError) as ex:
        raise SnapshotHold("G7_SNAPSHOT_JSON_INVALID") from ex
    if (canonical(meta)!=raw or type(meta) is not dict
         or meta.get("v")!=VERSION or meta.get("model_status")!="NO_MODEL"
         or meta.get("financial_authority")!="NONE"
         or meta.get("scientifically_qualified")!=0
         or meta.get("source_grade")!="OFFLINE_LAB_NONSCIENTIFIC"
         or type(meta.get("row_hashes")) is not list
         or any(type(x) is not str or len(x)!=64 for x in meta["row_hashes"])):
        raise SnapshotHold("G7_SNAPSHOT_FALSE_SCIENCE_OR_INVALID")
    return {"status":"VERIFIED_LAB_NO_MODEL","sha256":expected_sha256,
            "rows":len(meta["row_hashes"]),"bytes":len(raw)}
