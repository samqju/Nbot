"""G2 compact immutable decision/manifest receipts, never raw market frames.

A deliberately bounded, owner-private local directory. No auto-truncate,
retention deletion, schema migration, or automatic recovery of incomplete
records: fail closed pending a separate evidenced archive policy.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .observation import ObservationSnapshot, OBSERVATION_SCHEMA
from .universe import UniverseManifest, UNIVERSE_SCHEMA


class ObservationStorageHold(ValueError):
    pass


STORE_SCHEMA = "NBOT_V5_1_BROAD_STORE_V1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _validate_json(data: bytes) -> dict:
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ObservationStorageHold("G2_DUPLICATE_JSON_KEY")
            out[k] = v
        return out
    try:
        value = json.loads(data, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               ObservationStorageHold("G2_BAD_NUMBER")))
    except (ValueError, UnicodeError) as exc:
        raise ObservationStorageHold("G2_INVALID_JSON") from exc
    if type(value) is not dict or data != _canonical(value):
        raise ObservationStorageHold("G2_NONCANONICAL_RECEIPT")
    if set(value) != {"schema", "body", "sha256"} or value["schema"] != STORE_SCHEMA:
        raise ObservationStorageHold("G2_STORE_SCHEMA_MISMATCH")
    digest = value["sha256"]
    if type(digest) is not str or not _DIGEST.fullmatch(digest):
        raise ObservationStorageHold("G2_STORE_DIGEST_BAD")
    if hashlib.sha256(_canonical(value["body"])).hexdigest() != digest:
        raise ObservationStorageHold("G2_STORE_TAMPERED")
    if type(value["body"]) is not dict:
        raise ObservationStorageHold("G2_STORE_BODY_INVALID")
    return value["body"]


class CompactObservationStore:
    """Explicit fsync receipts of bounded source/clock snapshots.

    This is NOT independent custody (a writer could recompute hashes) and NOT
    a high-frequency original trade/quote archive. An interrupted file is
    quarantined by refusal; G2 does not silently repair or delete it.
    """
    def __init__(self, directory: Path, *, max_bytes: int = 64 * 1024 * 1024):
        if not isinstance(directory, Path) or not directory.is_absolute() or directory.is_symlink():
            raise ValueError("G2_STORAGE_PATH_INVALID")
        if (type(max_bytes) is not int or max_bytes < 128 * 1024
                or max_bytes > 1024 * 1024 * 1024):
            raise ValueError("G2_STORAGE_BUDGET_INVALID")
        self.directory = directory
        self.max_bytes = max_bytes

    def _checked_dir(self):
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise ObservationStorageHold("G2_STORAGE_DIRECTORY_MISSING")
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY
                     | getattr(os, "O_NOFOLLOW", 0))
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            os.close(fd)
            raise ObservationStorageHold("G2_STORAGE_PARENT_UNSAFE")
        return fd

    def _scan(self):
        used = 0
        entries = {}
        for p in self.directory.iterdir():
            if not re.fullmatch(r"(manifest|event)_[0-9a-f]{64}\.json", p.name):
                raise ObservationStorageHold("G2_STORAGE_UNKNOWN_OR_PARTIAL_FILE")
            st = p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise ObservationStorageHold("G2_STORAGE_UNSAFE_FILE")
            used += st.st_size
            if used > self.max_bytes:
                raise ObservationStorageHold("G2_STORAGE_QUOTA_EXCEEDED")
            entries[p.name] = st.st_size
        return used, entries

    @staticmethod
    def _receipt(body: dict) -> bytes:
        return _canonical({"schema": STORE_SCHEMA, "body": body,
                           "sha256": hashlib.sha256(_canonical(body)).hexdigest()})

    def _store(self, name: str, body: dict) -> str:
        directory_fd = self._checked_dir()
        try:
            used, entries = self._scan()
            blob = self._receipt(body)
            if len(blob) > 128 * 1024:
                raise ObservationStorageHold("G2_STORAGE_RECEIPT_TOO_LARGE")
            if name in entries:
                existing = self._read_unlocked(name)
                if existing != body:
                    raise ObservationStorageHold("G2_STORAGE_EVENT_CONFLICT")
                # A prior directory sync can fail; duplicate must re-fsync.
                target = os.open(self.directory / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    os.fsync(target)
                    os.fsync(directory_fd)
                finally:
                    os.close(target)
                return name
            if used + len(blob) > self.max_bytes:
                raise ObservationStorageHold("G2_STORAGE_QUOTA_EXCEEDED")
            target = self.directory / name
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(target, flags, 0o600)
            try:
                view = memoryview(blob)
                while view:
                    amount = os.write(fd, view)
                    if amount <= 0:
                        raise OSError("G2_STORAGE_SHORT_WRITE")
                    view = view[amount:]
                os.fsync(fd)
                os.fsync(directory_fd)
            finally:
                os.close(fd)
            return name
        finally:
            os.close(directory_fd)

    def _read_unlocked(self, name: str) -> dict:
        p = self.directory / name
        fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                    or st.st_uid != os.getuid() or st.st_mode & 0o077
                    or st.st_size > 128 * 1024):
                raise ObservationStorageHold("G2_STORAGE_UNSAFE_RECEIPT")
            blob = bytearray()
            while len(blob) <= 128 * 1024:
                part = os.read(fd, 131073 - len(blob))
                if not part:
                    break
                blob.extend(part)
            if len(blob) != st.st_size:
                raise ObservationStorageHold("G2_STORAGE_SIZE_CHANGED")
            return _validate_json(bytes(blob))
        finally:
            os.close(fd)

    def put_manifest(self, manifest: UniverseManifest) -> str:
        if type(manifest) is not UniverseManifest:
            raise ValueError("G2_MANIFEST_TYPE_INVALID")
        body = {"schema": UNIVERSE_SCHEMA,
                "received": manifest.source_received_at_ms,
                "selected": manifest.selected_at_ms,
                "source_sha": manifest.source_digest,
                "selection_sha": manifest.selection_digest,
                "entries": [{"symbol": e.symbol, "groups": list(e.groups),
                             "turnover": e.quote_turnover, "change": e.change_percent}
                            for e in manifest.entries],
                "rejected": [list(r) for r in manifest.rejected],
                "qualified_count": manifest.qualified_count,
                "public_receipts": [list(r) for r in manifest.public_receipts]}
        return self._store(f"manifest_{manifest.selection_digest}.json", body)

    def put_snapshot(self, snapshot: ObservationSnapshot) -> str:
        if type(snapshot) is not ObservationSnapshot:
            raise ValueError("G2_SNAPSHOT_TYPE_INVALID")
        return self._store(f"event_{snapshot.snapshot_id}.json", snapshot.as_record())

    def replay(self) -> tuple[dict, ...]:
        """Validate entire compact directory; partial/tampered data is HOLD."""
        directory_fd = self._checked_dir()
        try:
            _, entries = self._scan()
            result = []
            for name in sorted(entries):
                body = self._read_unlocked(name)
                if name.startswith("event_"):
                    if body.get("schema") != OBSERVATION_SCHEMA or body.get("id") != name[6:-5]:
                        raise ObservationStorageHold("G2_STORAGE_EVENT_ID_MISMATCH")
                    if (type(body.get("rows")) is not list or
                            len(body["rows"]) > 100 or
                            len({r.get("symbol") for r in body["rows"]}) != len(body["rows"])):
                        raise ObservationStorageHold("G2_STORAGE_DENOMINATOR_INVALID")
                elif body.get("schema") != UNIVERSE_SCHEMA or body.get("selection_sha") != name[9:-5]:
                    raise ObservationStorageHold("G2_STORAGE_MANIFEST_ID_MISMATCH")
                result.append(body)
            return tuple(result)
        finally:
            os.close(directory_fd)
