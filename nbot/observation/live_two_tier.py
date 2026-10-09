"""Live Observation integration for resource-bounded V3 two-tier research.

This module is deliberately research-only. It consumes completed causal 5-minute
Observation evidence, selects up to 100 broad symbols, admits at most 20 symbols
to high-resolution Binance public WebSocket monitoring, and writes immutable
counterfactual decision/outcome evidence. It has no account credentials and no
order submission path.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping

from .chronological_replay import TradeEvent
from .challengers import ContinuousChallengerCycle
from .research_memory import ResearchMemoryStore
from .counterfactual import ReplayCosts, TrailPolicy
from .decision_ledger import FrozenDecision
from .context_learning import describe
from .learned_recommendation import LearnedTestnetSource, SIGNAL_INPUTS, _execution_compatible_quotes
from .selection import _feature_vector, _ridge_score
from .selective_ml import LOWER_SCORE_WEIGHT, MEAN_SCORE_WEIGHT, SelectiveMLRuntime
from .two_tier_runtime import TwoTierV3ResearchRuntime
from .research_replay import ReplayHypothesis
from .watch_planner import WatchCandidate
from .wss_market import AggTrade, MarketDataUnavailable, WssMarketState
from .wss_transport import CombinedStreamRunner


AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"
DEFAULT_BROAD_TARGET = 100
DEFAULT_HIGH_RES_CAP = 20
DEFAULT_HORIZON_MS = 4 * 60 * 60 * 1000
DEFAULT_QUOTE_TTL_MS = 120_000
STATUS_VERSION = "NBOT_V3_TWO_TIER_LIVE_STATUS_V1"
TWO_TIER_MODEL_PREFIX = "two_tier:ridge_snapshot:"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _volatility_bucket(percentile: Any) -> str:
    try:
        value = float(percentile)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if not math.isfinite(value):
        return "UNKNOWN"
    if value < 1 / 3:
        return "LOW"
    if value < 2 / 3:
        return "MID"
    return "HIGH"


@dataclass(frozen=True)
class ResearchCandidate:
    decision: FrozenDecision
    hypothesis_entry_price: float
    one_r_price: float
    watch: WatchCandidate
    score: float


class BroadResearchScanner:
    """Reuse the live-paper Ridge/Selective-ML scoring stack for all broad candidates."""

    def __init__(self, database, *, release_sha: str, broad_target: int = DEFAULT_BROAD_TARGET) -> None:
        self.database = database
        self.release_sha = str(release_sha)
        self.broad_target = int(broad_target)
        self.source = LearnedTestnetSource(
            database,
            live=database,
            release_sha=self.release_sha,
            profile_name="live-paper",
        )
        self.memory = ResearchMemoryStore(self.source.memory_path)
        self.last_reason: str | None = None
        self.last_model_source: str | None = None

    def _two_tier_ridge_snapshot(self, *, event_open_ms: int) -> dict[str, Any] | None:
        history = self.memory.history_base()
        cutoff = history.get("through_event_ms")
        if cutoff is None:
            self.last_reason = "WAIT_FOR_RESEARCH_MEMORY"
            return None
        key = f"{TWO_TIER_MODEL_PREFIX}{self.release_sha}:{int(cutoff)}"
        record = self.memory.artifact(key)
        if record is None:
            artifact = ContinuousChallengerCycle(
                self.memory, release_sha=self.release_sha
            ).ridge_model_artifact()
            artifact = {
                **artifact,
                "artifact_type": "TWO_TIER_RIDGE_SNAPSHOT",
                "purpose": "BROAD_COUNTERFACTUAL_RESEARCH_ONLY",
                "automatic_promotion": False,
                "execution_authority": "NONE",
            }
            record = self.memory.persist_artifact(key, artifact)
        artifact = record["payload"]
        if artifact.get("release_sha") != self.release_sha:
            raise RuntimeError("TWO_TIER_MODEL_RELEASE_MISMATCH")
        if int(artifact["training_cutoff_event_ms"]) != int(cutoff):
            raise RuntimeError("TWO_TIER_MODEL_CUTOFF_MISMATCH")
        if int(artifact["model_available_at_ms"]) >= int(event_open_ms):
            self.last_reason = "MODEL_FROZEN_WAIT_NEXT_EVENT"
            return None
        return artifact

    def scan(self, *, event_open_ms: int, now_ms: int) -> tuple[ResearchCandidate, ...]:
        event_open_ms = int(event_open_ms)
        now_ms = int(now_ms)
        self.last_reason = None
        self.last_model_source = None
        artifact = self.source._model(event_open_ms)
        if artifact is not None:
            self.last_model_source = "COMPATIBLE_CHALLENGER"
        else:
            artifact = self._two_tier_ridge_snapshot(event_open_ms=event_open_ms)
            if artifact is None:
                return ()
            self.last_model_source = "CURRENT_RELEASE_RIDGE_SNAPSHOT"

        with self.database.connection() as conn:
            event = conn.execute(
                """SELECT event_close_ms,captured_at_ms FROM market_events
                   WHERE event_open_ms=? AND status='COMPLETE'""",
                (event_open_ms,),
            ).fetchone()
            quote_rows = conn.execute(
                """SELECT s.symbol,s.bid_price,s.ask_price,s.captured_at_ms
                   FROM market_snapshots s
                   JOIN event_provenance p USING(event_open_ms)
                   WHERE s.event_open_ms=? AND p.evidence_mode='LIVE_POINT_IN_TIME'
                     AND p.context_complete=1 AND p.membership_quality='POINT_IN_TIME'
                   ORDER BY s.symbol""",
                (event_open_ms,),
            ).fetchall()
        if event is None:
            self.last_reason = "EVENT_NOT_COMPLETE"
            return ()
        close_ms, captured_at_ms = map(int, event)
        if not close_ms <= captured_at_ms <= now_ms:
            self.last_reason = "EVENT_CAPTURE_TIME_INVALID"
            return ()
        quotes = _execution_compatible_quotes(
            quote_rows, close_ms=close_ms, now_ms=now_ms, ttl_ms=DEFAULT_QUOTE_TTL_MS
        )
        if not quotes:
            self.last_reason = "NO_USABLE_POINT_IN_TIME_QUOTES"
            return ()

        ml_record = self.source.selective_ml.latest_for_event(event_open_ms) if self.source.selective_ml else None
        ml_runtime = None
        threshold_r = 0.0
        if ml_record is not None:
            ml_runtime = SelectiveMLRuntime(ml_record["payload"])
            threshold_r = float(self.source.selective_ml.config.min_lower_r)

        feature_rows = [
            feature
            for feature in self.source.features.compute_event_rows(
                event_open_ms, computed_at_ms=now_ms, register_definition=False
            )
            if feature["full_history_4h"] and feature["symbol"] in quotes
        ]
        feature_rows.sort(key=lambda row: (int(row["selection_rank"]), str(row["symbol"])))
        allowed_symbols = {
            str(row["symbol"]) for row in feature_rows[: self.broad_target]
        }

        raw: list[dict[str, Any]] = []
        for feature in feature_rows:
            symbol = str(feature["symbol"])
            if symbol not in allowed_symbols:
                continue
            atr_frac = feature.get("atr14_frac")
            try:
                atr_frac = float(atr_frac)
            except (TypeError, ValueError):
                atr_frac = 0.0
            if not math.isfinite(atr_frac) or atr_frac <= 0:
                continue

            signals = self.source.signals._signals_for_feature_row(
                tuple(feature[key] for key in SIGNAL_INPUTS), computed_at_ms=now_ms
            )
            signals = {row["signal_version"]: row for row in signals}
            bid = float(quotes[symbol][1])
            ask = float(quotes[symbol][2])

            for side in ("LONG", "SHORT"):
                vector = _feature_vector(feature, signals, side)
                ridge = float(_ridge_score(artifact["model"], json.dumps(vector, allow_nan=False)))
                if not math.isfinite(ridge):
                    continue
                ml_mean = ml_lower = None
                conservative = ridge
                if ml_runtime is not None:
                    ml_mean, ml_lower = ml_runtime.score(vector)
                    ensemble_mean = 0.25 * ridge + 0.75 * ml_mean
                    conservative = MEAN_SCORE_WEIGHT * ensemble_mean + LOWER_SCORE_WEIGHT * ml_lower
                if not math.isfinite(conservative):
                    continue
                setup_id = str(describe(vector).get("setup") or "MODEL_ONLY")
                raw.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "vector": vector,
                        "feature": feature,
                        "ridge": ridge,
                        "ml_mean": None if ml_mean is None else float(ml_mean),
                        "ml_lower": None if ml_lower is None else float(ml_lower),
                        "score": float(conservative),
                        "threshold": threshold_r,
                        "setup_id": setup_id,
                        "bid": bid,
                        "ask": ask,
                        "atr_frac": atr_frac,
                    }
                )

        raw.sort(key=lambda row: (-row["score"], row["symbol"], row["side"]))
        result: list[ResearchCandidate] = []
        for index, row in enumerate(raw):
            runner_up = raw[index + 1]["score"] if index + 1 < len(raw) else None
            edge_gap = None if runner_up is None else row["score"] - runner_up
            approved = row["score"] >= row["threshold"]
            decision_id = _digest(
                {
                    "release": self.release_sha,
                    "event": event_open_ms,
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "setup": row["setup_id"],
                }
            )[:32]
            feature_digest = _digest(row["vector"])
            entry = row["ask"] if row["side"] == "LONG" else row["bid"]
            one_r = entry * row["atr_frac"]
            decision = FrozenDecision(
                decision_id=decision_id,
                event_id=f"LIVE5M:{event_open_ms}",
                decision_time_ms=close_ms,
                symbol=row["symbol"],
                side=row["side"],
                setup_id=row["setup_id"],
                release_sha=self.release_sha,
                model_id=str(artifact.get("model_digest") or artifact.get("model_version") or "UNKNOWN"),
                feature_digest=feature_digest,
                ridge_score_r=row["ridge"],
                ml_mean_r=row["ml_mean"],
                ml_lower_r=row["ml_lower"],
                conservative_score_r=row["score"],
                rank=index + 1,
                runner_up_score_r=runner_up,
                edge_gap_r=edge_gap,
                approved=approved,
                reason="ABOVE_RESEARCH_THRESHOLD" if approved else "BELOW_RESEARCH_THRESHOLD",
                bid=row["bid"],
                ask=row["ask"],
                quote_source="LIVE_POINT_IN_TIME_SNAPSHOT",
                policy_id=TrailPolicy.TICK_INTEGER_R.value,
                sampling_probability=1.0,
                capacity_available=True,
            )
            watch = WatchCandidate(
                symbol=row["symbol"],
                conservative_score_r=row["score"],
                threshold_r=row["threshold"],
                setup_id=row["setup_id"],
                volatility_bucket=_volatility_bucket(row["feature"].get("volatility_percentile")),
                ridge_score_r=row["ridge"],
                ml_score_r=row["ml_mean"],
                approved=approved,
            )
            result.append(ResearchCandidate(decision, entry, one_r, watch, row["score"]))
        if not result:
            self.last_reason = "NO_FULL_HISTORY_SCORABLE_ROWS"
        return tuple(result)


class ResearchWssFeed:
    """One background public WSS feed shared by all admitted hypotheses."""

    def __init__(self, runtime: TwoTierV3ResearchRuntime, *, event_sink=None) -> None:
        self.runtime = runtime
        self.event_sink = event_sink
        self.symbols: tuple[str, ...] = ()
        self.state: WssMarketState | None = None
        self.runners: list[CombinedStreamRunner] = []
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.last_error: str | None = None
        self.started_at_ms: int | None = None

    def _on_market_event(self, kind: str, value: Any) -> None:
        if kind != "aggTrade" or not isinstance(value, AggTrade):
            return
        try:
            self.runtime.ingest_trade(
                TradeEvent(value.symbol, value.aggregate_id, value.trade_time_ms, value.price)
            )
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}:{exc}"

    async def _run(self, shards) -> None:
        self.loop = asyncio.get_running_loop()
        self.runners = [
            CombinedStreamRunner(
                url=shard.combined_url,
                state=self.state,
                symbols=shard.symbols,
                event_sink=self._on_market_event,
            )
            for shard in shards
        ]
        try:
            await asyncio.gather(*(runner.run() for runner in self.runners))
        finally:
            self.loop = None
            self.runners = []

    def _thread_main(self, shards) -> None:
        try:
            asyncio.run(self._run(shards))
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}:{exc}"

    def update(self, symbols: tuple[str, ...], shards) -> None:
        normalized = tuple(sorted(set(symbols)))
        if normalized == self.symbols and self.thread is not None and self.thread.is_alive():
            return
        self.stop()
        self.symbols = normalized
        if not normalized:
            return
        self.state = WssMarketState(normalized)
        self.last_error = None
        self.started_at_ms = int(time.time() * 1000)
        self.thread = threading.Thread(
            target=self._thread_main,
            args=(shards,),
            name="nbot-two-tier-wss",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        loop = self.loop
        runners = tuple(self.runners)
        if loop is not None and runners:
            for runner in runners:
                try:
                    asyncio.run_coroutine_threadsafe(runner.stop(), loop)
                except Exception:
                    pass
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=8)
        self.thread = None
        self.loop = None
        self.runners = []
        self.state = None
        self.symbols = ()

    def wait_quotes(
        self, symbols: tuple[str, ...], *, timeout_seconds: float = 5.0, max_age_ms: int = 2_000
    ) -> dict[str, Any]:
        """Wait briefly for fresh WSS executable quotes for newly admitted symbols."""
        wanted = tuple(sorted(set(symbols)))
        if not wanted:
            return {}
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while time.monotonic() <= deadline:
            state = self.state
            if state is None:
                return {}
            now_ms = int(time.time() * 1000)
            found = {}
            for symbol in wanted:
                try:
                    found[symbol] = state.executable_quote(
                        symbol, now_ms=now_ms, max_age_ms=max_age_ms
                    )
                except MarketDataUnavailable:
                    pass
            if len(found) == len(wanted):
                return found
            time.sleep(0.05)
        return found if "found" in locals() else {}

    def snapshot(self) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        health = {}
        if self.state is not None:
            for symbol in self.symbols:
                item = self.state.health(symbol, now_ms=now_ms)
                health[symbol] = {
                    "connected": item.connected,
                    "quote_age_ms": item.quote_age_ms,
                    "trade_age_ms": item.trade_age_ms,
                    "gap_unresolved": item.gap_unresolved,
                    "duplicate_events": item.duplicate_events,
                    "out_of_order_events": item.out_of_order_events,
                    "missing_aggregate_ids": item.missing_aggregate_ids,
                }
        return {
            "symbols": list(self.symbols),
            "thread_alive": bool(self.thread and self.thread.is_alive()),
            "started_at_ms": self.started_at_ms,
            "last_error": self.last_error,
            "health": health,
            "dropped_messages": sum(runner.dropped for runner in self.runners),
        }


class LiveTwoTierResearchSupervisor:
    """Bridge completed Observation cycles to broad scoring and high-res replay."""

    def __init__(
        self,
        database,
        *,
        release_sha: str,
        ledger_path: str | Path = "data/observation/live/decision_outcomes.db",
        broad_target: int = DEFAULT_BROAD_TARGET,
        high_res_cap: int = DEFAULT_HIGH_RES_CAP,
        event_sink: Callable[[Mapping[str, object]], None] | None = None,
        enabled: bool = True,
    ) -> None:
        self.database = database
        self.release_sha = str(release_sha)
        self.enabled = bool(enabled)
        self.event_sink = event_sink
        self.runtime = TwoTierV3ResearchRuntime(
            ledger_path, broad_target=broad_target, high_res_cap=high_res_cap
        )
        self.scanner = BroadResearchScanner(
            database, release_sha=self.release_sha, broad_target=broad_target
        )
        self.feed = ResearchWssFeed(self.runtime, event_sink=event_sink)
        self.status_path = Path("runtime/observation/live/two_tier_research_status.json")
        self.last_event_open_ms: int | None = None
        if self.status_path.is_file():
            try:
                previous = json.loads(self.status_path.read_text(encoding="utf-8"))
                if previous.get("release_sha") == self.release_sha:
                    value = previous.get("last_event_open_ms")
                    self.last_event_open_ms = None if value is None else int(value)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        self.last_error: str | None = None
        self.last_scan_candidates = 0
        self.last_matured = 0

        # Precise WSS chronology is intentionally not reconstructed after a
        # process restart. Any previously pending path therefore becomes
        # explicitly unresolved instead of being resumed with missing ticks.
        restarted_pending = 0
        now_ms = int(time.time() * 1000)
        for pending in self.runtime.ledger.pending_decisions():
            decision_id = str(pending.get("decision_id") or "")
            policy_id = str(pending.get("policy_id") or "")
            if not decision_id or not policy_id:
                continue
            self.runtime.ledger.record_unresolved(
                decision_id,
                policy_id,
                now_ms,
                "PROCESS_RESTART_PATH_LOST",
                {"release_sha": self.release_sha},
            )
            restarted_pending += 1
        if restarted_pending:
            self._emit("TWO_TIER_RESTART_UNRESOLVED", decisions=restarted_pending)
        self._write_status("INITIALIZED")

    def _emit(self, event: str, **fields: object) -> None:
        if self.event_sink is None:
            return
        payload = {"event": event, "authority": AUTHORITY, **fields}
        try:
            self.event_sink(payload)
        except Exception:
            pass

    def _write_status(self, state: str) -> None:
        plan = self.runtime.watch_plan
        payload = {
            "version": STATUS_VERSION,
            "authority": AUTHORITY,
            "state": state,
            "enabled": self.enabled,
            "release_sha": self.release_sha,
            "broad_target": self.runtime.broad_target,
            "high_res_cap": self.runtime.high_res_cap,
            "last_event_open_ms": self.last_event_open_ms,
            "last_scan_candidates": self.last_scan_candidates,
            "scanner_reason": self.scanner.last_reason,
            "model_source": self.scanner.last_model_source,
            "last_matured": self.last_matured,
            "active_hypotheses": self.runtime.replays.active_count,
            "active_symbols": list(self.runtime.replays.active_symbols),
            "buffered_trade_events": self.runtime.replays.buffered_event_count(),
            "ledger_counts": self.runtime.ledger.counts(),
            "watch_plan": None if plan is None else {
                "broad_symbols": list(plan.broad_symbols),
                "high_res_symbols": list(plan.high_res_symbols),
                "retained_active_symbols": list(plan.retained_active_symbols),
                "newly_admitted_symbols": list(plan.newly_admitted_symbols),
                "rejected_for_capacity": list(plan.rejected_for_capacity),
                "reasons": dict(plan.reasons),
            },
            "wss": self.feed.snapshot(),
            "last_error": self.last_error,
            "updated_at_ms": int(time.time() * 1000),
        }
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.status_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
        temp.replace(self.status_path)

    def on_completed_cycle(self, *, event_open_ms: int, now_ms: int | None = None) -> None:
        if not self.enabled:
            return
        event_open_ms = int(event_open_ms)
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        if self.last_event_open_ms == event_open_ms:
            return
        self.last_event_open_ms = event_open_ms
        try:
            matured = self.runtime.mature_due(now_ms=now_ms)
            self.last_matured = len(matured)
            candidates = self.scanner.scan(event_open_ms=event_open_ms, now_ms=now_ms)
            self.last_scan_candidates = len(candidates)
            if not candidates:
                self._emit(
                    "TWO_TIER_RESEARCH_WAIT",
                    event_open_ms=event_open_ms,
                    reason=self.scanner.last_reason or "NO_COMPATIBLE_CANDIDATES",
                    model_source=self.scanner.last_model_source,
                )
                self._write_status("WAITING")
                return

            broad_symbols = []
            seen = set()
            for candidate in candidates:
                symbol = candidate.decision.symbol
                if symbol not in seen:
                    seen.add(symbol)
                    broad_symbols.append(symbol)

            plan = self.runtime.refresh_watch_plan(
                broad_symbols=broad_symbols,
                candidates=[candidate.watch for candidate in candidates],
            )
            self.feed.update(plan.high_res_symbols, self.runtime.high_res_stream_shards())

            newly = set(plan.newly_admitted_symbols)
            fresh_quotes = self.feed.wait_quotes(tuple(newly))
            chosen: dict[str, ResearchCandidate] = {}
            for candidate in candidates:
                symbol = candidate.decision.symbol
                if symbol in newly and symbol not in chosen:
                    chosen[symbol] = candidate

            retained = set(plan.retained_active_symbols)
            admitted = set(plan.high_res_symbols)
            for candidate in candidates:
                decision = candidate.decision
                if self.runtime.ledger.has_terminal_research_outcome(
                    decision.decision_id, decision.policy_id
                ):
                    continue
                if chosen.get(decision.symbol) is candidate and decision.symbol in fresh_quotes:
                    quote = fresh_quotes[decision.symbol]
                    entry = quote.ask if decision.side == "LONG" else quote.bid
                    risk_frac = candidate.one_r_price / candidate.hypothesis_entry_price
                    entry_time_ms = int(time.time() * 1000)
                    decision = replace(decision, capacity_available=True)
                    hypothesis = ReplayHypothesis(
                        decision.decision_id,
                        decision.symbol,
                        decision.side,
                        entry,
                        entry * risk_frac,
                        entry_time_ms,
                        TrailPolicy.TICK_INTEGER_R,
                        horizon_ms=DEFAULT_HORIZON_MS,
                        costs=ReplayCosts(),
                    )
                    self.runtime.activate(
                        decision,
                        hypothesis,
                        extras={
                            "broad_target": self.runtime.broad_target,
                            "high_res_cap": self.runtime.high_res_cap,
                            "entry_source": "WSS_BOOK",
                            "entry_time_ms": entry_time_ms,
                            "entry_bid": quote.bid,
                            "entry_ask": quote.ask,
                            "quote_receipt_time_ms": quote.receipt_time_ms,
                        },
                    )
                else:
                    if chosen.get(decision.symbol) is candidate and decision.symbol not in fresh_quotes:
                        reason = "HIGH_RES_WSS_NOT_READY"
                    elif decision.symbol in retained:
                        reason = "HIGH_RES_ACTIVE_SLOT_BUSY"
                    else:
                        reason = "HIGH_RES_NOT_ADMITTED"
                    decision = replace(
                        decision,
                        capacity_available=decision.symbol in admitted and reason != "HIGH_RES_WSS_NOT_READY",
                    )
                    self.runtime.record_without_replay(
                        decision,
                        reason=reason,
                        extras={
                            "broad_target": self.runtime.broad_target,
                            "high_res_cap": self.runtime.high_res_cap,
                        },
                    )

            self.last_error = None
            self._emit(
                "TWO_TIER_RESEARCH_CYCLE",
                event_open_ms=event_open_ms,
                broad_symbols=len(plan.broad_symbols),
                high_res_symbols=len(plan.high_res_symbols),
                newly_admitted=len(plan.newly_admitted_symbols),
                active_hypotheses=self.runtime.replays.active_count,
                matured=len(matured),
                candidate_decisions=len(candidates),
            )
            self._write_status("RUNNING")
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}:{exc}"
            self._emit(
                "TWO_TIER_RESEARCH_ERROR",
                event_open_ms=event_open_ms,
                error_type=type(exc).__name__,
                detail=str(exc)[:500],
            )
            self._write_status("ERROR")

    def stop(self) -> None:
        self.feed.stop()
        self._write_status("STOPPED")
