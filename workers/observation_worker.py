"""Observation-only runtime extracted from the legacy TradingEngine."""

from __future__ import annotations

import threading
import time

from communication.trade_request import TradeRequest
from config import (
    CANDIDATE_OUTCOMES_PATH,
    EXECUTION_MODE,
    OBSERVATION_UNIVERSE_REFRESH_SECONDS,
    OBSERVATION_UNIVERSE_SIZE,
    STRATEGY_MODE,
    TRADING_ENV,
)
from engine.universe import UniverseManager
from execution.binance_market_client import BinanceMarketClient
from observation.execution_outcome_receiver import LocalExecutionOutcomeReceiver
from observation.market_context import ObservationMarketContextProvider
from observation.virtual_cost_evidence import (
    ObservationVirtualCostEvidenceProvider,
)
from observation.recommendation import LatestRecommendationStore
from observation.trade_service import ObservationTradeService
from strategy.strategy_factory import build_strategy
from utils.observation_health import ObservationHealthMonitor


class ObservationWorker:
    """Continuously observe/learn and maintain one fresh recommendation.

    This worker owns no EntryLifecycle, PositionLifecycle, RiskManager,
    StateManager, private exchange adapter, or Binance order authority.
    """

    def __init__(
        self,
        *,
        system_log,
        market_client=None,
        strategy=None,
        universe=None,
        recommendation_store=None,
        outcome_receiver=None,
        health_monitor=None,
        market_context_provider=None,
        virtual_cost_evidence_provider=None,
    ):
        self.system_log = system_log
        if strategy is None:
            if STRATEGY_MODE != "STRUCTURE":
                raise RuntimeError(
                    "OBSERVATION_WORKER_REQUIRES_STRUCTURE_STRATEGY"
                )
            strategy = build_strategy(system_log=system_log)
        self.strategy = strategy
        self.market_client = market_client or BinanceMarketClient(
            system_log=system_log
        )
        self.universe = universe or UniverseManager(
            strategy=self.strategy,
            system_log=system_log,
        )
        self.market_context_provider = (
            market_context_provider
            or ObservationMarketContextProvider(
                market_client=self.market_client,
                system_log=system_log,
            )
        )
        self.virtual_cost_evidence_provider = (
            virtual_cost_evidence_provider
            or ObservationVirtualCostEvidenceProvider(
                market_client=self.market_client,
                system_log=system_log,
            )
        )
        self.recommendation_store = recommendation_store or LatestRecommendationStore(
            environment=TRADING_ENV,
            system_log=system_log,
        )
        self.trade_service = ObservationTradeService(
            recommendation_store=self.recommendation_store,
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
            system_log=system_log,
        )
        self.outcome_receiver = outcome_receiver or LocalExecutionOutcomeReceiver(
            candidate_outcomes_path=CANDIDATE_OUTCOMES_PATH,
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
            system_log=system_log,
        )
        self.health_monitor = health_monitor or ObservationHealthMonitor()
        self._prepared = False
        self._last_universe_refresh_monotonic = 0.0
        self._last_virtual_cost_bucket = None
        self._scale_lock = threading.Lock()
        self._scale_metrics = {
            "refresh_attempts": 0,
            "refresh_successes": 0,
            "refresh_failures": 0,
            "refresh_no_change": 0,
            "last_refresh_status": "NOT_RUN",
            "last_refresh_duration_ms": None,
            "max_refresh_duration_ms": 0.0,
            "last_refresh_monotonic": None,
            "last_warmup_symbols_count": 0,
            "last_execution_added": 0,
            "last_execution_removed": 0,
            "last_observation_added": 0,
            "last_observation_removed": 0,
            "peak_effective_universe_count": 0,
        }

    def prepare(self) -> None:
        """Connect public market data, restore universes, and warm Strategy."""
        self.recommendation_store.set_ready(
            False,
            reason="OBSERVATION_WARMUP",
        )
        self.market_client.connect()
        self.universe.load()
        self.universe.maybe_reload(
            exchange=self.market_client,
            force=True,
        )
        self.universe.warmup(self.market_client)
        self._sync_health_universes()
        self._update_scale_composition()
        self._prepared = True
        self._last_universe_refresh_monotonic = time.monotonic()
        if self.strategy.is_warmed_up():
            self.recommendation_store.set_ready(
                True,
                reason="READY_NO_RECOMMENDATION",
            )
            self.system_log.info(
                "OBSERVATION_WORKER_READY | "
                f"environment={TRADING_ENV} | "
                f"execution_mode={EXECUTION_MODE} | "
                f"execution_symbols={len(self.universe.symbols)} | "
                f"observation_symbols={len(self.universe.observation_symbols)} | "
                "order_authority=NONE"
            )
        else:
            self.recommendation_store.set_ready(
                False,
                reason="STRATEGY_NOT_WARMED",
            )

    def process_tick(self, tick) -> list[dict]:
        """Process one public Binance tick; exposed separately for tests."""
        if not self._prepared:
            raise RuntimeError("OBSERVATION_WORKER_NOT_PREPARED")

        self._maybe_refresh_universe()
        self._maybe_refresh_virtual_cost_evidence(tick)
        self.health_monitor.record_tick(tick.symbol)
        self.strategy.on_price(
            symbol=tick.symbol,
            price=tick.price,
            timestamp=tick.timestamp,
        )

        if not self.strategy.is_warmed_up():
            self.recommendation_store.set_ready(
                False,
                reason="STRATEGY_NOT_WARMED",
            )
            return []

        self.recommendation_store.set_ready(
            True,
            reason="READY_NO_RECOMMENDATION",
        )
        try:
            processed = self.strategy.process_ready_decision_cycles(
                # Observation does not know/care whether Execution is currently
                # flat. This flag means "produce a routed recommendation for the
                # latest completed cycle", not "place an order".
                paper_entry_allowed=True,
                market_context_provider=self._market_context_snapshot,
            )
        except TypeError as exc:
            # Compatibility for focused tests/local strategy doubles that
            # still expose the pre-Phase-7.1 method signature.
            if "market_context_provider" not in str(exc):
                raise
            processed = self.strategy.process_ready_decision_cycles(
                paper_entry_allowed=True,
            )
        if processed:
            self.health_monitor.record_decision_cycles(processed)
            intent = self.strategy.consume_observation_recommendation()
            if intent is None:
                self.recommendation_store.clear(
                    reason="NO_EXECUTION_ELIGIBLE_CANDIDATE"
                )
            else:
                self.recommendation_store.publish_intent(intent)
        return processed

    def _market_context_snapshot(self, *, candle_bucket: int) -> dict:
        return self.market_context_provider.snapshot(
            symbols=self.universe.observation_symbols,
            candle_bucket=candle_bucket,
        )

    def _maybe_refresh_virtual_cost_evidence(self, tick) -> None:
        setter = getattr(
            self.strategy,
            "set_virtual_cost_evidence",
            None,
        )
        if not callable(setter):
            return
        bucket = int(tick.timestamp) // 300000
        if self._last_virtual_cost_bucket == bucket:
            return

        end_ms = int(tick.timestamp)
        default_start_ms = max(0, end_ms - (4 * 60 * 60 * 1000))
        start_getter = getattr(
            self.strategy,
            "get_virtual_cost_evidence_start_ms",
            None,
        )
        start_ms = (
            start_getter(default_start_ms=default_start_ms)
            if callable(start_getter)
            else default_start_ms
        )
        try:
            snapshot = self.virtual_cost_evidence_provider.snapshot(
                symbols=self.universe.observation_symbols,
                candle_bucket=bucket,
                start_ms=int(start_ms),
                end_ms=end_ms,
            )
        except Exception as exc:
            self.system_log.warning(
                "PHASE7_COST_EVIDENCE_FAILED | "
                f"bucket={bucket} | "
                f"error={type(exc).__name__}:{exc} | "
                "learning_cost_completeness=PARTIAL"
            )
        else:
            setter(snapshot)
        finally:
            # One attempt per bucket. A failed snapshot remains incomplete and
            # therefore cannot silently enter Phase-7 training evidence.
            self._last_virtual_cost_bucket = bucket

    def observation_health_snapshot(self) -> dict:
        """Return read-only Observation metrics for local operator health."""
        virtual_metrics = {}
        getter = getattr(
            self.strategy,
            "get_virtual_trade_metrics",
            None,
        )
        if callable(getter):
            try:
                virtual_metrics = getter()
            except Exception:
                virtual_metrics = {}

        recommendation = {}
        status_getter = getattr(
            self.recommendation_store,
            "status_snapshot",
            None,
        )
        if callable(status_getter):
            try:
                recommendation = status_getter()
            except Exception:
                recommendation = {}

        transport_metrics = {}
        transport_getter = getattr(
            self.market_client,
            "market_data_integrity_snapshot",
            None,
        )
        if callable(transport_getter):
            try:
                transport_metrics = transport_getter()
            except Exception:
                transport_metrics = {}

        candle_metrics = {}
        candle_getter = getattr(
            self.strategy,
            "get_market_data_integrity_metrics",
            None,
        )
        if callable(candle_getter):
            try:
                candle_metrics = candle_getter()
            except Exception:
                candle_metrics = {}

        return self.health_monitor.snapshot(
            virtual_metrics=virtual_metrics,
            recommendation=recommendation,
            transport_metrics=transport_metrics,
            candle_metrics=candle_metrics,
            scale_metrics=self._scale_snapshot(),
        )

    def handle_trade_request(
        self,
        request: TradeRequest,
        *,
        now_ms: int | None = None,
    ):
        return self.trade_service.handle_trade_request(
            request,
            now_ms=now_ms,
        )

    def receive_execution_outcome(self, outcome):
        return self.outcome_receiver.receive(outcome)

    def run_forever(self) -> None:
        if not self._prepared:
            self.prepare()

        while True:
            try:
                stream = self.market_client.price_stream()
                for tick in stream:
                    self.process_tick(tick)
                self.recommendation_store.set_ready(
                    False,
                    reason="OBSERVATION_MARKET_STREAM_ENDED",
                )
                self.system_log.error(
                    "OBSERVATION_MARKET_STREAM_ENDED | restarting=true"
                )
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                self.recommendation_store.set_ready(
                    False,
                    reason="OBSERVATION_MARKET_STREAM_FAILURE",
                )
                self.system_log.error(
                    "OBSERVATION_WORKER_LOOP_FAILED | "
                    f"error={type(exc).__name__}:{exc} | retry=true"
                )
            time.sleep(2)

    def _maybe_refresh_universe(self) -> None:
        elapsed = time.monotonic() - self._last_universe_refresh_monotonic
        if elapsed < OBSERVATION_UNIVERSE_REFRESH_SECONDS:
            return

        old_execution = set(self.universe.symbols)
        old_observation = set(self.universe.observation_symbols)
        refresh_started = time.perf_counter()
        with self._scale_lock:
            self._scale_metrics["refresh_attempts"] += 1

        try:
            self.universe.maybe_reload(
                exchange=self.market_client,
                force=False,
            )
        except Exception:
            self._record_scale_refresh(
                status="FAILED_EXCEPTION",
                refresh_started=refresh_started,
                old_execution=old_execution,
                old_observation=old_observation,
            )
            raise

        composition = self._universe_scale_composition()
        status = str(
            composition.get("last_reload_status") or "UNKNOWN"
        ).upper()
        self._record_scale_refresh(
            status=status,
            refresh_started=refresh_started,
            old_execution=old_execution,
            old_observation=old_observation,
        )
        self._sync_health_universes()
        self._last_universe_refresh_monotonic = time.monotonic()

    def _universe_scale_composition(self) -> dict:
        getter = getattr(
            self.universe,
            "scale_composition_snapshot",
            None,
        )
        if callable(getter):
            try:
                return dict(getter() or {})
            except Exception:
                return {}
        return {
            "ranked_universe_count": len(
                self.universe.observation_symbols
            ),
            "effective_universe_count": len(
                self.universe.observation_symbols
            ),
            "retained_symbol_count": 0,
            "retained_extra_count": 0,
            "execution_symbol_count": len(self.universe.symbols),
            "last_reload_status": "UNKNOWN",
        }

    def _update_scale_composition(self) -> None:
        composition = self._universe_scale_composition()
        effective = int(
            composition.get("effective_universe_count", 0) or 0
        )
        with self._scale_lock:
            self._scale_metrics["peak_effective_universe_count"] = max(
                self._scale_metrics["peak_effective_universe_count"],
                effective,
            )

    def _record_scale_refresh(
        self,
        *,
        status,
        refresh_started,
        old_execution,
        old_observation,
    ) -> None:
        new_execution = set(self.universe.symbols)
        new_observation = set(self.universe.observation_symbols)
        duration_ms = max(
            0.0,
            (time.perf_counter() - refresh_started) * 1000.0,
        )
        status = str(status or "UNKNOWN").upper()
        with self._scale_lock:
            if status == "SUCCESS":
                self._scale_metrics["refresh_successes"] += 1
            elif status == "NO_CHANGE":
                self._scale_metrics["refresh_no_change"] += 1
            elif status.startswith("FAILED"):
                self._scale_metrics["refresh_failures"] += 1
            self._scale_metrics["last_refresh_status"] = status
            self._scale_metrics["last_refresh_duration_ms"] = duration_ms
            self._scale_metrics["max_refresh_duration_ms"] = max(
                self._scale_metrics["max_refresh_duration_ms"],
                duration_ms,
            )
            self._scale_metrics["last_refresh_monotonic"] = (
                time.monotonic()
            )
            self._scale_metrics["last_execution_added"] = len(
                new_execution - old_execution
            )
            self._scale_metrics["last_execution_removed"] = len(
                old_execution - new_execution
            )
            self._scale_metrics["last_observation_added"] = len(
                new_observation - old_observation
            )
            self._scale_metrics["last_observation_removed"] = len(
                old_observation - new_observation
            )
            self._scale_metrics["last_warmup_symbols_count"] = len(
                new_observation - old_observation
            )
        self._update_scale_composition()

    def _scale_snapshot(self) -> dict:
        composition = self._universe_scale_composition()
        now = time.monotonic()
        with self._scale_lock:
            snapshot = dict(self._scale_metrics)
        last_refresh = snapshot.pop("last_refresh_monotonic", None)
        snapshot["last_refresh_age_seconds"] = (
            None
            if last_refresh is None
            else max(0.0, now - float(last_refresh))
        )
        snapshot.update(composition)
        snapshot["peak_effective_universe_count"] = max(
            int(snapshot.get("peak_effective_universe_count", 0) or 0),
            int(snapshot.get("effective_universe_count", 0) or 0),
        )
        return snapshot

    def _sync_health_universes(self) -> None:
        self.health_monitor.set_universes(
            execution_symbols=self.universe.symbols,
            observation_symbols=self.universe.observation_symbols,
            observation_target_count=OBSERVATION_UNIVERSE_SIZE,
        )
