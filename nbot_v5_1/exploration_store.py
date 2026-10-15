"""G3 bounded, immutable-intent compressed 200-direction exploration receipts.

Explicit Linux I/O only; no import/startup effects. No fills, orders, market
ticks or profitability, no silent garbage collection. This is NOT remote WORM.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zlib

from .exploration import ExplorationBatch, G3_SCHEMA, PATTERN_IDS, MASKS, SIDES

RECEIPT_SCHEMA = "NBOT_V5_1_G3_RECEIPT_V1"
_FILENAME = re.compile(r"g3_([0-9]{16})_([0-9a-f]{64})\.json\.gz\Z")
MAX_RECORD_BYTES = 3 * 1024 * 1024
MAX_COMPRESSED_BYTES = 2 * 1024 * 1024


class ExplorationStoreHold(ValueError):
    """Never use a damaged/over-limit record as valid Exploration evidence."""


def _canon(body: object) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("ascii")


def _parse_unique(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ExplorationStoreHold("G3_JSON_DUPLICATE_KEY")
        out[key] = value
    return out


def _parse(body: bytes) -> dict:
    try:
        row = json.loads(body, object_pairs_hook=_parse_unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ExplorationStoreHold("G3_JSON_NONFINITE")))
    except (ValueError, TypeError, UnicodeError) as exc:
        if isinstance(exc, ExplorationStoreHold):
            raise
        raise ExplorationStoreHold("G3_RECEIPT_JSON_INVALID") from exc
    if type(row) is not dict or _canon(row) != body or set(row) != {
            "schema", "sha256", "batch"}:
        raise ExplorationStoreHold("G3_RECEIPT_FORMAT_INVALID")
    if row["schema"] != RECEIPT_SCHEMA or type(row["sha256"]) is not str:
        raise ExplorationStoreHold("G3_RECEIPT_SCHEMA_INVALID")
    if hashlib.sha256(_canon(row["batch"])).hexdigest() != row["sha256"]:
        raise ExplorationStoreHold("G3_RECEIPT_HASH_MISMATCH")
    if type(row["batch"]) is not dict or row["batch"].get("schema") != G3_SCHEMA:
        raise ExplorationStoreHold("G3_BATCH_SCHEMA_INVALID")
    batch = row["batch"]
    rows = batch.get("rows")
    if type(rows) is not list or not 1 <= len(rows) <= 200 or len(rows) % 2:
        raise ExplorationStoreHold("G3_ROWS_INCOMPLETE")
    names: set[tuple[str, str]] = set()
    counts = {"OBSERVED": 0, "NOT_EVALUATED_SOURCE": 0,
              "NOT_EVALUATED_CAPACITY": 0}
    for r in rows:
        if type(r) is not dict or type(r.get("symbol")) is not str or r.get("side") not in SIDES:
            raise ExplorationStoreHold("G3_ROW_SCHEMA_INVALID")
        key = (r["symbol"], r["side"])
        if key in names:
            raise ExplorationStoreHold("G3_DIRECTION_DUPLICATE")
        names.add(key)
        if r.get("status") not in counts or r.get("authority") != "NONE" or r.get("disposition") != "NO_TRADE":
            raise ExplorationStoreHold("G3_ROW_ORDER_AUTHORITY_INVALID")
        counts[r["status"]] += 1
        patterns = r.get("patterns")
        if type(patterns) is not dict or set(patterns) != set(PATTERN_IDS):
            raise ExplorationStoreHold("G3_PATTERN_DENOMINATOR_INVALID")
        if any(type(x) is not str or x not in MASKS for x in patterns.values()):
            raise ExplorationStoreHold("G3_PATTERN_STATE_INVALID")
        if r["status"] != "OBSERVED" and any(v != r["status"] for v in patterns.values()):
            raise ExplorationStoreHold("G3_MASK_CONTRADICTION")
    coins = {sym for sym,side in names}
    if len(names) != 2*len(coins) or any((s,side) not in names for s in coins for side in SIDES):
        raise ExplorationStoreHold("G3_PAIR_DENOMINATOR_INVALID")
    if (batch.get("evaluated_pairs") != counts["OBSERVED"]
            or batch.get("source_skipped_pairs") != counts["NOT_EVALUATED_SOURCE"]
            or batch.get("capacity_skipped_pairs") != counts["NOT_EVALUATED_CAPACITY"]):
        raise ExplorationStoreHold("G3_PAIR_COUNT_INVALID")
    return batch


class ExplorationStore:
    def __init__(self, directory: Path, *, budget_bytes: int = 64*1024*1024):
        if not isinstance(directory, Path) or not directory.is_absolute() or directory.is_symlink():
            raise ValueError("G3_STORE_PATH_INVALID")
        if type(budget_bytes) is not int or not 1*1024*1024 <= budget_bytes <= 512*1024*1024:
            raise ValueError("G3_STORE_QUOTA_INVALID")
        self.directory = directory
        self.budget_bytes = budget_bytes

    def _dirfd(self) -> int:
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise ExplorationStoreHold("G3_STORE_DIRECTORY_MISSING")
        fd = os.open(self.directory, os.O_RDONLY|os.O_DIRECTORY
                     |getattr(os,"O_NOFOLLOW",0))
        s = os.fstat(fd)
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
            os.close(fd)
            raise ExplorationStoreHold("G3_STORE_DIRECTORY_UNSAFE")
        return fd

    def _scan(self) -> dict[str, int]:
        files: dict[str,int] = {}
        for p in self.directory.iterdir():
            if _FILENAME.fullmatch(p.name) is None:
                raise ExplorationStoreHold("G3_UNKNOWN_OR_PARTIAL_RECORD")
            s = p.lstat()
            if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or
                    s.st_uid != os.getuid() or s.st_mode & 0o077 or
                    s.st_size > MAX_COMPRESSED_BYTES):
                raise ExplorationStoreHold("G3_STORE_FILE_UNSAFE")
            files[p.name] = s.st_size
        if sum(files.values()) > self.budget_bytes:
            raise ExplorationStoreHold("G3_STORE_QUOTA_FULL")
        return files

    def _read(self, name: str) -> dict:
        m = _FILENAME.fullmatch(name)
        if m is None:
            raise ExplorationStoreHold("G3_FILENAME_INVALID")
        fd = os.open(self.directory / name,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
        try:
            s = os.fstat(fd)
            if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or
                    s.st_uid != os.getuid() or s.st_mode & 0o077 or
                    s.st_size > MAX_COMPRESSED_BYTES):
                raise ExplorationStoreHold("G3_STORE_FILE_UNSAFE")
            parts = bytearray()
            while len(parts) <= MAX_COMPRESSED_BYTES:
                block = os.read(fd,MAX_COMPRESSED_BYTES+1-len(parts))
                if not block: break
                parts.extend(block)
            if len(parts) != s.st_size:
                raise ExplorationStoreHold("G3_STORE_READ_INCONSISTENT")
        finally:
            os.close(fd)
        try:
            obj = zlib.decompressobj(16+zlib.MAX_WBITS)
            data = obj.decompress(bytes(parts),MAX_RECORD_BYTES+1)
            if len(data)>MAX_RECORD_BYTES or not obj.eof or obj.unused_data:
                raise ExplorationStoreHold("G3_STORE_GZIP_INVALID")
        except zlib.error as exc:
            raise ExplorationStoreHold("G3_STORE_GZIP_BROKEN") from exc
        batch = _parse(data)
        if batch.get("id") != m.group(2) or batch.get("event_open_ms") != int(m.group(1)):
            raise ExplorationStoreHold("G3_STORE_EVENT_ID_MISMATCH")
        return batch

    def replay(self) -> tuple[dict, ...]:
        fd=self._dirfd()
        try:
            files=self._scan()
            events=set()
            receipts=[]
            for name in sorted(files):
                body=self._read(name)
                key=body["event_open_ms"]
                if key in events:
                    raise ExplorationStoreHold("G3_STORE_CONFLICTING_EVENT")
                events.add(key)
                receipts.append(body)
            return tuple(receipts)
        finally:
            os.close(fd)

    def append(self, batch: ExplorationBatch) -> str:
        if type(batch) is not ExplorationBatch:
            raise ValueError("G3_STORE_BATCH_INVALID")
        body=batch.as_record()
        encoded=_canon({"schema":RECEIPT_SCHEMA,
                        "sha256":hashlib.sha256(_canon(body)).hexdigest(),
                        "batch":body})
        # Reparse before saving: enforce the same rules on writer and reader.
        _parse(encoded)
        if len(encoded)>MAX_RECORD_BYTES:
            raise ExplorationStoreHold("G3_STORE_RECORD_TOO_LARGE")
        compressed=gzip.compress(encoded,compresslevel=6,mtime=0)
        if len(compressed)>MAX_COMPRESSED_BYTES:
            raise ExplorationStoreHold("G3_STORE_RECEIPT_TOO_LARGE")
        name=f"g3_{batch.event_open_ms:016d}_{batch.batch_id}.json.gz"
        fd=self._dirfd()
        try:
            files=self._scan()
            # Refuse if another event record in the same exact candle
            # exists under a conflicting policy, hash or source.
            conflicting=[name2 for name2 in files
                         if name2.split("_")[1] == f"{batch.event_open_ms:016d}"
                         and name2 != name]
            if conflicting:
                raise ExplorationStoreHold("G3_STORE_CONFLICTING_EVENT")
            if name in files:
                if self._read(name) != body:
                    raise ExplorationStoreHold("G3_STORE_DUPLICATE_CONFLICT")
                old=os.open(self.directory/name,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
                try:
                    os.fsync(old)
                    os.fsync(fd)
                finally:
                    os.close(old)
                return name
            if sum(files.values())+len(compressed)>self.budget_bytes:
                raise ExplorationStoreHold("G3_STORE_QUOTA_FULL")
            out=os.open(self.directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL
                        |getattr(os,"O_NOFOLLOW",0),0o600)
            try:
                buf=memoryview(compressed)
                while buf:
                    n=os.write(out,buf)
                    if n<=0:
                        raise OSError("G3_STORE_PARTIAL_WRITE")
                    buf=buf[n:]
                os.fsync(out)
                os.fsync(fd)
            finally:
                os.close(out)
            return name
        finally:
            os.close(fd)
