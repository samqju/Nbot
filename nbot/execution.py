from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .execution_protocol import ExecutionOutcome, ExecutionProposal, TradeRequest, TradeResponse


EXECUTION_STATE_VERSION = "NBOT_V2_EXECUTION_STATE_V1"
INTEGER_R_STEP_CONTROL = "INTEGER_R_STEP_CONTROL"
NO_ENTRY_AUTHORITY = "NONE"


class ExecutionSafetyError(RuntimeError):
    pass


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
class CloseFill:
    price: float
    timestamp_ms: int
    reason: str


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
    def ensure_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> None: ...
    def replace_protective_stop(self, symbol: str, side: str, quantity: float, stop_price: float) -> None: ...
    def close_position(self, symbol: str, side: str, *, reason: str) -> CloseFill: ...


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
            "processed_proposal_ids": [],
            "pending_outcomes": [],
            "previous_rejection": None,
        }

    def load(self) -> None:
        if not self.path.exists():
            self.data = self._empty()
            return
        raw = json.loads(self.path.read_text())
        if raw.get("state_version") != EXECUTION_STATE_VERSION:
            raise ExecutionSafetyError("EXECUTION_STATE_VERSION_MISMATCH")
        self.data = raw

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(self.data, sort_keys=True, separators=(",", ":"), allow_nan=False)
        temp.write_text(payload + "\n")
        os.replace(temp, self.path)

    @property
    def open_position(self) -> dict[str, Any] | None:
        return self.data.get("open_position")

    @open_position.setter
    def open_position(self, value: dict[str, Any] | None) -> None:
        self.data["open_position"] = value

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

    def queue_outcome(self, outcome: ExecutionOutcome) -> None:
        rows = list(self.data.get("pending_outcomes", []))
        if not any(row.get("outcome_id") == outcome.outcome_id for row in rows):
            rows.append(outcome.to_dict())
        self.data["pending_outcomes"] = rows
        self.save()

    def remove_outcome(self, outcome_id: str) -> None:
        self.data["pending_outcomes"] = [
            row for row in self.data.get("pending_outcomes", []) if row.get("outcome_id") != outcome_id
        ]
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
    ):
        config.validate()
        self.config = config
        self.exchange = exchange
        self.proposal_client = proposal_client
        self.outcome_client = outcome_client
        self.state = state or ExecutionStateStore(config.state_path)
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._prepared = False

    @property
    def entry_authority(self) -> str:
        return self.config.allowed_entry_authorities[0] if self.config.allowed_entry_authorities else NO_ENTRY_AUTHORITY

    def prepare(self) -> str:
        self.exchange.connect()
        exchange_position = self.exchange.position_snapshot()
        local = self.state.open_position
        if local is None and exchange_position is not None:
            raise ExecutionSafetyError("UNMANAGED_EXCHANGE_POSITION")
        if local is not None:
            if exchange_position is None:
                raise ExecutionSafetyError("LOCAL_POSITION_MISSING_ON_EXCHANGE")
            self._assert_position_match(local, exchange_position)
            self._load_exit_policy(str(local["exit_policy_version"]))
            self.exchange.ensure_protective_stop(
                local["symbol"], local["side"], float(local["quantity"]), float(local["stop_price"])
            )
        self._prepared = True
        return "POSITION_OPEN" if local is not None else "FLAT"

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
        self.state.data["trading_enabled"] = True
        self.state.save()

    def disable_new_entries(self) -> None:
        self.state.data["trading_enabled"] = False
        self.state.save()

    def process_flat_cycle(self) -> str:
        if not self._prepared:
            self.prepare()
        if self.state.open_position is not None:
            return "POSITION_OPEN"
        if not self._deliver_pending_outcomes():
            return "PENDING_OUTCOME"
        if not self.state.data.get("trading_enabled", False):
            return "ENTRY_DISABLED"
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
        try:
            response = self.proposal_client.request_trade(request)
        except Exception:
            return "OBSERVATION_UNAVAILABLE"
        self.state.data["previous_rejection"] = None
        self.state.save()
        if response.status == "NOT_READY":
            return "NOT_READY"
        if response.status == "NO_TRADE":
            return "NO_TRADE"
        return self._validate_and_enter(response.proposal)

    def _reject(self, proposal: ExecutionProposal, reason: str) -> str:
        self.state.data["previous_rejection"] = {"proposal_id": proposal.proposal_id, "reason": reason}
        self.state.save()
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
        client_order_id = f"NBV27-{proposal.proposal_id[:20]}"
        fill = self.exchange.open_market(plan, client_order_id=client_order_id)
        actual_stop = self._stop_for_fill(proposal.direction, fill.price, fill.quantity)
        try:
            self.exchange.ensure_protective_stop(plan.symbol, plan.side, fill.quantity, actual_stop)
        except Exception as exc:
            close = self.exchange.close_position(plan.symbol, plan.side, reason="PROTECTION_FAILED")
            self._queue_failed_entry_outcome(proposal, fill, close, actual_stop)
            raise ExecutionSafetyError("PROTECTION_FAILED_EMERGENCY_CLOSED") from exc

        self.state.open_position = {
            "proposal_id": proposal.proposal_id,
            "environment": proposal.environment,
            "symbol": proposal.symbol,
            "side": proposal.direction,
            "entry_price": float(fill.price),
            "quantity": float(fill.quantity),
            "initial_risk_usd": self.config.risk_per_trade_usd,
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
        }
        self.state.save()
        return "ENTRY_OPENED"

    def _build_plan(self, proposal: ExecutionProposal, entry_price: float) -> EntryPlan:
        quantity = self.config.max_notional_usd / entry_price
        stop = self._stop_for_fill(proposal.direction, entry_price, quantity)
        return EntryPlan(
            proposal.symbol, proposal.direction, quantity, entry_price, stop,
            self.config.risk_per_trade_usd, self.config.max_notional_usd, self.config.leverage,
        )

    def _stop_for_fill(self, side: str, price: float, quantity: float) -> float:
        risk_per_unit = self.config.risk_per_trade_usd / quantity
        stop = price - risk_per_unit if side == "LONG" else price + risk_per_unit
        if stop <= 0:
            raise ExecutionSafetyError("INITIAL_STOP_INVALID")
        return stop

    def process_open_price(self, symbol: str, price: float, timestamp_ms: int) -> str:
        """Capital hot path. Never contacts proposal or outcome clients."""
        if not self._prepared:
            self.prepare()
        position = self.state.open_position
        if position is None:
            return "FLAT"
        if symbol != position["symbol"]:
            return "IGNORED_OTHER_SYMBOL"
        if not math.isfinite(price) or price <= 0:
            raise ExecutionSafetyError("OPEN_POSITION_PRICE_INVALID")

        exchange_position = self.exchange.position_snapshot()
        if exchange_position is None:
            self._finalize_closed_position(price, timestamp_ms, "EXCHANGE_POSITION_CLOSED")
            return "POSITION_CLOSED"
        self._assert_position_match(position, exchange_position)

        entry = float(position["entry_price"])
        qty = float(position["quantity"])
        risk = float(position["initial_risk_usd"])
        pnl = (price - entry) * qty if position["side"] == "LONG" else (entry - price) * qty
        r = pnl / risk
        position["mfe_r"] = max(float(position.get("mfe_r", 0.0)), r)
        position["mae_r"] = min(float(position.get("mae_r", 0.0)), r)

        policy = self._load_exit_policy(str(position["exit_policy_version"]))
        next_stop = policy.next_stop(position)
        if next_stop is not None:
            self.exchange.replace_protective_stop(position["symbol"], position["side"], qty, next_stop)
            position["stop_price"] = next_stop

        breached = price <= float(position["stop_price"]) if position["side"] == "LONG" else price >= float(position["stop_price"])
        if breached:
            close = self.exchange.close_position(position["symbol"], position["side"], reason="LOCAL_STOP_BREACH")
            self._finalize_closed_position(close.price, close.timestamp_ms, close.reason)
            return "POSITION_CLOSED"

        self.state.open_position = position
        self.state.save()
        return "POSITION_MANAGED"

    def reconcile_open_position(self) -> str:
        """Exchange reconciliation only; deliberately no Observation dependency."""
        position = self.state.open_position
        exchange_position = self.exchange.position_snapshot()
        if position is None:
            if exchange_position is not None:
                raise ExecutionSafetyError("UNMANAGED_EXCHANGE_POSITION")
            return "FLAT"
        if exchange_position is None:
            raise ExecutionSafetyError("LOCAL_POSITION_MISSING_ON_EXCHANGE")
        self._assert_position_match(position, exchange_position)
        self.exchange.ensure_protective_stop(
            position["symbol"], position["side"], float(position["quantity"]), float(position["stop_price"])
        )
        return "POSITION_RECONCILED"

    def _finalize_closed_position(self, exit_price: float, timestamp_ms: int, reason: str) -> None:
        position = self.state.open_position
        if position is None:
            return
        qty = float(position["quantity"])
        entry = float(position["entry_price"])
        pnl = (exit_price - entry) * qty if position["side"] == "LONG" else (entry - exit_price) * qty
        risk = float(position["initial_risk_usd"])
        outcome = ExecutionOutcome.create(
            outcome_id=f"OUT-{uuid.uuid4().hex}",
            proposal_id=position["proposal_id"],
            environment=position["environment"],
            symbol=position["symbol"],
            side=position["side"],
            entry_price=entry,
            exit_price=float(exit_price),
            quantity=qty,
            initial_risk_usd=risk,
            realized_pnl_usd=pnl,
            r_multiple=pnl / risk,
            mae_r=float(position.get("mae_r", 0.0)),
            mfe_r=float(position.get("mfe_r", 0.0)),
            entry_timestamp_ms=int(position["entry_timestamp_ms"]),
            closed_timestamp_ms=int(timestamp_ms),
            exit_reason=reason,
            entry_authority=position["entry_authority"],
            model_version=position["model_version"],
            exit_policy_version=position["exit_policy_version"],
            feature_version=position["feature_version"],
            data_generation_id=position["data_generation_id"],
            market_event_id=position["market_event_id"],
        )
        self.state.queue_outcome(outcome)
        self.state.open_position = None
        self.state.save()

    def _queue_failed_entry_outcome(self, proposal: ExecutionProposal, fill: Fill, close: CloseFill, stop: float) -> None:
        pnl = (close.price - fill.price) * fill.quantity if proposal.direction == "LONG" else (fill.price - close.price) * fill.quantity
        risk = self.config.risk_per_trade_usd
        outcome = ExecutionOutcome.create(
            outcome_id=f"OUT-{uuid.uuid4().hex}", proposal_id=proposal.proposal_id,
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
        self.state.queue_outcome(outcome)

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
                return False
            self.state.remove_outcome(outcome.outcome_id)
        return True

    def status(self) -> dict[str, Any]:
        return {
            "phase": "V2.7",
            "role": "EXECUTION_CAPITAL_BOUNDARY",
            "environment": self.config.environment,
            "entry_authority": self.entry_authority,
            "approved_exit_policies": list(self.config.allowed_exit_policies),
            "trading_enabled": bool(self.state.data.get("trading_enabled", False)),
            "position": "OPEN" if self.state.open_position else "FLAT",
            "pending_outcomes": len(self.state.data.get("pending_outcomes", [])),
            "research_imports": "NONE",
        }
