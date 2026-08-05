"""Persistent local account state for paper trading.

This module does not connect to Binance and cannot submit exchange orders.
It owns only simulated balance, one open paper position, and immutable
completed-trade history.
"""

import json
import math
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from execution.paper_models import PaperPosition, PaperTrade


_STATE_VERSION = 1
_VALID_SIDES = {"LONG", "SHORT"}


class PaperAccount:
    """Thread-safe, single-position paper account with atomic persistence."""

    def __init__(
        self,
        *,
        starting_balance_usd: float,
        state_path: str,
        trades_path: str,
        source: str,
    ) -> None:
        self._validate_positive_finite(
            starting_balance_usd,
            "starting_balance_usd",
        )
        if not state_path:
            raise ValueError("PAPER_ACCOUNT_INVALID: state_path")
        if not trades_path:
            raise ValueError("PAPER_ACCOUNT_INVALID: trades_path")

        self.state_path = Path(state_path)
        self.trades_path = Path(trades_path)
        if self.state_path.resolve() == self.trades_path.resolve():
            raise ValueError("PAPER_ACCOUNT_INVALID: paths_must_differ")

        source = str(source).strip().upper()
        if not source:
            raise ValueError("PAPER_ACCOUNT_INVALID: source")

        self._lock = threading.RLock()
        self._starting_balance_usd = float(starting_balance_usd)
        self._state: Dict[str, Any] = {
            "version": _STATE_VERSION,
            "source": source,
            "starting_balance_usd": float(starting_balance_usd),
            "balance_usd": float(starting_balance_usd),
            "realized_pnl_usd": 0.0,
            "fees_paid_usd": 0.0,
            "completed_trade_count": 0,
            "open_position": None,
        }

    # --------------------------------------------------
    # Persistence
    # --------------------------------------------------

    def load_or_create(self) -> None:
        """Load an existing account or atomically create a new one."""
        with self._lock:
            if not self.state_path.exists():
                self._persist_state()
                return

            try:
                with self.state_path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
            except Exception as exc:
                raise RuntimeError(
                    f"PAPER_STATE_LOAD_FAILED | path={self.state_path} | "
                    f"error={exc}"
                ) from exc

            self._validate_state(loaded)
            if loaded["source"] != self._state["source"]:
                raise RuntimeError(
                    "PAPER_STATE_SOURCE_MISMATCH | "
                    f"stored={loaded['source']} | "
                    f"requested={self._state['source']}"
                )
            self._state = loaded

    def save(self) -> None:
        with self._lock:
            self._persist_state()

    def _persist_state(self) -> None:
        self._validate_state(self._state)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_path.with_name(self.state_path.name + ".tmp")

        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(
                    self._state,
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.state_path)
        except Exception as exc:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise RuntimeError(
                f"PAPER_STATE_SAVE_FAILED | path={self.state_path} | "
                f"error={exc}"
            ) from exc

    def _append_trade(self, trade: PaperTrade) -> None:
        self.trades_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.trades_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(trade.to_dict(), sort_keys=True))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception as exc:
            raise RuntimeError(
                f"PAPER_TRADE_APPEND_FAILED | path={self.trades_path} | "
                f"error={exc}"
            ) from exc

    # --------------------------------------------------
    # Read helpers
    # --------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def get_balance_usd(self) -> float:
        with self._lock:
            return float(self._state["balance_usd"])

    def get_realized_pnl_usd(self) -> float:
        with self._lock:
            return float(self._state["realized_pnl_usd"])

    def get_open_position(self) -> Optional[PaperPosition]:
        with self._lock:
            raw = self._state.get("open_position")
            if raw is None:
                return None
            return PaperPosition.from_dict(dict(raw))

    # --------------------------------------------------
    # Position lifecycle
    # --------------------------------------------------

    def open_position(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        entry_price: float,
        stop_loss: float,
        opened_at_ms: int,
        initial_risk_usd: float,
        entry_fee_usd: float,
        structure_fingerprint: Optional[str] = None,
        strategy_version: Optional[str] = None,
        model_version: Optional[str] = None,
        trade_id: Optional[str] = None,
    ) -> PaperPosition:
        with self._lock:
            if self._state["open_position"] is not None:
                raise RuntimeError("PAPER_POSITION_ALREADY_OPEN")

            symbol = str(symbol).strip().upper()
            side = str(side).strip().upper()
            if not symbol:
                raise ValueError("PAPER_POSITION_INVALID: symbol")
            if side not in _VALID_SIDES:
                raise ValueError("PAPER_POSITION_INVALID: side")

            for value, name in (
                (qty, "qty"),
                (entry_price, "entry_price"),
                (stop_loss, "stop_loss"),
                (initial_risk_usd, "initial_risk_usd"),
            ):
                self._validate_positive_finite(value, name)
            self._validate_nonnegative_finite(entry_fee_usd, "entry_fee_usd")
            if not isinstance(opened_at_ms, int) or opened_at_ms <= 0:
                raise ValueError("PAPER_POSITION_INVALID: opened_at_ms")
            if side == "LONG" and stop_loss >= entry_price:
                raise ValueError("PAPER_POSITION_INVALID: long_stop")
            if side == "SHORT" and stop_loss <= entry_price:
                raise ValueError("PAPER_POSITION_INVALID: short_stop")

            position = PaperPosition(
                trade_id=trade_id or uuid.uuid4().hex,
                symbol=symbol,
                side=side,
                qty=float(qty),
                entry_price=float(entry_price),
                stop_loss=float(stop_loss),
                opened_at_ms=opened_at_ms,
                initial_risk_usd=float(initial_risk_usd),
                entry_fee_usd=float(entry_fee_usd),
                highest_price=float(entry_price),
                lowest_price=float(entry_price),
                structure_fingerprint=structure_fingerprint,
                strategy_version=strategy_version,
                model_version=model_version,
            )

            self._state["open_position"] = position.to_dict()
            self._state["balance_usd"] -= float(entry_fee_usd)
            self._state["fees_paid_usd"] += float(entry_fee_usd)
            self._persist_state()
            return position

    def update_position_market_extremes(self, market_price: float) -> PaperPosition:
        with self._lock:
            self._validate_positive_finite(market_price, "market_price")
            position = self.get_open_position()
            if position is None:
                raise RuntimeError("PAPER_POSITION_NOT_OPEN")

            raw = position.to_dict()
            raw["highest_price"] = max(
                float(raw["highest_price"]),
                float(market_price),
            )
            raw["lowest_price"] = min(
                float(raw["lowest_price"]),
                float(market_price),
            )
            updated = PaperPosition.from_dict(raw)
            self._state["open_position"] = updated.to_dict()
            self._persist_state()
            return updated

    def update_stop_loss(self, stop_loss: float) -> PaperPosition:
        with self._lock:
            self._validate_positive_finite(stop_loss, "stop_loss")
            position = self.get_open_position()
            if position is None:
                raise RuntimeError("PAPER_POSITION_NOT_OPEN")
            if position.side == "LONG" and stop_loss >= position.entry_price:
                # A later trailing stop may move beyond entry, so only require
                # it to be below the current recorded high.
                if stop_loss >= float(position.highest_price):
                    raise ValueError("PAPER_POSITION_INVALID: long_stop")
            if position.side == "SHORT" and stop_loss <= position.entry_price:
                if stop_loss <= float(position.lowest_price):
                    raise ValueError("PAPER_POSITION_INVALID: short_stop")

            raw = position.to_dict()
            raw["stop_loss"] = float(stop_loss)
            updated = PaperPosition.from_dict(raw)
            self._state["open_position"] = updated.to_dict()
            self._persist_state()
            return updated

    def close_position(
        self,
        *,
        exit_price: float,
        closed_at_ms: int,
        exit_fee_usd: float,
        exit_reason: str,
    ) -> PaperTrade:
        with self._lock:
            position = self.get_open_position()
            if position is None:
                raise RuntimeError("PAPER_POSITION_NOT_OPEN")
            self._validate_positive_finite(exit_price, "exit_price")
            self._validate_nonnegative_finite(exit_fee_usd, "exit_fee_usd")
            if not isinstance(closed_at_ms, int) or closed_at_ms <= 0:
                raise ValueError("PAPER_TRADE_INVALID: closed_at_ms")
            if closed_at_ms < position.opened_at_ms:
                raise ValueError("PAPER_TRADE_INVALID: close_before_open")
            exit_reason = str(exit_reason).strip().upper()
            if not exit_reason:
                raise ValueError("PAPER_TRADE_INVALID: exit_reason")

            direction = 1.0 if position.side == "LONG" else -1.0
            gross_pnl = (
                (float(exit_price) - position.entry_price)
                * position.qty
                * direction
            )
            net_pnl = gross_pnl - position.entry_fee_usd - float(exit_fee_usd)
            net_r = net_pnl / position.initial_risk_usd

            trade = PaperTrade(
                trade_id=position.trade_id,
                symbol=position.symbol,
                side=position.side,
                qty=position.qty,
                entry_price=position.entry_price,
                exit_price=float(exit_price),
                opened_at_ms=position.opened_at_ms,
                closed_at_ms=closed_at_ms,
                initial_risk_usd=position.initial_risk_usd,
                gross_pnl_usd=gross_pnl,
                entry_fee_usd=position.entry_fee_usd,
                exit_fee_usd=float(exit_fee_usd),
                net_pnl_usd=net_pnl,
                net_r=net_r,
                exit_reason=exit_reason,
                highest_price=position.highest_price,
                lowest_price=position.lowest_price,
                structure_fingerprint=position.structure_fingerprint,
                strategy_version=position.strategy_version,
                model_version=position.model_version,
                source=self._state["source"],
            )

            # Trade history is written first. If that durable append fails,
            # the open position remains intact and can be retried safely.
            self._append_trade(trade)
            self._state["balance_usd"] += gross_pnl - float(exit_fee_usd)
            self._state["realized_pnl_usd"] += net_pnl
            self._state["fees_paid_usd"] += float(exit_fee_usd)
            self._state["completed_trade_count"] += 1
            self._state["open_position"] = None
            self._persist_state()
            return trade

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def _validate_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise ValueError("PAPER_STATE_CORRUPTED_NOT_DICT")
        required = {
            "version",
            "source",
            "starting_balance_usd",
            "balance_usd",
            "realized_pnl_usd",
            "fees_paid_usd",
            "completed_trade_count",
            "open_position",
        }
        missing = sorted(required.difference(state))
        if missing:
            raise ValueError(
                "PAPER_STATE_CORRUPTED_MISSING_KEYS:"
                + ",".join(missing)
            )
        if state["version"] != _STATE_VERSION:
            raise ValueError(
                f"PAPER_STATE_VERSION_UNSUPPORTED:{state['version']}"
            )
        if not isinstance(state["source"], str) or not state["source"]:
            raise ValueError("PAPER_STATE_CORRUPTED_SOURCE")

        self._validate_positive_finite(
            state["starting_balance_usd"],
            "starting_balance_usd",
        )
        for key in ("balance_usd", "realized_pnl_usd", "fees_paid_usd"):
            if not isinstance(state[key], (int, float)) or not math.isfinite(
                float(state[key])
            ):
                raise ValueError(f"PAPER_STATE_CORRUPTED_{key}")
        if state["balance_usd"] < 0:
            raise ValueError("PAPER_STATE_CORRUPTED_NEGATIVE_BALANCE")
        if state["fees_paid_usd"] < 0:
            raise ValueError("PAPER_STATE_CORRUPTED_NEGATIVE_FEES")
        if (
            not isinstance(state["completed_trade_count"], int)
            or state["completed_trade_count"] < 0
        ):
            raise ValueError("PAPER_STATE_CORRUPTED_TRADE_COUNT")

        raw_position = state["open_position"]
        if raw_position is not None:
            if not isinstance(raw_position, dict):
                raise ValueError("PAPER_STATE_CORRUPTED_OPEN_POSITION")
            position = PaperPosition.from_dict(raw_position)
            if position.side not in _VALID_SIDES:
                raise ValueError("PAPER_STATE_CORRUPTED_POSITION_SIDE")
            for value, name in (
                (position.qty, "position_qty"),
                (position.entry_price, "position_entry_price"),
                (position.stop_loss, "position_stop_loss"),
                (position.initial_risk_usd, "position_initial_risk_usd"),
            ):
                self._validate_positive_finite(value, name)

    @staticmethod
    def _validate_positive_finite(value: float, name: str) -> None:
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0
        ):
            raise ValueError(f"PAPER_ACCOUNT_INVALID: {name}")

    @staticmethod
    def _validate_nonnegative_finite(value: float, name: str) -> None:
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise ValueError(f"PAPER_ACCOUNT_INVALID: {name}")
