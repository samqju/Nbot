"""Observation-only runtime extracted from the legacy TradingEngine."""

from __future__ import annotations

import time

from communication.trade_request import TradeRequest
from config import (
    CANDIDATE_OUTCOMES_PATH,
    EXECUTION_MODE,
    OBSERVATION_UNIVERSE_REFRESH_SECONDS,
    STRATEGY_MODE,
    TRADING_ENV,
)
from engine.universe import UniverseManager
from execution.binance_market_client import BinanceMarketClient
from observation.execution_outcome_receiver import LocalExecutionOutcomeReceiver
from observation.recommendation import LatestRecommendationStore
from observation.trade_service import ObservationTradeService
from strategy.strategy_factory import build_strategy


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
        self._prepared = False
        self._last_universe_refresh_monotonic = 0.0

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
        processed = self.strategy.process_ready_decision_cycles(
            # Observation does not know/care whether Execution is currently
            # flat. This flag means "produce a routed recommendation for the
            # latest completed cycle", not "place an order".
            paper_entry_allowed=True,
        )
        if processed:
            intent = self.strategy.consume_observation_recommendation()
            if intent is None:
                self.recommendation_store.clear(
                    reason="NO_EXECUTION_ELIGIBLE_CANDIDATE"
                )
            else:
                self.recommendation_store.publish_intent(intent)
        return processed

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
        self.universe.maybe_reload(
            exchange=self.market_client,
            force=False,
        )
        self._last_universe_refresh_monotonic = time.monotonic()
