# ==========================================================
# ENGINE CORE
# TradingEngine
# Orchestrates lifecycle components.
# Owns trading enable/disable state.
# ==========================================================

import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from config import (
    MAX_NOTIONAL_USD,
    LEVERAGE,
    NOTIONAL_TOLERANCE_PCT,
    RISK_PER_TRADE_USD,
    RISK_TOLERANCE_PCT,
    SHADOW_MODE,
)
from execution.exceptions import MarketStateError
from risk.risk import RiskManager
from state.state import StateManager
from strategy.strategy import Strategy
from execution.exceptions import OperationalExchangeError
from utils.telegram_notifier import send_info, send_critical, start_operator_listener, send_warning
from engine.market_state import MarketState
from engine.daily_lifecycle import DailyLifecycle
from engine.intent_lifecycle import IntentLifecycle
from engine.entry_lifecycle import EntryLifecycle
from engine.position_lifecycle import PositionLifecycle
from engine.reconciliation import ReconciliationLifecycle
from engine.emergency import EmergencyHandler
from engine.universe import UniverseManager
from engine.throttle import LogThrottle
from pnl_report import generate_daily_pnl_summary

RUNNING = "RUNNING"
TRADING_DISABLED = "TRADING_DISABLED"
OPERATOR_COMMAND_FILE = "operator_command.json"

# ==========================================================
# Trading Engine
# ==========================================================


class TradingEngine:
    """Trading engine orchestrator."""

    # ------------------------------------------------------
    # Initialization
    # ------------------------------------------------------

    def __init__(self, exchange, system_log, trade_log):

        # --- Adapter contract sanity ---
        required_methods = [
            "connect",
            "disconnect",
            "price_stream",
            "get_position",
            "get_realized_pnl",
            "place_entry",
            "place_initial_sl",
            "update_sl",
            "cancel_pending_entries",
            "emergency_exit",
        ]
        for m in required_methods:
            assert hasattr(exchange, m), f"ADAPTER_MISSING_METHOD:{m}"

        self.exchange = exchange

        # Core components
        self.state = StateManager()
        self.strategy = Strategy(system_log=system_log)
        self.risk = RiskManager(
            NOTIONAL_TARGET=MAX_NOTIONAL_USD,
            NOTIONAL_TOLERANCE_PCT=NOTIONAL_TOLERANCE_PCT,
            RISK_PER_TRADE_USD=RISK_PER_TRADE_USD,
            RISK_TOLERANCE_PCT=RISK_TOLERANCE_PCT,
        )

        # Loggers
        self.system_log = system_log
        self.trade_log = trade_log

        # Market data
        self.market_state = MarketState()

        # Throttle
        self.throttle = LogThrottle(self.system_log)

        # Emergency
        self.emergency = EmergencyHandler(
            exchange=self.exchange,
            state=self.state,
            system_log=self.system_log,
            trade_log=self.trade_log,
        )

        # Universe
        self.universe = UniverseManager(
            strategy=self.strategy,
            system_log=self.system_log,
        )

        # Daily Lifecycle
        self.daily_lifecycle = DailyLifecycle(
            state=self.state,
            risk=self.risk,
            exchange=self.exchange,
            system_log=self.system_log,
        )

        # Entry lifecycle
        self.entry_lifecycle = EntryLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            emergency=self.emergency,
            system_log=self.system_log,
            trade_log=self.trade_log,
            throttle=self.throttle,
        )

        # Intent Lifecycle
        self.intent_lifecycle = IntentLifecycle(
            state=self.state,
            strategy=self.strategy,
            universe=self.universe,
            throttle=self.throttle,
            entry_lifecycle=self.entry_lifecycle,
            system_log=self.system_log,
        )

        # Reconciliation Lifecycle
        self.reconciliation = ReconciliationLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            universe=self.universe,
            system_log=self.system_log,
            trade_log=self.trade_log,
        )

        # Position Lifecycle
        self.position_lifecycle = PositionLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            emergency=self.emergency,
            reconciliation=self.reconciliation,
            universe=self.universe,
            system_log=self.system_log,
            trade_log=self.trade_log,
        )

        self.system_log.info("ENGINE_INITIALIZED")
        # ------------------------------------------
        # Startup Tick Barrier
        # ------------------------------------------
        self._symbols_seen = set()
        self._strategy_activated = False
        self._shadow_mode_logged = False
    # --------------------------------------------------
    # Start
    # --------------------------------------------------

    def start(self):

        # ------------------------------------------
        # Start Operator Telegram Listener
        # ------------------------------------------
        start_operator_listener(self._handle_operator_command)

        try:
            self.state.load()
        except Exception as e:
            self.system_log.error(
                f"STATE_LOAD_FAILED | {e}"
            )
            self._disable_trading(reason="STATE_LOAD_FAILED")
            self.state.save()
            return

        # --------------------------------------------------
        # Startup Disabled-State Notification
        # --------------------------------------------------
        engine_state = self.state.get_state().get("engine_state")
        halt_reason = self.state.get_state().get("engine_halt_reason")

        if engine_state == TRADING_DISABLED:
            send_warning(
                "ENGINE STARTED — TRADING DISABLED",
                f"Reason: {halt_reason}"
            )

        # Connecting to Exchange
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                self.system_log.info(
                    f"EXCHANGE_CONNECT_ATTEMPT | attempt={attempt}"
                )
                self.exchange.connect()
                self.system_log.info(
                    "EXCHANGE_CONNECT_SUCCESS"
                )
                break
            except Exception as e:
                self.system_log.error(
                    f"EXCHANGE_CONNECT_FAILED | "
                    f"attempt={attempt} | error={e}"
                )
                if attempt < max_attempts:
                    time.sleep(attempt)
                else:
                    send_critical(
                        "EXCHANGE CONNECT FAILED",
                        f"{e}\n\nTrading disabled."
                    )
                    self._disable_trading(
                        reason="EXCHANGE_CONNECT_FAILED"
                    )
                    self.state.save()
                    return

        try:
            result = self.reconciliation.run(
                reason="ENGINE_STARTUP"
            )

        except Exception as e:
            self.system_log.error(
                f"RECONCILIATION_STARTUP_FAILED | {e}"
            )
            self._disable_trading(reason="RECONCILIATION_STARTUP_FAILED")
            self.state.save()
            return

        self.universe.load()

        # --------------------------------------------------
        # Force Governance Refresh on Startup
        # --------------------------------------------------
        self.universe.maybe_reload(
            exchange=self.exchange,
            state=self.state,
            force=True
        )

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                self.system_log.info(
                    f"UNIVERSE_WARMUP_ATTEMPT | attempt={attempt}"
                )
                self.universe.warmup(self.exchange)
                self.system_log.info(
                    "UNIVERSE_WARMUP_SUCCESS"
                )
                break
            except Exception as e:
                self.system_log.error(
                    f"UNIVERSE_WARMUP_FAILED | "
                    f"attempt={attempt} | error={e}"
                )
                if attempt < max_attempts:
                    time.sleep(attempt)
                else:
                    self._disable_trading(
                        reason="UNIVERSE_WARMUP_FAILED"
                    )
                    self.state.save()
                    return

        actual_engine_state = self.state.get_state().get("engine_state")
        actual_halt_reason = self.state.get_state().get(
            "engine_halt_reason"
        )

        if SHADOW_MODE:
            runtime_status = (
                "SHADOW MODE — ORDERS BLOCKED\n"
                f"Persisted entry state: {actual_engine_state}"
            )
        else:
            runtime_status = f"Status: {actual_engine_state}"

        if actual_halt_reason:
            runtime_status += f"\nReason: {actual_halt_reason}"

        send_info(
            "ENGINE STARTED",
            f"UTC: {datetime.now(timezone.utc).strftime(
                '%Y-%m-%d %H:%M:%S')}\n"
            f"{runtime_status}"
        )

        self._main_loop()

    # --------------------------------------------------
    # Main Loop
    # --------------------------------------------------
    def _main_loop(self):

        last_persist_ms = 0

        # --- Supervisor loop: prevents engine exit on boundary errors ---
        while True:
            try:

                stream = self.exchange.price_stream()

                for tick in stream:

                    # ------------------------------------------
                    # Operator Command Check
                    # ------------------------------------------
                    self._process_operator_command()

                    # ------------------------------------------
                    # Update Market State
                    # ------------------------------------------
                    self.market_state.update(
                        symbol=tick.symbol,
                        price=tick.price,
                        timestamp=tick.timestamp,
                    )

                    # ------------------------------------------
                    # Always feed market data into the strategy.
                    # Entry permission and position exposure must not
                    # create gaps in candle history or simulations.
                    # ------------------------------------------
                    self.strategy.on_price(
                        symbol=tick.symbol,
                        price=tick.price,
                        timestamp=tick.timestamp,
                    )

                    # --------------------------------------------------
                    # POSITION MANAGEMENT HAS PRIORITY OVER ENTRY STATE
                    # --------------------------------------------------
                    # TRADING_DISABLED means "no new entries". It must
                    # never stop supervision of capital already exposed.
                    open_position = self.state.get_open_position()

                    # ==================================================
                    # MODE A — POSITION OPEN
                    # ==================================================
                    if open_position:

                        # Ignore irrelevant symbols; the exchange position
                        # is managed from ticks for its own symbol.
                        if tick.symbol != open_position["symbol"]:
                            continue

                        # Position lifecycle must run before any entry-state
                        # or daily-entry guard can block the loop.
                        self.position_lifecycle.manage(
                            market_state=self.market_state
                        )

                        # Daily lifecycle is evaluated after position
                        # supervision. A daily halt may block future entries,
                        # but it must not prevent management of this position.
                        self.daily_lifecycle.handle(
                            timestamp=tick.timestamp
                        )

                        # Heartbeat + persistence
                        self.state.heartbeat(
                            int(datetime.now(timezone.utc).timestamp() * 1000)
                        )

                        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

                        if now_ms - last_persist_ms > 5000:
                            try:
                                self.state.save()
                                last_persist_ms = now_ms
                            except Exception as e:
                                self.system_log.error(
                                    f"STATE_SAVE_FAILED | {e}"
                                )
                                self._disable_trading(reason="STATE_SAVE_FAILED")

                        continue

                    # --------------------------------------------------
                    # ENTRY GUARD — APPLIES ONLY WHILE FLAT
                    # --------------------------------------------------
                    engine_state = self.state.get_state().get("engine_state")
                    if engine_state != RUNNING and not SHADOW_MODE:
                        continue

                    # --------------------------------------------------
                    # STARTUP TICK BARRIER
                    # Delay new-entry strategy activation until enough
                    # universe symbols have produced a live tick.
                    # --------------------------------------------------
                    if not self._strategy_activated:

                        if tick.symbol in self.universe.symbols:
                            self._symbols_seen.add(tick.symbol)

                        if len(self._symbols_seen) >= int(0.9 * len(self.universe.symbols)):
                            self._strategy_activated = True
                            self.system_log.info(
                                "STARTUP_TICK_BARRIER_PASSED | "
                                f"symbols={len(self._symbols_seen)}"
                            )
                        else:
                            # Still collecting first ticks
                            continue

                    # ==================================================
                    # MODE B — NO POSITION
                    # ==================================================

                    # Daily lifecycle
                    result = self.daily_lifecycle.handle(
                        timestamp=tick.timestamp
                    )
                    if result is False:
                        continue

                    # Strategy market data was already updated above.
                    # Observe intent only when flat and entries are enabled.
                    self.intent_lifecycle.observe(
                        market_state=self.market_state
                    )

                    intent = self.intent_lifecycle.accepted_intent

                    # Shadow mode deliberately permits strategy evaluation and
                    # dataset generation while blocking every order submission.
                    if SHADOW_MODE:
                        if not self._shadow_mode_logged:
                            self.system_log.warning(
                                "SHADOW_MODE_ACTIVE | order_submission=BLOCKED"
                            )
                            self._shadow_mode_logged = True

                        if intent is not None:
                            self.system_log.info(
                                "SHADOW_INTENT_BLOCKED | "
                                f"symbol={intent.symbol} | "
                                f"direction={intent.direction}"
                            )
                            self.intent_lifecycle.clear_accepted_intent()

                    else:
                        # Try execute entry only when shadow mode is disabled.
                        entry_attempted = intent is not None

                        self.entry_lifecycle.maybe_execute(
                            intent=intent,
                            market_state=self.market_state,
                        )

                        # Clear intent after ANY attempt (success or failure)
                        if entry_attempted:
                            self.intent_lifecycle.clear_accepted_intent()

                    # Heartbeat
                    self.state.heartbeat(
                        int(datetime.now(timezone.utc).timestamp() * 1000)
                    )

                    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

                    # Persist every 5000 ms instead of every tick
                    if now_ms - last_persist_ms > 5000:
                        try:
                            self.state.save()
                            last_persist_ms = now_ms
                        except Exception as e:
                            self.system_log.error(
                                f"STATE_SAVE_FAILED | {e}"
                            )
                            self._disable_trading(reason="STATE_SAVE_FAILED")
                            self.state.save()

                # --------------------------------------------------
                # If price stream ends cleanly (should not happen),
                # restart it without killing engine.
                # --------------------------------------------------
                self.system_log.error(
                    "PRICE_STREAM_STOPPED_UNEXPECTEDLY | restarting"
                )
                time.sleep(2)
                continue

            except MarketStateError as e:
                # Market-level rejection (non-infrastructure)
                self.system_log.info(
                    f"MARKET_STATE_REJECTION | reason={str(e)}"
                )
                time.sleep(1)
                continue

            except OperationalExchangeError as e:
                error_str = str(e)
                self.system_log.error(
                    f"EXCHANGE_OPERATIONAL_FAILURE | error={error_str}"
                )

                # WebSocket failures are recoverable
                if "WS_PRICE_STREAM_FAILED" in error_str:
                    time.sleep(2)
                    continue
                # Other operational failures → disable trading
                self._disable_trading(
                    reason="EXCHANGE_OPERATIONAL_FAILURE"
                )
                self.state.save()
                time.sleep(2)
                continue

            except Exception as e:
                error_str = str(e)
                self.system_log.error(f"ENGINE_EXCEPTION | error={error_str}")
                self._disable_trading(reason=error_str)
                self.state.save()
                time.sleep(2)
                continue

    # ==========================================================
    # Trading Disable Notification
    # ==========================================================
    def _disable_trading(self, *, reason: str):

        if not reason:
            raise ValueError("DISABLE_TRADING_REQUIRES_REASON")

        current_state = self.state.get_state().get("engine_state")

        if current_state == TRADING_DISABLED:
            return
        timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.system_log.error(
            f"TRADING_DISABLED | "
            f"reason={reason} | "
            f"utc={timestamp}"
        )

        self.state.set_engine_state(TRADING_DISABLED, reason)
        self.state.save()

        send_critical("TRADING DISABLED", f"Reason: {reason}")

    #----------------------------------
    # Operator Commands
    #----------------------------------
    def _process_operator_command(self):

        if not os.path.exists(OPERATOR_COMMAND_FILE):
            return

        try:
            with open(OPERATOR_COMMAND_FILE, "r") as f:
                cmd = json.load(f)

            action = cmd.get("action")

            if action == "ENABLE_TRADING":
                # Keep new entries disabled until exchange/state truth has
                # reconciled successfully. Reconciliation is allowed to run
                # while the engine is TRADING_DISABLED.
                self.reconciliation.run(
                    reason="OPERATOR_RESUME"
                )
                self.state.set_engine_state(RUNNING, reason=None)
                self.state.save()
                self.system_log.info("OPERATOR_COMMAND | ENABLE_TRADING")

            elif action == "DISABLE_TRADING":
                self._disable_trading(reason="OPERATOR_DISABLE")
                self.state.save()
                self.system_log.info("OPERATOR_COMMAND | DISABLE_TRADING")

            elif action == "STATUS":
                self.system_log.info(
                    f"OPERATOR_STATUS | state={self.state.get_state().get('engine_state')}"
                )

        except Exception as e:
            self.system_log.error(
                f"OPERATOR_COMMAND_ERROR | {e}"
            )

        # Remove command after processing
        try:
            os.remove(OPERATOR_COMMAND_FILE)
        except Exception:
            pass

    def _handle_operator_command(self, text: str):

        if text == "/enable":
            # Reconcile while entries remain disabled. Only a successful
            # reconciliation may transition the engine back to RUNNING.
            self.reconciliation.run(
                reason="OPERATOR_RESUME"
            )
            self.state.set_engine_state(RUNNING, reason=None)
            self.state.save()
            self.system_log.info("OPERATOR_ENABLE")
            send_info("TRADING ENABLED", "Operator command accepted.")

        elif text == "/disable":
            self._disable_trading(reason="OPERATOR_DISABLE")
            self.state.save()
            self.system_log.info("OPERATOR_DISABLE")
            send_info("TRADING DISABLED", "Operator command accepted.")

        elif text == "/status":
            state = self.state.get_state().get("engine_state")
            send_info("ENGINE STATUS", f"State: {state}")

        elif text.startswith("/pnl"):
            parts = text.split()
            if len(parts) == 1:
                summary = generate_daily_pnl_summary()
            else:
                summary = generate_daily_pnl_summary(parts[1])
            send_info(
                "DAILY PNL REPORT",
                summary
            )
