# ==========================================================
# ENGINE
# ==========================================================

import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Optional

from strategy.strategy import Strategy
from strategy.trade_intent import TradeIntent
from risk.risk import RiskManager
from safety.safety import SafetyManager
from state.state import StateManager
from execution.exceptions import OperationalExchangeError
from utils.logger import system_logger, trade_logger, risk_logger, daily_logger
from utils.telegram_notifier import send_message, edit_message
from config import (
    SIM_START_BALANCE,
    MAX_NOTIONAL_USD,
    LEVERAGE,
    NOTIONAL_TOLERANCE_PCT,
    RISK_PER_TRADE_USD,
    RISK_TOLERANCE_PCT,
)

# ==========================================================
# Market Data State
# ==========================================================

class MarketState:
    """
    Authoritative in-memory market data cache.

    Responsibilities:
    - Store last known price per symbol
    - Store last known timestamp per symbol

    NON-responsibilities:
    - No trading logic
    - No strategy logic
    - No risk logic
    """

    def __init__(self):
        self.last_price: Dict[str, float] = {}
        self.last_timestamp: Dict[str, int] = {}

    def update(self, *, symbol: str, price: float, timestamp: int) -> None:
        self.last_price[symbol] = price
        self.last_timestamp[symbol] = timestamp

    def has_price(self, symbol: str) -> bool:
        return symbol in self.last_price

    def get_price(self, symbol: str) -> float:
        return self.last_price[symbol]

    def get_timestamp(self, symbol: str) -> int:
        return self.last_timestamp[symbol]


# ==========================================================
# EntryPlan
# ==========================================================

@dataclass
class EntryPlan:
    symbol: str
    direction: str
    entry_price: float
    quantity: float
    initial_sl: float
    risk_r: float


# --------------------------------------------------
# Universe
# --------------------------------------------------

UNIVERSE_SNAPSHOT_FILE = "universe_snapshot.json"
EXPECTED_UNIVERSE_SIZE = 15

# --------------------------------------------------
# TradeIntent validation policy
# --------------------------------------------------

MAX_INTENT_AGE_SECONDS = 30
RUNNING = "RUNNING"

# ==========================================================
# TRADING ENGINE
# ==========================================================

class TradingEngine:
    """
    Canonical trading engine.
    """
    # ------------------------------------------------------
    # Halt Types
    # ------------------------------------------------------

    DAILY_HALT = "DAILY_HALT"
    RISK_HALT = "RISK_HALT"
    INVARIANT_HALT = "INVARIANT_HALT"
    OPERATIONAL_HALT = "OPERATIONAL_HALT"
    MANUAL_HALT = "MANUAL_HALT"
    FATAL_HALT = "FATAL_HALT"

    def _build_open_position(
        self,
        *,
        symbol: str,
        side: str,
        entry_price: float,
        qty: float,
        stop_loss: Optional[float],
    ) -> dict:
        """
        Build canonical open_position structure.
        This is the ONLY place where open_position dicts are created.
        """
        return {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "qty": qty,
            "stop_loss": stop_loss,
            "risk_usd": RISK_PER_TRADE_USD,
            "highest_profit_usd": 0.0,
        }

    # ------------------------------------------------------
    # Initialization
    # ------------------------------------------------------

    def __init__(self, exchange):
        self.exchange = exchange

        # --- Adapter contract sanity (UNCHANGED) ---
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

        # --------------------------------------------------
        # Core components
        # --------------------------------------------------

        self.state = StateManager()
        self.strategy = Strategy()
        self.risk = RiskManager(
            NOTIONAL_TARGET=MAX_NOTIONAL_USD,
            NOTIONAL_TOLERANCE_PCT=NOTIONAL_TOLERANCE_PCT,
            RISK_PER_TRADE_USD=RISK_PER_TRADE_USD,
            RISK_TOLERANCE_PCT=RISK_TOLERANCE_PCT,
        )
        self.safety = SafetyManager()

        # --------------------------------------------------
        # Market Data State
        # --------------------------------------------------

        self.market_state = MarketState()

        # --------------------------------------------------
        # Existing engine state
        # --------------------------------------------------

        self.exit_in_progress = False
        self._commitment_reached = False
        self._last_utc_day = None

        # --------------------------------------------------
        # Loggers
        # --------------------------------------------------

        self.system_log = system_logger()
        self.trade_log = trade_logger()
        self.risk_log = risk_logger()
        self.daily_log = daily_logger()

        # --------------------------------------------------
        # Universe
        # --------------------------------------------------

        self.universe_symbols = []
        self.universe_generated_at = None

        # --------------------------------------------------
        # Pending entry
        # --------------------------------------------------

        self._pending_entry_plan = None

        # --------------------------------------------------
        # Strategy intent
        # --------------------------------------------------
        self._latest_intent = None

        # --------------------------------------------------
        # Accepted intent
        # --------------------------------------------------
        self._accepted_intent = None

        # --------------------------------------------------
        # Entry lifecycle state
        # --------------------------------------------------
        self._entry_in_progress = False

        self.system_log.info("ENGINE_INITIALIZED")

    # --------------------------------------------------
    # Engine Start (Market Data lifecycle)
    # --------------------------------------------------

    def start(self):
        """
        Start engine execution.
        """
        self.state.load()

        try:
            self.exchange.connect()
        except Exception as e:
            self.system_log.critical(
                f"EXCHANGE_CONNECT_FAILED | error={e}"
            )
            send_message(
                "🔴 <b>EXCHANGE CONNECT FAILED</b>\n\n"
                f"Error: {e}\n\n"
                "Engine did not start."
            )
            self.safety.halt("EXCHANGE_CONNECT_FAILED")
            return

        # --- Reconciliation gate ---
        engine_state = self.state.get_state().get("engine_state")
        if engine_state == self.DAILY_HALT:
           self.reconcile(reason="DAILY_HALT_RESUME")
        else:
            self.reconcile(reason="ENGINE_STARTUP")

        # --- Load universe snapshot ---
        self.load_universe()

        # --- Strategy warmup ---
        self.warmup_strategy()

        # --- Bootstrap balance if empty ---
        if self.state.get_state().get("balance", 0.0) == 0.0:
            self.state.update_after_trade(
                balance=SIM_START_BALANCE,
                open_position=None,
                last_trade=None,
            )
            self.state.save()

        # --------------------------------------------------
        # TELEGRAM Notification — information only
        # --------------------------------------------------
        send_message(
            "🟢 <b>ENGINE STARTED</b>\n\n"
            f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
            "Status: RUNNING"
        )

        self._main_loop()

    # --------------------------------------------------
    # Market Data Loop (STEP 1)
    # --------------------------------------------------

    def _main_loop(self):
        """
        Consume price ticks from exchange adapter.
        OWNERSHIP:
        - tick ingestion
        - market_state update
        """
        try:
            for tick in self.exchange.price_stream():

                if not self.safety.is_safe():
                    return

                # Authoritative market data ingestion
                self.market_state.update(
                    symbol=tick.symbol,
                    price=tick.price,
                    timestamp=tick.timestamp,
                )

                 # --------------------------------------------------
                 # STEP 3 — Time & Daily Risk lifecycle
                 # --------------------------------------------------
                if not self._handle_time_and_daily_risk(
                    timestamp=tick.timestamp
                ):
                    return

                # --------------------------------------------------
                # STEP 2 — Strategy observation (READ-ONLY)
                # --------------------------------------------------
                self.strategy.on_price(
                    symbol=tick.symbol,
                    price=tick.price,
                    timestamp=tick.timestamp,
                )

                # --------------------------------------------------
                # STEP 2 — Intent proposal (NO validation, NO action)
                # --------------------------------------------------

                intent = None
                if (
                    self._accepted_intent is None
                    and self._engine_is_idle()
                    and not self._position_lifecycle_active()
                ):
                    intent = self.strategy.propose_intent()
                if intent is not None:
                    if not self.market_state.has_price(intent.symbol):
                        self.system_log.info(
                            f"INTENT_IGNORED | NO_MARKET_PRICE | symbol={intent.symbol}"
                        )
                        intent = None

                # Engine stores intent proposal only
                # (later lifecycles will decide what to do)
                self._latest_intent = intent

                # --------------------------------------------------
                # STEP 4 — TradeIntent validation & acceptance
                # --------------------------------------------------
                if (
                    self._latest_intent is not None
                    and self._accepted_intent is None
                    and self._engine_is_idle()
                ):
                    is_valid, reason = self.validate_intent(
                        self._latest_intent
                    )

                    if not is_valid:
                        self.system_log.info(
                            f"INTENT_REJECTED | "
                            f"symbol={self._latest_intent.symbol} "
                            f"direction={self._latest_intent.direction} "
                            f"reason={reason}"
                        )
                        self._latest_intent = None
                    else:
                        self.system_log.info(
                            f"INTENT_ACCEPTED | "
                            f"symbol={self._latest_intent.symbol} "
                            f"direction={self._latest_intent.direction} "
                            f"pattern={self._latest_intent.pattern}"
                        )

                        self._accepted_intent = self._latest_intent
                        self._latest_intent = None

                # STEP 2 ONLY:
                # Strategy may propose intent.
                # Engine stores it, but takes NO action.

                # --------------------------------------------------
                # STEP 5 — Entry lifecycle
                # --------------------------------------------------
                if (
                    self._accepted_intent is not None
                    and self._engine_is_idle()
                ):
                    self._handle_entry(
                        intent=self._accepted_intent
                    )

                # --------------------------------------------------
                # STEP 6 — Open position lifecycle
                # --------------------------------------------------
                if not self._entry_in_progress:
                    self._handle_open_position()

                # Heartbeat is engine substrate (already shared)
                self.state.heartbeat(
                    int(datetime.now(timezone.utc).timestamp() * 1000)
                )
                self.state.save()

        except OperationalExchangeError as e:
            self.system_log.critical(
                f"OPERATIONAL_EXCHANGE_ERROR | {e}"
            )
            send_message(
                "🔴 <b>OPERATIONAL EXCHANGE ERROR</b>\n\n"
                f"{e}\n\n"
                "Engine halted.\n"
                "Existing positions remain protected.\n"
                "Profit protection is frozen."
            )
            self.safety.halt("OPERATIONAL_EXCHANGE_ERROR")

        except StopIteration:
            self.system_log.info("MARKET_DATA_EXHAUSTED")
            self.safety.halt("MARKET_DATA_EXHAUSTED")

    # --------------------------------------------------
    # UTC Day & Daily Risk lifecycle
    # --------------------------------------------------
    def _handle_time_and_daily_risk(self, *, timestamp: int) -> bool:
        """
        Handle UTC day rollover and daily risk.
        Returns True if trading is allowed, False if halted.
        """

        utc_day = time.gmtime(timestamp // 1000).tm_yday

        if self._last_utc_day is None:
            self._last_utc_day = utc_day
        elif utc_day != self._last_utc_day:
            self.system_log.info(
                f"UTC_DAY_ROLLOVER | from={self._last_utc_day} to={utc_day}"
            )

            self._last_utc_day = utc_day

            # Safety first: cancel any pending entry orders
            self.exchange.cancel_pending_entries()

            # HARD reset daily risk state (explicit, no assumptions)
            self.state.reset_daily(utc_day)

            # Persist immediately — trading must not continue without this
            self.state.save()

        state_snapshot = self.state.get_state()

        daily_decision = self.risk.evaluate_daily(
            state_snapshot.get("daily_realized_pnl", 0.0),
            state_snapshot.get("daily_peak_pnl", 0.0),
        )

        self.state.update_daily_loss_floor(
            daily_decision.daily_loss_floor
        )

        if daily_decision.halt:
            self.system_log.critical(
                f"DAILY_HALT | reason={daily_decision.reason}"
            )

            # Persist DAILY HALT — must survive restarts
            self.state.set_engine_state(
                engine_state=self.DAILY_HALT,
                reason=daily_decision.reason,
            )
            self.state.save()

            send_message(
                "⛔ <b>DAILY HALT</b>\n\n"
                f"Reason: {daily_decision.reason}\n"
                f"Daily Loss Floor: "
                f"{daily_decision.daily_loss_floor} USD\n\n"
                f"UTC: {datetime.now(timezone.utc).date()}\n\n"
                "No new trades will be taken today."
            )

            self.safety.halt(daily_decision.reason)
            return False

        return True
    # -----------------------------------------------------
    # STEP 4 — Accept a new intent onlynwhen engine is idle
    # -----------------------------------------------------

    def _engine_is_idle(self) -> bool:
        """
        Engine is idle when it is safe to consider a new intent.
        """
        if self.state.get_open_position() is not None:
            return False
        if self._entry_in_progress:
            return False
        if not self.safety.is_safe():
            return False
        return True

    # ----------------------------------
    # Position Lifecycle guard
    # ----------------------------------
    def _position_lifecycle_active(self) -> bool:
        """
        True if engine is currently managing an open position.
        """
        return self.state.get_open_position() is not None

    # --------------------------------------------------
    # TradeIntent validation (STEP 4)
    # --------------------------------------------------

    def validate_intent(self, intent: TradeIntent):
        """
        Validate TradeIntent.
        Returns (is_valid: bool, reason: str)
        """

        # 1. Structural
        if not isinstance(intent, TradeIntent):
            return False, "INVALID_INTENT_TYPE"

        # 2. Freshness
        now = datetime.now(timezone.utc)
        age = (now - intent.generated_at).total_seconds()
        if age > MAX_INTENT_AGE_SECONDS:
            return False, "INTENT_STALE"

        # 3. Engine readiness
        engine_state = self.state.get_state().get("engine_state")
        if engine_state != RUNNING:
            return False, f"ENGINE_NOT_RUNNING | {engine_state}"

        if self.state.get_open_position() is not None:
            return False, "POSITION_ALREADY_OPEN"

        # 4. Universe membership
        if intent.symbol not in self.universe_symbols:
            return False, "SYMBOL_NOT_IN_UNIVERSE"

        # 5. Direction enablement
        if intent.direction == "SHORT":
            return False, "SHORT_DISABLED"

        if intent.direction != "LONG":
            return False, "INVALID_DIRECTION"

        # 6. Strategy warmup
        if not self.strategy.is_warmed_up():
            return False, "STRATEGY_NOT_WARMED"

        return True, "OK"

    # --------------------------------------------------
    # Entry lifecycle
    # --------------------------------------------------

    def _handle_entry(self, *, intent: TradeIntent):
        """
        Handle new entry from an accepted TradeIntent.
        """

        if self._entry_in_progress:
            return

        self._entry_in_progress = True

        if not self.market_state.has_price(intent.symbol):
            self.system_log.info(
                f"ENTRY_BLOCKED | NO_MARKET_PRICE | symbol={intent.symbol}"
            )
            self._entry_in_progress = False
            return

        entry_price = self.market_state.get_price(intent.symbol)

        # --- Build entry plan (risk math only) ---
        entry_plan = self.risk.build_entry_plan(
            direction=intent.direction,
            entry_price=entry_price,
        )

        # --- Margin guard ---
        required_margin = MAX_NOTIONAL_USD / LEVERAGE
        balance = self.state.get_state().get("balance", 0.0)
        if balance < required_margin:
            self.system_log.info(
                "ENTRY_BLOCKED | INSUFFICIENT_MARGIN"
            )
            self._entry_in_progress = False
            return

        # --- Place entry via adapter ---
        ack = self.exchange.place_entry(
            side=intent.direction,
            notional_usd=MAX_NOTIONAL_USD,
            price=entry_price,
        )

        if ack.filled_qty <= 0:
            self.system_log.info("ENTRY_NO_FILL")
            self._entry_in_progress = False
            return

        # --- Post-fill notional invariant ---
        executed_notional = ack.filled_qty * ack.avg_price
        max_allowed = MAX_NOTIONAL_USD * (
            1 + NOTIONAL_TOLERANCE_PCT / 100
        )
        assert executed_notional <= max_allowed, (
            "ENGINE_NOTIONAL_BREACH"
        )

        open_position = self._build_open_position(
            symbol=intent.symbol,
            side=intent.direction,
            entry_price=ack.avg_price,
            qty=ack.filled_qty,
            stop_loss=entry_plan.initial_sl,
        )

        # --- Place initial protective SL (MANDATORY) ---
        self.exchange.place_initial_sl(
            side=intent.direction,
            qty=ack.filled_qty,
            stop_price=entry_plan.initial_sl,
        )

        self.state.update_after_trade(
            balance=balance,
            open_position=open_position,
            last_trade=None,
        )

        self.state.save()

        self.system_log.info(
            f"POSITION_OPENED | "
            f"price={ack.avg_price} "
            f"qty={ack.filled_qty}"
        )

        # Entry complete — clear accepted intent
        self._accepted_intent = None
        self._entry_in_progress = False

    # --------------------------------------------------
    # Open position lifecycle
    # --------------------------------------------------

    def _handle_open_position(self):
        """
        Manage an existing open position.
        """

        state = self.state.get_state()
        open_position = state.get("open_position")
        if open_position is None:
            return

        assert "risk_usd" in open_position, "OPEN_POSITION_RISK_MISSING"

        symbol = open_position["symbol"]

        if not self.market_state.has_price(symbol):
            return

        price = self.market_state.get_price(symbol)

        # --- Exchange truth ---
        exchange_position = self.exchange.get_position()

        # Position fully closed externally
        if exchange_position is None:
            self.system_log.info("POSITION_CLOSED_CONFIRMED")
            self.state.clear_open_position()
            self.exit_in_progress = False
            self._commitment_reached = False
            self.state.save()
            return

        # --- Position snapshot for RiskManager ---
        position_snapshot = open_position

        # --- Position risk evaluation ---
        position_decision = self.risk.evaluate_position(
            position=position_snapshot,
            price=price,
        )

        # Commitment reached (+1R)
        if (
            position_decision.highest_profit_usd is not None
            and not self._commitment_reached
        ):
            risk_usd = open_position.get("risk_usd", 0.0)
            if (
                risk_usd > 0
                and position_decision.highest_profit_usd >= risk_usd
            ):
                self._commitment_reached = True

        # --- Update trailing SL if required ---
        if position_decision.updated_stop_loss is not None:
            self.exchange.update_sl(
                side=open_position["side"],
                qty=open_position["qty"],
                new_stop_price=position_decision.updated_stop_loss,
            )

            # --- Verify SL truth via exchange ---
            exchange_position = self.exchange.get_position()

            if exchange_position is None:
                self.system_log.critical(
                    "SL_UPDATE_FAILED | POSITION_MISSING_AFTER_SL_UPDATE"
                )
                self.safety.halt("SL_VERIFICATION_FAILED")
                self.state.set_engine_state(
                    engine_state=self.INVARIANT_HALT,
                    reason="SL_VERIFICATION_FAILED",
                )
                self.state.save()
                return

            open_position["stop_loss"] = (
                position_decision.updated_stop_loss
            )

        if position_decision.highest_profit_usd is not None:
            open_position["highest_profit_usd"] = (
                position_decision.highest_profit_usd
            )

        self.state.update_open_position(open_position)

        # --- Exit on violation ---
        if position_decision.violation and not self.exit_in_progress:
            self.exit_in_progress = True

            self.system_log.critical(
                f"POSITION_RISK_VIOLATION | "
                f"reason={position_decision.reason}"
            )

            send_message(
                "🚨 <b>POSITION RISK VIOLATION</b>\n\n"
                f"Reason: {position_decision.reason}\n\n"
                "Emergency exit sent.\n"
                "ENGINE HALTED — manual intervention required."
            )

            # Emergency flatten
            self.exchange.emergency_exit()

            # Clear position state
            self.state.clear_open_position()

            # HARD HALT — this is critical
            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason=position_decision.reason,
            )

            self.safety.halt(position_decision.reason)

            self._commitment_reached = False
            self.state.save()

            return

    def reconcile(self, reason: str):
        """
        Reconcile engine state with exchange truth.
        """

        engine_state = self.state.get_state().get("engine_state")
        if engine_state in (
            self.RISK_HALT,
            self.INVARIANT_HALT,
            self.MANUAL_HALT,
            self.FATAL_HALT,
        ):
            self.system_log.critical(
                f"RECONCILIATION_BLOCKED | engine_state={engine_state}"
            )
            return

        self.system_log.info(
            f"RECONCILIATION_START | reason={reason}"
        )

        try:
            position = self.exchange.get_position()

            if position is None:
                self.state.update_after_trade(
                    balance=self.state.get_state().get("balance", 0.0),
                    open_position=None,
                    last_trade=None,
                )
            else:
                self.state.state["open_position"] = self._build_open_position(
                    symbol=position.symbol,
                    side=position.side,
                    entry_price=position.entry_price,
                    qty=position.qty,
                    stop_loss=position.stop_loss,
                )

                # Invariant: position must always have protective SL
                if position.stop_loss is None:
                    self.system_log.critical(
                        "RECONCILIATION_POSITION_WITHOUT_SL"
                    )
                    self.state.set_engine_state(
                        engine_state=self.INVARIANT_HALT,
                        reason="POSITION_WITHOUT_SL",
                    )
                    self.state.save()
                    self.safety.halt("POSITION_WITHOUT_SL")
                    return

                # Re-attach to existing position
                self.exit_in_progress = False
                self._entry_in_progress = False
                self._accepted_intent = None
                self._latest_intent = None

            utc_day = datetime.now(timezone.utc).date()
            realized = self.exchange.get_realized_pnl(utc_day)

            self.state.state["daily_realized_pnl"] = realized

            if realized > self.state.state.get("daily_peak_pnl", 0.0):
                self.state.state["daily_peak_pnl"] = realized

            self.state.save()

            self.exit_in_progress = False

            # Recompute commitment state from stored profit
            open_position = self.state.get_open_position()
            if open_position is not None:
                highest_profit = open_position.get("highest_profit_usd", 0.0)
                risk_usd = open_position.get("risk_usd", 1.0)
                self._commitment_reached = (
                    highest_profit >= risk_usd
                )
            else:
                self._commitment_reached = False
            self.system_log.info("RECONCILIATION_SUCCESS")

        except Exception as e:
            self.system_log.critical(
                f"RECONCILIATION_FAILED | error={e}"
            )
            send_message(
                "🔴 <b>RECONCILIATION FAILED</b>\n\n"
                f"{e}\n\n"
                "Engine halted.\n"
                "Existing positions remain protected.\n"
                "Profit protection is frozen."
            )
            self.safety.halt("RECONCILIATION_FAILED")
            raise

    def load_universe(self):
        """
        Load tradable universe snapshot.
        """
        if not os.path.exists(UNIVERSE_SNAPSHOT_FILE):
            raise RuntimeError("UNIVERSE_SNAPSHOT_MISSING")

        with open(UNIVERSE_SNAPSHOT_FILE, "r") as f:
            snapshot = json.load(f)

        symbols = snapshot.get("symbols")
        generated_at = snapshot.get("generated_at")

        assert isinstance(symbols, list)
        assert len(symbols) == EXPECTED_UNIVERSE_SIZE

        for s in symbols:
            assert isinstance(s, str)
            assert s.endswith("USDT")

        self.universe_symbols = symbols
        self.universe_generated_at = generated_at

        self.system_log.info(
            f"UNIVERSE_LOADED | count={len(symbols)}"
        )

    def warmup_strategy(self):
        """
        Warm up strategy with historical candles.
        """
        WARMUP_INTERVAL = "1m"
        WARMUP_LIMIT = 100

        for symbol in self.universe_symbols:
            candles = self.exchange.get_historical_candles(
                symbol=symbol,
                interval=WARMUP_INTERVAL,
                limit=WARMUP_LIMIT,
            )

            for ts, close_price in candles:
                self.strategy.on_price(
                    symbol=symbol,
                    price=close_price,
                    timestamp=ts,
                )

        self.system_log.info(
            f"STRATEGY_WARMUP_COMPLETE | symbols={len(self.universe_symbols)}"
        )
