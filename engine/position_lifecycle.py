# ==========================================================
# POSITION LIFECYCLE
# ==========================================================
# Owns:
# - Open position monitoring
# - Trailing SL updates
# - Exchange-truth verification
# - Trade close handling
# - Risk violation handling
# ==========================================================

import time
from utils.telegram_notifier import (
    send_critical,
    send_warning,
    edit_message,
    format_trade_panel,
)


class PositionLifecycle:

    RISK_HALT = "RISK_HALT"
    INVARIANT_HALT = "INVARIANT_HALT"

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

        self.exit_in_progress = False
        self._commitment_reached = False

    # --------------------------------------------------
    # Public
    # --------------------------------------------------

    def manage(self, *, market_state):

        state_snapshot = self.state.get_state()
        open_position = state_snapshot.get("open_position")

        if open_position is None:
            return

        symbol = open_position["symbol"]

        if not market_state.has_price(symbol):
            return

        price = market_state.get_price(symbol)

        exchange_position = self.exchange.get_position()

        # --------------------------------------------------
        # External close detected
        # --------------------------------------------------

        if exchange_position is None:

            self._handle_close(open_position)
            return

        # --------------------------------------------------
        # Evaluate risk
        # --------------------------------------------------

        decision = self.risk.evaluate_position(
            position=open_position,
            price=price,
        )

        # Track daily unrealised peak
        unrealised = (
            decision.highest_profit_usd
            if decision.highest_profit_usd is not None
            else 0.0
        )

        if unrealised > self.state.state.get(
            "daily_highest_unrealized_usd", 0.0
        ):
            self.state.state[
                "daily_highest_unrealized_usd"
            ] = unrealised

        # --------------------------------------------------
        # Trailing SL
        # --------------------------------------------------

        if decision.updated_stop_loss is not None:

            intended_sl = decision.updated_stop_loss
            intended_integer_R = decision.next_integer_R

            update_ok = False

            for _ in range(2):
                try:
                    self.exchange.update_sl(
                        symbol=open_position["symbol"],
                        side=open_position["side"],
                        qty=open_position["qty"],
                        new_stop_price=intended_sl,
                    )

                    verified = self.exchange.get_position()

                    if (
                        verified is not None
                        and verified.stop_loss is not None
                        and abs(verified.stop_loss - intended_sl) < 1e-8
                    ):
                        update_ok = True
                        break

                except Exception:
                    time.sleep(0.5)

            if not update_ok:
                send_warning(
                    "SL UPDATE VERIFICATION FAILED",
                    "Monitoring risk boundary."
                )

            else:
                # Commit integer trailing only AFTER verification
                if intended_integer_R is not None:
                    open_position["last_locked_R"] = (
                        intended_integer_R
                    )

            open_position["stop_loss"] = intended_sl

            msg_id = state_snapshot.get(
                "active_trade_panel_message_id"
            )

            if msg_id:
                panel_text = format_trade_panel(
                    symbol=open_position["symbol"],
                    side=open_position["side"],
                    entry_price=open_position["entry_price"],
                    stop_loss=open_position["stop_loss"],
                    qty=open_position["qty"],
                    risk_usd=open_position["risk_usd"],
                    status="OPEN 🔼",
                )
                edit_message(msg_id, panel_text)

        if decision.highest_profit_usd is not None:
            open_position["highest_profit_usd"] = (
                decision.highest_profit_usd
            )

        # Persist integer trailing state
        if "last_locked_R" in open_position:
            highest_R = (
                open_position["highest_profit_usd"]
                / open_position["risk_usd"]
            )
            open_position["last_locked_R"] = int(highest_R)

        self.state.update_open_position(open_position)
        self.state.save()

        # --------------------------------------------------
        # Risk violation
        # --------------------------------------------------

        if decision.violation and not self.exit_in_progress:

            self.exit_in_progress = True

            send_critical(
                "POSITION RISK VIOLATION",
                f"Reason: {decision.reason}\n\n"
                "Emergency exit sent.\n"
                "Engine halted."
            )

            self.emergency.execute(decision.reason)

            self.state.set_engine_state(
                engine_state=self.RISK_HALT,
                reason=decision.reason,
            )

            self.state.clear_open_position()
            self.state.save()
            self.safety.halt(decision.reason)

    # --------------------------------------------------
    # Close Handler
    # --------------------------------------------------

    def _handle_close(self, open_position):

        self.system_log.info("POSITION_CLOSED_CONFIRMED")

        trade_data = self.exchange.get_trade_realized_pnl(
            symbol=open_position["symbol"],
            since_timestamp=open_position.get("entry_timestamp"),
        )

        realized = trade_data["pnl"]
        exit_price = trade_data["exit_price"]

        self.state.update_daily_realized(realized)

        new_balance = self.exchange.get_available_balance()

        self.state.update_after_trade(
            balance=new_balance,
            open_position=None,
            last_trade=None,
        )

        msg_id = self.state.get_state().get(
            "active_trade_panel_message_id"
        )

        if msg_id:
            panel_text = format_trade_panel(
                symbol=open_position["symbol"],
                side=open_position["side"],
                entry_price=open_position["entry_price"],
                stop_loss=open_position["stop_loss"],
                qty=open_position["qty"],
                risk_usd=open_position["risk_usd"],
                status="CLOSED",
            ) + (
                f"Exit: {exit_price:.4f}\n"
                f"PnL: {realized:.2f} USD\n"
            )

            edit_message(msg_id, panel_text)

            self.state.state[
                "active_trade_panel_message_id"
            ] = None

        self.trade_log.info(
            f"TRADE_CLOSE | "
            f"symbol={open_position['symbol']} | "
            f"side={open_position['side']} | "
            f"entry={open_position['entry_price']:.4f} | "
            f"exit={exit_price:.4f} | "
            f"qty={open_position['qty']:.6f} | "
            f"pnl={realized:.2f}"
        )

        self.state.save()
        self.exit_in_progress = False
        self._commitment_reached = False
