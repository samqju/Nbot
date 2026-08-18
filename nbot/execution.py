from __future__ import annotations

import json
import logging
import math
import os
import time
import uuid
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .execution_protocol import ExecutionOutcome, ExecutionProposal, TradeRequest, TradeResponse


EXECUTION_STATE_VERSION = "NBOT_V2_EXECUTION_STATE_V1"
INTEGER_R_STEP_CONTROL = "INTEGER_R_STEP_CONTROL"
NO_ENTRY_AUTHORITY = "NONE"


class ExecutionSafetyError(RuntimeError):
    pass


class ExecutionInstanceLock:
    """Linux process lock for capital-mutating Execution actions.

    The lock file itself is intentionally not deleted on release. The kernel
    flock is authoritative, so process death releases the lock without an
    unlink/recreate race.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> "ExecutionInstanceLock":
        if self._handle is not None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        os.chmod(self.path, 0o600)
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ExecutionSafetyError(f"EXECUTION_INSTANCE_LOCK_HELD:{self.path}") from exc
        except Exception:
            handle.close()
            raise
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "acquired_at_ms": int(time.time() * 1000)}) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        return self

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._handle = None

    def __enter__(self) -> "ExecutionInstanceLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


@dataclass(frozen=True)
class ExecutionConfig:
    """V2.7 capital-boundary defaults copied from the frozen V1 mechanics.

    They have no live authority by themselves. New entries remain disabled until
    a later phase explicitly supplies an approved entry authority and exit policy.
    """

    environment: str = "TESTNET"
    state_path: Path = Path("data/execution_v2_state.json")
    risk_per_trade_usd: float = 10.0
    max_notional_usd: float = 1000.0
    leverage: int = 5
    max_spread_pct: float = 0.25
    max_reference_price_drift_pct: float = 0.25
    max_quote_age_ms: int = 5_000
    max_future_proposal_skew_ms: int = 5_000

    # Proven V1 execution-policy parity. These defaults intentionally preserve
    # the frozen V1 behavior; they are configurable so later paper/real phases
    # can change policy deliberately rather than through an architecture patch.
    notional_tolerance_pct: float = 1.0
    risk_tolerance_pct: float = 10.0
    max_entry_slippage_pct: float = 1.0
    daily_profit_lock_trigger_r: float = 100.0
    daily_normal_giveback_r: float = 95.0
    daily_profit_giveback_r: float = 3.0
    emergency_flatten_attempts: int = 2
    emergency_verify_delay_seconds: float = 0.5

    allowed_entry_authorities: tuple[str, ...] = ()
    allowed_exit_policies: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.environment not in {"TESTNET", "LIVE"}:
            raise ValueError("EXECUTION_ENVIRONMENT_INVALID")
        if self.risk_per_trade_usd <= 0 or self.max_notional_usd <= 0:
            raise ValueError("EXECUTION_RISK_LIMIT_INVALID")
        if self.leverage <= 0:
            raise ValueError("EXECUTION_LEVERAGE_INVALID")
        if not 0 < self.max_spread_pct <= 5:
            raise ValueError("EXECUTION_SPREAD_LIMIT_INVALID")
        if not 0 <= self.max_reference_price_drift_pct <= 10:
            raise ValueError("EXECUTION_DRIFT_LIMIT_INVALID")
        if self.max_quote_age_ms <= 0 or self.max_future_proposal_skew_ms < 0:
            raise ValueError("EXECUTION_TIME_LIMIT_INVALID")
        if not 0 <= self.notional_tolerance_pct <= 5:
            raise ValueError("EXECUTION_NOTIONAL_TOLERANCE_INVALID")
        if not 0 <= self.risk_tolerance_pct <= 20:
            raise ValueError("EXECUTION_RISK_TOLERANCE_INVALID")
        if not 0 <= self.max_entry_slippage_pct <= 10:
            raise ValueError("EXECUTION_SLIPPAGE_LIMIT_INVALID")
        if self.daily_profit_lock_trigger_r <= 0:
            raise ValueError("EXECUTION_DAILY_PROFIT_LOCK_TRIGGER_INVALID")
        if self.daily_normal_giveback_r <= 0 or self.daily_profit_giveback_r <= 0:
            raise ValueError("EXECUTION_DAILY_GIVEBACK_INVALID")
        if self.emergency_flatten_attempts < 1 or self.emergency_flatten_attempts > 10:
            raise ValueError("EXECUTION_EMERGENCY_ATTEMPTS_INVALID")
        if self.emergency_verify_delay_seconds < 0 or self.emergency_verify_delay_seconds > 10:
            raise ValueError("EXECUTION_EMERGENCY_DELAY_INVALID")
        for authority in self.allowed_entry_authorities:
            if not authority.strip():
                raise ValueError("EXECUTION_ENTRY_AUTHORITY_INVALID")
        for policy in self.allowed_exit_policies:
            if policy != INTEGER_R_STEP_CONTROL:
                raise ValueError(f"EXECUTION_EXIT_POLICY_UNSUPPORTED:{policy}")


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    timestamp_ms: int

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pct(self) -> float:
        return (self.ask - self.bid) / self.mid * 100.0


@dataclass(frozen=True)
class AccountSnapshot:
    available_balance_usd: float


@dataclass(frozen=True)
class Fill:
    price: float
    quantity: float
    order_id: str
    client_order_id: str
    timestamp_ms: int


@dataclass(frozen=True)
class ProtectiveStopRef:
    trigger_price: float
    algo_id: str | None = None
    client_algo_id: str | None = None


@dataclass(frozen=True)
class CloseFill:
    """Authoritative close evidence returned by the execution adapter.

    For exchange-backed execution, ``realized_pnl_usd`` is exchange accounting
    truth when available. ``theoretical_pnl_usd`` and ``pnl_variance_usd`` are
    audit-only diagnostics; they must never veto an otherwise proven exchange
    close. This restores V1's exchange-truth reconciliation principle without
    restoring V1's unsafe zero-value accounting fallback.
    """

    price: float
    timestamp_ms: int
    reason: str
    realized_pnl_usd: float | None = None
    order_ids: tuple[str, ...] = ()
    source: str = "ORDER_RESULT"
    theoretical_pnl_usd: float | None = None
    pnl_variance_usd: float | None = None


@dataclass(frozen=True)
class ExchangePosition:
    symbol: str
    side: str
    quantity: float
    entry_price: float


@dataclass(frozen=True)
class EntryPlan:
    symbol: str
    side: str
    quantity: float
    expected_entry_price: float
    initial_stop: float
    initial_risk_usd: float
    notional_usd: float
    leverage: int


class ExchangePort(Protocol):
    def connect(self) -> None: ...
    def is_healthy(self) -> bool: ...
    def quote(self, symbol: str) -> Quote: ...
    def account_snapshot(self) -> AccountSnapshot: ...
    def position_snapshot(self) -> ExchangePosition | None: ...
    def validate_protective_stop(self, symbol: str, side: str, stop_price: float) -> bool: ...
    def set_leverage(self, symbol: str, leverage: int) -> None: ...
    def open_market(self, plan: EntryPlan, *, client_order_id: str) -> Fill: ...
    def recover_inflight_entry(self, plan: EntryPlan, *, client_order_id: str) -> Fill | None: ...
    def ensure_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> ProtectiveStopRef: ...
    def replace_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> ProtectiveStopRef: ...
    def close_position(self, symbol: str, side: str, *, reason: str) -> CloseFill: ...
    def recover_closed_position(self, local_position: dict[str, Any]) -> CloseFill: ...


class ProposalClient(Protocol):
    def request_trade(self, request: TradeRequest) -> TradeResponse: ...


class OutcomeClient(Protocol):
    def send_outcome(self, outcome: ExecutionOutcome) -> str: ...


class ExecutionStateStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        self.load()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "state_version": EXECUTION_STATE_VERSION,
            "trading_enabled": False,
            "open_position": None,
            "entry_inflight": None,
            "processed_proposal_ids": [],
            "pending_outcomes": [],
            "execution_outcome_history": [],
            "previous_rejection": None,
            "last_close_audit": None,
            "daily_risk": {
                "utc_day": None,
                "realized_pnl_usd": 0.0,
                "peak_realized_pnl_usd": 0.0,
                "loss_floor_usd": None,
                "highest_unrealized_usd": 0.0,
                "halted": False,
                "halt_reason": None,
                "trades_closed": 0,
            },
        }

    def load(self) -> None:
        if not self.path.exists():
            self.data = self._empty()
            return
        try:
            raw = json.loads(self.path.read_text())
        except Exception as exc:
            raise ExecutionSafetyError(f"EXECUTION_STATE_CORRUPT:{type(exc).__name__}") from exc
        if not isinstance(raw, dict):
            raise ExecutionSafetyError("EXECUTION_STATE_CORRUPT_NOT_OBJECT")
        if raw.get("state_version") != EXECUTION_STATE_VERSION:
            raise ExecutionSafetyError("EXECUTION_STATE_VERSION_MISMATCH")
        raw.setdefault("entry_inflight", None)
        raw.setdefault("execution_outcome_history", [])
        raw.setdefault("last_close_audit", None)
        if "daily_risk" not in raw:
            # V2.8.4 -> V2.8.5 migration: reconstruct the current UTC day's
            # accounting from durable completed-execution history instead of
            # silently pretending the day started at zero. The configured loss
            # floor is calculated by ExecutionWorker after state load.
            daily = dict(self._empty()["daily_risk"])
            now_ms = int(time.time() * 1000)
            today = self.utc_day(now_ms)
            daily["utc_day"] = today
            realized = 0.0
            peak = 0.0
            highest_unrealized = 0.0
            trades = 0
            history = list(raw.get("execution_outcome_history", []))
            history.sort(key=lambda row: int(row.get("closed_timestamp_ms") or 0))
            for row in history:
                closed_ms = int(row.get("closed_timestamp_ms") or 0)
                if closed_ms <= 0 or self.utc_day(closed_ms) != today:
                    continue
                pnl = float(row.get("realized_pnl_usd") or 0.0)
                realized += pnl
                peak = max(peak, realized)
                highest_unrealized = max(
                    highest_unrealized,
                    float(row.get("mfe_r") or 0.0) * float(row.get("initial_risk_usd") or 0.0),
                )
                trades += 1
            daily.update({
                "realized_pnl_usd": realized,
                "peak_realized_pnl_usd": peak,
                "highest_unrealized_usd": highest_unrealized,
                "trades_closed": trades,
            })
            raw["daily_risk"] = daily
        if raw.get("open_position") is not None and not isinstance(raw.get("open_position"), dict):
            raise ExecutionSafetyError("EXECUTION_STATE_OPEN_POSITION_INVALID")
        if raw.get("entry_inflight") is not None and not isinstance(raw.get("entry_inflight"), dict):
            raise ExecutionSafetyError("EXECUTION_STATE_ENTRY_INFLIGHT_INVALID")
        for field_name in ("processed_proposal_ids", "pending_outcomes", "execution_outcome_history"):
            if not isinstance(raw.get(field_name, []), list):
                raise ExecutionSafetyError(f"EXECUTION_STATE_{field_name.upper()}_INVALID")
        daily = raw.get("daily_risk")
        if not isinstance(daily, dict):
            raise ExecutionSafetyError("EXECUTION_STATE_DAILY_RISK_INVALID")
        defaults = self._empty()["daily_risk"]
        for key, value in defaults.items():
            daily.setdefault(key, value)
        for key in ("realized_pnl_usd", "peak_realized_pnl_usd", "highest_unrealized_usd"):
            try:
                daily[key] = float(daily[key])
            except (TypeError, ValueError) as exc:
                raise ExecutionSafetyError(f"EXECUTION_STATE_DAILY_{key.upper()}_INVALID") from exc
        if daily.get("loss_floor_usd") is not None:
            try:
                daily["loss_floor_usd"] = float(daily["loss_floor_usd"])
            except (TypeError, ValueError) as exc:
                raise ExecutionSafetyError("EXECUTION_STATE_DAILY_LOSS_FLOOR_INVALID") from exc
        if daily["peak_realized_pnl_usd"] + 1e-9 < daily["realized_pnl_usd"]:
            raise ExecutionSafetyError("EXECUTION_STATE_DAILY_PEAK_INCONSISTENT")
        if int(daily.get("trades_closed", 0)) < 0:
            raise ExecutionSafetyError("EXECUTION_STATE_DAILY_TRADES_INVALID")
        daily["trades_closed"] = int(daily.get("trades_closed", 0))
        daily["halted"] = bool(daily.get("halted", False))
        raw["daily_risk"] = daily
        self.data = raw

    @staticmethod
    def utc_day(timestamp_ms: int) -> str:
        return datetime.fromtimestamp(int(timestamp_ms) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    def roll_daily(self, timestamp_ms: int) -> bool:
        """Reset realized daily accounting on UTC-day rollover.

        Operator entry enablement is independent of this reset. A daily halt is
        automatically cleared for the new UTC day, matching the intended
        semantics of a *daily* risk boundary.
        """
        day = self.utc_day(timestamp_ms)
        daily = dict(self.data.get("daily_risk") or {})
        if daily.get("utc_day") == day:
            return False
        self.data["daily_risk"] = {
            "utc_day": day,
            "realized_pnl_usd": 0.0,
            "peak_realized_pnl_usd": 0.0,
            "loss_floor_usd": None,
            "highest_unrealized_usd": 0.0,
            "halted": False,
            "halt_reason": None,
            "trades_closed": 0,
        }
        self.save()
        return True

    def set_daily_risk(self, daily: dict[str, Any]) -> None:
        self.data["daily_risk"] = dict(daily)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(self.data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.path)
        try:
            directory_fd = os.open(str(self.path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # File fsync + atomic replace is the primary durability contract.
            # Some filesystems do not permit directory fsync.
            pass

    @property
    def open_position(self) -> dict[str, Any] | None:
        return self.data.get("open_position")

    @open_position.setter
    def open_position(self, value: dict[str, Any] | None) -> None:
        self.data["open_position"] = value

    @property
    def entry_inflight(self) -> dict[str, Any] | None:
        return self.data.get("entry_inflight")

    def begin_entry(self, *, proposal: ExecutionProposal, plan: EntryPlan, client_order_id: str, started_at_ms: int) -> None:
        if self.open_position is not None:
            raise ExecutionSafetyError("EXECUTION_BEGIN_ENTRY_WHILE_OPEN")
        if self.entry_inflight is not None:
            raise ExecutionSafetyError("EXECUTION_ENTRY_ALREADY_INFLIGHT")
        self.data["entry_inflight"] = {
            "proposal": proposal.to_dict(),
            "plan": asdict(plan),
            "client_order_id": str(client_order_id),
            "started_at_ms": int(started_at_ms),
            "fill": None,
        }
        self.save()

    def record_inflight_fill(self, fill: Fill) -> None:
        row = self.entry_inflight
        if row is None:
            raise ExecutionSafetyError("EXECUTION_ENTRY_INFLIGHT_MISSING")
        row = dict(row)
        row["fill"] = asdict(fill)
        self.data["entry_inflight"] = row
        self.save()

    def promote_inflight_position(self, position: dict[str, Any]) -> None:
        if self.entry_inflight is None:
            raise ExecutionSafetyError("EXECUTION_ENTRY_INFLIGHT_MISSING")
        if self.open_position is not None:
            raise ExecutionSafetyError("EXECUTION_PROMOTE_ENTRY_WHILE_OPEN")
        self.data["open_position"] = position
        self.data["entry_inflight"] = None
        self.save()

    def clear_entry_inflight(self) -> None:
        self.data["entry_inflight"] = None
        self.save()

    def has_processed(self, proposal_id: str) -> bool:
        return proposal_id in set(self.data.get("processed_proposal_ids", []))

    def reserve(self, proposal_id: str) -> bool:
        if self.has_processed(proposal_id):
            return False
        ids = list(self.data.get("processed_proposal_ids", []))
        ids.append(proposal_id)
        self.data["processed_proposal_ids"] = ids[-10_000:]
        self.save()
        return True

    def queue_outcome(self, outcome: ExecutionOutcome, *, daily_risk: dict[str, Any] | None = None) -> None:
        rows = list(self.data.get("pending_outcomes", []))
        if not any(row.get("outcome_id") == outcome.outcome_id for row in rows):
            rows.append(outcome.to_dict())
        self.data["pending_outcomes"] = rows
        history = list(self.data.get("execution_outcome_history", []))
        if not any(row.get("outcome_id") == outcome.outcome_id for row in history):
            history.append(outcome.to_dict())
        self.data["execution_outcome_history"] = history[-10_000:]
        if daily_risk is not None:
            self.data["daily_risk"] = dict(daily_risk)
        self.save()

    def remove_outcome(self, outcome_id: str) -> None:
        self.data["pending_outcomes"] = [
            row for row in self.data.get("pending_outcomes", []) if row.get("outcome_id") != outcome_id
        ]
        self.save()

    def finalize_open_position(self, outcome: ExecutionOutcome, *, daily_risk: dict[str, Any] | None = None) -> None:
        """Atomically queue a close outcome and clear the local position.

        V1 paper state persisted capital/accounting truth before any learning
        work. V2 keeps that useful rule but makes the close transition one
        atomic execution-state replacement. Deterministic outcome IDs make a
        retry after process death idempotent.
        """
        current = self.open_position
        if current is None:
            raise ExecutionSafetyError("EXECUTION_FINALIZE_WITHOUT_OPEN_POSITION")
        if str(current.get("proposal_id") or "") != outcome.proposal_id:
            raise ExecutionSafetyError("EXECUTION_FINALIZE_PROPOSAL_MISMATCH")
        rows = list(self.data.get("pending_outcomes", []))
        if not any(row.get("outcome_id") == outcome.outcome_id for row in rows):
            rows.append(outcome.to_dict())
        self.data["pending_outcomes"] = rows
        history = list(self.data.get("execution_outcome_history", []))
        if not any(row.get("outcome_id") == outcome.outcome_id for row in history):
            history.append(outcome.to_dict())
        self.data["execution_outcome_history"] = history[-10_000:]
        self.data["open_position"] = None
        self.data["entry_inflight"] = None
        if daily_risk is not None:
            self.data["daily_risk"] = dict(daily_risk)
        self.save()


class IntegerRStepExitPolicy:
    version = INTEGER_R_STEP_CONTROL

    def next_stop(self, position: dict[str, Any]) -> float | None:
        risk = float(position["initial_risk_usd"])
        quantity = float(position["quantity"])
        entry = float(position["entry_price"])
        current = float(position["stop_price"])
        mfe_r = float(position.get("mfe_r", 0.0))
        if risk <= 0 or quantity <= 0 or mfe_r < 1.0:
            return None
        locked_r = math.floor(mfe_r) - 1
        if position["side"] == "LONG":
            candidate = entry + locked_r * risk / quantity
            return candidate if candidate > current else None
        candidate = entry - locked_r * risk / quantity
        return candidate if candidate < current else None


EXIT_POLICIES = {INTEGER_R_STEP_CONTROL: IntegerRStepExitPolicy()}


class ExecutionHealth:
    """Low-overhead execution-only health counters for operator visibility."""

    def __init__(self):
        self.counters: dict[str, int] = {
            "prepare_calls": 0,
            "flat_cycles": 0,
            "open_position_ticks": 0,
            "stop_updates": 0,
            "emergency_exits": 0,
            "reconciliations": 0,
            "proposal_rejections": 0,
        }
        self.last_position_manage_ms = 0.0
        self.max_position_manage_ms = 0.0
        self.last_event: str | None = None

    def inc(self, key: str, amount: int = 1) -> None:
        self.counters[key] = int(self.counters.get(key, 0)) + int(amount)

    def observe_manage_ms(self, value: float) -> None:
        value = max(0.0, float(value))
        self.last_position_manage_ms = value
        self.max_position_manage_ms = max(self.max_position_manage_ms, value)

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.counters,
            "last_position_manage_ms": self.last_position_manage_ms,
            "max_position_manage_ms": self.max_position_manage_ms,
            "last_event": self.last_event,
        }


class ExecutionWorker:
    """V2.7 capital-only worker. No research/selection/champion dependency."""

    def __init__(
        self,
        config: ExecutionConfig,
        exchange: ExchangePort,
        proposal_client: ProposalClient,
        outcome_client: OutcomeClient | None = None,
        *,
        state: ExecutionStateStore | None = None,
        now_ms=None,
        logger: logging.Logger | None = None,
        trade_logger: logging.Logger | None = None,
        notifier: Any | None = None,
        sleep_fn=None,
    ):
        config.validate()
        self.config = config
        self.exchange = exchange
        self.proposal_client = proposal_client
        self.outcome_client = outcome_client
        self.state = state or ExecutionStateStore(config.state_path)
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._sleep = sleep_fn or time.sleep
        self.logger = logger or logging.getLogger("nbot.v2.execution")
        self.trade_logger = trade_logger or logging.getLogger("nbot.v2.execution.trade")
        self.notifier = notifier
        self.health = ExecutionHealth()
        self._prepared = False

    @property
    def entry_authority(self) -> str:
        return self.config.allowed_entry_authorities[0] if self.config.allowed_entry_authorities else NO_ENTRY_AUTHORITY

    def _log(self, level: str, event: str, **fields: Any) -> None:
        message = event
        if fields:
            message += " " + " ".join(f"{key}={value}" for key, value in fields.items())
        getattr(self.logger, level, self.logger.info)(message)
        self.health.last_event = event

    def _trade_log(self, event: str, **fields: Any) -> None:
        message = event
        if fields:
            message += " " + " ".join(f"{key}={value}" for key, value in fields.items())
        self.trade_logger.info(message)

    def _notify(self, level: str, title: str, body: str = "") -> None:
        if self.notifier is None:
            return
        try:
            getattr(self.notifier, level)(title, body)
        except Exception as exc:
            # Operator visibility can fail; capital management cannot.
            self._log("error", "OPERATOR_NOTIFICATION_FAILED", error=f"{type(exc).__name__}:{exc}")

    def _daily_floor_usd(self, peak_realized_pnl_usd: float) -> float:
        peak_r = float(peak_realized_pnl_usd) / self.config.risk_per_trade_usd
        giveback_r = (
            self.config.daily_profit_giveback_r
            if peak_r >= self.config.daily_profit_lock_trigger_r
            else self.config.daily_normal_giveback_r
        )
        return (peak_r - giveback_r) * self.config.risk_per_trade_usd

    def _roll_daily(self, timestamp_ms: int) -> None:
        previous = (self.state.data.get("daily_risk") or {}).get("utc_day")
        if self.state.roll_daily(timestamp_ms):
            current = self.state.data["daily_risk"]["utc_day"]
            self._log("info", "UTC_DAY_ROLLOVER", previous=previous, current=current)
        daily = dict(self.state.data.get("daily_risk") or {})
        floor = self._daily_floor_usd(float(daily.get("peak_realized_pnl_usd", 0.0)))
        realized = float(daily.get("realized_pnl_usd", 0.0))
        halted = realized < floor
        changed = (
            daily.get("loss_floor_usd") != floor
            or bool(daily.get("halted", False)) != halted
            or daily.get("halt_reason") != ("DAILY_LOSS_FLOOR_BREACH" if halted else None)
        )
        if changed:
            daily["loss_floor_usd"] = floor
            daily["halted"] = halted
            daily["halt_reason"] = "DAILY_LOSS_FLOOR_BREACH" if halted else None
            self.state.set_daily_risk(daily)
            self.state.save()

    def _daily_after_close(self, outcome: ExecutionOutcome) -> dict[str, Any]:
        # A close belongs to the UTC day on which Binance/execution says it
        # closed, not the day on which the position was opened.
        self._roll_daily(outcome.closed_timestamp_ms)
        daily = dict(self.state.data.get("daily_risk") or {})
        realized = float(daily.get("realized_pnl_usd", 0.0)) + float(outcome.realized_pnl_usd)
        peak = max(float(daily.get("peak_realized_pnl_usd", 0.0)), realized)
        floor = self._daily_floor_usd(peak)
        halted = realized < floor
        daily.update({
            "realized_pnl_usd": realized,
            "peak_realized_pnl_usd": peak,
            "loss_floor_usd": floor,
            "halted": halted,
            "halt_reason": "DAILY_LOSS_FLOOR_BREACH" if halted else None,
            "trades_closed": int(daily.get("trades_closed", 0)) + 1,
        })
        return daily

    def _daily_entry_allowed(self) -> bool:
        self._roll_daily(self._now_ms())
        daily = dict(self.state.data.get("daily_risk") or {})
        if bool(daily.get("halted", False)):
            self._log(
                "error", "DAILY_HALT",
                realized=daily.get("realized_pnl_usd"),
                peak=daily.get("peak_realized_pnl_usd"),
                floor=daily.get("loss_floor_usd"),
            )
            return False
        return True

    def _verified_emergency_close(self, symbol: str, side: str, *, reason: str) -> CloseFill:
        self.health.inc("emergency_exits")
        self._log("error", "EMERGENCY_EXIT_TRIGGERED", symbol=symbol, side=side, reason=reason)
        self._notify("critical", "EXECUTION EMERGENCY EXIT", f"Symbol: {symbol}\nSide: {side}\nReason: {reason}")
        last_close: CloseFill | None = None
        last_error: Exception | None = None
        for attempt in range(1, self.config.emergency_flatten_attempts + 1):
            try:
                last_close = self.exchange.close_position(symbol, side, reason=reason)
            except Exception as exc:
                last_error = exc
                self._log("error", "EMERGENCY_EXIT_SEND_FAILED", attempt=attempt, error=f"{type(exc).__name__}:{exc}")
            if self.config.emergency_verify_delay_seconds:
                self._sleep(self.config.emergency_verify_delay_seconds)
            try:
                remaining = self.exchange.position_snapshot()
            except Exception as exc:
                last_error = exc
                self._log("error", "EMERGENCY_EXIT_VERIFY_FAILED", attempt=attempt, error=f"{type(exc).__name__}:{exc}")
                continue
            if remaining is None:
                if last_close is None:
                    raise ExecutionSafetyError("EMERGENCY_EXIT_FLAT_WITHOUT_CLOSE_ACCOUNTING")
                self._log("info", "EMERGENCY_EXIT_CONFIRMED_FLAT", attempt=attempt, symbol=symbol)
                return last_close
            self._log("error", "EMERGENCY_EXIT_STILL_EXPOSED", attempt=attempt, symbol=remaining.symbol, side=remaining.side, quantity=remaining.quantity)
        suffix = "" if last_error is None else f":{type(last_error).__name__}:{last_error}"
        raise ExecutionSafetyError(f"EMERGENCY_EXIT_FAILED_NOT_FLAT{suffix}")

    def _post_fill_violation(
        self, proposal: ExecutionProposal, plan: EntryPlan, fill: Fill, stop_ref: ProtectiveStopRef,
    ) -> str | None:
        tolerance = self.config.notional_tolerance_pct / 100.0
        executed_notional = float(fill.price) * float(fill.quantity)
        min_notional = float(plan.notional_usd) * (1.0 - tolerance)
        max_notional = float(plan.notional_usd) * (1.0 + tolerance)
        if not (min_notional <= executed_notional <= max_notional):
            return "POST_FILL_NOTIONAL_BREACH"
        slippage_pct = abs(float(fill.price) - float(plan.expected_entry_price)) / float(plan.expected_entry_price) * 100.0
        if slippage_pct > self.config.max_entry_slippage_pct:
            return "POST_FILL_SLIPPAGE_BREACH"
        actual_risk = abs(float(fill.price) - float(stop_ref.trigger_price)) * float(fill.quantity)
        max_risk = float(plan.initial_risk_usd) * (1.0 + self.config.risk_tolerance_pct / 100.0)
        if actual_risk > max_risk + 1e-9:
            return "POST_FILL_RISK_BREACH"
        return None

    def prepare(self) -> str:
        self.health.inc("prepare_calls")
        self.exchange.connect()
        self._roll_daily(self._now_ms())
        exchange_position = self.exchange.position_snapshot()
        local = self.state.open_position
        inflight = self.state.entry_inflight
        if local is not None and inflight is not None:
            raise ExecutionSafetyError("EXECUTION_STATE_OPEN_AND_ENTRY_INFLIGHT")
        if local is None and inflight is not None:
            result = self._recover_inflight_entry(inflight, exchange_position)
            self._prepared = True
            self._log("info", "EXECUTION_PREPARED", result=result)
            return result
        if local is None and exchange_position is not None:
            # A position with no local V2 entry journal cannot be assigned a
            # proposal/risk/policy identity safely. Keep the proven V1 rule
            # that exchange truth wins, but do not fabricate missing metadata.
            raise ExecutionSafetyError("UNMANAGED_EXCHANGE_POSITION")
        if local is not None:
            self._load_exit_policy(str(local["exit_policy_version"]))
            if exchange_position is None:
                self._recover_exchange_flat(local)
                self._prepared = True
                self._log("info", "EXECUTION_PREPARED", result="RECOVERED_CLOSED_POSITION")
                return "RECOVERED_CLOSED_POSITION"
            self._assert_position_match(local, exchange_position)
            stop_ref = self.exchange.ensure_protective_stop(
                local["symbol"], local["side"], float(local["quantity"]), float(local["stop_price"])
            )
            self._store_stop_ref(local, stop_ref)
            self.state.open_position = local
            self.state.save()
        self._prepared = True
        result = "POSITION_OPEN" if local is not None else "FLAT"
        self._log("info", "EXECUTION_PREPARED", result=result)
        return result

    @staticmethod
    def _store_stop_ref(position: dict[str, Any], stop_ref: ProtectiveStopRef | None) -> None:
        if stop_ref is None:
            return
        position["stop_price"] = float(stop_ref.trigger_price)
        position["protective_stop_algo_id"] = stop_ref.algo_id
        position["protective_stop_client_algo_id"] = stop_ref.client_algo_id

    def _position_from_fill(
        self,
        proposal: ExecutionProposal,
        plan: EntryPlan,
        fill: Fill,
        stop_ref: ProtectiveStopRef | None,
    ) -> dict[str, Any]:
        # Recovery must use the risk contract that was durably persisted before
        # the entry order, not whatever configuration happens to be loaded after
        # a restart.  The stop is still adjusted to the actual exchange fill so
        # the original dollar risk is preserved.
        actual_stop = self._stop_for_fill(
            proposal.direction,
            float(fill.price),
            float(fill.quantity),
            risk_usd=float(plan.initial_risk_usd),
        )
        position = {
            "proposal_id": proposal.proposal_id,
            "environment": proposal.environment,
            "symbol": proposal.symbol,
            "side": proposal.direction,
            "entry_price": float(fill.price),
            "quantity": float(fill.quantity),
            "initial_risk_usd": float(plan.initial_risk_usd),
            "stop_price": actual_stop,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "entry_timestamp_ms": int(fill.timestamp_ms),
            "entry_order_id": fill.order_id,
            "entry_client_order_id": fill.client_order_id,
            "entry_authority": proposal.entry_authority,
            "model_version": proposal.model_version,
            "exit_policy_version": proposal.exit_policy_version,
            "feature_version": proposal.feature_version,
            "data_generation_id": proposal.data_generation_id,
            "market_event_id": proposal.market_event_id,
            "reference_price": proposal.reference_price,
            "advisory_initial_risk": proposal.advisory_initial_risk,
            "protective_stop_algo_id": None,
            "protective_stop_client_algo_id": None,
        }
        self._store_stop_ref(position, stop_ref)
        return position

    def _recover_inflight_entry(
        self, inflight: dict[str, Any], exchange_position: ExchangePosition | None,
    ) -> str:
        """Recover the crash window between entry intent and durable OPEN state.

        V1 had mature restart reconciliation. V2.8.4 restores that behavior
        without guessing: the persisted client order ID plus exchange order and
        position truth must prove the entry. No new entry order is submitted.
        """
        try:
            proposal = ExecutionProposal.from_dict(inflight["proposal"])
            plan = EntryPlan(**dict(inflight["plan"]))
            client_order_id = str(inflight["client_order_id"])
        except Exception as exc:
            raise ExecutionSafetyError("EXECUTION_ENTRY_INFLIGHT_CORRUPT") from exc
        if proposal.environment != self.config.environment:
            raise ExecutionSafetyError("EXECUTION_ENTRY_INFLIGHT_ENVIRONMENT_MISMATCH")
        self._load_exit_policy(proposal.exit_policy_version)

        stored_fill = inflight.get("fill")
        fill = Fill(**dict(stored_fill)) if isinstance(stored_fill, dict) else None
        if fill is None:
            try:
                fill = self.exchange.recover_inflight_entry(plan, client_order_id=client_order_id)
            except Exception as exc:
                raise ExecutionSafetyError(
                    f"ENTRY_INFLIGHT_RECOVERY_FAILED:{type(exc).__name__}:{exc}"
                ) from exc
        if fill is None:
            if exchange_position is not None:
                raise ExecutionSafetyError("ENTRY_INFLIGHT_NOT_FILLED_BUT_POSITION_EXISTS")
            self.state.clear_entry_inflight()
            return "FLAT"

        if str(fill.client_order_id) != client_order_id:
            raise ExecutionSafetyError("ENTRY_INFLIGHT_CLIENT_ORDER_ID_MISMATCH")
        if fill.quantity <= 0 or fill.price <= 0:
            raise ExecutionSafetyError("ENTRY_INFLIGHT_FILL_INVALID")
        self.state.record_inflight_fill(fill)
        position = self._position_from_fill(proposal, plan, fill, None)

        # The entry may itself have opened and closed while Execution was down.
        # Persist its proven identity first, then run the same exchange-truth
        # close recovery used for any other locally known position.
        if exchange_position is None:
            self.state.promote_inflight_position(position)
            self._recover_exchange_flat(position)
            return "RECOVERED_CLOSED_POSITION"

        self._assert_position_match(position, exchange_position)
        stop_ref = self.exchange.ensure_protective_stop(
            position["symbol"], position["side"], float(position["quantity"]), float(position["stop_price"])
        )
        self._store_stop_ref(position, stop_ref)
        violation = self._post_fill_violation(proposal, plan, fill, stop_ref)
        if violation is not None:
            # The recovered fill is already protected; flatten it rather than
            # silently adopting a position outside the persisted entry contract.
            self.state.promote_inflight_position(position)
            close = self._verified_emergency_close(position["symbol"], position["side"], reason=violation)
            self._finalize_closed_position(close)
            return "RECOVERED_CLOSED_POSITION"
        self.state.promote_inflight_position(position)
        self._log("info", "ENTRY_INFLIGHT_RECOVERED", proposal_id=proposal.proposal_id, symbol=position["symbol"])
        return "POSITION_OPEN"

    def _recover_exchange_flat(self, position: dict[str, Any]) -> None:
        """Recover a close that occurred while Execution was offline.

        Exchange truth is authoritative, as in the proven V1 reconciliation
        path, but V2 refuses to invent a zero-price close. The adapter must
        provide sufficient close evidence or local OPEN state is preserved and
        new entries remain blocked.
        """
        try:
            close = self.exchange.recover_closed_position(position)
        except Exception as exc:
            raise ExecutionSafetyError(
                f"EXTERNAL_CLOSE_RECOVERY_FAILED:{type(exc).__name__}:{exc}"
            ) from exc
        self._finalize_closed_position(close)

    def _assert_position_match(self, local: dict[str, Any], exchange_position: ExchangePosition) -> None:
        if (
            local["symbol"] != exchange_position.symbol
            or local["side"] != exchange_position.side
            or abs(float(local["quantity"]) - float(exchange_position.quantity)) > 1e-9
        ):
            raise ExecutionSafetyError("EXECUTION_RECONCILIATION_MISMATCH")

    def _load_exit_policy(self, version: str) -> IntegerRStepExitPolicy:
        policy = EXIT_POLICIES.get(version)
        if policy is None:
            raise ExecutionSafetyError(f"EXIT_POLICY_NOT_INSTALLED:{version}")
        return policy

    def enable_new_entries(self) -> None:
        self._roll_daily(self._now_ms())
        if bool((self.state.data.get("daily_risk") or {}).get("halted", False)):
            raise ExecutionSafetyError("DAILY_RISK_HALT_ACTIVE")
        self.state.data["trading_enabled"] = True
        self.state.save()
        self._log("info", "EXECUTION_NEW_ENTRIES_ENABLED")

    def disable_new_entries(self) -> None:
        self.state.data["trading_enabled"] = False
        self.state.save()
        self._log("info", "EXECUTION_NEW_ENTRIES_DISABLED")

    def process_flat_cycle(self) -> str:
        self.health.inc("flat_cycles")
        if not self._prepared:
            self.prepare()
        if self.state.open_position is not None:
            return "POSITION_OPEN"
        if not self._deliver_pending_outcomes():
            return "PENDING_OUTCOME"
        if not self.state.data.get("trading_enabled", False):
            return "ENTRY_DISABLED"
        if not self._daily_entry_allowed():
            return "DAILY_BLOCKED"
        if not self.config.allowed_entry_authorities or not self.config.allowed_exit_policies:
            return "NO_APPROVED_AUTHORITY"
        now = self._now_ms()
        previous = self.state.data.get("previous_rejection") or {}
        request = TradeRequest.create(
            request_id=f"REQ-{uuid.uuid4().hex}",
            requested_at_ms=now,
            environment=self.config.environment,
            previous_proposal_id=previous.get("proposal_id"),
            previous_rejection_reason=previous.get("reason"),
        )
        self._log(
            "info", "TRADE_REQUEST_CREATED", request_id=request.request_id,
            previous_proposal_id=request.previous_proposal_id,
            previous_rejection_reason=request.previous_rejection_reason,
        )
        try:
            response = self.proposal_client.request_trade(request)
        except Exception as exc:
            self._log("warning", "OBSERVATION_REQUEST_FAILED", request_id=request.request_id, error=f"{type(exc).__name__}:{exc}")
            return "OBSERVATION_UNAVAILABLE"
        self._log(
            "info", "TRADE_REQUEST_RESULT", request_id=request.request_id, status=response.status,
            proposal_id=None if response.proposal is None else response.proposal.proposal_id,
        )
        self.state.data["previous_rejection"] = None
        self.state.save()
        if response.status == "NOT_READY":
            return "NOT_READY"
        if response.status == "NO_TRADE":
            return "NO_TRADE"
        return self._validate_and_enter(response.proposal)

    def _reject(self, proposal: ExecutionProposal, reason: str) -> str:
        self.health.inc("proposal_rejections")
        self.state.data["previous_rejection"] = {"proposal_id": proposal.proposal_id, "reason": reason}
        self.state.save()
        self._log("info", "EXECUTION_PROPOSAL_REJECTED", proposal_id=proposal.proposal_id, reason=reason)
        return f"PROPOSAL_REJECTED:{reason}"

    def _validate_and_enter(self, proposal: ExecutionProposal | None) -> str:
        if proposal is None:
            raise ExecutionSafetyError("PROPOSAL_RESPONSE_MISSING_PROPOSAL")
        now = self._now_ms()
        if proposal.environment != self.config.environment:
            return self._reject(proposal, "ENVIRONMENT_MISMATCH")
        if proposal.generated_at_ms > now + self.config.max_future_proposal_skew_ms:
            return self._reject(proposal, "FUTURE_TIMESTAMP")
        if proposal.is_expired(now):
            return self._reject(proposal, "EXPIRED")
        if self.state.has_processed(proposal.proposal_id):
            return self._reject(proposal, "DUPLICATE")
        if proposal.entry_authority not in self.config.allowed_entry_authorities:
            return self._reject(proposal, "ENTRY_AUTHORITY_NOT_APPROVED")
        if proposal.exit_policy_version not in self.config.allowed_exit_policies:
            return self._reject(proposal, "EXIT_POLICY_NOT_APPROVED")
        self._load_exit_policy(proposal.exit_policy_version)
        if not self.exchange.is_healthy():
            return self._reject(proposal, "EXCHANGE_UNHEALTHY")
        if self.exchange.position_snapshot() is not None:
            return self._reject(proposal, "POSITION_ALREADY_OPEN")

        quote = self.exchange.quote(proposal.symbol)
        if quote.timestamp_ms > now + self.config.max_future_proposal_skew_ms or now - quote.timestamp_ms > self.config.max_quote_age_ms:
            return self._reject(proposal, "QUOTE_STALE_OR_FUTURE")
        if quote.bid <= 0 or quote.ask <= quote.bid:
            return self._reject(proposal, "QUOTE_INVALID")
        if quote.spread_pct > self.config.max_spread_pct:
            return self._reject(proposal, "SPREAD_TOO_WIDE")
        entry_price = quote.ask if proposal.direction == "LONG" else quote.bid
        drift_pct = abs(entry_price - proposal.reference_price) / proposal.reference_price * 100.0
        if drift_pct > self.config.max_reference_price_drift_pct:
            return self._reject(proposal, "REFERENCE_PRICE_DRIFT")

        plan = self._build_plan(proposal, entry_price)
        account = self.exchange.account_snapshot()
        if account.available_balance_usd * self.config.leverage + 1e-9 < plan.notional_usd:
            return self._reject(proposal, "INSUFFICIENT_MARGIN")
        if not self.exchange.validate_protective_stop(plan.symbol, plan.side, plan.initial_stop):
            return self._reject(proposal, "PROTECTIVE_STOP_INFEASIBLE")
        if not self.state.reserve(proposal.proposal_id):
            return self._reject(proposal, "DUPLICATE")

        self.exchange.set_leverage(plan.symbol, plan.leverage)
        client_order_id = f"NBV28-{proposal.proposal_id[:20]}"
        # Persist the complete entry identity BEFORE the first order-capable
        # call. A process death from this point onward is recoverable without a
        # duplicate market order.
        self.state.begin_entry(
            proposal=proposal, plan=plan, client_order_id=client_order_id, started_at_ms=now,
        )
        fill = self.exchange.open_market(plan, client_order_id=client_order_id)
        self.state.record_inflight_fill(fill)
        actual_stop = self._stop_for_fill(
            proposal.direction, fill.price, fill.quantity,
            risk_usd=plan.initial_risk_usd,
        )
        try:
            stop_ref = self.exchange.ensure_protective_stop(plan.symbol, plan.side, fill.quantity, actual_stop)
        except Exception as exc:
            close = self._verified_emergency_close(plan.symbol, plan.side, reason="PROTECTION_FAILED")
            self._queue_failed_entry_outcome(proposal, plan, fill, close, actual_stop)
            self.state.clear_entry_inflight()
            raise ExecutionSafetyError("PROTECTION_FAILED_EMERGENCY_CLOSED") from exc

        violation = self._post_fill_violation(proposal, plan, fill, stop_ref)
        if violation is not None:
            close = self._verified_emergency_close(plan.symbol, plan.side, reason=violation)
            self._queue_failed_entry_outcome(proposal, plan, fill, close, stop_ref.trigger_price)
            self.state.clear_entry_inflight()
            raise ExecutionSafetyError(f"{violation}_EMERGENCY_CLOSED")

        position = self._position_from_fill(proposal, plan, fill, stop_ref)
        self.state.promote_inflight_position(position)
        self._log(
            "info", "POSITION_OPENED", proposal_id=proposal.proposal_id, symbol=plan.symbol, side=plan.side,
            entry=fill.price, quantity=fill.quantity, initial_stop=stop_ref.trigger_price,
            risk_usd=plan.initial_risk_usd, leverage=plan.leverage, entry_order_id=fill.order_id,
            market_event_id=proposal.market_event_id, model_version=proposal.model_version,
        )
        self._trade_log(
            "TRADE_OPEN", proposal_id=proposal.proposal_id, symbol=plan.symbol, side=plan.side,
            entry=fill.price, quantity=fill.quantity, risk_usd=plan.initial_risk_usd,
            entry_order_id=fill.order_id, entry_client_order_id=fill.client_order_id,
            market_event_id=proposal.market_event_id, model_version=proposal.model_version,
        )
        self._notify(
            "info", "TRADE OPEN",
            f"Symbol: {plan.symbol}\nSide: {plan.side}\nEntry: {fill.price}\nQty: {fill.quantity}\nRisk: ${plan.initial_risk_usd:.2f}\nStop: {stop_ref.trigger_price}",
        )
        return "ENTRY_OPENED"

    def _build_plan(self, proposal: ExecutionProposal, entry_price: float) -> EntryPlan:
        quantity = self.config.max_notional_usd / entry_price
        stop = self._stop_for_fill(
            proposal.direction, entry_price, quantity,
            risk_usd=self.config.risk_per_trade_usd,
        )
        return EntryPlan(
            proposal.symbol, proposal.direction, quantity, entry_price, stop,
            self.config.risk_per_trade_usd, self.config.max_notional_usd, self.config.leverage,
        )

    def _stop_for_fill(
        self, side: str, price: float, quantity: float, *, risk_usd: float | None = None,
    ) -> float:
        risk = self.config.risk_per_trade_usd if risk_usd is None else float(risk_usd)
        if risk <= 0:
            raise ExecutionSafetyError("INITIAL_RISK_INVALID")
        risk_per_unit = risk / quantity
        stop = price - risk_per_unit if side == "LONG" else price + risk_per_unit
        if stop <= 0:
            raise ExecutionSafetyError("INITIAL_STOP_INVALID")
        return stop

    def process_open_price(self, symbol: str, price: float, timestamp_ms: int) -> str:
        """Capital hot path. Never contacts proposal or outcome clients."""
        started = time.perf_counter()
        self.health.inc("open_position_ticks")
        try:
            if not self._prepared:
                self.prepare()
            position = self.state.open_position
            if position is None:
                return "FLAT"
            if symbol != position["symbol"]:
                return "IGNORED_OTHER_SYMBOL"
            if not math.isfinite(price) or price <= 0:
                raise ExecutionSafetyError("OPEN_POSITION_PRICE_INVALID")

            self._roll_daily(timestamp_ms)
            exchange_position = self.exchange.position_snapshot()
            if exchange_position is None:
                self._recover_exchange_flat(position)
                return "POSITION_CLOSED"
            self._assert_position_match(position, exchange_position)

            entry = float(position["entry_price"])
            qty = float(position["quantity"])
            risk = float(position["initial_risk_usd"])
            pnl = (price - entry) * qty if position["side"] == "LONG" else (entry - price) * qty
            r = pnl / risk
            position["mfe_r"] = max(float(position.get("mfe_r", 0.0)), r)
            position["mae_r"] = min(float(position.get("mae_r", 0.0)), r)

            daily = dict(self.state.data.get("daily_risk") or {})
            daily["highest_unrealized_usd"] = max(float(daily.get("highest_unrealized_usd", 0.0)), pnl)
            self.state.set_daily_risk(daily)

            # V1 parity: a protective stop is primary, but an observed loss that
            # exceeds the immutable risk contract plus tolerance is a verified
            # emergency-flatten condition rather than a reason to keep waiting.
            max_allowed_loss = risk * (1.0 + self.config.risk_tolerance_pct / 100.0)
            if pnl < -max_allowed_loss:
                close = self._verified_emergency_close(
                    position["symbol"], position["side"], reason="RISK_CONTRACT_BREACH",
                )
                self._finalize_closed_position(close)
                return "POSITION_CLOSED"

            policy = self._load_exit_policy(str(position["exit_policy_version"]))
            next_stop = policy.next_stop(position)
            if next_stop is not None:
                stop_ref = self.exchange.replace_protective_stop(position["symbol"], position["side"], qty, next_stop)
                position["stop_price"] = next_stop
                self._store_stop_ref(position, stop_ref)
                self.health.inc("stop_updates")
                self._log(
                    "info", "PROTECTIVE_STOP_UPDATED", symbol=position["symbol"],
                    proposal_id=position.get("proposal_id"), stop=position["stop_price"], mfe_r=position["mfe_r"],
                )

            breached = price <= float(position["stop_price"]) if position["side"] == "LONG" else price >= float(position["stop_price"])
            if breached:
                close = self._verified_emergency_close(
                    position["symbol"], position["side"], reason="LOCAL_STOP_BREACH",
                )
                self._finalize_closed_position(close)
                return "POSITION_CLOSED"

            self.state.open_position = position
            self.state.save()
            return "POSITION_MANAGED"
        finally:
            self.health.observe_manage_ms((time.perf_counter() - started) * 1000.0)

    def force_close_open_position(self, *, reason: str = "OPERATOR_TESTNET_FLATTEN") -> str:
        """Close the locally managed position without contacting Observation.

        This exists for the V2.8 mechanical canary and emergency/operator cleanup.
        It never creates a new entry and therefore remains available even when
        new-entry authority is disabled after a position has been opened.
        """
        if not self._prepared:
            self.prepare()
        position = self.state.open_position
        if position is None:
            exchange_position = self.exchange.position_snapshot()
            if exchange_position is not None:
                raise ExecutionSafetyError("UNMANAGED_EXCHANGE_POSITION")
            return "FLAT"
        close = self._verified_emergency_close(position["symbol"], position["side"], reason=reason)
        self._finalize_closed_position(close)
        return "POSITION_CLOSED"

    def reconcile_open_position(self) -> str:
        """Exchange reconciliation only; deliberately no Observation dependency."""
        self.health.inc("reconciliations")
        position = self.state.open_position
        exchange_position = self.exchange.position_snapshot()
        if position is None:
            if exchange_position is not None:
                raise ExecutionSafetyError("UNMANAGED_EXCHANGE_POSITION")
            return "FLAT"
        if exchange_position is None:
            self._recover_exchange_flat(position)
            return "POSITION_CLOSE_RECOVERED"
        self._assert_position_match(position, exchange_position)
        stop_ref = self.exchange.ensure_protective_stop(
            position["symbol"], position["side"], float(position["quantity"]), float(position["stop_price"])
        )
        self._store_stop_ref(position, stop_ref)
        self.state.open_position = position
        self.state.save()
        return "POSITION_RECONCILED"

    @staticmethod
    def _deterministic_outcome_id(position: dict[str, Any]) -> str:
        identity = "|".join((
            str(position.get("environment") or ""),
            str(position.get("proposal_id") or ""),
            str(position.get("entry_order_id") or ""),
            str(position.get("entry_client_order_id") or ""),
        ))
        return f"OUT-{uuid.uuid5(uuid.NAMESPACE_URL, 'nbot-v2-execution-outcome|' + identity).hex}"

    def _finalize_closed_position(self, close: CloseFill) -> None:
        position = self.state.open_position
        if position is None:
            return
        qty = float(position["quantity"])
        entry = float(position["entry_price"])
        price_pnl = (close.price - entry) * qty if position["side"] == "LONG" else (entry - close.price) * qty
        pnl = price_pnl if close.realized_pnl_usd is None else float(close.realized_pnl_usd)
        # Exchange accounting wins whenever the adapter supplies it. Local PnL
        # is retained only as an audit comparison and never vetoes settlement.
        theoretical = price_pnl if close.theoretical_pnl_usd is None else float(close.theoretical_pnl_usd)
        variance = (pnl - theoretical) if close.pnl_variance_usd is None else float(close.pnl_variance_usd)
        self.state.data["last_close_audit"] = {
            "proposal_id": position.get("proposal_id"),
            "symbol": position.get("symbol"),
            "source": close.source,
            "reason": close.reason,
            "order_ids": list(close.order_ids),
            "exchange_realized_pnl_usd": None if close.realized_pnl_usd is None else float(close.realized_pnl_usd),
            "theoretical_pnl_usd": theoretical,
            "pnl_variance_usd": variance,
            "closed_timestamp_ms": int(close.timestamp_ms),
        }
        risk = float(position["initial_risk_usd"])
        outcome = ExecutionOutcome.create(
            outcome_id=self._deterministic_outcome_id(position),
            proposal_id=position["proposal_id"],
            environment=position["environment"],
            symbol=position["symbol"],
            side=position["side"],
            entry_price=entry,
            exit_price=float(close.price),
            quantity=qty,
            initial_risk_usd=risk,
            realized_pnl_usd=pnl,
            r_multiple=pnl / risk,
            mae_r=float(position.get("mae_r", 0.0)),
            mfe_r=float(position.get("mfe_r", 0.0)),
            entry_timestamp_ms=int(position["entry_timestamp_ms"]),
            closed_timestamp_ms=int(close.timestamp_ms),
            exit_reason=close.reason,
            entry_authority=position["entry_authority"],
            model_version=position["model_version"],
            exit_policy_version=position["exit_policy_version"],
            feature_version=position["feature_version"],
            data_generation_id=position["data_generation_id"],
            market_event_id=position["market_event_id"],
        )
        daily = self._daily_after_close(outcome)
        self.state.finalize_open_position(outcome, daily_risk=daily)
        self._log(
            "info", "POSITION_CLOSED", outcome_id=outcome.outcome_id, proposal_id=outcome.proposal_id, symbol=outcome.symbol, side=outcome.side,
            exit=outcome.exit_price, realized_pnl_usd=outcome.realized_pnl_usd, r_multiple=outcome.r_multiple,
            exit_reason=outcome.exit_reason, daily_realized_pnl_usd=daily["realized_pnl_usd"],
            daily_loss_floor_usd=daily["loss_floor_usd"],
        )
        self._trade_log(
            "TRADE_CLOSE", outcome_id=outcome.outcome_id, proposal_id=outcome.proposal_id, symbol=outcome.symbol, side=outcome.side,
            exit=outcome.exit_price, realized_pnl_usd=outcome.realized_pnl_usd, r_multiple=outcome.r_multiple,
            exit_reason=outcome.exit_reason, market_event_id=outcome.market_event_id, model_version=outcome.model_version,
        )
        self._notify(
            "info", "TRADE CLOSED",
            f"Symbol: {outcome.symbol}\nSide: {outcome.side}\nExit: {outcome.exit_price}\nPnL: ${outcome.realized_pnl_usd:+.4f}\nResult: {outcome.r_multiple:+.3f}R\nReason: {outcome.exit_reason}",
        )
        if daily["halted"]:
            self._notify(
                "critical", "DAILY RISK HALT",
                f"Realized: ${daily['realized_pnl_usd']:+.2f}\nPeak: ${daily['peak_realized_pnl_usd']:+.2f}\nFloor: ${daily['loss_floor_usd']:+.2f}",
            )

    def _queue_failed_entry_outcome(
        self,
        proposal: ExecutionProposal,
        plan: EntryPlan,
        fill: Fill,
        close: CloseFill,
        stop: float,
    ) -> None:
        theoretical = (
            (close.price - fill.price) * fill.quantity
            if proposal.direction == "LONG"
            else (fill.price - close.price) * fill.quantity
        )
        pnl = theoretical if close.realized_pnl_usd is None else float(close.realized_pnl_usd)
        risk = float(plan.initial_risk_usd)
        outcome = ExecutionOutcome.create(
            outcome_id=f"OUT-{uuid.uuid5(uuid.NAMESPACE_URL, 'nbot-v2-failed-entry|' + proposal.proposal_id + '|' + fill.order_id).hex}", proposal_id=proposal.proposal_id,
            environment=proposal.environment, symbol=proposal.symbol, side=proposal.direction,
            entry_price=fill.price, exit_price=close.price, quantity=fill.quantity,
            initial_risk_usd=risk, realized_pnl_usd=pnl, r_multiple=pnl / risk,
            mae_r=min(0.0, pnl / risk), mfe_r=max(0.0, pnl / risk),
            entry_timestamp_ms=fill.timestamp_ms, closed_timestamp_ms=close.timestamp_ms,
            exit_reason=close.reason, entry_authority=proposal.entry_authority,
            model_version=proposal.model_version, exit_policy_version=proposal.exit_policy_version,
            feature_version=proposal.feature_version, data_generation_id=proposal.data_generation_id,
            market_event_id=proposal.market_event_id,
        )
        daily = self._daily_after_close(outcome)
        self.state.queue_outcome(outcome, daily_risk=daily)
        self._trade_log(
            "TRADE_CLOSE", outcome_id=outcome.outcome_id, proposal_id=outcome.proposal_id, symbol=outcome.symbol, side=outcome.side,
            exit=outcome.exit_price, realized_pnl_usd=outcome.realized_pnl_usd, r_multiple=outcome.r_multiple,
            exit_reason=outcome.exit_reason, market_event_id=outcome.market_event_id, model_version=outcome.model_version,
        )
        if daily["halted"]:
            self._notify(
                "critical", "DAILY RISK HALT",
                f"Realized: ${daily['realized_pnl_usd']:+.2f}\nPeak: ${daily['peak_realized_pnl_usd']:+.2f}\nFloor: ${daily['loss_floor_usd']:+.2f}",
            )

    def _deliver_pending_outcomes(self) -> bool:
        rows = list(self.state.data.get("pending_outcomes", []))
        if not rows:
            return True
        if self.outcome_client is None:
            return False
        for row in rows:
            outcome = ExecutionOutcome.from_dict(row)
            try:
                ack = self.outcome_client.send_outcome(outcome)
            except Exception:
                return False
            if ack not in {"RECORDED", "ALREADY_RECORDED"}:
                self._log("warning", "OUTCOME_DELIVERY_REJECTED", outcome_id=outcome.outcome_id, ack=ack)
                return False
            self._log("info", "OUTCOME_DELIVERED", outcome_id=outcome.outcome_id, proposal_id=outcome.proposal_id, ack=ack)
            self.state.remove_outcome(outcome.outcome_id)
        return True

    def status(self) -> dict[str, Any]:
        daily = dict(self.state.data.get("daily_risk") or {})
        return {
            "phase": "V2.8",
            "role": "EXECUTION_CAPITAL_BOUNDARY",
            "environment": self.config.environment,
            "entry_authority": self.entry_authority,
            "approved_exit_policies": list(self.config.allowed_exit_policies),
            "trading_enabled": bool(self.state.data.get("trading_enabled", False)),
            "position": "OPEN" if self.state.open_position else "FLAT",
            "entry_inflight": self.state.entry_inflight is not None,
            "pending_outcomes": len(self.state.data.get("pending_outcomes", [])),
            "outcome_history": len(self.state.data.get("execution_outcome_history", [])),
            "daily_risk": daily,
            "risk_policy": {
                "risk_per_trade_usd": self.config.risk_per_trade_usd,
                "max_notional_usd": self.config.max_notional_usd,
                "leverage": self.config.leverage,
                "risk_tolerance_pct": self.config.risk_tolerance_pct,
                "notional_tolerance_pct": self.config.notional_tolerance_pct,
                "max_entry_slippage_pct": self.config.max_entry_slippage_pct,
                "daily_profit_lock_trigger_r": self.config.daily_profit_lock_trigger_r,
                "daily_normal_giveback_r": self.config.daily_normal_giveback_r,
                "daily_profit_giveback_r": self.config.daily_profit_giveback_r,
            },
            "health": self.health.snapshot(),
            "research_imports": "NONE",
        }
