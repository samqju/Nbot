"""Verified immutable segment relocation to an explicitly mounted archive.

Copies, fsyncs and hashes bytes before publishing a durable locator and
releasing hot-disk bytes. A mounted archive can be off-host; no remote client
or credential is created here. Missing mounts fail closed during replay.
Only a caller-authorized source directory is touched; never called at import.
"""
import hashlib
import json
import os
from pathlib import Path

from nbot.v5.g4_segmented_source import canonical, sha, _durable_publish


def private_directory(path):
    path=Path(path)
    if (not path.is_absolute() or not path.is_dir()
            or path.stat().st_mode & 0o077
            or any(p.is_symlink() for p in (path,*path.parents))):
        raise ValueError("G4_ARCHIVE_DESTINATION_UNSAFE")
    return path


def resolve_payload(root, stem, meta):
    local=root/(stem+".gz")
    locator=root/(stem+".location.json")
    if not locator.exists():
        return local
    if locator.is_symlink() or locator.stat().st_size>4096:
        raise ValueError("G4_ARCHIVE_LOCATOR_UNSAFE")
    receipt=json.loads(locator.read_bytes())
    body={k:v for k,v in receipt.items() if k!="locator_sha256"}
    if (receipt.get("locator_sha256")!=sha(canonical(body))
            or body.get("compressed_sha")!=meta["compressed_sha"]
            or body.get("manifest_sha")!=meta["manifest_sha"]
            or body.get("version")!="NBOT_V5_ARCHIVE_LOCATOR_V1"):
        raise ValueError("G4_ARCHIVE_LOCATOR_INVALID")
    remote=Path(body["path"])
    private_directory(remote.parent)
    if remote.is_symlink() or not remote.is_file():
        raise ValueError("G4_ARCHIVE_PAYLOAD_UNAVAILABLE")
    if remote.stat().st_size!=body["bytes"]:
        raise ValueError("G4_ARCHIVE_PAYLOAD_SIZE")
    # Duplicate verified copies can exist after termination between locator
    # publication and local unlink. They are never separate source receipts.
    if local.exists():
        if local.is_symlink() or local.read_bytes()!=remote.read_bytes():
            raise ValueError("G4_ARCHIVE_DUPLICATE_CONFLICT")
    return remote


def archive_committed_segments(root, destination, *, keep_recent=2, max_segments=64):
    from nbot.v5.g4_segmented_source import read_segments
    root=private_directory(Path(root).resolve())
    destination=private_directory(destination)
    if root==destination or root in destination.parents or destination in root.parents:
        raise ValueError("G4_ARCHIVE_NOT_SEPARATE_STORAGE")
    if (type(keep_recent) is not int or keep_recent<1 or
            type(max_segments) is not int or not 1<=max_segments<=64):
        raise ValueError("G4_ARCHIVE_BATCH_BOUNDS")
    # Refuse to relocate anything from an incomplete/corrupt checkpoint.
    for _ in read_segments(root):
        pass
    metas=sorted(root.glob("segment-????????.json"))
    moved=bytes_released=0
    for metadata in metas[:-keep_recent][:max_segments]:
        stem=metadata.stem
        local=root/(stem+".gz")
        if not local.exists():
            continue
        meta=json.loads(metadata.read_bytes())
        target=destination/(meta["compressed_sha"]+".gz")
        raw=local.read_bytes()
        if sha(raw)!=meta["compressed_sha"]:
            raise ValueError("G4_ARCHIVE_SOURCE_CHANGED")
        if target.exists():
            if target.is_symlink() or target.read_bytes()!=raw:
                raise ValueError("G4_ARCHIVE_TARGET_CONFLICT")
        else:
            _durable_publish(target,raw)
        # Independent reopen, after stable publication. Never trust copy return.
        with target.open("rb") as archived:
            if hashlib.file_digest(archived,"sha256").hexdigest()!=meta["compressed_sha"]:
                raise ValueError("G4_ARCHIVE_COPY_VERIFY_FAILED")
        body={"version":"NBOT_V5_ARCHIVE_LOCATOR_V1","path":str(target),
              "compressed_sha":meta["compressed_sha"],"manifest_sha":meta["manifest_sha"],"bytes":len(raw)}
        locator={**body,"locator_sha256":sha(canonical(body))}
        pointer=root/(stem+".location.json")
        if pointer.exists():
            if pointer.read_bytes()!=canonical(locator):
                raise ValueError("G4_ARCHIVE_LOCATOR_CONFLICT")
        else:
            _durable_publish(pointer,canonical(locator))
        resolve_payload(root,stem,meta)
        local.unlink()
        directory=os.open(str(root),os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        moved+=1
        bytes_released+=len(raw)-pointer.stat().st_size
    return {"segments_relocated":moved,"hot_bytes_released":bytes_released,
            "original_bytes_rewritten":False,"order_authority":"NONE"}
