"""G4 bounded RAM ingestion -> lossless, compressed, hash-chained segments.

No SQLite inserts per WebSocket frame. Each finalized segment is fsynced and
atomically published with a manifest. All original bytes survive *committed*
checkpoints. The unflushed RAM tail does not: after an unclean restart the
next route epoch records ABRUPT_RESTART_HOLD and no continuity is inferred.

This is a raw source recorder, NOT a G4 science verifier or executable fill.
The existing original-G4 quote/path consumers still require independently
validated replay adapters; this format does not bypass their HOLD gates.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path

from nbot.v5.g4_forward_stream_contract import (
    forward_stream_endpoints, verify_frame,
)

VERSION = "NBOT_V5_G4_COMPRESSED_SEGMENT_V1"
ROUTES = frozenset(("market_aggtrade", "public_bookticker", "market_markprice"))
ZERO = "0" * 64
MAX_RAW_FRAME = 32768
MAX_SEGMENT_UNCOMPRESSED = 8 * 1024 * 1024


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hold(code):
    raise ValueError("G4_SEGMENT_" + code)


def _durable_publish(path, payload):
    if path.exists() or path.is_symlink():
        hold("EXISTING_SEGMENT")
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists() or tmp.is_symlink():
        hold("ORPHAN_TMP_FILE")
    with tmp.open("xb") as output:
        os.chmod(tmp, 0o600)
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    os.replace(tmp, path)
    directory = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_segments(root, expected_cohort=None):
    """Independent, bounded decompression and byte-for-byte SHA replay.

    Refuse unexpected/orphan/partial files. Yield dictionaries only *after*
    the full segment and its manifest have passed verification.
    """
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
        hold("ROOT_UNSAFE")
    entries = sorted(p for p in root.iterdir() if p.is_file() or p.is_symlink())
    for entry in entries:
        if entry.is_symlink() or entry.name.endswith(".tmp"):
            hold("SYMLINK_OR_ORPHAN")
    header = root / "cohort.json"
    if not header.is_file():
        hold("COHORT_MISSING")
    try:
        cohort = json.loads(header.read_bytes())
    except (OSError, ValueError, UnicodeError):
        hold("COHORT_CORRUPT")
    symbols = cohort.get("symbols") if isinstance(cohort, dict) else None
    if (not isinstance(symbols, list) or
            cohort != {"version": VERSION, "symbols": symbols,
                       "cohort_sha": sha(canonical({"version": VERSION, "symbols": symbols}))}
            or symbols != sorted(set(symbols)) or not 1 <= len(symbols) <= 50
            or "BTCUSDT" not in symbols):
        hold("COHORT_INVALID")
    if expected_cohort is not None and symbols != list(expected_cohort):
        hold("COHORT_CONFLICT")
    data = sorted(p for p in entries if p.name.startswith("segment-") and p.suffix == ".gz")
    metas = sorted(p for p in entries if p.name.startswith("segment-") and p.suffix == ".json")
    expected_files = {header}
    for i in range(1, len(data) + 1):
        expected_files |= {root / f"segment-{i:08d}.gz",
                           root / f"segment-{i:08d}.json"}
    if len(data) != len(metas) or set(entries) != expected_files:
        hold("ORPHAN_OR_MISSING_SEGMENT")
    prior_segment = prior_receipt = ZERO
    seq = 0
    last_route = {}
    counts = {"FRAME": 0, "OPEN": 0, "CLOSED": 0, "ABRUPT_RESTART_HOLD": 0}
    for i in range(1, len(data) + 1):
        name = f"segment-{i:08d}"
        meta = json.loads((root / (name + ".json")).read_bytes())
        payload = (root / (name + ".gz")).read_bytes()
        if len(payload) > MAX_SEGMENT_UNCOMPRESSED or (
                meta.get("segment_index") != i or
                meta.get("prior_segment_sha") != prior_segment or
                meta.get("compressed_sha") != sha(payload) or
                meta.get("first_seq") != seq + 1 or
                meta.get("cohort_sha") != cohort["cohort_sha"]):
            hold("SEGMENT_MANIFEST_INVALID")
        body = {key: value for key, value in meta.items() if key != "manifest_sha"}
        if meta.get("manifest_sha") != sha(canonical(body)):
            hold("MANIFEST_SHA_MISMATCH")
        try:
            decompressor = gzip.GzipFile(fileobj=__import__("io").BytesIO(payload))
            raw_data = decompressor.read(MAX_SEGMENT_UNCOMPRESSED + 1)
            decompressor.close()
        except (EOFError, OSError, ValueError):
            hold("SEGMENT_DECOMPRESSION_INVALID")
        if len(raw_data) > MAX_SEGMENT_UNCOMPRESSED or (
                meta.get("uncompressed_sha") != sha(raw_data)):
            hold("SEGMENT_CONTENT_INVALID")
        lines = raw_data.splitlines()
        if not lines:
            hold("SEGMENT_EMPTY")
        batch = []
        for line in lines:
            try:
                record = json.loads(line)
                if line != canonical(record) or set(record) != {
                    "seq", "route", "epoch", "kind", "at_ms", "symbol",
                    "state", "reasons", "raw_b64", "raw_sha", "prior_sha", "chain_sha"}:
                    hold("RECORD_FORMAT_INVALID")
                raw = base64.b64decode(record["raw_b64"], validate=True)
                body = {key: value for key, value in record.items() if key != "chain_sha"}
                if (len(raw) > MAX_RAW_FRAME or record["raw_sha"] != sha(raw)
                        or record["prior_sha"] != prior_receipt or
                        record["chain_sha"] != sha(canonical(body)) or
                        record["seq"] != seq + 1 or record["route"] not in ROUTES
                        or record["kind"] not in counts or
                        type(record["at_ms"]) is not int or record["at_ms"] <= 0):
                    hold("RECORD_CHAIN_INVALID")
                previous = last_route.get(record["route"])
                if previous and record["at_ms"] < previous["at_ms"]:
                    hold("ROUTE_CLOCK_REWIND")
                if record["kind"] == "OPEN":
                    if (previous and previous["kind"] not in
                            ("CLOSED", "ABRUPT_RESTART_HOLD")):
                        hold("MISSING_RESTART_HOLD_MARKER")
                    if record["epoch"] != (previous["epoch"] + 1 if previous else 1):
                        hold("EPOCH_SEQUENCE_INVALID")
                elif not previous or record["epoch"] != previous["epoch"]:
                    hold("EPOCH_SEQUENCE_INVALID")
                elif (record["kind"] == "ABRUPT_RESTART_HOLD"
                      and previous["kind"] not in ("OPEN","FRAME")):
                    hold("RESTART_MARKER_OUT_OF_PLACE")
                elif (record["kind"] in ("CLOSED","FRAME")
                      and previous["kind"] not in ("OPEN","FRAME")):
                    hold("FRAME_OR_CLOSE_WITHOUT_ROUTE")
                if record["kind"] == "FRAME" and len(raw) == 0:
                    hold("EMPTY_FRAME")
                if record["kind"] != "FRAME" and raw:
                    hold("MARKER_HAS_FRAME")
                last_route[record["route"]] = record
                counts[record["kind"]] += 1
                prior_receipt = record["chain_sha"]
                seq += 1
                batch.append((record, raw))
            except (KeyError, TypeError, ValueError, UnicodeError) as exc:
                if str(exc).startswith("G4_SEGMENT_"):
                    raise
                hold("CORRUPT_RECEIPT")
        if seq != meta.get("last_seq") or prior_receipt != meta.get("last_receipt_sha"):
            hold("SEGMENT_TAIL_INVALID")
        prior_segment = meta["manifest_sha"]
        for record, raw in batch:
            yield record, raw


class SegmentedForwardSource:
    """Single-owner source recorder with a strict bounded unflushed RAM tail."""

    flush_interval_seconds = 5.0

    def __init__(self, root, *, symbols, max_pending_bytes=2*1024*1024,
                 max_pending_frames=2048, max_disk_bytes=256*1024*1024):
        if (type(max_pending_bytes) is not int or
                not 32768 <= max_pending_bytes <= MAX_SEGMENT_UNCOMPRESSED or
                type(max_pending_frames) is not int or
                not 1 <= max_pending_frames <= 8192 or
                type(max_disk_bytes) is not int or
                not 65536 <= max_disk_bytes <= 8*1024**3):
            hold("RESOURCE_BOUNDS_INVALID")
        self.root = Path(root)
        if (self.root.is_symlink() or not self.root.is_dir()
                or self.root.stat().st_mode & 0o077):
            hold("ROOT_UNSAFE")
        syms = list(forward_stream_endpoints(symbols)["cohort_symbols"])
        header = {"version": VERSION, "symbols": syms,
                  "cohort_sha": sha(canonical({"version": VERSION, "symbols": syms}))}
        if not (self.root / "cohort.json").exists():
            if any(self.root.iterdir()):
                hold("UNKNOWN_ORPHAN_FILES")
            _durable_publish(self.root / "cohort.json", canonical(header))
        self.max_pending_bytes = max_pending_bytes
        self.max_pending_frames = max_pending_frames
        self.max_disk_bytes = max_disk_bytes
        self.symbols = syms
        self.pending = []
        self.pending_bytes = 0
        self.total_written = 0
        self.seq = 0
        self.head = ZERO
        self.segment_head = ZERO
        self.segment_count = 0
        self.by_route = {}
        self.by_symbol = {}
        previous = ZERO
        for record, raw in read_segments(self.root, syms):
            self.seq = record["seq"]
            self.head = record["chain_sha"]
            self.by_route[record["route"]] = record
            if record["kind"] == "FRAME" and record["symbol"] is not None:
                self.by_symbol[(record["route"], record["symbol"])] = (record, raw)
            elif record["kind"] == "OPEN":
                self.by_symbol = {k: v for k, v in self.by_symbol.items()
                                  if k[0] != record["route"]}
        manifests = sorted(self.root.glob("segment-*.json"))
        if manifests:
            self.segment_head = json.loads(manifests[-1].read_bytes())["manifest_sha"]
            self.segment_count = len(manifests)
        self.total_written = sum(p.stat().st_size for p in self.root.iterdir())

    def _last(self, route):
        state = self.by_route.get(route)
        if state is None:
            return None
        return (state["seq"], route, state["epoch"], state["kind"], state["at_ms"])

    def _append(self, route, kind, at_ms, *, symbol=None, raw=b"",
                state="HOLD", reasons=()):
        if (route not in ROUTES or kind not in (
                "FRAME", "OPEN", "CLOSED", "ABRUPT_RESTART_HOLD")
                or type(at_ms) is not int or at_ms <= 0
                or type(raw) is not bytes or len(raw) > MAX_RAW_FRAME):
            hold("INPUT_INVALID")
        last = self.by_route.get(route)
        if last and at_ms < last["at_ms"]:
            hold("ROUTE_CLOCK_REWIND")
        epoch = (last["epoch"]+1 if last else 1) if kind == "OPEN" else (
            last["epoch"] if last else 0)
        if epoch < 1:
            hold("ROUTE_NOT_OPEN")
        seq = self.seq + 1
        body = {
            "seq": seq, "route": route, "epoch": epoch, "kind": kind,
            "at_ms": at_ms, "symbol": symbol, "state": state,
            "reasons": list(sorted(set(reasons))),
            "raw_b64": base64.b64encode(raw).decode("ascii"), "raw_sha": sha(raw),
            "prior_sha": self.head}
        rec = {**body, "chain_sha": sha(canonical(body))}
        encoded = canonical(rec) + b"\n"
        if len(encoded) > MAX_SEGMENT_UNCOMPRESSED:
            hold("ENCODED_FRAME_OVERSIZE")
        if self.pending and self.pending_bytes + len(encoded) > self.max_pending_bytes:
            self.flush()
        if len(encoded) > self.max_pending_bytes:
            hold("FRAME_EXCEEDS_RAM_BUDGET")
        self.pending.append(encoded)
        self.pending_bytes += len(encoded)
        self.seq = seq
        self.head = rec["chain_sha"]
        self.by_route[route] = rec
        if kind == "OPEN":
            self.by_symbol = {k: v for k, v in self.by_symbol.items()
                              if k[0] != route}
        if kind == "FRAME" and symbol is not None:
            self.by_symbol[(route, symbol)] = (rec, raw)
        if len(self.pending) >= self.max_pending_frames or kind != "FRAME":
            self.flush()
        return rec

    def connect(self, *, route, at_ms):
        if route not in ROUTES:
            hold("UNKNOWN_ROUTE")
        old = self.by_route.get(route)
        if old and old["kind"] not in ("CLOSED", "ABRUPT_RESTART_HOLD"):
            self._append(route, "ABRUPT_RESTART_HOLD", at_ms,
                         reasons=("UNKNOWN_LOSS_AFTER_LAST_COMMITTED_CHECKPOINT",))
        return self._append(route, "OPEN", at_ms,
                            reasons=("INITIAL_EPOCH_CONTINUITY_UNPROVEN",))

    def disconnect(self, *, route, at_ms):
        last = self.by_route.get(route)
        if not last or last["kind"] not in ("FRAME", "OPEN"):
            hold("ROUTE_NOT_CONNECTED")
        return self._append(route, "CLOSED", at_ms,
                            reasons=("SOURCE_DISCONNECTED",))

    def ingest(self, *, route, at_ms, raw):
        last = self.by_route.get(route)
        if route not in ROUTES or not last or last["kind"] not in ("OPEN", "FRAME"):
            hold("ROUTE_NOT_CONNECTED")
        if type(raw) is not bytes or len(raw) > MAX_RAW_FRAME:
            hold("FRAME_SIZE_INVALID")
        sym = None
        try:
            envelope = json.loads(raw)
            if isinstance(envelope, dict):
                data = envelope.get("data")
                if isinstance(data, dict):
                    sym = data.get("s")
        except (ValueError, UnicodeError):
            pass
        if sym not in self.symbols:
            sym = None
        prev = self.by_symbol.get((route, sym))
        reasons = []
        prior_agg = prior_trade = None
        if prev and prev[0]["state"] != "SOURCE_RECORDED":
            reasons.append("PRIOR_SYMBOL_SOURCE_HELD")
        if prev and prev[1] == raw:
            reasons.append("DUPLICATE_RAW_FRAME")
        if route == "market_aggtrade" and prev:
            try:
                past = json.loads(prev[1])["data"]
                prior_agg, prior_trade = past.get("a"), past.get("l")
            except (KeyError, ValueError, TypeError, UnicodeError):
                reasons.append("PRIOR_AGGTRADE_INVALID")
        try:
            verified = verify_frame(route=route, raw=raw, received_at_ms=at_ms,
                                    source_epoch=last["epoch"],
                                    selected_symbols=self.symbols,
                                    prior_agg_id=prior_agg,
                                    prior_last_trade_id=prior_trade)
            reasons.extend(verified.reasons)
            state = verified.state
        except (ValueError, UnicodeError, TypeError):
            reasons.append("MALFORMED_OR_INVALID_FRAME")
            state = "HOLD"
        if reasons:
            state = "HOLD"
        return self._append(route, "FRAME", at_ms, symbol=sym, raw=raw,
                            state=state, reasons=reasons)

    def flush(self):
        """Exactly one durable compressed segment per full RAM checkpoint."""
        if not self.pending:
            return
        data = b"".join(self.pending)
        if len(data) > MAX_SEGMENT_UNCOMPRESSED:
            hold("UNCOMPRESSED_SEGMENT_OVERFLOW")
        zipped = gzip.compress(data, compresslevel=3, mtime=0)
        number = self.segment_count + 1
        name = f"segment-{number:08d}"
        head = json.loads(self.pending[-1])["chain_sha"]
        start = json.loads(self.pending[0])["seq"]
        meta = {
            "segment_index": number, "first_seq": start, "last_seq": self.seq,
            "cohort_sha": sha(canonical({"version": VERSION, "symbols": self.symbols})),
            "prior_segment_sha": self.segment_head,
            "compressed_sha": sha(zipped), "uncompressed_sha": sha(data),
            "last_receipt_sha": head}
        meta["manifest_sha"] = sha(canonical(meta))
        encoded = canonical(meta)
        if self.total_written + len(zipped) + len(encoded) > self.max_disk_bytes:
            hold("ARCHIVE_DISK_CAP_HOLD")
        _durable_publish(self.root / (name + ".gz"), zipped)
        _durable_publish(self.root / (name + ".json"), encoded)
        self.segment_head = meta["manifest_sha"]
        self.segment_count = number
        self.total_written += len(zipped) + len(encoded)
        self.pending.clear()
        self.pending_bytes = 0

    def audit(self):
        """Independently reread all flushed segments before source reporting."""
        if self.pending:
            hold("UNFLUSHED_AUDIT_UNAVAILABLE")
        counts = {"OPEN": 0, "FRAME": 0, "CLOSED": 0, "ABRUPT_RESTART_HOLD": 0}
        recorded = held = 0
        last_head = ZERO
        for record, raw in read_segments(self.root, self.symbols):
            counts[record["kind"]] += 1
            if record["kind"] == "FRAME":
                if record["state"] == "SOURCE_RECORDED":
                    recorded += 1
                else:
                    held += 1
            last_head = record["chain_sha"]
        return {"audit": "PASS", "source_contract": VERSION,
                "frozen_cohort": len(self.symbols), "counts": counts,
                "frames_verified": recorded, "frames_held": held,
                "source_grade": "ORIGINAL_WSS_SEGMENT_NOT_YET_SCIENCE_QUALIFIED",
                "head_sha256": last_head,
                "economic_outcomes": 0, "order_authority": "NONE",
                "model_training_authority": "NONE"}
