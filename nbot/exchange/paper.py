"""Local PAPER implementation of the NBOT V3 :class:`ExchangePort`.

The adapter intentionally contains no Binance/private-order transport.  Market
truth is delegated to a read-only quote source while all capital-changing
operations are simulated in one atomically persisted local paper account.

Important safety properties:

* one paper capital position maximum;
* deterministic, durable entry identity for ambiguous-entry recovery;
* an entry fill exists before protection, preserving the real crash window;
* protective-stop identity is persisted and replacement is atomic;
* stop simulation is driven only by observed Execution market ticks/quotes;
* close results include explicit after-fee paper realized PnL;
* close recovery is keyed by the original deterministic entry client ID;
* corrupt/incompatible paper state fails closed rather than resetting flat.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from nbot.common.atomic_io import atomic_write_json
from nbot.config.profiles import Profile
from nbot.exchange.contracts import (
    AccountSnapshot,
    CloseFill,
    EntryPlan,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Quote,
    Side,
)
from nbot.execution.models import EntryInflight, OpenPosition

PAPER_ACCOUNT_VERSION = "NBOT_V3_PAPER_ACCOUNT_V1"


class PaperExchangeError(RuntimeError):
    """Fail-closed local paper-exchange safety error."""


@runtime_checkable
class PaperMarketDataPort(Protocol):
    """Read-only market boundary required by :class:`PaperExchange`."""

    def connect(self) -> None: ...

    def is_healthy(self) -> bool: ...

    def quote(self, symbol: str) -> Quote: ...


@dataclass(frozen=True, slots=True)
class PaperExchangeConfig:
    starting_balance_usd: float = 10_000.0
    entry_slippage_pct: float = 0.02
    exit_slippage_pct: float = 0.02
    taker_fee_rate: float = 0.0005

    def __post_init__(self) -> None:
        _positive("PAPER_STARTING_BALANCE_USD", self.starting_balance_usd)
        _nonnegative("PAPER_ENTRY_SLIPPAGE_PCT", self.entry_slippage_pct)
        _nonnegative("PAPER_EXIT_SLIPPAGE_PCT", self.exit_slippage_pct)
        fee = _nonnegative("PAPER_TAKER_FEE_RATE", self.taker_fee_rate)
        if fee >= 1.0:
            raise ValueError("PAPER_TAKER_FEE_RATE_INVALID")


class PaperExchange:
    """ExchangePort-compatible local capital simulator for ``live-paper``.

    ``on_market_tick`` is an additional PAPER-only hook.  The future Execution
    worker must feed the same open-symbol market tick into this adapter before
    position management so that local stop settlement is independent from
    Observation and uses Execution's own market truth.
    """

    def __init__(
        self,
        *,
        repo_root: Path | str,
        profile: Profile,
        market_data: PaperMarketDataPort,
        config: PaperExchangeConfig | None = None,
    ) -> None:
        if profile.name != "live-paper":
            raise ValueError("PAPER_PROFILE_MUST_BE_LIVE_PAPER")
        if profile.execution_mode != "PAPER" or profile.binance_order_writes:
            raise ValueError("PAPER_PROFILE_ORDER_AUTHORITY_INVALID")
        if profile.capital_kind != "LOCAL_PAPER" or profile.real_capital:
            raise ValueError("PAPER_PROFILE_CAPITAL_KIND_INVALID")
        if not isinstance(market_data, PaperMarketDataPort):
            raise TypeError("PAPER_MARKET_DATA_PORT_INVALID")

        self.profile = profile
        self.market_data = market_data
        self.config = config or PaperExchangeConfig()
        self.account_path = Path(repo_root) / profile.execution_state_dir / "account.json"
        self._lock = threading.RLock()
        self._state: dict | None = None
        self._connected = False
        self._latest_quotes: dict[str, Quote] = {}

    # ------------------------------------------------------------------
    # ExchangePort market/account boundary
    # ------------------------------------------------------------------

    def connect(self) -> None:
        with self._lock:
            self._load_or_create()
        self.market_data.connect()
        self._connected = True

    def is_healthy(self) -> bool:
        if not self._connected or self._state is None:
            return False
        try:
            return bool(self.market_data.is_healthy())
        except Exception:
            return False

    def quote(self, symbol: str) -> Quote:
        self._require_ready()
        quote = self.market_data.quote(symbol)
        if quote.symbol != symbol:
            raise PaperExchangeError("PAPER_QUOTE_SYMBOL_MISMATCH")
        self.on_market_tick(
            symbol=quote.symbol,
            bid=quote.bid,
            ask=quote.ask,
            timestamp_ms=quote.timestamp_ms,
        )
        return quote

    def wait_quote(
        self,
        symbol: str,
        *,
        after_sequence: int = 0,
        timeout_seconds: float | None = None,
    ):
        """Wait for the next WSS quote and apply it to PAPER stop settlement."""
        self._require_ready()
        wait = getattr(self.market_data, "wait_quote", None)
        if not callable(wait):
            raise PaperExchangeError("PAPER_STREAM_WAIT_UNAVAILABLE")
        update = wait(
            symbol,
            after_sequence=after_sequence,
            timeout_seconds=timeout_seconds,
        )
        quote = update.quote
        if quote.symbol != symbol:
            raise PaperExchangeError("PAPER_QUOTE_SYMBOL_MISMATCH")
        self.on_market_tick(
            symbol=quote.symbol,
            bid=quote.bid,
            ask=quote.ask,
            timestamp_ms=quote.timestamp_ms,
        )
        return update

    def recovery_quote(self, symbol: str) -> Quote:
        """Explicit REST recovery path for an already-open PAPER position."""
        self._require_ready()
        recover = getattr(self.market_data, "recovery_quote", None)
        if not callable(recover):
            raise PaperExchangeError("PAPER_RECOVERY_QUOTE_UNAVAILABLE")
        quote = recover(symbol)
        if quote.symbol != symbol:
            raise PaperExchangeError("PAPER_QUOTE_SYMBOL_MISMATCH")
        self.on_market_tick(
            symbol=quote.symbol,
            bid=quote.bid,
            ask=quote.ask,
            timestamp_ms=quote.timestamp_ms,
        )
        return quote

    def account_snapshot(self) -> AccountSnapshot:
        with self._lock:
            state = self._require_state()
            available = float(state["balance_usd"])
            position = state["position"]
            if position is not None:
                leverage = int(position["leverage"])
                margin = float(position["entry_price"]) * float(position["quantity"]) / leverage
                available = max(0.0, available - margin)
            return AccountSnapshot(available_balance_usd=available)

    def position_snapshot(self) -> ExchangePosition | None:
        with self._lock:
            position = self._require_state()["position"]
            if position is None:
                return None
            return ExchangePosition(
                symbol=position["symbol"],
                side=position["side"],
                quantity=float(position["quantity"]),
                entry_price=float(position["entry_price"]),
            )

    def protective_stop_snapshot(self, symbol: str) -> ProtectiveStopRef | None:
        with self._lock:
            state = self._require_state()
            raw = state["protective_stop"]
            if raw is None:
                return None
            stop = self._decode_stop(raw)
            position = state["position"]
            if position is None:
                # Reconciliation must be able to see/clean an orphan stop while
                # the paper capital position is already flat.
                return stop if stop.symbol == symbol else None
            if position["symbol"] != symbol:
                return None
            return stop

    def validate_protective_stop(self, symbol: str, side: Side, stop_price: float) -> bool:
        trigger = _positive("PAPER_STOP_PRICE", stop_price)
        with self._lock:
            state = self._require_state()
            position = state["position"]
            raw = state["protective_stop"]
            if position is not None:
                if raw is None:
                    return False
                stop = self._decode_stop(raw)
                return (
                    stop.symbol == symbol
                    and stop.side == side
                    and math.isclose(float(stop.trigger_price), trigger, rel_tol=1e-12, abs_tol=1e-12)
                )

        # Before entry there is no active stop to inspect.  In this phase the
        # same ExchangePort method is also the pre-entry stop-feasibility gate:
        # prove that the requested trigger is on the protective side of current
        # Execution market truth.
        quote = self.market_data.quote(symbol)
        if quote.symbol != symbol:
            raise PaperExchangeError("PAPER_QUOTE_SYMBOL_MISMATCH")
        if side == "LONG":
            return trigger < float(quote.bid)
        if side == "SHORT":
            return trigger > float(quote.ask)
        raise ValueError("SIDE_INVALID")

    def set_leverage(self, symbol: str, leverage: int) -> None:
        if not isinstance(symbol, str) or not symbol or symbol != symbol.strip():
            raise ValueError("PAPER_SYMBOL_INVALID")
        if isinstance(leverage, bool) or not isinstance(leverage, int) or leverage <= 0:
            raise ValueError("PAPER_LEVERAGE_INVALID")
        with self._lock:
            state = self._require_state()
            updated = dict(state)
            leverages = dict(state["leverage_by_symbol"])
            leverages[symbol] = leverage
            updated["leverage_by_symbol"] = leverages
            self._commit(updated)

    # ------------------------------------------------------------------
    # Entry / protection lifecycle
    # ------------------------------------------------------------------

    def open_market(self, plan: EntryPlan, *, client_order_id: str) -> Fill:
        client_order_id = _text("PAPER_CLIENT_ORDER_ID", client_order_id, max_length=128)
        signature = self._plan_signature(plan)
        with self._lock:
            state = self._require_state()
            existing = state["fills_by_client_id"].get(client_order_id)
            if existing is not None:
                if existing["plan_signature"] != signature:
                    raise PaperExchangeError("PAPER_CLIENT_ORDER_ID_PLAN_MISMATCH")
                return self._decode_fill(existing["fill"])
            if state["position"] is not None:
                raise PaperExchangeError("PAPER_POSITION_ALREADY_OPEN")
            configured_leverage = state["leverage_by_symbol"].get(plan.symbol)
            if configured_leverage != plan.leverage:
                raise PaperExchangeError("PAPER_LEVERAGE_NOT_SET")

        market_quote = self.market_data.quote(plan.symbol)
        if market_quote.symbol != plan.symbol:
            raise PaperExchangeError("PAPER_QUOTE_SYMBOL_MISMATCH")
        execution_price = float(market_quote.ask if plan.side == "LONG" else market_quote.bid)
        adverse = float(self.config.entry_slippage_pct) / 100.0
        fill_price = execution_price * (1.0 + adverse if plan.side == "LONG" else 1.0 - adverse)
        if fill_price <= 0:
            raise PaperExchangeError("PAPER_ENTRY_FILL_PRICE_INVALID")
        fill = Fill(
            price=fill_price,
            quantity=float(plan.quantity),
            order_id=self._stable_id("PAPER-E", client_order_id),
            client_order_id=client_order_id,
            timestamp_ms=int(market_quote.timestamp_ms),
        )
        entry_fee = fill.price * fill.quantity * float(self.config.taker_fee_rate)

        with self._lock:
            state = self._require_state()
            existing = state["fills_by_client_id"].get(client_order_id)
            if existing is not None:
                if existing["plan_signature"] != signature:
                    raise PaperExchangeError("PAPER_CLIENT_ORDER_ID_PLAN_MISMATCH")
                return self._decode_fill(existing["fill"])
            if state["position"] is not None:
                raise PaperExchangeError("PAPER_POSITION_ALREADY_OPEN")
            updated = dict(state)
            fills = dict(state["fills_by_client_id"])
            fills[client_order_id] = {
                "plan_signature": signature,
                "fill": self._encode_fill(fill),
            }
            updated["fills_by_client_id"] = fills
            updated["position"] = {
                "symbol": plan.symbol,
                "side": plan.side,
                "quantity": fill.quantity,
                "entry_price": fill.price,
                "entry_order_id": fill.order_id,
                "entry_client_order_id": fill.client_order_id,
                "entry_timestamp_ms": fill.timestamp_ms,
                "entry_fee_usd": entry_fee,
                "leverage": int(plan.leverage),
            }
            updated["protective_stop"] = None
            self._commit(updated)
            self._latest_quotes[market_quote.symbol] = market_quote
        return fill

    def recover_inflight_entry(self, plan: EntryPlan, *, client_order_id: str) -> Fill | None:
        client_order_id = _text("PAPER_CLIENT_ORDER_ID", client_order_id, max_length=128)
        signature = self._plan_signature(plan)
        with self._lock:
            existing = self._require_state()["fills_by_client_id"].get(client_order_id)
            if existing is None:
                return None
            if existing["plan_signature"] != signature:
                raise PaperExchangeError("PAPER_CLIENT_ORDER_ID_PLAN_MISMATCH")
            return self._decode_fill(existing["fill"])

    def ensure_protective_stop(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        stop_price: float,
    ) -> ProtectiveStopRef:
        with self._lock:
            state = self._require_state()
            position = self._require_position_identity(state, symbol, side, quantity)
            existing = state["protective_stop"]
            if existing is not None:
                stop = self._decode_stop(existing)
                if math.isclose(stop.trigger_price, float(stop_price), rel_tol=1e-12, abs_tol=1e-12):
                    return stop
                raise PaperExchangeError("PAPER_DIFFERENT_PROTECTIVE_STOP_ALREADY_ACTIVE")
            trigger = _positive("PAPER_STOP_PRICE", stop_price)
            self._require_stop_direction(position, trigger)
            sequence = int(state["stop_sequence"]) + 1
            stop = ProtectiveStopRef(
                symbol=symbol,
                side=side,
                quantity=float(quantity),
                trigger_price=trigger,
                stop_id=self._stop_id(position["entry_client_order_id"], sequence, trigger),
                client_stop_id=self._stop_client_id(position["entry_client_order_id"], sequence),
            )
            updated = dict(state)
            updated["stop_sequence"] = sequence
            updated["protective_stop"] = self._encode_stop(stop)
            self._commit(updated)
            return stop

    def replace_protective_stop(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        stop_price: float,
    ) -> ProtectiveStopRef:
        with self._lock:
            state = self._require_state()
            position = self._require_position_identity(state, symbol, side, quantity)
            raw_old = state["protective_stop"]
            if raw_old is None:
                raise PaperExchangeError("PAPER_PROTECTIVE_STOP_MISSING")
            old = self._decode_stop(raw_old)
            trigger = _positive("PAPER_STOP_PRICE", stop_price)
            if side == "LONG" and trigger + 1e-12 < old.trigger_price:
                raise PaperExchangeError("PAPER_PROTECTIVE_STOP_LOOSEN_FORBIDDEN")
            if side == "SHORT" and trigger - 1e-12 > old.trigger_price:
                raise PaperExchangeError("PAPER_PROTECTIVE_STOP_LOOSEN_FORBIDDEN")
            sequence = int(state["stop_sequence"]) + 1
            new_stop = ProtectiveStopRef(
                symbol=symbol,
                side=side,
                quantity=float(quantity),
                trigger_price=trigger,
                stop_id=self._stop_id(position["entry_client_order_id"], sequence, trigger),
                client_stop_id=self._stop_client_id(position["entry_client_order_id"], sequence),
            )
            # Atomic account replacement means there is never a persisted state
            # where the old known protection has been removed but the new stop
            # is not yet present.
            updated = dict(state)
            updated["stop_sequence"] = sequence
            updated["protective_stop"] = self._encode_stop(new_stop)
            self._commit(updated)
            return new_stop

    # ------------------------------------------------------------------
    # Close / recovery lifecycle
    # ------------------------------------------------------------------

    def close_position(self, symbol: str, side: Side, *, reason: str) -> CloseFill:
        reason = _text("PAPER_CLOSE_REASON", reason, max_length=160)
        with self._lock:
            state = self._require_state()
            position = state["position"]
            if position is None:
                raise PaperExchangeError("PAPER_POSITION_NOT_FOUND")
            self._require_position_identity(state, symbol, side, float(position["quantity"]))

        quote = self.market_data.quote(symbol)
        if quote.symbol != symbol:
            raise PaperExchangeError("PAPER_QUOTE_SYMBOL_MISMATCH")
        return self._close_from_observed_quote(quote=quote, reason=reason)

    def recover_closed_position(self, local_position: OpenPosition) -> CloseFill:
        with self._lock:
            raw = self._require_state()["closed_by_client_id"].get(local_position.entry_client_order_id)
            if raw is None:
                raise PaperExchangeError("PAPER_CLOSE_EVIDENCE_NOT_FOUND")
            close = self._decode_close(raw["close"])
            if raw["symbol"] != local_position.symbol or raw["side"] != local_position.side:
                raise PaperExchangeError("PAPER_CLOSE_EVIDENCE_IDENTITY_MISMATCH")
            return close

    def recover_closed_inflight_entry(self, inflight: EntryInflight) -> CloseFill:
        if inflight.fill is None:
            raise PaperExchangeError("PAPER_INFLIGHT_CLOSE_REQUIRES_FILL")
        with self._lock:
            raw = self._require_state()["closed_by_client_id"].get(inflight.client_order_id)
            if raw is None:
                raise PaperExchangeError("PAPER_CLOSE_EVIDENCE_NOT_FOUND")
            if raw["symbol"] != inflight.plan.symbol or raw["side"] != inflight.plan.side:
                raise PaperExchangeError("PAPER_CLOSE_EVIDENCE_IDENTITY_MISMATCH")
            return self._decode_close(raw["close"])

    def cleanup_orphan_protective_stops(self) -> int:
        """Atomically remove the one possible PAPER orphan stop."""
        with self._lock:
            state = self._require_state()
            if state["position"] is not None or state["protective_stop"] is None:
                return 0
            # Decode first so corrupt stop evidence does not get silently erased.
            self._decode_stop(state["protective_stop"])
            updated = dict(state)
            updated["protective_stop"] = None
            self._commit(updated)
            return 1

    def on_market_tick(
        self,
        *,
        symbol: str,
        bid: float,
        ask: float,
        timestamp_ms: int,
    ) -> CloseFill | None:
        """Apply one Execution-owned market tick and simulate stop settlement."""
        quote = Quote(symbol=symbol, bid=bid, ask=ask, timestamp_ms=timestamp_ms)
        with self._lock:
            previous = self._latest_quotes.get(symbol)
            if previous is not None and quote.timestamp_ms < previous.timestamp_ms:
                return None
            self._latest_quotes[symbol] = quote
            state = self._require_state()
            position = state["position"]
            stop_raw = state["protective_stop"]
            if position is None or stop_raw is None or position["symbol"] != symbol:
                return None
            stop = self._decode_stop(stop_raw)
            hit = (stop.side == "LONG" and quote.bid <= stop.trigger_price) or (
                stop.side == "SHORT" and quote.ask >= stop.trigger_price
            )
            if not hit:
                return None
        return self._close_from_observed_quote(quote=quote, reason="STOP_LOSS")

    # ------------------------------------------------------------------
    # Internal durable account handling
    # ------------------------------------------------------------------

    def _close_from_observed_quote(self, *, quote: Quote, reason: str) -> CloseFill:
        with self._lock:
            state = self._require_state()
            position = state["position"]
            if position is None:
                raise PaperExchangeError("PAPER_POSITION_NOT_FOUND")
            if position["symbol"] != quote.symbol:
                raise PaperExchangeError("PAPER_POSITION_SYMBOL_MISMATCH")

            side: Side = position["side"]
            executable = float(quote.bid if side == "LONG" else quote.ask)
            adverse = float(self.config.exit_slippage_pct) / 100.0
            exit_price = executable * (1.0 - adverse if side == "LONG" else 1.0 + adverse)
            _positive("PAPER_EXIT_PRICE", exit_price)
            quantity = float(position["quantity"])
            entry_price = float(position["entry_price"])
            gross = (
                (exit_price - entry_price) * quantity
                if side == "LONG"
                else (entry_price - exit_price) * quantity
            )
            exit_fee = exit_price * quantity * float(self.config.taker_fee_rate)
            realized = gross - float(position["entry_fee_usd"]) - exit_fee
            client_id = position["entry_client_order_id"]
            close = CloseFill(
                price=exit_price,
                timestamp_ms=int(quote.timestamp_ms),
                reason=reason,
                realized_pnl_usd=realized,
                order_ids=(self._stable_id("PAPER-C", f"{client_id}:{quote.timestamp_ms}:{reason}"),),
                source="PAPER_ACCOUNT",
                theoretical_pnl_usd=gross,
                pnl_variance_usd=realized - gross,
            )
            updated = dict(state)
            updated["balance_usd"] = float(state["balance_usd"]) + realized
            closes = dict(state["closed_by_client_id"])
            closes[client_id] = {
                "symbol": position["symbol"],
                "side": side,
                "close": self._encode_close(close),
            }
            updated["closed_by_client_id"] = closes
            updated["position"] = None
            updated["protective_stop"] = None
            self._commit(updated)
            return close

    def _load_or_create(self) -> None:
        if not self.account_path.exists():
            self._commit(self._new_state())
            return
        try:
            raw = json.loads(self.account_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise PaperExchangeError("PAPER_ACCOUNT_CORRUPT") from exc
        try:
            self._validate_state(raw)
        except PaperExchangeError:
            raise
        except Exception as exc:
            raise PaperExchangeError("PAPER_ACCOUNT_SCHEMA_INVALID") from exc
        if not math.isclose(
            float(raw["starting_balance_usd"]),
            float(self.config.starting_balance_usd),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise PaperExchangeError("PAPER_STARTING_BALANCE_CONFIG_MISMATCH")
        self._state = raw

    def _new_state(self) -> dict:
        return {
            "version": PAPER_ACCOUNT_VERSION,
            "profile": self.profile.name,
            "market_environment": self.profile.market_environment,
            "starting_balance_usd": float(self.config.starting_balance_usd),
            "balance_usd": float(self.config.starting_balance_usd),
            "leverage_by_symbol": {},
            "position": None,
            "protective_stop": None,
            "fills_by_client_id": {},
            "closed_by_client_id": {},
            "stop_sequence": 0,
        }

    def _commit(self, state: dict) -> None:
        self._validate_state(state)
        atomic_write_json(self.account_path, state, mode=0o600)
        self._state = state

    def _validate_state(self, raw: object) -> None:
        if not isinstance(raw, dict):
            raise PaperExchangeError("PAPER_ACCOUNT_SCHEMA_INVALID")
        required = {
            "version",
            "profile",
            "market_environment",
            "starting_balance_usd",
            "balance_usd",
            "leverage_by_symbol",
            "position",
            "protective_stop",
            "fills_by_client_id",
            "closed_by_client_id",
            "stop_sequence",
        }
        if set(raw) != required:
            raise PaperExchangeError("PAPER_ACCOUNT_SCHEMA_INVALID")
        if raw["version"] != PAPER_ACCOUNT_VERSION:
            raise PaperExchangeError("PAPER_ACCOUNT_VERSION_UNSUPPORTED")
        if raw["profile"] != self.profile.name or raw["market_environment"] != self.profile.market_environment:
            raise PaperExchangeError("PAPER_ACCOUNT_PROFILE_MISMATCH")
        _positive("PAPER_STATE_STARTING_BALANCE", raw["starting_balance_usd"])
        _finite("PAPER_STATE_BALANCE", raw["balance_usd"])
        if not isinstance(raw["leverage_by_symbol"], dict):
            raise PaperExchangeError("PAPER_ACCOUNT_LEVERAGE_SCHEMA_INVALID")
        for symbol, leverage in raw["leverage_by_symbol"].items():
            _text("PAPER_STATE_SYMBOL", symbol, max_length=40)
            if isinstance(leverage, bool) or not isinstance(leverage, int) or leverage <= 0:
                raise PaperExchangeError("PAPER_ACCOUNT_LEVERAGE_SCHEMA_INVALID")
        if isinstance(raw["stop_sequence"], bool) or not isinstance(raw["stop_sequence"], int) or raw["stop_sequence"] < 0:
            raise PaperExchangeError("PAPER_ACCOUNT_STOP_SEQUENCE_INVALID")
        position = raw["position"]
        stop_raw = raw["protective_stop"]
        if position is not None:
            self._validate_position(position)
            if stop_raw is not None:
                stop = self._decode_stop(stop_raw)
                if stop.symbol != position["symbol"] or stop.side != position["side"]:
                    raise PaperExchangeError("PAPER_ACCOUNT_STOP_POSITION_MISMATCH")
                if not math.isclose(stop.quantity, float(position["quantity"]), rel_tol=1e-12, abs_tol=1e-12):
                    raise PaperExchangeError("PAPER_ACCOUNT_STOP_POSITION_MISMATCH")
        elif stop_raw is not None:
            # A syntactically valid orphan is recoverable state, not clean flatness.
            # Reconciliation must explicitly remove it before entries can resume.
            self._decode_stop(stop_raw)
        for field in ("fills_by_client_id", "closed_by_client_id"):
            if not isinstance(raw[field], dict):
                raise PaperExchangeError("PAPER_ACCOUNT_HISTORY_SCHEMA_INVALID")
        for client_id, record in raw["fills_by_client_id"].items():
            _text("PAPER_HISTORY_CLIENT_ID", client_id, max_length=128)
            if not isinstance(record, dict) or set(record) != {"plan_signature", "fill"}:
                raise PaperExchangeError("PAPER_ACCOUNT_FILL_HISTORY_INVALID")
            _text("PAPER_PLAN_SIGNATURE", record["plan_signature"], max_length=64)
            fill = self._decode_fill(record["fill"])
            if fill.client_order_id != client_id:
                raise PaperExchangeError("PAPER_ACCOUNT_FILL_HISTORY_INVALID")
        for client_id, record in raw["closed_by_client_id"].items():
            _text("PAPER_HISTORY_CLIENT_ID", client_id, max_length=128)
            if not isinstance(record, dict) or set(record) != {"symbol", "side", "close"}:
                raise PaperExchangeError("PAPER_ACCOUNT_CLOSE_HISTORY_INVALID")
            _text("PAPER_CLOSE_SYMBOL", record["symbol"], max_length=40)
            if record["side"] not in {"LONG", "SHORT"}:
                raise PaperExchangeError("PAPER_ACCOUNT_CLOSE_HISTORY_INVALID")
            self._decode_close(record["close"])

    @staticmethod
    def _validate_position(position: object) -> None:
        if not isinstance(position, dict):
            raise PaperExchangeError("PAPER_ACCOUNT_POSITION_INVALID")
        required = {
            "symbol",
            "side",
            "quantity",
            "entry_price",
            "entry_order_id",
            "entry_client_order_id",
            "entry_timestamp_ms",
            "entry_fee_usd",
            "leverage",
        }
        if set(position) != required:
            raise PaperExchangeError("PAPER_ACCOUNT_POSITION_INVALID")
        _text("PAPER_POSITION_SYMBOL", position["symbol"], max_length=40)
        if position["side"] not in {"LONG", "SHORT"}:
            raise PaperExchangeError("PAPER_ACCOUNT_POSITION_INVALID")
        _positive("PAPER_POSITION_QUANTITY", position["quantity"])
        _positive("PAPER_POSITION_ENTRY_PRICE", position["entry_price"])
        _text("PAPER_POSITION_ORDER_ID", position["entry_order_id"])
        _text("PAPER_POSITION_CLIENT_ID", position["entry_client_order_id"], max_length=128)
        if isinstance(position["entry_timestamp_ms"], bool) or not isinstance(position["entry_timestamp_ms"], int) or position["entry_timestamp_ms"] <= 0:
            raise PaperExchangeError("PAPER_ACCOUNT_POSITION_INVALID")
        _nonnegative("PAPER_POSITION_ENTRY_FEE", position["entry_fee_usd"])
        if isinstance(position["leverage"], bool) or not isinstance(position["leverage"], int) or position["leverage"] <= 0:
            raise PaperExchangeError("PAPER_ACCOUNT_POSITION_INVALID")

    def _require_position_identity(self, state: dict, symbol: str, side: Side, quantity: float) -> dict:
        position = state["position"]
        if position is None:
            raise PaperExchangeError("PAPER_POSITION_NOT_FOUND")
        if position["symbol"] != symbol:
            raise PaperExchangeError("PAPER_POSITION_SYMBOL_MISMATCH")
        if position["side"] != side:
            raise PaperExchangeError("PAPER_POSITION_SIDE_MISMATCH")
        if not math.isclose(float(position["quantity"]), float(quantity), rel_tol=1e-12, abs_tol=1e-12):
            raise PaperExchangeError("PAPER_POSITION_QUANTITY_MISMATCH")
        return position

    @staticmethod
    def _require_stop_direction(position: dict, trigger: float) -> None:
        entry = float(position["entry_price"])
        if position["side"] == "LONG" and trigger >= entry:
            raise PaperExchangeError("PAPER_INITIAL_LONG_STOP_INVALID")
        if position["side"] == "SHORT" and trigger <= entry:
            raise PaperExchangeError("PAPER_INITIAL_SHORT_STOP_INVALID")

    def _require_ready(self) -> None:
        if not self._connected or self._state is None:
            raise PaperExchangeError("PAPER_EXCHANGE_NOT_CONNECTED")

    def _require_state(self) -> dict:
        if self._state is None:
            raise PaperExchangeError("PAPER_ACCOUNT_NOT_LOADED")
        return self._state

    @staticmethod
    def _stable_id(prefix: str, seed: str) -> str:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}-{digest}"

    @classmethod
    def _stop_id(cls, client_id: str, sequence: int, trigger: float) -> str:
        return cls._stable_id("PAPER-S", f"{client_id}:{sequence}:{trigger:.16g}")

    @classmethod
    def _stop_client_id(cls, client_id: str, sequence: int) -> str:
        return cls._stable_id("PAPER-CS", f"{client_id}:{sequence}")

    @staticmethod
    def _plan_signature(plan: EntryPlan) -> str:
        payload = "|".join(
            (
                plan.symbol,
                plan.side,
                f"{float(plan.quantity):.16g}",
                f"{float(plan.expected_entry_price):.16g}",
                f"{float(plan.initial_stop_price):.16g}",
                f"{float(plan.initial_risk_usd):.16g}",
                f"{float(plan.notional_usd):.16g}",
                str(plan.leverage),
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _encode_fill(fill: Fill) -> dict:
        return {
            "price": fill.price,
            "quantity": fill.quantity,
            "order_id": fill.order_id,
            "client_order_id": fill.client_order_id,
            "timestamp_ms": fill.timestamp_ms,
        }

    @staticmethod
    def _decode_fill(raw: object) -> Fill:
        if not isinstance(raw, dict):
            raise PaperExchangeError("PAPER_FILL_SCHEMA_INVALID")
        try:
            return Fill(**raw)
        except (TypeError, ValueError) as exc:
            raise PaperExchangeError("PAPER_FILL_SCHEMA_INVALID") from exc

    @staticmethod
    def _encode_stop(stop: ProtectiveStopRef) -> dict:
        return {
            "symbol": stop.symbol,
            "side": stop.side,
            "quantity": stop.quantity,
            "trigger_price": stop.trigger_price,
            "stop_id": stop.stop_id,
            "client_stop_id": stop.client_stop_id,
        }

    @staticmethod
    def _decode_stop(raw: object) -> ProtectiveStopRef:
        if not isinstance(raw, dict):
            raise PaperExchangeError("PAPER_STOP_SCHEMA_INVALID")
        try:
            return ProtectiveStopRef(**raw)
        except (TypeError, ValueError) as exc:
            raise PaperExchangeError("PAPER_STOP_SCHEMA_INVALID") from exc

    @staticmethod
    def _encode_close(close: CloseFill) -> dict:
        return {
            "price": close.price,
            "timestamp_ms": close.timestamp_ms,
            "reason": close.reason,
            "realized_pnl_usd": close.realized_pnl_usd,
            "order_ids": list(close.order_ids),
            "source": close.source,
            "theoretical_pnl_usd": close.theoretical_pnl_usd,
            "pnl_variance_usd": close.pnl_variance_usd,
        }

    @staticmethod
    def _decode_close(raw: object) -> CloseFill:
        if not isinstance(raw, dict):
            raise PaperExchangeError("PAPER_CLOSE_SCHEMA_INVALID")
        value = dict(raw)
        order_ids = value.get("order_ids")
        if not isinstance(order_ids, list):
            raise PaperExchangeError("PAPER_CLOSE_SCHEMA_INVALID")
        value["order_ids"] = tuple(order_ids)
        try:
            return CloseFill(**value)
        except (TypeError, ValueError) as exc:
            raise PaperExchangeError("PAPER_CLOSE_SCHEMA_INVALID") from exc


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}_INVALID")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name}_INVALID")
    return number


def _positive(name: str, value: object) -> float:
    number = _finite(name, value)
    if number <= 0:
        raise ValueError(f"{name}_INVALID")
    return number


def _nonnegative(name: str, value: object) -> float:
    number = _finite(name, value)
    if number < 0:
        raise ValueError(f"{name}_INVALID")
    return number


def _text(name: str, value: object, *, max_length: int = 160) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > max_length:
        raise ValueError(f"{name}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name}_INVALID")
    return value
