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
        error_log,
        trade_log,
        throttle,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.safety = safety
        self.emergency = emergency
        self.system_log = system_log
        self.trade_log = trade_log
        self.throttle = throttle
        self.error_log = error_log
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
            self.system_log.info(
                f"ENTRY_BLOCKED_NO_PRICE | symbol={symbol}"
            )
            return False

        entry_price = market_state.get_price(symbol)

        if entry_price <= 0:
            error_log.error(
                f"ENTRY_BLOCKED_INVALID_PRICE | "
                f"symbol={symbol} | price={entry_price}"
            )
            return False

        # --------------------------------------------------
        # Spread guard
        # --------------------------------------------------

        spread_pct = self.exchange.get_current_spread_pct(
            symbol=symbol
        )

        if spread_pct > MAX_SPREAD_PCT:
            self.throttle.log(
                key=f"spread_block_{symbol}",
                level="info",
                message=(
                    f"ENTRY_BLOCKED_SPREAD | "
                    f"symbol={symbol} | "
                    f"spread_pct={spread_pct} | "
                    f"max_allowed={MAX_SPREAD_PCT}"
                ),
            )
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
        # balance stored via update_after_trade later
        if balance < required_margin:
            error_log.error(
                f"ENTRY_BLOCKED_MARGIN | "
                f"symbol={symbol} | "
                f"balance={balance} | "
                f"required={required_margin}"
            )
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
            error_log.error(
                f"ENTRY_NOT_FILLED | symbol={symbol}"
            )
            return False

        # --------------------------------------------------
        # Partial fill guard
        # --------------------------------------------------

        if not ack.fully_filled:

            error_log.error(
                f"PARTIAL_FILL | "
                f"symbol={symbol} | "
                f"requested={ack.requested_qty} | "
                f"filled={ack.filled_qty}"
            )
            raise RuntimeError("PARTIAL_FILL_ABORT")

        # --------------------------------------------------
        # Notional invariant
        # --------------------------------------------------

        executed_notional = ack.filled_qty * ack.avg_price
        max_allowed = MAX_NOTIONAL_USD * (
            1 + NOTIONAL_TOLERANCE_PCT / 100
        )

        if executed_notional > max_allowed:

            raise RuntimeError("ENGINE_NOTIONAL_BREACH")
        # --------------------------------------------------
        # Recalculate SL
        # --------------------------------------------------

        actual_risk_usd = 0.9 * self.risk.RISK_PER_TRADE_USD
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

            raise RuntimeError("POST_FILL_RISK_BREACH")
        # --------------------------------------------------
        # Slippage guard
        # --------------------------------------------------

        slippage_pct = abs(
            (ack.avg_price - entry_price) / entry_price
        ) * 100.0

        if slippage_pct > ENTRY_SLIPPAGE_PCT:

            raise RuntimeError("SLIPPAGE_BREACH")
        # --------------------------------------------------
        # Place initial SL
        # --------------------------------------------------

        sl_placed = False
        sl_start_time = time.time()

        expected_sl = self.exchange.quantize_price(
            symbol,
            corrected_sl,
        )

        for attempt in range(2):
            try:
                self.exchange.place_initial_sl(
                    symbol=symbol,
                    side=intent.direction,
                    qty=ack.filled_qty,
                    stop_price=corrected_sl,
                )

                verified = self.exchange.get_position()

                if verified is None:
                    error_log.error(
                        f"INITIAL_SL_VERIFY_POSITION_NONE | "
                        f"symbol={symbol} | "
                        f"attempt={attempt+1}"
                    )
                    continue

                if (
                    verified.stop_loss is not None
                    and abs(
                        verified.stop_loss - expected_sl
                    ) < 1e-12
                ):
                    sl_placed = True
                    self.system_log.info(
                        f"INITIAL_SL_VERIFIED | "
                        f"symbol={symbol} | "
                        f"stop_loss={verified.stop_loss}"
                    )
                    break
                else:
                    error_log.error(
                        f"INITIAL_SL_VERIFICATION_MISMATCH | "
                        f"symbol={symbol} | "
                        f"expected={expected_sl} | "
                        f"actual={getattr(verified, 'stop_loss', None)}"
                    )

            except Exception as e:
                error_log.error(
                    f"INITIAL_SL_PLACEMENT_EXCEPTION | "
                    f"symbol={symbol} | "
                    f"attempt={attempt+1} | "
                    f"error={e}"
                )
                time.sleep(0.5)

        if not sl_placed:
            send_warning(
                "SL PLACEMENT FAILED",
                "Monitoring risk boundary."
            )

        if (time.time() - sl_start_time) > MAX_SL_PLACEMENT_SECONDS:

            raise RuntimeError("SL_TIMING_BREACH")
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
            self.state.set_trade_panel_message_id(msg_id)
            self.state.save()

        self.trade_log.info(
            f"TRADE_OPEN | "
            f"symbol={symbol} | "
            f"side={intent.direction} | "
            f"entry={ack.avg_price:.4f} | "
            f"qty={ack.filled_qty:.6f}"
        )

        return True
