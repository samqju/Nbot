"""G4 isolated original-frame receipt vault; no trading or G1/G2/G3 DB access.

Record every raw market/public WSS frame, rejected source, disconnect and
unclean restart in append-only, SHA-chained SQLite. One DB per frozen cohort.
A recorded message is local observed source evidence, NOT a fill, complete
trade path, authenticated exchange signature, or qualified economic label.

Only a separately approved G4 runner may ever call this on a dedicated DB.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
from typing import Sequence

from nbot.v5.g4_forward_stream_contract import verify_frame

SOURCE_VAULT_VERSION = "NBOT_V5_G4_FORWARD_RAW_SOURCE_V1"
_ZERO = "0" * 64
_ROUTES = frozenset(("public_bookticker", "market_aggtrade"))
_FORBIDDEN = frozenset((
    "g1f_event_manifest", "g1f_candidate_events", "g2_quote_witness",
    "g3_event_context", "candle_rows", "v5_candidate_observations",
    "g4_label_intents", "g4_label_terminals", "paper_trades",
    "virtual_trades", "research_decisions", "v5_source_epochs",
))
_SCHEMA = frozenset(("g4_forward_cohort", "g4_forward_receipts", "sqlite_sequence"))


def _canon(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _clock(value: object) -> bool:
    return type(value) is int and value > 0


def _hash_receipt(data: dict) -> str:
    return _sha(_canon(data).encode())


@dataclass(frozen=True)
class Receipt:
    seq: int
    route: str
    epoch: int
    kind: str
    at_ms: int
    symbol: str | None
    evidence_state: str
    reasons: tuple[str, ...]
    raw_sha256: str
    prior_sha256: str
    chain_sha256: str
    economic_outcomes: int = 0
    order_authority: str = "NONE"


class ForwardSourceVault:
    def __init__(self, db: sqlite3.Connection, *, symbols: Sequence[str]):
        # Never auto-create on a production/legacy/mixed source schema.
        if not isinstance(db, sqlite3.Connection):
            raise ValueError("G4_VAULT_CONNECTION_INVALID")
        from nbot.v5.g4_forward_stream_contract import forward_stream_endpoints
        normalized = forward_stream_endpoints(symbols)["cohort_symbols"]
        existing = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if existing & _FORBIDDEN or existing - _SCHEMA:
            raise ValueError("G4_VAULT_MIXED_OR_PRODUCTION_DB_FORBIDDEN")
        self.db = db
        self.symbols = normalized
        self.cohort_sha = _hash_receipt({"symbols": normalized,
                                         "version": SOURCE_VAULT_VERSION})
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS g4_forward_cohort (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cohort_sha TEXT NOT NULL,
            symbols_json TEXT NOT NULL,
            contract TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS g4_forward_receipts (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            route TEXT NOT NULL,
            epoch INTEGER NOT NULL CHECK (epoch > 0),
            kind TEXT NOT NULL CHECK (kind IN (
                'OPEN','CLOSED','ABRUPT_RESTART_HOLD','FRAME')),
            at_ms INTEGER NOT NULL CHECK (at_ms > 0),
            symbol TEXT,
            evidence_state TEXT NOT NULL,
            reasons_json TEXT NOT NULL,
            raw_sha256 TEXT NOT NULL,
            raw_frame BLOB NOT NULL,
            prior_sha256 TEXT NOT NULL,
            chain_sha256 TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS g4_forward_cohort_no_update
          BEFORE UPDATE ON g4_forward_cohort
          BEGIN SELECT RAISE(ABORT,'G4_VAULT_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g4_forward_cohort_no_delete
          BEFORE DELETE ON g4_forward_cohort
          BEGIN SELECT RAISE(ABORT,'G4_VAULT_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g4_forward_receipts_no_update
          BEFORE UPDATE ON g4_forward_receipts
          BEGIN SELECT RAISE(ABORT,'G4_VAULT_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g4_forward_receipts_no_delete
          BEFORE DELETE ON g4_forward_receipts
          BEGIN SELECT RAISE(ABORT,'G4_VAULT_IMMUTABLE'); END;
        """)
        old = db.execute(
            "SELECT cohort_sha,symbols_json,contract "
            "FROM g4_forward_cohort WHERE id=1").fetchone()
        expected = (self.cohort_sha, _canon(normalized), SOURCE_VAULT_VERSION)
        if old is not None and old != expected:
            raise ValueError("G4_VAULT_FROZEN_COHORT_CONFLICT")
        if old is None:
            if db.execute("SELECT count(*) FROM g4_forward_receipts").fetchone()[0]:
                raise ValueError("G4_VAULT_ORPHAN_RECEIPTS")
            with db:
                db.execute("INSERT INTO g4_forward_cohort VALUES (1,?,?,?)",
                           expected)

    def _last(self, route: str | None = None):
        if route is None:
            return self.db.execute(
                "SELECT seq,route,epoch,kind,at_ms,symbol,evidence_state,"
                "reasons_json,raw_sha256,raw_frame,prior_sha256,chain_sha256 "
                "FROM g4_forward_receipts ORDER BY seq DESC LIMIT 1").fetchone()
        return self.db.execute(
            "SELECT seq,route,epoch,kind,at_ms,symbol,evidence_state,"
            "reasons_json,raw_sha256,raw_frame,prior_sha256,chain_sha256 "
            "FROM g4_forward_receipts WHERE route=? "
            "ORDER BY seq DESC LIMIT 1", (route,)).fetchone()

    def _append(self, route: str, epoch: int, kind: str, at_ms: int,
                symbol: str | None, state: str, reasons: tuple[str,...],
                raw: bytes) -> Receipt:
        if not _clock(at_ms) or kind not in (
                "OPEN", "CLOSED", "ABRUPT_RESTART_HOLD", "FRAME"):
            raise ValueError("G4_VAULT_RECEIPT_CLOCK_OR_KIND_INVALID")
        last = self._last()
        previous_sha = last[-1] if last else _ZERO
        raw_sha = _sha(raw)
        reasons_json = _canon(reasons)
        fields = {"contract": SOURCE_VAULT_VERSION, "route": route,
                  "epoch": epoch, "kind": kind, "at_ms": at_ms,
                  "symbol": symbol, "state": state,
                  "reasons_json": reasons_json, "raw_sha": raw_sha,
                  "prior_sha": previous_sha}
        chain = _hash_receipt(fields)
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO g4_forward_receipts "
                "(route,epoch,kind,at_ms,symbol,evidence_state,reasons_json,"
                "raw_sha256,raw_frame,prior_sha256,chain_sha256) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (route,epoch,kind,at_ms,symbol,state,reasons_json,
                 raw_sha,raw,previous_sha,chain))
        return Receipt(cursor.lastrowid,route,epoch,kind,at_ms,symbol,
                       state,reasons,raw_sha,previous_sha,chain)

    def connect(self, *, route: str, at_ms: int) -> Receipt:
        if route not in _ROUTES:
            raise ValueError("G4_VAULT_ROUTE_INVALID")
        if not _clock(at_ms):
            raise ValueError("G4_VAULT_CLOCK_INVALID")
        latest = self._last(route)
        if latest is None:
            generation = 1
        else:
            if at_ms < latest[4]:
                # Validation MUST precede all writes; even a rejected restart
                # cannot create a false source-gap marker.
                raise ValueError("G4_VAULT_CLOCK_REWIND")
            generation = latest[2] + 1
            if latest[3] not in ("CLOSED", "ABRUPT_RESTART_HOLD"):
                # This proves only when an unexpected open connection was
                # DISCOVERED after restart. The true gap start is UNKNOWN.
                self._append(route, latest[2], "ABRUPT_RESTART_HOLD",at_ms,
                             None,"HOLD",("UNKNOWN_INTERRUPTION_SINCE_LAST_RECEIPT",),b"")
        return self._append(route,generation,"OPEN",at_ms,None,"HOLD",
                            ("INITIAL_EPOCH_CONTINUITY_UNPROVEN",),b"")

    def disconnect(self, *, route: str, at_ms: int) -> Receipt:
        last = self._last(route)
        if route not in _ROUTES or last is None or last[3] not in ("OPEN", "FRAME"):
            raise ValueError("G4_VAULT_ROUTE_NOT_CONNECTED")
        if not _clock(at_ms) or at_ms < last[4]:
            raise ValueError("G4_VAULT_CLOCK_REWIND")
        return self._append(route,last[2],"CLOSED",at_ms,None,"HOLD",
                            ("SOURCE_DISCONNECTED",),b"")

    def ingest(self, *, route: str, at_ms: int, raw: bytes) -> Receipt:
        if route not in _ROUTES:
            raise ValueError("G4_VAULT_ROUTE_INVALID")
        last = self._last(route)
        if last is None or last[3] not in ("OPEN", "FRAME"):
            raise ValueError("G4_VAULT_ROUTE_NOT_CONNECTED")
        if not _clock(at_ms) or at_ms < last[4]:
            raise ValueError("G4_VAULT_CLOCK_REWIND")
        if not isinstance(raw, bytes):
            raise ValueError("G4_VAULT_RAW_BYTES_REQUIRED")
        # Never suppress invalid or stale *bounded* original-source messages:
        # preserve raw bytes as HOLD, with typed reason, in the chained ledger.
        symbol = None
        try:
            value = json.loads(raw)
            if isinstance(value, dict) and isinstance(value.get("data"), dict):
                symbol = value["data"].get("s")
        except (UnicodeError,ValueError):
            pass
        if symbol not in self.symbols:
            symbol = None
        previous = (self.db.execute(
            "SELECT evidence_state,raw_frame FROM g4_forward_receipts "
            "WHERE route=? AND epoch=? AND symbol=? AND kind='FRAME' "
            "ORDER BY seq DESC LIMIT 1", (route,last[2],symbol)).fetchone()
            if symbol is not None else None)
        prior_agg = prior_trade = None
        inherited_hold = bool(previous and previous[0] != "SOURCE_RECORDED")
        if route == "market_aggtrade" and previous:
            try:
                old = json.loads(previous[1])["data"]
                prior_agg = old.get("a")
                prior_trade = old.get("l")
            except (KeyError,ValueError,TypeError,UnicodeError):
                inherited_hold = True
        try:
            proof = verify_frame(route=route,raw=raw,received_at_ms=at_ms,
                                 source_epoch=last[2],selected_symbols=self.symbols,
                                 prior_agg_id=prior_agg,
                                 prior_last_trade_id=prior_trade)
            state = proof.state
            reasons = list(proof.reasons)
        except (ValueError,TypeError,UnicodeError) as exc:
            state = "HOLD"
            reasons = ["MALFORMED_OR_OVERSIZED_FRAME"]
            # Reject storage overload, not just parsing, at boundary.
            if len(raw) > 32768:
                raise ValueError("G4_VAULT_FRAME_OVERSIZE")
        if inherited_hold:
            reasons.append("PRIOR_SYMBOL_SOURCE_HELD")
        if previous is not None and previous[1] == raw:
            reasons.append("DUPLICATE_RAW_FRAME")
        if reasons:
            state = "HOLD"
        return self._append(route,last[2],"FRAME",at_ms,symbol,state,
                            tuple(sorted(set(reasons))),raw)

    def audit(self) -> dict:
        """Read-only hash-chain, raw byte, and source-state independent audit."""
        found = self.db.execute(
            "SELECT cohort_sha,symbols_json,contract FROM g4_forward_cohort "
            "WHERE id=1").fetchall()
        if found != [(self.cohort_sha,_canon(self.symbols),SOURCE_VAULT_VERSION)]:
            raise ValueError("G4_VAULT_COHORT_TAMPERED")
        last_sha = _ZERO
        counts = {"OPEN":0,"CLOSED":0,"ABRUPT_RESTART_HOLD":0,
                  "SOURCE_RECORDED":0,"HOLD":0}
        last_epoch = {}
        for seq,route,epoch,kind,at,sym,state,reasons,raw_sha,raw,previous,chain in (
            self.db.execute(
                "SELECT seq,route,epoch,kind,at_ms,symbol,evidence_state,"
                "reasons_json,raw_sha256,raw_frame,prior_sha256,chain_sha256 "
                "FROM g4_forward_receipts ORDER BY seq")
        ):
            if route not in _ROUTES or previous != last_sha or _sha(raw) != raw_sha:
                raise ValueError("G4_VAULT_SHA_CHAIN_INVALID")
            fields={"contract":SOURCE_VAULT_VERSION,"route":route,
                    "epoch":epoch,"kind":kind,"at_ms":at,
                    "symbol":sym,"state":state,"reasons_json":reasons,
                    "raw_sha":raw_sha,"prior_sha":previous}
            if _hash_receipt(fields)!=chain:
                raise ValueError("G4_VAULT_SHA_CHAIN_INVALID")
            last_sha=chain
            counts[kind if kind!="FRAME" else state]+=1
            last_epoch[route]=epoch
        return {"audit":"PASS","source_contract":SOURCE_VAULT_VERSION,
                "frozen_cohort":len(self.symbols),
                "cohort_sha256":self.cohort_sha,
                "counts":counts,"head_sha256":last_sha,
                "model_training_authority":"NONE",
                "scored_outcomes":0,"order_authority":"NONE"}
