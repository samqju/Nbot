"""NBOT V4 clean-slate fixed-capacity virtual research factory.

V4 owns a new research ledger.  It reuses only canonical features and the proven
credential-free WSS replay machinery; it does not reuse V2/V3 fitted models,
artifacts, approvals, or outcomes.

Contract:
- target 100 concurrent virtual research trades;
- open/refill only on completed 5-minute events;
- WSS evaluates open paths continuously;
- same symbol+side may have at most one open V4 research trade;
- LONG and SHORT for the same symbol are independent research hypotheses;
- every 1,000 resolved research trades closes one generation batch;
- no order authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any

from .candidate_setups import load_histories, matches
from .counterfactual import ReplayCosts, TrailPolicy
from .decision_ledger import FrozenDecision
from .features import CanonicalFeatureStore
from .learned_recommendation import SIGNAL_INPUTS, _feature_vector
from .live_two_tier import ResearchWssFeed
from .research_replay import ReplayHypothesis
from .redesign_runtime import V3ResearchRuntime
from .signals import ResearchSignalStore
from .wss_market import plan_combined_streams

VERSION = "NBOT_V4_RESEARCH_FACTORY_V1"
AUTHORITY = "V4_RESEARCH_ONLY_NO_EXECUTION"
ORDER_AUTHORITY = "NONE"
CAPACITY = 100
BATCH_SIZE = 1000
INTERVAL_MS = 300_000
HORIZON_MS = 4 * 60 * 60 * 1000
UNIVERSE_SYMBOLS = 100


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class V4Candidate:
    symbol: str
    side: str
    vector: dict[str, Any]
    setup_tags: tuple[dict[str, str], ...]
    atr_frac: float
    selection_rank: int
    bid: float
    ask: float
    research_priority: tuple[Any, ...]


class V4CandidateScanner:
    """Model-free bootstrap scanner; no V2/V3 score is used."""

    def __init__(self, database) -> None:
        self.database = database
        self.features = CanonicalFeatureStore(database)
        self.signals = ResearchSignalStore(database)

    def scan(self, *, event_open_ms: int, now_ms: int) -> tuple[V4Candidate, ...]:
        with self.database.connection() as conn:
            event = conn.execute(
                "SELECT event_close_ms,captured_at_ms FROM market_events "
                "WHERE event_open_ms=? AND status='COMPLETE'",
                (int(event_open_ms),),
            ).fetchone()
            quotes = conn.execute(
                """SELECT s.symbol,s.bid_price,s.ask_price,s.captured_at_ms
                   FROM market_snapshots s
                   JOIN event_provenance p USING(event_open_ms)
                   WHERE s.event_open_ms=?
                     AND p.evidence_mode='LIVE_POINT_IN_TIME'
                     AND p.context_complete=1
                     AND p.membership_quality='POINT_IN_TIME'
                   ORDER BY s.symbol""",
                (int(event_open_ms),),
            ).fetchall()
        if event is None:
            return ()
        close_ms, captured_at_ms = map(int, event)
        if not close_ms <= captured_at_ms <= int(now_ms):
            return ()
        quote_map = {
            str(symbol): (float(bid), float(ask))
            for symbol, bid, ask, _captured in quotes
            if float(bid) > 0 and float(ask) > float(bid)
        }
        rows = [
            row for row in self.features.compute_event_rows(
                int(event_open_ms), computed_at_ms=int(now_ms), register_definition=False
            )
            if row["full_history_4h"] and str(row["symbol"]) in quote_map
        ]
        rows.sort(key=lambda r: (int(r["selection_rank"]), str(r["symbol"])))
        rows = rows[:UNIVERSE_SYMBOLS]
        histories = load_histories(self.database, [str(r["symbol"]) for r in rows], int(event_open_ms))

        out: list[V4Candidate] = []
        for feature in rows:
            symbol = str(feature["symbol"])
            bars = histories.get(symbol)
            if not bars:
                continue
            try:
                atr_frac = float(feature["atr14_frac"])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(atr_frac) or atr_frac <= 0:
                continue
            signals = self.signals._signals_for_feature_row(
                tuple(feature[k] for k in SIGNAL_INPUTS), computed_at_ms=int(now_ms)
            )
            signal_map = {row["signal_version"]: row for row in signals}
            bid, ask = quote_map[symbol]
            for side in ("LONG", "SHORT"):
                vector = _feature_vector(feature, signal_map, side)
                tags = tuple(matches(vector, side, bars))
                # Bootstrap priority is deliberately model-free:
                # recognized structures first, then more structure agreement,
                # then point-in-time universe rank.  Hash only breaks exact ties.
                tie = _digest([event_open_ms, symbol, side])
                priority = (0 if tags else 1, -len(tags), int(feature["selection_rank"]), tie)
                out.append(V4Candidate(
                    symbol, side, vector, tags, atr_frac,
                    int(feature["selection_rank"]), bid, ask, priority
                ))
        out.sort(key=lambda c: c.research_priority)
        return tuple(out)


class V4ResearchStore:
    """Small metadata companion to the immutable decision/outcome ledger."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS v4_meta(
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS v4_batches(
                batch_no INTEGER PRIMARY KEY,
                first_outcome_no INTEGER NOT NULL,
                last_outcome_no INTEGER NOT NULL,
                closed_at_ms INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'READY_FOR_TRAINING'
            );
            """)
            conn.execute(
                "INSERT OR IGNORE INTO v4_meta VALUES('contract',?)",
                (json.dumps({
                    "version": VERSION,
                    "capacity": CAPACITY,
                    "batch_size": BATCH_SIZE,
                    "interval_ms": INTERVAL_MS,
                    "order_authority": ORDER_AUTHORITY,
                }, sort_keys=True),),
            )

    def close_ready_batches(self, resolved_count: int, *, now_ms: int) -> list[int]:
        self.initialize()
        ready: list[int] = []
        complete_batches = int(resolved_count) // BATCH_SIZE
        with sqlite3.connect(self.path) as conn:
            existing = {int(r[0]) for r in conn.execute("SELECT batch_no FROM v4_batches")}
            for batch_no in range(1, complete_batches + 1):
                if batch_no in existing:
                    continue
                first_no = (batch_no - 1) * BATCH_SIZE + 1
                last_no = batch_no * BATCH_SIZE
                conn.execute(
                    "INSERT INTO v4_batches(batch_no,first_outcome_no,last_outcome_no,closed_at_ms) "
                    "VALUES(?,?,?,?)",
                    (batch_no, first_no, last_no, int(now_ms)),
                )
                ready.append(batch_no)
        return ready

    def record_cycle(self, cycle: dict[str, Any]) -> None:
        """Persist only the latest bounded cycle summary for operator visibility."""
        self.initialize()
        payload = {
            key: cycle.get(key)
            for key in (
                "event_open_ms", "matured_this_cycle", "opened_this_cycle",
                "active", "vacancies_after_refill", "resolved",
                "next_training_at", "new_training_batches",
            )
        }
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO v4_meta(key,value_json) VALUES('last_cycle',?)",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
            )

    def status(self) -> dict[str, Any]:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            batches = conn.execute(
                "SELECT batch_no,status,closed_at_ms FROM v4_batches ORDER BY batch_no"
            ).fetchall()
            row = conn.execute(
                "SELECT value_json FROM v4_meta WHERE key='last_cycle'"
            ).fetchone()
        last_cycle = None
        if row is not None:
            try:
                value = json.loads(row[0])
                last_cycle = value if isinstance(value, dict) else None
            except (TypeError, json.JSONDecodeError):
                last_cycle = None
        return {
            "version": VERSION,
            "capacity": CAPACITY,
            "batch_size": BATCH_SIZE,
            "batches": [
                {"batch_no": int(n), "status": str(s), "closed_at_ms": int(t)}
                for n, s, t in batches
            ],
            "last_cycle": last_cycle,
            "order_authority": ORDER_AUTHORITY,
        }


class V4ResearchFactory:
    def __init__(
        self,
        database,
        *,
        release_sha: str,
        ledger_path: str | Path = "data/observation/v4/research_ledger.db",
        meta_path: str | Path = "data/observation/v4/research_meta.db",
        capacity: int = CAPACITY,
    ) -> None:
        self.database = database
        self.release_sha = str(release_sha)
        self.capacity = int(capacity)
        if self.capacity != CAPACITY:
            raise ValueError("V4_CAPACITY_CONTRACT_MISMATCH")
        self.runtime = V3ResearchRuntime(ledger_path)
        self.meta = V4ResearchStore(meta_path)
        self.meta.initialize()
        self.scanner = V4CandidateScanner(database)
        self.feed = ResearchWssFeed(self.runtime)
        self._feed_universe: tuple[str, ...] = ()
        self.last_event_open_ms: int | None = None

        # A process restart cannot prove missing tick chronology. Fail closed.
        now_ms = int(time.time() * 1000)
        for pending in self.runtime.ledger.pending_decisions():
            self.runtime.ledger.record_unresolved(
                str(pending["decision_id"]),
                str(pending["policy_id"]),
                now_ms,
                "V4_PROCESS_RESTART_PATH_LOST",
                {"release_sha": self.release_sha},
            )

    def _active_pairs(self) -> set[tuple[str, str]]:
        pairs = set()
        active = set(self.runtime.replays.active_ids)
        if not active:
            return pairs
        for row in self.runtime.ledger.pending_decisions():
            if str(row["decision_id"]) in active:
                pairs.add((str(row["symbol"]), str(row["side"])))
        return pairs

    def _ensure_feed(self, candidates: tuple[V4Candidate, ...]) -> None:
        if self._feed_universe:
            return
        symbols = tuple(sorted({c.symbol for c in candidates}))
        if not symbols:
            return
        self._feed_universe = symbols
        self.feed.update(symbols, plan_combined_streams(symbols))

    def on_five_minute_event(self, *, event_open_ms: int, now_ms: int | None = None) -> dict[str, Any]:
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        if int(event_open_ms) % INTERVAL_MS:
            raise ValueError("V4_EVENT_NOT_5M_ALIGNED")
        if self.last_event_open_ms is not None and int(event_open_ms) <= self.last_event_open_ms:
            return self.status()

        matured = self.runtime.mature_due(now_ms=now_ms)
        candidates = self.scanner.scan(event_open_ms=int(event_open_ms), now_ms=now_ms)
        self._ensure_feed(candidates)

        # Keep one stable broad WSS universe for the process lifetime so adding
        # a new slot never tears down streams for still-open paths.
        if self._feed_universe:
            candidates = tuple(c for c in candidates if c.symbol in self._feed_universe)

        active_pairs = self._active_pairs()
        vacancies = max(0, self.capacity - self.runtime.replays.active_count)
        opened = 0
        for candidate in candidates:
            if opened >= vacancies:
                break
            pair = (candidate.symbol, candidate.side)
            if pair in active_pairs:
                continue

            quote = self.feed.wait_quotes((candidate.symbol,), timeout_seconds=2.0).get(candidate.symbol)
            bid = candidate.bid if quote is None else float(quote.bid)
            ask = candidate.ask if quote is None else float(quote.ask)
            entry = ask if candidate.side == "LONG" else bid
            one_r = entry * candidate.atr_frac
            if not (entry > 0 and one_r > 0 and math.isfinite(one_r)):
                continue

            decision_id = _digest({
                "v": VERSION,
                "release": self.release_sha,
                "event": int(event_open_ms),
                "symbol": candidate.symbol,
                "side": candidate.side,
            })[:32]
            feature_digest = _digest(candidate.vector)
            decision = FrozenDecision(
                decision_id=decision_id,
                event_id=f"V4LIVE5M:{int(event_open_ms)}",
                decision_time_ms=max(int(event_open_ms) + INTERVAL_MS, now_ms),
                symbol=candidate.symbol,
                side=candidate.side,
                setup_id=(candidate.setup_tags[0]["id"] if candidate.setup_tags else "MODEL_ONLY"),
                release_sha=self.release_sha,
                model_id="V4_BOOTSTRAP_NO_MODEL",
                feature_digest=feature_digest,
                ridge_score_r=0.0,
                ml_mean_r=None,
                ml_lower_r=None,
                conservative_score_r=0.0,
                rank=opened + 1,
                runner_up_score_r=None,
                edge_gap_r=None,
                approved=False,
                reason="V4_VIRTUAL_RESEARCH",
                bid=bid,
                ask=ask,
                quote_source=("WSS_BOOK" if quote is not None else "LIVE_POINT_IN_TIME_SNAPSHOT"),
                policy_id=TrailPolicy.TICK_INTEGER_R.value,
                sampling_probability=1.0,
                capacity_available=True,
            )
            extras = {
                "v4_contract": VERSION,
                "feature_vector": candidate.vector,
                "feature_digest": feature_digest,
                "setup_tags": list(candidate.setup_tags),
                "selection_rank": candidate.selection_rank,
                "entry_time_ms": decision.decision_time_ms,
                "entry_price": entry,
                "one_r_price": one_r,
                "horizon_ms": HORIZON_MS,
                "research_priority": list(candidate.research_priority[:-1]),
                "authority": AUTHORITY,
            }
            self.runtime.submit(
                decision,
                ReplayHypothesis(
                    decision_id, candidate.symbol, candidate.side, entry, one_r,
                    decision.decision_time_ms, TrailPolicy.TICK_INTEGER_R,
                    horizon_ms=HORIZON_MS,
                    costs=ReplayCosts(entry_slippage_bps=1.0, exit_slippage_bps=1.0),
                ),
                extras=extras,
            )
            active_pairs.add(pair)
            opened += 1

        counts = self.runtime.ledger.counts()
        resolved = counts["matured_research"]
        batches = self.meta.close_ready_batches(resolved, now_ms=now_ms)
        self.last_event_open_ms = int(event_open_ms)
        result = {
            "version": VERSION,
            "event_open_ms": int(event_open_ms),
            "matured_this_cycle": len(matured),
            "opened_this_cycle": opened,
            "active": self.runtime.replays.active_count,
            "vacancies_after_refill": self.capacity - self.runtime.replays.active_count,
            "resolved": resolved,
            "new_training_batches": batches,
            "next_training_at": ((resolved // BATCH_SIZE) + 1) * BATCH_SIZE,
            "authority": AUTHORITY,
            "order_authority": ORDER_AUTHORITY,
        }
        self.meta.record_cycle(result)
        return result

    def status(self) -> dict[str, Any]:
        counts = self.runtime.ledger.counts()
        resolved = counts["matured_research"]
        return {
            "version": VERSION,
            "capacity": self.capacity,
            "active": self.runtime.replays.active_count,
            "resolved": resolved,
            "unresolved": counts["unresolved"],
            "next_training_at": ((resolved // BATCH_SIZE) + 1) * BATCH_SIZE,
            "feed_symbols": len(self._feed_universe),
            "last_event_open_ms": self.last_event_open_ms,
            "authority": AUTHORITY,
            "order_authority": ORDER_AUTHORITY,
        }

    def stop(self) -> None:
        self.feed.stop()

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("V4_RESEARCH_HAS_NO_ORDER_AUTHORITY")
