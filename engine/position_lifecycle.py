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
from config import (
    TRADING_ENV,
    EXECUTION_MODE,
    STOP_TRIGGER_GRACE_SECONDS,
    STOP_TRIGGER_POLL_INTERVAL_SECONDS,
)
from execution.outcome_builder import build_execution_outcome
from utils.telegram_notifier import (
    send_critical,
    send_warning,
    edit_message,
    format_trade_close_panel,
)


class PositionLifecycle:

    def __init__(
        self,
        *,
        exchange,
        state,
        risk,
        emergency,
        reconciliation,
        universe,
        system_log,
        trade_log,
        outcome_publisher=None,
    ):
        self.exchange = exchange
        self.state = state
        self.risk = risk
        self.emergency = emergency
        self.reconciliation = reconciliation
        self.universe = universe
        self.system_log = system_log
        self.trade_log = trade_log
        self.outcome_publisher = outcome_publisher
        self.exit_in_progress = False

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
        entry_price = open_position["entry_price"]
        qty = open_position["qty"]
        side = open_position["side"]
        if side == "LONG":
            pnl_move = (price - entry_price) * qty
        else:
            pnl_move = (entry_price - price) * qty

        # update MFE (max favorable excursion)
        open_position["mfe"] = max(open_position.get("mfe", pnl_move), pnl_move)

        # update MAE (max adverse excursion)
        open_position["mae"] = min(open_position.get("mae", pnl_move), pnl_move)

        exchange_position = self.exchange.get_position()

        # --------------------------------------------------
        # Live SL Missing → reconciliation recovery
        # --------------------------------------------------

        if (
            exchange_position
            and exchange_position.stop_loss is None
        ):
            if not getattr(self, "_sl_recovery_in_progress", False):
                self._sl_recovery_in_progress = True
                self.system_log.warning(
                    f"LIVE_SL_MISSING_DETECTED | symbol={exchange_position.symbol} | "
                    f"action=WAIT_FOR_SETTLEMENT"
                )
                try:
                    deadline = time.monotonic() + STOP_TRIGGER_GRACE_SECONDS
                    while time.monotonic() < deadline:
                        time.sleep(STOP_TRIGGER_POLL_INTERVAL_SECONDS)
                        settled = self.exchange.get_position()
                        if settled is None:
                            self.system_log.info(
                                f"STOP_TRIGGER_SETTLED | symbol={symbol}"
                            )
                            self._handle_close(open_position)
                            return
                        if settled.stop_loss is not None:
                            self.system_log.info(
                                f"LIVE_SL_REAPPEARED | symbol={symbol} | "
                                f"stop_loss={settled.stop_loss}"
                            )
                            return

                    self.reconciliation.run(reason="LIVE_SL_MISSING")
                finally:
                    self._sl_recovery_in_progress = False
            return

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
            self.state.update_daily_highest_unrealized(unrealised)

        # --------------------------------------------------
        # Trailing SL
        # --------------------------------------------------

        if decision.updated_stop_loss is not None:

            intended_sl = decision.updated_stop_loss
            intended_integer_R = decision.next_integer_R

            self.system_log.info(
                f"SL_UPDATE_ATTEMPT | "
                f"symbol={symbol} | "
                f"current_sl={open_position['stop_loss']:.8f} | "
                f"intended_sl={intended_sl} | "
                f"price={price} | "
                f"next_integer_R={intended_integer_R}"
            )

            update_ok = False
            expected_sl = None

            for attempt in range(2):
                try:
                    sl_ref = self.exchange.update_sl(
                        symbol=open_position["symbol"],
                        side=open_position["side"],
                        qty=open_position["qty"],
                        new_stop_price=intended_sl,
                    )

                    verified = self.exchange.get_position()

                    if verified is None:
                        self.system_log.error(
                            f"SL_VERIFY_POSITION_NONE | "
                            f"symbol={symbol} | "
                            f"intended_sl={intended_sl}"
                        )
                        continue

                    # Adapter is SINGLE source of quantization truth
                    expected_sl = self.exchange.quantize_price(
                        symbol,
                        intended_sl,
                    )

                    if (
                        verified.stop_loss is not None
                        and abs(
                            verified.stop_loss - expected_sl
                        ) < 1e-12
                    ):
                        update_ok = True
                        open_position["sl_order_id"] = sl_ref["algo_id"]
                        self.system_log.info(
                            f"SL_UPDATE_VERIFIED | "
                            f"symbol={symbol} | "
                            f"stop_loss={verified.stop_loss}"
                        )
                        break
                    else:
                        self.system_log.error(
                            f"SL_VERIFICATION_MISMATCH | "
                            f"symbol={symbol} | "
                            f"expected={expected_sl} | "
                            f"actual={getattr(verified, 'stop_loss', None)}"
                        )

                except Exception as e:
                    self.system_log.error(
                        f"SL_UPDATE_EXCEPTION | "
                        f"symbol={symbol} | "
                        f"intended_sl={intended_sl} | "
                        f"attempt={attempt+1} | "
                        f"error={type(e).__name__}:{e}"
                    )
                    time.sleep(0.5)

            if not update_ok:

                send_warning(
                    "SL UPDATE VERIFICATION FAILED",
                    "Verifying whether exchange protection still exists."
                )

                try:
                    exchange_pos = self.exchange.get_position()
                except Exception as verify_error:
                    self.system_log.error(
                        f"SL_UPDATE_FINAL_POSITION_CHECK_FAILED | "
                        f"symbol={symbol} | error={verify_error}"
                    )
                    self.emergency.execute(
                        reason=f"SL_UPDATE_OUTCOME_UNKNOWN:{symbol}"
                    )
                    raise RuntimeError(
                        f"SL_UPDATE_OUTCOME_UNKNOWN | symbol={symbol}"
                    ) from verify_error

                # The position may have closed while the stop update was in
                # flight. Process the close instead of attempting to flatten
                # an already-flat account.
                if exchange_pos is None:
                    self.system_log.info(
                        f"SL_UPDATE_POSITION_CLOSED | symbol={symbol}"
                    )
                    self._handle_close(open_position)
                    return

                exchange_sl = getattr(exchange_pos, "stop_loss", None)

                self.system_log.error(
                    f"SL_UPDATE_FAILED | "
                    f"symbol={symbol} | "
                    f"intended_sl={intended_sl} | "
                    f"exchange_sl={exchange_sl}"
                )

                # update_sl may cancel the old protective order before a new
                # one is accepted. Never continue managing an exposed
                # position when exchange truth shows no stop protection.
                if exchange_sl is None:
                    self.emergency.execute(
                        reason=f"SL_UPDATE_LEFT_POSITION_UNPROTECTED:{symbol}"
                    )
                    raise RuntimeError(
                        f"SL_UPDATE_LEFT_POSITION_UNPROTECTED | symbol={symbol}"
                    )

                # A protective stop still exists, but the requested trailing
                # level was not confirmed. Synchronize local state to the
                # actual exchange stop and do not advance last_locked_R.
                open_position["stop_loss"] = exchange_sl
                open_position["sl_status"] = "VERIFIED"

            else:
                # Mutate the local canonical snapshot only after exchange
                # confirmation. This same object is persisted below.
                #
                # Do not update StateManager separately here: the final
                # update_open_position(open_position) call would otherwise
                # overwrite the confirmed SL with this snapshot's old value.
                open_position["stop_loss"] = expected_sl
                open_position["sl_status"] = "VERIFIED"

                if intended_integer_R is not None:
                    open_position["last_locked_R"] = intended_integer_R


        if decision.highest_profit_usd is not None:
            open_position["highest_profit_usd"] = (
                decision.highest_profit_usd
            )

        self.state.update_open_position(open_position)
        self.state.save()

        # --------------------------------------------------
        # Risk violation
        # --------------------------------------------------

        if decision.violation and not self.exit_in_progress:
            self.exit_in_progress = True
            self.system_log.error(
                f"POSITION_RISK_VIOLATION | "
                f"symbol={open_position['symbol']} | "
                f"reason={decision.reason}"
            )

            try:
                self.emergency.execute(
                    reason=(
                        f"POSITION_RISK_VIOLATION:"
                        f"{open_position['symbol']}:"
                        f"{decision.reason}"
                    )
                )
            except Exception as emergency_error:
                self.system_log.critical(
                    f"POSITION_RISK_EMERGENCY_FAILED | "
                    f"symbol={open_position['symbol']} | "
                    f"reason={decision.reason} | "
                    f"error={emergency_error}"
                )
                raise RuntimeError(
                    f"POSITION_RISK_EMERGENCY_FAILED | "
                    f"symbol={open_position['symbol']} | "
                    f"reason={decision.reason}"
                ) from emergency_error
            finally:
                self.exit_in_progress = False

            raise RuntimeError(
                f"POSITION_RISK_VIOLATION_FLATTENED | "
                f"{decision.reason}"
            )

    # --------------------------------------------------
    # Close Handler
    # --------------------------------------------------

    def _handle_close(self, open_position):

        self.system_log.info("POSITION_CLOSED_CONFIRMED")

        realized = None
        exit_price = None
        exit_reason = "EXCHANGE_POSITION_CLOSED"

        for attempt in range(3):
            try:
                trade_data = self.exchange.get_trade_realized_pnl(
                    symbol=open_position["symbol"],
                    since_timestamp=open_position.get("entry_timestamp"),
                )

                realized = trade_data["pnl"]
                exit_price = trade_data["exit_price"]
                reported_reason = trade_data.get("exit_reason")
                if reported_reason:
                    exit_reason = str(reported_reason).strip().upper()

                self.system_log.info(
                    f"POSITION_CLOSE_DETAILS | "
                    f"symbol={open_position['symbol']} | "
                    f"entry={open_position['entry_price']} | "
                    f"exit={exit_price} | "
                    f"pnl={realized} | "
                    f"exit_reason={exit_reason}"
                )

                if exit_price is not None:
                    break

                self.system_log.error(
                    f"CLOSE_DETAILS_DELAYED | "
                    f"symbol={open_position['symbol']} | "
                    f"attempt={attempt+1}"
                )

                time.sleep(0.5)

            except Exception as e:
                self.system_log.error(
                    f"CLOSE_FETCH_EXCEPTION | "
                    f"symbol={open_position['symbol']} | "
                    f"attempt={attempt+1} | error={e}"
                )
                time.sleep(0.5)

        if exit_price is None:
            self.system_log.error(
                f"CLOSE_DETAILS_UNAVAILABLE | "
                f"symbol={open_position['symbol']}"
            )
            exit_price = 0.0
            realized = 0.0

        self.state.update_daily_realized(realized)
        # --------------------------------------------------
        # Compute trade experiment metrics
        # --------------------------------------------------

        # MAE and MFE are accumulated as USD PnL values, so their R-unit
        # denominator must also be USD. Use the immutable entry-risk basis;
        # the current stop may have trailed and is not a valid historical
        # denominator. Realized PnL includes the exchange-reported outcome.
        initial_risk_usd = float(
            open_position.get(
                "initial_risk_usd",
                open_position.get("risk_usd", 0.0),
            )
            or 0.0
        )

        if initial_risk_usd > 0:
            r_multiple = float(realized) / initial_risk_usd
            mae_r = float(open_position.get("mae", 0.0)) / initial_risk_usd
            mfe_r = float(open_position.get("mfe", 0.0)) / initial_risk_usd
        else:
            r_multiple = 0.0
            mae_r = 0.0
            mfe_r = 0.0

        # Entry timestamps are stored in milliseconds; time.time() is seconds.
        entry_ts = open_position.get("entry_timestamp")
        holding_seconds = (
            max(0, int(time.time() - (float(entry_ts) / 1000.0)))
            if entry_ts
            else 0
        )

        new_balance = self.exchange.get_available_balance()
        closed_timestamp = int(time.time() * 1000)

        # Persist a complete, JSON-safe close summary. This is audit state,
        # independent of whether the trade is eligible for ML recording.
        last_trade = {
            "symbol": str(open_position["symbol"]),
            "side": str(open_position["side"]),
            "entry_price": float(open_position["entry_price"]),
            "exit_price": float(exit_price),
            "qty": float(open_position["qty"]),
            "pnl": float(realized),
            "r_multiple": float(r_multiple),
            "mae_usd": float(open_position.get("mae", 0.0)),
            "mfe_usd": float(open_position.get("mfe", 0.0)),
            "mae_r": float(mae_r),
            "mfe_r": float(mfe_r),
            "holding_time": int(holding_seconds),
            "entry_timestamp": open_position.get("entry_timestamp"),
            "closed_timestamp": closed_timestamp,
            "entry_order_id": open_position.get("entry_order_id"),
            "entry_client_order_id": open_position.get(
                "entry_client_order_id"
            ),
            "sl_order_id": open_position.get("sl_order_id"),
            "initial_risk_usd": float(initial_risk_usd),
            "initial_stop_loss": open_position.get("initial_stop_loss"),
            "final_stop_loss": open_position.get("stop_loss"),
            "exit_reason": exit_reason,
            "proposal_id": open_position.get("proposal_id"),
            "execution_outcome_id": None,
            "outcome_delivery_status": "PENDING",
            "learning_recorded": False,
            "candidate_observation_id": open_position.get(
                "candidate_observation_id"
            ),
            "decision_batch_id": open_position.get(
                "decision_batch_id"
            ),
            "market_event_id": open_position.get(
                "market_event_id"
            ),
            "strategy_version": open_position.get(
                "strategy_version"
            ),
            "strategy_variant_id": open_position.get(
                "strategy_variant_id"
            ),
            "model_version": open_position.get("model_version"),
            "experiment_context": open_position.get(
                "experiment_context"
            ),
        }

        self.state.update_after_trade(
            balance=new_balance,
            open_position=None,
            last_trade=last_trade,
        )
        # Capital/accounting truth is durable before any learning delivery.
        self.state.save()

        msg_id = self.state.get_state().get(
            "active_trade_panel_message_id"
        )

        if msg_id:
            panel_text = format_trade_close_panel(
                symbol=open_position.get("symbol", "UNKNOWN"),
                side=open_position.get("side", "UNKNOWN"),
                entry_price=open_position.get("entry_price"),
                initial_stop_loss=open_position.get(
                    "initial_stop_loss",
                    open_position.get("stop_loss"),
                ),
                final_stop_loss=open_position.get("stop_loss"),
                qty=open_position.get("qty"),
                risk_usd=initial_risk_usd,
                exit_price=exit_price,
                realized_pnl=realized,
                r_multiple=r_multiple,
                status="CLOSED",
                exit_reason=exit_reason,
            )

            edit_message(msg_id, panel_text)

            self.state.clear_trade_panel_message_id()

        self.trade_log.info(
            f"TRADE_CLOSE | "
            f"symbol={open_position['symbol']} | "
            f"side={open_position['side']} | "
            f"entry={open_position['entry_price']:.4f} | "
            f"exit={exit_price:.4f} | "
            f"qty={open_position['qty']:.6f} | "
            f"pnl={realized:.2f} | "
            f"exit_reason={exit_reason} | "
            f"structure={open_position.get('structure_fingerprint')}"
        )

        # --------------------------------------------------
        # Execution outcome boundary
        # --------------------------------------------------
        # PositionLifecycle no longer imports or writes learning files. The
        # publisher persists the outcome to the Execution outbox first, then
        # hands it to the configured Observation receiver/client.
        candidate_observation_id = open_position.get(
            "candidate_observation_id"
        )
        outcome_delivered = False
        try:
            if self.outcome_publisher is None:
                if candidate_observation_id:
                    self.system_log.error(
                        "EXECUTION_OUTCOME_PUBLISHER_UNAVAILABLE | "
                        f"symbol={open_position['symbol']}"
                    )
            else:
                execution_outcome = build_execution_outcome(
                    open_position=open_position,
                    environment=TRADING_ENV,
                    execution_mode=EXECUTION_MODE,
                    exit_price=float(exit_price),
                    realized_pnl_usd=float(realized),
                    exit_reason=exit_reason,
                    closed_timestamp=closed_timestamp,
                    holding_seconds=holding_seconds,
                )
                last_trade["execution_outcome_id"] = (
                    execution_outcome.outcome_id
                )
                if last_trade.get("proposal_id") is None:
                    last_trade["proposal_id"] = execution_outcome.proposal_id
                outcome_delivered = bool(
                    self.outcome_publisher.publish(execution_outcome)
                )
        except Exception as exc:
            self.system_log.error(
                "EXECUTION_OUTCOME_PUBLISH_FAILED | "
                f"symbol={open_position['symbol']} | "
                f"error={type(exc).__name__}:{exc}"
            )

        last_trade["outcome_delivery_status"] = (
            "DELIVERED" if outcome_delivered else "PENDING"
        )
        last_trade["learning_recorded"] = bool(
            outcome_delivered and candidate_observation_id
        )

        # update_after_trade stored the same last_trade object by reference,
        # but assign it explicitly so the final learning_recorded flag is
        # unambiguous before atomic persistence.
        self.state.state["last_trade"] = last_trade
        self.state.save()
        self.exit_in_progress = False

        # --------------------------------------------------
        # Governance Refresh after close
        # --------------------------------------------------
        try:
            self.universe.maybe_reload(
                exchange=self.exchange,
                state=self.state,
                force=True,
            )
        except Exception as e:
            self.system_log.error(
                f"UNIVERSE_RELOAD_AFTER_CLOSE_FAILED | {e}"
            )
