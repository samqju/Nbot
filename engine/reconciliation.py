# ==========================================================
# RECONCILIATION LIFECYCLE
# ==========================================================
import time
from engine.events import EngineEvent
from utils.telegram_notifier import send_critical, send_trade_panel, format_trade_panel
from utils.logger import trade_logger

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
        self.trade_log = trade_logger()

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
        entry_timestamp=None,
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
            "entry_timestamp": entry_timestamp,
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

                existing = self.state.get_open_position()

                if existing:

                    self.system_log.warning(
                        f"RECON_CLOSE_DETECTED | "
                        f"symbol={existing['symbol']}"
                   )

                    realized = 0.0
                    exit_price = 0.0

                    try:
                        trade_data = self.exchange.get_trade_realized_pnl(
                            symbol=existing["symbol"],
                            since_timestamp=existing.get("entry_timestamp"),
                        )

                        realized = trade_data["pnl"]
                        exit_price = trade_data["exit_price"]

                    except Exception as e:
                        self.system_log.critical(
                            f"RECON_CLOSE_FETCH_FAILED | error={e}"
                        )

                    # Update daily accounting
                    self.state.update_daily_realized(realized)

                    # Log close in trades.log
                    self.trade_log.info(
                        f"TRADE_CLOSE | "
                        f"symbol={existing['symbol']} | "
                        f"side={existing['side']} | "
                        f"entry={existing['entry_price']:.4f} | "
                        f"exit={exit_price:.4f} | "
                        f"qty={existing['qty']:.6f} | "
                        f"pnl={realized:.2f} | "
                        f"source=RECON"
                    )

                # Clear state
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
                existing = self.state.get_open_position()
                restored_ts = None
                if existing:
                    restored_ts = existing.get("entry_timestamp")

                # CRITICAL FIX: If timestamp missing, reconstruct safely
                if restored_ts is None:
                    restored_ts = int(time.time() * 1000)

                rebuilt = self._build_open_position(
                    symbol=position.symbol,
                    side=position.side,
                    entry_price=position.entry_price,
                    qty=position.qty,
                    stop_loss=position.stop_loss,
                    entry_timestamp=restored_ts,
                )

                # --------------------------------------------------
                # Preserve trailing state (MONEY FIX)
                # --------------------------------------------------
                if existing:
                    rebuilt["highest_profit_usd"] = existing.get(
                        "highest_profit_usd", 0.0
                    )
                    rebuilt["last_locked_R"] = existing.get(
                        "last_locked_R", 0
                    )

                # Ensure stop_loss key always exists
                if rebuilt.get("stop_loss") is None:
                    self.system_log.warning(
                        "RECON_POSITION_WITHOUT_SL | recovery required"
                    )

                existing = self.state.get_open_position()

                if existing:
                    rebuilt["highest_profit_usd"] = existing.get(
                        "highest_profit_usd", 0.0
                    )
                    rebuilt["last_locked_R"] = existing.get(
                        "last_locked_R", 0
                    )

                self.state.update_open_position(rebuilt)

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
                    self.system_log.info(
                        f"RECOVERY_SL_ATTEMPT | "
                        f"symbol={position.symbol} | "
                        f"intended_sl={intended_sl}"
                    )

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

                        return EngineEvent(
                            severity="CRITICAL",
                            category="SL",
                            money_at_risk=True,
                            requires_flatten=True,
                            requires_disable=True,
                            retryable=False,
                            reason="RECOVERY_SL_BREACHED",
                        )

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
                        return EngineEvent(
                            severity="CRITICAL",
                            category="SL",
                            money_at_risk=True,
                            requires_flatten=False,
                            requires_disable=True,
                            retryable=False,
                            reason="RECOVERY_SL_PLACEMENT_FAILED",
                        )

                    verified = self.exchange.get_position()

                    if verified is None or verified.stop_loss is None:
                        self.system_log.critical(
                            "RECOVERY_SL_VERIFICATION_FAILED"
                        )
                        return EngineEvent(
                            severity="CRITICAL",
                            category="SL",
                            money_at_risk=True,
                            requires_flatten=False,
                            requires_disable=True,
                            retryable=False,
                            reason="RECOVERY_SL_VERIFICATION_FAILED",
                        )
                    self.state.state["open_position"]["stop_loss"] = intended_sl
                    self.system_log.info("RECOVERY_SL_SUCCESS")
                    self.system_log.info(
                        f"RECOVERY_SL_CONFIRMED | "
                        f"symbol={position.symbol} | "
                        f"stop_loss={verified.stop_loss}"
                    )

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
                        self.state.set_trade_panel_message_id(msg_id)

            self.state.save()
            self.system_log.info("RECONCILIATION_SUCCESS")

            # Reset lifecycle runtime state (original engine behavior)
            # These must be reset on reconciliation
            # so entry/intent lifecycle resumes cleanly.
            try:
                # Optional — if these attributes exist
                self.state.clear_shutdown_request()
            except Exception:
                pass

            # Note: intent & entry lifecycle reset is handled in core

        except Exception as e:
            self.system_log.critical(
                f"RECONCILIATION_FAILED | error={e}"
            )
            return EngineEvent(
                severity="CRITICAL",
                category="INFRA",
                money_at_risk=self.state.get_open_position() is not None,
                requires_flatten=False,
                requires_disable=True,
                retryable=False,
                reason="RECONCILIATION_FAILED",
            )

        # Success path
        return None
