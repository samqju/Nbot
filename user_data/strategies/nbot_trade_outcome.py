"""Offline NBOT V6 research: what-if complete trade outcomes, not exchange fills.

Setup features use only candles through the decision close. Outcomes are
future-only training LABELS from entry at next candle OPEN, 2% adverse
stop, 5% favorable target, and finite horizon. OHLC ambiguity = STOP first.
Every eligible breakout/pullback opportunity can be recorded, even when
the actual original portfolio rejected it. Never a trading engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
from pandas import DataFrame, Series

KINDS = ("breakout_long", "breakout_short", "pullback_long", "pullback_short")


@dataclass(frozen=True)
class CostPolicy:
    fee_side: float = 0.0005
    slippage_side: float = 0.0005
    funding_reserve: float = 0.0001
    stop: float = 0.02
    target: float = 0.05
    horizon: int = 12

    def __post_init__(self):
        for key in ("fee_side", "slippage_side", "funding_reserve"):
            val = getattr(self, key)
            if not math.isfinite(val) or not 0 <= val <= 0.02:
                raise ValueError("INVALID_COST_" + key)
        if type(self.horizon) is not int or not 1 <= self.horizon <= 288:
            raise ValueError("INVALID_HORIZON")
        if not 0 < self.stop <= .1 or not 0 < self.target <= .3:
            raise ValueError("INVALID_STOP_TARGET")

    @property
    def cost_roundtrip(self):
        return 2 * (self.fee_side + self.slippage_side) + self.funding_reserve


def setups(df: DataFrame) -> DataFrame:
    needed = {"open", "high", "low", "close", "volume"}
    if not needed.issubset(df):
        raise ValueError("MISSING_OHLCV")
    close = df["close"]
    fast = close.ewm(span=20, adjust=False, min_periods=20).mean()
    slow = close.ewm(span=50, adjust=False, min_periods=50).mean()
    prior_high = df["high"].shift(1).rolling(20, min_periods=20).max()
    prior_low = df["low"].shift(1).rolling(20, min_periods=20).min()
    valid = (
        np.isfinite(df[["open", "high", "low", "close", "volume"]]).all(axis=1)
        & (df[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (df["volume"] > 0)
        & (df["high"] >= df[["open", "low", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "high", "close"]].min(axis=1))
    )
    up, down = fast > slow, fast < slow
    result = DataFrame(index=df.index)
    result["breakout_long"] = valid & up & (close > prior_high)
    result["breakout_short"] = valid & down & (close < prior_low)
    result["pullback_long"] = valid & up & (close.shift(1) <= fast.shift(1)) & (close > fast)
    result["pullback_short"] = valid & down & (close.shift(1) >= fast.shift(1)) & (close < fast)
    return result.fillna(False).astype(bool)


def outcome(df: DataFrame, decision: int, side: int,
            cost: CostPolicy = CostPolicy()) -> dict | None:
    """Hypothetical trade from NEXT OPEN. Never label missing future bars."""
    end = decision + cost.horizon
    if side not in (-1, 1) or decision < 0 or end >= len(df):
        return None
    values = df.iloc[decision + 1:end + 1][["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        return None
    if (values[:, 1] < values[:, [0, 2, 3]].max(axis=1)).any():
        return None
    if (values[:, 2] > values[:, [0, 1, 3]].min(axis=1)).any():
        return None
    entry = float(values[0, 0])
    stop = entry * (1 - side * cost.stop)
    take = entry * (1 + side * cost.target)
    exit_px, bars, reason = float(values[-1, 3]), cost.horizon, "time"
    for j, (op, hi, lo, cl) in enumerate(values, start=1):
        if side == 1:
            if op <= stop: exit_px, bars, reason = float(op), j, "gap_stop"
            elif lo <= stop: exit_px, bars, reason = stop, j, "stop_first"
            elif op >= take or hi >= take: exit_px, bars, reason = take, j, "target"
            else: continue
        else:
            if op >= stop: exit_px, bars, reason = float(op), j, "gap_stop"
            elif hi >= stop: exit_px, bars, reason = stop, j, "stop_first"
            elif op <= take or lo <= take: exit_px, bars, reason = take, j, "target"
            else: continue
        break
    gross = side * (exit_px / entry - 1)
    return {
        "entry_index": decision + 1, "exit_index": decision + bars,
        "side": "long" if side == 1 else "short",
        "gross_return": gross, "net_return": gross - cost.cost_roundtrip,
        "assumed_roundtrip_cost": cost.cost_roundtrip,
        "exit_reason": reason
    }


def opportunity_table(df: DataFrame, cost: CostPolicy = CostPolicy()) -> DataFrame:
    """Keep EVERY matching kind, including rejected portfolio opportunities."""
    flags = setups(df)
    rows = []
    for i in range(len(df) - cost.horizon):
        for kind in KINDS:
            if not flags[kind].iloc[i]:
                continue
            result = outcome(df, i, -1 if kind.endswith("_short") else 1, cost)
            if result is None:
                continue
            rows.append({"decision_index": i, "candidate": kind,
                         "wins_after_costs": result["net_return"] > 0, **result})
    return DataFrame.from_records(rows)


def priority_kind(flags: DataFrame) -> Series:
    """Single FreqAI target per candle; breakouts take priority.

    Offline opportunity_table retains both when they coincide.
    """
    result = Series(0, index=flags.index, dtype="int64")
    for i, kind in reversed(list(enumerate(KINDS, start=1))):
        result.loc[flags[kind]] = i
    return result


def training_labels(df: DataFrame, cost: CostPolicy = CostPolicy()) -> DataFrame:
    """Attach only &-target future outcomes; missing opportunities = NaN."""
    flags = setups(df)
    code = priority_kind(flags)
    values = np.full(len(df), np.nan)
    for i in range(len(df) - cost.horizon):
        idx = int(code.iloc[i])
        if idx == 0:
            continue
        result = outcome(df, i, -1 if KINDS[idx - 1].endswith("_short") else 1, cost)
        if result is not None:
            values[i] = result["net_return"]
    frame = df.copy()
    frame["&-trade_net_return"] = values
    return frame


def decision_features(df: DataFrame) -> DataFrame:
    """Numeric past-only FreqAI %-features; never use trade outcomes here."""
    flags = setups(df)
    frame = df.copy()
    frame["%-setup_id"] = priority_kind(flags).astype(float)
    fast = df["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    slow = df["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    frame["%-market_trend"] = fast / slow - 1
    frame["%-recent_volatility"] = df["close"].pct_change().rolling(24, min_periods=24).std()
    frame["%-relative_volume"] = df["volume"] / df["volume"].rolling(24, min_periods=24).mean() - 1
    return frame
