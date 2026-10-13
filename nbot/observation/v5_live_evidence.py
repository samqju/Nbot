"""Opt-in public USD-M evidence bridge. Research only; no execution client.

Every accepted mutation commits a chained audit event; periodic bounded
checkpoints accelerate replay. Network gaps never become reconstructed quotes.
The legacy tick-only lab retains its original contract and digest version.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from copy import deepcopy
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time

from .v5_accounting import FundingSettlement, TradeAccounting
from .v5_paired_exits import (
    PairedEntry, PairedExitLab, ArmResult, _Arm, _encode,
    MAX_RECEIPT_DELAY_MS, HORIZON_CLOSE_GRACE_MS,
)

from .v5_evidence_trust import CONTRACT, observed_costs

VERSION = "NBOT_V5_JOINT_EVIDENCE_V3"
CHECKPOINT_INTERVAL = 128
MAX_DEPTH_BUFFER_BYTES = 2 * 1024 * 1024
ORDER_AUTHORITY = "NONE"
MAX_SYMBOLS = 20
MAX_LEVELS = 5000
MAX_BUFFER = 2000
MAX_DB_BYTES = 256 * 1024 * 1024
MAX_FUNDING_EVENTS = 1000
FUNDING_GRACE_MS = 60_000
# bookTicker is event-driven, not a continuous heartbeat. When loss cannot
# be distinguished from legitimate silence, reject observed simulation.
MAX_BOOKTICKER_SILENCE_MS = 30_000


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("V5_EVIDENCE_INTEGER_INVALID")
    return value


def number(value, *, zero=False):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("V5_EVIDENCE_NUMBER_INVALID") from exc
    if not result.is_finite() or result < 0 or (not zero and result == 0):
        raise ValueError("V5_EVIDENCE_NUMBER_INVALID")
    return result


def symbol_name(value):
    if (not isinstance(value, str) or not value.isascii()
            or not value.isalnum() or value != value.upper()):
        raise ValueError("V5_EVIDENCE_SYMBOL_INVALID")
    return value


class _Chain:
    """Versioned resumable hash chain, rather than pickled hashlib internals."""
    def __init__(self, value=None):
        self.value = value or hashlib.sha256(VERSION.encode()).hexdigest()

    def update(self, raw):
        self.value = hashlib.sha256(bytes.fromhex(self.value) + raw).hexdigest()

    def hexdigest(self):
        return self.value


class JointExitLab(PairedExitLab):
    """Trade continuity and executable quote triggers are distinct events.

Strict transaction-time ordering is conservative across independent sockets:
late or reversed events invalidate a sample; they are never reordered using
future quotes. bookTicker update IDs are NOT a consecutive trade sequence.
"""
    def finalize(self, *_args, **_kwargs):
        raise RuntimeError('V5_JOINT_FINALIZATION_REQUIRES_TRUST_BRIDGE')

    def add(self, entry):
        super().add(entry)
        path = self._paths[entry.decision_id]
        path.digest = _Chain()
        path.digest.update(_encode({"v": VERSION, "entry": asdict(entry)}))
        path.joint_time = entry.entry_time_ms
        path.quote = None
        path.depth_watermark = None
        path.ticker_last_time = entry.entry_quote_time_ms
        path.ticker_events = 0

    def event(self, symbol, row, receipt, *, trade=False, depth_watermark=None,
              source=None):
        timestamp = integer(row["T"])
        for decision in tuple(self._by_symbol.get(symbol, ())):
            path = self._paths[decision]
            if path.gap_reason:
                continue
            if timestamp > path.deadline + HORIZON_CLOSE_GRACE_MS and path.horizon_witnessed:
                continue
            if (timestamp < path.joint_time or receipt < timestamp
                    or receipt - timestamp > MAX_RECEIPT_DELAY_MS):
                path.gap_reason = "JOINT_EVENT_LATE_OR_REVERSED"
                continue
            if timestamp - path.ticker_last_time > MAX_BOOKTICKER_SILENCE_MS:
                path.gap_reason = "BOOKTICKER_COVERAGE_GAP"
                continue
            if timestamp <= path.entry.entry_time_ms:
                path.gap_reason = "JOINT_ENTRY_BOUNDARY_AMBIGUOUS"
                continue
            if timestamp > path.deadline + HORIZON_CLOSE_GRACE_MS:
                path.gap_reason = "HORIZON_CLOSE_WITNESS_MISSING"
                continue
            if trade:
                if row["a"] != path.last_agg_id + 1:
                    path.gap_reason = "WSS_GAP"
                    continue
                path.last_agg_id = row["a"]
                path.last_trade_time_ms = timestamp
            else:
                if (path.last_quote_update_id is not None
                        and row["u"] < path.last_quote_update_id):
                    path.gap_reason = "JOINT_QUOTE_ID_REVERSED"
                    continue
                # An identical second source quote at the same timestamp adds
                # provenance, but cannot ratchet a trailing stop twice.
                quote = (timestamp, row["b"], row["a"])
                if path.quote and timestamp == path.quote[0] and quote != path.quote:
                    path.gap_reason = "JOINT_QUOTE_ORDER_AMBIGUOUS"
                    continue
                if quote != path.quote:
                    px = float(row["b"] if path.entry.side == "LONG" else row["a"])
                    for arm in path.arms.values():
                        arm.apply(time_ms=timestamp, price=px, entry=path.entry,
                                  horizon=timestamp >= path.deadline)
                    path.quote = quote
                path.last_quote_update_id = row["u"]
                if source == "bookTicker":
                    path.ticker_last_time = timestamp
                    path.ticker_events += 1
            path.joint_time = timestamp
            if depth_watermark:
                path.depth_watermark = depth_watermark
            path.digest.update(_encode({"row": row, "receipt": receipt, "trade": trade}))
            path.events_seen += 1
            # A horizon quote needs a trade-stream watermark at or beyond it.
            # Silence alone is not proof of continuous aggregate history.
            if (path.quote and path.quote[0] >= path.deadline
                    and path.last_trade_time_ms >= path.quote[0]
                    and path.ticker_last_time >= path.deadline - MAX_BOOKTICKER_SILENCE_MS
                    and path.depth_watermark
                    and path.depth_watermark[0] >= path.last_quote_update_id
                    and path.depth_watermark[1] >= path.quote[0]):
                path.horizon_witnessed = True

    def dump(self):
        paths = {}
        for key, p in self._paths.items():
            paths[key] = {"entry": asdict(p.entry),
                          "arms": {k: asdict(a) for k, a in p.arms.items()},
                          "digest": p.digest.hexdigest(),
                          **{k: getattr(p, k) for k in (
                              "last_agg_id", "last_trade_time_ms", "last_quote_update_id",
                              "events_seen", "horizon_witnessed", "gap_reason",
                              "joint_time", "quote", "depth_watermark",
                              "ticker_last_time", "ticker_events")}}
        return {"paths": paths, "completed": {
            k: [asdict(r) for r in rows] for k, rows in self._completed.items()}}

    @classmethod
    def restore(cls, state):
        lab = cls()
        for key, data in state["paths"].items():
            lab.add(PairedEntry(**data["entry"]))
            p = lab._paths[key]
            p.arms = {k: _Arm(**a) for k, a in data["arms"].items()}
            p.digest = _Chain(data["digest"])
            for name, value in data.items():
                if name not in ("entry", "arms", "digest"):
                    setattr(p, name, tuple(value) if name in ("quote", "depth_watermark") and value else value)
        for key, rows in state["completed"].items():
            output = []
            for row in rows:
                row = dict(row)
                if row["accounting"]:
                    a = dict(row["accounting"])
                    a["funding_settlements"] = tuple(
                        FundingSettlement(**x) for x in a["funding_settlements"])
                    row["accounting"] = TradeAccounting(**a)
                output.append(ArmResult(**row))
            lab._completed[key] = tuple(output)
        return lab


class LiveEvidenceBridge:
    """Synchronous single-writer bridge. Construction has no I/O.

Call initialize explicitly before use. CAS checkpoint writes reject concurrent
owners. On database failure state rolls back and a nonrollbackable fault latch
blocks use until explicit invalidating recovery. No certified path is produced.
"""
    def __init__(self, path=Path("data/observation/v5/live_evidence_v3.db"), *, symbols, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: time.time_ns() // 1_000_000)
        if self.path.resolve().parent.name.lower() != "v5":
            raise ValueError("V5_EVIDENCE_PATH_REQUIRED")
        self.symbols = tuple(sorted(set(symbol_name(s) for s in symbols)))
        if not 0 < len(self.symbols) <= MAX_SYMBOLS:
            raise ValueError("V5_EVIDENCE_UNIVERSE_INVALID")
        self.lab = JointExitLab()
        self.feeds = {s: self._fresh() for s in self.symbols}
        self.funding = {}
        self.seq = 0
        self.ready = False
        self.integrity_fault = None
        self.chain = hashlib.sha256(VERSION.encode()).hexdigest()
        self._replaying = False
        self._event = None
        self._lock = threading.RLock()

    @staticmethod
    def _fresh():
        return {"agg": None, "trade": None, "bids": {}, "asks": {},
                "depth_id": None, "synced": False, "buffer": [],
                "ticker": None, "quote": None, "depth_quote": None,
                "connected": False, "trade_receipt": None,
                "quote_receipt": None, "ticker_receipt": None,
                "depth_receipt": None, "synced_since": None,
                "snapshot_completed": None, "book_available": None,
                "validation_available": None, "last_receipt": None,
                "source_receipts": {"aggTrade": None, "bookTicker": None,
                                    "depthUpdate": None}}

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            conn.execute("PRAGMA synchronous=FULL")
            with conn:
                yield conn
        finally:
            conn.close()

    def _dump(self):
        return {"version": VERSION, "symbols": self.symbols, "lab": self.lab.dump(),
                "feeds": self.feeds, "funding": self.funding}

    def _restore(self, state):
        if state["version"] != VERSION or tuple(state["symbols"]) != self.symbols:
            raise ValueError("V5_EVIDENCE_CONTRACT_MISMATCH")
        self.lab = JointExitLab.restore(state["lab"])
        self.feeds, self.funding = state["feeds"], state["funding"]

    def initialize(self):
        """Reject legacy DBs; verify the entire journal before replaying its tail."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoint'").fetchone():
                prior = conn.execute('SELECT state,digest FROM checkpoint WHERE id=1').fetchone()
                if prior:
                    if hashlib.sha256(prior[0].encode()).hexdigest() != prior[1]:
                        raise ValueError('V5_CHECKPOINT_CORRUPT')
                    if json.loads(prior[0]).get('version') != VERSION:
                        raise ValueError('V5_EVIDENCE_CONTRACT_MISMATCH')
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoint(
                    id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL,
                    state TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS journal(
                    seq INTEGER PRIMARY KEY, event TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS decision_ids(
                    decision_id TEXT PRIMARY KEY, entry TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS journal_head(
                    id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL,
                    digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revocations(
                    seq INTEGER NOT NULL, decision_id TEXT NOT NULL, reason TEXT NOT NULL,
                    PRIMARY KEY(seq,decision_id,reason));
                CREATE TABLE IF NOT EXISTS published_windows(
                    decision_id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
                    start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
                    payload TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS published_by_time
                    ON published_windows(symbol,start_ms,end_ms);
            """)
            for table in ("decision_ids", "journal", "revocations", "published_windows"):
                for op in ("update", "delete"):
                    conn.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table} "
                                 "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_AUDIT'); END")
            row = conn.execute("SELECT seq,state,digest FROM checkpoint WHERE id=1").fetchone()
            checkpoint_seq = 0
            if row:
                if hashlib.sha256(row[1].encode()).hexdigest() != row[2]:
                    raise ValueError("V5_CHECKPOINT_CORRUPT")
                state = json.loads(row[1])
                self._restore(state)  # V1/V2 contract mismatch; never silently migrate.
                checkpoint_seq = row[0]
            head = conn.execute("SELECT seq,digest FROM journal_head WHERE id=1").fetchone()
            tail = []
            expected_revocations = []
            expected_pairs = {}
            expected_entries = {}
            sequence = 0
            checkpoint_chain = None
            chain = hashlib.sha256(VERSION.encode()).hexdigest()
            for seq, raw, digest in conn.execute("SELECT seq,event,digest FROM journal ORDER BY seq"):
                chain = hashlib.sha256(bytes.fromhex(chain) + raw.encode()).hexdigest()
                if seq != sequence + 1 or digest != chain:
                    raise ValueError("V5_JOURNAL_CORRUPT_OR_TRUNCATED")
                event = json.loads(raw)
                if event['kind'] == 'ENTRY':
                    expected_entries[event['entry']['decision_id']] = _encode(event['entry']).decode()
                if event.get('pair'):
                    expected_pairs.setdefault(event['decision'], _encode(event['pair']).decode())
                expected_revocations.extend((seq, r['decision'], r['reason'])
                                            for r in event.get('revocations', []))
                if event.get("version") != VERSION:
                    raise ValueError("V5_EVIDENCE_CONTRACT_MISMATCH")
                sequence = seq
                if seq == checkpoint_seq:
                    checkpoint_chain = chain
                if seq > checkpoint_seq:
                    tail.append(event)
            if (sequence and head != (sequence, chain)) or (not sequence and head):
                raise ValueError("V5_JOURNAL_HEAD_MISMATCH")
            if checkpoint_seq > sequence or (row and state.get("journal_chain") != checkpoint_chain):
                raise ValueError("V5_CHECKPOINT_JOURNAL_MISMATCH")
            actual = conn.execute('SELECT seq,decision_id,reason FROM revocations ORDER BY seq,decision_id,reason').fetchall()
            if sorted(set(expected_revocations)) != actual:
                raise ValueError('V5_REVOCATION_JOURNAL_MISMATCH')
            actual_pairs = dict(conn.execute('SELECT decision_id,payload FROM published_windows'))
            if actual_pairs != expected_pairs:
                raise ValueError('V5_PUBLISHED_PAIR_JOURNAL_MISMATCH')
            if dict(conn.execute('SELECT decision_id,entry FROM decision_ids')) != expected_entries:
                raise ValueError('V5_DECISION_JOURNAL_MISMATCH')
            for decision,symbol,start,end in conn.execute('SELECT decision_id,symbol,start_ms,end_ms FROM published_windows'):
                entry = json.loads(expected_entries[decision])
                if (symbol,start,end) != (entry['symbol'], entry['entry_time_ms'],
                                         entry['entry_time_ms'] + entry['horizon_ms'] + HORIZON_CLOSE_GRACE_MS):
                    raise ValueError('V5_PUBLISHED_WINDOW_JOURNAL_MISMATCH')
            for payload,digest in conn.execute('SELECT payload,digest FROM published_windows'):
                if hashlib.sha256(payload.encode()).hexdigest() != digest:
                    raise ValueError('V5_PUBLISHED_PAIR_CORRUPT')
            self.seq, self.chain = sequence, chain
        self._replaying = True
        try:
            for event in tail:
                self._replay(event)
        finally:
            self._replaying = False
        self.ready = True
        self._change({"kind": "PROCESS_RESTART"}, self._restart)

    def _replay(self, e):
        kind = e["kind"]
        if kind == "WSS":
            r = e["payload"].get("data", e["payload"])
            self._ingest(r["s"], r["e"], r, e["receipt"])
        elif kind == "CONNECTED":
            self.feeds[e["symbol"]]["connected"] = True
        elif kind == "ENTRY":
            self.lab.add(PairedEntry(**e["entry"]))
        elif kind == "DEPTH_SNAPSHOT":
            self.snapshot(e["symbol"], e["payload"], e["receipt"])
        elif kind == "REST_AGG_RECOVERY":
            f = self.feeds[e["symbol"]]
            for raw in e["rows"]:
                r = self._trade(raw)
                if r["a"] > e["through"]:
                    break
                f["agg"], f["trade"] = r["a"], r
        elif kind == "FUNDING_RECONCILED":
            self.funding[e["key"]] = e["proof"]
        elif kind == 'FUNDING_READ_PENDING':
            pass
        elif kind == "FUNDING_REVOKED":
            for key in e["keys"]:
                self.funding[key]["state"] = "REVOKED"
                self.funding[key]["contradiction"] = e["observations"]
        elif kind == "FINALIZE":
            self.finalize(e["decision"], now_ms=e["now"], funding_key=e["funding_key"])
        elif kind == "LEDGER_ACK":
            self.lab.acknowledge_persisted(e["decision"])
        elif kind in ("PROCESS_RESTART", "INTEGRITY_RECOVERY"):
            self._restart()
        else:
            self.disconnect(e["symbol"], kind)
        for revocation in e.get("revocations", []):
            self._revoke_pending(revocation["decision"], revocation["reason"])

    def _restart(self):
        for symbol in self.symbols:
            # No clean source-close barrier exists. A new process cannot know
            # whether its predecessor lost an event or a fault marker.
            self._quarantine(symbol, 'PROCESS_RESTART_UNCERTAIN_CONTINUITY')
            # A horizon witness never establishes final source closure.
            for decision in self.lab._by_symbol.get(symbol, ()):
                self.lab._paths[decision].gap_reason = "PROCESS_RESTART"
            old = self.feeds[symbol]
            fresh = self._fresh()
            fresh["agg"], fresh["trade"] = old["agg"], old["trade"]
            fresh["trade_receipt"] = old["trade_receipt"]
            self.feeds[symbol] = fresh

    def _revoke_pending(self, decision, reason):
        if decision in self.lab._completed:
            self.lab._completed[decision] = tuple(
                replace(r, status="REVOKED", evidence_class="REVOKED", reason=reason)
                for r in self.lab._completed[decision])
        if decision in self.lab._paths:
            self.lab._paths[decision].gap_reason = reason

    def _quarantine(self, symbol, reason, *, timestamp=None):
        if self._replaying:
            return
        with self._connect() as conn:
            entries = conn.execute("SELECT decision_id,entry FROM decision_ids").fetchall()
        for decision, raw in entries:
            entry = json.loads(raw)
            if entry["symbol"] != symbol:
                continue
            if timestamp is not None and not (entry["entry_time_ms"] <= timestamp <=
                    entry["entry_time_ms"] + entry["horizon_ms"] + HORIZON_CLOSE_GRACE_MS):
                continue
            self._event.setdefault("revocations", []).append({"decision": decision, "reason": reason})
            self._revoke_pending(decision, reason)

    def revocations(self, decision):
        with self._lock, self._connect() as conn:
            if self.integrity_fault is not None or not self.ready:
                raise RuntimeError('V5_REVOCATION_AUTHORITY_UNAVAILABLE')
            head = conn.execute('SELECT seq,digest FROM journal_head WHERE id=1').fetchone()
            if head != (self.seq, self.chain):
                raise RuntimeError('V5_REVOCATION_AUTHORITY_STALE')
            return conn.execute("SELECT seq,reason FROM revocations WHERE decision_id=? ORDER BY seq",
                                (decision,)).fetchall()

    def published_pair(self, decision):
        with self._lock:
            self.revocations(decision)  # current nonfaulted authority required
            with self._connect() as conn:
                row = conn.execute('SELECT payload,digest FROM published_windows WHERE decision_id=?',
                                   (decision,)).fetchone()
            if not row or hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
                raise ValueError('V5_PAIR_PROVENANCE_UNPROVEN')
            return row

    def published_entry(self, decision):
        with self._lock:
            self.revocations(decision)
            with self._connect() as conn:
                row = conn.execute('SELECT entry FROM decision_ids WHERE decision_id=?',(decision,)).fetchone()
            if not row:
                raise ValueError('V5_PAIR_PROVENANCE_UNPROVEN')
            return json.loads(row[0])

    def recover_integrity(self):
        """Explicit invalidating recovery; no exact-event replay or continuity claim."""
        with self._lock:
            if self.integrity_fault is None:
                raise ValueError("V5_NO_INTEGRITY_FAULT")
            fault = self.integrity_fault
            self.integrity_fault = None
            def action():
                for symbol in self.symbols:
                    self._quarantine(symbol, "EVIDENCE_PERSISTENCE_FAILED")
                self._restart()
            try:
                self._change({"kind": "INTEGRITY_RECOVERY", "failed_event": fault}, action)
            except BaseException:
                self.integrity_fault = fault
                raise

    def _change(self, event, action):
        if self._replaying:
            return action()
        with self._lock:
            if not self.ready:
                raise RuntimeError("V5_EVIDENCE_NOT_INITIALIZED")
            if self.integrity_fault is not None:
                raise RuntimeError("V5_EVIDENCE_INTEGRITY_FAULT")
            # Only the affected book is copied; hypotheses/funding are bounded.
            symbol = event.get("symbol")
            if event["kind"] == "WSS":
                symbol = event["payload"].get("data", event["payload"])["s"]
            keys = (symbol,) if symbol else self.symbols
            feeds = {k: deepcopy(self.feeds[k]) for k in keys}
            lab, funding = self.lab.dump(), deepcopy(self.funding)
            self._event = event
            try:
                result = action()
            except BaseException as exc:
                if isinstance(exc, (OSError, sqlite3.Error)):
                    self.integrity_fault = {"event": event, "error": type(exc).__name__}
                self.lab = JointExitLab.restore(lab)
                self.feeds.update(feeds)
                self.funding = funding
                self._event = None
                raise
            try:
                size = sum(p.stat().st_size for p in (self.path, Path(str(self.path) + "-wal")) if p.exists())
                if size >= MAX_DB_BYTES:
                    raise RuntimeError("V5_EVIDENCE_DISK_BACKPRESSURE")
                event["version"] = VERSION
                if event['kind'] == 'WSS':
                    event['evidence_class'] = 'RECEIVED_EVIDENCE'
                if event['kind'] == 'FINALIZE' and result:
                    event['pair'] = {'contract': CONTRACT, 'arms': [asdict(r) for r in result]}
                raw = _encode(event).decode()
                digest = hashlib.sha256(bytes.fromhex(self.chain) + raw.encode()).hexdigest()
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    head = conn.execute("SELECT seq,digest FROM journal_head WHERE id=1").fetchone()
                    if (head or (0, hashlib.sha256(VERSION.encode()).hexdigest())) != (self.seq, self.chain):
                        raise RuntimeError("V5_EVIDENCE_CONCURRENT_WRITER")
                    if event["kind"] == "ENTRY":
                        decision = event["entry"]["decision_id"]
                        if conn.execute("SELECT 1 FROM decision_ids WHERE decision_id=?", (decision,)).fetchone():
                            raise ValueError("V5_PAIRED_DECISION_REUSED")
                        conn.execute("INSERT INTO decision_ids VALUES(?,?)", (decision, _encode(event["entry"]).decode()))
                    if event['kind'] == 'FINALIZE' and result:
                        frozen = conn.execute('SELECT entry FROM decision_ids WHERE decision_id=?',
                                              (event['decision'],)).fetchone()
                        if frozen:
                            entry = json.loads(frozen[0])
                            pair = _encode(event['pair']).decode()
                            conn.execute('INSERT OR IGNORE INTO published_windows VALUES(?,?,?,?,?,?)',
                                         (event['decision'], entry['symbol'], entry['entry_time_ms'],
                                          entry['entry_time_ms'] + entry['horizon_ms'] + HORIZON_CLOSE_GRACE_MS,
                                          pair, hashlib.sha256(pair.encode()).hexdigest()))
                    conn.execute("INSERT INTO journal VALUES(?,?,?)", (self.seq + 1, raw, digest))
                    for r in event.get("revocations", []):
                        conn.execute("INSERT OR IGNORE INTO revocations VALUES(?,?,?)",
                                     (self.seq + 1, r["decision"], r["reason"]))
                    conn.execute("INSERT OR REPLACE INTO journal_head VALUES(1,?,?)", (self.seq + 1, digest))
                    if event["kind"] != "WSS" or (self.seq + 1) % CHECKPOINT_INTERVAL == 0:
                        state = self._dump()
                        state["journal_chain"] = digest
                        checkpoint = _encode(state).decode()
                        conn.execute("INSERT OR REPLACE INTO checkpoint VALUES(1,?,?,?)",
                                     (self.seq + 1, checkpoint, hashlib.sha256(checkpoint.encode()).hexdigest()))
                self.seq += 1
                self.chain = digest
                if symbol and event["kind"] in ("WSS", "DEPTH_SNAPSHOT"):
                    f = self.feeds[symbol]
                    f["validation_available"] = max(self.clock(), f["validation_available"] or 0)
                return result
            except BaseException as exc:
                self.lab = JointExitLab.restore(lab)
                self.feeds.update(feeds)
                self.funding = funding
                # Permanent-ID rejection is safe; uncertain commits poison use.
                if not (isinstance(exc, ValueError) and str(exc) == "V5_PAIRED_DECISION_REUSED"):
                    self.integrity_fault = {"event": event, "error": type(exc).__name__}
                raise
            finally:
                self._event = None

    def connected(self, symbol):
        self._feed(symbol)
        self._change({"kind": "CONNECTED", "symbol": symbol},
                     lambda: self.feeds[symbol].update(connected=True))

    def _feed(self, symbol):
        if symbol not in self.feeds:
            raise ValueError("V5_EVIDENCE_SYMBOL_MISMATCH")
        return self.feeds[symbol]

    def disconnect(self, symbol, reason="WSS_DISCONNECTED"):
        self._feed(symbol)
        def action():
            self._quarantine(symbol, reason)
            for decision in self.lab._by_symbol.get(symbol, ()):
                self.lab._paths[decision].gap_reason = reason
            f = self.feeds[symbol]
            f.update(connected=False, synced=False, buffer=[], depth_id=None,
                     bids={}, asks={}, quote=None, ticker=None,
                     depth_quote=None, ticker_receipt=None, depth_receipt=None,
                     synced_since=None, snapshot_completed=None, book_available=None,
                     validation_available=None, last_receipt=None,
                     source_receipts={"aggTrade": None, "bookTicker": None,
                                      "depthUpdate": None})
        self._change({"kind": reason, "symbol": symbol}, action)

    def add(self, entry):
        def action():
            f = self._feed(entry.symbol)
            q = f["quote"]
            depth = f["depth_quote"]
            ticker = f["ticker"]
            if (not f["connected"] or not f["synced"] or not q or not f["trade"]
                    or not ticker or not depth or f["ticker_receipt"] is None
                    or q != ticker or ticker["b"] != depth["b"]
                    or ticker["a"] != depth["a"]
                    or ticker["T"] < depth["T"] or ticker["u"] < depth["u"]
                    or f["depth_receipt"] is None or f["snapshot_completed"] is None
                    or f["book_available"] is None or f["validation_available"] is None
                    or entry.entry_time_ms < max(f["depth_receipt"], f["snapshot_completed"],
                                                 f["book_available"], f["validation_available"])
                    or entry.entry_time_ms - depth["T"] > MAX_RECEIPT_DELAY_MS
                    or f["quote_receipt"] is None or f["trade_receipt"] is None
                    or entry.entry_time_ms < max(f["quote_receipt"], f["trade_receipt"])
                    or entry.anchor_agg_id != f["agg"]
                    or entry.anchor_trade_time_ms != f["trade"]["T"]
                    or entry.entry_quote_time_ms != q["T"]
                    or entry.entry_bid != float(q["b"]) or entry.entry_ask != float(q["a"])):
                raise ValueError("V5_ENTRY_LIVE_ANCHOR_UNPROVEN")
            self.lab.add(entry)
        self._change({"kind": "ENTRY", "entry": asdict(entry)}, action)

    def ingest(self, payload, receipt_ms):
        integer(receipt_ms)
        if not isinstance(payload, dict):
            raise ValueError("V5_WSS_MESSAGE_INVALID")
        row = payload.get("data", payload)
        if not isinstance(row, dict):
            raise ValueError("V5_WSS_MESSAGE_INVALID")
        s = row.get("s")
        self._feed(s)
        kind = row.get("e")
        if kind not in ("aggTrade", "bookTicker", "depthUpdate"):
            raise ValueError("V5_WSS_EVENT_INVALID")
        try:
            self._change({"kind": "WSS", "receipt": receipt_ms, "payload": payload},
                         lambda: self._ingest(s, kind, row, receipt_ms))
        except (ValueError, KeyError, TypeError, OverflowError):
            self.disconnect(s, "FEED_UNCERTAIN")
            raise

    def _ingest(self, s, kind, row, receipt):
        f = self.feeds[s]
        if not f["connected"]:
            raise ValueError("V5_WSS_NOT_CONNECTED")
        t = integer(row["T"])
        if f["last_receipt"] is not None and receipt < f["last_receipt"]:
            raise ValueError("V5_RECEIPT_REVERSED")
        f["last_receipt"] = receipt
        f["validation_available"] = receipt
        if not self._replaying:
            with self._connect() as conn:
                published = conn.execute('SELECT 1 FROM published_windows WHERE symbol=? AND start_ms<=? AND end_ms>=? LIMIT 1',
                                         (s,t,t)).fetchone()
            if published:
                self._quarantine(s, "LATE_EVIDENCE_AFTER_PUBLICATION", timestamp=t)
        event_time = integer(row["E"])
        if event_time < t or receipt < event_time or receipt - t > MAX_RECEIPT_DELAY_MS:
            raise ValueError("V5_WSS_RECEIPT_STALE")
        if kind == "aggTrade":
            r = self._trade(row)
            if f["trade"] == r:
                return
            if f["agg"] is not None and (r["a"] != f["agg"] + 1
                    or r["T"] < f["trade"]["T"]):
                self.lab.invalidate_symbol(s, reason="WSS_GAP")
                # Keep cursor: explicit bounded REST recovery must close it.
                raise ValueError("V5_AGGTRADE_GAP")
            f["agg"], f["trade"] = r["a"], r
            f["trade_receipt"] = receipt
            f["source_receipts"]["aggTrade"] = receipt
            self.lab.event(s, r, receipt, trade=True)
        elif kind == "bookTicker":
            r = {"T": t, "u": integer(row["u"]),
                 "b": str(number(row["b"]).normalize()),
                 "a": str(number(row["a"]).normalize())}
            number(row["B"]); number(row["A"])
            if Decimal(r["b"]) >= Decimal(r["a"]):
                raise ValueError("V5_QUOTE_CROSSED")
            if f["ticker"] == r:
                return
            if f["ticker"] and (r["u"] <= f["ticker"]["u"] or t < f["ticker"]["T"]):
                raise ValueError("V5_TICKER_REVERSED_OR_CONFLICT")
            depth = f["depth_quote"]
            if depth and (r["T"] < depth["T"] or r["u"] < depth["u"]):
                raise ValueError("V5_TICKER_BEHIND_DEPTH")
            f["ticker"] = r
            f["ticker_receipt"] = receipt
            f["source_receipts"]["bookTicker"] = receipt
            if f["synced"]:
                f["quote"] = r
                f["quote_receipt"] = receipt
                self.lab.event(s, r, receipt, source="bookTicker")
        else:
            integer(row["U"]); integer(row["u"]); integer(row["pu"])
            if row["U"] > row["u"]:
                raise ValueError("V5_DEPTH_RANGE_INVALID")
            self._levels(row["b"]); self._levels(row["a"])
            if f["depth_id"] is None:
                if (len(f["buffer"]) >= MAX_BUFFER or
                        sum(len(_encode(x)) for x in f["buffer"]) + len(_encode(row)) > MAX_DEPTH_BUFFER_BYTES):
                    raise ValueError("V5_DEPTH_BUFFER_OVERFLOW")
                f["buffer"].append({"row": row, "receipt": receipt})
            else:
                self._depth(s, row, receipt)

    @staticmethod
    def _trade(row):
        r = {k: integer(row[k]) for k in ("a", "f", "l", "T")}
        r.update(p=str(number(row["p"]).normalize()),
                 q=str(number(row["q"]).normalize()), m=row["m"])
        if r["f"] > r["l"] or type(r["m"]) is not bool:
            raise ValueError("V5_TRADE_INVALID")
        return r

    @staticmethod
    def _levels(rows):
        if not isinstance(rows, list) or len(rows) > MAX_LEVELS:
            raise ValueError("V5_DEPTH_LEVELS_INVALID")
        levels = {}
        for price, qty in rows:
            price, qty = str(number(price).normalize()), str(number(qty, zero=True).normalize())
            if price in levels:
                raise ValueError("V5_DEPTH_LEVEL_DUPLICATE")
            levels[price] = qty
        return levels

    def snapshot(self, symbol, payload, receipt_ms):
        self._feed(symbol)
        integer(receipt_ms)
        def action():
            f = self.feeds[symbol]
            if f["synced"] or not f["connected"]:
                raise ValueError("V5_DEPTH_SNAPSHOT_NOT_REQUESTED")
            if receipt_ms < integer(payload["T"]) or receipt_ms - payload["T"] > 2000:
                raise ValueError("V5_DEPTH_SNAPSHOT_STALE")
            f["snapshot_completed"] = receipt_ms
            f["book_available"] = receipt_ms
            f["validation_available"] = max(receipt_ms, f["validation_available"] or 0)
            f["depth_id"] = integer(payload["lastUpdateId"])
            f["bids"] = self._levels(payload["bids"])
            f["asks"] = self._levels(payload["asks"])
            buffer, f["buffer"] = f["buffer"], []
            for item in buffer:
                self._depth(symbol, item["row"], item["receipt"])
            if f["synced"]:
                f["synced_since"] = receipt_ms
                if f["ticker"] and f["depth_quote"]:
                    latest, depth = f["ticker"], f["depth_quote"]
                    if latest["T"] >= depth["T"] and latest["u"] >= depth["u"]:
                        f["quote"] = latest
                        f["quote_receipt"] = f["ticker_receipt"]
        try:
            self._change({"kind": "DEPTH_SNAPSHOT", "symbol": symbol,
                          "receipt": receipt_ms, "payload": payload}, action)
        except (ValueError, KeyError, TypeError):
            self.disconnect(symbol, "QUOTE_GAP")
            raise

    def _depth(self, s, row, receipt):
        f = self.feeds[s]
        if row["u"] < f["depth_id"]:
            return
        if not f["synced"]:
            if not row["U"] <= f["depth_id"] <= row["u"]:
                raise ValueError("V5_DEPTH_SNAPSHOT_BRIDGE_MISSING")
        else:
            if row["u"] == f["depth_id"]:
                # A retransmit is only accepted by exact last-event identity.
                if row == f.get("last_depth"):
                    return
                raise ValueError("V5_DEPTH_DUPLICATE_CONFLICT")
            if row["pu"] != f["depth_id"]:
                raise ValueError("V5_DEPTH_PU_GAP")
        for key, rows in (("bids", row["b"]), ("asks", row["a"])):
            for price, qty in self._levels(rows).items():
                if Decimal(qty) == 0:
                    f[key].pop(price, None)
                else:
                    f[key][price] = qty
            if not f[key] or len(f[key]) > MAX_LEVELS:
                raise ValueError("V5_DEPTH_BOOK_EXHAUSTED_OR_OVERFLOW")
        bid = max(f["bids"], key=Decimal)
        ask = min(f["asks"], key=Decimal)
        if Decimal(bid) >= Decimal(ask):
            raise ValueError("V5_DEPTH_BOOK_CROSSED")
        r = {"T": row["T"], "u": row["u"], "b": bid, "a": ask}
        ticker = f["ticker"]
        if ticker and (r["T"] < ticker["T"] or r["u"] < ticker["u"]):
            # Late depth cannot replace newer bookTicker price evidence.
            # Outer ingest/snapshot error handling invalidates existing
            # hypotheses and blocks subsequent entry admission.
            raise ValueError("V5_DEPTH_BEHIND_TICKER")
        f.update(depth_id=row["u"], synced=True, last_depth=row)
        f["depth_quote"] = r
        f["depth_receipt"] = receipt
        f["book_available"] = max(receipt, f["book_available"] or 0)
        f["validation_available"] = max(receipt, f["validation_available"] or 0)
        f["source_receipts"]["depthUpdate"] = receipt
        # Depth updates can trigger virtual stops but cannot become
        # a replacement bookTicker executable entry anchor.
        self.lab.event(s, r, receipt, depth_watermark=(row["u"], row["T"]),
                       source="depthUpdate")

    def recover_trades(self, symbol, through_id, rest, *, max_pages=10):
        """Recover available IDs inclusively; never issue paired quote ticks.

        Each page is committed with its cursor. Partial progress survives API
        failure. Call after disconnect; active paired paths remain unscorable.
        """
        f = self._feed(symbol)
        integer(through_id)
        if f["connected"] or f["agg"] is None or not 0 < max_pages <= 100:
            raise ValueError("V5_RECOVERY_STATE_INVALID")
        for _ in range(max_pages):
            start = self.feeds[symbol]["agg"] + 1
            if start > through_id:
                return True
            rows = rest("/fapi/v1/aggTrades", {"symbol": symbol, "fromId": start, "limit": 1000})
            if not isinstance(rows, list) or not rows or len(rows) > 1000:
                return False
            parsed = [self._trade(r) for r in rows]
            def action():
                f = self.feeds[symbol]
                for r in parsed:
                    if r["a"] != f["agg"] + 1 or r["T"] < f["trade"]["T"]:
                        raise ValueError("V5_REST_RECOVERY_NOT_CONTIGUOUS")
                    if r["a"] > through_id:
                        break
                    f["agg"], f["trade"] = r["a"], r
            self._change({"kind": "REST_AGG_RECOVERY", "symbol": symbol,
                          "fromId": start, "rows": rows, "through": through_id}, action)
        return self.feeds[symbol]["agg"] >= through_id

    def reconcile_funding(self, symbol, start_ms, end_ms, rest, *, now_ms, max_pages=10):
        """Two exhausted public history responses; finality remains unproven.

        Settled rate+associated mark are research evidence, NOT private account
        cash income. No prediction, assumed eight-hour schedule or zero fallback.
        Unsupported simultaneous settlement types fail the V1 accounting gate.
        """
        self._feed(symbol)
        integer(start_ms); integer(end_ms); integer(now_ms)
        if start_ms > end_ms or now_ms < end_ms + FUNDING_GRACE_MS or not 0 < max_pages <= 100:
            raise ValueError("V5_FUNDING_WINDOW_UNSETTLED")
        self._change({'kind':'FUNDING_READ_PENDING', 'symbol':symbol,
                      'start':start_ms, 'end':end_ms, 'observed':now_ms,
                      'state':'PENDING'}, lambda: None)
        def scan():
            events = []
            cursor = start_ms
            for _ in range(max_pages):
                rows = rest("/fapi/v1/fundingRate", {"symbol": symbol, "startTime": cursor,
                            "endTime": end_ms, "limit": 1000})
                if not isinstance(rows, list) or len(rows) > 1000:
                    raise ValueError("V5_FUNDING_RESPONSE_INVALID")
                for row in rows:
                    t = integer(row["fundingTime"])
                    if (row["symbol"] != symbol or not cursor <= t <= end_ms
                            or (events and t <= events[-1]["time_ms"])
                            or row.get("rateType", "Regular") != "Regular"):
                        raise ValueError("V5_FUNDING_CHRONOLOGY_OR_TYPE_INVALID")
                    settlement = FundingSettlement(symbol, t, float(row["fundingRate"]),
                                                   float(row["markPrice"]))
                    events.append(asdict(settlement))
                    if len(events) > MAX_FUNDING_EVENTS:
                        raise ValueError("V5_FUNDING_EVENT_BUDGET_EXCEEDED")
                if len(rows) < 1000:
                    return events
                cursor = events[-1]["time_ms"] + 1
                if cursor > end_ms:
                    return events
            raise ValueError("V5_FUNDING_PAGINATION_INCOMPLETE")
        first, second = scan(), scan()
        with self._lock:
            conflicts = []
            for key, old in self.funding.items():
                lo, hi = max(start_ms, old["start"]), min(end_ms, old["end"])
                if old["symbol"] == symbol and lo <= hi:
                    prior = [e for e in old["events"] if lo <= e["time_ms"] <= hi]
                    if any(prior != [e for e in current if lo <= e["time_ms"] <= hi]
                           for current in (first, second)):
                        conflicts.append(key)
            if conflicts:
                def revoke():
                    for key in conflicts:
                        self.funding[key]["state"] = "REVOKED"
                        self.funding[key]["contradiction"] = [first, second]
                    self._quarantine(symbol, "FUNDING_PROOF_CONTRADICTED")
                self._change({"kind": "FUNDING_REVOKED", "keys": conflicts,
                              "transitions": ['CONTRADICTED','REVOKED'],
                              "observations": [first, second], "symbol": symbol}, revoke)
                raise ValueError("V5_FUNDING_PROOF_CONFLICT")
            if first != second:
                raise ValueError("V5_FUNDING_RECONCILIATION_MISMATCH")
            key = f"{symbol}:{start_ms}:{end_ms}"
            if key in self.funding:
                if self.funding[key]["state"] == "REVOKED":
                    raise ValueError("V5_FUNDING_PROOF_REVOKED")
                return key
            if len(self.funding) >= 100:
                raise RuntimeError("V5_FUNDING_PROOF_BACKPRESSURE")
            proof = {"symbol": symbol, "start": start_ms, "end": end_ms,
                     "observed": now_ms, "source": "/fapi/v1/fundingRate",
                     "events": first, "version": VERSION,
                     "state": "VERIFIED_RESPONSE_AGREEMENT", "finality": "UNPROVEN",
                     "proof_type": "TWO_EXHAUSTED_HISTORY_RESPONSES", "proof_version": 1,
                     "validation": "MATCHED_RESPONSES_ONLY"}
            self._change({"kind": "FUNDING_RECONCILED", "key": key, "proof": proof},
                         lambda: self.funding.update({key: proof}))
            return key

    def check_source_coverage(self, now_ms, *, max_silence_ms=MAX_BOOKTICKER_SILENCE_MS):
        """Check each symbol's bookTicker separately from other WSS traffic.

        A bookTicker feed has no per-symbol heartbeats. Prolonged genuine
        silence cannot be distinguished from quote loss, so reject rather
        than certifying the stop path. Does not write on healthy checks.
        """
        integer(now_ms)
        if type(max_silence_ms) is not int or max_silence_ms <= 0:
            raise ValueError("V5_QUOTE_COVERAGE_POLICY_INVALID")
        for symbol in self.symbols:
            f = self.feeds[symbol]
            if not f["connected"] or not f["synced"]:
                continue
            last = f["ticker_receipt"]
            baseline = last if last is not None else f["synced_since"]
            if baseline is not None and now_ms - baseline > max_silence_ms:
                self.disconnect(symbol, "FEED_UNCERTAIN")
                raise RuntimeError("V5_BOOKTICKER_SOURCE_SILENT")

    def finalize(self, decision_id, *, now_ms, funding_key=None):
        integer(now_ms)
        def action():
            if decision_id in self.lab._completed:
                return self.lab._completed[decision_id]
            p = self.lab._paths[decision_id]
            if not p.ready(now_ms):
                return None
            reason = p.gap_reason
            if reason is None and (not p.horizon_witnessed or not p.ticker_events):
                reason = "OBSERVED_HORIZON_INCOMPLETE"
            if reason is None and any(a.exit_time_ms is None for a in p.arms.values()):
                reason = "OBSERVED_EXIT_INCOMPLETE"
            proof = self.funding.get(funding_key)
            if proof and proof["state"] == "REVOKED":
                reason = "FUNDING_PROOF_REVOKED"
            events = proof["events"] if proof and proof["symbol"] == p.entry.symbol else []
            if any(e["time_ms"] == p.entry.entry_time_ms or
                   any(e["time_ms"] == a.exit_time_ms for a in p.arms.values()) for e in events):
                reason = "FUNDING_BOUNDARY_AMBIGUOUS"
            p.digest.update(_encode({"funding_observations": proof, "trust_contract": CONTRACT}))
            rows = tuple(ArmResult(
                decision_id, a.policy_id, "UNSCORABLE" if reason else "OBSERVED_STREAM",
                reason or "OBSERVED_PATH_ONLY_FUNDING_FINALITY_UNPROVEN",
                a.exit_time_ms, a.exit_reason, a.high_r, a.low_r, a.stop_r,
                p.events_seen, p.digest.hexdigest(), None,
                CONTRACT, "UNSCORABLE" if reason else "OBSERVED_STREAM",
                None if reason else observed_costs(p.entry, a, events), None)
                for a in p.arms.values())
            if len(self.lab._completed) >= 100:
                raise RuntimeError("V5_PAIRED_PERSISTENCE_BACKPRESSURE")
            del self.lab._paths[decision_id]
            self.lab._by_symbol[p.entry.symbol].remove(decision_id)
            if not self.lab._by_symbol[p.entry.symbol]:
                del self.lab._by_symbol[p.entry.symbol]
            self.lab._completed[decision_id] = rows
            return rows
        return self._change({"kind": "FINALIZE", "decision": decision_id,
                             "now": now_ms, "funding_key": funding_key}, action)

    def persist_results(self, store, decision_id):
        with self._lock:
            if self.integrity_fault is not None:
                raise RuntimeError("V5_EVIDENCE_INTEGRITY_FAULT")
            store.record_observed_pair(self.lab._completed[decision_id], authority=self)
            self._change({"kind": "LEDGER_ACK", "decision": decision_id},
                         lambda: self.lab.acknowledge_persisted(decision_id))


def submit_order(*_args, **_kwargs):
    raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
