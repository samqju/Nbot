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
        emergency,
        system_log,
        trade_log,
        throttle,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.emergency = emergency
        self.system_log = system_log
        self.trade_log = trade_log
        self.throttle = throttle
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

        # --------------------------------------------------
        # HARD SAFETY: Block entry if exchange already has position
        # --------------------------------------------------
        try:
            live_position = self.exchange.get_position()
        except Exception:
            live_position = None

        if live_position is not None:
            self.system_log.error(
                f"ENTRY_ABORT_LIVE_POSITION_EXISTS | "
                f"symbol={live_position.symbol} | qty={live_position.qty}"
            )
            raise RuntimeError("LIVE_POSITION_EXISTS")

        if not market_state.has_price(symbol):
            self.system_log.info(
                f"ENTRY_BLOCKED_NO_PRICE | symbol={symbol}"
            )
            return False

        entry_price = market_state.get_price(symbol)

        if entry_price <= 0:
            self.system_log.error(
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
            self.system_log.error(
                f"ENTRY_BLOCKED_MARGIN | "
                f"symbol={symbol} | "
                f"balance={balance} | "
                f"required={required_margin}"
            )
            return False

        # --------------------------------------------------
        # Capture Pre-Order Position State (Stack Protection)
        # --------------------------------------------------

        pre_position = None
        pre_qty = 0.0

        try:
            pre_position = self.exchange.get_position()
        except Exception:
            pre_position = None

        if pre_position is not None and pre_position.symbol == symbol:
            pre_qty = pre_position.qty


        # --------------------------------------------------
        # Place entry
        # --------------------------------------------------

        ack = self.exchange.place_entry(
            symbol=symbol,
            side=intent.direction,
            quantity=entry_plan.quantity,
            price=entry_price,
        )

        # --------------------------------------------------
        # Authoritative REST Reconciliation (Delta-Based)
        # Fixes testnet executedQty=0 behavior
        # --------------------------------------------------

        try:
            post_position = self.exchange.get_position()
        except Exception:
            post_position = None

        if post_position is None or post_position.symbol != symbol:
            self.system_log.error(
                f"ENTRY_NOT_CONFIRMED_BY_REST | symbol={symbol}"
            )
            raise RuntimeError("ENTRY_NOT_CONFIRMED")

        post_qty = post_position.qty
        delta_qty = post_qty - pre_qty

        # Hard guard — stacking not allowed
        if pre_qty > 0:
            self.system_log.error(
                f"STACK_DETECTED | "
                f"symbol={symbol} | "
                f"pre_qty={pre_qty} | "
                f"post_qty={post_qty}"
            )
            raise RuntimeError("STACKING_NOT_ALLOWED")

        if delta_qty <= 0:
            self.system_log.error(
                f"ENTRY_DELTA_ZERO | "
                f"symbol={symbol} | "
                f"pre_qty={pre_qty} | "
                f"post_qty={post_qty}"
            )
            raise RuntimeError("ENTRY_NOT_FILLED")

        # --------------------------------------------------
        # Mutate ack to authoritative truth
        # Keeps rest of lifecycle unchanged
        # --------------------------------------------------

        from execution.testnet_exchange import EntryAck

        ack = EntryAck(
            filled_qty=delta_qty,
            avg_price=post_position.entry_price,
            requested_qty=ack.requested_qty,
            fully_filled=abs(delta_qty - ack.requested_qty) < 1e-12,
        )

        # Now apply normal partial fill guard
        if not ack.fully_filled:
            self.system_log.error(
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

        # HARD SAFETY: Validate total exchange exposure
        try:
            live_position = self.exchange.get_position()
            if live_position is not None:
                total_notional = live_position.qty * live_position.entry_price
                if total_notional > max_allowed:
                    raise RuntimeError("ENGINE_TOTAL_NOTIONAL_BREACH")
        except Exception:
            pass

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
        # ATOMIC COMMIT PHASE:
        # Place SL first, verify everything once
        # --------------------------------------------------

        sl_start_time = time.time()

        # Place SL immediately (protection first)
        try:
            self.exchange.place_initial_sl(
                symbol=symbol,
                side=intent.direction,
                qty=ack.filled_qty,
                stop_price=corrected_sl,
            )
        except Exception as e:
            self.system_log.error(
                f"INITIAL_SL_PLACEMENT_EXCEPTION | "
                f"symbol={symbol} | error={e}"
            )
            raise RuntimeError("INITIAL_SL_FAILED")

        # --------------------------------------------------
        # SINGLE VERIFICATION PASS (bounded ≤ 0.5s)
        # --------------------------------------------------

        verified_position = None
        expected_sl = self.exchange.quantize_price(symbol, corrected_sl)

        deadline = sl_start_time + MAX_SL_PLACEMENT_SECONDS

        while time.time() < deadline:

            try:
                verified_position = self.exchange.get_position()
            except Exception:
                verified_position = None

            if (
                verified_position is not None
                and verified_position.symbol == symbol
                and verified_position.stop_loss is not None
                and abs(verified_position.stop_loss - expected_sl) < 1e-12
            ):
                self.system_log.info(
                    f"ENTRY_VERIFIED | "
                    f"symbol={symbol} | "
                    f"qty={verified_position.qty} | "
                    f"stop_loss={verified_position.stop_loss}"
                )
                break

            time.sleep(0.05)

        if verified_position is None:
            self.system_log.error(
                f"ENTRY_VERIFICATION_FAILED_NO_POSITION | symbol={symbol}"
            )
            raise RuntimeError("ENTRY_VERIFICATION_FAILED")

        if verified_position.stop_loss is None:
            self.system_log.error(
               f"ENTRY_VERIFICATION_FAILED_NO_SL | symbol={symbol}"
            )
            raise RuntimeError("SL_VERIFICATION_FAILED")

        if abs(verified_position.stop_loss - expected_sl) >= 1e-12:
            self.system_log.error(
                f"SL_VERIFICATION_MISMATCH | "
                f"symbol={symbol} | "
                f"expected={expected_sl} | "
                f"actual={verified_position.stop_loss}"
            )
            raise RuntimeError("SL_VERIFICATION_MISMATCH")

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
