"""Local paper-execution adapter.

Market-data operations are delegated to a supplied read-only market client.
All account-changing operations are simulated through :class:`PaperAccount`.
This module contains no Binance order-submission code.
"""

import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional

from config import (
    LEVERAGE,
    PAPER_ENTRY_SLIPPAGE_PCT,
    PAPER_EXIT_SLIPPAGE_PCT,
    PAPER_HEARTBEAT_INTERVAL_SECONDS,
    PAPER_PREFLIGHT_CANDLE_LIMIT,
    PAPER_PREFLIGHT_SYMBOL,
    PAPER_TAKER_FEE_RATE,
)
from execution.exceptions import EntryValidationError
from execution.paper_account import PaperAccount


@dataclass(frozen=True)
class PaperEntryAck:
    filled_qty: float
    avg_price: float
    requested_qty: float
    fully_filled: bool
    order_id: str
    client_order_id: str


class PaperExchange:
    """Exchange-compatible local simulator with delegated market data."""

    def __init__(
        self,
        *,
        market_client: Any,
        account: PaperAccount,
        system_log: Any,
    ) -> None:
        self.market_client = market_client
        self.account = account
        self.system_log = system_log
        self._pending_entry: Optional[dict] = None
        self._last_trade = None
        self._leverage_by_symbol: dict[str, int] = {}
        self._active_sl_order_id: Optional[int] = None
        self._last_heartbeat_monotonic = 0.0
        self._latest_price_by_symbol: dict[str, float] = {}

    # ---------------- Market-data delegation ----------------

    def connect(self):
        self.account.load_or_create()
        self._restore_runtime_metadata()
        self._log_startup_state(self.account.snapshot())
        self.market_client.connect()
        report = self.market_client.preflight(
            symbol=PAPER_PREFLIGHT_SYMBOL,
            candle_limit=PAPER_PREFLIGHT_CANDLE_LIMIT,
        )
        self.system_log.info(
            "PAPER_RUNTIME_PREFLIGHT_OK | "
            f"source={self.account.snapshot()['source']} | "
            f"symbol={report['symbol']} | auth={report['auth']}"
        )
        return report

    def _restore_runtime_metadata(self) -> None:
        """Rebuild non-persistent adapter metadata from durable paper state."""
        position = self.account.get_open_position()
        self._pending_entry = None
        self._last_trade = None
        if position is None:
            self._active_sl_order_id = None
            return
        if not position.trade_id or not position.symbol or position.stop_loss <= 0:
            raise RuntimeError("PAPER_RECOVERY_STATE_INCOMPLETE")
        self._active_sl_order_id = self._stable_paper_order_id(
            f"paper-sl-recovered:{position.trade_id}"
        )

    def _log_startup_state(self, state: dict) -> None:
        position = self.account.get_open_position()
        if position is None:
            self.system_log.info(
                "PAPER_ACCOUNT_READY | "
                f"source={state['source']} | "
                f"balance_usd={state['balance_usd']:.8f} | "
                f"realized_pnl_usd={state['realized_pnl_usd']:.8f} | "
                f"completed_trades={state['completed_trade_count']} | "
                "position=FLAT"
            )
            return
        self.system_log.warning(
            "PAPER_POSITION_RECOVERED | "
            f"trade_id={position.trade_id} | "
            f"symbol={position.symbol} | side={position.side} | "
            f"qty={position.qty} | entry={position.entry_price} | "
            f"stop={position.stop_loss} | opened_at_ms={position.opened_at_ms} | "
            f"sl_ref={self._active_sl_order_id}"
        )

    def disconnect(self):
        return self.market_client.disconnect()

    def price_stream(self):
        """Yield real market ticks while advancing local paper execution."""
        for tick in self.market_client.price_stream():
            self.on_market_tick(
                symbol=tick.symbol,
                price=tick.price,
                timestamp=tick.timestamp,
            )
            self._maybe_log_heartbeat(tick=tick)
            yield tick

    def on_market_tick(self, *, symbol: str, price: float, timestamp: int):
        """Apply one real market tick to the local paper position.

        This method never submits an exchange order. It updates paper MAE/MFE
        price extremes and closes the local position when its simulated stop
        is crossed.
        """
        symbol = str(symbol).strip().upper()
        self._positive(price, "market_price")
        self._latest_price_by_symbol[symbol] = float(price)

        position = self.account.get_open_position()
        if position is None or position.symbol != symbol:
            return None

        self.account.update_position_market_extremes(float(price))
        position = self.account.get_open_position()
        if position is None:
            return None

        stop_hit = (
            position.side == "LONG" and float(price) <= position.stop_loss
        ) or (
            position.side == "SHORT" and float(price) >= position.stop_loss
        )

        if not stop_hit:
            return None

        trade = self._close_at_observed_price(
            observed_price=float(price),
            closed_at_ms=int(timestamp),
            exit_reason="STOP_LOSS",
        )
        self.system_log.info(
            "PAPER_STOP_FILLED | "
            f"symbol={symbol} | "
            f"side={position.side} | "
            f"stop={position.stop_loss} | "
            f"observed_price={price}"
        )
        return trade


    def _maybe_log_heartbeat(self, *, tick: Any) -> None:
        now = time.monotonic()
        if (
            self._last_heartbeat_monotonic > 0
            and now - self._last_heartbeat_monotonic
            < PAPER_HEARTBEAT_INTERVAL_SECONDS
        ):
            return
        self._last_heartbeat_monotonic = now
        state = self.account.snapshot()
        position = self.account.get_open_position()
        if position is None:
            self.system_log.info(
                "PAPER_HEARTBEAT | "
                f"source={state['source']} | position=FLAT | "
                f"balance_usd={state['balance_usd']:.8f} | "
                f"realized_pnl_usd={state['realized_pnl_usd']:.8f} | "
                f"fees_paid_usd={state['fees_paid_usd']:.8f} | "
                f"completed_trades={state['completed_trade_count']}"
            )
            return
        observed_price = self._latest_price_by_symbol.get(position.symbol)
        if observed_price is None and str(tick.symbol).upper() == position.symbol:
            observed_price = float(tick.price)
        unrealized = None
        if observed_price is not None:
            direction = 1.0 if position.side == "LONG" else -1.0
            unrealized = (observed_price - position.entry_price) * position.qty * direction
        self.system_log.info(
            "PAPER_HEARTBEAT | "
            f"source={state['source']} | position=OPEN | "
            f"trade_id={position.trade_id} | symbol={position.symbol} | "
            f"side={position.side} | qty={position.qty} | "
            f"entry={position.entry_price} | stop={position.stop_loss} | "
            f"observed_price={observed_price} | "
            f"unrealized_pnl_usd={unrealized} | "
            f"balance_usd={state['balance_usd']:.8f}"
        )

    def get_historical_candles(self, *, symbol: str, interval: str, limit: int):
        return self.market_client.get_historical_candles(
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

    def get_current_spread_pct(self, *, symbol: str) -> float:
        return float(self.market_client.get_current_spread_pct(symbol=symbol))

    def get_last_price(self, symbol: str) -> float:
        return float(self.market_client.get_last_price(symbol))

    def quantize_price(self, symbol: str, price: float) -> float:
        return float(self.market_client.quantize_price(symbol, price))

    def is_user_stream_healthy(self) -> bool:
        return True

    def wait_for_user_stream_ready(self, timeout: float | None = None) -> bool:
        return True

    # ---------------- Local account truth ----------------

    def set_leverage(self, *, symbol: str, leverage: int):
        symbol = str(symbol).strip().upper()
        if not symbol or not isinstance(leverage, int) or leverage <= 0:
            raise ValueError("PAPER_LEVERAGE_INVALID")
        self._leverage_by_symbol[symbol] = leverage
        return {"symbol": symbol, "leverage": leverage}

    def enforce_leverage_for_universe(self, symbols):
        for symbol in symbols:
            self.set_leverage(symbol=symbol, leverage=LEVERAGE)

    def get_available_balance(self, *, asset: str = "USDT") -> float:
        if str(asset).upper() != "USDT":
            raise ValueError("PAPER_ASSET_UNSUPPORTED")
        return self.account.get_balance_usd()

    def get_realized_pnl(self, utc_day) -> float:
        if utc_day != datetime.now(timezone.utc).date():
            return 0.0
        return self.account.get_realized_pnl_usd()

    def get_position(self):
        position = self.account.get_open_position()
        if position is None:
            return None
        return SimpleNamespace(
            symbol=position.symbol,
            side=position.side,
            qty=position.qty,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
        )

    @staticmethod
    def _new_paper_order_id() -> int:
        """Return a positive integer compatible with engine state validation."""
        return (uuid.uuid4().int % 9_000_000_000_000_000_000) + 1

    @staticmethod
    def _stable_paper_order_id(seed: str) -> int:
        """Return a stable positive integer for recovered paper metadata."""
        value = uuid.uuid5(uuid.NAMESPACE_URL, str(seed)).int
        return (value % 9_000_000_000_000_000_000) + 1

    # ---------------- Simulated order lifecycle ----------------

    def place_entry(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        client_order_id: str,
    ) -> PaperEntryAck:
        if self.account.get_open_position() is not None or self._pending_entry:
            raise EntryValidationError("PAPER_ENTRY_POSITION_ALREADY_EXISTS")
        symbol = str(symbol).strip().upper()
        side = str(side).strip().upper()
        if side not in {"LONG", "SHORT"}:
            raise EntryValidationError("PAPER_ENTRY_SIDE_INVALID")
        self._positive(quantity, "quantity")
        self._positive(price, "price")
        client_order_id = str(client_order_id).strip()
        if not symbol or not client_order_id:
            raise EntryValidationError("PAPER_ENTRY_IDENTIFIER_INVALID")

        adverse = PAPER_ENTRY_SLIPPAGE_PCT / 100.0
        fill_price = float(price) * (1.0 + adverse if side == "LONG" else 1.0 - adverse)
        order_id = self._new_paper_order_id()
        ack = PaperEntryAck(
            filled_qty=float(quantity),
            avg_price=fill_price,
            requested_qty=float(quantity),
            fully_filled=True,
            order_id=order_id,
            client_order_id=client_order_id,
        )
        self._pending_entry = {
            "ack": ack,
            "symbol": symbol,
            "side": side,
            "created_at_ms": int(time.time() * 1000),
        }
        return ack

    def query_order_by_client_id(self, *, symbol: str, client_order_id: str):
        pending = self._pending_entry
        if not pending:
            return None
        ack = pending["ack"]
        if pending["symbol"] == str(symbol).upper() and ack.client_order_id == client_order_id:
            return ack
        return None

    def resolve_ambiguous_entry(
        self,
        *,
        symbol: str,
        client_order_id: str,
        requested_qty: float,
        fallback_price: float,
        timeout_seconds: float = 10.0,
    ):
        ack = self.query_order_by_client_id(
            symbol=symbol,
            client_order_id=client_order_id,
        )
        if ack is not None:
            return {"outcome": "FILLED", "ack": ack}
        position = self.get_position()
        if position is not None:
            return {"outcome": "POSITION_EXISTS", "position": position}
        return {"outcome": "NOT_FOUND"}

    def place_initial_sl(self, *, symbol: str, side: str, qty: float, stop_price: float):
        pending = self._pending_entry
        if pending is None:
            raise RuntimeError("PAPER_PENDING_ENTRY_NOT_FOUND")
        if pending["symbol"] != str(symbol).upper() or pending["side"] != str(side).upper():
            raise RuntimeError("PAPER_PENDING_ENTRY_MISMATCH")
        ack = pending["ack"]
        if abs(float(qty) - ack.filled_qty) > 1e-12:
            raise RuntimeError("PAPER_PENDING_ENTRY_QTY_MISMATCH")
        stop = self.quantize_price(symbol, stop_price)
        risk_usd = abs(ack.avg_price - stop) * ack.filled_qty
        self._positive(risk_usd, "initial_risk_usd")
        entry_fee = ack.avg_price * ack.filled_qty * PAPER_TAKER_FEE_RATE
        self.account.open_position(
            symbol=symbol,
            side=side,
            qty=ack.filled_qty,
            entry_price=ack.avg_price,
            stop_loss=stop,
            opened_at_ms=pending["created_at_ms"],
            initial_risk_usd=risk_usd,
            entry_fee_usd=entry_fee,
            trade_id=ack.order_id,
        )
        self._pending_entry = None
        self._active_sl_order_id = self._new_paper_order_id()
        return {"algo_id": self._active_sl_order_id}

    def update_sl(self, *, symbol: str, side: str, qty: float, new_stop_price: float):
        position = self.account.get_open_position()
        if position is None or position.symbol != str(symbol).upper():
            raise RuntimeError("PAPER_POSITION_NOT_FOUND")
        stop = self.quantize_price(symbol, new_stop_price)
        self.account.update_stop_loss(stop)
        self._active_sl_order_id = self._new_paper_order_id()
        return {"algo_id": self._active_sl_order_id}

    def get_active_sl_order_id(self):
        return self._active_sl_order_id

    def recover_active_stop_loss(self, symbol: str):
        position = self.account.get_open_position()
        if position is None or position.symbol != str(symbol).upper():
            self._active_sl_order_id = None
            return None
        if self._active_sl_order_id is None:
            self._active_sl_order_id = self._new_paper_order_id()
        return {"algo_id": self._active_sl_order_id, "stop_price": position.stop_loss}

    def cancel_pending_entries(self):
        had_pending = self._pending_entry is not None
        self._pending_entry = None
        return had_pending

    def emergency_exit(self):
        self._pending_entry = None
        position = self.account.get_open_position()
        if position is None:
            return None
        observed = self.get_last_price(position.symbol)
        return self._close_at_observed_price(
            observed_price=observed,
            closed_at_ms=int(time.time() * 1000),
            exit_reason="EMERGENCY_EXIT",
        )

    def _close_at_observed_price(
        self,
        *,
        observed_price: float,
        closed_at_ms: int,
        exit_reason: str,
    ):
        position = self.account.get_open_position()
        if position is None:
            return None
        self._positive(observed_price, "observed_exit_price")
        adverse = PAPER_EXIT_SLIPPAGE_PCT / 100.0
        exit_price = float(observed_price) * (
            1.0 - adverse if position.side == "LONG" else 1.0 + adverse
        )
        exit_fee = exit_price * position.qty * PAPER_TAKER_FEE_RATE
        trade = self.account.close_position(
            exit_price=exit_price,
            closed_at_ms=int(closed_at_ms),
            exit_fee_usd=exit_fee,
            exit_reason=str(exit_reason),
        )
        self._last_trade = trade
        self._active_sl_order_id = None
        return trade

    def get_trade_realized_pnl(self, *, symbol: str, since_timestamp=None):
        trade = self._last_trade
        if trade is None or trade.symbol != str(symbol).upper():
            return {"pnl": 0.0, "exit_price": None}
        return {"pnl": trade.net_pnl_usd, "exit_price": trade.exit_price}

    @staticmethod
    def _positive(value: float, name: str) -> None:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
            raise EntryValidationError(f"PAPER_VALUE_INVALID:{name}")
