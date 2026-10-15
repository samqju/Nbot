"""G8 immutable lab-only model card snapshot and independent re-verification.

No pickle, eval, dynamic loading, executable model, account credentials,
network/market import, Champion token or paper authorization. Explicit
file I/O only; read-only verifier never upgrades grade/authority.
"""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from .learning_contract import LearningDataset,canonical
from .training_lab import (
    LabProtocol,FrozenLabModel,LabBacktest,TrainingHold,verify_model)

SCHEMA="NBOT_V5_1_G8_LAB_FROZEN_CARD_V1"
MAX_FILE=1*1024*1024
MAX_TOTAL=4*1024*1024
_PATTERN=re.compile(r"g8-lab-[a-f0-9]{32}\.json\Z")


class FreezeHold(ValueError):pass


def _dir(path):
    if (not isinstance(path,Path) or not path.is_absolute() or
        path.is_symlink() or not path.is_dir()):
        raise FreezeHold("G8_PRIVATE_ARTIFACT_DIR_REQUIRED")
    s=path.stat()
    if s.st_uid!=os.getuid() or s.st_mode&0o077:
        raise FreezeHold("G8_ARTIFACT_OWNER_OR_PERMISSIONS")


def _read(path):
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        s=os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid()
            or s.st_nlink!=1 or s.st_mode&0o077 or
            s.st_size>MAX_FILE or s.st_size<10):
            raise FreezeHold("G8_ARTIFACT_FILE_UNSAFE")
        buf=bytearray()
        while len(buf)<=MAX_FILE:
            chunk=os.read(fd,min(65536,MAX_FILE+1-len(buf)))
            if not chunk:break
            buf.extend(chunk)
        if len(buf)!=s.st_size or len(buf)>MAX_FILE:
            raise FreezeHold("G8_ARTIFACT_PARTIAL_OR_QUOTA")
        return bytes(buf)
    finally:os.close(fd)


def _sha(raw):return sha256(raw).hexdigest()


def _card(model,backtest):
    return {"schema":SCHEMA,"model":asdict(model),"backtest":asdict(backtest),
        "kind":"SYNTHETIC_OFFLINE_LAB_ONLY",
        "model_authority":"NONE","paper_authority":"NONE",
        "real_authority":"NONE","qualified_original":0}


def seal_lab_model(root:Path,model:FrozenLabModel,
                    backtest:LabBacktest,dataset:LearningDataset)->dict:
    _dir(root)
    verify_model(model,dataset)
    if (type(backtest) is not LabBacktest or
        backtest.model_sha256!=model.model_sha256 or
        backtest.dataset_sha256!=dataset.dataset_sha256 or
        backtest.protocol_sha256!=model.policy_sha256 or
        backtest.status!="LAB_ONLY_HOLD" or
        backtest.release_authority!="NONE" or
        backtest.scientific_advantage_proved or
        backtest.qualified_original!=0):
        raise FreezeHold("G8_UNQUALIFIED_BACKTEST_OR_FALSE_RELEASE")
    raw=canonical(_card(model,backtest))
    if len(raw)>MAX_FILE:
        raise FreezeHold("G8_CARD_TOO_LARGE")
    name="g8-lab-"+_sha(raw)[:32]+".json"
    filename=root/name
    if any(p.is_symlink() for p in root.iterdir()):
        raise FreezeHold("G8_ROOT_CONTAINS_SYMLINK")
    if filename.exists():
        if _read(filename)!=raw:
            raise FreezeHold("G8_IMMUTABLE_ARTIFACT_CONFLICT")
        return {"status":"IDEMPOTENT_VERIFIED_LAB_ONLY",
                "sha256":_sha(raw),"name":name,"bytes":len(raw)}
    if sum(p.stat().st_size for p in root.iterdir() if p.is_file())+len(raw)>MAX_TOTAL:
        raise FreezeHold("G8_CARD_FINITE_TOTAL_QUOTA")
    fd=os.open(filename,os.O_CREAT|os.O_EXCL|os.O_WRONLY|
               getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        left=memoryview(raw)
        while left:
            n=os.write(fd,left)
            if n<=0:raise OSError("G8_SHORT_ARTIFACT_WRITE")
            left=left[n:]
        os.fsync(fd)
    finally:os.close(fd)
    dfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(dfd)
    finally:os.close(dfd)
    return {"status":"FROZEN_SYNTHETIC_LAB_ONLY",
            "sha256":_sha(raw),"name":name,"bytes":len(raw)}


def verify_lab_model(root:Path,name:str,expected_sha256:str,
                     dataset:LearningDataset|None=None)->dict:
    _dir(root)
    if (type(name) is not str or not _PATTERN.fullmatch(name) or
        type(expected_sha256) is not str or len(expected_sha256)!=64 or
        name[7:39]!=expected_sha256[:32]):
        raise FreezeHold("G8_CARD_PATH_OR_HASH")
    raw=_read(root/name)
    if _sha(raw)!=expected_sha256:
        raise FreezeHold("G8_ARTIFACT_CHANGED")
    try:meta=json.loads(raw)
    except (ValueError,UnicodeError) as ex:
        raise FreezeHold("G8_JSON_CORRUPTION") from ex
    if (type(meta) is not dict or canonical(meta)!=raw or
        set(meta)!={"schema","model","backtest","kind","model_authority",
                     "paper_authority","real_authority","qualified_original"} or
        meta["schema"]!=SCHEMA or meta["kind"]!="SYNTHETIC_OFFLINE_LAB_ONLY"
        or any(meta.get(k)!="NONE" for k in
               ("model_authority","paper_authority","real_authority"))
        or meta["qualified_original"]!=0):
        raise FreezeHold("G8_SNAPSHOT_FALSE_SCIENCE")
    try:
        obj=meta["model"]; protocol=LabProtocol(**obj["policy"])
        m=FrozenLabModel(**{**obj,"policy":protocol,
                           "estimates":tuple(tuple(x) for x in obj["estimates"])})
        verify_model(m,dataset)
        report=LabBacktest(**meta["backtest"])
        if (report.model_sha256!=m.model_sha256 or
            report.dataset_sha256!=m.dataset_sha256 or
            report.protocol_sha256!=m.policy_sha256 or
            report.release_authority!="NONE" or
            report.qualified_original!=0 or report.scientific_advantage_proved
            or report.status!="LAB_ONLY_HOLD"):
            raise FreezeHold("G8_ARTIFACT_AUDIT_MISMATCH")
    except (TrainingHold,ValueError,KeyError,TypeError) as ex:
        raise FreezeHold("G8_ARTIFACT_REPLAY_INVALID") from ex
    return {"status":"VERIFIED_IMMUTABLE_LAB_ONLY",
            "sha256":expected_sha256,
            "model_sha256":m.model_sha256,
            "bytes":len(raw),"qualified_original":0,
            "orders_allowed":False}
