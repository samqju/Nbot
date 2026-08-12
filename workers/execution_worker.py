"""Capital-only runtime extracted from the legacy TradingEngine."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from communication.observation_client import ObservationClientError
from config import (
    BOT_STATE_PATH,
    EXECUTION_MODE,
    EXECUTION_CONTROL_LOOP_INTERVAL_SECONDS,
    EXECUTION_OUTBOX_PATH,
    EXECUTION_OUTCOME_RETRY_INTERVAL_SECONDS,
    EXECUTION_PROPOSAL_MAX_FUTURE_SKEW_SECONDS,
    MAX_NOTIONAL_USD,
    NOTIONAL_TOLERANCE_PCT,
    RISK_PER_TRADE_USD,
    RISK_TOLERANCE_PCT,
    TRADING_ENV,
)
from engine.daily_lifecycle import DailyLifecycle
from engine.emergency import EmergencyHandler
from engine.entry_lifecycle import EntryLifecycle
from engine.market_state import MarketState
from engine.position_lifecycle import PositionLifecycle
from engine.reconciliation import ReconciliationLifecycle
from engine.throttle import LogThrottle
from execution.exceptions import MarketStateError, OperationalExchangeError
from execution.exchange_contract import validate_exchange_adapter
from execution.outcome_outbox import ExecutionOutcomeOutbox
from execution.outcome_publisher import ExecutionOutcomePublisher
from execution.operator_status import (
    build_execution_operator_status,
    build_heartbeat_operator_status,
)
from execution.proposal_adapter import proposal_to_execution_intent
from pnl_report import generate_daily_pnl_summary
from risk.risk import RiskManager
from state.state import StateManager
from utils.execution_health import ExecutionHealthMonitor
from utils.telegram_notifier import (
    send_critical,
    send_info,
    send_warning,
    start_operator_listener,
)


RUNNING = "RUNNING"
TRADING_DISABLED = "TRADING_DISABLED"
OPERATOR_COMMAND_FILE = "operator_command.json"


class ExecutionWorker:
    """Own capital, execution state, risk, protection, and reconciliation only.

    No Strategy, UniverseManager, IntentLifecycle, candidate pipeline, virtual
    trade engine, model evaluation, promotion, or learning module is imported
    or initialized here.
    """

    def __init__(
        self,
        *,
        exchange,
        observation_client,
        system_log,
        trade_log,
        state=None,
        risk=None,
        market_state=None,
        throttle=None,
        outcome_publisher=None,
        emergency=None,
        daily_lifecycle=None,
        entry_lifecycle=None,
        reconciliation=None,
        position_lifecycle=None,
        request_interval_seconds: float = 1.0,
        control_loop_interval_seconds: float = (
            EXECUTION_CONTROL_LOOP_INTERVAL_SECONDS
        ),
        outcome_retry_interval_seconds: float = (
            EXECUTION_OUTCOME_RETRY_INTERVAL_SECONDS
        ),
        proposal_max_future_skew_seconds: float = (
            EXECUTION_PROPOSAL_MAX_FUTURE_SKEW_SECONDS
        ),
    ):
        contract_report = validate_exchange_adapter(exchange)
        system_log.info(
            "EXECUTION_EXCHANGE_ADAPTER_CONTRACT_OK | "
            f"adapter={contract_report.adapter_class} | "
            f"required_methods={contract_report.required_count}"
        )

        interval = float(request_interval_seconds)
        if interval < 0:
            raise ValueError("EXECUTION_REQUEST_INTERVAL_INVALID")
        control_interval = float(control_loop_interval_seconds)
        if not (0.05 <= control_interval <= 5.0):
            raise ValueError("EXECUTION_CONTROL_LOOP_INTERVAL_INVALID")
        outcome_retry_interval = float(outcome_retry_interval_seconds)
        if outcome_retry_interval < 0.1:
            raise ValueError("EXECUTION_OUTCOME_RETRY_INTERVAL_INVALID")
        future_skew = float(proposal_max_future_skew_seconds)
        if future_skew < 0:
            raise ValueError("EXECUTION_PROPOSAL_FUTURE_SKEW_INVALID")

        self.exchange = exchange
        self.observation_client = observation_client
        self.system_log = system_log
        self.trade_log = trade_log
        self.state = state or StateManager(filename=BOT_STATE_PATH)
        self.risk = risk or RiskManager(
            NOTIONAL_TARGET=MAX_NOTIONAL_USD,
            NOTIONAL_TOLERANCE_PCT=NOTIONAL_TOLERANCE_PCT,
            RISK_PER_TRADE_USD=RISK_PER_TRADE_USD,
            RISK_TOLERANCE_PCT=RISK_TOLERANCE_PCT,
        )
        self.market_state = market_state or MarketState()
        self.throttle = throttle or LogThrottle(self.system_log)
        self.execution_health = ExecutionHealthMonitor(
            system_log=self.system_log,
        )
        try:
            self.state.execution_health_monitor = self.execution_health
        except Exception:
            pass
        attach_health = getattr(
            self.exchange,
            "set_execution_health_monitor",
            None,
        )
        if callable(attach_health):
            attach_health(self.execution_health)

        if outcome_publisher is None:
            outbox = ExecutionOutcomeOutbox(EXECUTION_OUTBOX_PATH)
            outcome_publisher = ExecutionOutcomePublisher(
                outbox=outbox,
                receiver=self.observation_client,
                system_log=self.system_log,
            )
        self.execution_outcome_publisher = outcome_publisher

        self.emergency = emergency or EmergencyHandler(
            exchange=self.exchange,
            state=self.state,
            system_log=self.system_log,
            trade_log=self.trade_log,
        )
        self.daily_lifecycle = daily_lifecycle or DailyLifecycle(
            state=self.state,
            risk=self.risk,
            exchange=self.exchange,
            system_log=self.system_log,
        )
        self.entry_lifecycle = entry_lifecycle or EntryLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            emergency=self.emergency,
            system_log=self.system_log,
            trade_log=self.trade_log,
            throttle=self.throttle,
        )
        self.reconciliation = reconciliation or ReconciliationLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            emergency=self.emergency,
            system_log=self.system_log,
            trade_log=self.trade_log,
            outcome_publisher=self.execution_outcome_publisher,
        )
        self.position_lifecycle = position_lifecycle or PositionLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            emergency=self.emergency,
            reconciliation=self.reconciliation,
            system_log=self.system_log,
            trade_log=self.trade_log,
            outcome_publisher=self.execution_outcome_publisher,
            execution_health_monitor=self.execution_health,
        )
        if position_lifecycle is not None:
            try:
                self.position_lifecycle.execution_health_monitor = (
                    self.execution_health
                )
            except Exception:
                pass

        self.request_interval_seconds = interval
        self.control_loop_interval_seconds = control_interval
        self.outcome_retry_interval_seconds = outcome_retry_interval
        self.proposal_max_future_skew_seconds = future_skew
        self._last_request_monotonic = float("-inf")
        self._last_outcome_retry_monotonic = float("-inf")
        self._session_processed_proposal_ids: set[str] = set()
        self._last_persist_ms = 0
        self._prepared = False
        self._previous_proposal_id = None
        self._previous_proposal_result = None
        self._previous_rejection_reason = None

    def prepare(self) -> None:
        """Load state, connect, reconcile, then deliver old outcomes if flat."""
        self.state.load()
        self.exchange.connect()
        self.reconciliation.run(reason="EXECUTION_STARTUP")

        # Absolutely no normal Observation dependency while capital is open.
        if self.state.get_open_position() is None:
            pending = self.execution_outcome_publisher.pending_count()
            if pending:
                delivered = self.execution_outcome_publisher.retry_pending()
                self._last_outcome_retry_monotonic = time.monotonic()
                self.system_log.info(
                    "EXECUTION_OUTCOME_STARTUP_RETRY | "
                    f"pending_before={pending} | delivered={delivered} | "
                    "pending_after="
                    f"{self.execution_outcome_publisher.pending_count()}"
                )

        self._prepared = True
        self.system_log.info(
            "EXECUTION_WORKER_READY | "
            f"environment={TRADING_ENV} | execution_mode={EXECUTION_MODE} | "
            f"position={'OPEN' if self.state.get_open_position() else 'FLAT'}"
        )

    def start(self) -> None:
        # Capital-first startup: load/connect/reconcile before accepting any
        # Telegram command. The listener discards commands queued while the
        # process was offline, so a stale /enable cannot arm a restarted bot.
        if not self._prepared:
            self.prepare()
        self._notify_started()
        start_operator_listener(self._handle_operator_command)
        self.run_forever()

    def run_forever(self) -> None:
        """Run a control loop while flat and one-symbol market data while open."""
        if not self._prepared:
            self.prepare()

        while True:
            try:
                open_position = self.state.get_open_position()
                if open_position is not None:
                    self._run_open_position_stream(
                        symbol=open_position["symbol"]
                    )
                    continue

                self.process_control_cycle()
                if self.state.get_open_position() is not None:
                    # Entry just opened: connect the dedicated position feed
                    # immediately rather than sleeping through a control tick.
                    continue
                time.sleep(self.control_loop_interval_seconds)
            except KeyboardInterrupt:
                raise
            except MarketStateError as exc:
                self.system_log.info(
                    f"EXECUTION_MARKET_STATE_REJECTION | reason={exc}"
                )
                time.sleep(1)
            except OperationalExchangeError as exc:
                error_str = str(exc)
                self.system_log.error(
                    "EXECUTION_EXCHANGE_OPERATIONAL_FAILURE | "
                    f"error={error_str}"
                )
                if "WS_PRICE_STREAM_FAILED" in error_str:
                    time.sleep(2)
                    continue
                self._disable_trading(
                    reason="EXECUTION_EXCHANGE_OPERATIONAL_FAILURE"
                )
                self.state.save()
                time.sleep(2)
            except Exception as exc:
                self.system_log.error(
                    "EXECUTION_WORKER_EXCEPTION | "
                    f"error={type(exc).__name__}:{exc}"
                )
                self._disable_trading(reason=str(exc))
                self.state.save()
                time.sleep(2)

    def _run_open_position_stream(self, *, symbol: str) -> None:
        """Manage one open position from a dedicated symbol-only feed."""
        stream_factory = getattr(
            self.exchange,
            "position_price_stream",
            None,
        )
        if not callable(stream_factory):
            raise OperationalExchangeError(
                "EXECUTION_POSITION_STREAM_CAPABILITY_MISSING"
            )

        symbol = str(symbol).strip().upper()
        self.system_log.info(
            "EXECUTION_POSITION_STREAM_START | "
            f"symbol={symbol} | scope=POSITION_ONLY"
        )
        stream = stream_factory(symbol)
        try:
            for tick in stream:
                current = self.state.get_open_position()
                if current is None:
                    return
                if str(current.get("symbol", "")).upper() != symbol:
                    raise OperationalExchangeError(
                        "EXECUTION_POSITION_SYMBOL_CHANGED_UNEXPECTEDLY | "
                        f"expected={symbol} | "
                        f"current={current.get('symbol')}"
                    )
                if str(tick.symbol).upper() != symbol:
                    raise OperationalExchangeError(
                        "EXECUTION_POSITION_STREAM_SYMBOL_MISMATCH | "
                        f"expected={symbol} | received={tick.symbol}"
                    )

                self.process_tick(tick)
                if self.state.get_open_position() is None:
                    self.system_log.info(
                        "EXECUTION_POSITION_STREAM_STOP | "
                        f"symbol={symbol} | reason=POSITION_CLOSED"
                    )
                    return

            if self.state.get_open_position() is not None:
                raise OperationalExchangeError(
                    "WS_PRICE_STREAM_FAILED | "
                    f"symbol={symbol} | reason=STREAM_ENDED"
                )
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def process_control_cycle(self):
        """Advance flat-state control work without requiring a market tick."""
        self._process_operator_command()
        self.execution_health.increment("control_cycles")
        return self._process_flat_cycle(timestamp=int(time.time() * 1000))

    def process_tick(self, tick):
        """Process one Execution-owned market tick.

        The open-position branch returns before any trade-request or pending
        outcome retry logic. Position management therefore has no normal
        Observation API dependency.
        """
        self._process_operator_command()
        self.market_state.update(
            symbol=tick.symbol,
            price=tick.price,
            timestamp=tick.timestamp,
        )

        open_position = self.state.get_open_position()
        self.execution_health.increment("total_ticks")

        if open_position is not None:
            self.execution_health.increment("open_position_ticks")
            if tick.symbol != open_position["symbol"]:
                self.execution_health.increment("irrelevant_open_ticks")
                return "POSITION_OPEN_OTHER_SYMBOL"

            self.execution_health.increment("position_symbol_ticks")
            self.execution_health.observe_ms(
                "internal_tick_age_ms",
                max(
                    0.0,
                    (time.time() * 1000.0) - float(tick.timestamp),
                ),
            )
            manage_started = time.perf_counter()
            try:
                self.position_lifecycle.manage(
                    market_state=self.market_state
                )
            finally:
                self.execution_health.observe_ms(
                    "position_manage_ms",
                    (time.perf_counter() - manage_started) * 1000.0,
                )
            self.daily_lifecycle.handle(timestamp=tick.timestamp)
            self._heartbeat_and_persist()
            return "POSITION_MANAGED"

        return self._process_flat_cycle(timestamp=tick.timestamp)

    def _process_flat_cycle(self, *, timestamp: int):
        """Run flat-only delivery, risk, and proposal work."""
        if self.execution_outcome_publisher.pending_count():
            now_monotonic = time.monotonic()
            if (
                now_monotonic - self._last_outcome_retry_monotonic
                >= self.outcome_retry_interval_seconds
            ):
                self.execution_outcome_publisher.retry_pending()
                self._last_outcome_retry_monotonic = now_monotonic
            if self.execution_outcome_publisher.pending_count():
                self.throttle.log(
                    key="execution_outcome_pending",
                    level="warning",
                    message="NEW_ENTRY_BLOCKED_PENDING_EXECUTION_OUTCOME",
                )
                self._heartbeat_and_persist()
                return "PENDING_OUTCOME"

        # Operator disable means no new entries in every execution mode.
        # Open-position management and durable outcome delivery intentionally
        # run above this flat-entry guard.
        engine_state = self.state.get_state().get("engine_state")
        if engine_state != RUNNING:
            return "ENTRY_DISABLED"

        if self.daily_lifecycle.handle(timestamp=timestamp) is False:
            return "DAILY_BLOCKED"

        now_monotonic = time.monotonic()
        if (
            now_monotonic - self._last_request_monotonic
            < self.request_interval_seconds
        ):
            self._heartbeat_and_persist()
            return "REQUEST_THROTTLED"
        self._last_request_monotonic = now_monotonic

        result = self._request_and_maybe_execute()
        self._heartbeat_and_persist()
        return result

    def _request_and_maybe_execute(self):
        feedback = {
            "previous_proposal_id": self._previous_proposal_id,
            "previous_proposal_result": self._previous_proposal_result,
            "previous_rejection_reason": self._previous_rejection_reason,
        }
        try:
            response = self.observation_client.request_best_trade(
                environment=TRADING_ENV,
                execution_mode=EXECUTION_MODE,
                **feedback,
            )
        except (ObservationClientError, OSError, ConnectionError) as exc:
            self.system_log.warning(
                "EXECUTION_OBSERVATION_UNAVAILABLE | "
                f"error={type(exc).__name__}:{exc} | action=STAY_FLAT"
            )
            return "OBSERVATION_UNAVAILABLE"

        # A response proves any prior rejection report reached Observation.
        self._clear_previous_feedback()

        if response.status == "NOT_READY":
            self.system_log.info(
                "EXECUTION_OBSERVATION_NOT_READY | "
                f"reason={response.reason}"
            )
            return "NOT_READY"
        if response.status == "NO_TRADE":
            return "NO_TRADE"

        proposal = response.proposal
        rejection = self._proposal_rejection_reason(proposal)
        if rejection is not None:
            self._remember_rejection(proposal.proposal_id, rejection)
            self.system_log.info(
                "EXECUTION_PROPOSAL_REJECTED | "
                f"proposal_id={proposal.proposal_id} | reason={rejection}"
            )
            return "PROPOSAL_REJECTED"

        # Re-check capital truth immediately before doing any entry work.
        if self.state.get_open_position() is not None:
            self._remember_rejection(
                proposal.proposal_id,
                "POSITION_ALREADY_OPEN",
            )
            return "PROPOSAL_REJECTED"
        if getattr(self.entry_lifecycle, "entry_in_progress", False):
            self._remember_rejection(
                proposal.proposal_id,
                "ENTRY_ALREADY_IN_PROGRESS",
            )
            return "PROPOSAL_REJECTED"

        try:
            current_price = float(self.exchange.get_last_price(proposal.symbol))
            if current_price <= 0:
                raise ValueError("CURRENT_PRICE_NON_POSITIVE")
            self.market_state.update(
                symbol=proposal.symbol,
                price=current_price,
                timestamp=int(time.time() * 1000),
            )
        except Exception as exc:
            self._remember_rejection(
                proposal.proposal_id,
                "CURRENT_PRICE_UNAVAILABLE",
            )
            self.system_log.warning(
                "EXECUTION_PROPOSAL_PRICE_REFRESH_FAILED | "
                f"proposal_id={proposal.proposal_id} | "
                f"symbol={proposal.symbol} | "
                f"error={type(exc).__name__}:{exc}"
            )
            return "PROPOSAL_REJECTED"

        # Reserve and persist the proposal ID before any order-capable entry
        # work. A crash after this point may miss one trade, but it must never
        # replay the same proposal into a second capital exposure.
        if not self._reserve_proposal_for_entry(proposal.proposal_id):
            self._remember_rejection(
                proposal.proposal_id,
                "DUPLICATE_PROPOSAL",
            )
            return "PROPOSAL_REJECTED"

        intent = proposal_to_execution_intent(proposal)
        executed = self.entry_lifecycle.maybe_execute(
            intent=intent,
            market_state=self.market_state,
        )
        if executed:
            return "ENTRY_OPENED"

        self._remember_rejection(
            proposal.proposal_id,
            "ENTRY_REJECTED_BY_LOCAL_VALIDATION",
        )
        return "PROPOSAL_REJECTED"

    def _proposal_rejection_reason(self, proposal) -> str | None:
        now_ms = int(time.time() * 1000)
        if proposal.environment != TRADING_ENV:
            return "PROPOSAL_ENVIRONMENT_MISMATCH"
        max_future_ms = int(self.proposal_max_future_skew_seconds * 1000)
        if proposal.generated_at > now_ms + max_future_ms:
            return "PROPOSAL_FUTURE_TIMESTAMP"
        if proposal.is_expired(now_ms=now_ms):
            return "PROPOSAL_EXPIRED"
        if self._proposal_already_processed(proposal.proposal_id):
            return "DUPLICATE_PROPOSAL"
        if (
            proposal.selection_authority in {"PAPER_CANARY", "PAPER_CHAMPION"}
            and EXECUTION_MODE != "SHADOW"
        ):
            return "PAPER_MODEL_AUTHORITY_REQUIRES_SHADOW"
        return None

    def _proposal_already_processed(self, proposal_id: str) -> bool:
        proposal_id = str(proposal_id or "").strip()
        if proposal_id in self._session_processed_proposal_ids:
            return True
        checker = getattr(self.state, "has_processed_proposal", None)
        if callable(checker):
            return bool(checker(proposal_id))
        return False

    def _reserve_proposal_for_entry(self, proposal_id: str) -> bool:
        proposal_id = str(proposal_id or "").strip()
        if not proposal_id or self._proposal_already_processed(proposal_id):
            return False
        marker = getattr(self.state, "mark_processed_proposal", None)
        if callable(marker) and not marker(proposal_id):
            return False
        self._session_processed_proposal_ids.add(proposal_id)
        # The durable reservation must reach disk before EntryLifecycle can
        # place an order or create a local paper fill.
        self.state.save()
        return True

    def _remember_rejection(self, proposal_id: str, reason: str) -> None:
        self._previous_proposal_id = proposal_id
        self._previous_proposal_result = "REJECTED"
        self._previous_rejection_reason = reason

    def _clear_previous_feedback(self) -> None:
        self._previous_proposal_id = None
        self._previous_proposal_result = None
        self._previous_rejection_reason = None

    def _heartbeat_and_persist(self) -> None:
        now_ms = int(time.time() * 1000)
        self.state.heartbeat(now_ms)
        if now_ms - self._last_persist_ms <= 5000:
            return
        self.state.save()
        self._last_persist_ms = now_ms

    def _disable_trading(
        self,
        *,
        reason: str,
        operator_initiated: bool = False,
        notify: bool = True,
    ) -> bool:
        if not reason:
            raise ValueError("DISABLE_TRADING_REQUIRES_REASON")
        current_state = self.state.get_state().get("engine_state")
        if current_state == TRADING_DISABLED:
            return False

        if operator_initiated:
            self.system_log.info(
                "OPERATOR_DISABLE | "
                f"reason={reason} | "
                f"utc={datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            self.system_log.error(
                "EXECUTION_TRADING_DISABLED | "
                f"reason={reason} | "
                f"utc={datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            )

        self.state.set_engine_state(TRADING_DISABLED, reason)
        self.state.save()

        if notify:
            if operator_initiated:
                send_info("TRADING DISABLED", "Operator command accepted.")
            else:
                send_critical("TRADING DISABLED", f"Reason: {reason}")
        return True

    def _run_emergency_exit_test(self) -> None:
        """Run the real emergency handler under non-production test gates."""
        environment = str(TRADING_ENV).strip().upper()
        mode = str(EXECUTION_MODE).strip().upper()
        if mode != "SHADOW" and environment != "TESTNET":
            raise RuntimeError(
                "EMERGENCY_EXIT_TEST_FORBIDDEN_IN_LIVE_TRADE"
            )

        engine_state = self.state.get_state().get("engine_state")
        if engine_state != TRADING_DISABLED:
            raise RuntimeError(
                "EMERGENCY_EXIT_TEST_REQUIRES_TRADING_DISABLED"
            )

        open_position = self.state.get_open_position()
        if open_position is None:
            raise RuntimeError(
                "EMERGENCY_EXIT_TEST_REQUIRES_OPEN_POSITION"
            )

        symbol = str(open_position.get("symbol") or "").strip().upper()
        self.system_log.warning(
            "EMERGENCY_EXIT_TEST_REQUESTED | "
            f"environment={environment} | mode={mode} | symbol={symbol}"
        )

        self.emergency.execute(
            reason=f"PHASE6A_EMERGENCY_EXIT_TEST:{symbol}"
        )

        remaining = self.exchange.get_position()
        if remaining is not None:
            raise RuntimeError(
                "EMERGENCY_EXIT_TEST_NOT_FLAT_AFTER_HANDLER | "
                f"symbol={getattr(remaining, 'symbol', symbol)}"
            )

        self.system_log.warning(
            "EMERGENCY_EXIT_TEST_CONFIRMED_FLAT | "
            f"symbol={symbol} | exchange_position=FLAT"
        )

    def _process_operator_command(self) -> None:
        if not os.path.exists(OPERATOR_COMMAND_FILE):
            return
        try:
            with open(OPERATOR_COMMAND_FILE, "r", encoding="utf-8") as handle:
                command = json.load(handle)
            action = str(command.get("action") or "").strip().upper()
            if action == "ENABLE_TRADING":
                self.reconciliation.run(reason="OPERATOR_RESUME")
                self.state.set_engine_state(RUNNING, reason=None)
                self.state.save()
                self.system_log.info("OPERATOR_ENABLE | source=FILE")
            elif action == "DISABLE_TRADING":
                self._disable_trading(
                    reason="OPERATOR_DISABLE",
                    operator_initiated=True,
                    notify=False,
                )
            elif action == "EMERGENCY_EXIT_TEST":
                self._run_emergency_exit_test()
            elif action == "STATUS":
                self.system_log.info(
                    "OPERATOR_STATUS | source=FILE | "
                    f"state={self.state.get_state().get('engine_state')}"
                )
            else:
                self.system_log.warning(
                    "EXECUTION_OPERATOR_COMMAND_UNKNOWN | "
                    f"action={action or 'MISSING'}"
                )
        except Exception as exc:
            self.system_log.error(
                "EXECUTION_OPERATOR_COMMAND_ERROR | "
                f"error={type(exc).__name__}:{exc}"
            )
        finally:
            try:
                os.remove(OPERATOR_COMMAND_FILE)
            except Exception:
                pass

    @staticmethod
    def _operator_command_parts(text: str) -> tuple[str, list[str]]:
        parts = str(text or "").strip().split()
        if not parts:
            return "", []
        command = parts[0].split("@", 1)[0].lower()
        return command, parts[1:]

    def _handle_operator_command(self, text: str) -> None:
        command, args = self._operator_command_parts(text)

        try:
            if command == "/enable":
                self.reconciliation.run(reason="OPERATOR_RESUME")
                self.state.set_engine_state(RUNNING, reason=None)
                self.state.save()
                self.system_log.info("OPERATOR_ENABLE | source=TELEGRAM")
                send_info("TRADING ENABLED", "Operator command accepted.")

            elif command == "/disable":
                changed = self._disable_trading(
                    reason="OPERATOR_DISABLE",
                    operator_initiated=True,
                    notify=False,
                )
                if not changed:
                    self.system_log.info(
                        "OPERATOR_DISABLE | source=TELEGRAM | already_disabled=true"
                    )
                send_info(
                    "TRADING DISABLED",
                    "Operator command accepted."
                    if changed
                    else "Trading was already disabled.",
                )

            elif command == "/status":
                state = self.state.get_state()
                position = self.state.get_open_position()
                self.system_log.info(
                    "OPERATOR_STATUS | source=TELEGRAM | "
                    f"state={state.get('engine_state')} | "
                    f"halt_reason={state.get('engine_halt_reason')} | "
                    f"position={'OPEN' if position else 'FLAT'}"
                )
                send_info(
                    "ENGINE STATUS",
                    f"State: {state.get('engine_state')}\n"
                    f"Halt reason: {state.get('engine_halt_reason') or 'NONE'}\n"
                    f"Position: {'OPEN' if position else 'FLAT'}",
                )

            elif command == "/pnl":
                if len(args) > 1:
                    send_warning(
                        "PNL COMMAND INVALID",
                        "Use /pnl or /pnl YYYY-MM-DD",
                    )
                    return
                summary = (
                    generate_daily_pnl_summary()
                    if not args
                    else generate_daily_pnl_summary(args[0])
                )
                self.system_log.info(
                    "OPERATOR_PNL_STATUS | source=TELEGRAM | "
                    f"day={args[0] if args else 'CURRENT'}"
                )
                send_info("DAILY PNL REPORT", summary)

            elif command == "/execution":
                body, log_line = build_execution_operator_status(
                    state=self.state,
                    execution_health=self.execution_health,
                    outcome_publisher=self.execution_outcome_publisher,
                )
                self.system_log.info(log_line)
                send_info("EXECUTION HEALTH", body)

            elif command == "/heartbeat":
                body, log_line = build_heartbeat_operator_status(
                    state=self.state,
                    exchange=self.exchange,
                    market_state=self.market_state,
                    execution_health=self.execution_health,
                )
                self.system_log.info(log_line)
                send_info("EXECUTION HEARTBEAT", body)

            elif command == "/learning":
                if args:
                    send_warning(
                        "LEARNING COMMAND INVALID",
                        "Use /learning with no arguments.",
                    )
                    return
                try:
                    payload = self.observation_client.request_learning_status()
                except ObservationClientError as exc:
                    self.system_log.warning(
                        "OPERATOR_LEARNING_STATUS_UNAVAILABLE | "
                        f"source=TELEGRAM | error={exc}"
                    )
                    send_warning(
                        "LEARNING STATUS UNAVAILABLE",
                        "Observation learning status could not be read. "
                        "Trading and open-position management are unchanged.",
                    )
                    return
                self.system_log.info(
                    "OPERATOR_LEARNING_STATUS | source=TELEGRAM | "
                    "owner=OBSERVATION | order_authority=NONE"
                )
                send_info(
                    "LEARNING STATUS",
                    payload["telegram_body"],
                )

            elif command == "/help":
                self.system_log.info(
                    f"OPERATOR_HELP | source=TELEGRAM | command={command}"
                )
                send_info(
                    "EXECUTION COMMANDS",
                    "/status — engine/position state\n"
                    "/execution — technical execution health\n"
                    "/heartbeat — cached position/account snapshot\n"
                    "/learning — Observation learning/challenger status\n"
                    "/pnl [YYYY-MM-DD] — daily PnL\n"
                    "/enable — enable new entries after reconciliation\n"
                    "/disable — disable new entries\n"
                    "/help — show this command list",
                )

            elif command:
                self.system_log.info(
                    "OPERATOR_UNKNOWN_COMMAND | source=TELEGRAM | "
                    f"command={command}"
                )
                send_warning(
                    "UNKNOWN COMMAND",
                    f"Unknown command: {command}\nUse /help for active Execution commands.",
                )
        except Exception as exc:
            self.system_log.error(
                "OPERATOR_TELEGRAM_COMMAND_FAILED | "
                f"command={command or 'EMPTY'} | "
                f"error={type(exc).__name__}:{exc}"
            )
            send_warning(
                "COMMAND FAILED",
                f"{command or 'Command'} could not be completed. "
                "Execution safety state was not bypassed.",
            )

    def _notify_started(self) -> None:
        state = self.state.get_state()
        engine_state = state.get("engine_state")
        halt_reason = state.get("engine_halt_reason")
        position = self.state.get_open_position()
        position_text = "FLAT"
        if position is not None:
            position_text = (
                f"OPEN {position.get('symbol')} {position.get('side')} "
                f"qty={position.get('qty')}"
            )

        utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.system_log.info(
            "EXECUTION_STARTED | "
            f"utc={utc} | environment={TRADING_ENV} | mode={EXECUTION_MODE} | "
            f"engine_state={engine_state} | "
            f"halt_reason={halt_reason or 'NONE'} | "
            f"position={position_text.replace(' ', '_')} | reconciliation=OK"
        )

        body = (
            f"UTC: {utc}\n"
            f"Environment: {TRADING_ENV}\n"
            f"Execution mode: {EXECUTION_MODE}\n"
            f"Engine: {engine_state}\n"
            f"Position: {position_text}\n"
            "Reconciliation: OK"
        )
        if engine_state == TRADING_DISABLED:
            send_warning(
                "EXECUTION WORKER STARTED — TRADING DISABLED",
                body + f"\nReason: {halt_reason or 'UNKNOWN'}",
            )
        else:
            send_info("EXECUTION WORKER STARTED", body)
