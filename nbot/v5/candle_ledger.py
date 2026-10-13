"""NBOT V5 isolated, append-only five-minute candle evidence ledger.

No model, order, credential, paper executor, systemd service, or trade authority.
A verified REST *candle* recovery never repairs missing trades or quotes.
Use ONLY a new V5 sandbox database, not any old observation/paper DB.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Mapping, Sequence

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import decode_klines

SCHEMA = "NBOT_V5_CANDLE_LEDGER_1"
SOURCES = {"REST_BOOTSTRAP", "REST_GAP_RECOVERY", "WSS_FINAL"}


class EvidenceHold(ValueError):
    """Evidence cannot safely advance the V5 candle cursor."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _row(bar: Sequence) -> tuple:
    if not isinstance(bar, (tuple, list)) or len(bar) != 6:
        raise EvidenceHold("V5_LEDGER_BAR_SHAPE")
    t, *numbers = bar
    if type(t) is not int or t < 0 or t % INTERVAL_MS:
        raise EvidenceHold("V5_LEDGER_BAR_TIME")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in numbers):
        raise EvidenceHold("V5_LEDGER_BAR_VALUE")
    try:
        o, h, l, c, v = map(float, numbers)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EvidenceHold("V5_LEDGER_BAR_VALUE") from exc
    if (not all(map(math.isfinite, (o, h, l, c, v)))
            or min(o, h, l, c) <= 0 or v < 0
            or h < max(o, c) or l > min(o, c) or l > h):
        raise EvidenceHold("V5_LEDGER_BAR_OHLCV")
    return (t, o, h, l, c, v)


class CandleEvidenceLedger:
    """SQLite FULL-sync WAL journal; one writer per connection, no online trading.

    Candle rows are immutable. Source proof and gate transition logs are also
    append-only. A gap freezes advancing WSS data until a separately validated
    REST 96-bar as-of-window reconciles it. Cohort/trade/quote remain UNVERIFIED.
    """

    def __init__(self, path: str | Path):
        path = Path(path).expanduser().resolve()
        # One-way guard against accidentally recreating/resetting prior V4 data.
        if (str(path).startswith("/home/ubuntu/Nbot/")
                or any(part.lower() in ("v4", "live", "v3")
                       for part in path.parts)):
            raise EvidenceHold("V5_LEDGER_LEGACY_PATH_FORBIDDEN")
        if path.suffix not in (".db", ".sqlite") or not path.parent.is_dir():
            raise EvidenceHold("V5_LEDGER_NEW_DB_PATH_REQUIRED")
        if path.is_symlink():
            raise EvidenceHold("V5_LEDGER_SYMLINK_FORBIDDEN")
        self.path = path
        self.db = sqlite3.connect(str(path), timeout=5)
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS candle_rows (
                    symbol TEXT NOT NULL,
                    open_ms INTEGER NOT NULL,
                    candle_json TEXT NOT NULL,
                    candle_sha TEXT NOT NULL,
                    first_source TEXT NOT NULL
                        CHECK(first_source IN ('REST_BOOTSTRAP','REST_GAP_RECOVERY','WSS_FINAL')),
                    first_seen_ms INTEGER NOT NULL,
                    source_window_sha TEXT NOT NULL,
                    PRIMARY KEY(symbol,open_ms)
                );
                CREATE TABLE IF NOT EXISTS evidence_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    open_ms INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    proof_sha TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS gate_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('OPEN','RESOLVED')),
                    evidence_sha TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS candle_no_update
                BEFORE UPDATE ON candle_rows BEGIN
                    SELECT RAISE(ABORT,'V5_IMMUTABLE_CANDLE');
                END;
                CREATE TRIGGER IF NOT EXISTS candle_no_delete
                BEFORE DELETE ON candle_rows BEGIN
                    SELECT RAISE(ABORT,'V5_IMMUTABLE_CANDLE');
                END;
                CREATE TRIGGER IF NOT EXISTS evidence_no_update
                BEFORE UPDATE ON evidence_events BEGIN
                    SELECT RAISE(ABORT,'V5_IMMUTABLE_EVIDENCE');
                END;
                CREATE TRIGGER IF NOT EXISTS evidence_no_delete
                BEFORE DELETE ON evidence_events BEGIN
                    SELECT RAISE(ABORT,'V5_IMMUTABLE_EVIDENCE');
                END;
                CREATE TRIGGER IF NOT EXISTS gate_no_update
                BEFORE UPDATE ON gate_events BEGIN
                    SELECT RAISE(ABORT,'V5_IMMUTABLE_GATE');
                END;
                CREATE TRIGGER IF NOT EXISTS gate_no_delete
                BEFORE DELETE ON gate_events BEGIN
                    SELECT RAISE(ABORT,'V5_IMMUTABLE_GATE');
                END;
            """)
        except Exception:
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self):
        self.db.close()

    def _last(self, symbol: str) -> int | None:
        row = self.db.execute(
            "SELECT MAX(open_ms) FROM candle_rows WHERE symbol=?", (symbol,)
        ).fetchone()
        return row[0]

    def _stored(self, symbol: str, open_ms: int) -> tuple | None:
        row = self.db.execute(
            "SELECT candle_json FROM candle_rows WHERE symbol=? AND open_ms=?",
            (symbol, open_ms),
        ).fetchone()
        return tuple(json.loads(row[0])) if row else None

    def _open_gates(self, symbol: str) -> tuple[str, ...]:
        rows = self.db.execute("""
            SELECT g.reason FROM gate_events g
            INNER JOIN (
                SELECT reason, MAX(event_id) AS last
                FROM gate_events WHERE symbol=? GROUP BY reason
            ) state ON g.event_id = state.last
            WHERE g.action='OPEN' ORDER BY g.reason
        """, (symbol,)).fetchall()
        return tuple(x[0] for x in rows)

    def _gate(self, symbol: str, reason: str, action: str, evidence_sha: str):
        active = reason in self._open_gates(symbol)
        if (action == "OPEN" and active) or (action == "RESOLVED" and not active):
            return
        self.db.execute(
            "INSERT INTO gate_events(symbol,reason,action,evidence_sha) "
            "VALUES (?,?,?,?)", (symbol, reason, action, evidence_sha),
        )

    def _insert(self, symbol: str, candle: tuple, source: str,
                observed_ms: int, source_sha: str):
        self.db.execute("""
            INSERT INTO candle_rows
                (symbol,open_ms,candle_json,candle_sha,
                 first_source,first_seen_ms,source_window_sha)
            VALUES (?,?,?,?,?,?,?)
        """, (symbol, candle[0], _json(candle), _sha(candle),
              source, observed_ms, source_sha))
        self.db.execute("""
            INSERT INTO evidence_events(symbol,kind,open_ms,source,proof_sha)
            VALUES (?,?,?,?,?)
        """, (symbol, "APPENDED_CLOSED_BAR", candle[0], source, source_sha))

    @staticmethod
    def _valid_event(symbol: str, open_ms: int, received_ms: int):
        from nbot.v5.ws_contract import UnsafeStream
        from nbot.v5.ws_contract import stream_urls
        try:
            stream_urls((symbol,))
        except UnsafeStream as exc:
            raise EvidenceHold("V5_LEDGER_SYMBOL_INVALID") from exc
        if (type(open_ms) is not int or open_ms < 0
                or open_ms % INTERVAL_MS
                or type(received_ms) is not int
                or received_ms <= open_ms + INTERVAL_MS - 1):
            raise EvidenceHold("V5_LEDGER_NOT_FULLY_CLOSED")

    def bootstrap_rest(self, symbol: str, rows: Sequence[list], *,
                       event_open_ms: int, observed_ms: int) -> int:
        """Exactly 96 real closed 5m REST bars; no historic liquidity claims."""
        self._valid_event(symbol, event_open_ms, observed_ms)
        try:
            bars = tuple(_row(x) for x in decode_klines(
                rows, event_open_ms=event_open_ms
            ))
        except (ValueError, TypeError, OverflowError) as exc:
            raise EvidenceHold("V5_LEDGER_REST_BOOTSTRAP_INVALID") from exc
        digest = _sha({"source": "REST_BOOTSTRAP", "bars": bars})
        if self._last(symbol) is not None:
            if (all(self._stored(symbol, bar[0]) == bar for bar in bars)
                    and self._last(symbol) == event_open_ms):
                return 0
            raise EvidenceHold("V5_LEDGER_ALREADY_BOOTSTRAPPED")
        with self.db:
            for bar in bars:
                self._insert(symbol, bar, "REST_BOOTSTRAP", observed_ms, digest)
        return len(bars)

    def append_wss_final(self, event: Mapping[str, object]) -> str:
        """Only finalized validated kline events; rejects missing candle gaps."""
        if (event.get("route") != "market"
                or event.get("kind") != "kline_5m"
                or event.get("closed") is not True
                or event.get("order_authority") != "NONE"):
            raise EvidenceHold("V5_LEDGER_NOT_VERIFIED_WSS_FINAL")
        symbol = event.get("symbol")
        if not isinstance(symbol, str):
            raise EvidenceHold("V5_LEDGER_SYMBOL_INVALID")
        bar = _row(event.get("candle"))
        received_ms = event.get("received_ms")
        self._valid_event(symbol, bar[0], received_ms)
        if received_ms < event.get("event_ms", 0):
            raise EvidenceHold("V5_LEDGER_WSS_EVENT_FUTURE")
        previous = self._last(symbol)
        if previous is None:
            with self.db:
                self._gate(symbol, "NOT_BOOTSTRAPPED", "OPEN", _sha(bar))
            return "HOLD_NOT_BOOTSTRAPPED"
        stored = self._stored(symbol, bar[0])
        if stored is not None:
            if stored == bar:
                return "UNCHANGED_REPLAY"
            with self.db:
                self._gate(symbol, "SOURCE_CONFLICT", "OPEN", _sha(bar))
            raise EvidenceHold("V5_LEDGER_SOURCE_CONFLICT")
        if ("CANDLE_GAP" in self._open_gates(symbol)
                or "SOURCE_CONFLICT" in self._open_gates(symbol)):
            return "HOLD_UNRESOLVED_SOURCE"
        if bar[0] < previous:
            return "OLD_FINAL_CANDLE_REJECTED"
        if bar[0] != previous + INTERVAL_MS:
            with self.db:
                self._gate(symbol, "CANDLE_GAP", "OPEN", _sha({
                    "expected": previous + INTERVAL_MS, "got": bar[0]
                }))
            return "HOLD_CANDLE_GAP"
        with self.db:
            self._insert(symbol, bar, "WSS_FINAL", received_ms,
                         _sha({"wss_final": bar, "event_ms": event["event_ms"]}))
        return "APPENDED_WSS_FINAL"

    def reconcile_rest_gap(self, symbol: str, rows: Sequence[list], *,
                           event_open_ms: int, observed_ms: int) -> int:
        """Reconcile historical candle gaps only, never trade/quote/cohort gaps.

        Requires overlapping 96-bar as-of REST proof and an existing WSS gap
        hold. Mismatched source bars permanently flag a conflict for review.
        """
        self._valid_event(symbol, event_open_ms, observed_ms)
        if "CANDLE_GAP" not in self._open_gates(symbol):
            raise EvidenceHold("V5_LEDGER_RECOVERY_NOT_REQUESTED")
        previous = self._last(symbol)
        if previous is None or event_open_ms <= previous:
            raise EvidenceHold("V5_LEDGER_RECOVERY_BAD_CURSOR")
        try:
            bars = tuple(_row(x) for x in decode_klines(
                rows, event_open_ms=event_open_ms
            ))
        except (ValueError, TypeError, OverflowError) as exc:
            raise EvidenceHold("V5_LEDGER_REST_RECOVERY_INVALID") from exc
        if bars[0][0] > previous:
            raise EvidenceHold("V5_LEDGER_RECOVERY_OVERLAP_REQUIRED")
        existing = self.db.execute(
            "SELECT open_ms, candle_json FROM candle_rows "
            "WHERE symbol=? AND open_ms>=? AND open_ms<=? ORDER BY open_ms",
            (symbol, bars[0][0], event_open_ms),
        ).fetchall()
        lookup = {bar[0]: bar for bar in bars}
        mismatch = [
            open_ms for open_ms, payload in existing
            if tuple(json.loads(payload)) != lookup.get(open_ms)
        ]
        if mismatch:
            with self.db:
                self._gate(symbol, "SOURCE_CONFLICT", "OPEN",
                           _sha({"mismatched_opens": mismatch}))
            raise EvidenceHold("V5_LEDGER_REST_WSS_MISMATCH")
        fresh = tuple(bar for bar in bars if bar[0] > previous)
        if not fresh or fresh[0][0] != previous + INTERVAL_MS:
            raise EvidenceHold("V5_LEDGER_RECOVERY_NOT_CONTIGUOUS")
        digest = _sha({"source": "REST_GAP_RECOVERY", "bars": bars})
        if "SOURCE_CONFLICT" in self._open_gates(symbol):
            raise EvidenceHold("V5_LEDGER_CONFLICT_NEEDS_MANUAL_REVIEW")
        with self.db:
            for bar in fresh:
                self._insert(symbol, bar, "REST_GAP_RECOVERY", observed_ms, digest)
            self._gate(symbol, "CANDLE_GAP", "RESOLVED", digest)
        return len(fresh)

    def inspect(self, symbol: str) -> dict:
        """Checks every immutable candle digest and contiguous event cursor."""
        rows = self.db.execute(
            "SELECT open_ms,candle_json,candle_sha FROM candle_rows "
            "WHERE symbol=? ORDER BY open_ms", (symbol,)
        ).fetchall()
        last = None
        for opened, payload, digest in rows:
            value = _row(json.loads(payload))
            if value[0] != opened or _sha(value) != digest:
                raise EvidenceHold("V5_LEDGER_CHECKSUM_FAILED")
            if last is not None and opened != last + INTERVAL_MS:
                raise EvidenceHold("V5_LEDGER_STORED_GAP")
            last = opened
        healthy_sqlite = self.db.execute("PRAGMA quick_check").fetchone()[0]
        if healthy_sqlite != "ok":
            raise EvidenceHold("V5_LEDGER_SQLITE_INTEGRITY_FAILED")
        gates = self._open_gates(symbol)
        return {
            "symbol": symbol,
            "schema": SCHEMA,
            "closed_bar_count": len(rows),
            "last_event_open_ms": last,
            "open_candle_gates": gates,
            "candle_contiguous": bool(rows) and not gates,
            "quote_health": "UNVERIFIED",
            "trade_health": "UNVERIFIED",
            "cohort_health": "UNVERIFIED",
            "research_ready": False,
            "training_labels_matured": 0,
            "order_authority": "NONE",
        }
