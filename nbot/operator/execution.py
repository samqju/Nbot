"""Execution-owned logs, Telegram commands and editable trade panel.

Nothing in this module is allowed to create entry authority.  The surface reads
already-durable Execution truth and can only impose an additional operator
entry block.  Telegram failures are best-effort and never propagate into the
capital worker.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import html
import json
import logging
from pathlib import Path
import time
import threading
from typing import Callable, Mapping

from nbot.common.atomic_io import atomic_write_json, atomic_write_text
from nbot.execution.execution import ExecutionWorker
from nbot.execution.state import ExecutionStatePaths
from .telegram import TelegramClient, TelegramCommandListener, TelegramDispatcher


OPERATOR_BLOCK_FILE = "OPERATOR_ENTRIES_DISABLED"
OPERATOR_STATE_FILE = "operator_state.json"

EXECUTION_TELEGRAM_COMMANDS: tuple[tuple[str, str], ...] = (
    ("status", "Execution state"),
    ("position", "Current position"),
    ("recent", "Last completed trade"),
    ("pnl", "Today's paper PnL"),
    ("learning", "V4 research and model progress"),
    ("enable", "Allow new entries after safety checks"),
    ("disable", "Pause new entries"),
    ("help", "Show commands"),
)


def operator_block_path(repo_root: Path, profile: str) -> Path:
    leaf = {"testnet-trade": "testnet", "live-paper": "paper", "live-trade": "real"}[profile]
    return Path(repo_root) / "runtime" / "execution" / leaf / OPERATOR_BLOCK_FILE


def operator_entries_blocked(repo_root: Path, profile: str) -> bool:
    return operator_block_path(repo_root, profile).is_file()


def set_operator_entry_block(repo_root: Path, profile: str, *, blocked: bool) -> None:
    path = operator_block_path(repo_root, profile)
    if blocked:
        atomic_write_text(path, f"profile={profile}\nblocked_at_ms={int(time.time()*1000)}\n", mode=0o600)
    else:
        path.unlink(missing_ok=True)


def _f(value: object, digits: int = 8) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def _signed(value: object, suffix: str = "") -> str:
    try:
        return f"{float(value):+.2f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def _duration_ms(start: object, end: object) -> str:
    try:
        seconds = max(0, int((int(end) - int(start)) / 1000))
    except (TypeError, ValueError):
        return "N/A"
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


class ExecutionOperatorSurface:
    def __init__(
        self,
        *,
        repo_root: Path,
        profile: str,
        worker: ExecutionWorker,
        telegram: TelegramClient,
        system_log: logging.Logger,
        trade_log: logging.Logger,
        enable_policy: Callable[[], tuple[bool, str]],
        runtime_mode: str | None = None,
        position_manage_warn_ms: float = 1000.0,
        observation_status_reader: Callable[[str], Mapping[str, object]] | None = None,
        paper_review_writer: Callable[[Mapping[str, object]], Mapping[str, object]] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.profile = profile
        self.worker = worker
        self.telegram = telegram
        # Main dispatcher is the single outbound destination. Configure its
        # chat_id as the Telegram channel ID. A separate command_chat_id is
        # input-only and can never redirect replies away from the channel.
        self.dispatcher = TelegramDispatcher(telegram, logger=system_log)
        command_telegram = telegram
        command_chat = telegram.config.command_chat_id
        if command_chat and command_chat != telegram.config.chat_id:
            command_telegram = TelegramClient(
                replace(telegram.config, chat_id=command_chat),
                logger=system_log, requester=telegram._requester)
        self.system_log = system_log
        self.trade_log = trade_log
        self.enable_policy = enable_policy
        self.runtime_mode = None if runtime_mode is None else str(runtime_mode).strip() or None
        self.position_manage_warn_ms = max(1.0, float(position_manage_warn_ms))
        self.observation_status_reader = observation_status_reader
        self.paper_review_writer = paper_review_writer
        self._review_stop = threading.Event()
        self._review_thread = None
        paths = ExecutionStatePaths.for_profile(self.repo_root, profile)
        self.operator_state_path = paths.base_dir / OPERATOR_STATE_FILE
        self.review_notification_path = paths.base_dir / 'paper_review_notification.json'
        self._state = self._load_operator_state()
        self._listener = TelegramCommandListener(
            command_telegram,
            self.handle_command,
            logger=system_log,
        )
        self._last_daily_halt_reason: str | None = None

    @property
    def command_dispatcher(self):
        # Command responses always go to the main outbound destination/channel.
        return self.dispatcher

    def _default_state(self) -> dict[str, object]:
        return {
            "panel_message_id": None,
            "panel_proposal_id": None,
            "last_stop_price": None,
            "closed_outcome_id": None,
            "closed_panel_acked": None,
            "last_emergency_exits": 0,
            "last_stop_missing_events": 0,
            "latency_alert_active": False,
            "last_entries_enabled": None,
            "panel_send_pending": False,
        }

    def _load_operator_state(self) -> dict[str, object]:
        if not self.operator_state_path.is_file():
            return self._default_state()
        try:
            data = json.loads(self.operator_state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not object")
            result = self._default_state()
            result.update({key: data.get(key) for key in result})
            return result
        except Exception as exc:
            # Operator-state loss can recreate a panel; it must never corrupt or
            # block capital state.
            self.system_log.warning(
                "OPERATOR_STATE_RESET error=%s:%s", type(exc).__name__, exc
            )
            return self._default_state()

    def _save_operator_state(self) -> None:
        try:
            atomic_write_json(self.operator_state_path, self._state, mode=0o600)
        except Exception as exc:
            self.system_log.warning(
                "OPERATOR_STATE_SAVE_FAILED error=%s:%s", type(exc).__name__, exc
            )

    def start(self, *, prepared_status: str) -> None:
        self.dispatcher.start()
        self.dispatcher.set_commands(EXECUTION_TELEGRAM_COMMANDS)
        self.sync(recovered=True)
        snapshot = self.worker.state.snapshot
        # Some legacy runtime-wiring tests intentionally provide a minimal
        # snapshot object with only the fields needed by the capital worker.
        # Operator visibility must remain additive and must not turn those
        # runtime contracts into new hard requirements.
        position = getattr(snapshot, "open_position", getattr(self.worker.state, "open_position", None))
        entries_enabled = bool(getattr(snapshot, "entries_enabled", False))
        body = (
            f"Profile: {html.escape(self.profile)}\n"
            f"Prepared: {html.escape(prepared_status)}\n"
            f"Entries enabled: {str(entries_enabled).lower()}\n"
            f"Operator block: {str(operator_entries_blocked(self.repo_root, self.profile)).lower()}\n"
            f"Position: {'FLAT' if position is None else html.escape(position.symbol + ' ' + position.side)}"
        )
        if self.profile == "live-paper":
            mode = self.runtime_mode or "LIVE_PAPER"
            body += f"\nMode: {html.escape(mode)}\nBinance private writes: false"
        self.dispatcher.send_info("EXECUTION WORKER STARTED", body)
        self._listener.start()
        if self.profile == 'live-paper' and self.observation_status_reader and self.paper_review_writer and self.telegram.config.commands_enabled:
            self._review_thread = threading.Thread(target=self._poll_paper_review, name='nbot-paper-review-notify', daemon=True)
            self._review_thread.start()
        self.system_log.info(
            "EXECUTION_OPERATOR_SURFACE_STARTED profile=%s telegram=%s commands=%s",
            self.profile,
            self.telegram.config.enabled,
            self.telegram.config.commands_enabled,
        )

    def stop(self) -> None:
        self._review_stop.set()
        if self._review_thread is not None:
            self._review_thread.join(timeout=1)
        self._listener.stop()
        self.dispatcher.send_info("EXECUTION WORKER STOPPED", f"Profile: {html.escape(self.profile)}")
        self.dispatcher.stop()

    def runtime_error(self, exc: BaseException) -> None:
        self.dispatcher.send_critical(
            "EXECUTION RUNTIME ERROR",
            f"Profile: {html.escape(self.profile)}\nError: {html.escape(type(exc).__name__ + ':' + str(exc))}",
        )

    def after_flat_result(self, result: str) -> None:
        if result.startswith("PROPOSAL_REJECTED:"):
            reason = result.split(":", 1)[1]
            self.dispatcher.send_warning(
                "PROPOSAL VETOED",
                f"Profile: {html.escape(self.profile)}\nReason: {html.escape(reason)}\nCapital remained flat.",
            )
        if result == "DAILY_BLOCKED":
            reason = self.worker.state.daily_risk.halt_reason or "DAILY_RISK_GATE"
            if reason != self._last_daily_halt_reason:
                self._last_daily_halt_reason = reason
                self.dispatcher.send_warning(
                    "DAILY ENTRY HALT",
                    f"Profile: {html.escape(self.profile)}\nReason: {html.escape(reason)}",
                )
        self.sync()

    def _history_for_proposal(self, proposal_id: str) -> Mapping[str, object] | None:
        try:
            rows = self.worker.durable.history.records()
        except Exception as exc:
            self.system_log.warning("OPERATOR_HISTORY_READ_FAILED error=%s:%s", type(exc).__name__, exc)
            return None
        for row in reversed(rows):
            payload = row.get("payload")
            if isinstance(payload, Mapping) and payload.get("proposal_id") == proposal_id:
                return payload
        return None

    def _outcome_pending(self, outcome_id: str) -> bool:
        try:
            return any(row.get("record_id") == outcome_id for row in self.worker.durable.outbox.pending())
        except Exception:
            return True

    def _open_panel(self, position, *, recovered: bool) -> str:
        status = "OPEN (RECOVERED)" if recovered else "OPEN"
        return (
            f"📊 <b>TRADE {status}</b>\n\n"
            f"{html.escape(position.symbol)} {html.escape(position.side)}\n"
            f"Entry: {_f(position.entry_price)}\n"
            f"Stop: {_f(position.stop_price)}\n"
            f"Risk: {_f(position.initial_risk_usd, 2)} USD\n"
            f"MFE/MAE: {_signed(position.mfe_r, 'R')} / {_signed(position.mae_r, 'R')}\n"
            "Protection: VERIFIED"
        )

    def _close_panel(self, payload: Mapping[str, object], *, acked: bool) -> str:
        return (
            "✅ <b>TRADE CLOSED</b>\n\n"
            f"{html.escape(str(payload.get('symbol') or 'N/A'))} "
            f"{html.escape(str(payload.get('side') or 'N/A'))}\n"
            f"PnL: {_signed(payload.get('realized_pnl_usd'), ' USD')} | "
            f"{_signed(payload.get('r_multiple'), 'R')}\n"
            f"MFE/MAE: {_signed(payload.get('mfe_r'), 'R')} / {_signed(payload.get('mae_r'), 'R')}\n"
            f"Holding: {_duration_ms(payload.get('entry_timestamp_ms'), payload.get('closed_timestamp_ms'))}\n"
            f"Reason: {html.escape(str(payload.get('exit_reason') or 'UNKNOWN'))}\n"
            f"Observation ACK: {'RECORDED' if acked else 'PENDING'}"
        )

    def _sync_health_alerts(self) -> None:
        # Operator telemetry is deliberately optional.  Minimal/fake worker
        # states used by older runtime-wiring tests may omit health entirely;
        # absence of operator telemetry must never affect capital behavior.
        health = getattr(self.worker.state, "health", None)
        if health is None:
            return
        emergencies = int(getattr(health, "emergency_exits", 0))
        missing = int(getattr(health, "stop_missing_events", 0))
        if emergencies > int(self._state.get("last_emergency_exits") or 0):
            self.dispatcher.send_critical(
                "EXECUTION EMERGENCY EVENT",
                f"Profile: {html.escape(self.profile)}\nLast event: {html.escape(str(health.last_event or 'UNKNOWN'))}",
            )
        if missing > int(self._state.get("last_stop_missing_events") or 0):
            self.dispatcher.send_warning(
                "PROTECTIVE STOP WARNING",
                f"Profile: {html.escape(self.profile)}\nLast event: {html.escape(str(health.last_event or 'UNKNOWN'))}",
            )
        self._state["last_emergency_exits"] = emergencies
        self._state["last_stop_missing_events"] = missing

        entries_enabled = bool(self.worker.state.snapshot.entries_enabled)
        previous_entries = self._state.get("last_entries_enabled")
        if previous_entries is not None and bool(previous_entries) != entries_enabled:
            title = "NEW ENTRIES ENABLED" if entries_enabled else "NEW ENTRIES DISABLED"
            body = f"Profile: {html.escape(self.profile)}\nOpen-position management is unchanged."
            if entries_enabled:
                self.dispatcher.send_info(title, body)
            else:
                self.dispatcher.send_warning(title, body)
        self._state["last_entries_enabled"] = entries_enabled

        last_ms = float(getattr(health, "last_position_manage_ms", 0.0))
        active = bool(self._state.get("latency_alert_active"))
        if last_ms >= self.position_manage_warn_ms and not active:
            self.dispatcher.send_warning(
                "POSITION MANAGEMENT LATENCY",
                f"Last manage: {last_ms:.2f} ms\nThreshold: {self.position_manage_warn_ms:.2f} ms",
            )
            self._state["latency_alert_active"] = True
        elif last_ms < self.position_manage_warn_ms * 0.5 and active:
            self._state["latency_alert_active"] = False

    def sync(self, *, recovered: bool = False) -> None:
        """Reflect already-durable capital truth into logs/Telegram."""
        try:
            self._sync_health_alerts()
            position = self.worker.state.open_position
            panel_proposal = self._state.get("panel_proposal_id")
            panel_id = self._state.get("panel_message_id")

            if position is not None:
                is_new_trade = panel_proposal != position.proposal_id
                stop_changed = self._state.get("last_stop_price") != float(position.stop_price)
                text = self._open_panel(position, recovered=recovered and is_new_trade)
                if is_new_trade:
                    self._state.update(
                        panel_message_id=None,
                        panel_proposal_id=position.proposal_id,
                        last_stop_price=float(position.stop_price),
                        closed_outcome_id=None,
                        closed_panel_acked=None,
                        panel_send_pending=False,
                    )
                    self.trade_log.info(
                        "TRADE_OPEN proposal_id=%s symbol=%s side=%s entry=%s stop=%s qty=%s risk_usd=%s authority=%s exit_policy=%s recovered=%s",
                        position.proposal_id, position.symbol, position.side, position.entry_price,
                        position.stop_price, position.quantity, position.initial_risk_usd,
                        position.entry_authority, position.exit_policy_version, recovered,
                    )
                    panel_id = None

                if not panel_id and not bool(self._state.get("panel_send_pending")):
                    proposal_id = position.proposal_id
                    self._state["panel_send_pending"] = True

                    def _panel_created(result, *, expected=proposal_id):
                        try:
                            self._state["panel_send_pending"] = False
                            if result and self._state.get("panel_proposal_id") == expected:
                                self._state["panel_message_id"] = int(result)
                            self._save_operator_state()
                        except Exception as exc:
                            self.system_log.warning(
                                "TRADE_PANEL_CALLBACK_FAILED error=%s:%s", type(exc).__name__, exc
                            )

                    queued = self.dispatcher.send_message(text, callback=_panel_created)
                    if not queued:
                        self._state["panel_send_pending"] = False
                elif panel_id and stop_changed:
                    self.dispatcher.edit_message(int(panel_id), text)
                    self._state["last_stop_price"] = float(position.stop_price)
                    self.trade_log.info(
                        "TRADE_STOP_UPDATE proposal_id=%s symbol=%s stop=%s mfe_r=%s mae_r=%s",
                        position.proposal_id, position.symbol, position.stop_price, position.mfe_r, position.mae_r,
                    )
                elif stop_changed:
                    # Preserve the latest durable stop so a panel created after a
                    # transient Telegram outage starts from current protection.
                    self._state["last_stop_price"] = float(position.stop_price)
                self._save_operator_state()
                return

            # Position is flat. If a panel is associated with a prior proposal,
            # wait for authoritative close history before editing it closed.
            if panel_proposal:
                payload = self._history_for_proposal(str(panel_proposal))
                if payload is not None:
                    outcome_id = str(payload.get("outcome_id") or "")
                    acked = bool(outcome_id and not self._outcome_pending(outcome_id))
                    text = self._close_panel(payload, acked=acked)
                    previous_outcome_id = self._state.get("closed_outcome_id")
                    previous_acked = self._state.get("closed_panel_acked")
                    close_changed = previous_outcome_id != outcome_id
                    ack_changed = previous_acked is None or bool(previous_acked) != acked
                    if close_changed or ack_changed:
                        if panel_id:
                            self.dispatcher.edit_message(int(panel_id), text)
                        elif close_changed:
                            self.dispatcher.send_message(text)
                    if close_changed:
                        self.trade_log.info(
                            "TRADE_CLOSE outcome_id=%s proposal_id=%s symbol=%s side=%s pnl_usd=%s r=%s reason=%s acked=%s",
                            outcome_id, payload.get("proposal_id"), payload.get("symbol"), payload.get("side"),
                            payload.get("realized_pnl_usd"), payload.get("r_multiple"), payload.get("exit_reason"), acked,
                        )
                    self._state["closed_outcome_id"] = outcome_id
                    self._state["closed_panel_acked"] = acked
                    if acked:
                        self.trade_log.info("TRADE_OUTCOME_ACK outcome_id=%s", outcome_id)
                        self._state = self._default_state()
                    self._save_operator_state()
                    return
            self._save_operator_state()
        except Exception as exc:
            # This boundary is intentionally unable to stop capital management.
            self.system_log.warning("EXECUTION_OPERATOR_SYNC_FAILED error=%s:%s", type(exc).__name__, exc)

    def _status_body(self) -> str:
        snap = self.worker.state.snapshot
        pos = snap.open_position
        daily = snap.daily_risk
        if daily.halted:
            state = "HALTED"
        elif operator_entries_blocked(self.repo_root, self.profile) or not snap.entries_enabled:
            state = "PAUSED"
        elif pos is not None:
            state = "MANAGING POSITION"
        else:
            state = "READY / WAITING"

        body = (
            f"Mode: {html.escape(self.runtime_mode or self.profile)}\n"
            f"State: {state}\n"
            f"Position: {'FLAT' if pos is None else html.escape(pos.symbol + ' ' + pos.side)}\n"
            f"Daily PnL: {_signed(daily.realized_pnl_usd, ' USD')}\n"
            f"Trades today: {daily.trades_closed}"
        )
        if daily.halted:
            body += f"\nRisk halt: {html.escape(daily.halt_reason or 'ACTIVE')}"
        try:
            payload = self.observation_status_reader("recommendation") if self.observation_status_reader else None
            if not isinstance(payload, Mapping) or payload.get("order_authority") != "NONE":
                raise ValueError("READ_ONLY_STATUS_UNAVAILABLE")
            data = payload.get("document")
            if not isinstance(data, Mapping):
                raise ValueError("READ_ONLY_STATUS_INVALID")
            ready = data.get("status") == "READY"
            body += "\nLearning service: " + ("ready." if ready else "not ready.")
            reason = str(data.get("reason") or "").replace("_", " ").lower()
            if reason:
                body += "\nReason: " + html.escape(reason)
        except Exception:
            body += "\nLearning service status unavailable."
        return body

    def _position_body(self) -> str:
        pos = self.worker.state.open_position
        if pos is None:
            return "FLAT"
        return (
            f"{html.escape(pos.symbol)} {html.escape(pos.side)}\n"
            f"Entry: {_f(pos.entry_price)}\n"
            f"Stop: {_f(pos.stop_price)}\n"
            f"Risk: {_f(pos.initial_risk_usd, 2)} USD\n"
            f"MFE/MAE: {_signed(pos.mfe_r, 'R')} / {_signed(pos.mae_r, 'R')}"
        )

    def _health_body(self) -> str:
        health = asdict(self.worker.state.health)
        return "\n".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in health.items())

    def _recent_body(self) -> str:
        rows = self.worker.durable.history.records()
        if not rows:
            return "No completed trades."
        payload = rows[-1]["payload"]
        return (
            f"{html.escape(str(payload.get('symbol') or 'N/A'))} "
            f"{html.escape(str(payload.get('side') or 'N/A'))}\n"
            f"PnL: {_signed(payload.get('realized_pnl_usd'), ' USD')} | "
            f"{_signed(payload.get('r_multiple'), 'R')}\n"
            f"Holding: {_duration_ms(payload.get('entry_timestamp_ms'), payload.get('closed_timestamp_ms'))}\n"
            f"Reason: {html.escape(str(payload.get('exit_reason') or 'UNKNOWN'))}"
        )

    def _pnl_body(self) -> str:
        daily = self.worker.state.daily_risk
        body = (
            f"Realized: {_signed(daily.realized_pnl_usd, ' USD')}\n"
            f"Trades: {daily.trades_closed}\n"
            f"Halted: {str(daily.halted).lower()}"
        )
        if daily.halted:
            body += f"\nReason: {html.escape(daily.halt_reason or 'ACTIVE')}"
        return body

    def _remote_observation_status(self, *, view: str, title: str) -> None:
        """Display read-only Observation status on the Execution Telegram bot.

        This method runs only on the Telegram command-listener thread.  Failure
        to reach Observation is informational and never mutates worker state.
        """
        reader = self.observation_status_reader
        if reader is None:
            self.command_dispatcher.send_warning(
                "OBSERVATION STATUS UNAVAILABLE",
                "Read-only Observation proxy is not configured. Execution is unchanged.",
            )
            return
        try:
            payload = reader(view)
            if not isinstance(payload, Mapping):
                raise RuntimeError("OBSERVATION_OPERATOR_RESPONSE_INVALID")
            if payload.get("order_authority") != "NONE":
                raise RuntimeError("OBSERVATION_OPERATOR_AUTHORITY_INVALID")
            body = payload.get("telegram_body")
            if not isinstance(body, str) or not body.strip():
                raise RuntimeError("OBSERVATION_OPERATOR_BODY_INVALID")
        except Exception as exc:
            self.system_log.warning(
                "OPERATOR_OBSERVATION_STATUS_UNAVAILABLE view=%s error=%s:%s",
                view,
                type(exc).__name__,
                exc,
            )
            self.command_dispatcher.send_warning(
                "OBSERVATION STATUS UNAVAILABLE",
                f"View: {html.escape(view)}\nExecution and open-position management are unchanged.",
            )
            return
        self.system_log.info(
            "OPERATOR_OBSERVATION_STATUS source=TELEGRAM view=%s authority=NONE",
            view,
        )
        self.command_dispatcher.send_info(title, body)

    def _poll_paper_review(self) -> None:
        # Remote polling/Telegram delivery never runs in the capital hot path.
        while not self._review_stop.is_set():
            try:
                self._notify_paper_review()
            except Exception as exc:
                self.system_log.warning('V4_REVIEW_NOTIFY_FAILED error=%s', type(exc).__name__)
            self._review_stop.wait(60)

    def _notify_paper_review(self) -> None:
        payload = self.observation_status_reader('v4-review')
        if payload.get('order_authority') != 'NONE':
            raise ValueError('V4_REVIEW_AUTHORITY_INVALID')
        document = payload['document']
        if not document.get('review_ready'):
            return
        contest = document['contest']
        identity = [contest['contest_id'], contest['challenger_generation']]
        if self.review_notification_path.is_file():
            saved = json.loads(self.review_notification_path.read_text(encoding='utf-8'))
            if saved.get('review') == identity:
                return
        if self.telegram.send_info('PAPER EXAM READY FOR YOUR REVIEW', payload['telegram_body']) is not None:
            atomic_write_json(self.review_notification_path, {'review': identity}, mode=0o600)

    def _paper_review_command(self, text: str) -> None:
        if self.profile != 'live-paper' or self.paper_review_writer is None:
            raise ValueError('V4_PAPER_REVIEW_NOT_CONFIGURED')
        args = text.strip().split()[1:]
        if not args:
            self._remote_observation_status(view='v4-review', title='V4 PAPER CHAMPION REVIEW')
            return
        if len(args) != 3 or args[0] not in {'approve', 'reject'}:
            self.command_dispatcher.send_warning('REVIEW COMMAND', 'Use /champion to see the current exam and its exact approval or rejection command.')
            return
        result = self.paper_review_writer({'action': args[0], 'contest_id': int(args[1]), 'generation': int(args[2])})
        if result.get('order_authority') != 'NONE':
            raise ValueError('V4_REVIEW_AUTHORITY_INVALID')
        self.command_dispatcher.send_info('PAPER REVIEW RECORDED',
            f"Contest {int(result['contest_id'])}: {html.escape(result['decision'])}\nPaper Champion: {result.get('champion_generation') or 'none'}\nEntry enablement is unchanged. Real-money execution remains disabled.")

    def handle_command(self, text: str) -> None:
        command = str(text or "").strip().split()[0].split("@", 1)[0].lower() if str(text or "").strip() else ""
        try:
            if command == "/status":
                self.command_dispatcher.send_info("EXECUTION STATUS", self._status_body())
            elif command == "/position":
                self.command_dispatcher.send_info("POSITION", self._position_body())
            elif command == "/recent":
                self.command_dispatcher.send_info("RECENT TRADE", self._recent_body())
            elif command == "/pnl":
                self.command_dispatcher.send_info("DAILY PNL", self._pnl_body())
            elif command == "/learning":
                self._remote_observation_status(view="learning", title="LEARNING PROGRESS")
            elif command == '/champion':
                self._paper_review_command(text)
            elif command == "/disable":
                set_operator_entry_block(self.repo_root, self.profile, blocked=True)
                self.worker.disable_new_entries()
                self.system_log.warning("OPERATOR_ENTRY_DISABLE source=TELEGRAM")
                self.command_dispatcher.send_warning("NEW ENTRIES DISABLED", "Open position management continues.")
            elif command == "/enable":
                allowed, reason = self.enable_policy()
                if not allowed:
                    self.system_log.warning("OPERATOR_ENTRY_ENABLE_REJECTED reason=%s", reason)
                    self.command_dispatcher.send_warning("ENABLE REJECTED", html.escape(reason))
                    return
                set_operator_entry_block(self.repo_root, self.profile, blocked=False)
                result = self.worker.enable_new_entries()
                self.system_log.warning("OPERATOR_ENTRY_ENABLE source=TELEGRAM reconciliation=%s", result.status)
                self.command_dispatcher.send_info("NEW ENTRIES ENABLED", f"Safety check: {html.escape(result.status)}")
            elif command == "/help":
                body = "\n".join(f"/{name} - {description}" for name, description in EXECUTION_TELEGRAM_COMMANDS)
                body += "\n\nReplies and alerts are posted to the configured channel. Only /enable and /disable change entry state."
                if self.profile == 'live-paper':
                    body += '\n/champion - Paper exam, gates, and explicit approve/reject commands. Promotion changes only the paper model role.'
                self.command_dispatcher.send_info("BOT COMMANDS", body)
            elif command:
                self.command_dispatcher.send_warning("UNKNOWN COMMAND", f"{html.escape(command)}\nUse /help.")
        except Exception as exc:
            self.system_log.warning("OPERATOR_COMMAND_FAILED command=%s error=%s:%s", command, type(exc).__name__, exc)
            self.command_dispatcher.send_warning("COMMAND FAILED", "Execution safety state was not bypassed.")
