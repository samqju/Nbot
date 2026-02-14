# ==========================================================
# ENTRY LIFECYCLE
# ==========================================================
# Owns:
# - Entry execution
# - Margin guard
# - Spread guard
# - Slippage guard
# - Post-fill invariants
# - Initial SL placement
# ==========================================================

import time
from datetime import datetime, timezone

from config import (
    MAX_NOTIONAL_USD,
    LEVERAGE,
    NOTIONAL_TOLERANCE_PCT,
    RISK_PER_TRADE_USD,
    RISK_TOLERANCE_PCT,
    ENTRY_SLIPPAGE_PCT,
    MAX_SPREAD_PCT,
)

from utils.telegram_notifier import (
    send_warning,
    send_critical,
    send_trade_panel,
    format_trade_panel,
)

MAX_SL_PLACEMENT_SECONDS = 2.0


class EntryLifecycle:

    RISK_HALT = "RISK_HALT"

    def __init__(
        self,
        *,
        exchange,
        state,
        risk,
        safety,
        emergency,
        system_log,
        trade_log,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.safety = safety
        self.emergency = emergency
        self.system_log = system_log
        self.trade_log = trade_log

        self._entry_in_progress = False

    @property
    def entry_in_progress(self):
        return self._entry_in_progress

    # --------------------------------------------------
    # Public
    # --------------------------------------------------

    def maybe_execute(self, *, intent, market_state):

        if intent is None:
            return False

        if self._entry_in_progress:
            return False

        if not self.safety.is_safe():
            return False

        self._entry_in_progress = True

        try:
            return self._execute(intent, market_state)
        finally:
            self._entry_in_progress = False

    # --------------------------------------------------
    # Core Execution
    # --------------------------------------------------

    def _execute(self, intent, market_state):

        symbol = intent.symbol

        if not market_state.has_price(symbol):
            return False

        entry_price = market_state.get_price(symbol)

        if entry_price <= 0:
            return False

        # --------------------------------------------------
        # Spread guard
        # --------------------------------------------------

        spread_pct = self.exchange.get_current_spread_pct(
            symbol=symbol
        )

        if spread_pct > MAX_SPREAD_PCT:
            return False

        # --------------------------------------------------
        # Build entry plan
        # --------------------------------------------------

        entry_plan = self.risk.build_entry_plan(
            direction=intent.direction,
            entry_price=entry_price,
        )

        required_margin = MAX_NOTIONAL_USD / LEVERAGE

        balance = self.exchange.get_available_balance()
        self.state.state["balance"] = balance

        if balance < required_margin:
            return False

        # --------------------------------------------------
        # Place entry
        # --------------------------------------------------

        ack = self.exchange.place_entry(
            symbol=symbol,
            side=intent.direction,
            quantity=entry_plan.quantity,
            price=entry_price,
        )

        if ack.filled_qty <= 0:
            return False

        # --------------------------------------------------
        # Partial fill guard
        # --------------------------------------------------

        if not ack.fully_filled:

            send_critical(
                "PARTIAL FILL DETECTED",
                f"Symbol: {symbol}\n"
                f"Requested: {ack.requested_qty}\n"
                f"Filled: {ack.filled_qty}\n"
                "Engine halting."
            )

            self.exchange.cancel_pending_entries()
            self.emergency.execute("PARTIAL_FILL_ABORT")

            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason="PARTIAL_FILL_ABORT",
            )
            self.state.save()
            self.safety.halt("PARTIAL_FILL_ABORT")
            return

        # --------------------------------------------------
        # Notional invariant
        # --------------------------------------------------

        executed_notional = ack.filled_qty * ack.avg_price
        max_allowed = MAX_NOTIONAL_USD * (
            1 + NOTIONAL_TOLERANCE_PCT / 100
        )

        if executed_notional > max_allowed:

            send_critical(
                "ENGINE NOTIONAL BREACH",
                f"Executed: {executed_notional:.4f}\n"
                f"Allowed: {max_allowed:.4f}\n"
                "Emergency exit triggered."
            )

            self.emergency.execute("ENGINE_NOTIONAL_BREACH")

            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason="ENGINE_NOTIONAL_BREACH",
            )
            self.state.save()
            self.safety.halt("ENGINE_NOTIONAL_BREACH")
            return

        # --------------------------------------------------
        # Recalculate SL
        # --------------------------------------------------

        actual_risk_usd = 0.9 * RISK_PER_TRADE_USD

        if intent.direction == "LONG":
            corrected_sl = ack.avg_price - (
                actual_risk_usd / ack.filled_qty
            )
        else:
            corrected_sl = ack.avg_price + (
                actual_risk_usd / ack.filled_qty
            )

        open_position = {
            "symbol": symbol,
            "side": intent.direction,
            "entry_price": ack.avg_price,
            "qty": ack.filled_qty,
            "stop_loss": corrected_sl,
            "risk_usd": RISK_PER_TRADE_USD,
            "highest_profit_usd": 0.0,
            "last_locked_R": 0,
            "entry_timestamp": int(
                datetime.now(timezone.utc).timestamp() * 1000
            ),
        }

        # --------------------------------------------------
        # Post-fill risk guard
        # --------------------------------------------------

        actual_risk_usd = abs(
            (ack.avg_price - corrected_sl)
            * ack.filled_qty
        )

        max_allowed_risk = RISK_PER_TRADE_USD * (
            1 + RISK_TOLERANCE_PCT / 100
        )

        if actual_risk_usd > max_allowed_risk:

            send_critical(
                "POST-FILL RISK BREACH",
                f"Symbol: {symbol}\n"
                f"Actual Risk: {actual_risk_usd:.4f} USD\n"
                f"Allowed: {max_allowed_risk:.4f} USD\n"
                "Emergency exit triggered."
            )

            self.emergency.execute("POST_FILL_RISK_BREACH")

            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason="POST_FILL_RISK_BREACH",
            )
            self.state.save()
            self.safety.halt("POST_FILL_RISK_BREACH")
            return

        # --------------------------------------------------
        # Slippage guard
        # --------------------------------------------------

        slippage_pct = abs(
            (ack.avg_price - entry_price) / entry_price
        ) * 100.0

        if slippage_pct > ENTRY_SLIPPAGE_PCT:

            send_critical(
                "SLIPPAGE BREACH",
                f"Symbol: {symbol}\n"
                f"Slippage: {slippage_pct:.4f}%\n"
                f"Allowed: {ENTRY_SLIPPAGE_PCT:.4f}%\n"
                "Emergency exit triggered."
            )

            self.emergency.execute("SLIPPAGE_BREACH")

            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason="SLIPPAGE_BREACH",
            )
            self.state.save()
            self.safety.halt("SLIPPAGE_BREACH")
            return

        # --------------------------------------------------
        # Place initial SL
        # --------------------------------------------------

        sl_placed = False
        sl_start_time = time.time()

        for _ in range(2):
            try:
                self.exchange.place_initial_sl(
                    symbol=symbol,
                    side=intent.direction,
                    qty=ack.filled_qty,
                    stop_price=corrected_sl,
                )
                sl_placed = True
                break
            except Exception:
                time.sleep(0.5)

        if not sl_placed:
            send_warning(
                "SL PLACEMENT FAILED",
                "Monitoring risk boundary."
            )

        if (time.time() - sl_start_time) > MAX_SL_PLACEMENT_SECONDS:

            send_critical(
                "SL TIMING BREACH",
                f"Symbol: {symbol}\n"
                "Emergency exit triggered."
            )

            self.emergency.execute("SL_TIMING_BREACH")

            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason="SL_TIMING_BREACH",
            )
            self.state.save()
            self.safety.halt("SL_TIMING_BREACH")
            return

        # --------------------------------------------------
        # Persist position
        # --------------------------------------------------

        self.state.update_after_trade(
            balance=balance,
            open_position=open_position,
            last_trade=None,
        )

        self.state.save()

        panel_text = format_trade_panel(
            symbol=symbol,
            side=intent.direction,
            entry_price=ack.avg_price,
            stop_loss=corrected_sl,
            qty=ack.filled_qty,
            risk_usd=RISK_PER_TRADE_USD,
            status="OPEN",
        )

        msg_id = send_trade_panel(panel_text)

        if msg_id:
            self.state.state["active_trade_panel_message_id"] = msg_id
            self.state.save()

        self.trade_log.info(
            f"TRADE_OPEN | "
            f"symbol={symbol} | "
            f"side={intent.direction} | "
            f"entry={ack.avg_price:.4f} | "
            f"qty={ack.filled_qty:.6f}"
        )

        return True
