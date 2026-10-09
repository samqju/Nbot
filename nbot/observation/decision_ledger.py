"""High-resolution decision outcome ledger for rejected and approved hypotheses.

This store is research-only. It never submits orders and never calls Execution.
Every frozen symbol/side decision can become a four-hour counterfactual experiment
driven by chronological Binance aggregate trades. The result is explicitly not
actual execution PnL.

The simulation mirrors the current LIVE/PAPER risk geometry:
- decision-time executable bid/ask;
- $1,000 notional and $10 configured risk by default;
- adverse entry/exit slippage proxy of 2 bps;
- 5 bps taker fee per side;
- initial stop rebuilt around the simulated fill, matching Execution;
- INTEGER_R_STEP_CONTROL trailing stop around the simulated fill;
- stop crossing is checked before favorable progress on every aggTrade.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable

from nbot.common.market import AggTrade

VERSION = "DECISION_OUTCOME_LEDGER_V1"
AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"
PATH_SOURCE = "BINANCE_USDM_AGGTRADE"
HORIZON_MS = 4 * 60 * 60 * 1000

SCHEMA = """
CREATE TABLE IF NOT EXISTS decision_ledger_meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_hypotheses(
    hypothesis_id TEXT PRIMARY KEY,
    release_sha TEXT NOT NULL,
    profile TEXT NOT NULL CHECK(profile IN ('live-paper','live-trade')),
    event_ms INTEGER NOT NULL,
    decision_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('LONG','SHORT')),
    selected INTEGER NOT NULL CHECK(selected IN (0,1)),
    decision TEXT NOT NULL CHECK(decision IN ('APPROVED','REJECTED')),
    blocker TEXT,
    horizon_ms INTEGER NOT NULL,
    frozen_json TEXT NOT NULL,
    frozen_digest TEXT NOT NULL,
    state_json TEXT NOT NULL,
    state_digest TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('OPEN','MATURED','UNSCORABLE')),
    result_json TEXT,
    result_digest TEXT,
    matured_at_ms INTEGER,
    UNIQUE(release_sha,profile,event_ms,symbol,side)
);
CREATE INDEX IF NOT EXISTS decision_hypotheses_open_symbol
ON decision_hypotheses(status,symbol,decision_ms);
CREATE INDEX IF NOT EXISTS decision_hypotheses_event
ON decision_hypotheses(event_ms,symbol,side);
CREATE INDEX IF NOT EXISTS decision_hypotheses_matured
ON decision_hypotheses(status,matured_at_ms);
CREATE TABLE IF NOT EXISTS decision_ledger_conflicts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id TEXT NOT NULL,
    observed_at_ms INTEGER NOT NULL,
    existing_digest TEXT NOT NULL,
    incoming_digest TEXT NOT NULL
);
"""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _finite(name: str, value: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name}_INVALID")
    if positive and number <= 0:
        raise ValueError(f"{name}_INVALID")
    if nonnegative and number < 0:
        raise ValueError(f"{name}_INVALID")
    return number


@dataclass(frozen=True)
class DecisionLedgerConfig:
    risk_usd: float = 10.0
    notional_usd: float = 1_000.0
    entry_slippage_pct: float = 0.02
    exit_slippage_pct: float = 0.02
    taker_fee_rate: float = 0.0005
    horizon_ms: int = HORIZON_MS

    def validate(self) -> None:
        risk = _finite("DECISION_LEDGER_RISK_USD", self.risk_usd, positive=True)
        notional = _finite("DECISION_LEDGER_NOTIONAL_USD", self.notional_usd, positive=True)
        if risk >= notional:
            raise ValueError("DECISION_LEDGER_RISK_NOTIONAL_INVALID")
        _finite("DECISION_LEDGER_ENTRY_SLIPPAGE", self.entry_slippage_pct, nonnegative=True)
        _finite("DECISION_LEDGER_EXIT_SLIPPAGE", self.exit_slippage_pct, nonnegative=True)
        fee = _finite("DECISION_LEDGER_FEE", self.taker_fee_rate, nonnegative=True)
        if fee >= 1:
            raise ValueError("DECISION_LEDGER_FEE_INVALID")
        if isinstance(self.horizon_ms, bool) or not isinstance(self.horizon_ms, int) or self.horizon_ms != HORIZON_MS:
            raise ValueError("DECISION_LEDGER_HORIZON_INVALID")


class DecisionOutcomeLedger:
    def __init__(
        self,
        path: Path | str = Path("data/observation/live/decision_outcomes.db"),
        *,
        config: DecisionLedgerConfig | None = None,
    ) -> None:
        self.path = Path(path)
        self.config = config or DecisionLedgerConfig()
        self.config.validate()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            meta = {
                "version": VERSION,
                "authority": AUTHORITY,
                "path_source": PATH_SOURCE,
                "counterfactual_not_execution_pnl": True,
                "config": {
                    "risk_usd": self.config.risk_usd,
                    "notional_usd": self.config.notional_usd,
                    "entry_slippage_pct": self.config.entry_slippage_pct,
                    "exit_slippage_pct": self.config.exit_slippage_pct,
                    "taker_fee_rate": self.config.taker_fee_rate,
                    "horizon_ms": self.config.horizon_ms,
                },
            }
            raw = _json(meta)
            row = conn.execute("SELECT value FROM decision_ledger_meta WHERE key='definition'").fetchone()
            if row is None:
                conn.execute("INSERT INTO decision_ledger_meta VALUES('definition',?)", (raw,))
            elif row[0] != raw:
                raise ValueError("DECISION_LEDGER_DEFINITION_MISMATCH")

    @staticmethod
    def _hypothesis_id(release_sha: str, profile: str, event_ms: int, symbol: str, side: str) -> str:
        raw = f"{VERSION}|{release_sha}|{profile}|{event_ms}|{symbol}|{side}".encode()
        return "CF-" + hashlib.sha256(raw).hexdigest()[:48]

    @staticmethod
    def _signed_r(side: str, price: float, fill: float, per_r_price: float) -> float:
        sign = 1.0 if side == "LONG" else -1.0
        return sign * (float(price) - float(fill)) / float(per_r_price)

    @staticmethod
    def _price_for_r(side: str, r_value: float, fill: float, per_r_price: float) -> float:
        sign = 1.0 if side == "LONG" else -1.0
        return float(fill) + sign * float(r_value) * float(per_r_price)

    def record(self, *, release_sha: str, profile: str, event_ms: int, decision_ms: int,
               symbol: str, side: str, bid: float, ask: float, selected: bool,
               decision: str, blocker: str | None, feature_vector: dict[str, Any],
               candidate_ids: Iterable[str], scores: dict[str, Any],
               rank: int, model_digest: str | None = None) -> str:
        release_sha = str(release_sha).strip().lower()
        profile = str(profile).strip().lower()
        symbol = str(symbol).strip().upper()
        side = str(side).strip().upper()
        if len(release_sha) != 40 or any(c not in "0123456789abcdef" for c in release_sha):
            raise ValueError("DECISION_LEDGER_RELEASE_SHA_INVALID")
        if profile not in {"live-paper", "live-trade"}:
            raise ValueError("DECISION_LEDGER_PROFILE_INVALID")
        if side not in {"LONG", "SHORT"}:
            raise ValueError("DECISION_LEDGER_SIDE_INVALID")
        if decision not in {"APPROVED", "REJECTED"} or bool(selected) != (decision == "APPROVED"):
            raise ValueError("DECISION_LEDGER_DECISION_INVALID")
        bid = _finite("DECISION_LEDGER_BID", bid, positive=True)
        ask = _finite("DECISION_LEDGER_ASK", ask, positive=True)
        if ask < bid:
            raise ValueError("DECISION_LEDGER_CROSSED_QUOTE")
        if not isinstance(event_ms, int) or not isinstance(decision_ms, int) or event_ms <= 0 or decision_ms <= 0:
            raise ValueError("DECISION_LEDGER_TIME_INVALID")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
            raise ValueError("DECISION_LEDGER_RANK_INVALID")

        executable = ask if side == "LONG" else bid
        adverse_entry = self.config.entry_slippage_pct / 100.0
        fill = executable * (1.0 + adverse_entry if side == "LONG" else 1.0 - adverse_entry)
        quantity = self.config.notional_usd / executable
        per_r_price = self.config.risk_usd / quantity
        # Execution rebuilds the protective stop around the actual fill after
        # entry. Mirror that geometry here instead of leaving the stop anchored
        # to the pre-fill executable quote.
        initial_stop = fill - per_r_price if side == "LONG" else fill + per_r_price
        initial_stop_r = self._signed_r(side, initial_stop, fill, per_r_price)
        candidates = sorted({str(x) for x in candidate_ids if str(x)})
        frozen = {
            "version": VERSION, "authority": AUTHORITY,
            "counterfactual_not_execution_pnl": True,
            "event_ms": int(event_ms), "decision_ms": int(decision_ms),
            "release_sha": release_sha, "profile": profile, "symbol": symbol, "side": side,
            "selected": bool(selected), "decision": decision, "blocker": blocker,
            "rank": rank, "candidate_ids": candidates,
            "feature_vector": feature_vector, "scores": scores,
            "model_digest": model_digest,
            "decision_quote": {"bid": bid, "ask": ask},
            "entry_assumption": {
                "mode": "DECISION_TIME_EXECUTABLE_PLUS_FIXED_ADVERSE_SLIPPAGE",
                "executable_price": executable, "simulated_fill_price": fill,
                "quantity": quantity, "notional_usd": self.config.notional_usd,
                "risk_usd": self.config.risk_usd, "per_r_price": per_r_price,
                "initial_stop_price": initial_stop,
                "initial_stop_r_from_fill": initial_stop_r,
                "entry_slippage_pct": self.config.entry_slippage_pct,
                "exit_slippage_pct": self.config.exit_slippage_pct,
                "taker_fee_rate": self.config.taker_fee_rate,
            },
            "exit_policy": "INTEGER_R_STEP_CONTROL_EXECUTION_ALIGNED",
            "path_source": PATH_SOURCE,
            "horizon_ms": self.config.horizon_ms,
        }
        state = {
            "entry_price": fill, "quantity": quantity, "per_r_price": per_r_price,
            "initial_stop_price": initial_stop, "stop_price": initial_stop,
            "stop_r": initial_stop_r, "peak_r": 0.0, "mfe_r": 0.0, "mae_r": 0.0,
            "last_price": None, "last_trade_time_ms": None, "last_agg_id": None,
            "trade_count": 0, "backfill_trade_count": 0,
            "stream_gap_count": 0, "unresolved_gap_count": 0,
            "crossings": {}, "stop_trace": [[int(decision_ms), initial_stop_r, initial_stop, "INITIAL_RISK"]],
        }
        hypothesis_id = self._hypothesis_id(release_sha, profile, event_ms, symbol, side)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT frozen_json,frozen_digest FROM decision_hypotheses WHERE hypothesis_id=?",
                (hypothesis_id,),
            ).fetchone()
            if existing is not None:
                incoming_json, incoming_digest = _json(frozen), _digest(frozen)
                if existing != (incoming_json, incoming_digest):
                    # The first causal freeze always wins. A retry/restart may
                    # recompute later wall-clock metadata, but research must not
                    # rewrite what was first observed. Preserve the conflict as
                    # diagnostics without affecting recommendation authority.
                    conn.execute(
                        "INSERT INTO decision_ledger_conflicts("
                        "hypothesis_id,observed_at_ms,existing_digest,incoming_digest"
                        ") VALUES(?,?,?,?)",
                        (hypothesis_id, int(time.time() * 1000), str(existing[1]), incoming_digest),
                    )
                return hypothesis_id
            conn.execute(
                "INSERT INTO decision_hypotheses VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    hypothesis_id, release_sha, profile, event_ms, decision_ms, symbol, side,
                    int(selected), decision, blocker, self.config.horizon_ms,
                    _json(frozen), _digest(frozen), _json(state), _digest(state),
                    "OPEN", None, None, None,
                ),
            )
        return hypothesis_id

    @staticmethod
    def _verified(raw: str, digest: str) -> dict[str, Any]:
        value = json.loads(raw)
        if _digest(value) != digest:
            raise ValueError("DECISION_LEDGER_DIGEST_MISMATCH")
        return value

    def pending_symbols(self) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM decision_hypotheses WHERE status='OPEN' ORDER BY symbol"
            ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def catchup_start_ms(self, symbol: str) -> int | None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT decision_ms,state_json,state_digest FROM decision_hypotheses "
                "WHERE status='OPEN' AND symbol=?",
                (str(symbol).upper(),),
            ).fetchall()
        starts: list[int] = []
        for decision_ms, raw, check in rows:
            state = self._verified(raw, check)
            last = state.get("last_trade_time_ms")
            # Start inclusively at the last persisted millisecond. Multiple
            # aggregate trades can share one timestamp; aggregate-trade ID
            # deduplication inside replay safely removes the already-committed
            # event without losing later IDs from the same millisecond.
            starts.append(int(decision_ms) if last is None else int(last))
        return min(starts) if starts else None

    def mark_stream_gap(self, *, at_ms: int, symbol: str | None = None) -> int:
        updated = 0
        target = None if symbol is None else str(symbol).strip().upper()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if target is None:
                rows = conn.execute(
                    "SELECT hypothesis_id,state_json,state_digest FROM decision_hypotheses "
                    "WHERE status='OPEN'"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT hypothesis_id,state_json,state_digest FROM decision_hypotheses "
                    "WHERE status='OPEN' AND symbol=?",
                    (target,),
                ).fetchall()
            for hid, raw, check in rows:
                state = self._verified(raw, check)
                state["stream_gap_count"] = int(state["stream_gap_count"]) + 1
                state["unresolved_gap_count"] = int(state["unresolved_gap_count"]) + 1
                state["last_gap_at_ms"] = int(at_ms)
                conn.execute(
                    "UPDATE decision_hypotheses SET state_json=?,state_digest=? WHERE hypothesis_id=?",
                    (_json(state), _digest(state), hid),
                )
                updated += 1
        return updated

    def resolve_stream_gap(self, symbol: str) -> int:
        """Mark a fully backfilled symbol chronology as resolved.

        Backfill can itself cross a stop and mature a hypothesis before this
        method runs. Therefore both OPEN state and already-MATURED results must
        be repaired atomically; otherwise a completely backfilled path would be
        permanently excluded from training as an unresolved gap.
        """
        updated = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT hypothesis_id,status,state_json,state_digest,result_json,result_digest "
                "FROM decision_hypotheses WHERE status IN ('OPEN','MATURED') AND symbol=?",
                (str(symbol).upper(),),
            ).fetchall()
            for hid, status, state_raw, state_check, result_raw, result_check in rows:
                state = self._verified(state_raw, state_check)
                if int(state.get("unresolved_gap_count", 0)) <= 0:
                    continue
                state["unresolved_gap_count"] = 0
                if status == "MATURED":
                    if result_raw is None or result_check is None:
                        raise ValueError("DECISION_LEDGER_MATURED_RESULT_MISSING")
                    result = self._verified(result_raw, result_check)
                    result["unresolved_gap_count"] = 0
                    result["path_quality"] = "AGGTRADE_RESOLVED"
                    conn.execute(
                        "UPDATE decision_hypotheses SET state_json=?,state_digest=?,"
                        "result_json=?,result_digest=? WHERE hypothesis_id=?",
                        (_json(state), _digest(state), _json(result), _digest(result), hid),
                    )
                else:
                    conn.execute(
                        "UPDATE decision_hypotheses SET state_json=?,state_digest=? WHERE hypothesis_id=?",
                        (_json(state), _digest(state), hid),
                    )
                updated += 1
        return updated

    def on_agg_trade(self, trade: AggTrade, *, source: str = "WSS") -> int:
        """Compatibility wrapper for one event.

        Realtime replay should prefer :meth:`on_agg_trades` so a burst of
        Binance events is applied in one SQLite transaction per batch rather
        than one transaction per market event.
        """
        return self.on_agg_trades((trade,), source=source)

    def on_agg_trades(self, trades: Iterable[AggTrade], *, source: str = "WSS") -> int:
        """Replay a chronological batch and persist each hypothesis at most once.

        The Binance stream can produce many aggregate trades per second across a
        wide universe. Doing a SQLite read/write transaction for every aggTrade
        would make the research recorder itself the bottleneck and could block
        the WebSocket receive thread. Batching preserves exact per-symbol event
        order while reducing durable writes to one final state per affected
        hypothesis (or one sealed result when a stop/horizon is reached).

        Crash recovery remains causal: the last persisted aggregate-trade ID and
        timestamp are a checkpoint, and the passive service REST-backfills from
        that checkpoint before resuming WSS replay.
        """
        if source not in {"WSS", "REST_BACKFILL"}:
            raise ValueError("DECISION_LEDGER_PATH_SOURCE_INVALID")
        materialized = tuple(trades)
        if not materialized:
            return 0
        grouped: dict[str, list[AggTrade]] = {}
        for trade in materialized:
            if not isinstance(trade, AggTrade):
                raise TypeError("DECISION_LEDGER_AGGTRADE_INVALID")
            grouped.setdefault(trade.symbol, []).append(trade)
        for rows in grouped.values():
            rows.sort(key=lambda item: (int(item.trade_time_ms), int(item.aggregate_trade_id)))

        touched = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for symbol in sorted(grouped):
                symbol_trades = grouped[symbol]
                max_time = int(symbol_trades[-1].trade_time_ms)
                rows = conn.execute(
                    "SELECT hypothesis_id,decision_ms,side,frozen_json,frozen_digest,"
                    "state_json,state_digest FROM decision_hypotheses "
                    "WHERE status='OPEN' AND symbol=? AND decision_ms<=? ORDER BY decision_ms",
                    (symbol, max_time),
                ).fetchall()
                for hid, decision_ms, side, frozen_raw, frozen_check, state_raw, state_check in rows:
                    frozen = self._verified(frozen_raw, frozen_check)
                    state = self._verified(state_raw, state_check)
                    last_id = state.get("last_agg_id")
                    last_time = state.get("last_trade_time_ms")
                    changed = False
                    matured = False
                    horizon_end = int(decision_ms) + int(frozen["horizon_ms"])

                    for trade in symbol_trades:
                        trade_time = int(trade.trade_time_ms)
                        trade_id = int(trade.aggregate_trade_id)
                        if trade_time < int(decision_ms):
                            continue
                        if last_id is not None and trade_id <= int(last_id):
                            continue
                        if last_time is not None and trade_time < int(last_time):
                            continue
                        if trade_time > horizon_end:
                            if state.get("last_price") is not None:
                                self._mature_in_tx(
                                    conn, hid, frozen, state,
                                    exit_price_raw=state["last_price"],
                                    exit_time_ms=horizon_end,
                                    exit_reason="HORIZON_4H",
                                )
                            else:
                                result = {
                                    "version": VERSION,
                                    "status": "UNSCORABLE",
                                    "reason": "NO_AGGTRADE_PATH",
                                    "counterfactual_not_execution_pnl": True,
                                    "path_quality": "UNRESOLVED",
                                }
                                conn.execute(
                                    "UPDATE decision_hypotheses SET status='UNSCORABLE',"
                                    "result_json=?,result_digest=?,matured_at_ms=? WHERE hypothesis_id=?",
                                    (_json(result), _digest(result), int(time.time() * 1000), hid),
                                )
                            matured = True
                            changed = True
                            break

                        price = float(trade.price)
                        fill = float(state["entry_price"])
                        per_r = float(state["per_r_price"])
                        current_r = self._signed_r(side, price, fill, per_r)
                        state["mae_r"] = min(float(state["mae_r"]), current_r, 0.0)
                        stop = float(state["stop_price"])

                        # Active protection wins before favorable progress at
                        # this same chronological market event.
                        hit = price <= stop if side == "LONG" else price >= stop
                        state["last_price"] = price
                        state["last_trade_time_ms"] = trade_time
                        state["last_agg_id"] = trade_id
                        state["trade_count"] = int(state["trade_count"]) + 1
                        if source == "REST_BACKFILL":
                            state["backfill_trade_count"] = int(state["backfill_trade_count"]) + 1
                        changed = True
                        last_id, last_time = trade_id, trade_time

                        if hit:
                            self._mature_in_tx(
                                conn, hid, frozen, state,
                                exit_price_raw=price,
                                exit_time_ms=trade_time,
                                exit_reason="STOP",
                            )
                            matured = True
                            break

                        peak = max(float(state["peak_r"]), current_r, 0.0)
                        state["peak_r"] = peak
                        state["mfe_r"] = max(float(state["mfe_r"]), current_r, 0.0)
                        crossings = dict(state["crossings"])
                        for level in range(1, int(math.floor(peak + 1e-12)) + 1):
                            crossings.setdefault(f"+{level}R", trade_time)
                        state["crossings"] = crossings

                        if peak >= 1.0:
                            locked_r = float(math.floor(peak + 1e-12) - 1)
                            target = self._price_for_r(side, locked_r, fill, per_r)
                            current_stop = float(state["stop_price"])
                            tighter = (
                                target > current_stop + 1e-12
                                if side == "LONG"
                                else target < current_stop - 1e-12
                            )
                            if tighter:
                                state["stop_price"] = target
                                state["stop_r"] = locked_r
                                trace = list(state["stop_trace"])
                                trace.append([trade_time, locked_r, target, "INTEGER_R_STEP"])
                                state["stop_trace"] = trace

                    if changed and not matured:
                        conn.execute(
                            "UPDATE decision_hypotheses SET state_json=?,state_digest=? "
                            "WHERE hypothesis_id=?",
                            (_json(state), _digest(state), hid),
                        )
                    touched += int(changed)
        return touched

    def expire(self, *, now_ms: int | None = None) -> int:
        now = int(time.time() * 1000) if now_ms is None else int(now_ms)
        matured = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT hypothesis_id,decision_ms,frozen_json,frozen_digest,state_json,state_digest "
                "FROM decision_hypotheses WHERE status='OPEN' AND decision_ms+horizon_ms<=?",
                (now,),
            ).fetchall()
            for hid, decision_ms, frozen_raw, frozen_check, state_raw, state_check in rows:
                frozen = self._verified(frozen_raw, frozen_check)
                state = self._verified(state_raw, state_check)
                # Never seal a horizon result across a known chronology gap.
                # Keep it OPEN so the passive service can REST-backfill first.
                if int(state.get("unresolved_gap_count", 0)) > 0:
                    continue
                if state.get("last_price") is None:
                    result = {
                        "version": VERSION, "status": "UNSCORABLE",
                        "reason": "NO_AGGTRADE_PATH", "counterfactual_not_execution_pnl": True,
                        "path_quality": "UNRESOLVED",
                    }
                    conn.execute(
                        "UPDATE decision_hypotheses SET status='UNSCORABLE',result_json=?,result_digest=?,matured_at_ms=? "
                        "WHERE hypothesis_id=?",
                        (_json(result), _digest(result), now, hid),
                    )
                else:
                    self._mature_in_tx(
                        conn, hid, frozen, state,
                        exit_price_raw=float(state["last_price"]),
                        exit_time_ms=int(decision_ms) + int(frozen["horizon_ms"]),
                        exit_reason="HORIZON_4H",
                    )
                matured += 1
        return matured

    def _mature_in_tx(self, conn: sqlite3.Connection, hid: str, frozen: dict[str, Any],
                      state: dict[str, Any], *, exit_price_raw: Any,
                      exit_time_ms: int, exit_reason: str) -> None:
        if exit_price_raw is None:
            raise ValueError("DECISION_LEDGER_EXIT_PRICE_MISSING")
        raw_exit = _finite("DECISION_LEDGER_EXIT_PRICE", exit_price_raw, positive=True)
        side = str(frozen["side"])
        adverse = self.config.exit_slippage_pct / 100.0
        exit_price = raw_exit * (1.0 - adverse if side == "LONG" else 1.0 + adverse)
        fill = float(state["entry_price"])
        quantity = float(state["quantity"])
        sign = 1.0 if side == "LONG" else -1.0
        gross_usd = sign * (exit_price - fill) * quantity
        entry_fee = fill * quantity * self.config.taker_fee_rate
        exit_fee = exit_price * quantity * self.config.taker_fee_rate
        fee_usd = entry_fee + exit_fee
        net_usd = gross_usd - fee_usd
        gross_r = gross_usd / self.config.risk_usd
        net_r = net_usd / self.config.risk_usd
        gaps = int(state.get("unresolved_gap_count", 0))
        path_quality = "AGGTRADE_RESOLVED" if gaps == 0 else "AGGTRADE_UNRESOLVED_GAP"
        if frozen["decision"] == "REJECTED":
            if net_r > 0.05:
                assessment = "MISSED_PROFITABLE_POLICY_OUTCOME"
            elif net_r < -0.05:
                assessment = "AVOIDED_LOSS"
            else:
                assessment = "REJECTED_FLAT"
        else:
            assessment = "APPROVED_COUNTERFACTUAL"
        result = {
            "version": VERSION, "authority": AUTHORITY,
            "counterfactual_not_execution_pnl": True,
            "path_source": PATH_SOURCE, "path_quality": path_quality,
            "exit_reason": exit_reason, "exit_time_ms": int(exit_time_ms),
            "raw_crossing_price": raw_exit, "exit_price_after_slippage": exit_price,
            "gross_usd": gross_usd, "fee_usd": fee_usd,
            "funding_cost_usd": None, "funding_cost_frac": None,
            "funding_complete": False,
            "cost_basis": "TAKER_FEES_AND_FIXED_SLIPPAGE_V1_FUNDING_PENDING",
            "net_usd_before_funding": net_usd,
            "gross_r": gross_r, "net_r_before_funding": net_r,
            "target_net_r": None,
            "mfe_r": float(state["mfe_r"]), "mae_r": float(state["mae_r"]),
            "peak_r": float(state["peak_r"]), "final_stop_r": float(state["stop_r"]),
            "crossings": state["crossings"], "stop_trace": state["stop_trace"],
            "trade_count": int(state["trade_count"]),
            "backfill_trade_count": int(state["backfill_trade_count"]),
            "stream_gap_count": int(state["stream_gap_count"]),
            "unresolved_gap_count": gaps,
            "assessment": assessment,
        }
        conn.execute(
            "UPDATE decision_hypotheses SET state_json=?,state_digest=?,status='MATURED',"
            "result_json=?,result_digest=?,matured_at_ms=? WHERE hypothesis_id=?",
            (_json(state), _digest(state), _json(result), _digest(result), int(time.time() * 1000), hid),
        )

    def funding_requirement_start_ms(self) -> int | None:
        """Earliest decision whose matured result still needs funding proof."""
        starts: list[int] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT decision_ms,result_json,result_digest FROM decision_hypotheses "
                "WHERE status='MATURED' ORDER BY decision_ms"
            ).fetchall()
        for decision_ms, raw, check in rows:
            result = self._verified(raw, check)
            if not bool(result.get("funding_complete")):
                starts.append(int(decision_ms))
        return min(starts) if starts else None

    def finalize_funding(
        self,
        funding_events: Iterable[Any],
        *,
        coverage_start_ms: int | None = None,
        coverage_end_ms: int | None = None,
    ) -> int:
        """Complete cost accounting after stop/horizon using actual funding events.

        When coverage bounds are supplied, a result is finalized only if its
        complete decision-to-exit interval is inside the proven query window.
        This prevents a service restart from incorrectly treating missing old
        funding history as a zero-funding interval.
        """
        events_by_symbol: dict[str, list[tuple[int, float]]] = {}
        for item in funding_events:
            symbol = str(getattr(item, "symbol", item.get("symbol") if isinstance(item, dict) else "")).upper()
            when = getattr(item, "funding_time_ms", item.get("funding_time_ms") if isinstance(item, dict) else None)
            rate = getattr(item, "funding_rate", item.get("funding_rate") if isinstance(item, dict) else None)
            if not symbol or when is None or rate is None:
                raise ValueError("DECISION_LEDGER_FUNDING_EVENT_INVALID")
            events_by_symbol.setdefault(symbol, []).append((int(when), float(rate)))

        completed = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT hypothesis_id,decision_ms,symbol,side,frozen_json,frozen_digest,"
                "state_json,state_digest,result_json,result_digest "
                "FROM decision_hypotheses WHERE status='MATURED'"
            ).fetchall()
            for hid, decision_ms, symbol, side, frozen_raw, frozen_check, state_raw, state_check, result_raw, result_check in rows:
                frozen = self._verified(frozen_raw, frozen_check)
                state = self._verified(state_raw, state_check)
                result = self._verified(result_raw, result_check)
                if bool(result.get("funding_complete")):
                    continue
                exit_ms = int(result["exit_time_ms"])
                if coverage_start_ms is not None and int(decision_ms) < int(coverage_start_ms):
                    continue
                if coverage_end_ms is not None and exit_ms > int(coverage_end_ms):
                    continue
                rates = [
                    rate for when, rate in events_by_symbol.get(str(symbol), [])
                    if int(decision_ms) < when <= exit_ms
                ]
                funding_frac = sum(rates) if side == "LONG" else -sum(rates)
                notional = float(state["entry_price"]) * float(state["quantity"])
                funding_usd = funding_frac * notional
                net_usd = float(result["net_usd_before_funding"]) - funding_usd
                net_r = net_usd / self.config.risk_usd
                result["funding_cost_frac"] = funding_frac
                result["funding_cost_usd"] = funding_usd
                result["funding_complete"] = True
                result["cost_basis"] = "TAKER_FEES_FIXED_SLIPPAGE_AND_ACTUAL_FUNDING_V1"
                result["net_usd"] = net_usd
                result["target_net_r"] = net_r
                if frozen["decision"] == "REJECTED":
                    result["assessment"] = (
                        "MISSED_PROFITABLE_POLICY_OUTCOME" if net_r > 0.05
                        else "AVOIDED_LOSS" if net_r < -0.05
                        else "REJECTED_FLAT"
                    )
                conn.execute(
                    "UPDATE decision_hypotheses SET result_json=?,result_digest=? WHERE hypothesis_id=?",
                    (_json(result), _digest(result), hid),
                )
                completed += 1
        return completed

    def training_targets(
        self, *, profile: str = "live-paper", through_event_ms: int | None = None
    ) -> dict[tuple[int, str, str], dict[str, Any]]:
        profile = str(profile).strip().lower()
        if profile not in {"live-paper", "live-trade"}:
            raise ValueError("DECISION_LEDGER_PROFILE_INVALID")
        sql = (
            "SELECT event_ms,symbol,side,frozen_json,frozen_digest,result_json,result_digest "
            "FROM decision_hypotheses WHERE status='MATURED' AND profile=?"
        )
        params: list[Any] = [profile]
        if through_event_ms is not None:
            sql += " AND event_ms<=?"
            params.append(int(through_event_ms))
        sql += " ORDER BY event_ms,symbol,side"
        output: dict[tuple[int, str, str], dict[str, Any]] = {}
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        for event_ms, symbol, side, frozen_raw, frozen_check, result_raw, result_check in rows:
            frozen = self._verified(frozen_raw, frozen_check)
            result = self._verified(result_raw, result_check)
            if result.get("path_quality") != "AGGTRADE_RESOLVED" or not bool(result.get("funding_complete")):
                continue
            output[(int(event_ms), str(symbol), str(side))] = {
                "event_ms": int(event_ms), "decision_ms": int(frozen["decision_ms"]),
                "symbol": str(symbol), "side": str(side),
                "feature_vector": frozen["feature_vector"],
                "scores": frozen["scores"], "rank": frozen["rank"],
                "selected": frozen["selected"], "decision": frozen["decision"],
                "blocker": frozen.get("blocker"),
                "target_net_r": float(result["target_net_r"]),
                "mfe_r": float(result["mfe_r"]), "mae_r": float(result["mae_r"]),
                "exit_time_ms": int(result["exit_time_ms"]),
                "assessment": result["assessment"],
            }
        return output

    def decision_policy_rows(self, *, profile: str = "live-paper") -> list[dict[str, Any]]:
        targets = self.training_targets(profile=profile)
        return sorted(targets.values(), key=lambda r: (r["event_ms"], r["rank"], r["symbol"], r["side"]))

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            counts = dict(conn.execute(
                "SELECT status,COUNT(*) FROM decision_hypotheses GROUP BY status"
            ).fetchall())
            rejected = int(conn.execute(
                "SELECT COUNT(*) FROM decision_hypotheses WHERE decision='REJECTED'"
            ).fetchone()[0])
            approved = int(conn.execute(
                "SELECT COUNT(*) FROM decision_hypotheses WHERE decision='APPROVED'"
            ).fetchone()[0])
            conflicts = int(conn.execute(
                "SELECT COUNT(*) FROM decision_ledger_conflicts"
            ).fetchone()[0])
            quality = conn.execute(
                "SELECT result_json,result_digest FROM decision_hypotheses WHERE status='MATURED'"
            ).fetchall()
        resolved = missed = avoided = 0
        for raw, check in quality:
            result = self._verified(raw, check)
            resolved += int(result.get("path_quality") == "AGGTRADE_RESOLVED")
            missed += int(result.get("assessment") == "MISSED_PROFITABLE_POLICY_OUTCOME")
            avoided += int(result.get("assessment") == "AVOIDED_LOSS")
        return {
            "version": VERSION, "authority": AUTHORITY, "database": str(self.path),
            "open": int(counts.get("OPEN", 0)), "matured": int(counts.get("MATURED", 0)),
            "unscorable": int(counts.get("UNSCORABLE", 0)),
            "approved_hypotheses": approved, "rejected_hypotheses": rejected,
            "immutable_retry_conflicts": conflicts,
            "aggtrade_resolved": resolved,
            "funding_complete": sum(
                1 for raw, check in quality
                if bool(self._verified(raw, check).get("funding_complete"))
            ),
            "missed_profitable_policy_outcomes": missed, "avoided_losses": avoided,
            "pending_symbols": len(self.pending_symbols()),
            "counterfactual_not_execution_pnl": True,
        }
