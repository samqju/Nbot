# ==========================================================
# Strategy — 5M Structured Conservative (Engine Compatible)
# ==========================================================

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, Optional
from strategy.trade_intent import TradeIntent
import threading
import time
from config import (
    CANDIDATE_OBSERVATIONS_PATH,
    CANDIDATE_OUTCOMES_PATH,
    PHASE7_EVIDENCE_LEDGER_PATH,
    PHASE7_EVIDENCE_GENERATION,
    PHASE7_PENDING_FACT_RETENTION_HOURS,
    LEARNING_RAW_SEGMENT_MAX_MB,
    LEARNING_RAW_RETAIN_SEGMENTS,
    AUTO_TRAINING_OUTCOME_TYPE,
    LEARNING_RUNTIME_STATE_PATH,
    SHADOW_MODEL_ARTIFACT_PATH,
    SHADOW_MODEL_PREDICTIONS_PATH,
    SHADOW_MODEL_REFRESH_SECONDS,
    SHADOW_MODEL_SCORING_ENABLED,
    RISK_PER_TRADE_USD,
    MAX_NOTIONAL_USD,
    TRADING_ENV,
    EXECUTION_MODE,
    FORWARD_OUTCOME_VARIANT_ID,
    FORWARD_SIMULATION_MAX_CANDLES,
    VIRTUAL_LAB_CATALOG_VERSION,
    VIRTUAL_LAB_ENABLED,
    VIRTUAL_LAB_MAX_ACTIVE,
    MODEL_REGISTRY_PATH,
    RULE_MODEL_VERSION,
    SHADOW_DECISIONS_PATH,
    SHADOW_DECISION_MIN_COVERAGE,
    SHADOW_DECISION_SETTLE_SECONDS,
    SHADOW_DECISION_TESTING_ENABLED,
    SHADOW_DECISION_TOP_K,
    PAPER_CANARY_EXECUTION_ENABLED,
    PAPER_CANARY_ALLOCATION_FRACTION,
    PAPER_CANARY_RISK_MULTIPLIER,
    PAPER_CANARY_MAX_TRADES_PER_UTC_DAY,
    PAPER_CANARY_MIN_MODEL_PROBABILITY,
    PAPER_CANARY_DECISIONS_PATH,
)
from strategy.structure_classifier import StructureClassifier
from strategy.candidate import rank_candidates
from strategy.candidate_generator import StructureCandidateGenerator
from strategy.candidate_observer import CandidateObservationWriter
from strategy.candidate_outcome import CandidateOutcomeWriter
from strategy.candidate_scorer import CandidateScorer
from strategy.candidate_risk import CandidateRiskPlanner
from strategy.virtual_trade_engine import VirtualTradeEngine
from strategy.learning_runtime_state import LearningRuntimeStateStore
from strategy.features import (
    CANDIDATE_FEATURE_NAMES,
    CandidateFeatureExtractor,
)
from learning.shadow_scorer import ShadowModelScorer
from learning.shadow_decision_testing import (
    ChampionChallengerShadowTester,
)
from learning.paper_canary import PaperCanaryRouter
from strategy.decision_cycle import FiveMinuteDecisionCycleCoordinator
from strategy.experiment_contract import (
    build_market_event_id,
    copy_experiment_context,
    new_decision_batch_id,
    validate_experiment_context,
)

class Strategy:

    def __init__(self, max_history: int = 200, system_log=None):
        self.system_log = system_log
        # -----------------------------
        # Candle Storage
        # -----------------------------
        self._current_candle: Dict[str, dict] = {}
        self._candle_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        self._last_ts: Dict[str, int] = {}

        # Phase 6B.2 market-data integrity telemetry. These counters are
        # observational only and never change candle construction or selection.
        self._market_data_integrity_lock = threading.Lock()
        self._candle_gap_events = 0
        self._candle_gap_buckets = 0
        self._out_of_order_tick_events = 0
        self._latest_candle_gap_by_symbol: dict[str, dict] = {}
        self._latest_out_of_order_by_symbol: dict[str, dict] = {}
        self._market_data_symbol_sample_limit = 20

        # Phase 3.6B.1 dual-universe contract.
        #
        # During B.1 both sets intentionally contain the same existing
        # symbols, so runtime behavior remains unchanged. Later B patches
        # will widen only the observation universe.
        self._execution_universe = set()
        self._observation_universe = set()

        # Backward-compatible alias used by existing candidate-generation
        # and warmup logic until the later dual-universe behavior patches.
        self._universe = set()
        self._warmed_up = False

        self._classifier = StructureClassifier()
        self._latest_structure = {}

        # Protect pending simulations and retained-observation symbol state.
        self._ml_lock = threading.Lock()

        # Phase 4 shadow scoring is the authoritative model path.
        self._learning_runtime_store = LearningRuntimeStateStore(
            LEARNING_RUNTIME_STATE_PATH,
            system_log=system_log,
        )
        self._pending_simulations = (
            self._restore_pending_simulations()
        )
        self._pending_runtime_dirty = False
        self._learning_runtime_dirty_since_monotonic = None
        self._learning_runtime_max_dirty_seconds = 30.0
        self.MAX_FORWARD_CANDLES = FORWARD_SIMULATION_MAX_CANDLES

        # -----------------------------
        # Trade Governor (UNCHANGED)
        # -----------------------------
        self._last_trade_info = {}  # {symbol: (bucket, direction)}
        # Last current-candle bucket evaluated per symbol. Since the
        # strategy uses completed candles only, a new current bucket means
        # exactly one newly closed 5-minute candle is available.
        self._last_evaluated_bucket = {}
        self.COUNTER_TRADE_SPACING_BUCKETS = 6

        # -----------------------------
        # 5M Windows
        # -----------------------------
        self.SHORT_WINDOW = 10
        self.LONG_WINDOW = 30
        self.WARMUP_WINDOW = 50

        # Phase 3.1: candidate discovery is isolated from final intent
        # selection while preserving the existing structure rules.
        self._feature_extractor = CandidateFeatureExtractor(self)
        self._candidate_generator = StructureCandidateGenerator(self)
        self._candidate_scorer = CandidateScorer()
        self._candidate_risk_planner = CandidateRiskPlanner()
        raw_segment_max_bytes = int(
            LEARNING_RAW_SEGMENT_MAX_MB * 1024 * 1024
        )
        self._candidate_observer = CandidateObservationWriter(
            CANDIDATE_OBSERVATIONS_PATH,
            system_log=system_log,
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
            evidence_ledger_path=PHASE7_EVIDENCE_LEDGER_PATH,
            evidence_generation=PHASE7_EVIDENCE_GENERATION,
            training_outcome_type=AUTO_TRAINING_OUTCOME_TYPE,
            pending_fact_retention_hours=(
                PHASE7_PENDING_FACT_RETENTION_HOURS
            ),
            raw_segment_max_bytes=raw_segment_max_bytes,
            raw_retain_segments=LEARNING_RAW_RETAIN_SEGMENTS,
        )
        self._candidate_outcome_writer = CandidateOutcomeWriter(
            CANDIDATE_OUTCOMES_PATH,
            system_log=system_log,
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
            evidence_ledger_path=PHASE7_EVIDENCE_LEDGER_PATH,
            evidence_generation=PHASE7_EVIDENCE_GENERATION,
            training_outcome_type=AUTO_TRAINING_OUTCOME_TYPE,
            pending_fact_retention_hours=(
                PHASE7_PENDING_FACT_RETENTION_HOURS
            ),
            raw_segment_max_bytes=raw_segment_max_bytes,
            raw_retain_segments=LEARNING_RAW_RETAIN_SEGMENTS,
        )
        self._virtual_trade_engine = VirtualTradeEngine(
            system_log=system_log,
            outcome_writer=self._candidate_outcome_writer,
            runtime_store=self._learning_runtime_store,
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
            lab_enabled=VIRTUAL_LAB_ENABLED,
            catalog_version=VIRTUAL_LAB_CATALOG_VERSION,
            max_active=VIRTUAL_LAB_MAX_ACTIVE,
        )
        self._shadow_model_scorer = ShadowModelScorer(
            enabled=SHADOW_MODEL_SCORING_ENABLED,
            artifact_path=SHADOW_MODEL_ARTIFACT_PATH,
            predictions_path=SHADOW_MODEL_PREDICTIONS_PATH,
            refresh_seconds=SHADOW_MODEL_REFRESH_SECONDS,
            system_log=system_log,
        )
        self._decision_cycle_coordinator = (
            FiveMinuteDecisionCycleCoordinator(
                minimum_coverage=SHADOW_DECISION_MIN_COVERAGE,
                settle_seconds=SHADOW_DECISION_SETTLE_SECONDS,
            )
        )
        self._champion_challenger_tester = (
            ChampionChallengerShadowTester(
                enabled=SHADOW_DECISION_TESTING_ENABLED,
                environment=TRADING_ENV,
                registry_path=MODEL_REGISTRY_PATH,
                default_champion_model_id=RULE_MODEL_VERSION,
                decisions_path=SHADOW_DECISIONS_PATH,
                top_k=SHADOW_DECISION_TOP_K,
                system_log=system_log,
                require_phase7_validation=True,
            )
        )
        self._paper_canary_router = PaperCanaryRouter(
            enabled=PAPER_CANARY_EXECUTION_ENABLED,
            execution_mode=EXECUTION_MODE,
            environment=TRADING_ENV,
            registry_path=MODEL_REGISTRY_PATH,
            default_champion_model_id=RULE_MODEL_VERSION,
            decisions_path=PAPER_CANARY_DECISIONS_PATH,
            trades_path=CANDIDATE_OUTCOMES_PATH,
            allocation_fraction=PAPER_CANARY_ALLOCATION_FRACTION,
            risk_multiplier=PAPER_CANARY_RISK_MULTIPLIER,
            max_trades_per_utc_day=(
                PAPER_CANARY_MAX_TRADES_PER_UTC_DAY
            ),
            minimum_model_probability=(
                PAPER_CANARY_MIN_MODEL_PROBABILITY
            ),
            system_log=system_log,
        )
        self._pending_paper_candidate = None
        self._pending_paper_route = None
        self._coordinated_runtime_enabled = False

    def _restore_pending_simulations(self):
        rows = self._learning_runtime_store.get_section(
            "pending_simulations"
        )
        restored = []
        ids = set()
        for simulation in rows:
            self._validate_pending_simulation(simulation)
            observation_id = simulation[
                "candidate_observation_id"
            ]
            if observation_id in ids:
                raise RuntimeError(
                    "PENDING_SIMULATION_RECOVERY_DUPLICATE_ID"
                )
            ids.add(observation_id)
            restored.append(dict(simulation))

        if self.system_log:
            self.system_log.info(
                "PENDING_SIMULATIONS_RECOVERED | "
                f"count={len(restored)}"
            )
        return restored

    @staticmethod
    def _validate_pending_simulation(simulation):
        required = {
            "candidate_observation_id",
            "symbol",
            "direction",
            "entry_price",
            "risk_distance",
            "candles_seen",
            "mae",
            "mfe",
        }
        if (
            not isinstance(simulation, dict)
            or not required.issubset(simulation)
        ):
            raise RuntimeError(
                "PENDING_SIMULATION_RECOVERY_SCHEMA_INVALID"
            )
        if simulation["direction"] not in {"LONG", "SHORT"}:
            raise RuntimeError(
                "PENDING_SIMULATION_RECOVERY_DIRECTION_INVALID"
            )
        if float(simulation["entry_price"]) <= 0:
            raise RuntimeError(
                "PENDING_SIMULATION_RECOVERY_ENTRY_INVALID"
            )
        if float(simulation["risk_distance"]) <= 0:
            raise RuntimeError(
                "PENDING_SIMULATION_RECOVERY_RISK_INVALID"
            )
        if int(simulation["candles_seen"]) < 0:
            raise RuntimeError(
                "PENDING_SIMULATION_RECOVERY_CANDLES_INVALID"
            )

    def add_pending_simulation(
        self,
        simulation,
        *,
        persist: bool = True,
    ):
        self._validate_pending_simulation(simulation)
        with self._ml_lock:
            observation_id = simulation[
                "candidate_observation_id"
            ]
            if any(
                row.get("candidate_observation_id")
                == observation_id
                for row in self._pending_simulations
            ):
                return False
            self._pending_simulations.append(dict(simulation))
            if persist:
                self._persist_pending_simulations_locked()
            else:
                self._pending_runtime_dirty = True
                self._mark_learning_runtime_dirty()
        return True

    def _persist_pending_simulations_locked(self):
        self._learning_runtime_store.replace_section(
            "pending_simulations",
            [
                dict(simulation)
                for simulation in self._pending_simulations
            ],
        )
        self._pending_runtime_dirty = False

    def _mark_learning_runtime_dirty(
        self,
        *,
        now_monotonic: float | None = None,
    ) -> None:
        if self._learning_runtime_dirty_since_monotonic is not None:
            return
        self._learning_runtime_dirty_since_monotonic = (
            time.monotonic()
            if now_monotonic is None
            else float(now_monotonic)
        )

    def _maybe_flush_learning_runtime_progress(
        self,
        *,
        force: bool = False,
        now_monotonic: float | None = None,
    ) -> bool:
        """Persist deferred learning progress in one atomic checkpoint."""
        dirty_getter = getattr(
            self._virtual_trade_engine,
            "has_dirty_state",
            None,
        )
        virtual_dirty = (
            bool(dirty_getter())
            if callable(dirty_getter)
            else False
        )
        dirty = self._pending_runtime_dirty or virtual_dirty
        if not dirty:
            self._learning_runtime_dirty_since_monotonic = None
            return False

        now = (
            time.monotonic()
            if now_monotonic is None
            else float(now_monotonic)
        )
        if self._learning_runtime_dirty_since_monotonic is None:
            self._learning_runtime_dirty_since_monotonic = now
        dirty_age = now - self._learning_runtime_dirty_since_monotonic
        if not force and dirty_age < self._learning_runtime_max_dirty_seconds:
            return False

        with self._ml_lock:
            pending_rows = [
                dict(simulation)
                for simulation in self._pending_simulations
            ]
        snapshot_getter = getattr(
            self._virtual_trade_engine,
            "runtime_state_snapshot",
            None,
        )
        if callable(snapshot_getter):
            active_rows = snapshot_getter()
            self._learning_runtime_store.replace_sections({
                "pending_simulations": pending_rows,
                "active_virtual_trades": active_rows,
            })
        else:
            # Compatibility with narrow test/local substitutes that provide
            # only enroll_all(). The production VirtualTradeEngine always
            # supports a combined snapshot.
            self._learning_runtime_store.replace_section(
                "pending_simulations",
                pending_rows,
            )

        self._pending_runtime_dirty = False
        persisted_marker = getattr(
            self._virtual_trade_engine,
            "mark_runtime_state_persisted",
            None,
        )
        if callable(persisted_marker):
            persisted_marker()
        self._learning_runtime_dirty_since_monotonic = None
        return True

    # ======================================================
    # Candle Builder (5M)
    # ======================================================

    def on_price(self, symbol: str, price: float, timestamp: int):

        # The exchange price stream may contain every listed contract. The
        # strategy must build candles only for the active selected universe.
        if self._universe and symbol not in self._universe:
            return

        bucket = timestamp // 300000  # 5m bucket

        candle = self._current_candle.get(symbol)

        if candle is not None and candle["bucket"] != bucket:
            self._record_candle_transition_integrity(
                symbol=symbol,
                previous_bucket=int(candle["bucket"]),
                new_bucket=int(bucket),
            )

        if candle is None or candle["bucket"] != bucket:

            if candle is not None:
                self._candle_history[symbol].append(
                    (
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                    )
                )

                # Keep the latest market-structure fingerprint aligned
                # with the newest completed 5-minute candle.
                try:
                    self._latest_structure[symbol] = self._classifier.fingerprint(
                        list(self._candle_history[symbol])
                    )
                except Exception as e:
                    if self.system_log:
                        self.system_log.error(
                            f"STRUCTURE_FINGERPRINT_ERROR | "
                            f"symbol={symbol} | error={e}"
                        )

                # Update learning simulations in memory. Runtime state is
                # checkpointed once for the coordinated rollover batch instead
                # of rewriting the whole recovery document per symbol.
                self._update_simulations(symbol, persist=False)
                self._virtual_trade_engine.on_candle(
                    symbol,
                    (
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                    ),
                    persist=False,
                    closed_at_ms=timestamp,
                )
                if self._virtual_trade_engine.has_dirty_state():
                    self._mark_learning_runtime_dirty()
                self._decision_cycle_coordinator.mark_rollover(
                    symbol=symbol,
                    new_bucket=bucket,
                )

            self._current_candle[symbol] = {
                "bucket": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }

        else:
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

        self._last_ts[symbol] = timestamp

        # Warmup check
        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

    def _record_candle_transition_integrity(
        self,
        *,
        symbol: str,
        previous_bucket: int,
        new_bucket: int,
    ) -> None:
        """Record gaps/out-of-order bucket transitions without changing them."""
        previous_bucket = int(previous_bucket)
        new_bucket = int(new_bucket)
        symbol = str(symbol).strip().upper()
        with self._market_data_integrity_lock:
            if new_bucket > previous_bucket + 1:
                missing = new_bucket - previous_bucket - 1
                self._candle_gap_events += 1
                self._candle_gap_buckets += missing
                self._latest_candle_gap_by_symbol[symbol] = {
                    "symbol": symbol,
                    "previous_bucket": previous_bucket,
                    "new_bucket": new_bucket,
                    "missing_buckets": missing,
                }
                self._bound_integrity_samples_locked(
                    self._latest_candle_gap_by_symbol
                )
            elif new_bucket < previous_bucket:
                self._out_of_order_tick_events += 1
                self._latest_out_of_order_by_symbol[symbol] = {
                    "symbol": symbol,
                    "previous_bucket": previous_bucket,
                    "new_bucket": new_bucket,
                }
                self._bound_integrity_samples_locked(
                    self._latest_out_of_order_by_symbol
                )

    def _bound_integrity_samples_locked(self, rows: dict) -> None:
        while len(rows) > self._market_data_symbol_sample_limit:
            rows.pop(next(iter(rows)))

    def _decision_cycle_integrity_snapshot(self) -> dict:
        coordinator = getattr(self, "_decision_cycle_coordinator", None)
        getter = getattr(coordinator, "integrity_snapshot", None)
        if not callable(getter):
            return {}
        try:
            return getter()
        except Exception:
            return {}

    def get_market_data_integrity_metrics(self) -> dict:
        """Return read-only live candle-continuity diagnostics."""
        try:
            with self._market_data_integrity_lock:
                return {
                    "candle_gap_events": self._candle_gap_events,
                    "missing_candle_buckets": self._candle_gap_buckets,
                    "out_of_order_tick_events": (
                        self._out_of_order_tick_events
                    ),
                    "gap_symbols_count": len(
                        self._latest_candle_gap_by_symbol
                    ),
                    "out_of_order_symbols_count": len(
                        self._latest_out_of_order_by_symbol
                    ),
                    "gap_symbols_sample": [
                        dict(row)
                        for row in self._latest_candle_gap_by_symbol.values()
                    ],
                    "out_of_order_symbols_sample": [
                        dict(row)
                        for row in (
                            self._latest_out_of_order_by_symbol.values()
                        )
                    ],
                    "decision_cycle_quality": (
                        self._decision_cycle_integrity_snapshot()
                    ),
                }
        except Exception:
            return {}

    # ======================================================
    # Historical Warmup Seeder
    # ======================================================

    def seed_candle_history(self, symbol: str, candles) -> int:
        """
        Replace one symbol's completed history with closed REST candles.

        UniverseManager calls this while preparing newly added symbols,
        before committing the new universe to Strategy. Therefore this
        method must not reject a symbol merely because it is not yet in
        self._universe.
        """
        ordered = sorted(candles, key=lambda item: int(item[0]))
        history = self._candle_history[symbol]
        history.clear()

        last_bucket = None

        for timestamp, o, h, l, c in ordered:
            bucket = int(timestamp) // 300000

            # Defensive de-duplication for repeated REST rows.
            if bucket == last_bucket:
                continue

            o = float(o)
            h = float(h)
            l = float(l)
            c = float(c)

            if min(o, h, l, c) <= 0:
                continue
            if h < max(o, c) or l > min(o, c) or h < l:
                continue

            history.append((o, h, l, c))
            last_bucket = bucket

        # Historical rows are completed candles. The current live candle must
        # be created only by the first live tick received after startup.
        self._current_candle.pop(symbol, None)
        self._last_ts.pop(symbol, None)
        self._last_evaluated_bucket.pop(symbol, None)

        if history:
            try:
                self._latest_structure[symbol] = self._classifier.fingerprint(
                    list(history)
                )
            except Exception as e:
                if self.system_log:
                    self.system_log.error(
                        f"STRUCTURE_FINGERPRINT_ERROR | symbol={symbol} | error={e}"
                    )

        self._warmed_up = bool(
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        )

        return len(history)

    # ======================================================
    # Warmup Seeder (UNCHANGED CONTRACT)
    # ======================================================

    def seed_candle(
        self,
        symbol: str,
        o: float,
        h: float,
        l: float,
        c: float,
        timestamp: int,
    ):

        bucket = timestamp // 300000

        self._candle_history[symbol].append((o, h, l, c))

        candles = list(self._candle_history[symbol])

        if len(candles) < 20:
            return

        try:
            fingerprint = self._classifier.fingerprint(candles)
            self._latest_structure[symbol] = fingerprint
        except Exception as e:
            if self.system_log:
                self.system_log.error(
                    f"STRUCTURE_FINGERPRINT_ERROR | symbol={symbol} | error={e}"
                )
        self._current_candle[symbol] = {
            "bucket": bucket,
            "open": c,
            "high": c,
            "low": c,
            "close": c,
        }

        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

    # ======================================================
    # Universe
    # ======================================================

    def set_universe(self, symbols):
        """Backward-compatible setter for one shared universe."""
        self.set_universes(
            execution_symbols=symbols,
            observation_symbols=symbols,
        )

    def set_universes(
        self,
        *,
        execution_symbols,
        observation_symbols,
    ):
        """Set the execution and observation symbol sets.

        Phase 3.6B.1 establishes the contract only. The current
        UniverseManager supplies the same 30 symbols to both sets.
        """
        execution = set(execution_symbols)
        observation = set(observation_symbols)

        if not execution:
            raise ValueError("EXECUTION_UNIVERSE_EMPTY")
        if not observation:
            raise ValueError("OBSERVATION_UNIVERSE_EMPTY")
        if not execution.issubset(observation):
            raise ValueError(
                "EXECUTION_UNIVERSE_NOT_SUBSET_OF_OBSERVATION"
            )

        self._execution_universe = execution
        self._observation_universe = observation

        # Existing scanning behavior remains tied to the shared alias in
        # B.1. B.2 will intentionally point scanning at the expanded
        # observation universe.
        self._universe = set(observation)
        self._decision_cycle_coordinator.set_symbols(
            observation,
            execution_symbols=execution,
        )
        self._warmed_up = False

    def get_execution_universe(self):
        return set(self._execution_universe)

    def get_observation_universe(self):
        return set(self._observation_universe)

    def get_retained_observation_symbols(self):
        """Symbols whose learning lifecycle has not yet completed."""
        with self._ml_lock:
            pending_symbols = {
                sim["symbol"]
                for sim in self._pending_simulations
                if sim.get("symbol")
            }
        return (
            pending_symbols
            | self._virtual_trade_engine.active_symbols()
        )

    def get_virtual_trade_metrics(self) -> dict:
        """Expose virtual-trade telemetry without changing virtual state."""
        return self._virtual_trade_engine.metrics_snapshot()

    def set_virtual_cost_evidence(self, snapshot: dict | None) -> None:
        setter = getattr(
            self._virtual_trade_engine,
            "set_cost_evidence_snapshot",
            None,
        )
        if callable(setter):
            setter(snapshot)

    def get_virtual_cost_evidence_start_ms(
        self,
        *,
        default_start_ms: int,
    ) -> int:
        getter = getattr(
            self._virtual_trade_engine,
            "oldest_active_opened_at_ms",
            None,
        )
        oldest = getter() if callable(getter) else None
        if oldest is None:
            return int(default_start_ms)
        # Phase 7.5C.1: when virtual trades are active, the oldest open
        # timestamp is the exact funding-evidence horizon we need.  The old
        # min(default_start_ms, oldest) behavior forced every live refresh to
        # request at least four hours of global Binance funding history even
        # when the oldest trade was only minutes old.  That enlarged/paginated
        # the response unnecessarily and could make funding completeness fail
        # for otherwise valid short-lived virtual outcomes.
        return int(oldest)

    def get_structure(self, symbol):
        return self._latest_structure.get(symbol)

    def is_warmed_up(self) -> bool:
        return self._warmed_up

    # ======================================================
    # Helpers
    # ======================================================

    def _counter_trade_spacing_ok(self, symbol, bucket, direction):
        """
        Prevent immediate counter-trade.
        Allow same-direction continuation.
        """
        last = self._last_trade_info.get(symbol)

        if last is None:
            return True

        last_bucket, last_direction = last

        # Only block opposite direction
        if last_direction != direction:
            return (
                bucket - last_bucket
            ) >= self.COUNTER_TRADE_SPACING_BUCKETS

        return True

    def _avg_range(self, candles, window):
        if len(candles) < window:
            return None
        recent = list(candles)[-window:]
        ranges = [(c[1] - c[2]) for c in recent]
        return sum(ranges) / len(ranges)

    def _trend_score(self, candles):
        c_list = list(candles)
        closes = [c[3] for c in c_list[-10:]]
        score = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                score += 1
            elif closes[i] < closes[i - 1]:
                score -= 1
        return score

    def _strong_pullback(self, candles):
        if len(candles) < 5:
            return False

        last3 = list(candles)[-3:]
        r0 = last3[0][1] - last3[0][2]
        r1 = last3[1][1] - last3[1][2]
        r2 = last3[2][1] - last3[2][2]

        return r1 < r0 and r2 < r1

    def _breakout_score(self, candles):
        c_list = list(candles)

        highs = [c[1] for c in c_list[-20:]]
        lows = [c[2] for c in c_list[-20:]]
        last_close = c_list[-1][3]

        if last_close > max(highs[:-1]):
            return 4
        if last_close < min(lows[:-1]):
            return 4
        return 0

    # --------------------------------------------------
    # STRUCTURE QUALITY SCORE
    # --------------------------------------------------

    def _structure_score(self, candles):

        trend = abs(self._trend_score(candles)) / 10.0

        ranges = [(c[1] - c[2]) for c in candles]

        short = sum(ranges[-5:]) / 5
        long = sum(ranges) / len(ranges)

        volatility = short / long if long > 0 else 0

        breakout = abs(self._breakout_score(candles))

        pullback = 1.0 if self._strong_pullback(candles) else 0.0

        score = (
            0.35 * trend +
            0.30 * volatility +
            0.20 * breakout +
            0.15 * pullback
        )

        return score

    def _is_compressing(self, candles):
        """
        Strong compression:
        - Last 8 candles tighter than prior 12
        - AND bodies shrinking
        """

        if len(candles) < 25:
            return False

        c = list(candles)

        recent = c[-8:]
        prior = c[-20:-8]

        recent_range = sum(x[1] - x[2] for x in recent) / len(recent)
        prior_range = sum(x[1] - x[2] for x in prior) / len(prior)

        if prior_range <= 0:
            return False

        # Volatility compression
        if recent_range >= (0.65 * prior_range):
            return False

        # Body contraction
        recent_body = sum(abs(x[3] - x[0]) for x in recent) / len(recent)
        prior_body = sum(abs(x[3] - x[0]) for x in prior) / len(prior)

        if recent_body >= prior_body:
            return False

        return True

    def _has_directional_bias(self, candles):
        """
        Require directional push before breakout.
        Prevents entering random spikes.
        """

        if len(candles) < 15:
            return False

        closes = [c[3] for c in list(candles)[-10:]]

        up_moves = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        down_moves = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])

        return max(up_moves, down_moves) >= 6

    # ==========================================================
    # Machine Learning
    # ==========================================================
    # ======================================================
    # Forward Simulation Labeling
    # ======================================================
    def _update_simulations(self, symbol, *, persist: bool = True):

        candles = self._candle_history.get(symbol)
        if not candles:
            return

        latest = candles[-1]
        high = latest[1]
        low = latest[2]

        finished = []
        changed = False

        with self._ml_lock:
            for sim in self._pending_simulations:

                # A newly closed candle may update only simulations for
                # the same symbol. Cross-symbol prices would corrupt MAE,
                # MFE, candle counts, and every resulting training label.
                if sim["symbol"] != symbol:
                    continue
                changed = True

                entry = sim["entry_price"]
                direction = sim["direction"]
                risk = sim["risk_distance"]

                # Convert to R units
                if direction == "LONG":
                    adverse_move = (entry - low) / risk
                    favorable_move = (high - entry) / risk
                else:
                    adverse_move = (high - entry) / risk
                    favorable_move = (entry - low) / risk

                sim["mae"] = max(sim["mae"], adverse_move)
                sim["mfe"] = max(sim["mfe"], favorable_move)

                sim["candles_seen"] += 1

                # --- EARLY WEAKNESS LABEL ---
                label = None

                # After first 3 candles decide
                if sim["candles_seen"] == 3:
                    if sim["mae"] >= 0.5:
                        label = 1  # BAD ENTRY
                    else:
                        label = 0  # GOOD ENTRY

                # Hard stop at 5 candles to finalize dataset row
                if sim["candles_seen"] >= self.MAX_FORWARD_CANDLES:

                    target_r = sim["mfe"] - sim["mae"]

                    try:
                        self._candidate_outcome_writer.append(
                            observation_id=sim.get(
                                "candidate_observation_id"
                            ),
                            outcome_type="FORWARD_5_CANDLE",
                            symbol=sim["symbol"],
                            direction=sim["direction"],
                            payload={
                                "mae_r": sim["mae"],
                                "mfe_r": sim["mfe"],
                                "target_r": target_r,
                                "label": 1 if target_r > 0 else 0,
                                "candles_seen": sim["candles_seen"],
                                "outcome_variant_id": (
                                    FORWARD_OUTCOME_VARIANT_ID
                                ),
                            },
                            experiment_context=sim.get(
                                "experiment_context"
                            ),
                            outcome_variant_id=(
                                FORWARD_OUTCOME_VARIANT_ID
                            ),
                        )
                    except Exception as e:
                        if self.system_log:
                            self.system_log.error(
                                "CANDIDATE_FORWARD_OUTCOME_WRITE_FAILED | "
                                f"symbol={sim['symbol']} | error={e}"
                            )
                    finished.append(sim)

            for f in finished:
                self._pending_simulations.remove(f)

            # Direct callers preserve the original immediate durability.
            # The coordinated Observation runtime defers these whole-state
            # rewrites and checkpoints the rollover batch atomically.
            if changed:
                if persist:
                    self._persist_pending_simulations_locked()
                else:
                    self._pending_runtime_dirty = True
                    self._mark_learning_runtime_dirty()

    # ======================================================
    # Phase 5.9 Decision-Cycle Processing
    # ======================================================

    def process_ready_decision_cycles(
        self,
        *,
        paper_entry_allowed: bool,
        now_monotonic: float | None = None,
        market_context_provider=None,
    ) -> list[dict]:
        """Evaluate completed five-minute cycles regardless of paper exposure.

        When paper_entry_allowed is false, the same candidates, virtual
        experiments, and champion/challenger decisions are recorded, but no
        TradeIntent is retained for later execution.
        """
        self._coordinated_runtime_enabled = True
        if not self._warmed_up:
            return []
        ready = self._decision_cycle_coordinator.ready_buckets(
            now_monotonic=now_monotonic
        )
        self._maybe_flush_learning_runtime_progress(
            force=bool(ready),
            now_monotonic=now_monotonic,
        )
        processed = []
        for index, coverage in enumerate(ready):
            bucket = int(coverage["candle_bucket"])
            allow_paper = bool(
                paper_entry_allowed and index == len(ready) - 1
            )
            market_context_snapshot = None
            if callable(market_context_provider):
                try:
                    market_context_snapshot = market_context_provider(
                        candle_bucket=bucket
                    )
                except Exception as e:
                    if self.system_log:
                        self.system_log.error(
                            "PHASE7_MARKET_CONTEXT_FAILED | "
                            f"bucket={bucket} | error={e} | "
                            "candidate_selection_effect=NONE"
                        )
            try:
                result = self._evaluate_decision_batch(
                    decision_bucket=bucket,
                    paper_entry_allowed=allow_paper,
                    cycle_coverage=coverage,
                    market_context_snapshot=market_context_snapshot,
                )
                processed.append(result)
            finally:
                self._decision_cycle_coordinator.mark_processed(bucket)
        return processed

    def _evaluate_decision_batch(
        self,
        *,
        decision_bucket: int | None,
        paper_entry_allowed: bool,
        cycle_coverage: dict | None = None,
        market_context_snapshot: dict | None = None,
    ) -> dict:
        decision_batch_id = new_decision_batch_id()
        generator_kwargs = {
            "decision_batch_id": decision_batch_id,
            "decision_bucket": decision_bucket,
        }
        if market_context_snapshot is not None:
            generator_kwargs["market_context_snapshot"] = (
                market_context_snapshot
            )
        try:
            candidates = self._candidate_generator.generate(
                **generator_kwargs
            )
        except TypeError as exc:
            text = str(exc)
            if (
                "market_context_snapshot" in generator_kwargs
                and "unexpected keyword" in text
            ):
                generator_kwargs.pop("market_context_snapshot", None)
                candidates = self._candidate_generator.generate(
                    **generator_kwargs
                )
            elif decision_bucket is None and "unexpected keyword" in text:
                # Older tests and local extensions may replace generate()
                # with a no-argument callable on the direct path.
                candidates = self._candidate_generator.generate()
            else:
                raise
        self._pending_paper_candidate = None
        self._pending_paper_route = None

        scored_candidates = self._candidate_scorer.score_all(candidates)
        planned_candidates = self._candidate_risk_planner.plan_all(
            scored_candidates
        )
        try:
            self._virtual_trade_engine.enroll_all(
                planned_candidates,
                persist=False,
            )
        except TypeError as exc:
            # Preserve compatibility with older tests/local extensions that
            # replace enroll_all() with the original one-argument callable.
            if "unexpected keyword" not in str(exc):
                raise
            self._virtual_trade_engine.enroll_all(planned_candidates)

        dirty_getter = getattr(
            self._virtual_trade_engine,
            "has_dirty_state",
            None,
        )
        if callable(dirty_getter) and dirty_getter():
            self._mark_learning_runtime_dirty()

        # Candidate generation may have added many forward simulations with
        # deferred persistence. Checkpoint pending simulations and virtual
        # enrollments together once per completed evaluation batch.
        self._maybe_flush_learning_runtime_progress(force=True)
        ranked_candidates = rank_candidates(planned_candidates)
        execution_candidates = [
            candidate
            for candidate in ranked_candidates
            if candidate.symbol in self._execution_universe
        ]
        rule_candidate = (
            execution_candidates[0]
            if paper_entry_allowed and execution_candidates
            else None
        )

        if decision_bucket is None:
            candidate_buckets = [
                int(getattr(candidate, "bucket", 0) or 0)
                for candidate in ranked_candidates
            ]
            effective_bucket = (
                max(candidate_buckets) if candidate_buckets else 0
            )
        else:
            effective_bucket = int(decision_bucket)
        market_event_id = build_market_event_id(
            environment=TRADING_ENV,
            candle_bucket=effective_bucket,
        )

        paper_route = None
        paper_candidate = rule_candidate
        if rule_candidate is not None:
            paper_route = self._paper_canary_router.route(
                candidates=execution_candidates,
                rule_candidate=rule_candidate,
                decision_batch_id=decision_batch_id,
                market_event_id=market_event_id,
                candle_bucket=effective_bucket,
            )
            paper_candidate = paper_route.candidate

        # Preserve the legacy Phase 4 shadow stream for historical continuity.
        try:
            self._shadow_model_scorer.score_candidates(
                ranked_candidates,
                rule_selected_candidate=rule_candidate,
            )
        except Exception as e:
            if self.system_log:
                self.system_log.error(
                    "SHADOW_MODEL_BATCH_FAILED | "
                    f"error={e} | runtime_effect=NONE"
                )
        snapshot = None
        try:
            snapshot = self._champion_challenger_tester.record_cycle(
                candidates=ranked_candidates,
                decision_batch_id=decision_batch_id,
                market_event_id=market_event_id,
                candle_bucket=effective_bucket,
                cycle_coverage=cycle_coverage,
            )
        except Exception as e:
            if self.system_log:
                self.system_log.error(
                    "CHAMPION_CHALLENGER_DECISION_FAILED | "
                    f"batch={decision_batch_id} | error={e} | "
                    "runtime_effect=NONE"
                )

        for rank, candidate in enumerate(ranked_candidates, start=1):
            try:
                self._candidate_observer.append(
                    candidate,
                    rank=rank,
                    selected=(candidate is paper_candidate),
                )
            except Exception as e:
                if self.system_log:
                    self.system_log.error(
                        "CANDIDATE_OBSERVATION_WRITE_FAILED | "
                        f"symbol={candidate.symbol} | error={e}"
                    )

        if paper_candidate is not None:
            self._pending_paper_candidate = paper_candidate
            self._pending_paper_route = paper_route
        elif self.system_log and ranked_candidates:
            self.system_log.info(
                "OBSERVATION_CANDIDATES_ONLY | "
                f"count={len(ranked_candidates)} | "
                "paper_intent=NONE"
            )

        return {
            "decision_batch_id": decision_batch_id,
            "market_event_id": market_event_id,
            "candle_bucket": effective_bucket,
            "candidate_count": len(ranked_candidates),
            "cycle_coverage": dict(cycle_coverage or {}),
            "paper_candidate_id": (
                paper_candidate.observation_id
                if paper_candidate is not None
                else None
            ),
            "shadow_snapshot_written": snapshot is not None,
            "paper_selection_authority": (
                paper_route.selection_authority
                if paper_route is not None
                else ("RULES" if paper_candidate is not None else None)
            ),
            "paper_canary_model_id": (
                paper_route.model_id if paper_route is not None else None
            ),
        }

    # ======================================================
    # Main Proposal Logic
    # ======================================================

    def propose_intent(self) -> Optional[TradeIntent]:
        """Consume the next execution intent using the legacy engine semantics.

        The existing single-process engine treats proposal creation as the
        point at which its trade-spacing governor advances. Keep that behavior
        unchanged while Phase 6A.0 extracts the Observation Worker.
        """
        if not self._warmed_up:
            return None

        # Backward-compatible direct-call path for unit tests and utilities.
        # The production engine enables coordinated runtime processing before
        # asking for an intent, so it never fragments a five-minute batch.
        if (
            self._pending_paper_candidate is None
            and not self._coordinated_runtime_enabled
        ):
            self._evaluate_decision_batch(
                decision_bucket=None,
                paper_entry_allowed=True,
            )

        return self._consume_pending_intent(update_trade_governor=True)

    def consume_observation_recommendation(self) -> Optional[TradeIntent]:
        """Consume the latest routed candidate without claiming execution.

        Observation continuously maintains a recommendation even when the
        future Execution Worker is busy or offline. Merely publishing that
        recommendation must not mutate the legacy trade-spacing governor,
        because publication is not proof that capital was entered.
        """
        if not self._warmed_up:
            return None
        return self._consume_pending_intent(update_trade_governor=False)

    def _consume_pending_intent(
        self,
        *,
        update_trade_governor: bool,
    ) -> Optional[TradeIntent]:
        best_candidate = self._pending_paper_candidate
        paper_route = self._pending_paper_route
        self._pending_paper_candidate = None
        self._pending_paper_route = None
        if best_candidate is None:
            return None

        best_symbol = best_candidate.symbol
        best_direction = best_candidate.direction

        if self.system_log and best_candidate.risk_plan is not None:
            plan = best_candidate.risk_plan
            self.system_log.info(
                "CANDIDATE_RISK_PLAN | "
                f"symbol={best_symbol} | direction={best_direction} | "
                f"risk_usd={plan.risk_budget_usd:.6f} | "
                f"stop_pct={plan.stop_distance_pct:.6f} | "
                f"notional={plan.suggested_notional_usd:.6f} | "
                f"margin={plan.required_margin_usd:.6f} | "
                f"capped_by={plan.capped_by} | advisory_only=true"
            )

        if self.system_log and best_candidate.score_breakdown is not None:
            breakdown = best_candidate.score_breakdown
            self.system_log.info(
                "CANDIDATE_SELECTED | "
                f"symbol={best_symbol} | direction={best_direction} | "
                f"final_score={breakdown.final_score:.6f} | "
                f"rule_score={breakdown.rule_score:.6f} | "
                f"trend={breakdown.trend_alignment:.6f} | "
                f"volatility={breakdown.volatility_quality:.6f} | "
                f"location={breakdown.location_quality:.6f}"
            )

        if update_trade_governor:
            bucket = self._current_candle[best_symbol]["bucket"]
            self._last_trade_info[best_symbol] = (
                bucket,
                best_direction,
            )

        intent_context = copy_experiment_context(
            best_candidate.experiment_context
        )
        if (
            intent_context is not None
            and paper_route is not None
            and paper_route.is_model_selected
        ):
            intent_context["selection_model_version"] = paper_route.model_id
            intent_context["paper_policy"]["selection_authority"] = (
                paper_route.selection_authority
            )
            intent_context["paper_policy"]["allocation_id"] = (
                paper_route.allocation_id
            )
            intent_context["paper_policy"]["risk_multiplier"] = 1.0
            validate_experiment_context(intent_context)

        return TradeIntent(
            symbol=best_symbol,
            direction=best_direction,
            pattern=best_candidate.pattern,
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
            structure_fingerprint=best_candidate.structure_fingerprint,
            advisory_risk_plan=(
                best_candidate.risk_plan.as_dict()
                if best_candidate.risk_plan is not None
                else None
            ),
            candidate_observation_id=best_candidate.observation_id,
            decision_batch_id=best_candidate.decision_batch_id,
            market_event_id=best_candidate.market_event_id,
            strategy_version=best_candidate.strategy_version,
            strategy_variant_id=best_candidate.strategy_variant_id,
            model_version=(
                paper_route.model_id
                if paper_route is not None and paper_route.is_model_selected
                else best_candidate.model_version
            ),
            experiment_context=intent_context,
            selection_authority=(
                paper_route.selection_authority
                if paper_route is not None
                else "RULES"
            ),
            paper_canary_model_id=(
                paper_route.model_id
                if paper_route is not None and paper_route.is_model_selected
                else None
            ),
            paper_risk_multiplier=(
                paper_route.risk_multiplier
                if paper_route is not None
                else 1.0
            ),
            paper_allocation_id=(
                paper_route.allocation_id
                if paper_route is not None and paper_route.is_canary
                else None
            ),
        )
