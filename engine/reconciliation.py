# ==========================================================
# RECONCILIATION LIFECYCLE
# ==========================================================

from utils.telegram_notifier import send_critical, send_trade_panel, format_trade_panel


class ReconciliationLifecycle:
    """
    Reconcile engine state with exchange truth.
    """

    RISK_HALT = "RISK_HALT"
    INVARIANT_HALT = "INVARIANT_HALT"
    MANUAL_HALT = "MANUAL_HALT"
    FATAL_HALT = "FATAL_HALT"

    def __init__(
        self,
        *,
        exchange,
        state,
        risk,
        safety,
        system_log,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.safety = safety
        self.system_log = system_log

    # --------------------------------------------------
    # Canonical Open Position Builder
    # --------------------------------------------------

    def _build_open_position(
        self,
        *,
        symbol: str,
        side: str,
        entry_price: float,
        qty: float,
        stop_loss,
    ):
        return {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "qty": qty,
            "stop_loss": stop_loss,
            "risk_usd": self.risk.RISK_PER_TRADE_USD,
            "highest_profit_usd": 0.0,
            "last_locked_R": 0,
        }

    # --------------------------------------------------
    # Run
    # --------------------------------------------------

    def run(self, reason: str):

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

            # --------------------------------------------------
            # No position
            # --------------------------------------------------
            if position is None:

                self.state.update_after_trade(
                    balance=self.state.get_state().get("balance", 0.0),
                    open_position=None,
                    last_trade=None,
                )

                self.state.state["active_trade_panel_message_id"] = None

            # --------------------------------------------------
            # Position exists
            # --------------------------------------------------
            else:

                rebuilt = self._build_open_position(
                    symbol=position.symbol,
                    side=position.side,
                    entry_price=position.entry_price,
                    qty=position.qty,
                    stop_loss=position.stop_loss,
                )

                existing = self.state.get_open_position()

                if existing:
                    rebuilt["highest_profit_usd"] = existing.get(
                        "highest_profit_usd", 0.0
                    )
                    rebuilt["last_locked_R"] = existing.get(
                        "last_locked_R", 0
                    )

                self.state.state["open_position"] = rebuilt

                # --------------------------------------------------
                # SL Recovery
                # --------------------------------------------------
                if position.stop_loss is None:

                    self.system_log.critical(
                        "POSITION_WITHOUT_SL | attempting recovery"
                    )

                    entry_plan = self.risk.build_entry_plan(
                        direction=position.side,
                        entry_price=position.entry_price,
                    )

                    intended_sl = entry_plan.initial_sl

                    live_price = self.exchange.get_last_price(
                        position.symbol
                    )

                    if (
                        (position.side == "LONG" and intended_sl >= live_price)
                        or
                        (position.side == "SHORT" and intended_sl <= live_price)
                    ):
                        self.system_log.critical(
                            "RECOVERY_SL_ALREADY_BREACHED"
                        )

                        send_critical(
                            "RECOVERY SL BREACHED",
                            f"Symbol: {position.symbol}\n"
                            "Emergency exit required."
                        )

                        self.state.set_engine_state(
                            engine_state=self.RISK_HALT,
                            reason="RECOVERY_SL_BREACHED",
                        )
                        self.state.save()
                        self.safety.halt("RECOVERY_SL_BREACHED")
                        return

                    try:
                        self.exchange.place_initial_sl(
                            symbol=position.symbol,
                            side=position.side,
                            qty=position.qty,
                            stop_price=intended_sl,
                        )
                    except Exception as e:
                        self.system_log.critical(
                            f"RECOVERY_SL_PLACEMENT_FAILED | {e}"
                        )
                        send_critical(
                            "RECOVERY SL PLACEMENT FAILED",
                            f"{e}\n\nEngine halted."
                        )
                        self.state.set_engine_state(
                            engine_state=self.INVARIANT_HALT,
                            reason="RECOVERY_SL_PLACEMENT_FAILED",
                        )
                        self.state.save()
                        self.safety.halt("RECOVERY_SL_PLACEMENT_FAILED")
                        return

                    verified = self.exchange.get_position()

                    if verified is None or verified.stop_loss is None:
                        self.system_log.critical(
                            "RECOVERY_SL_VERIFICATION_FAILED"
                        )
                        send_critical(
                            "RECOVERY SL VERIFICATION FAILED",
                            f"Symbol: {position.symbol}\n"
                            "Engine halting."
                        )
                        self.state.set_engine_state(
                            engine_state=self.INVARIANT_HALT,
                            reason="RECOVERY_SL_VERIFICATION_FAILED",
                        )
                        self.state.save()
                        self.safety.halt("RECOVERY_SL_VERIFICATION_FAILED")
                        return

                    self.state.state["open_position"]["stop_loss"] = intended_sl
                    self.system_log.info("RECOVERY_SL_SUCCESS")

                # --------------------------------------------------
                # Telegram Recovery
                # --------------------------------------------------
                if (
                    self.state.state.get("active_trade_panel_message_id")
                    is None
                ):
                    panel = format_trade_panel(
                        symbol=position.symbol,
                        side=position.side,
                        entry_price=position.entry_price,
                        stop_loss=position.stop_loss,
                        qty=position.qty,
                        risk_usd=rebuilt["risk_usd"],
                        status="OPEN (RECOVERED)",
                    )
                    msg_id = send_trade_panel(panel)
                    if msg_id:
                        self.state.state[
                            "active_trade_panel_message_id"
                        ] = msg_id

            self.state.save()
            self.system_log.info("RECONCILIATION_SUCCESS")

            # Reset lifecycle runtime state (original engine behavior)
            # These must be reset on reconciliation
            # so entry/intent lifecycle resumes cleanly.
            try:
                # Optional — if these attributes exist
                self.state.state["shutdown_requested"] = False
            except Exception:
                pass

            # Note: intent & entry lifecycle reset is handled in core

        except Exception as e:
            self.system_log.critical(
                f"RECONCILIATION_FAILED | error={e}"
            )
            send_critical(
                "RECONCILIATION FAILED",
                f"{e}\n\nEngine halted."
            )
            self.safety.halt("RECONCILIATION_FAILED")
            raise
