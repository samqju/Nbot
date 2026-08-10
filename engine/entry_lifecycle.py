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
import uuid
from datetime import datetime, timezone
from config import (
    MAX_NOTIONAL_USD,
    LEVERAGE,
    NOTIONAL_TOLERANCE_PCT,
    RISK_PER_TRADE_USD,
    RISK_TOLERANCE_PCT,
    ENTRY_SLIPPAGE_PCT,
    MAX_SPREAD_PCT,
    EXECUTION_MODE,
)

from execution.exceptions import EntryValidationError

from utils.telegram_notifier import (
    send_warning,
    send_trade_panel,
    format_trade_panel,
)

MAX_SL_PLACEMENT_SECONDS = 2.0

class EntryLifecycle:

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

        # Set only after the exchange confirms a positive fill.
        # Cleared only after the initial stop-loss is verified.
        self._unprotected_entry_symbol = None

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
        self._unprotected_entry_symbol = None

        try:
            return self._execute(intent, market_state)

        except Exception as entry_error:
            # A positive fill without a verified initial SL is a capital
            # emergency. Flatten before allowing the error to reach core.
            if self._unprotected_entry_symbol is not None:
                self._abort_unprotected_entry(
                    symbol=self._unprotected_entry_symbol,
                    error=entry_error,
                )
            raise

        finally:
            self._unprotected_entry_symbol = None
            self._entry_in_progress = False


    # --------------------------------------------------
    # Post-Fill Emergency Boundary
    # --------------------------------------------------

    def _abort_unprotected_entry(self, *, symbol: str, error: Exception):
        """
        Flatten a confirmed fill that does not yet have a verified SL.

        This method returns only after EmergencyHandler confirms the
        exchange is flat. If flattening cannot be verified, it raises a
        fatal error and preserves the emergency failure as the cause.
        """

        reason = (
            f"POST_FILL_UNPROTECTED_FAILURE | "
            f"symbol={symbol} | "
            f"error={type(error).__name__}:{error}"
        )

        self.system_log.critical(reason)

        try:
            self.emergency.execute(reason=reason)
        except Exception as emergency_error:
            self.system_log.critical(
                f"POST_FILL_EMERGENCY_FAILED | "
                f"symbol={symbol} | "
                f"original_error={type(error).__name__}:{error} | "
                f"emergency_error={type(emergency_error).__name__}:{emergency_error}"
            )
            raise RuntimeError(
                f"POST_FILL_EMERGENCY_FAILED | symbol={symbol}"
            ) from emergency_error

        self.system_log.error(
            f"POST_FILL_EMERGENCY_FLATTEN_CONFIRMED | symbol={symbol}"
        )

    # --------------------------------------------------
    # Core Execution
    # --------------------------------------------------

    def _execute(self, intent, market_state):

        symbol = intent.symbol
        selection_authority = str(
            getattr(intent, "selection_authority", "RULES") or "RULES"
        ).strip().upper()
        risk_multiplier = float(
            getattr(intent, "paper_risk_multiplier", 1.0) or 1.0
        )
        if not (0.0 < risk_multiplier <= 1.0):
            raise RuntimeError("ENTRY_PAPER_RISK_MULTIPLIER_INVALID")
        if (
            selection_authority in {"PAPER_CANARY", "PAPER_CHAMPION"}
            and EXECUTION_MODE != "SHADOW"
        ):
            self.system_log.error(
                "PAPER_MODEL_ENTRY_BLOCKED_NON_SHADOW | "
                f"symbol={symbol} | execution_mode={EXECUTION_MODE}"
            )
            return False
        if (
            selection_authority in {"PAPER_CANARY", "PAPER_CHAMPION"}
            and abs(risk_multiplier - 1.0) > 1e-12
        ):
            raise RuntimeError("ENTRY_MODEL_RISK_MULTIPLIER_MUST_EQUAL_ONE")
        target_notional_usd = MAX_NOTIONAL_USD * risk_multiplier
        target_risk_usd = RISK_PER_TRADE_USD * risk_multiplier

        if not market_state.has_price(symbol):
            self.system_log.info(
                f"ENTRY_BLOCKED_NO_PRICE | symbol={symbol}"
            )
            return False

        entry_price = market_state.get_price(symbol)

        # --------------------------------------------------
        # Leverage Enforcement (Per-Symbol, Pre-Entry)
        # --------------------------------------------------

        leverage_set = False

        for attempt in range(1, 3):
            try:
                self.system_log.info(
                    f"LEVERAGE_SET_ATTEMPT | "
                    f"symbol={symbol} | "
                    f"leverage={LEVERAGE} | "
                    f"attempt={attempt}"
                )

                self.exchange.set_leverage(
                    symbol=symbol,
                    leverage=LEVERAGE,
                )

                leverage_set = True
                break

            except Exception as e:
                self.system_log.error(
                    f"LEVERAGE_SET_FAILED | "
                    f"symbol={symbol} | "
                    f"attempt={attempt} | "
                    f"error={type(e).__name__}:{e}"
                )
                time.sleep(0.5 * attempt)

        if not leverage_set:
            self.system_log.error(
                f"ENTRY_BLOCKED_LEVERAGE_FAILURE | symbol={symbol}"
            )
            return False

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
            notional_target=target_notional_usd,
            risk_usd=target_risk_usd,
        )

        required_margin = target_notional_usd / LEVERAGE

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
        # Place entry
        # --------------------------------------------------

        # Binance requires this identifier to resolve a timeout without
        # risking a duplicate market order. Keep it unique and under the
        # exchange's 36-character client-order-id limit.
        client_order_id = (
            f"nb{int(time.time() * 1000)}{uuid.uuid4().hex[:10]}"
        )

        try:
            ack = self.exchange.place_entry(
                symbol=symbol,
                side=intent.direction,
                quantity=entry_plan.quantity,
                price=entry_price,
                client_order_id=client_order_id,
            )
        except EntryValidationError as entry_error:
            # Deterministic adapter-side validation occurs before the POST.
            # No order can exist, so ambiguous-order recovery is incorrect.
            self.system_log.info(
                f"ENTRY_REJECTED_LOCALLY | "
                f"symbol={symbol} | "
                f"client_order_id={client_order_id} | "
                f"reason={entry_error}"
            )
            return False
        except Exception as entry_error:
            # A timeout or transport failure does not prove that Binance
            # rejected the order. Resolve the exact order by client ID and
            # corroborate it with authoritative position truth. Never retry
            # the market order itself.
            self.system_log.error(
                f"ENTRY_ACK_AMBIGUOUS | "
                f"symbol={symbol} | "
                f"client_order_id={client_order_id} | "
                f"error={entry_error}"
            )

            resolution = self.exchange.resolve_ambiguous_entry(
                symbol=symbol,
                client_order_id=client_order_id,
                requested_qty=entry_plan.quantity,
                fallback_price=entry_price,
                timeout_seconds=10.0,
            )

            outcome = resolution.get("outcome")

            if outcome == "FILLED":
                ack = resolution["ack"]
                self.system_log.warning(
                    f"ENTRY_ACK_RECOVERED | "
                    f"symbol={symbol} | "
                    f"client_order_id={client_order_id} | "
                    f"filled_qty={ack.filled_qty} | "
                    f"avg_price={ack.avg_price}"
                )

            elif outcome == "POSITION_EXISTS":
                position = resolution["position"]
                self._unprotected_entry_symbol = symbol
                self.system_log.error(
                    f"ENTRY_ACK_FAILED_POSITION_EXISTS | "
                    f"requested_symbol={symbol} | "
                    f"client_order_id={client_order_id} | "
                    f"exchange_symbol={position.symbol} | "
                    f"qty={position.qty}"
                )

                try:
                    self.emergency.execute(
                        reason=(
                            "AMBIGUOUS_ENTRY_ACK_WITH_OPEN_POSITION:"
                            f"{symbol}:{client_order_id}"
                        )
                    )
                except Exception as emergency_error:
                    raise RuntimeError(
                        f"AMBIGUOUS_ENTRY_EMERGENCY_FAILED | "
                        f"symbol={symbol} | "
                        f"client_order_id={client_order_id} | "
                        f"entry_error={entry_error} | "
                        f"emergency_error={emergency_error}"
                    ) from emergency_error
                finally:
                    self._unprotected_entry_symbol = None

                raise RuntimeError(
                    f"AMBIGUOUS_ENTRY_FLATTENED | "
                    f"symbol={symbol} | "
                    f"client_order_id={client_order_id}"
                ) from entry_error

            else:
                raise RuntimeError(
                    f"ENTRY_OUTCOME_UNRESOLVED | "
                    f"symbol={symbol} | "
                    f"client_order_id={client_order_id} | "
                    f"resolution={outcome} | "
                    f"entry_error={entry_error}"
                ) from entry_error

        if ack.filled_qty <= 0:
            self.system_log.error(
                f"ENTRY_NOT_FILLED | symbol={symbol}"
            )
            return False

        # From this point until initial-SL verification, any exception
        # must trigger a verified emergency flatten.
        self._unprotected_entry_symbol = symbol

        # --------------------------------------------------
        # Partial fill guard
        # --------------------------------------------------

        if not ack.fully_filled:

            self.system_log.error(
                f"PARTIAL_FILL | "
                f"symbol={symbol} | "
                f"requested={ack.requested_qty} | "
                f"filled={ack.filled_qty}"
            )
            raise RuntimeError(
                f"ENTRY_PARTIAL_FILL_ABORT | "
                f"symbol={symbol} | "
                f"requested={ack.requested_qty} | "
                f"filled={ack.filled_qty}"
            )

        # --------------------------------------------------
        # Notional invariant
        # --------------------------------------------------

        executed_notional = ack.filled_qty * ack.avg_price
        max_allowed = target_notional_usd * (
            1 + NOTIONAL_TOLERANCE_PCT / 100
        )

        if executed_notional > max_allowed:
            self.system_log.error(
                f"ENTRY_NOTIONAL_BREACH | "
                f"symbol={symbol} | "
                f"executed_notional={executed_notional} | "
                f"max_allowed={max_allowed}"
            )
            raise RuntimeError(
                f"ENTRY_NOTIONAL_BREACH | symbol={symbol}"
            )

        # --------------------------------------------------
        # Recalculate SL
        # --------------------------------------------------

        actual_risk_usd = target_risk_usd
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
            "entry_order_id": ack.order_id,
            "entry_client_order_id": (
                ack.client_order_id or client_order_id
            ),
            "sl_order_id": None,
            # Immutable entry-risk basis for later R-multiple, MAE, and MFE
            # calculations. stop_loss may trail after entry, so it cannot be
            # used as the historical denominator when the trade closes.
            "initial_stop_loss": corrected_sl,
            "risk_usd": actual_risk_usd,
            "initial_risk_usd": actual_risk_usd,
            "sl_status": "PENDING_VERIFICATION",
            "highest_profit_usd": 0.0,
            "last_locked_R": 0,
            "entry_timestamp": int(
                datetime.now(timezone.utc).timestamp() * 1000
            ),
            "structure_fingerprint": intent.structure_fingerprint,
            "pattern": intent.pattern,
            "proposal_id": getattr(intent, "proposal_id", None),
            "candidate_observation_id": (
                intent.candidate_observation_id
            ),
            "advisory_risk_plan": intent.advisory_risk_plan,
            "decision_batch_id": intent.decision_batch_id,
            "market_event_id": intent.market_event_id,
            "strategy_version": intent.strategy_version,
            "strategy_variant_id": intent.strategy_variant_id,
            "model_version": intent.model_version,
            "experiment_context": intent.experiment_context,
            "selection_authority": selection_authority,
            "paper_canary_model_id": getattr(
                intent, "paper_canary_model_id", None
            ),
            "paper_risk_multiplier": risk_multiplier,
            "paper_allocation_id": getattr(
                intent, "paper_allocation_id", None
            ),
            "mae": 0.0,
            "mfe": 0.0,
	        }

        # --------------------------------------------------
        # Post-fill risk guard
        # --------------------------------------------------

        actual_risk_usd = abs(
            (ack.avg_price - corrected_sl)
            * ack.filled_qty
        )

        max_allowed_risk = target_risk_usd * (
            1 + RISK_TOLERANCE_PCT / 100
        )

        if actual_risk_usd > max_allowed_risk:

            self.system_log.error(
                f"ENTRY_POST_FILL_RISK_BREACH | "
                f"symbol={symbol} | "
                f"actual_risk={actual_risk_usd} | "
                f"max_allowed={max_allowed_risk}"
            )
            raise RuntimeError(
                f"ENTRY_POST_FILL_RISK_BREACH | symbol={symbol}"
            )
        # --------------------------------------------------
        # Slippage guard
        # --------------------------------------------------

        slippage_pct = abs(
            (ack.avg_price - entry_price) / entry_price
        ) * 100.0

        if slippage_pct > ENTRY_SLIPPAGE_PCT:
            self.system_log.error(
                f"ENTRY_SLIPPAGE_BREACH | "
                f"symbol={symbol} | "
                f"slippage_pct={slippage_pct} | "
                f"max_allowed={ENTRY_SLIPPAGE_PCT}"
            )
            raise RuntimeError(
                f"ENTRY_SLIPPAGE_BREACH | symbol={symbol}"
            )

        # --------------------------------------------------
        # Attach experiment metadata to local paper execution.
        # Other adapters need not implement this optional method; the engine
        # state above remains the canonical metadata source for them.
        # --------------------------------------------------
        metadata_setter = getattr(
            self.exchange,
            "set_pending_entry_metadata",
            None,
        )
        if callable(metadata_setter):
            metadata_setter(
                symbol=symbol,
                client_order_id=(
                    ack.client_order_id or client_order_id
                ),
                metadata={
                    "proposal_id": getattr(intent, "proposal_id", None),
                    "candidate_observation_id": (
                        intent.candidate_observation_id
                    ),
                    "decision_batch_id": intent.decision_batch_id,
                    "market_event_id": intent.market_event_id,
                    "strategy_version": intent.strategy_version,
                    "strategy_variant_id": (
                        intent.strategy_variant_id
                    ),
                    "model_version": intent.model_version,
                    "structure_fingerprint": (
                        intent.structure_fingerprint
                    ),
                    "pattern": intent.pattern,
                    "experiment_context": (
                        intent.experiment_context
                    ),
                    "selection_authority": selection_authority,
                    "paper_canary_model_id": getattr(
                        intent, "paper_canary_model_id", None
                    ),
                    "paper_risk_multiplier": risk_multiplier,
                    "paper_allocation_id": getattr(
                        intent, "paper_allocation_id", None
                    ),
                },
            )

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
                sl_ref = self.exchange.place_initial_sl(
                    symbol=symbol,
                    side=intent.direction,
                    qty=ack.filled_qty,
                    stop_price=corrected_sl,
                )

                verified = self.exchange.get_position()

                if verified is None:
                    self.system_log.error(
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
                    open_position["sl_status"] = "VERIFIED"
                    open_position["sl_order_id"] = sl_ref["algo_id"]
                    self.system_log.info(
                        f"INITIAL_SL_VERIFIED | "
                        f"symbol={symbol} | "
                        f"stop_loss={verified.stop_loss}"
                    )
                    break
                else:
                    self.system_log.error(
                        f"INITIAL_SL_VERIFICATION_MISMATCH | "
                        f"symbol={symbol} | "
                        f"expected={expected_sl} | "
                        f"actual={getattr(verified, 'stop_loss', None)}"
                    )

            except Exception as e:
                self.system_log.error(
                    f"INITIAL_SL_PLACEMENT_EXCEPTION | "
                    f"symbol={symbol} | "
                    f"attempt={attempt+1} | "
                    f"error={e}"
                )
                time.sleep(0.5)

        if not sl_placed:
            send_warning(
                "INITIAL SL NOT VERIFIED — EMERGENCY EXIT",
                (
                    f"Symbol: {symbol}\n"
                    "The initial stop-loss could not be verified.\n\n"
                    "A verified emergency flatten is being triggered."
                ),
            )

            self.system_log.critical(
                f"INITIAL_SL_NOT_VERIFIED | symbol={symbol}"
            )

            raise RuntimeError(
                f"INITIAL_SL_NOT_VERIFIED | symbol={symbol}"
            )

        # The exchange has confirmed the protective stop. Later failures
        # are no longer failures of an unprotected-entry boundary.
        self._unprotected_entry_symbol = None

        if (time.time() - sl_start_time) > MAX_SL_PLACEMENT_SECONDS:
            self.system_log.error(
                f"ENTRY_SL_TIMING_WARNING | "
                f"symbol={symbol} | "
                f"elapsed_seconds={time.time() - sl_start_time}"
            )

        # --------------------------------------------------
        # Persist position
        # --------------------------------------------------

        self.state.update_after_trade(
            balance=balance,
            open_position=open_position,
            last_trade=None,
        )

        self.state.save()

        # One compact execution-audit record after the entry is filled, the
        # protective stop is exchange-verified, and the open position is
        # durable. Use the verified/quantized stop, not the pre-quantization
        # calculated stop held in the entry plan.
        self.system_log.info(
            "POSITION_OPENED | "
            f"proposal_id={open_position.get('proposal_id')} | "
            f"symbol={symbol} | "
            f"side={intent.direction} | "
            f"entry={ack.avg_price} | "
            f"qty={ack.filled_qty} | "
            f"leverage={LEVERAGE} | "
            f"initial_sl={verified.stop_loss} | "
            f"sl_status={open_position.get('sl_status')} | "
            f"entry_order_id={open_position.get('entry_order_id')} | "
            f"sl_order_id={open_position.get('sl_order_id')}"
        )

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
