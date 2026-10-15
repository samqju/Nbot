"""CS-00 durable, source-only G2/G3 receipts with a checkpointed owner backup boundary.

No exchange calls or service startup. All writers share the private state
flock with the owner one-command backup to avoid interleaved snapshots.
A committed boundary is a final SHA-linked receipt of its observation and
exploration files. An interrupted boundary has no commit -> prebackup HOLD.
"""
from __future__ import annotations
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import os
import re
import stat
from contextlib import nullcontext

from .observation_store import CompactObservationStore
from .exploration_store import ExplorationStore

SCHEMA="NBOT_V5_1_CS00_STATE_CHECKPOINT_V1"
_NAME=re.compile(r"checkpoint_[0-9]{16}\.json\Z")

class StateCheckpointHold(ValueError):pass

@contextmanager
def state_gate(root:Path):
    if (not isinstance(root,Path) or not root.is_absolute() or
            not root.is_dir() or root.is_symlink()
            or root.stat().st_mode&0o077
            or root.stat().st_uid!=os.getuid()):
        raise StateCheckpointHold("CS00_STATE_ROOT_NOT_OWNER_PRIVATE")
    gate=root.parent/".nbot-v5.1-state.lock"
    if gate.is_symlink():
        raise StateCheckpointHold("CS00_STATE_LOCK_SYMLINK")
    fd=os.open(gate,os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        st=os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid()
                or st.st_nlink!=1 or st.st_mode&0o077):
            raise StateCheckpointHold("CS00_STATE_LOCK_UNSAFE")
        fcntl.flock(fd,fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

def _safe_folder(path):
    if (not path.is_dir() or path.is_symlink() or
            path.stat().st_uid!=os.getuid() or
            path.stat().st_mode&0o077):
        raise StateCheckpointHold("CS00_STATE_FOLDER_UNSAFE")

def _bytes(path):
    if path.is_symlink():
        raise StateCheckpointHold("CS00_STATE_RECEIPT_SYMLINK")
    data=path.read_bytes()
    if not 0<len(data)<=2*1024*1024:
        raise StateCheckpointHold("CS00_STATE_RECEIPT_BOUNDS")
    return data

def _canon(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),
                      allow_nan=False).encode("ascii")

class SourceOnlyStateWriter:
    """Explicit deployment-prepared dirs; never silently makes random roots."""
    def __init__(self,root:Path):
        _safe_folder(root)
        self.root=root
        for k in ("observations","exploration","journals","evidence"):
            _safe_folder(root/k)
        self.g2=CompactObservationStore(root/"observations",
                                        max_bytes=512*1024*1024)
        self.g3=ExplorationStore(root/"exploration",
                                 budget_bytes=512*1024*1024)

    def record_boundary(self,book,snapshot,batch):
        if (snapshot.event_open_ms!=batch.event_open_ms or
                snapshot.universe_sha!=batch.universe_sha or
                snapshot.decision_at_ms!=batch.decision_at_ms):
            raise StateCheckpointHold("CS00_STATE_G2_G3_CAUSAL_MISMATCH")
        n=f"checkpoint_{snapshot.event_open_ms:016d}.json"
        with state_gate(self.root):
            j=self.root/"journals"
            if (j/n).exists():
                old=json.loads(_bytes(j/n))
                if old.get("snapshot_id")==snapshot.snapshot_id and old.get("batch_id")==batch.batch_id:
                    self.verify()
                    return old
                raise StateCheckpointHold("CS00_STATE_EVENT_DUPLICATE_CHANGED")
            m=self.g2.put_manifest(book.manifest)
            o=self.g2.put_snapshot(snapshot)
            e=self.g3.append(batch)
            paths=["observations/"+m,"observations/"+o,"exploration/"+e]
            receipt={"schema":SCHEMA,"event_ms":snapshot.event_open_ms,
                     "snapshot_id":snapshot.snapshot_id,"batch_id":batch.batch_id,
                     "state":"COMMITTED_SOURCE_ONLY_UNQUALIFIED",
                     "financial_authority":"NONE",
                     "files":[{"path":q,"sha256":sha256(_bytes(self.root/q)).hexdigest()}
                              for q in paths]}
            raw=_canon(receipt)
            fd=os.open(j/n,os.O_WRONLY|os.O_EXCL|os.O_CREAT|
                       getattr(os,"O_NOFOLLOW",0),0o600)
            try:
                os.write(fd,raw)
                os.fsync(fd)
            finally:os.close(fd)
            dirfd=os.open(j,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(dirfd)
            finally:os.close(dirfd)
            return receipt

    def verify(self):
        """Called under backup gate or externally while service is stopped.

        Check every G2 event has one G3 event and a final 3-file checkpoint.
        Any interrupted/uncommitted boundary blocks backups and start release.
        """
        g2=self.g2.replay()
        g3=self.g3.replay()
        obs={v["open"]:v for v in g2 if v.get("schema") and "open" in v}
        exp={v["event_open_ms"]:v for v in g3}
        checkpoints={}
        for p in sorted((self.root/"journals").iterdir()):
            if not _NAME.fullmatch(p.name):
                raise StateCheckpointHold("CS00_STATE_UNKNOWN_CHECKPOINT_FILE")
            data=_bytes(p)
            doc=json.loads(data)
            if _canon(doc)!=data or doc.get("schema")!=SCHEMA:
                raise StateCheckpointHold("CS00_STATE_CHECKPOINT_SCHEMA_OR_CANONICAL")
            event=doc.get("event_ms")
            if (type(event) is not int or p.name!=f"checkpoint_{event:016d}.json"
                    or doc.get("financial_authority")!="NONE"
                    or doc.get("state")!="COMMITTED_SOURCE_ONLY_UNQUALIFIED"
                    or type(doc.get("files")) is not list
                    or len(doc["files"])!=3 or event in checkpoints):
                raise StateCheckpointHold("CS00_STATE_CHECKPOINT_FIELDS")
            for item in doc["files"]:
                if (type(item) is not dict or
                        type(item.get("path")) is not str or
                        not re.fullmatch(r"(observations/(manifest|event)_[a-f0-9]{64}\\.json|exploration/g3_[0-9]{16}_[a-f0-9]{64}\\.json\\.gz)",item["path"])
                        or type(item.get("sha256")) is not str or
                        not re.fullmatch("[a-f0-9]{64}",item["sha256"])):
                    raise StateCheckpointHold("CS00_STATE_PATH_OR_DIGEST")
                if sha256(_bytes(self.root/item["path"])).hexdigest()!=item["sha256"]:
                    raise StateCheckpointHold("CS00_STATE_CHECKPOINT_TAMPER")
            if (event not in obs or event not in exp or
                    doc.get("snapshot_id")!=obs[event].get("id") or
                    doc.get("batch_id")!=exp[event].get("id")):
                raise StateCheckpointHold("CS00_STATE_G2_G3_CHECKPOINT_DIVERGENCE")
            checkpoints[event]=doc
        if set(obs)!=set(exp) or set(exp)!=set(checkpoints):
            raise StateCheckpointHold("CS00_STATE_UNCOMMITTED_PARTIAL_BOUNDARY")
        return {"checkpoints":len(checkpoints),"g2":len(obs),"g3":len(exp),
                "state":"VALID_LOCAL_SOURCE_ONLY_NOT_ORIGINAL","financial_authority":"NONE"}
