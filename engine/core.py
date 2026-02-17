# ==========================================================
# ENGINE CORE
# SINGLE AUTHORITY RULE:
# Only TradingEngine may:
# - disable trading
# - call emergency exit
# - change engine_state
# - escalate to critical
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
)

from risk.risk import RiskManager
from safety.safety import SafetyManager
from state.state import StateManager
from strategy.strategy import Strategy
from execution.exceptions import OperationalExchangeError
from utils.logger import system_logger, trade_logger, risk_logger, daily_logger
from utils.telegram_notifier import send_info, send_critical, start_operator_listener
from engine.events import EngineEvent
from engine.market_state import MarketState
from engine.daily_lifecycle import DailyLifecycle
from engine.intent_lifecycle import IntentLifecycle
from engine.entry_lifecycle import EntryLifecycle
from engine.position_lifecycle import PositionLifecycle
from engine.reconciliation import ReconciliationLifecycle
from engine.emergency import EmergencyHandler
from engine.universe import UniverseManager
from engine.throttle import LogThrottle

RUNNING = "RUNNING"
TRADING_DISABLED = "TRADING_DISABLED"
OPERATOR_COMMAND_FILE = "operator_command.json"

# ==========================================================
# Trading Engine
# ==========================================================

class TradingEngine:
    """
    Trading Engine — Orchestrator Only
    """

    DAILY_HALT = "DAILY_HALT"
    RISK_HALT = "RISK_HALT"
    INVARIANT_HALT = "INVARIANT_HALT"
    OPERATIONAL_HALT = "OPERATIONAL_HALT"
    MANUAL_HALT = "MANUAL_HALT"
    FATAL_HALT = "FATAL_HALT"

    # ------------------------------------------------------
    # Initialization
    # ------------------------------------------------------

    def __init__(self, exchange):

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
        self.strategy = Strategy()
        self.risk = RiskManager(
            NOTIONAL_TARGET=MAX_NOTIONAL_USD,
            NOTIONAL_TOLERANCE_PCT=NOTIONAL_TOLERANCE_PCT,
            RISK_PER_TRADE_USD=RISK_PER_TRADE_USD,
            RISK_TOLERANCE_PCT=RISK_TOLERANCE_PCT,
        )
        self.safety = SafetyManager()

        # Loggers
        self.system_log = system_logger()
        self.trade_log = trade_logger()
        self.risk_log = risk_logger()
        self.daily_log = daily_logger()

        # Market data
        self.market_state = MarketState()

        # Throttle
        self.throttle = LogThrottle(self.system_log)

        # Universe
        self.universe = UniverseManager(self.strategy, self.system_log)

        # Emergency
        self.emergency = EmergencyHandler(
            exchange=self.exchange,
            state=self.state,
            safety=self.safety,
            system_log=self.system_log,
        )

        # Entry lifecycle
        self.entry_lifecycle = EntryLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            safety=self.safety,
            emergency=self.emergency,
            system_log=self.system_log,
            trade_log=self.trade_log,
            throttle=self.throttle,
        )

        # Lifecycles
        self.daily_lifecycle = DailyLifecycle(
            state=self.state,
            risk=self.risk,
            exchange=self.exchange,
            safety=self.safety,
            system_log=self.system_log,
            daily_log=self.daily_log,
        )

        self.intent_lifecycle = IntentLifecycle(
            state=self.state,
            strategy=self.strategy,
            safety=self.safety,
            universe=self.universe,
            system_log=self.system_log,
            throttle=self.throttle,
            entry_lifecycle=self.entry_lifecycle,
        )

        self.position_lifecycle = PositionLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            safety=self.safety,
            emergency=self.emergency,
            system_log=self.system_log,
            trade_log=self.trade_log,
        )

        self.reconciliation = ReconciliationLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            safety=self.safety,
            system_log=self.system_log,
        )

        self.system_log.info("ENGINE_INITIALIZED")

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
            self.system_log.critical(
                f"STATE_LOAD_FAILED | {e}"
            )
            self._handle_event(
                EngineEvent(
                    severity="CRITICAL",
                    category="INFRA",
                    money_at_risk=False,
                    requires_flatten=False,
                    requires_disable=True,
                    retryable=False,
                    reason="STATE_LOAD_FAILED",
                )
            )
            return

        try:
            self.exchange.connect()
        except Exception as e:
            self.system_log.critical(
                f"EXCHANGE_CONNECT_FAILED | error={e}"
            )
            send_critical(
                "EXCHANGE CONNECT FAILED",
                f"{e}\n\nEngine did not start."
            )
            self.safety.halt("EXCHANGE_CONNECT_FAILED")
            return

        engine_state = self.state.get_state().get("engine_state")

        try:
            if engine_state == self.DAILY_HALT:
                result = self.reconciliation.run(
                    reason="DAILY_HALT_RESUME"
                )
            else:
                result = self.reconciliation.run(
                    reason="ENGINE_STARTUP"
                )

            if isinstance(result, EngineEvent):
                self._handle_event(result)
        except Exception as e:
            self.system_log.critical(
                f"RECONCILIATION_STARTUP_FAILED | {e}"
            )
            self._handle_event(
                EngineEvent(
                    severity="CRITICAL",
                    category="INFRA",
                    money_at_risk=False,
                    requires_flatten=False,
                    requires_disable=True,
                    retryable=True,
                    reason="RECONCILIATION_STARTUP_FAILED",
                )
            )

        self.universe.load()

        try:
            self.exchange.enforce_leverage_for_universe(
                self.universe.symbols
            )
            self.system_log.info(
                f"LEVERAGE_ENFORCED | leverage={LEVERAGE}"
            )
        except Exception as e:
            self.system_log.critical(
                f"LEVERAGE_ENFORCEMENT_FAILED | {e}"
            )
            send_critical(
                "LEVERAGE ENFORCEMENT FAILED",
                f"{e}\n\nEngine halted."
            )
            self.safety.halt("LEVERAGE_ENFORCEMENT_FAILED")
            return

        try:
            self.universe.warmup(self.exchange)
        except Exception as e:
            self.system_log.critical(
                f"UNIVERSE_WARMUP_FAILED | {e}"
            )
            self._handle_event(
                EngineEvent(
                    severity="CRITICAL",
                    category="INFRA",
                    money_at_risk=False,
                    requires_flatten=False,
                    requires_disable=True,
                    retryable=False,
                    reason="UNIVERSE_WARMUP_FAILED",
                )
            )

        send_info(
            "ENGINE STARTED",
            f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
            "Status: RUNNING"
        )

        self._main_loop()

    # --------------------------------------------------
    # Main Loop
    # --------------------------------------------------

    def _main_loop(self):

        try:
            last_persist_ms = 0

            for tick in self.exchange.price_stream():

                # ------------------------------------------
                # Operator Command Check
                # ------------------------------------------
                self._process_operator_command()

                if not self.safety.is_safe():
                    self._handle_event(
                        EngineEvent(
                            severity="CRITICAL",
                            category="INFRA",
                            money_at_risk=self.state.get_open_position() is not None,
                            requires_flatten=False,
                            requires_disable=True,
                            retryable=False,
                            reason="SAFETY_TRIGGERED",
                        )
                    )
                    continue

                self.market_state.update(
                    symbol=tick.symbol,
                    price=tick.price,
                    timestamp=tick.timestamp,
                )

                open_position = self.state.get_open_position()

                # --------------------------------------------------
                # MODE A — POSITION OPEN
                # --------------------------------------------------
                if open_position:

                    # Ignore irrelevant symbols
                    if tick.symbol != open_position["symbol"]:
                        continue

                    result = self.daily_lifecycle.handle(
                        timestamp=tick.timestamp
                    )
                    if isinstance(result, EngineEvent):
                        self._handle_event(result)
                        continue

                result = self.position_lifecycle.manage(
                    market_state=self.market_state
                )

                if isinstance(result, EngineEvent):
                    self._handle_event(result)
                    continue

                continue

                # --------------------------------------------------
                # MODE B — NO POSITION
                # --------------------------------------------------

                result = self.daily_lifecycle.handle(
                    timestamp=tick.timestamp
                )
                if isinstance(result, EngineEvent):
                    self._handle_event(result)
                    continue

                self.strategy.on_price(
                    symbol=tick.symbol,
                    price=tick.price,
                    timestamp=tick.timestamp,
                )

                self.intent_lifecycle.observe(
                    market_state=self.market_state
                )

                intent = self.intent_lifecycle.accepted_intent

                result = self.entry_lifecycle.maybe_execute(
                    intent=intent,
                    market_state=self.market_state,
                )

                if isinstance(result, EngineEvent):
                    self._handle_event(result)
                elif result:
                    self.intent_lifecycle.clear_accepted_intent()

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
                        self.system_log.critical(
                            f"STATE_SAVE_FAILED | {e}"
                        )
                        self._handle_event(
                            EngineEvent(
                                severity="CRITICAL",
                                category="INFRA",
                                money_at_risk=self.state.get_open_position() is not None,
                                requires_flatten=False,
                                requires_disable=True,
                                retryable=True,
                                reason="STATE_SAVE_FAILED",
                            )
                        )
                        continue

        except OperationalExchangeError as e:
            self._handle_event(
                EngineEvent(
                    severity="CRITICAL",
                    category="INFRA",
                    money_at_risk=self.state.get_open_position() is not None,
                    requires_flatten=False,
                    requires_disable=True,
                    retryable=True,
                    reason="OPERATIONAL_EXCHANGE_ERROR",
                )
            )

            self.system_log.critical("TRADING_DISABLED | continuing monitoring")

        except StopIteration:
            self.system_log.info("MARKET_DATA_EXHAUSTED")
            self.safety.halt("MARKET_DATA_EXHAUSTED")

        except Exception as e:
            self.system_log.critical(
                f"UNEXPECTED_ENGINE_ERROR | {e}"
            )
            self._handle_event(
                EngineEvent(
                    severity="CRITICAL",
                    category="INFRA",
                    money_at_risk=self.state.get_open_position() is not None,
                    requires_flatten=False,
                    requires_disable=True,
                    retryable=False,
                    reason="UNEXPECTED_ENGINE_ERROR",
                )
            )
            self.system_log.critical("TRADING_DISABLED | monitoring continues")

    def _process_operator_command(self):

        if not os.path.exists(OPERATOR_COMMAND_FILE):
            return

        try:
            with open(OPERATOR_COMMAND_FILE, "r") as f:
                cmd = json.load(f)

            action = cmd.get("action")

            if action == "ENABLE_TRADING":
                self.state.set_engine_state(RUNNING, reason="OPERATOR_ENABLE")
                self.state.save()
                self.system_log.info("OPERATOR_COMMAND | ENABLE_TRADING")

            elif action == "DISABLE_TRADING":
                self.state.disable_trading("OPERATOR_DISABLE")
                self.state.save()
                self.system_log.info("OPERATOR_COMMAND | DISABLE_TRADING")

            elif action == "STATUS":
                self.system_log.info(
                    f"OPERATOR_STATUS | state={self.state.get_state().get('engine_state')}"
                )

        except Exception as e:
            self.system_log.critical(
                f"OPERATOR_COMMAND_ERROR | {e}"
            )

        # Remove command after processing
        try:
            os.remove(OPERATOR_COMMAND_FILE)
        except Exception:
            pass

    def _handle_operator_command(self, text: str):

        if text == "/enable":
            self.state.set_engine_state("RUNNING", reason="OPERATOR_ENABLE")
            self.state.save()
            self.system_log.info("OPERATOR_ENABLE")
            send_info("TRADING ENABLED", "Operator command accepted.")

        elif text == "/disable":
            self.state.disable_trading("OPERATOR_DISABLE")
            self.state.save()
            self.system_log.info("OPERATOR_DISABLE")
            send_info("TRADING DISABLED", "Operator command accepted.")

        elif text == "/status":
            state = self.state.get_state().get("engine_state")
            send_info("ENGINE STATUS", f"State: {state}")

        elif text == "/pnl":
            from pnl_report import generate_daily_pnl_summary
            summary = generate_daily_pnl_summary()
            send_info("DAILY PNL REPORT", summary)

     # --------------------------------------------------
     # Event Authority Handler (Blueprint v1)
     # --------------------------------------------------

    def _handle_event(self, event: EngineEvent):
        """
        Centralized authority decision handler.
        Only core may:
        - disable trading
        - call emergency flatten
        - escalate alerts
        """

        if event is None:
            return

        # --------------------------------------------------
        # Flatten if required
        # --------------------------------------------------
        if event.requires_flatten:
            self.system_log.critical(
                f"ENGINE_EVENT_FLATTEN | reason={event.reason}"
            )
            try:
                emergency_result = self.emergency.execute(event.reason)

                if isinstance(emergency_result, EngineEvent):
                    self._handle_event(emergency_result)

            except Exception as e:
                self.system_log.critical(
                    f"EMERGENCY_EXECUTION_FAILED | {e}"
                )

        # --------------------------------------------------
        # Disable trading if required
        # --------------------------------------------------
        if event.requires_disable:
            self.system_log.critical(
                f"ENGINE_EVENT_DISABLE | reason={event.reason}"
            )
            self.state.disable_trading(event.reason)
            self.state.save()

        # --------------------------------------------------
        # Alert escalation
        # --------------------------------------------------
        if event.severity == "CRITICAL":
            send_critical(
                "ENGINE EVENT",
                f"Category: {event.category}\nReason: {event.reason}"
            )
        elif event.severity == "WARNING":
            send_info(
                "ENGINE WARNING",
                f"Category: {event.category}\nReason: {event.reason}"
            )

