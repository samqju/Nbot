"""Forward-only V4 paper examination for frozen model generations.

Paper/research only.  This module cannot place exchange orders.

Contest semantics:
- Gen-1 first runs a BASELINE_EXAM by itself.
- After a Champion exists, each Challenger starts a fresh HEAD_TO_HEAD epoch.
- Champion and Challenger have separate one-position paper books.
- Both see the same completed five-minute candidate universe.
- Each contest/model needs 100 completed scored trades before review.
- Interrupted WSS/process paths are unscorable, never fabricated.
- Promotion is always an explicit review action; never automatic.
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

from .counterfactual import ReplayCosts, TrailPolicy
from .decision_ledger import FrozenDecision
from .live_two_tier import ResearchWssFeed
from .research_replay import ReplayHypothesis
from .redesign_runtime import V3ResearchRuntime
from .selective_ml import ML_FEATURE_NAMES, augment_vector, _ml_imports
from .v4_generation import V4GenerationStore
from .v4_research import (
    HORIZON_MS,
    INTERVAL_MS,
    V4Candidate,
    V4CandidateScanner,
    _digest as research_digest,
)
from .wss_market import plan_combined_streams

VERSION = "NBOT_V4_PAPER_CONTEST_V1"
AUTHORITY = "V4_PAPER_ONLY_NO_ORDER_AUTHORITY"
ORDER_AUTHORITY = "NONE"
CHECKPOINT_TRADES = 100
STARTING_BALANCE_USD = 10_000.0
RISK_USD = 10.0


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: V4Candidate
    score: float


class FrozenGenerationModel:
    def __init__(self, generation: int, record: dict[str, Any]) -> None:
        self.generation = int(generation)
        self.qualification = str(record["qualification_status"])
        self.artifact = dict(record["artifact"])
        if self.artifact.get("order_authority") != "NONE":
            raise ValueError("V4_PAPER_MODEL_AUTHORITY_INVALID")
        if tuple(self.artifact.get("feature_names") or ()) != tuple(ML_FEATURE_NAMES):
            raise ValueError("V4_PAPER_MODEL_FEATURE_CONTRACT_MISMATCH")
        lgb, _ = _ml_imports()
        self.model = lgb.Booster(model_str=str(self.artifact["ranking_model"]))
        self.model_digest = str(self.artifact["model_digest"])
        self.trained_at_ms = int(self.artifact["trained_at_ms"])

    def score(self, candidate: V4Candidate) -> float:
        _, np = _ml_imports()
        vector = augment_vector(candidate.vector)
        values = np.asarray(
            [[float(vector[name]) for name in ML_FEATURE_NAMES]], dtype="float32"
        )
        score = float(self.model.predict(values)[0])
        if not math.isfinite(score):
            raise ValueError("V4_PAPER_MODEL_SCORE_INVALID")
        return score


class V4PaperContestStore:
    def __init__(self, path: str | Path = "data/observation/v4/paper_contest.db") -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS paper_models(
                generation INTEGER PRIMARY KEY,
                qualification TEXT NOT NULL,
                model_digest TEXT NOT NULL,
                first_admitted_at_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contests(
                contest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at_ms INTEGER NOT NULL,
                champion_generation INTEGER,
                challenger_generation INTEGER NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                closed_at_ms INTEGER,
                review_decision TEXT
            );
            CREATE TABLE IF NOT EXISTS contest_models(
                contest_id INTEGER NOT NULL,
                generation INTEGER NOT NULL,
                role TEXT NOT NULL,
                starting_balance_usd REAL NOT NULL,
                realized_r REAL NOT NULL DEFAULT 0,
                peak_realized_r REAL NOT NULL DEFAULT 0,
                max_drawdown_r REAL NOT NULL DEFAULT 0,
                completed_trades INTEGER NOT NULL DEFAULT 0,
                positive_trades INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                PRIMARY KEY(contest_id,generation)
            );
            CREATE TABLE IF NOT EXISTS paper_decisions(
                contest_id INTEGER NOT NULL,
                generation INTEGER NOT NULL,
                event_open_ms INTEGER NOT NULL,
                decision_id TEXT,
                symbol TEXT,
                side TEXT,
                score REAL,
                rank INTEGER,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                PRIMARY KEY(contest_id,generation,event_open_ms)
            );
            CREATE TABLE IF NOT EXISTS paper_trades(
                decision_id TEXT PRIMARY KEY,
                contest_id INTEGER NOT NULL,
                generation INTEGER NOT NULL,
                event_open_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_time_ms INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                one_r_price REAL NOT NULL,
                status TEXT NOT NULL,
                exit_time_ms INTEGER,
                net_r REAL,
                mfe_r REAL,
                mae_r REAL,
                exit_reason TEXT,
                source_digest TEXT
            );
            CREATE INDEX IF NOT EXISTS paper_trades_contest_model
              ON paper_trades(contest_id,generation,status,event_open_ms);
            """)

    def admitted_generations(self) -> set[int]:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            return {int(r[0]) for r in conn.execute("SELECT generation FROM paper_models")}

    def _register_model(
        self, generation: int, *, qualification: str, model_digest: str, now_ms: int
    ) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO paper_models VALUES(?,?,?,?)",
                (int(generation), str(qualification), str(model_digest), int(now_ms)),
            )

    def ensure_contest(
        self, *, champion_generation: int | None, challenger_generation: int,
        models: dict[int, FrozenGenerationModel], now_ms: int
    ) -> int:
        self.initialize()
        champion = None if champion_generation is None else int(champion_generation)
        challenger = int(challenger_generation)
        if champion == challenger:
            raise ValueError("V4_PAPER_CONTEST_SAME_MODEL")
        mode = "BASELINE_EXAM" if champion is None else "HEAD_TO_HEAD"
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """SELECT contest_id,champion_generation,challenger_generation
                   FROM contests
                   WHERE status IN ('ACTIVE','REVIEW_REQUIRED')
                   ORDER BY contest_id DESC LIMIT 1"""
            ).fetchone()
            if row is not None:
                same = (
                    (None if row[1] is None else int(row[1])) == champion
                    and int(row[2]) == challenger
                )
                if not same:
                    raise RuntimeError("V4_PAPER_PRIOR_CONTEST_REVIEW_PENDING")
                return int(row[0])

            cur = conn.execute(
                """INSERT INTO contests(
                    started_at_ms,champion_generation,challenger_generation,mode,status
                ) VALUES(?,?,?,?, 'ACTIVE')""",
                (int(now_ms), champion, challenger, mode),
            )
            contest_id = int(cur.lastrowid)

        roles = {challenger: "CHALLENGER"}
        if champion is not None:
            roles[champion] = "CHAMPION"
        for generation, role in roles.items():
            model = models[generation]
            self._register_model(
                generation, qualification=model.qualification,
                model_digest=model.model_digest, now_ms=now_ms,
            )
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    """INSERT INTO contest_models(
                        contest_id,generation,role,starting_balance_usd,status
                    ) VALUES(?,?,?,?, 'EXAMINING')""",
                    (contest_id, generation, role, STARTING_BALANCE_USD),
                )
        return contest_id

    def active_contest(self) -> dict[str, Any] | None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT * FROM contests
                   WHERE status IN ('ACTIVE','REVIEW_REQUIRED')
                   ORDER BY contest_id DESC LIMIT 1"""
            ).fetchone()
        return None if row is None else dict(row)

    def contest_model_status(self, contest_id: int, generation: int) -> dict[str, Any] | None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM contest_models WHERE contest_id=? AND generation=?",
                (int(contest_id), int(generation)),
            ).fetchone()
        return None if row is None else dict(row)

    def record_decision(
        self, contest_id: int, generation: int, event_open_ms: int, *,
        decision_id: str | None, symbol: str | None, side: str | None,
        score: float | None, rank: int | None, action: str, reason: str, now_ms: int
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO paper_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    int(contest_id), int(generation), int(event_open_ms), decision_id,
                    symbol, side, score, rank, str(action), str(reason), int(now_ms),
                ),
            )

    def open_trade(
        self, *, decision_id: str, contest_id: int, generation: int,
        event_open_ms: int, symbol: str, side: str, entry_time_ms: int,
        entry_price: float, one_r_price: float
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO paper_trades(
                    decision_id,contest_id,generation,event_open_ms,symbol,side,
                    entry_time_ms,entry_price,one_r_price,status
                ) VALUES(?,?,?,?,?,?,?,?,?, 'OPEN')""",
                (
                    decision_id, int(contest_id), int(generation), int(event_open_ms),
                    symbol, side, int(entry_time_ms), float(entry_price), float(one_r_price),
                ),
            )

    def close_trade(
        self, decision_id: str, *, net_r: float, mfe_r: float, mae_r: float,
        exit_time_ms: int | None, exit_reason: str, source_digest: str
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT contest_id,generation,status FROM paper_trades WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
            if row is None or row[2] != "OPEN":
                return
            contest_id, generation = int(row[0]), int(row[1])
            conn.execute(
                """UPDATE paper_trades SET status='CLOSED',exit_time_ms=?,net_r=?,
                   mfe_r=?,mae_r=?,exit_reason=?,source_digest=?
                   WHERE decision_id=? AND status='OPEN'""",
                (
                    None if exit_time_ms is None else int(exit_time_ms),
                    float(net_r), float(mfe_r), float(mae_r), str(exit_reason),
                    str(source_digest), decision_id,
                ),
            )
            m = conn.execute(
                """SELECT realized_r,peak_realized_r,max_drawdown_r,
                          completed_trades,positive_trades
                   FROM contest_models WHERE contest_id=? AND generation=?""",
                (contest_id, generation),
            ).fetchone()
            if m is None:
                raise ValueError("V4_PAPER_CONTEST_MODEL_UNKNOWN")
            realized = float(m[0]) + float(net_r)
            peak = max(float(m[1]), realized)
            drawdown = max(float(m[2]), peak - realized)
            completed = int(m[3]) + 1
            positive = int(m[4]) + (1 if float(net_r) > 0 else 0)
            model_status = "REVIEW_REQUIRED" if completed >= CHECKPOINT_TRADES else "EXAMINING"
            conn.execute(
                """UPDATE contest_models SET realized_r=?,peak_realized_r=?,
                   max_drawdown_r=?,completed_trades=?,positive_trades=?,status=?
                   WHERE contest_id=? AND generation=?""",
                (
                    realized, peak, drawdown, completed, positive, model_status,
                    contest_id, generation,
                ),
            )
            pending = conn.execute(
                """SELECT COUNT(*) FROM contest_models
                   WHERE contest_id=? AND completed_trades<?""",
                (contest_id, CHECKPOINT_TRADES),
            ).fetchone()[0]
            if int(pending) == 0:
                conn.execute(
                    "UPDATE contests SET status='REVIEW_REQUIRED' WHERE contest_id=?",
                    (contest_id,),
                )

    def mark_unscorable(self, decision_id: str, *, reason: str) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """UPDATE paper_trades SET status='UNSCORABLE',exit_reason=?
                   WHERE decision_id=? AND status='OPEN'""",
                (str(reason), decision_id),
            )

    def finish_review(
        self, contest_id: int, *, decision: str, now_ms: int
    ) -> None:
        if decision not in {"PROMOTE", "REJECT"}:
            raise ValueError("V4_PAPER_REVIEW_DECISION_INVALID")
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT status FROM contests WHERE contest_id=?", (int(contest_id),)
            ).fetchone()
            if row is None or row[0] != "REVIEW_REQUIRED":
                raise ValueError("V4_PAPER_CONTEST_NOT_REVIEW_READY")
            conn.execute(
                """UPDATE contests SET status='CLOSED',closed_at_ms=?,review_decision=?
                   WHERE contest_id=?""",
                (int(now_ms), decision, int(contest_id)),
            )

    def open_trades(self) -> list[dict[str, Any]]:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM paper_trades WHERE status='OPEN' ORDER BY entry_time_ms"
            )]

    def status(self) -> dict[str, Any]:
        self.initialize()
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            contests = [dict(r) for r in conn.execute(
                "SELECT * FROM contests ORDER BY contest_id DESC LIMIT 10"
            )]
            model_rows = [dict(r) for r in conn.execute(
                """SELECT cm.* FROM contest_models cm
                   JOIN contests c USING(contest_id)
                   WHERE c.status IN ('ACTIVE','REVIEW_REQUIRED')
                   ORDER BY cm.role,cm.generation"""
            )]
            open_rows = [dict(r) for r in conn.execute(
                """SELECT contest_id,generation,decision_id,symbol,side,entry_time_ms
                   FROM paper_trades WHERE status='OPEN' ORDER BY generation"""
            )]
            excluded_rows = conn.execute(
                """SELECT contest_id,generation,COUNT(*) FROM paper_trades
                   WHERE status='UNSCORABLE' GROUP BY contest_id,generation"""
            ).fetchall()
            tail_rows = conn.execute(
                """SELECT contest_id,generation,MIN(net_r),AVG(net_r),
                          SUM(CASE WHEN side='LONG' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN side='SHORT' THEN 1 ELSE 0 END),
                          MIN(entry_time_ms),MAX(COALESCE(exit_time_ms,entry_time_ms))
                   FROM paper_trades WHERE status='CLOSED'
                   GROUP BY contest_id,generation"""
            ).fetchall()
        excluded = {(int(c), int(g)): int(n) for c, g, n in excluded_rows}
        tails = {
            (int(r[0]), int(r[1])): {
                "worst_net_r": r[2],
                "mean_net_r": r[3],
                "long_trades": int(r[4] or 0),
                "short_trades": int(r[5] or 0),
                "first_entry_ms": r[6],
                "last_exit_ms": r[7],
            }
            for r in tail_rows
        }
        for model in model_rows:
            key = (int(model["contest_id"]), int(model["generation"]))
            completed = int(model["completed_trades"])
            model["positive_rate"] = (
                0.0 if completed == 0 else int(model["positive_trades"]) / completed
            )
            model["balance_usd"] = (
                float(model["starting_balance_usd"]) + float(model["realized_r"]) * RISK_USD
            )
            model["checkpoint_trades"] = CHECKPOINT_TRADES
            model["remaining_to_checkpoint"] = max(0, CHECKPOINT_TRADES - completed)
            model["unscorable_trades"] = excluded.get(key, 0)
            model.update(tails.get(key, {
                "worst_net_r": None, "mean_net_r": None, "long_trades": 0,
                "short_trades": 0, "first_entry_ms": None, "last_exit_ms": None,
            }))
        return {
            "version": VERSION,
            "active_contest": contests[0] if contests and contests[0]["status"] in {
                "ACTIVE", "REVIEW_REQUIRED"
            } else None,
            "recent_contests": contests,
            "models": model_rows,
            "open_positions": open_rows,
            "checkpoint_trades": CHECKPOINT_TRADES,
            "order_authority": ORDER_AUTHORITY,
            "automatic_promotion": False,
        }


class V4PaperReviewAdmin:
    def __init__(
        self, *, generation_path: str | Path = "data/observation/v4/generations.db",
        contest_path: str | Path = "data/observation/v4/paper_contest.db"
    ) -> None:
        self.generations = V4GenerationStore(generation_path)
        self.generations.initialize()
        self.store = V4PaperContestStore(contest_path)
        self.store.initialize()

    def promote_challenger(self, *, now_ms: int | None = None) -> dict[str, Any]:
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        contest = self.store.active_contest()
        if contest is None or contest["status"] != "REVIEW_REQUIRED":
            raise ValueError("V4_PAPER_CONTEST_NOT_REVIEW_READY")
        challenger = int(contest["challenger_generation"])
        self.store.finish_review(int(contest["contest_id"]), decision="PROMOTE", now_ms=now_ms)
        self.generations.set_state("champion_generation", challenger)
        self.generations.set_state("challenger_generation", None)
        return {
            "contest_id": int(contest["contest_id"]),
            "decision": "PROMOTE",
            "champion_generation": challenger,
            "order_authority": ORDER_AUTHORITY,
        }

    def reject_challenger(self, *, now_ms: int | None = None) -> dict[str, Any]:
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        contest = self.store.active_contest()
        if contest is None or contest["status"] != "REVIEW_REQUIRED":
            raise ValueError("V4_PAPER_CONTEST_NOT_REVIEW_READY")
        self.store.finish_review(int(contest["contest_id"]), decision="REJECT", now_ms=now_ms)
        self.generations.set_state("challenger_generation", None)
        return {
            "contest_id": int(contest["contest_id"]),
            "decision": "REJECT",
            "champion_generation": self.generations.state()["champion_generation"],
            "order_authority": ORDER_AUTHORITY,
        }


class V4PaperContest:
    def __init__(
        self, database, *, release_sha: str,
        generation_path: str | Path = "data/observation/v4/generations.db",
        paper_ledger_path: str | Path = "data/observation/v4/paper_ledger.db",
        contest_path: str | Path = "data/observation/v4/paper_contest.db",
    ) -> None:
        self.database = database
        self.release_sha = str(release_sha)
        self.generations = V4GenerationStore(generation_path)
        self.generations.initialize()
        self.store = V4PaperContestStore(contest_path)
        self.store.initialize()
        self.runtime = V3ResearchRuntime(paper_ledger_path)
        self.feed = ResearchWssFeed(self.runtime)
        self.scanner = V4CandidateScanner(database)
        self._feed_universe: tuple[str, ...] = ()
        self._models: dict[int, FrozenGenerationModel] = {}
        self._active: dict[int, str] = {}
        self.last_event_open_ms: int | None = None

        now_ms = int(time.time() * 1000)
        for pending in self.runtime.ledger.pending_decisions():
            decision_id = str(pending["decision_id"])
            self.runtime.ledger.record_unresolved(
                decision_id, str(pending["policy_id"]), now_ms,
                "V4_PAPER_PROCESS_RESTART_PATH_LOST",
                {"release_sha": self.release_sha},
            )
            self.store.mark_unscorable(
                decision_id, reason="V4_PAPER_PROCESS_RESTART_PATH_LOST"
            )

    def _generation_record(self, generation: int) -> dict[str, Any]:
        record = self.generations.generation(generation)
        if record is None:
            raise ValueError("V4_PAPER_GENERATION_UNKNOWN")
        return record

    def _load_model(self, generation: int) -> FrozenGenerationModel:
        generation = int(generation)
        if generation not in self._models:
            self._models[generation] = FrozenGenerationModel(
                generation, self._generation_record(generation)
            )
        return self._models[generation]

    def _assign_waiting_challenger(self) -> None:
        state = self.generations.state()
        if state["challenger_generation"] is not None:
            return
        admitted = self.store.admitted_generations()
        champion = state["champion_generation"]
        with sqlite3.connect(self.generations.path) as conn:
            rows = conn.execute(
                """SELECT generation FROM generations
                   WHERE qualification_status IN ('BASELINE_READY','CHALLENGER_READY')
                   ORDER BY generation"""
            ).fetchall()
        queued = [
            int(r[0]) for r in rows
            if int(r[0]) not in admitted and int(r[0]) != champion
        ]
        if queued:
            self.generations.set_state("challenger_generation", queued[0])

    def _roles_and_contest(self, now_ms: int) -> tuple[int | None, dict[int, str]]:
        self._assign_waiting_challenger()
        state = self.generations.state()
        challenger = state["challenger_generation"]
        if challenger is None:
            return None, {}
        champion = state["champion_generation"]
        roles = {int(challenger): "CHALLENGER"}
        if champion is not None:
            roles[int(champion)] = "CHAMPION"
        models = {generation: self._load_model(generation) for generation in roles}
        contest_id = self.store.ensure_contest(
            champion_generation=champion,
            challenger_generation=int(challenger),
            models=models,
            now_ms=now_ms,
        )
        return contest_id, roles

    def _ensure_feed(self, candidates: tuple[V4Candidate, ...]) -> None:
        if self._feed_universe:
            return
        symbols = tuple(sorted({c.symbol for c in candidates}))
        if not symbols:
            return
        self._feed_universe = symbols
        self.feed.update(symbols, plan_combined_streams(symbols))

    def _sync_matured(self, now_ms: int) -> int:
        matured = self.runtime.mature_due(now_ms=now_ms)
        active_ids = set(self.runtime.replays.active_ids)
        closed = 0
        for generation, decision_id in tuple(self._active.items()):
            if decision_id in matured:
                outcome = matured[decision_id]
                evidence = dict(outcome.evidence or {})
                self.store.close_trade(
                    decision_id,
                    net_r=float(outcome.net_r),
                    mfe_r=float(outcome.mfe_r or 0.0),
                    mae_r=float(outcome.mae_r or 0.0),
                    exit_time_ms=evidence.get("exit_time_ms"),
                    exit_reason=outcome.exit_reason,
                    source_digest=outcome.source_digest,
                )
                del self._active[generation]
                closed += 1
            elif decision_id not in active_ids:
                self.store.mark_unscorable(decision_id, reason="GAP_UNRESOLVED")
                del self._active[generation]
        return closed

    def on_five_minute_event(
        self, *, event_open_ms: int, now_ms: int | None = None
    ) -> dict[str, Any]:
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        event_open_ms = int(event_open_ms)
        if event_open_ms % INTERVAL_MS:
            raise ValueError("V4_PAPER_EVENT_NOT_5M_ALIGNED")
        if self.last_event_open_ms is not None and event_open_ms <= self.last_event_open_ms:
            return self.status()

        closed = self._sync_matured(now_ms)
        contest_id, roles = self._roles_and_contest(now_ms)
        candidates = self.scanner.scan(event_open_ms=event_open_ms, now_ms=now_ms)
        self._ensure_feed(candidates)
        if self._feed_universe:
            candidates = tuple(c for c in candidates if c.symbol in self._feed_universe)

        opened = 0
        if contest_id is not None:
            for generation in sorted(roles):
                if generation in self._active:
                    self.store.record_decision(
                        contest_id, generation, event_open_ms, decision_id=None,
                        symbol=None, side=None, score=None, rank=None, action="HOLD",
                        reason="PAPER_BOOK_POSITION_OPEN", now_ms=now_ms,
                    )
                    continue

                contest_model = self.store.contest_model_status(contest_id, generation)
                if contest_model is not None and contest_model["status"] == "REVIEW_REQUIRED":
                    self.store.record_decision(
                        contest_id, generation, event_open_ms, decision_id=None,
                        symbol=None, side=None, score=None, rank=None, action="HOLD",
                        reason="PAPER_CHECKPOINT_REVIEW_REQUIRED", now_ms=now_ms,
                    )
                    continue

                model = self._load_model(generation)
                if event_open_ms + INTERVAL_MS <= model.trained_at_ms:
                    self.store.record_decision(
                        contest_id, generation, event_open_ms, decision_id=None,
                        symbol=None, side=None, score=None, rank=None, action="ABSTAIN",
                        reason="MODEL_NOT_AVAILABLE_AT_EVENT", now_ms=now_ms,
                    )
                    continue

                scored: list[ScoredCandidate] = []
                for candidate in candidates:
                    try:
                        scored.append(ScoredCandidate(candidate, model.score(candidate)))
                    except (KeyError, TypeError, ValueError):
                        continue
                scored.sort(
                    key=lambda item: (
                        -item.score, item.candidate.symbol, item.candidate.side
                    )
                )
                if not scored:
                    self.store.record_decision(
                        contest_id, generation, event_open_ms, decision_id=None,
                        symbol=None, side=None, score=None, rank=None, action="ABSTAIN",
                        reason="NO_SCORABLE_CANDIDATE", now_ms=now_ms,
                    )
                    continue

                winner = scored[0]
                candidate = winner.candidate
                quote = self.feed.wait_quotes(
                    (candidate.symbol,), timeout_seconds=2.0
                ).get(candidate.symbol)
                if quote is None:
                    self.store.record_decision(
                        contest_id, generation, event_open_ms, decision_id=None,
                        symbol=candidate.symbol, side=candidate.side, score=winner.score,
                        rank=1, action="ABSTAIN",
                        reason="FRESH_WSS_QUOTE_UNAVAILABLE", now_ms=now_ms,
                    )
                    continue

                entry = float(quote.ask if candidate.side == "LONG" else quote.bid)
                one_r = entry * float(candidate.atr_frac)
                if not (entry > 0 and one_r > 0 and math.isfinite(one_r)):
                    self.store.record_decision(
                        contest_id, generation, event_open_ms, decision_id=None,
                        symbol=candidate.symbol, side=candidate.side, score=winner.score,
                        rank=1, action="ABSTAIN",
                        reason="PAPER_RISK_GEOMETRY_INVALID", now_ms=now_ms,
                    )
                    continue

                decision_id = _digest({
                    "version": VERSION,
                    "contest_id": contest_id,
                    "generation": generation,
                    "model_digest": model.model_digest,
                    "event_open_ms": event_open_ms,
                    "symbol": candidate.symbol,
                    "side": candidate.side,
                })[:32]
                decision_time_ms = max(event_open_ms + INTERVAL_MS, now_ms)
                decision = FrozenDecision(
                    decision_id=decision_id,
                    event_id=f"V4PAPER5M:{event_open_ms}",
                    decision_time_ms=decision_time_ms,
                    symbol=candidate.symbol,
                    side=candidate.side,
                    setup_id=(
                        candidate.setup_tags[0]["id"]
                        if candidate.setup_tags else "MODEL_ONLY"
                    ),
                    release_sha=self.release_sha,
                    model_id=f"V4_MODEL_GEN_{generation:03d}",
                    feature_digest=research_digest(candidate.vector),
                    ridge_score_r=None,
                    ml_mean_r=winner.score,
                    ml_lower_r=None,
                    conservative_score_r=winner.score,
                    rank=1,
                    runner_up_score_r=(scored[1].score if len(scored) > 1 else None),
                    edge_gap_r=(
                        winner.score - scored[1].score if len(scored) > 1 else None
                    ),
                    approved=True,
                    reason="V4_PAPER_TOP1",
                    bid=float(quote.bid),
                    ask=float(quote.ask),
                    quote_source="WSS_BOOK",
                    policy_id=TrailPolicy.TICK_INTEGER_R.value,
                    sampling_probability=1.0,
                    capacity_available=True,
                )
                self.runtime.submit(
                    decision,
                    ReplayHypothesis(
                        decision_id, candidate.symbol, candidate.side, entry, one_r,
                        decision_time_ms, TrailPolicy.TICK_INTEGER_R,
                        horizon_ms=HORIZON_MS,
                        costs=ReplayCosts(
                            taker_fee_rate=.0005,
                            entry_slippage_bps=1.0,
                            exit_slippage_bps=1.0,
                        ),
                    ),
                    extras={
                        "v4_paper_contract": VERSION,
                        "contest_id": contest_id,
                        "generation": generation,
                        "model_digest": model.model_digest,
                        "feature_vector": candidate.vector,
                        "selection_rank": candidate.selection_rank,
                        "entry_price": entry,
                        "one_r_price": one_r,
                        "paper_starting_balance_usd": STARTING_BALANCE_USD,
                        "paper_risk_usd": RISK_USD,
                        "order_authority": ORDER_AUTHORITY,
                    },
                )
                self.store.record_decision(
                    contest_id, generation, event_open_ms, decision_id=decision_id,
                    symbol=candidate.symbol, side=candidate.side, score=winner.score,
                    rank=1, action="OPEN", reason="V4_PAPER_TOP1", now_ms=now_ms,
                )
                self.store.open_trade(
                    decision_id=decision_id, contest_id=contest_id,
                    generation=generation, event_open_ms=event_open_ms,
                    symbol=candidate.symbol, side=candidate.side,
                    entry_time_ms=decision_time_ms, entry_price=entry,
                    one_r_price=one_r,
                )
                self._active[generation] = decision_id
                opened += 1

        self.last_event_open_ms = event_open_ms
        return {
            "version": VERSION,
            "event_open_ms": event_open_ms,
            "contest_id": contest_id,
            "models_examining": len(roles),
            "closed_this_cycle": closed,
            "opened_this_cycle": opened,
            "active_positions": len(self._active),
            "checkpoint_trades": CHECKPOINT_TRADES,
            "order_authority": ORDER_AUTHORITY,
        }

    def status(self) -> dict[str, Any]:
        return {
            **self.store.status(),
            "generation_state": self.generations.state(),
            "feed_symbols": len(self._feed_universe),
            "last_event_open_ms": self.last_event_open_ms,
            "active_positions": len(self._active),
            "order_authority": ORDER_AUTHORITY,
        }

    def stop(self) -> None:
        self.feed.stop()

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("V4_PAPER_HAS_NO_ORDER_AUTHORITY")
