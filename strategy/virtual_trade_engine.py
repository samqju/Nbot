"""Parallel virtual-trade engine for all candidates."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from config import (
    VIRTUAL_TRADES_PATH,
    VIRTUAL_TRADE_MAX_ACTIVE,
    VIRTUAL_TRADE_MAX_CANDLES,
    VIRTUAL_TRADE_TARGET_R,
)


class VirtualTradeEngine:
    def __init__(
        self,
        *,
        system_log=None,
        outcome_writer=None,
        runtime_store=None,
        environment: str | None = None,
        execution_mode: str | None = None,
    ):
        self.system_log = system_log
        self.environment = (
            str(environment).strip().upper() if environment else None
        )
        self.execution_mode = (
            str(execution_mode).strip().upper() if execution_mode else None
        )
        self.outcome_writer = outcome_writer
        self.runtime_store = runtime_store
        self.path = Path(VIRTUAL_TRADES_PATH)
        self.max_active = VIRTUAL_TRADE_MAX_ACTIVE
        self.max_candles = VIRTUAL_TRADE_MAX_CANDLES
        self.target_r = VIRTUAL_TRADE_TARGET_R
        self._active = {}
        self._lock = threading.Lock()
        self._restore_active_trades()

    def enroll(self, candidate) -> bool:
        if candidate.risk_plan is None:
            raise ValueError("VIRTUAL_TRADE_RISK_PLAN_MISSING")
        key = candidate.observation_id
        with self._lock:
            if key in self._active:
                return False
            if len(self._active) >= self.max_active:
                if self.system_log:
                    self.system_log.warning(
                        "VIRTUAL_TRADE_CAPACITY_REACHED | "
                        f"active={len(self._active)}"
                    )
                return False
            plan = candidate.risk_plan
            self._active[key] = {
                "candidate_observation_id": key,
                "symbol": candidate.symbol,
                "direction": candidate.direction,
                "pattern": candidate.pattern,
                "entry_price": float(plan.reference_price),
                "stop_price": float(plan.suggested_stop_price),
                "risk_distance": float(plan.stop_distance_price),
                "target_price": (
                    float(plan.reference_price) + self.target_r * float(plan.stop_distance_price)
                    if candidate.direction == "LONG"
                    else float(plan.reference_price) - self.target_r * float(plan.stop_distance_price)
                ),
                "candles_seen": 0,
                "mae_r": 0.0,
                "mfe_r": 0.0,
                "opened_at_ms": int(time.time() * 1000),
                "environment": self.environment,
                "execution_mode": self.execution_mode,
            }
            self._persist_active_locked()
        return True

    def enroll_all(self, candidates) -> int:
        return sum(1 for candidate in candidates if self.enroll(candidate))

    def on_candle(self, symbol: str, candle: tuple) -> list[dict]:
        _, high, low, close = candle
        finished = []
        with self._lock:
            for key, trade in list(self._active.items()):
                if trade["symbol"] != symbol:
                    continue
                risk = trade["risk_distance"]
                entry = trade["entry_price"]
                if trade["direction"] == "LONG":
                    adverse = max(0.0, (entry - low) / risk)
                    favorable = max(0.0, (high - entry) / risk)
                    stop_hit = low <= trade["stop_price"]
                    target_hit = high >= trade["target_price"]
                else:
                    adverse = max(0.0, (high - entry) / risk)
                    favorable = max(0.0, (entry - low) / risk)
                    stop_hit = high >= trade["stop_price"]
                    target_hit = low <= trade["target_price"]

                trade["mae_r"] = max(trade["mae_r"], adverse)
                trade["mfe_r"] = max(trade["mfe_r"], favorable)
                trade["candles_seen"] += 1

                reason = None
                exit_r = None
                if stop_hit and target_hit:
                    reason, exit_r = "AMBIGUOUS_STOP_FIRST", -1.0
                elif stop_hit:
                    reason, exit_r = "STOP_LOSS", -1.0
                elif target_hit:
                    reason, exit_r = "TARGET", self.target_r
                elif trade["candles_seen"] >= self.max_candles:
                    reason = "TIMEOUT"
                    exit_r = (
                        (close - entry) / risk
                        if trade["direction"] == "LONG"
                        else (entry - close) / risk
                    )

                if reason is not None:
                    result = dict(trade)
                    result.update({
                        "closed_at_ms": int(time.time() * 1000),
                        "exit_reason": reason,
                        "exit_r": float(exit_r),
                        "profitable": bool(exit_r > 0),
                    })
                    finished.append(result)
                    del self._active[key]

            # Persist MAE/MFE/candle-count progress even when no trade closes.
            self._persist_active_locked()

        for result in finished:
            self._append(result)
            if self.outcome_writer:
                self.outcome_writer.append(
                    observation_id=result["candidate_observation_id"],
                    outcome_type="VIRTUAL_TRADE",
                    symbol=result["symbol"],
                    direction=result["direction"],
                    payload={
                        "pattern": result["pattern"],
                        "exit_reason": result["exit_reason"],
                        "exit_r": result["exit_r"],
                        "mae_r": result["mae_r"],
                        "mfe_r": result["mfe_r"],
                        "candles_seen": result["candles_seen"],
                        "profitable": result["profitable"],
                    },
                )
        return finished

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def active_symbols(self) -> set[str]:
        """Return symbols that still require candle updates."""
        with self._lock:
            return {
                trade["symbol"]
                for trade in self._active.values()
                if trade.get("symbol")
            }

    def _restore_active_trades(self) -> None:
        if self.runtime_store is None:
            return

        rows = self.runtime_store.get_section(
            "active_virtual_trades"
        )
        restored = {}
        for trade in rows:
            self._validate_recovered_trade(trade)
            key = trade["candidate_observation_id"]
            if key in restored:
                raise RuntimeError(
                    "VIRTUAL_TRADE_RECOVERY_DUPLICATE_ID"
                )
            restored[key] = dict(trade)

        if len(restored) > self.max_active:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_CAPACITY_EXCEEDED"
            )

        self._active = restored
        if self.system_log:
            self.system_log.info(
                "VIRTUAL_TRADES_RECOVERED | "
                f"count={len(restored)}"
            )

    @staticmethod
    def _validate_recovered_trade(trade: dict) -> None:
        required = {
            "candidate_observation_id",
            "symbol",
            "direction",
            "pattern",
            "entry_price",
            "stop_price",
            "risk_distance",
            "target_price",
            "candles_seen",
            "mae_r",
            "mfe_r",
            "opened_at_ms",
        }
        if not isinstance(trade, dict) or not required.issubset(trade):
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_SCHEMA_INVALID"
            )
        if trade["direction"] not in {"LONG", "SHORT"}:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_DIRECTION_INVALID"
            )
        if float(trade["entry_price"]) <= 0:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_ENTRY_INVALID"
            )
        if float(trade["risk_distance"]) <= 0:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_RISK_INVALID"
            )
        if int(trade["candles_seen"]) < 0:
            raise RuntimeError(
                "VIRTUAL_TRADE_RECOVERY_CANDLES_INVALID"
            )

    def _persist_active_locked(self) -> None:
        if self.runtime_store is None:
            return
        self.runtime_store.replace_section(
            "active_virtual_trades",
            [dict(trade) for trade in self._active.values()],
        )

    def _append(self, row):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str)
        fd = os.open(
            self.path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
