# ==========================================================
# RECONCILIATION LIFECYCLE
# Synchronizes engine state with exchange truth
# ==========================================================
import time
from utils.telegram_notifier import send_trade_panel, format_trade_panel, edit_message

class ReconciliationLifecycle:
    """Reconcile engine memory with exchange position state."""

    def __init__(
        self,
        *,
        exchange,
        state,
        risk,
        universe,
        system_log,
        trade_log,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.universe = universe
        self.system_log = system_log
        self.trade_log = trade_log

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
        highest_profit_usd: float = 0.0,
        last_locked_R: int = 0,
    ):
        return {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "qty": qty,
            "stop_loss": stop_loss,
            "risk_usd": self.risk.RISK_PER_TRADE_USD,
            "highest_profit_usd": highest_profit_usd,
            "last_locked_R": last_locked_R,
            "entry_timestamp": entry_timestamp,
        }

    # --------------------------------------------------
    # Run
    # --------------------------------------------------

    def run(self, reason: str):

        engine_state = self.state.get_state().get("engine_state")
        if engine_state != "RUNNING":
            self.system_log.info(
                f"RECONCILIATION_SKIPPED | engine_state={engine_state}"
            )
            return None
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

                    self.system_log.info(
                        f"RECON_CLOSE_DETECTED | "
                        f"symbol={existing['symbol']}"
                    )

                    # --------------------------------------------------
                    # Orphan SL Cleanup
                    # --------------------------------------------------
                    try:
                        orders = self.exchange._get(
                            "/fapi/v1/openOrders",
                            {
                                "symbol": existing["symbol"],
                               "timestamp": int(time.time() * 1000),
                            },
                        )

                        for o in orders:
                            if (
                                o.get("type") == "STOP_MARKET"
                                and o.get("reduceOnly") is True
                            ):
                                try:
                                    self.exchange._delete(
                                        "/fapi/v1/order",
                                        {
                                            "symbol": existing["symbol"],
                                            "orderId": o["orderId"],
                                            "timestamp": int(time.time() * 1000),
                                        },
                                    )
                                    self.system_log.info(
                                        f"RECON_ORPHAN_SL_CANCELLED | "
                                        f"symbol={existing['symbol']}"
                                    )
                                except Exception as e:
                                    self.system_log.error(
                                        f"RECON_ORPHAN_SL_CANCEL_FAILED | {e}"
                                    )
                    except Exception as e:
                        self.system_log.error(
                            f"RECON_SL_CLEANUP_FETCH_FAILED | error={e}"
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
                        self.system_log.error(
                            f"RECON_CLOSE_PNL_FETCH_FAILED | error={e}"
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

                    # --------------------------------------------
                    # Update Telegram Trade Panel (Manual Close)
                    # --------------------------------------------
                    msg_id = self.state.get_state().get(
                        "active_trade_panel_message_id"
                    )

                    if msg_id:
                        last_step = existing.get("last_locked_R", 0)
                        step = 0.5

                        if last_step > 0:
                            locked_R = (last_step - 1) * step
                        else:
                            locked_R = 0.0

                        panel_text = format_trade_panel(
                            symbol=existing["symbol"],
                            side=existing["side"],
                            entry_price=existing["entry_price"],
                            stop_loss=existing["stop_loss"],
                            qty=existing["qty"],
                            risk_usd=existing["risk_usd"],
                            status="CLOSED (RECON)",
                        ) + (
                            f"Locked: +{locked_R:.1f}R\n"
                            f"Exit: {exit_price:.4f}\n"
                            f"PnL: {realized:.2f} USD\n"
                        )

                        edit_message(msg_id, panel_text)
                        self.state.clear_trade_panel_message_id()

                    # Prepare informational event (do NOT return yet)
                    manual_close_event = "MANUAL_CLOSE_DETECTED"


                # Clear state
                self.state.update_after_trade(
                    balance=self.state.get_state().get("balance", 0.0),
                    open_position=None,
                    last_trade=None,
                )

                # --------------------------------------------------
                # Governance Refresh on Flat Transition
                # Only trigger if reconciliation actually closed a position
                # --------------------------------------------------
                if existing:
                    try:
                        self.universe.maybe_reload(
                            exchange=self.exchange,
                            state=self.state,
                            force=True,
                        )
                    except Exception as e:
                        self.system_log.error(
                            f"UNIVERSE_RELOAD_AFTER_RECON_CLOSE_FAILED | {e}"
                        )

            # --------------------------------------------------
            # Position exists
            # --------------------------------------------------
            else:
                previous_state = self.state.get_open_position()
                restored_ts = None
                # Preserve trailing state BEFORE rebuild
                if previous_state:
                    highest_profit_usd = previous_state.get("highest_profit_usd", 0.0)
                    last_locked_R = previous_state.get("last_locked_R", 0)
                else:
                    highest_profit_usd = 0.0
                    last_locked_R = 0

                if previous_state:
                    restored_ts = previous_state.get("entry_timestamp")

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
                    highest_profit_usd=highest_profit_usd,
                    last_locked_R=last_locked_R,
                )

                # --------------------------------------------------
                # Capture PREVIOUS SL before state overwrite
                # --------------------------------------------------
                previous_sl = None
                if previous_state and previous_state.get("stop_loss") is not None:
                    previous_sl = previous_state.get("stop_loss")

                self.state.update_open_position(rebuilt)

                # --------------------------------------------------
                # SL Recovery
                # --------------------------------------------------
                if position.stop_loss is None:

                    self.system_log.error(
                        "POSITION_WITHOUT_SL | attempting recovery"
                    )

                    # --------------------------------------------------
                    # FIX: Preserve Trailed SL If State Exists
                    # --------------------------------------------------
                    # Use preserved SL from previous state if available
                    if previous_sl is not None:
                        intended_sl = previous_sl
                        self.system_log.info(
                            f"RECOVERY_USING_STATE_SL | "
                            f"symbol={position.symbol} | "
                            f"state_sl={intended_sl}"
                        )
                    else:
                        # --------------------------------------------------
                        # Deterministic SL reconstruction from R memory
                        # --------------------------------------------------

                        reconstructed = False

                        last_locked_R = rebuilt.get("last_locked_R", 0)

                        if last_locked_R and last_locked_R > 0:

                            locked_R = last_locked_R - 1

                            if locked_R >= 0:

                                risk_usd = rebuilt["risk_usd"]
                                qty = rebuilt["qty"]
                                entry = rebuilt["entry_price"]

                                locked_profit_usd = locked_R * risk_usd

                                if position.side == "LONG":
                                    intended_sl = entry + (locked_profit_usd / qty)
                                else:
                                    intended_sl = entry - (locked_profit_usd / qty)

                                reconstructed = True

                                self.system_log.info(
                                    f"RECOVERY_RECONSTRUCTED_SL | "
                                    f"symbol={position.symbol} | "
                                    f"last_locked_R={last_locked_R} | "
                                    f"intended_sl={intended_sl}"
                                )

                        if not reconstructed:

                            entry_plan = self.risk.build_entry_plan(
                                direction=position.side,
                                entry_price=position.entry_price,
                            )

                            intended_sl = entry_plan.initial_sl

                            self.system_log.error(
                                f"RECOVERY_FALLBACK_INITIAL_SL | "
                                f"symbol={position.symbol} | "
                                f"initial_sl={intended_sl}"
                            )

                    live_price = self.exchange.get_last_price(
                        position.symbol
                    )

                    if (
                        (position.side == "LONG" and intended_sl >= live_price)
                        or
                        (position.side == "SHORT" and intended_sl <= live_price)
                    ):
                        self.system_log.error(
                            "RECOVERY_SL_ALREADY_BREACHED"
                        )

                        raise RuntimeError("RECOVERY_SL_ALREADY_BREACHED")

                    try:
                        self.exchange.place_initial_sl(
                            symbol=position.symbol,
                            side=position.side,
                            qty=position.qty,
                            stop_price=intended_sl,
                        )
                    except Exception as e:
                        self.system_log.error(
                            f"RECOVERY_SL_PLACEMENT_FAILED | error={e}"
                        )
                        raise RuntimeError("RECOVERY_SL_PLACEMENT_FAILED")

                    verified = self.exchange.get_position()

                    if verified is None or verified.stop_loss is None:
                        self.system_log.error(
                            "RECOVERY_SL_VERIFICATION_FAILED"
                        )
                        raise RuntimeError("RECOVERY_SL_VERIFICATION_FAILED")

                    self.state.update_stop_loss(verified.stop_loss)
                    self.system_log.info("RECOVERY_SL_SUCCESS")
                    self.system_log.info(
                        f"RECOVERY_SL_CONFIRMED | "
                        f"symbol={position.symbol} | stop_loss={verified.stop_loss}"
                    )

                # --------------------------------------------------
                # Telegram Recovery
                # --------------------------------------------------
                if (
                    self.state.get_state().get("active_trade_panel_message_id")
                    is None
                ):
                    current_state = self.state.get_open_position()
                    panel = format_trade_panel(
                        symbol=position.symbol,
                        side=position.side,
                        entry_price=position.entry_price,
                        stop_loss=current_state["stop_loss"],
                        qty=position.qty,
                        risk_usd=rebuilt["risk_usd"],
                        status="OPEN (RECOVERED)",
                    )
                    msg_id = send_trade_panel(panel)
                    if msg_id:
                        self.state.set_trade_panel_message_id(msg_id)

            self.state.save()
            self.system_log.info("RECONCILIATION_SUCCESS")

            try:
                # Optional — if these attributes exist
                self.state.clear_shutdown_request()
            except Exception:
                pass

            # Note: intent & entry lifecycle reset is handled in core

        except Exception as e:
            self.system_log.error(
                f"RECONCILIATION_FAILED | "
                f"reason={reason} | "
                f"error={e}"
            )
            raise RuntimeError("RECONCILIATION_FAILED")
        # Success path
        return None
