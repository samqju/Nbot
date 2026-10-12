"""Opt-in public USD-M evidence bridge. Research only; no execution client.

Every mutation commits an audit event and a checksummed bounded checkpoint in
one SQLite transaction. Network gaps never become reconstructed quote paths.
The legacy tick-only lab retains its original contract and digest version.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sqlite3
import threading

from .v5_accounting import FundingSettlement, TradeAccounting
from .v5_paired_exits import (
    PairedEntry, PairedExitLab, ArmResult, _Arm, _encode,
    MAX_RECEIPT_DELAY_MS, HORIZON_CLOSE_GRACE_MS,
)

VERSION = "NBOT_V5_JOINT_EVIDENCE_V1"
ORDER_AUTHORITY = "NONE"
MAX_SYMBOLS = 20
MAX_LEVELS = 5000
MAX_BUFFER = 2000
MAX_DB_BYTES = 256 * 1024 * 1024
FUNDING_GRACE_MS = 60_000


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
    def add(self, entry):
        super().add(entry)
        path = self._paths[entry.decision_id]
        path.digest = _Chain()
        path.digest.update(_encode({"v": VERSION, "entry": asdict(entry)}))
        path.joint_time = entry.entry_time_ms
        path.quote = None

    def event(self, symbol, row, receipt, *, trade=False):
        timestamp = integer(row["T"])
        for decision in tuple(self._by_symbol.get(symbol, ())):
            path = self._paths[decision]
            if path.gap_reason or path.horizon_witnessed:
                continue
            if (timestamp < path.joint_time or receipt < timestamp
                    or receipt - timestamp > MAX_RECEIPT_DELAY_MS):
                path.invalidate("JOINT_EVENT_LATE_OR_REVERSED")
                continue
            if timestamp <= path.entry.entry_time_ms:
                path.invalidate("JOINT_ENTRY_BOUNDARY_AMBIGUOUS")
                continue
            if timestamp > path.deadline + HORIZON_CLOSE_GRACE_MS:
                path.invalidate("HORIZON_CLOSE_WITNESS_MISSING")
                continue
            if trade:
                if row["a"] != path.last_agg_id + 1:
                    path.invalidate("WSS_GAP")
                    continue
                path.last_agg_id = row["a"]
                path.last_trade_time_ms = timestamp
            else:
                # An identical second source quote at the same timestamp adds
                # provenance, but cannot ratchet a trailing stop twice.
                quote = (timestamp, row["b"], row["a"])
                if path.quote and timestamp == path.quote[0] and quote != path.quote:
                    path.invalidate("JOINT_QUOTE_ORDER_AMBIGUOUS")
                    continue
                if quote != path.quote:
                    px = float(row["b"] if path.entry.side == "LONG" else row["a"])
                    for arm in path.arms.values():
                        arm.apply(time_ms=timestamp, price=px, entry=path.entry,
                                  horizon=timestamp >= path.deadline)
                    path.quote = quote
                path.last_quote_update_id = row["u"]
            path.joint_time = timestamp
            path.digest.update(_encode({"row": row, "receipt": receipt, "trade": trade}))
            path.events_seen += 1
            # A horizon quote needs a trade-stream watermark at or beyond it.
            # Silence alone is not proof of continuous aggregate history.
            if (path.quote and path.quote[0] >= path.deadline
                    and path.last_trade_time_ms >= path.quote[0]):
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
                              "joint_time", "quote")}}
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
                    setattr(p, name, tuple(value) if name == "quote" and value else value)
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
owners. On database failure in-memory state rolls back to the last commit.
"""
    def __init__(self, path=Path("data/observation/v5/live_evidence.db"), *, symbols):
        self.path = Path(path)
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
        self._lock = threading.RLock()

    @staticmethod
    def _fresh():
        return {"agg": None, "trade": None, "bids": {}, "asks": {},
                "depth_id": None, "synced": False, "buffer": [],
                "ticker": None, "quote": None, "connected": False}

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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoint(
                    id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL,
                    state TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS journal(
                    seq INTEGER PRIMARY KEY, event TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS journal_no_update BEFORE UPDATE ON journal
                    BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_JOURNAL'); END;
                CREATE TRIGGER IF NOT EXISTS journal_no_delete BEFORE DELETE ON journal
                    BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_JOURNAL'); END;
            """)
            row = conn.execute("SELECT seq,state,digest FROM checkpoint WHERE id=1").fetchone()
            if row:
                if hashlib.sha256(row[1].encode()).hexdigest() != row[2]:
                    raise ValueError("V5_CHECKPOINT_CORRUPT")
                journal = conn.execute("SELECT digest FROM journal WHERE seq=?", (row[0],)).fetchone()
                latest = conn.execute("SELECT MAX(seq) FROM journal").fetchone()[0]
                if not journal or journal[0] != row[2] or latest != row[0]:
                    raise ValueError("V5_CHECKPOINT_JOURNAL_MISMATCH")
                self.seq = row[0]
                self._restore(json.loads(row[1]))
        self.ready = True
        # Restore frozen entries, exits, digests and pending results. A restart
        # still loses prospective quote continuity for unfinished horizons.
        self._change({"kind": "PROCESS_RESTART"}, self._restart)

    def _restart(self):
        for s in self.symbols:
            self.lab.invalidate_symbol(s, reason="PROCESS_RESTART")
            old = self.feeds[s]
            fresh = self._fresh()
            fresh["agg"], fresh["trade"] = old["agg"], old["trade"]
            self.feeds[s] = fresh

    def _change(self, event, action):
        if not self.ready:
            raise RuntimeError("V5_EVIDENCE_NOT_INITIALIZED")
        with self._lock:
            backup = json.loads(_encode(self._dump()))
            try:
                size = sum(p.stat().st_size for p in (
                    self.path, Path(str(self.path) + "-wal")) if p.exists())
                if size >= MAX_DB_BYTES:
                    raise RuntimeError("V5_EVIDENCE_DISK_BACKPRESSURE")
                result = action()
                raw = _encode(self._dump()).decode()
                digest = hashlib.sha256(raw.encode()).hexdigest()
                with self._connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    row = conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()
                    if (row[0] if row else 0) != self.seq:
                        raise RuntimeError("V5_EVIDENCE_CONCURRENT_WRITER")
                    conn.execute("INSERT INTO journal VALUES(?,?,?)",
                                 (self.seq + 1, _encode(event).decode(), digest))
                    conn.execute("INSERT OR REPLACE INTO checkpoint VALUES(1,?,?,?)",
                                 (self.seq + 1, raw, digest))
                self.seq += 1
                return result
            except BaseException:
                self._restore(backup)
                raise

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
            self.lab.invalidate_symbol(symbol, reason=reason)
            f = self.feeds[symbol]
            f.update(connected=False, synced=False, buffer=[], depth_id=None,
                     bids={}, asks={}, quote=None, ticker=None)
        self._change({"kind": reason, "symbol": symbol}, action)

    def add(self, entry):
        f = self._feed(entry.symbol)
        q = f["quote"]
        if (not f["connected"] or not f["synced"] or not q or not f["trade"]
                or entry.anchor_agg_id != f["agg"]
                or entry.anchor_trade_time_ms != f["trade"]["T"]
                or entry.entry_quote_time_ms != q["T"]
                or entry.entry_bid != float(q["b"]) or entry.entry_ask != float(q["a"])):
            raise ValueError("V5_ENTRY_LIVE_ANCHOR_UNPROVEN")
        self._change({"kind": "ENTRY", "entry": asdict(entry)}, lambda: self.lab.add(entry))

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
        integer(row["E"])
        if receipt < t or receipt - t > MAX_RECEIPT_DELAY_MS:
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
            self.lab.event(s, r, receipt, trade=True)
        elif kind == "bookTicker":
            r = {"T": t, "u": integer(row["u"]),
                 "b": str(number(row["b"])), "a": str(number(row["a"]))}
            number(row["B"]); number(row["A"])
            if Decimal(r["b"]) >= Decimal(r["a"]):
                raise ValueError("V5_QUOTE_CROSSED")
            if f["ticker"] == r:
                return
            if f["ticker"] and (r["u"] <= f["ticker"]["u"] or t < f["ticker"]["T"]):
                raise ValueError("V5_TICKER_REVERSED_OR_CONFLICT")
            f["ticker"] = r
            if f["synced"]:
                f["quote"] = r
                self.lab.event(s, r, receipt)
        else:
            integer(row["U"]); integer(row["u"]); integer(row["pu"])
            if row["U"] > row["u"]:
                raise ValueError("V5_DEPTH_RANGE_INVALID")
            self._levels(row["b"]); self._levels(row["a"])
            if f["depth_id"] is None:
                if len(f["buffer"]) >= MAX_BUFFER:
                    raise ValueError("V5_DEPTH_BUFFER_OVERFLOW")
                f["buffer"].append({"row": row, "receipt": receipt})
            else:
                self._depth(s, row, receipt)

    @staticmethod
    def _trade(row):
        r = {k: integer(row[k]) for k in ("a", "f", "l", "T")}
        r.update(p=str(number(row["p"])), q=str(number(row["q"])), m=row["m"])
        if r["f"] > r["l"] or type(r["m"]) is not bool:
            raise ValueError("V5_TRADE_INVALID")
        return r

    @staticmethod
    def _levels(rows):
        if not isinstance(rows, list) or len(rows) > MAX_LEVELS:
            raise ValueError("V5_DEPTH_LEVELS_INVALID")
        levels = {}
        for price, qty in rows:
            price, qty = str(number(price)), str(number(qty, zero=True))
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
            f["depth_id"] = integer(payload["lastUpdateId"])
            f["bids"] = self._levels(payload["bids"])
            f["asks"] = self._levels(payload["asks"])
            buffer, f["buffer"] = f["buffer"], []
            for item in buffer:
                self._depth(symbol, item["row"], item["receipt"])
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
        f.update(depth_id=row["u"], synced=True, last_depth=row)
        r = {"T": row["T"], "u": row["u"], "b": bid, "a": ask}
        f["quote"] = r
        self.lab.event(s, r, receipt)

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
                          "fromId": start, "rows": rows}, action)
        return self.feeds[symbol]["agg"] >= through_id

    def reconcile_funding(self, symbol, start_ms, end_ms, rest, *, now_ms, max_pages=10):
        """Two exhaustive public history reads after publication grace.

        Settled rate+associated mark are research evidence, NOT private account
        cash income. No prediction, assumed eight-hour schedule or zero fallback.
        Unsupported simultaneous settlement types fail the V1 accounting gate.
        """
        self._feed(symbol)
        integer(start_ms); integer(end_ms); integer(now_ms)
        if start_ms > end_ms or now_ms < end_ms + FUNDING_GRACE_MS or not 0 < max_pages <= 100:
            raise ValueError("V5_FUNDING_WINDOW_UNSETTLED")
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
                if len(rows) < 1000:
                    return events
                cursor = events[-1]["time_ms"] + 1
                if cursor > end_ms:
                    return events
            raise ValueError("V5_FUNDING_PAGINATION_INCOMPLETE")
        first, second = scan(), scan()
        if first != second:
            raise ValueError("V5_FUNDING_RECONCILIATION_MISMATCH")
        proof = {"symbol": symbol, "start": start_ms, "end": end_ms,
                 "observed": now_ms, "source": "/fapi/v1/fundingRate",
                 "events": first, "version": VERSION}
        # Reject contradictory overlapping proofs, including disappearing events.
        for old in self.funding.values():
            if old["symbol"] == symbol:
                lo, hi = max(start_ms, old["start"]), min(end_ms, old["end"])
                if lo <= hi:
                    a = [e for e in old["events"] if lo <= e["time_ms"] <= hi]
                    b = [e for e in first if lo <= e["time_ms"] <= hi]
                    if a != b:
                        raise ValueError("V5_FUNDING_PROOF_CONFLICT")
        key = f"{symbol}:{start_ms}:{end_ms}"
        if key in self.funding:
            return key
        if len(self.funding) >= 100:
            raise RuntimeError("V5_FUNDING_PROOF_BACKPRESSURE")
        self._change({"kind": "FUNDING_RECONCILED", "proof": proof},
                     lambda: self.funding.update({key: proof}))
        return key

    def finalize(self, decision_id, *, now_ms, funding_key=None):
        integer(now_ms)
        def action():
            if decision_id in self.lab._completed:
                return self.lab._completed[decision_id]
            p = self.lab._paths[decision_id]
            proof = self.funding.get(funding_key)
            exits = [a.exit_time_ms for a in p.arms.values()]
            covered = bool(proof and proof["symbol"] == p.entry.symbol
                           and proof["start"] <= p.entry.entry_time_ms
                           and all(t is not None and t <= proof["end"] for t in exits))
            events = [FundingSettlement(**r) for r in proof["events"]] if covered else ()
            if p.ready(now_ms):
                p.digest.update(_encode({"funding_proof": proof if covered else None}))
            rows = self.lab.finalize(decision_id, now_ms=now_ms, funding_events=events,
                                     funding_coverage_confirmed=covered)
            if rows:
                rows = tuple(replace(r, reason="JOINT_WSS_EVIDENCE_RESOLVED")
                             if r.status == "SCORED" else r for r in rows)
                self.lab._completed[decision_id] = rows
            return rows
        return self._change({"kind": "FINALIZE", "decision": decision_id,
                             "now": now_ms, "funding_key": funding_key}, action)

    def persist_results(self, store, decision_id):
        from .v5_paired_exits import persist_to_v5_ledger
        with self._lock:
            # Retry all immutable rows before releasing the durable pending set.
            persist_to_v5_ledger(store, self.lab._completed[decision_id])
            self._change({"kind": "LEDGER_ACK", "decision": decision_id},
                         lambda: self.lab.acknowledge_persisted(decision_id))


def submit_order(*_args, **_kwargs):
    raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
