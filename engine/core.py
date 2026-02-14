# ==========================================================
# ENGINE CORE (Orchestrator Only)
# ==========================================================

import time
from datetime import datetime, timezone

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
from utils.telegram_notifier import send_info, send_critical

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

        try:
            self.state.load()
        except Exception as e:
            self.system_log.critical(
                f"STATE_LOAD_FAILED | {e}"
            )
            self.safety.halt("STATE_LOAD_FAILED")
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
                self.reconciliation.run(reason="DAILY_HALT_RESUME")
            else:
                self.reconciliation.run(reason="ENGINE_STARTUP")
        except Exception as e:
            self.system_log.critical(
                f"RECONCILIATION_STARTUP_FAILED | {e}"
            )
            self.state.set_engine_state(
                engine_state=self.OPERATIONAL_HALT,
                reason="RECONCILIATION_STARTUP_FAILED",
            )
            self.state.save()
            self.safety.halt("RECONCILIATION_STARTUP_FAILED")
            return

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
            self.state.set_engine_state(
                engine_state=self.OPERATIONAL_HALT,
                reason="UNIVERSE_WARMUP_FAILED",
            )
            self.state.save()
            self.safety.halt("UNIVERSE_WARMUP_FAILED")
            return

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
            for tick in self.exchange.price_stream():

                if not self.safety.is_safe():
                    return

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

                    if not self.daily_lifecycle.handle(
                        timestamp=tick.timestamp
                    ):
                        return

                    self.position_lifecycle.manage(
                        market_state=self.market_state
                    )

                    continue

                # --------------------------------------------------
                # MODE B — NO POSITION
                # --------------------------------------------------

                if not self.daily_lifecycle.handle(
                    timestamp=tick.timestamp
                ):
                    return

                self.strategy.on_price(
                    symbol=tick.symbol,
                    price=tick.price,
                    timestamp=tick.timestamp,
                )

                self.intent_lifecycle.observe(
                    market_state=self.market_state
                )

                intent = self.intent_lifecycle.accepted_intent

                executed = self.entry_lifecycle.maybe_execute(
                    intent=intent,
                    market_state=self.market_state,
                )

                if executed:
                    self.intent_lifecycle.clear_accepted_intent()

                self.state.heartbeat(
                    int(datetime.now(timezone.utc).timestamp() * 1000)
                )

                try:
                    self.state.save()
                except Exception as e:
                    self.system_log.critical(
                        f"STATE_SAVE_FAILED | {e}"
                    )
                    self.safety.halt("STATE_SAVE_FAILED")
                    return

        except OperationalExchangeError as e:
            self.system_log.critical(
                f"OPERATIONAL_EXCHANGE_ERROR | {e}"
            )
            send_critical(
                "OPERATIONAL EXCHANGE ERROR",
                f"{e}\n\nEngine halted."
            )
            self.safety.halt("OPERATIONAL_EXCHANGE_ERROR")

        except StopIteration:
            self.system_log.info("MARKET_DATA_EXHAUSTED")
            self.safety.halt("MARKET_DATA_EXHAUSTED")

        except Exception as e:
            self.system_log.critical(
                f"UNEXPECTED_ENGINE_ERROR | {e}"
            )
            self.state.set_engine_state(
                engine_state=self.OPERATIONAL_HALT,
                reason="UNEXPECTED_ENGINE_ERROR",
            )
            self.state.save()
            send_critical(
                "UNEXPECTED ENGINE ERROR",
                f"{e}\n\nEngine halted."
            )
            self.safety.halt("UNEXPECTED_ENGINE_ERROR")
