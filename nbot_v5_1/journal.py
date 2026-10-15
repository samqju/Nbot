"""G1-02 bounded append-only audit journal, explicit I/O only.

NOT a market capture/archive, source authenticator, database, credential store,
order log, or a transactional engine for research/paper/live positions.

Record append uses a private regular file, advisory exclusive flock, a chained
SHA-256, O_APPEND, and fsync. Replay fails closed on any damaged tail or
changed record. No recovery by truncating or silently repairing evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

JOURNAL_SCHEMA_VERSION = "NBOT_V5_1_JOURNAL_V1"
DEFAULT_MAX_BYTES = 4 * 1024 * 1024
_MAX_LINE = 4096
_EMPTY_SHA = "0" * 64
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REASON = re.compile(r"[A-Z][A-Z0-9_]*\Z")


class JournalIntegrityError(ValueError):
    """Corrupt, unsafe, untrusted or unsupported on-disk evidence."""


class JournalKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    SOURCE_HOLD = "SOURCE_HOLD"
    GUARDIAN_VETO = "GUARDIAN_VETO"
    RESTART_HOLD = "RESTART_HOLD"


@dataclass(frozen=True)
class JournalEvent:
    kind: JournalKind
    event_id: str
    recorded_at_ms: int
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.kind) is not JournalKind:
            raise ValueError("G1_JOURNAL_KIND_INVALID")
        if type(self.event_id) is not str or _SHA.fullmatch(self.event_id) is None:
            raise ValueError("G1_JOURNAL_EVENT_ID_INVALID")
        if type(self.recorded_at_ms) is not int or self.recorded_at_ms < 0:
            raise ValueError("G1_JOURNAL_TIME_INVALID")
        if (type(self.reason_codes) is not tuple
                or any(type(reason) is not str or _REASON.fullmatch(reason) is None
                       for reason in self.reason_codes)
                or self.reason_codes != tuple(sorted(set(self.reason_codes)))):
            raise ValueError("G1_JOURNAL_REASONS_INVALID")

    def as_record(self) -> dict[str, object]:
        return {"kind": self.kind.value, "id": self.event_id,
                "at": self.recorded_at_ms, "reasons": list(self.reason_codes)}


@dataclass(frozen=True)
class JournalReceipt:
    sequence: int
    digest: str
    event: JournalEvent


def _json_bytes(value: dict[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise JournalIntegrityError("G1_JOURNAL_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_constant(_: str) -> object:
    raise JournalIntegrityError("G1_JOURNAL_NONFINITE")


def _parse(raw: bytes) -> list[JournalReceipt]:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise JournalIntegrityError("G1_JOURNAL_TORN_TAIL")
    items: list[JournalReceipt] = []
    previous = _EMPTY_SHA
    seen: set[str] = set()
    for line in raw.splitlines(keepends=True):
        if len(line) > _MAX_LINE or not line.endswith(b"\n"):
            raise JournalIntegrityError("G1_JOURNAL_LINE_INVALID")
        try:
            value = json.loads(line[:-1], object_pairs_hook=_reject_duplicate_keys,
                               parse_constant=_reject_constant)
            if type(value) is not dict or set(value) != {"v", "n", "p", "e", "h"}:
                raise JournalIntegrityError("G1_JOURNAL_SCHEMA_INVALID")
            if value["v"] != JOURNAL_SCHEMA_VERSION or type(value["v"]) is not str:
                raise JournalIntegrityError("G1_JOURNAL_VERSION_INVALID")
            if type(value["n"]) is not int or value["n"] != len(items) + 1:
                raise JournalIntegrityError("G1_JOURNAL_SEQUENCE_INVALID")
            if type(value["p"]) is not str or value["p"] != previous:
                raise JournalIntegrityError("G1_JOURNAL_LINK_INVALID")
            if type(value["h"]) is not str or _SHA.fullmatch(value["h"]) is None:
                raise JournalIntegrityError("G1_JOURNAL_HASH_FORMAT_INVALID")
            ev = value["e"]
            if type(ev) is not dict or set(ev) != {"kind", "id", "at", "reasons"}:
                raise JournalIntegrityError("G1_JOURNAL_EVENT_SCHEMA_INVALID")
            if type(ev["reasons"]) is not list:
                raise JournalIntegrityError("G1_JOURNAL_REASONS_INVALID")
            event = JournalEvent(JournalKind(ev["kind"]), ev["id"], ev["at"],
                                 tuple(ev["reasons"]))
            content = {key: value[key] for key in ("v", "n", "p", "e")}
            digest = hashlib.sha256(_json_bytes(content)).hexdigest()
            if value["h"] != digest:
                raise JournalIntegrityError("G1_JOURNAL_HASH_MISMATCH")
            if line[:-1] != _json_bytes(value):
                raise JournalIntegrityError("G1_JOURNAL_CANONICAL_INVALID")
            if event.event_id in seen:
                raise JournalIntegrityError("G1_JOURNAL_DUPLICATE_EVENT")
            seen.add(event.event_id)
            items.append(JournalReceipt(value["n"], digest, event))
            previous = digest
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            if isinstance(exc, JournalIntegrityError):
                raise
            raise JournalIntegrityError("G1_JOURNAL_RECORD_INVALID") from exc
    return items


class AppendOnlyJournal:
    """Small fsync-on-append audit log, no implicit filesystem I/O on import.

    The caller must supply an existing, non-symlink parent directory. Only
    ordinary owner-private files are accepted. Do not use for market tick data.
    """

    def __init__(self, path: str | Path, *, max_bytes: int = DEFAULT_MAX_BYTES):
        if not isinstance(path, (str, Path)):
            raise ValueError("G1_JOURNAL_PATH_INVALID")
        self.path = Path(path)
        if (not self.path.is_absolute() or self.path.name in ("", ".", "..")
                or self.path.parent.is_symlink()
                or os.path.realpath(self.path.parent) != str(self.path.parent)):
            raise ValueError("G1_JOURNAL_PATH_UNSAFE")
        if type(max_bytes) is not int or not 4096 <= max_bytes <= 64 * 1024 * 1024:
            raise ValueError("G1_JOURNAL_BUDGET_INVALID")
        self.max_bytes = max_bytes

    @staticmethod
    def _check_fd(fd: int) -> None:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1
                or s.st_uid != os.getuid() or (s.st_mode & 0o077)):
            raise JournalIntegrityError("G1_JOURNAL_UNSAFE_FILE")

    def _sync_parent(self) -> None:
        """Sync parent directory entry; required on first create and duplicate retry."""
        d = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(d)
        finally:
            os.close(d)

    def _read_locked(self, fd: int) -> list[JournalReceipt]:
        size = os.fstat(fd).st_size
        if size > self.max_bytes:
            raise JournalIntegrityError("G1_JOURNAL_BUDGET_EXCEEDED")
        os.lseek(fd, 0, os.SEEK_SET)
        data = bytearray()
        while len(data) <= self.max_bytes:
            block = os.read(fd, min(65536, self.max_bytes + 1 - len(data)))
            if not block:
                break
            data.extend(block)
        if len(data) > self.max_bytes or len(data) != size:
            raise JournalIntegrityError("G1_JOURNAL_SIZE_CHANGED")
        return _parse(bytes(data))

    def replay(self) -> tuple[JournalReceipt, ...]:
        """Strict verified read. Missing file is empty; damaged file is HOLD."""
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(self.path, flags)
        except FileNotFoundError:
            return ()
        try:
            self._check_fd(fd)
            fcntl.flock(fd, fcntl.LOCK_SH)
            return tuple(self._read_locked(fd))
        finally:
            os.close(fd)

    def append(self, event: JournalEvent) -> JournalReceipt:
        """Append one fully synced unique audit event; retries are idempotent.

        Existing corrupt/truncated records reject the append, never auto-repair.
        All cooperating writers must use this advisory-lock implementation.
        """
        if type(event) is not JournalEvent:
            raise ValueError("G1_JOURNAL_EVENT_TYPE_INVALID")
        if not self.path.parent.is_dir():
            raise JournalIntegrityError("G1_JOURNAL_PARENT_MISSING")
        # A durable *new filename* requires syncing its parent directory too.
        # Reject writable/shared parents so other users cannot swap the inode.
        dir_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        dir_fd = os.open(self.path.parent, dir_flags)
        try:
            parent = os.fstat(dir_fd)
            if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
                    or parent.st_mode & 0o022):
                raise JournalIntegrityError("G1_JOURNAL_UNSAFE_PARENT")
        finally:
            os.close(dir_fd)
        flags = (os.O_RDWR | os.O_CREAT | os.O_APPEND
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
        fd = os.open(self.path, flags, 0o600)
        try:
            self._check_fd(fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
            items = self._read_locked(fd)
            for item in items:
                if item.event.event_id == event.event_id:
                    if item.event == event:
                        # A prior first-create may have failed to sync its
                        # directory. A retry must not claim durable success
                        # without fsyncing both file and directory.
                        os.fsync(fd)
                        self._sync_parent()
                        return item
                    raise JournalIntegrityError("G1_JOURNAL_REPLAY_CONFLICT")
            payload: dict[str, object] = {
                "v": JOURNAL_SCHEMA_VERSION, "n": len(items) + 1,
                "p": items[-1].digest if items else _EMPTY_SHA,
                "e": event.as_record(),
            }
            digest = hashlib.sha256(_json_bytes(payload)).hexdigest()
            line = _json_bytes({**payload, "h": digest}) + b"\n"
            if len(line) > _MAX_LINE or os.fstat(fd).st_size + len(line) > self.max_bytes:
                raise JournalIntegrityError("G1_JOURNAL_BUDGET_EXCEEDED")
            # O_APPEND + advisory lock handles cooperating processes. No rewrite.
            view = memoryview(line)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("G1_JOURNAL_WRITE_FAILED")
                view = view[written:]
            os.fsync(fd)
            # Force the directory entry as well as the data to stable storage.
            # If this fails, do not claim append success: retry is idempotent.
            self._sync_parent()
            return JournalReceipt(len(items) + 1, digest, event)
        finally:
            os.close(fd)
