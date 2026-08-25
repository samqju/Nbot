"""Execution-owned logs, Telegram commands and editable trade panel.

Nothing in this module is allowed to create entry authority.  The surface reads
already-durable Execution truth and can only impose an additional operator
entry block.  Telegram failures are best-effort and never propagate into the
capital worker.
"""

from __future__ import annotations

from dataclasses import asdict
import html
import json
import logging
from pathlib import Path
import time
from typing import Callable, Mapping

from nbot.common.atomic_io import atomic_write_json, atomic_write_text
from nbot.execution.execution import ExecutionWorker
from nbot.execution.state import ExecutionStatePaths
from .telegram import TelegramClient, TelegramCommandListener, TelegramDispatcher


OPERATOR_BLOCK_FILE = "OPERATOR_ENTRIES_DISABLED"
OPERATOR_STATE_FILE = "operator_state.json"

EXECUTION_TELEGRAM_COMMANDS: tuple[tuple[str, str], ...] = (
    ("status", "Execution and capital summary"),
    ("position", "Current protected position"),
    ("health", "Execution health and latency"),
    ("recent", "Most recent completed trade"),
    ("pnl", "Current UTC-day PnL and risk"),
    ("observation", "Observation health"),
    ("recommendation", "Recommendation readiness"),
    ("memory", "Compact research memory"),
    ("epoch", "Research epoch status"),
    ("champion", "Base Research Champion evaluator"),
    ("challenger", "Active and latest challenger"),
    ("governance", "Frozen Research Champion eligibility"),
    ("research", "Research Champion review"),
    ("paper", "Frozen Paper Champion gate"),
    ("learning", "Combined V3.9 learning status"),
    ("db", "Observation database integrity"),
    ("disable", "Block new entries only"),
    ("enable", "Request new-entry enable gate"),
    ("help", "Show all Execution commands"),
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
    ) -> None:
        self.repo_root = Path(repo_root)
        self.profile = profile
        self.worker = worker
        self.telegram = telegram
        self.dispatcher = TelegramDispatcher(telegram, logger=system_log)
        self.system_log = system_log
        self.trade_log = trade_log
        self.enable_policy = enable_policy
        self.runtime_mode = None if runtime_mode is None else str(runtime_mode).strip() or None
        self.position_manage_warn_ms = max(1.0, float(position_manage_warn_ms))
        self.observation_status_reader = observation_status_reader
        paths = ExecutionStatePaths.for_profile(self.repo_root, profile)
        self.operator_state_path = paths.base_dir / OPERATOR_STATE_FILE
        self._state = self._load_operator_state()
        self._listener = TelegramCommandListener(
            telegram,
            self.handle_command,
            logger=system_log,
        )
        self._last_daily_halt_reason: str | None = None

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
        self.system_log.info(
            "EXECUTION_OPERATOR_SURFACE_STARTED profile=%s telegram=%s commands=%s",
            self.profile,
            self.telegram.config.enabled,
            self.telegram.config.commands_enabled,
        )

    def stop(self) -> None:
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
            f"Profile: {html.escape(self.profile)}\n"
            f"Symbol: {html.escape(position.symbol)}\n"
            f"Side: {html.escape(position.side)}\n"
            f"Entry: {_f(position.entry_price)}\n"
            f"Initial Stop: {_f(position.initial_stop_price)}\n"
            f"Current Stop: {_f(position.stop_price)} ✅\n"
            f"Qty: {_f(position.quantity, 6)}\n"
            f"Risk: {_f(position.initial_risk_usd, 2)} USD\n"
            f"MFE: {_signed(position.mfe_r, 'R')}\n"
            f"MAE: {_signed(position.mae_r, 'R')}\n"
            f"Authority: {html.escape(position.entry_authority)}\n"
            f"Exit Policy: {html.escape(position.exit_policy_version)}\n"
            f"Proposal: {html.escape(position.proposal_id)}\n"
            "Protection: VERIFIED"
        )

    def _close_panel(self, payload: Mapping[str, object], *, acked: bool) -> str:
        return (
            "✅ <b>TRADE CLOSED</b>\n\n"
            f"Profile: {html.escape(str(payload.get('profile') or self.profile))}\n"
            f"Symbol: {html.escape(str(payload.get('symbol') or 'N/A'))}\n"
            f"Side: {html.escape(str(payload.get('side') or 'N/A'))}\n"
            f"Entry: {_f(payload.get('entry_price'))}\n"
            f"Exit: {_f(payload.get('exit_price'))}\n"
            f"Final Stop: {_f(payload.get('final_stop_price'))}\n"
            f"Qty: {_f(payload.get('quantity'), 6)}\n"
            f"Risk: {_f(payload.get('initial_risk_usd'), 2)} USD\n"
            f"PnL: {_signed(payload.get('realized_pnl_usd'), ' USD')}\n"
            f"Result: {_signed(payload.get('r_multiple'), 'R')}\n"
            f"MFE: {_signed(payload.get('mfe_r'), 'R')}\n"
            f"MAE: {_signed(payload.get('mae_r'), 'R')}\n"
            f"Holding: {_duration_ms(payload.get('entry_timestamp_ms'), payload.get('closed_timestamp_ms'))}\n"
            f"Reason: {html.escape(str(payload.get('exit_reason') or 'UNKNOWN'))}\n"
            f"Outcome: {html.escape(str(payload.get('outcome_id') or 'N/A'))}\n"
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
        return (
            f"Profile: {html.escape(self.profile)}\n"
            f"Entries enabled: {str(snap.entries_enabled).lower()}\n"
            f"Operator block: {str(operator_entries_blocked(self.repo_root, self.profile)).lower()}\n"
            f"Position: {'FLAT' if pos is None else html.escape(pos.symbol + ' ' + pos.side)}\n"
            f"Entry inflight: {'NONE' if snap.entry_inflight is None else html.escape(snap.entry_inflight.proposal_id)}\n"
            f"Pending outcomes: {self.worker.durable.outbox.pending_count()}\n"
            f"Daily PnL: {_signed(daily.realized_pnl_usd, ' USD')}\n"
            f"Daily halt: {str(daily.halted).lower()}\n"
            f"Last event: {html.escape(snap.health.last_event or 'NONE')}"
        )

    def _position_body(self) -> str:
        pos = self.worker.state.open_position
        if pos is None:
            return "Position: FLAT"
        return self._open_panel(pos, recovered=False).replace("📊 <b>TRADE OPEN</b>\n\n", "")

    def _health_body(self) -> str:
        health = asdict(self.worker.state.health)
        return "\n".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in health.items())

    def _recent_body(self) -> str:
        rows = self.worker.durable.history.records()
        if not rows:
            return "No completed trades."
        payload = rows[-1]["payload"]
        return self._close_panel(payload, acked=not self._outcome_pending(str(payload.get("outcome_id") or ""))).replace(
            "✅ <b>TRADE CLOSED</b>\n\n", ""
        )

    def _pnl_body(self) -> str:
        daily = self.worker.state.daily_risk
        return (
            f"UTC day: {html.escape(daily.utc_day or 'NOT_ROLLED')}\n"
            f"Realized: {_signed(daily.realized_pnl_usd, ' USD')}\n"
            f"Peak realized: {_signed(daily.peak_realized_pnl_usd, ' USD')}\n"
            f"Highest unrealized: {_signed(daily.highest_unrealized_usd, ' USD')}\n"
            f"Trades closed: {daily.trades_closed}\n"
            f"Halted: {str(daily.halted).lower()}\n"
            f"Reason: {html.escape(daily.halt_reason or 'NONE')}"
        )

    def _remote_observation_status(self, *, view: str, title: str) -> None:
        """Display read-only Observation status on the Execution Telegram bot.

        This method runs only on the Telegram command-listener thread.  Failure
        to reach Observation is informational and never mutates worker state.
        """
        reader = self.observation_status_reader
        if reader is None:
            self.dispatcher.send_warning(
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
            self.dispatcher.send_warning(
                "OBSERVATION STATUS UNAVAILABLE",
                f"View: {html.escape(view)}\nExecution and open-position management are unchanged.",
            )
            return
        self.system_log.info(
            "OPERATOR_OBSERVATION_STATUS source=TELEGRAM view=%s authority=NONE",
            view,
        )
        self.dispatcher.send_info(title, body)

    def handle_command(self, text: str) -> None:
        command = str(text or "").strip().split()[0].split("@", 1)[0].lower() if str(text or "").strip() else ""
        try:
            if command == "/status":
                self.dispatcher.send_info("EXECUTION STATUS", self._status_body())
            elif command == "/position":
                self.dispatcher.send_info("POSITION", self._position_body())
            elif command == "/health":
                self.dispatcher.send_info("EXECUTION HEALTH", self._health_body())
            elif command == "/recent":
                self.dispatcher.send_info("RECENT TRADE", self._recent_body())
            elif command == "/pnl":
                self.dispatcher.send_info("DAILY PNL", self._pnl_body())
            elif command == "/observation":
                self._remote_observation_status(view="observation", title="OBSERVATION STATUS")
            elif command == "/recommendation":
                self._remote_observation_status(view="recommendation", title="RECOMMENDATION STATUS")
            elif command == "/memory":
                self._remote_observation_status(view="memory", title="RESEARCH MEMORY")
            elif command == "/epoch":
                self._remote_observation_status(view="epoch", title="RESEARCH EPOCH")
            elif command == "/champion":
                self._remote_observation_status(view="champion", title="RESEARCH CHAMPION")
            elif command == "/challenger":
                self._remote_observation_status(view="challenger", title="CHALLENGER STATUS")
            elif command == "/governance":
                self._remote_observation_status(view="governance", title="RESEARCH GOVERNANCE")
            elif command == "/research":
                self._remote_observation_status(view="research", title="RESEARCH CHAMPION REVIEW")
            elif command == "/paper":
                self._remote_observation_status(view="paper", title="PAPER CHAMPION GATE")
            elif command == "/learning":
                self._remote_observation_status(view="learning", title="V3.9 LEARNING STATUS")
            elif command == "/db":
                self._remote_observation_status(view="db", title="OBSERVATION DATABASE")
            elif command == "/disable":
                set_operator_entry_block(self.repo_root, self.profile, blocked=True)
                self.worker.disable_new_entries()
                self.system_log.warning("OPERATOR_ENTRY_DISABLE source=TELEGRAM")
                self.dispatcher.send_warning("NEW ENTRIES DISABLED", "Open-position management remains active.")
            elif command == "/enable":
                allowed, reason = self.enable_policy()
                if not allowed:
                    self.system_log.warning("OPERATOR_ENTRY_ENABLE_REJECTED reason=%s", reason)
                    self.dispatcher.send_warning("ENABLE REJECTED", html.escape(reason))
                    return
                set_operator_entry_block(self.repo_root, self.profile, blocked=False)
                result = self.worker.enable_new_entries()
                self.system_log.warning("OPERATOR_ENTRY_ENABLE source=TELEGRAM reconciliation=%s", result.status)
                self.dispatcher.send_info("NEW ENTRIES ENABLED", f"Reconciliation: {html.escape(result.status)}")
            elif command == "/help":
                self.dispatcher.send_info(
                    "EXECUTION COMMANDS",
                    "/status — engine/capital summary\n"
                    "/position — current protected position\n"
                    "/health — execution health counters/latency\n"
                    "/recent — most recent completed trade\n"
                    "/pnl — current UTC-day PnL/risk state\n"
                    "\nRead-only Observation / research:\n"
                    "/observation — Observation health\n"
                    "/recommendation — recommendation readiness\n"
                    "/memory — compact research memory\n"
                    "/epoch — research epoch status\n"
                    "/champion — base Research Champion evaluator\n"
                    "/challenger — active/latest challenger + PASS/REJECT\n"
                    "/governance — frozen Research Champion eligibility\n"
                    "/research — Research Champion review/pointer\n"
                    "/paper — frozen Paper Champion gate\n"
                    "/learning — compact combined V3.9 learning status\n"
                    "/db — Observation DB integrity\n"
                    "\nCapital controls:\n"
                    "/disable — block new entries only\n"
                    "/enable — request entry gate; all profile/authority/risk gates still apply\n"
                    "/help — this list",
                )
            elif command:
                self.dispatcher.send_warning("UNKNOWN COMMAND", f"{html.escape(command)}\nUse /help.")
        except Exception as exc:
            self.system_log.warning("OPERATOR_COMMAND_FAILED command=%s error=%s:%s", command, type(exc).__name__, exc)
            self.dispatcher.send_warning("COMMAND FAILED", "Execution safety state was not bypassed.")
