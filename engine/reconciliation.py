# ==========================================================
# RECONCILIATION LIFECYCLE
# Synchronizes engine state with exchange truth
# ==========================================================
import time
from config import (
    EXECUTION_MODE,
    STOP_TRIGGER_GRACE_SECONDS,
    STOP_TRIGGER_POLL_INTERVAL_SECONDS,
    TRADING_ENV,
)
from execution.outcome_builder import build_execution_outcome
from utils.telegram_notifier import (
    send_trade_panel,
    format_trade_panel,
    format_trade_close_panel,
    edit_message,
)

class ReconciliationLifecycle:
    """Reconcile engine memory with exchange position state."""

    def __init__(
        self,
        *,
        exchange,
        state,
        risk,
        emergency,
        system_log,
        trade_log,
        outcome_publisher=None,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.emergency = emergency
        self.system_log = system_log
        self.trade_log = trade_log
        self.outcome_publisher = outcome_publisher


    @staticmethod
    def _number(value, default: float = 0.0) -> float:
        """Return a log-safe float for partially populated stale state."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _cleanup_orphan_stop_orders(self, symbol: str) -> None:
        """Cancel legacy REST stop orders only when the adapter supports it.

        PaperExchange intentionally exposes no private HTTP helpers. Calling
        ``_get``/``_delete`` unconditionally made LIVE+SHADOW reconciliation
        fail before it could repair stale engine state.
        """
        raw_get = getattr(self.exchange, "_get", None)
        raw_delete = getattr(self.exchange, "_delete", None)
        if not callable(raw_get) or not callable(raw_delete):
            self.system_log.info(
                "RECON_ORPHAN_SL_CLEANUP_NOT_APPLICABLE | "
                f"adapter={type(self.exchange).__name__} | symbol={symbol}"
            )
            return

        try:
            orders = raw_get(
                "/fapi/v1/openOrders",
                {
                    "symbol": symbol,
                    "timestamp": int(time.time() * 1000),
                },
            )
        except Exception as exc:
            self.system_log.error(
                f"RECON_SL_CLEANUP_FETCH_FAILED | error={exc}"
            )
            return

        for order in orders or []:
            if (
                order.get("type") != "STOP_MARKET"
                or order.get("reduceOnly") is not True
            ):
                continue
            try:
                raw_delete(
                    "/fapi/v1/order",
                    {
                        "symbol": symbol,
                        "orderId": order["orderId"],
                        "timestamp": int(time.time() * 1000),
                    },
                )
                self.system_log.info(
                    f"RECON_ORPHAN_SL_CANCELLED | symbol={symbol}"
                )
            except Exception as exc:
                self.system_log.error(
                    f"RECON_ORPHAN_SL_CANCEL_FAILED | error={exc}"
                )

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
        structure_fingerprint=None,
        pattern=None,
        sl_status=None,
        mae: float = 0.0,
        mfe: float = 0.0,
        risk_usd=None,
        initial_risk_usd=None,
        initial_stop_loss=None,
        entry_order_id=None,
        entry_client_order_id=None,
        sl_order_id=None,
        proposal_id=None,
        candidate_observation_id=None,
        decision_batch_id=None,
        market_event_id=None,
        strategy_version=None,
        strategy_variant_id=None,
        model_version=None,
        selection_authority=None,
        paper_canary_model_id=None,
        paper_risk_multiplier=1.0,
        paper_allocation_id=None,
        experiment_context=None,
    ):
        if sl_status is None:
            sl_status = "VERIFIED" if stop_loss is not None else "MISSING"

        if risk_usd is None:
            risk_usd = self.risk.RISK_PER_TRADE_USD
        if initial_risk_usd is None:
            initial_risk_usd = risk_usd
        if initial_stop_loss is None:
            initial_stop_loss = stop_loss

        return {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "qty": qty,
            "stop_loss": stop_loss,
            "initial_stop_loss": initial_stop_loss,
            "risk_usd": risk_usd,
            "initial_risk_usd": initial_risk_usd,
            "entry_order_id": entry_order_id,
            "entry_client_order_id": entry_client_order_id,
            "sl_order_id": sl_order_id,
            "proposal_id": proposal_id,
            "highest_profit_usd": highest_profit_usd,
            "last_locked_R": last_locked_R,
            "entry_timestamp": entry_timestamp,
            "structure_fingerprint": structure_fingerprint,
            "pattern": pattern,
            "sl_status": sl_status,
            "mae": mae,
            "mfe": mfe,
            "candidate_observation_id": candidate_observation_id,
            "decision_batch_id": decision_batch_id,
            "market_event_id": market_event_id,
            "strategy_version": strategy_version,
            "strategy_variant_id": strategy_variant_id,
            "model_version": model_version,
            "selection_authority": selection_authority,
            "paper_canary_model_id": paper_canary_model_id,
            "paper_risk_multiplier": paper_risk_multiplier,
            "paper_allocation_id": paper_allocation_id,
            "experiment_context": experiment_context,
        }

    # --------------------------------------------------
    # Run
    # --------------------------------------------------

    def run(self, reason: str):

        engine_state = self.state.get_state().get("engine_state")
        if engine_state != "RUNNING":
            # Reconciliation protects existing exchange exposure and repairs
            # persisted truth. Entry permission must never suppress it.
            self.system_log.info(
                f"RECONCILIATION_RUNNING_WITH_ENTRIES_DISABLED | "
                f"engine_state={engine_state}"
            )

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
                    self._cleanup_orphan_stop_orders(existing["symbol"])

                    realized = 0.0
                    exit_price = 0.0
                    exit_reason = "RECONCILIATION"

                    try:
                        trade_data = self.exchange.get_trade_realized_pnl(
                            symbol=existing["symbol"],
                            since_timestamp=existing.get("entry_timestamp"),
                        )

                        realized = trade_data["pnl"]
                        exit_price = trade_data["exit_price"]
                        if trade_data.get("exit_reason"):
                            exit_reason = str(
                                trade_data["exit_reason"]
                            ).strip().upper()

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
                        f"entry={self._number(existing.get('entry_price')):.4f} | "
                        f"exit={self._number(exit_price):.4f} | "
                        f"qty={self._number(existing.get('qty')):.6f} | "
                        f"pnl={self._number(realized):.2f} | "
                        f"exit_reason={exit_reason} | "
                        f"source=RECON"
                    )

                    initial_risk_usd = self._number(
                        existing.get(
                            "initial_risk_usd",
                            existing.get("risk_usd"),
                        )
                    )
                    r_multiple = (
                        self._number(realized) / initial_risk_usd
                        if initial_risk_usd > 0 else 0.0
                    )
                    entry_timestamp = existing.get("entry_timestamp")
                    holding_seconds = (
                        max(
                            0,
                            int(
                                time.time()
                                - float(entry_timestamp) / 1000.0
                            ),
                        )
                        if entry_timestamp else 0
                    )
                    candidate_observation_id = existing.get(
                        "candidate_observation_id"
                    )
                    closed_timestamp = int(time.time() * 1000)
                    execution_outcome = None
                    execution_outcome_id = None
                    outcome_delivered = False
                    learning_recorded = False

                    if self.outcome_publisher is not None:
                        try:
                            execution_outcome = build_execution_outcome(
                                open_position=existing,
                                environment=TRADING_ENV,
                                execution_mode=EXECUTION_MODE,
                                exit_price=self._number(exit_price),
                                realized_pnl_usd=self._number(realized),
                                exit_reason=exit_reason,
                                closed_timestamp=closed_timestamp,
                                holding_seconds=holding_seconds,
                            )
                            execution_outcome_id = execution_outcome.outcome_id
                        except Exception as exc:
                            self.system_log.error(
                                "RECON_EXECUTION_OUTCOME_BUILD_FAILED | "
                                f"symbol={existing['symbol']} | "
                                f"error={type(exc).__name__}:{exc}"
                            )
                    elif candidate_observation_id:
                        self.system_log.error(
                            "RECON_EXECUTION_OUTCOME_PUBLISHER_UNAVAILABLE | "
                            f"symbol={existing['symbol']}"
                        )

                    reconciled_last_trade = {
                        "symbol": existing.get("symbol"),
                        "side": existing.get("side"),
                        "entry_price": self._number(
                            existing.get("entry_price")
                        ),
                        "exit_price": self._number(exit_price),
                        "qty": self._number(existing.get("qty")),
                        "pnl": self._number(realized),
                        "r_multiple": r_multiple,
                        "holding_time": holding_seconds,
                        "entry_timestamp": entry_timestamp,
                        "closed_timestamp": closed_timestamp,
                        "exit_reason": exit_reason,
                        "candidate_observation_id": (
                            candidate_observation_id
                        ),
                        "decision_batch_id": existing.get(
                            "decision_batch_id"
                        ),
                        "market_event_id": existing.get(
                            "market_event_id"
                        ),
                        "strategy_version": existing.get(
                            "strategy_version"
                        ),
                        "strategy_variant_id": existing.get(
                            "strategy_variant_id"
                        ),
                        "model_version": existing.get(
                            "model_version"
                        ),
                        "experiment_context": existing.get(
                            "experiment_context"
                        ),
                        "execution_outcome_id": execution_outcome_id,
                        "outcome_delivery_status": (
                            "DELIVERED" if outcome_delivered else "PENDING"
                        ),
                        "learning_recorded": learning_recorded,
                    }

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

                        initial_risk_usd = float(
                            existing.get("initial_risk_usd")
                            or existing.get("risk_usd")
                            or 0.0
                        )
                        r_multiple = (
                            float(realized) / initial_risk_usd
                            if initial_risk_usd > 0
                            else 0.0
                        )
                        panel_text = format_trade_close_panel(
                            symbol=existing.get("symbol", "UNKNOWN"),
                            side=existing.get("side", "UNKNOWN"),
                            entry_price=existing.get("entry_price"),
                            initial_stop_loss=existing.get(
                                "initial_stop_loss",
                                existing.get("stop_loss"),
                            ),
                            final_stop_loss=existing.get("stop_loss"),
                            qty=existing.get("qty"),
                            risk_usd=initial_risk_usd,
                            exit_price=exit_price,
                            realized_pnl=realized,
                            r_multiple=r_multiple,
                            status="CLOSED (RECON)",
                            exit_reason=exit_reason,
                        )

                        edit_message(msg_id, panel_text)
                        self.state.clear_trade_panel_message_id()

                    # Prepare informational event (do NOT return yet)
                    manual_close_event = "MANUAL_CLOSE_DETECTED"


                # Clear state
                self.state.update_after_trade(
                    balance=self.state.get_state().get("balance", 0.0),
                    open_position=None,
                    last_trade=(
                        reconciled_last_trade if existing else None
                    ),
                )

                if existing:
                    # Persist the flat/accounting truth before attempting any
                    # Observation-side learning delivery.
                    self.state.save()

                    if execution_outcome is not None:
                        try:
                            outcome_delivered = bool(
                                self.outcome_publisher.publish(
                                    execution_outcome
                                )
                            )
                        except Exception as exc:
                            self.system_log.error(
                                "RECON_EXECUTION_OUTCOME_PUBLISH_FAILED | "
                                f"symbol={existing['symbol']} | "
                                f"error={type(exc).__name__}:{exc}"
                            )

                        reconciled_last_trade[
                            "outcome_delivery_status"
                        ] = (
                            "DELIVERED"
                            if outcome_delivered
                            else "PENDING"
                        )
                        reconciled_last_trade["learning_recorded"] = bool(
                            outcome_delivered
                            and candidate_observation_id
                        )
                        self.state.update_after_trade(
                            balance=self.state.get_state().get(
                                "balance", 0.0
                            ),
                            open_position=None,
                            last_trade=reconciled_last_trade,
                        )
                        self.state.save()


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
                    mae = previous_state.get("mae", 0.0)
                    mfe = previous_state.get("mfe", 0.0)
                else:
                    highest_profit_usd = 0.0
                    last_locked_R = 0
                    mae = 0.0
                    mfe = 0.0

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
                    structure_fingerprint=(
                        previous_state.get("structure_fingerprint")
                        if previous_state
                        else getattr(
                            position, "structure_fingerprint", None
                        )
                    ),
                    pattern=(
                        previous_state.get("pattern")
                        if previous_state
                        else getattr(position, "pattern", None)
                    ),
                    mae=mae,
                    mfe=mfe,
                    risk_usd=(
                        previous_state.get("risk_usd")
                        if previous_state
                        else self.risk.RISK_PER_TRADE_USD
                    ),
                    initial_risk_usd=(
                        previous_state.get(
                            "initial_risk_usd",
                            previous_state.get("risk_usd"),
                        )
                        if previous_state
                        else self.risk.RISK_PER_TRADE_USD
                    ),
                    initial_stop_loss=(
                        previous_state.get(
                            "initial_stop_loss",
                            previous_state.get("stop_loss"),
                        )
                        if previous_state
                        else position.stop_loss
                    ),
                    entry_order_id=(
                        previous_state.get("entry_order_id")
                        if previous_state
                        else None
                    ),
                    entry_client_order_id=(
                        previous_state.get("entry_client_order_id")
                        if previous_state
                        else None
                    ),
                    sl_order_id=(
                        self.exchange.get_active_sl_order_id()
                        if position.stop_loss is not None
                        else None
                    ),
                    proposal_id=(
                        previous_state.get("proposal_id")
                        if previous_state else getattr(
                            position, "proposal_id", None
                        )
                    ),
                    candidate_observation_id=(
                        previous_state.get("candidate_observation_id")
                        if previous_state else getattr(
                            position,
                            "candidate_observation_id",
                            None,
                        )
                    ),
                    decision_batch_id=(
                        previous_state.get("decision_batch_id")
                        if previous_state else getattr(
                            position, "decision_batch_id", None
                        )
                    ),
                    market_event_id=(
                        previous_state.get("market_event_id")
                        if previous_state else getattr(
                            position, "market_event_id", None
                        )
                    ),
                    strategy_version=(
                        previous_state.get("strategy_version")
                        if previous_state else getattr(
                            position, "strategy_version", None
                        )
                    ),
                    strategy_variant_id=(
                        previous_state.get("strategy_variant_id")
                        if previous_state else getattr(
                            position, "strategy_variant_id", None
                        )
                    ),
                    model_version=(
                        previous_state.get("model_version")
                        if previous_state else getattr(
                            position, "model_version", None
                        )
                    ),
                    selection_authority=(
                        previous_state.get("selection_authority")
                        if previous_state else getattr(
                            position, "selection_authority", None
                        )
                    ),
                    paper_canary_model_id=(
                        previous_state.get("paper_canary_model_id")
                        if previous_state else getattr(
                            position, "paper_canary_model_id", None
                        )
                    ),
                    paper_risk_multiplier=(
                        previous_state.get("paper_risk_multiplier", 1.0)
                        if previous_state else getattr(
                            position, "paper_risk_multiplier", 1.0
                        )
                    ),
                    paper_allocation_id=(
                        previous_state.get("paper_allocation_id")
                        if previous_state else getattr(
                            position, "paper_allocation_id", None
                        )
                    ),
                    experiment_context=(
                        previous_state.get("experiment_context")
                        if previous_state else getattr(
                            position, "experiment_context", None
                        )
                    ),
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
                        self.system_log.warning(
                            "RECOVERY_SL_ALREADY_BREACHED | "
                            f"symbol={position.symbol} | action=WAIT_FOR_SETTLEMENT"
                        )

                        deadline = time.monotonic() + STOP_TRIGGER_GRACE_SECONDS
                        while time.monotonic() < deadline:
                            time.sleep(STOP_TRIGGER_POLL_INTERVAL_SECONDS)
                            settled = self.exchange.get_position()
                            if settled is None:
                                self.system_log.info(
                                    "STOP_TRIGGER_SETTLED_DURING_RECON | "
                                    f"symbol={position.symbol}"
                                )
                                return self.run(reason="STOP_TRIGGER_SETTLED")

                        self.system_log.error(
                            "RECOVERY_BREACHED_SL_POSITION_STILL_OPEN | "
                            f"symbol={position.symbol} | action=EMERGENCY_EXIT"
                        )
                        self.emergency.execute(
                            reason=f"RECOVERY_BREACHED_SL:{position.symbol}"
                        )
                        return self.run(reason="RECOVERY_BREACHED_SL_FLATTENED")

                    try:
                        sl_ref = self.exchange.place_initial_sl(
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

                    rebuilt["stop_loss"] = verified.stop_loss
                    rebuilt["sl_status"] = "RECOVERED"
                    rebuilt["sl_order_id"] = sl_ref["algo_id"]
                    self.state.update_open_position(rebuilt)
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
