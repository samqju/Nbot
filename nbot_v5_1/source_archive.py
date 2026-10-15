"""G2 bounded, byte-exact public REST source receipt archive (offline API).

The original HTTP response bytes, URI path, observed-at time and SHA are
durably stored in gzip receipts. This is public REST OHLCV custody only, NOT
unforgeable exchange attribution, trade/quote/funding stream or WORM storage.
No network, secrets, account or trading I/O here. Never auto-truncate/rotate.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zlib

from .public_market import PublicResponse

ARCHIVE_SCHEMA = "NBOT_V5_1_PUBLIC_SOURCE_ARCHIVE_V1"
MAX_PAYLOAD = 4 * 1024 * 1024
MAX_DECOMPRESSED = 6 * 1024 * 1024
_ALLOWED = {"EXCHANGE_INFO": "/fapi/v1/exchangeInfo",
            "TICKER_24HR": "/fapi/v1/ticker/24hr",
            "BOOK_TICKER": "/fapi/v1/ticker/bookTicker",
            "KLINES": "/fapi/v1/klines"}


class PublicArchiveHold(ValueError):
    pass


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class SourceReceipt:
    name: str
    response: PublicResponse
    archive_sha256: str


class PublicSourceArchive:
    """Explicit bounded receipt I/O to existing private, single-owner directory."""

    def __init__(self, root: Path, *, budget_bytes: int = 64 * 1024 * 1024):
        if not isinstance(root, Path) or not root.is_absolute() or root.is_symlink():
            raise ValueError("G2_ARCHIVE_PATH_INVALID")
        if type(budget_bytes) is not int or not 1 * 1024 * 1024 <= budget_bytes <= 1024 * 1024 * 1024:
            raise ValueError("G2_ARCHIVE_BUDGET_INVALID")
        self.root, self.budget_bytes = root, budget_bytes

    def _directory_fd(self) -> int:
        if not self.root.is_dir() or self.root.is_symlink():
            raise PublicArchiveHold("G2_ARCHIVE_DIRECTORY_MISSING")
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY
                     | getattr(os, "O_NOFOLLOW", 0))
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            os.close(fd)
            raise PublicArchiveHold("G2_ARCHIVE_DIR_UNSAFE")
        return fd

    def _files(self) -> dict[str, int]:
        files: dict[str, int] = {}
        used = 0
        for p in self.root.iterdir():
            if not re.fullmatch(r"source_[0-9a-f]{64}\.json\.gz", p.name):
                raise PublicArchiveHold("G2_ARCHIVE_UNKNOWN_FILE_OR_TORN_WRITE")
            st = p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise PublicArchiveHold("G2_ARCHIVE_FILE_UNSAFE")
            files[p.name] = st.st_size
            used += st.st_size
        if used > self.budget_bytes:
            raise PublicArchiveHold("G2_ARCHIVE_FULL")
        return files

    @staticmethod
    def _make_payload(response: PublicResponse) -> bytes:
        if type(response) is not PublicResponse or type(response.raw_bytes) is not bytes:
            raise ValueError("G2_ARCHIVE_SOURCE_TYPE_INVALID")
        if response.kind not in _ALLOWED or response.path != _ALLOWED[response.kind]:
            raise PublicArchiveHold("G2_ARCHIVE_NON_PUBLIC_ENDPOINT")
        raw = response.raw_bytes
        if not 1 <= len(raw) <= MAX_PAYLOAD or hashlib.sha256(raw).hexdigest() != response.body_sha256:
            raise PublicArchiveHold("G2_ARCHIVE_SOURCE_BYTES_INVALID")
        if type(response.received_at_ms) is not int or response.received_at_ms < 0:
            raise PublicArchiveHold("G2_ARCHIVE_TIME_INVALID")
        body = {"schema": ARCHIVE_SCHEMA,
                "kind": response.kind, "path": response.path,
                "received_at_ms": response.received_at_ms,
                "sha256": response.body_sha256,
                "raw_base64": base64.b64encode(raw).decode("ascii")}
        return _canon(body)

    def _read_one(self, name: str) -> SourceReceipt:
        fd = os.open(self.root / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                    or st.st_uid != os.getuid() or st.st_mode & 0o077
                    or st.st_size > MAX_PAYLOAD):
                raise PublicArchiveHold("G2_ARCHIVE_FILE_UNSAFE")
            data = bytearray()
            while len(data) <= MAX_PAYLOAD:
                block = os.read(fd, MAX_PAYLOAD + 1 - len(data))
                if not block:
                    break
                data.extend(block)
            if len(data) != st.st_size:
                raise PublicArchiveHold("G2_ARCHIVE_FILE_CHANGED")
        finally:
            os.close(fd)
        if not bytes(data).startswith(b"\x1f\x8b"):
            raise PublicArchiveHold("G2_ARCHIVE_NOT_GZIP")
        try:
            decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
            expanded = decomp.decompress(bytes(data), MAX_DECOMPRESSED + 1)
            if len(expanded) > MAX_DECOMPRESSED or not decomp.eof or decomp.unused_data:
                raise PublicArchiveHold("G2_ARCHIVE_GZIP_BROKEN")
            value = json.loads(expanded)
        except (zlib.error, ValueError, UnicodeError, TypeError) as exc:
            if isinstance(exc, PublicArchiveHold):
                raise
            raise PublicArchiveHold("G2_ARCHIVE_INVALID_BODY") from exc
        if type(value) is not dict or _canon(value) != expanded or set(value) != {
                "schema", "kind", "path", "received_at_ms", "sha256", "raw_base64"}:
            raise PublicArchiveHold("G2_ARCHIVE_SCHEMA_BAD")
        if value["schema"] != ARCHIVE_SCHEMA or value["kind"] not in _ALLOWED or value["path"] != _ALLOWED[value["kind"]]:
            raise PublicArchiveHold("G2_ARCHIVE_ENDPOINT_BAD")
        try:
            raw = base64.b64decode(value["raw_base64"], validate=True)
            if (len(raw) > MAX_PAYLOAD or
                    hashlib.sha256(raw).hexdigest() != value["sha256"]):
                raise PublicArchiveHold("G2_ARCHIVE_BODY_HASH_MISMATCH")
            parsed = json.loads(raw)
        except (ValueError, TypeError, UnicodeError) as exc:
            if isinstance(exc, PublicArchiveHold):
                raise
            raise PublicArchiveHold("G2_ARCHIVE_SOURCE_JSON_INVALID") from exc
        if "source_" + hashlib.sha256(expanded).hexdigest() + ".json.gz" != name:
            raise PublicArchiveHold("G2_ARCHIVE_NAME_HASH_MISMATCH")
        response = PublicResponse(value["kind"], value["path"],
                value["received_at_ms"], value["sha256"], parsed, 0, raw)
        return SourceReceipt(name, response, hashlib.sha256(bytes(data)).hexdigest())

    def append(self, response: PublicResponse) -> SourceReceipt:
        expanded = self._make_payload(response)
        name = "source_" + hashlib.sha256(expanded).hexdigest() + ".json.gz"
        encoded = gzip.compress(expanded, compresslevel=6, mtime=0)
        if len(encoded) > MAX_PAYLOAD:
            raise PublicArchiveHold("G2_ARCHIVE_RECEIPT_TOO_LARGE")
        dir_fd = self._directory_fd()
        try:
            existing = self._files()
            if name in existing:
                receipt = self._read_one(name)
                f = os.open(self.root / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                try:
                    os.fsync(f)
                    os.fsync(dir_fd)
                finally:
                    os.close(f)
                return receipt
            if sum(existing.values()) + len(encoded) > self.budget_bytes:
                raise PublicArchiveHold("G2_ARCHIVE_FULL")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.root / name, flags, 0o600)
            try:
                data = memoryview(encoded)
                while data:
                    count = os.write(fd, data)
                    if count <= 0:
                        raise OSError("G2_ARCHIVE_PARTIAL_WRITE")
                    data = data[count:]
                os.fsync(fd)
                os.fsync(dir_fd)
            finally:
                os.close(fd)
            return self._read_one(name)
        finally:
            os.close(dir_fd)

    def replay(self) -> tuple[SourceReceipt, ...]:
        dir_fd = self._directory_fd()
        try:
            return tuple(self._read_one(name) for name in sorted(self._files()))
        finally:
            os.close(dir_fd)
