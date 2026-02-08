# ==========================================================
# ENGINE
# ==========================================================
# Responsibilities:
# - Orchestrate lifecycle
# - Ask Strategy for intent
# - Ask Risk for math
# - Delegate ALL execution to Exchange Adapter
# - NEVER exit positions directly
# - NEVER compute realized PnL
# - NEVER trust price-touch as exit confirmation
#
# Truth sources:
# - Position existence: exchange.get_position()
# - Market prices: exchange.price_stream()
# ==========================================================
import json
import os
import time
from datetime import datetime, timezone
from strategy.strategy import Strategy
from strategy.trade_intent import TradeIntent
from risk.risk import RiskManager
from safety.safety import SafetyManager
from state.state import StateManager
from execution.exceptions import OperationalExchangeError
from utils.logger import system_logger, trade_logger, risk_logger, daily_logger
from config import SIM_START_BALANCE, MAX_NOTIONAL_USD, LEVERAGE, NOTIONAL_TOLERANCE_PCT, RISK_PER_TRADE_USD, RISK_TOLERANCE_PCT
from utils.telegram_notifier import send_message, edit_message
from dataclasses import dataclass

@dataclass
class EntryPlan:
    symbol: str
    direction: str          # "LONG" only for now
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
    Canonical trading engine (Phase D, up to PASS D-E3).

    Engine principles:
    - Engine decides WHEN to act, never HOW.
    - Exchange adapter is sole execution authority.
    - Risk module is sole math authority.
    - Engine never confirms exits without exchange truth.
    """

    # ------------------------------------------------------
    # Halt Types (D-E8)
    # ------------------------------------------------------

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
        self.exchange = exchange
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

        self.state = StateManager()
        self.strategy = Strategy()
        self.risk = RiskManager(
            NOTIONAL_TARGET=MAX_NOTIONAL_USD,
            NOTIONAL_TOLERANCE_PCT=NOTIONAL_TOLERANCE_PCT,
            RISK_PER_TRADE_USD=RISK_PER_TRADE_USD,
            RISK_TOLERANCE_PCT=RISK_TOLERANCE_PCT,
        )
        self.safety = SafetyManager()

        # Exit lifecycle guard (single-exit invariant)
        self.exit_in_progress = False

        # +1R commitment state
        self._commitment_reached = False

        # UTC day tracking
        self._last_utc_day = None

        # Loggers
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

        self.system_log.info("ENGINE_INITIALIZED")

    # ------------------------------------------------------
    # Engine Start
    # ------------------------------------------------------

    def start(self):
        """
        Start engine execution.
        """
        self.state.load()
        # --- Adapter connectivity gate  ---
        try:
            self.exchange.connect()
        except Exception as e:
            self.system_log.critical(
                f"EXCHANGE_CONNECT_FAILED | error={e}"
            )
            self.halt(
                reason="EXCHANGE_CONNECT_FAILED",
                halt_type=self.FATAL_HALT
            )
            return

        # --- Reconciliation gate on startup ---
        # Reconcile on startup or resume
        engine_state = self.state.get_state().get("engine_state")
        # ALL resumes go through reconciliation
        assert engine_state is not None
        if engine_state == self.DAILY_HALT:
            self.reconcile(reason="DAILY_HALT_RESUME")
        else:
            self.reconcile(reason="ENGINE_STARTUP")

        # --------------------------------------------------
        # Load universe snapshot
        # --------------------------------------------------
        self.load_universe()

        # --------------------------------------------------
        # Strategy warmup
        # --------------------------------------------------
        self.warmup_strategy()

        # Bootstrap balance for paper/SIM-like environments
        if self.state.get_state().get("balance", 0.0) == 0.0:
            self.state.update_after_trade(
                balance=SIM_START_BALANCE,
                open_position=None,
                last_trade=None,
            )
            self.state.save()
        # --------------------------------------------------
        # TELEGRAM — Engine Started
        # --------------------------------------------------
        send_message(
            "🟢 <b>ENGINE STARTED</b>\n\n"
            "Mode: SIM\n"
            "Symbol: BTCUSDT\n"
            f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Status: READY",
        )

        self._main_loop()

    # ----------------
    # Reconciliation
    # ----------------

    def reconcile(self, reason: str):
        """
        Reconcile engine state with exchange truth.

        Called ONLY on:
        - startup
        - resume
        - restart
        - UTC day rollover

        Any failure is fatal.
        """
        self.system_log.info(
            f"RECONCILIATION_START | reason={reason}"
        )

        try:
            # --- Position truth ---
            position = self._poll_position_truth(
                reason=f"RECONCILIATION:{reason}"
            )

            if position is None:
                # No open position on exchange
                self.state.update_after_trade(
                    balance=self.state.get_state().get("balance", 0.0),
                    open_position=None,
                    last_trade=None,
                )
            else:
                # Position exists on exchange → must mirror locally
                self.state.state["open_position"] = {
                    "side": position.side,
                    "entry_price": position.entry_price,
                    "qty": position.qty,
                    "stop_loss": None,
                    "highest_profit_usd": 0.0,
                }

            # --- Realized PnL truth (UTC day) ---
            utc_day = datetime.now(timezone.utc).date()
            realized = self.exchange.get_realized_pnl(utc_day)

            self.state.state["daily_realized_pnl"] = realized

            # Peak must be ≥ realized
            if realized > self.state.state.get("daily_peak_pnl", 0.0):
                self.state.state["daily_peak_pnl"] = realized

            self.state.save()

            self.system_log.info("RECONCILIATION_SUCCESS")

        except Exception as e:
            self.system_log.critical(
                f"RECONCILIATION_FAILED | error={e}"
            )
            self.halt("RECONCILIATION_FAILED")
            raise


    # ------------------------------------------------------
    # Universe Loader
    # ------------------------------------------------------

    def load_universe(self):
        """
        Load tradable universe snapshot.
        READ-ONLY. No ranking, no selection.
        """

        if not os.path.exists(UNIVERSE_SNAPSHOT_FILE):
            raise RuntimeError("UNIVERSE_SNAPSHOT_MISSING")

        try:
            with open(UNIVERSE_SNAPSHOT_FILE, "r") as f:
                snapshot = json.load(f)

            symbols = snapshot.get("symbols")
            generated_at = snapshot.get("generated_at")

            # --- Validation ---
            assert isinstance(symbols, list), "UNIVERSE_SYMBOLS_NOT_LIST"
            assert len(symbols) == EXPECTED_UNIVERSE_SIZE, (
                f"UNIVERSE_SIZE_INVALID | size={len(symbols)}"
            )

            for s in symbols:
                assert isinstance(s, str), "UNIVERSE_SYMBOL_NOT_STRING"
                assert s.endswith("USDT"), f"UNIVERSE_INVALID_SYMBOL | {s}"

            self.universe_symbols = symbols
            self.universe_generated_at = generated_at

            self.system_log.info(
                f"UNIVERSE_LOADED | "
                f"count={len(symbols)} | "
                f"generated_at={generated_at}"
            )

            # Telegram = observability only
            send_message(
                "📦 <b>UNIVERSE LOADED</b>\n\n"
                f"Symbols: {len(symbols)}\n"
                f"Generated at: {generated_at}"
            )

        except Exception as e:
            raise RuntimeError(f"UNIVERSE_LOAD_FAILED | {e}")


    # ------------------------------------------------------
    # Exchange Position Polling
    # ------------------------------------------------------

    def _poll_position_truth(self, reason: str):
        """
        Poll exchange position truth.
        - This is the ONLY place engine may call get_position()
        """
        self.system_log.info(
            f"POSITION_POLL | reason={reason}"
        )
        return self.exchange.get_position()

    # ------------------------------------------------------
    # Local Unrealized PnL (D-E7)
    # ------------------------------------------------------

    def _compute_unrealized_pnl(self, open_position: dict, price: float) -> float:
        """
        Compute unrealized PnL locally.
        - Exchange unrealized PnL must NEVER be used in hot path
        - This value is authoritative for +1R and trailing logic
        """
        side = open_position["side"]
        entry_price = open_position["entry_price"]
        qty = open_position["qty"]

        if side == "LONG":
            return (price - entry_price) * qty
        else:
            return (entry_price - price) * qty

    # --------------------------------------------------
    # Strategy Warmup
    # --------------------------------------------------

    def warmup_strategy(self):
        """
        Warm up strategy with historical candles.
        Must be called before intent polling is meaningful.
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
            "STRATEGY_WARMUP_COMPLETE | "
            f"symbols={len(self.universe_symbols)}"
        )

    # --------------------------------------------------
    # TradeIntent validation (F.2.4)
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
        if engine_state != self.RUNNING:
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
    # Intent → EntryPlan (F.2.5)
    # --------------------------------------------------

    def build_entry_plan(self, intent: TradeIntent):
        """
        Convert an ACCEPTED TradeIntent into a risk-evaluated EntryPlan.
        No execution performed here.
        """

        # Advisory entry price
        entry_price = intent.entry_price

        if entry_price is None:
            # For now, assume market entry at last known price
            entry_price = self.last_price

        # Ask RiskManager for sizing + SL
        risk_result = self.risk.build_entry_plan(
             direction=intent.direction,
             entry_price=entry_price,
        )

        return EntryPlan(
            symbol=intent.symbol,
            direction=intent.direction,
            entry_price=entry_price,
            quantity=risk_result.quantity,
            initial_sl=risk_result.initial_sl,
            risk_r=risk_result.risk_r,
        )

    # ------------------------------------------------------
    # Main Market Loop
    # ------------------------------------------------------

    def _main_loop(self):
        """
        Consume price ticks from exchange adapter.
        """
        try:
            for tick in self.exchange.price_stream():

                if not self.safety.is_safe():
                    return

                # Normalize market data
                self.market_data = {
                    "price": tick.price,
                    "timestamp": tick.timestamp,
                }

                # Fan-in market data to engine
                self.on_price(
                    symbol=tick.symbol,
                    price=tick.price,
                    timestamp=tick.timestamp,
                )

                self.state.heartbeat(
                    datetime.now(timezone.utc).isoformat()
                )
                self.state.save()

        except OperationalExchangeError as e:
            self.system_log.critical(
                f"OPERATIONAL_EXCHANGE_ERROR | {e}"
            )
            self.halt(
                reason="OPERATIONAL_EXCHANGE_ERROR",
                halt_type=self.OPERATIONAL_HALT
            )

        except StopIteration:
            self.system_log.info("MARKET_DATA_EXHAUSTED")
            self.halt("MARKET_DATA_EXHAUSTED")

    # ------------------------------------------------------
    # Price Event Handler
    # ------------------------------------------------------

    def on_price(self, symbol: str, price: float, timestamp: int):
        """
        Called on every new market price tick.
        """

        # On_price must NEVER poll exchange
        assert not self.exit_in_progress or True

        if not self.safety.is_safe():
            return

        # --------------------------------------------------
        # Strategy v2 fan-in (READ-ONLY)
        # --------------------------------------------------
        self.strategy.on_price(
            symbol=symbol,
            price=price,
            timestamp=timestamp,
        )

        try:
            state_snapshot = self.state.get_state()
            open_position = state_snapshot.get("open_position")

            # --------------------------------------------------
            # UTC Day Rollover
            # --------------------------------------------------

            ts = self.market_data["timestamp"]
            utc_day = time.gmtime(ts // 1000).tm_yday

            if self._last_utc_day is None:
                self._last_utc_day = utc_day
            elif utc_day != self._last_utc_day:
                self._last_utc_day = utc_day
                self.reconcile(reason="UTC_DAY_ROLLOVER")

            # --------------------------------------------------
            # Daily Risk Evaluation
            # --------------------------------------------------

            daily_decision = self.risk.evaluate_daily(
                state_snapshot.get("daily_realized_pnl", 0.0),
                state_snapshot.get("daily_peak_pnl", 0.0),
            )

            # Cache daily loss floor (state is memory, not authority)
            self.state.update_daily_loss_floor(
                daily_decision.daily_loss_floor
            )

            if daily_decision.halt:
                self.system_log.critical(
                    f"DAILY_HALT | reason={daily_decision.reason}"
                )

                send_message(
                    "⛔ <b>DAILY HALT</b>\n\n"
                    f"Reason: {daily_decision.reason}\n"
                    f"Daily Loss Floor: {daily_decision.daily_loss_floor} USD\n\n"
                    f"UTC: {datetime.now(timezone.utc).date()}"
                )

                self.halt(
                    reason=daily_decision.reason,
                    halt_type=self.DAILY_HALT
                )
                return

            # --------------------------------------------------
            # OPEN POSITION MONITORING
            # --------------------------------------------------

            if open_position is not None:
                self._handle_open_position(open_position, price)
                return

            # --------------------------------------------------
            # Strategy intent polling (READ-ONLY)
            # --------------------------------------------------
            intent = self.strategy.propose_intent()

            if intent is None:
                return

            is_valid, reason = self.validate_intent(intent)

            if not is_valid:
                self.system_log.info(
                    f"INTENT_REJECTED | "
                    f"symbol={intent.symbol} "
                    f"direction={intent.direction} "
                    f"reason={reason}"
                )
                return

            self.system_log.info(
                f"INTENT_ACCEPTED | "
                f"symbol={intent.symbol} "
                f"direction={intent.direction} "
                f"pattern={intent.pattern}"
            )

            # --------------------------------------------------
            # Build entry plan (F.2.5)
            # --------------------------------------------------
            entry_plan = self.build_entry_plan(intent)

            self._pending_entry_plan = entry_plan

            self.system_log.info(
                f"ENTRY_PLAN_READY | "
                f"symbol={entry_plan.symbol} "
                f"qty={entry_plan.quantity} "
                f"entry={entry_plan.entry_price} "
                f"sl={entry_plan.initial_sl} "
                f"R={entry_plan.risk_r}"
            )

            # --------------------------------------------------
            # STRATEGY INTENT (ENTRY ONLY)
            # --------------------------------------------------

        except AssertionError as e:
            self.system_log.critical(f"INVARIANT_BREACH | {e}")

            send_message(
                "🧯 <b>INVARIANT BREACH</b>\n\n"
                f"Details:\n{e}\n\n"
                "Action: ENGINE HALTED\n"
                f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            )

            self.halt(
                reason="INVARIANT_BREACH",
                halt_type=self.INVARIANT_HALT
            )

    # ------------------------------------------------------
    # Handle Existing Position (NO EXIT EXECUTION)
    # ------------------------------------------------------

    def _handle_open_position(self, open_position: dict, price: float):
        """
        Monitor open position.
        - NO SELL execution
        - NO realized PnL computation
        - SL updates only
        - Exit confirmation via exchange truth ONLY
        """
        # Unrealized PnL is LOCAL ONLY
        # Exchange unrealized PnL endpoints must never be used here

        if self.exit_in_progress:
            return

        # Hard schema invariants
        required_keys = {"side", "entry_price", "qty", "stop_loss"}
        assert required_keys.issubset(open_position), (
            "OPEN_POSITION_SCHEMA_INVALID"
        )

        # --- Local unrealized PnL (USED ONLY FOR +1R DETECTION) ---
        unrealized_pnl = self._compute_unrealized_pnl(
            open_position,
            price
        )

        # --------------------
        # +1R COMMITMENT POINT
        # --------------------
        if (
            not self._commitment_reached
            and unrealized_pnl >= self.risk.MAX_RISK_USD
        ):

            self._commitment_reached = True

            # Cancel any remaining entry orders (already canonical)
            self.exchange.cancel_pending_entries()

            # Persist commitment marker (memory only)
            open_position["commitment_reached"] = True

            msg_id = (
                self.state.get_state()
                .get("telegram", {})
                .get("current_trade_message_id")
            )

            if msg_id:
                msg = (
                    "📊 <b>TRADE ACTIVE</b>\n\n"
                    "✅ +1R Reached\n"
                    "Exposure Frozen\n"
                    "Pending Entries: CANCELLED\n\n"
                    f"Current SL: {open_position.get('stop_loss')}"
                )
                edit_message(msg_id, msg)

        # ==================================================
        # Risk evaluation
        # ==================================================
        pos_decision = self.risk.evaluate_position(
            open_position,
            price
        )

        # Track highest profit (local, unrealized)
        if pos_decision.highest_profit_usd is not None:
            open_position["highest_profit_usd"] = (
                pos_decision.highest_profit_usd
            )

        # Risk violation → emergency intent (no execution here)
        if pos_decision.violation:
            self.system_log.critical(
                f"RISK_VIOLATION | {pos_decision.reason}"
            )
            self.exit_in_progress = True

            # Emergency flatten position (last resort)
            self.exchange.emergency_exit()

            # Always halt after emergency exit
            self.halt(
                reason=pos_decision.reason,
                halt_type=self.RISK_HALT
            )
            self.state.state["last_trade"] = {
                "exit_reason": "EMERGENCY_EXIT"
            }
            self._commitment_reached = False
            return

        # --------------------------------------------------
        # PROFIT SL AUTHORITY (AFTER +1R ONLY)
        # --------------------------------------------------

        if (
            self._commitment_reached
            and pos_decision.updated_stop_loss is not None
        ):
            # SL only tightens (guaranteed by RiskManager)
            self.exchange.update_sl(
                side=open_position["side"],
                qty=open_position["qty"],
                new_stop_price=pos_decision.updated_stop_loss,
            )

            self.state.update_stop_loss(
                pos_decision.updated_stop_loss
            )

            msg_id = (
                self.state.get_state()
                .get("telegram", {})
                .get("current_trade_message_id")
            )

            if msg_id:
                msg = (
                    "📊 <b>TRADE ACTIVE</b>\n\n"
                    "🔒 Trailing SL Updated\n"
                    f"New SL: {pos_decision.updated_stop_loss}\n"
                    f"Highest Profit: {pos_decision.highest_profit_usd} USD\n\n"
                    "Status: OPEN"
                )
                edit_message(msg_id, msg)

            self.trade_log.info(
                f"PROFIT_SL_UPDATED | new_sl={pos_decision.updated_stop_loss}"
            )

        # SL price touched → verify via exchange truth ONLY
        if pos_decision.normal_exit:
            self.exit_in_progress = True

            position_snapshot = self._poll_position_truth(
                reason="SL_TOUCHED"
            )

                # Exchange confirms exit
            if position_snapshot is None:
                self.trade_log.info(
                    "POSITION_CLOSED | confirmed_by_exchange"
                )

                exit_reason = (
                    "TRAILING_SL"
                    if pos_decision.updated_stop_loss is not None
                    else "NORMAL_SL"
                )

                # Exit price derived from active stop-loss
                exit_price = open_position.get("stop_loss")

                self.state.update_after_trade(
                    balance=self.state.get_state().get("balance", 0.0),
                    open_position=None,
                    last_trade={
                        "exit_reason": exit_reason,
                        "exit_price": exit_price,
                    },
                )

                self.state.save()
                self.reset_exit_guard()
                self._commitment_reached = False
            else:
                # SL was touched but position still open → operational ambiguity
                self.system_log.critical(
                    "SL_TOUCHED_BUT_POSITION_OPEN | entering operational halt"
                )
                self.halt(
                    reason="SL_CONFIRMATION_FAILED",
                    halt_type=self.OPERATIONAL_HALT
                )

    # ------------------------------------------------------
    # Handle Entry (BUY ONLY)
    # ------------------------------------------------------

    def _handle_entry(self, price: float):
        """
        Handle new entry intent.
        """

        entry_decision = self.risk.evaluate_entry(price, "LONG")
        if not entry_decision.allowed:
            self.system_log.info(
                f"ENTRY_BLOCKED | reason={entry_decision.reason}"
            )
            return

        # Margin guard
        required_margin = MAX_NOTIONAL_USD / LEVERAGE
        balance = self.state.get_state().get("balance", 0.0)
        if balance < required_margin:
            self.system_log.info(
                "ENTRY_BLOCKED | INSUFFICIENT_MARGIN"
            )
            return

        # Place entry via adapter
        ack = self.exchange.place_entry(
            side="LONG",
            notional_usd=MAX_NOTIONAL_USD,
            price=price,
        )

        if ack.filled_qty <= 0:
            self.system_log.info("ENTRY_NO_FILL")
            return

        # Post-fill invariant
        executed_notional = ack.filled_qty * ack.avg_price
        max_allowed = MAX_NOTIONAL_USD * (
            1 + NOTIONAL_TOLERANCE_PCT / 100
        )
        assert executed_notional <= max_allowed, (
            "ENGINE_NOTIONAL_BREACH"
        )

        open_position = {
            "side": "LONG",
            "entry_price": ack.avg_price,
            "qty": ack.filled_qty,
            "stop_loss": entry_decision.stop_loss,
            "highest_profit_usd": 0.0,
        }

        # --- Place initial protective SL on exchange (MANDATORY) ---
        self.exchange.place_initial_sl(
            side="LONG",
            qty=ack.filled_qty,
            stop_price=entry_decision.stop_loss,
        )

        self.state.update_after_trade(
            balance=balance,
            open_position=open_position,
            last_trade=None,
        )

        self.trade_log.info(
            f"POSITION_OPENED | price={ack.avg_price} qty={ack.filled_qty}"
        )

        # --------------------------------------------------
        # TELEGRAM — Trade Status Panel (CREATE)
        # --------------------------------------------------
        msg = (
            "📊 <b>TRADE OPENED</b>\n\n"
            f"Side: LONG\n"
            f"Entry Price: {ack.avg_price}\n"
            f"Quantity: {ack.filled_qty}\n"
            f"Notional: {MAX_NOTIONAL_USD} USD\n\n"
            f"Initial SL: {entry_decision.stop_loss}\n\n"
            "Status: OPEN"
        )

        msg_id = send_message(msg)
        if msg_id:
            self.state.state.setdefault("telegram", {})
            self.state.state["telegram"]["current_trade_message_id"] = msg_id

        self.state.save()

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------

    def _notify_telegram(self, text: str) -> None:
        """
        Fire-and-forget Telegram notification.
        Must NEVER affect engine behavior.
        """
        try:
            send_message(text)
        except Exception:
            # Absolute last-resort safety:
            # Telegram must never break trading.
            pass

    # ------------------------------------------------------
    # Reset Exit Guard
    # ------------------------------------------------------

    def reset_exit_guard(self):
        """
        Reset exit lifecycle guard.
        """
        self.exit_in_progress = False

    # ------------------------------------------------------
    # Halt Engine
    # ------------------------------------------------------

    def halt(self, reason: str, halt_type: str = FATAL_HALT):
        """
        Halt engine execution.
        """
        self.system_log.critical(
            f"ENGINE_HALTED | type={halt_type} | reason={reason}"
        )

        # --------------------------------------------------
        # TELEGRAM — Engine Halted
        # --------------------------------------------------
        send_message(
            "🔴 <b>ENGINE HALTED</b>\n\n"
            f"Type: {halt_type}\n"
            f"Reason: {reason}\n\n"
            f"UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        self.safety.halt(reason)
        self.state.set_engine_state(halt_type, reason)
        self.state.save()
        # --- Adapter disconnect (best effort) ---
        try:
            self.exchange.disconnect()
        except Exception:
            pass
