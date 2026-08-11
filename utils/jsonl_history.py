"""Safe append-only JSONL rotation with transparent gzip history reads.

The live writer keeps using one small ``*.jsonl`` file. Completed history can
be atomically rotated into ``data/history/<stem>/`` and gzip-compressed. Readers
use :func:`iter_jsonl_lines` so archived and live rows remain one logical stream.
"""

from __future__ import annotations

import fcntl
import gzip
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_SEGMENT_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def history_directory(path: str | Path) -> Path:
    source = Path(path)
    return source.parent / "history" / source.stem


def _lock_path(path: Path) -> Path:
    return path.parent / f".{path.name}.lock"


@contextmanager
def jsonl_write_lock(path: str | Path):
    """Cross-process advisory lock shared by appenders and the rotator."""
    source = Path(path)
    source.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(source)
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def append_jsonl_line(path: str | Path, line: str) -> None:
    """Append one complete line and fsync it without racing history rotation."""
    source = Path(path)
    source.parent.mkdir(parents=True, exist_ok=True)
    payload = (str(line).rstrip("\n") + "\n").encode("utf-8")
    with jsonl_write_lock(source):
        fd = os.open(
            source,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)


def _history_segments(path: Path) -> list[Path]:
    root = history_directory(path)
    if not root.exists():
        return []

    # During compression both raw and gzip forms can exist briefly. Prefer the
    # gzip form for the same segment stem so a reader never sees duplicates.
    by_key: dict[str, Path] = {}
    for candidate in root.iterdir():
        if not candidate.is_file() or candidate.name.startswith("."):
            continue
        name = candidate.name
        if name.endswith(".jsonl.gz"):
            key = name[:-3]
            by_key[key] = candidate
        elif name.endswith(".jsonl"):
            by_key.setdefault(name, candidate)
    return [by_key[key] for key in sorted(by_key)]


def iter_jsonl_lines(path: str | Path) -> Iterator[str]:
    """Yield archived rows first, then the current live JSONL rows."""
    source = Path(path)
    for segment in _history_segments(source):
        opener = gzip.open if segment.name.endswith(".gz") else open
        try:
            with opener(segment, "rt", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield line
        except FileNotFoundError:
            # A segment may finish compression between discovery and open.
            # Re-reading on the next caller is safer than failing the worker.
            continue

    if not source.exists():
        return
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield line


def logical_jsonl_exists(path: str | Path) -> bool:
    source = Path(path)
    return source.exists() or bool(_history_segments(source))


def logical_jsonl_bytes(path: str | Path) -> int:
    source = Path(path)
    total = source.stat().st_size if source.exists() else 0
    for segment in _history_segments(source):
        try:
            total += segment.stat().st_size
        except FileNotFoundError:
            continue
    return total


def rotate_jsonl_to_history(
    path: str | Path,
    *,
    segment_tag: str,
    min_bytes: int = 0,
) -> dict:
    """Atomically rotate the whole live JSONL and gzip it outside the lock.

    Rows newer than the most recent training cutoff may be rotated too. That is
    intentional: archive + live are one logical stream, and consumers still
    apply their own timestamp cutoffs. The operation therefore changes storage
    layout only, never learning semantics.
    """
    source = Path(path)
    minimum = max(0, int(min_bytes))
    safe_tag = _SEGMENT_SAFE.sub("-", str(segment_tag).strip()) or "segment"
    archive = history_directory(source)
    archive.mkdir(parents=True, exist_ok=True)

    with jsonl_write_lock(source):
        if not source.exists():
            return {"rotated": False, "reason": "SOURCE_MISSING", "bytes": 0}
        size = source.stat().st_size
        if size <= 0:
            return {"rotated": False, "reason": "SOURCE_EMPTY", "bytes": 0}
        if size < minimum:
            return {
                "rotated": False,
                "reason": "BELOW_MIN_BYTES",
                "bytes": size,
            }

        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        nonce = time.time_ns()
        raw_segment = archive / (
            f"{source.stem}.{stamp}.{safe_tag}.{nonce}.jsonl"
        )
        os.replace(source, raw_segment)
        fd = os.open(source, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)

    gzip_target = Path(str(raw_segment) + ".gz")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{gzip_target.name}.",
        suffix=".tmp",
        dir=str(archive),
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with raw_segment.open("rb") as src, gzip.open(
            temporary, "wb", compresslevel=6
        ) as dst:
            while True:
                block = src.read(1024 * 1024)
                if not block:
                    break
                dst.write(block)
        os.replace(temporary, gzip_target)
        raw_segment.unlink()
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        # Keep raw_segment intact. Readers support raw archived segments too.
        raise

    compressed = gzip_target.stat().st_size
    return {
        "rotated": True,
        "source_bytes": size,
        "archive_bytes": compressed,
        "bytes_reclaimed": max(0, size - compressed),
        "archive_path": str(gzip_target),
    }
