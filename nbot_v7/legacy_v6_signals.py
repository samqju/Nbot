"""Exact selectively extracted V6 pure signal functions; frozen negative controls.
No Freqtrade classes, execution permissions, policy optimization or alpha claims.
Source: user_data/strategies/NbotV6LibraryResearch.py; see V7_V6_SIGNAL_PORT.json.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pandas import DataFrame

FAMILIES = (
    "ema_cross", "donchian_breakout", "bollinger_reversion", "rsi_reversion",
    "macd_momentum", "stochastic_reversal", "atr_breakout", "volume_trend",
)

def _safe_div(n: pd.Series, d: pd.Series) -> pd.Series:
    return n / d.replace(0, np.nan)

def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    move = close.diff()
    up = move.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    down = (-move.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    ratio = _safe_div(up, down)
    value = 100 - 100 / (1 + ratio)
    return value.where(down != 0, 100).where((up != 0) | (down != 0), 50)

def library_indicators(df: DataFrame) -> DataFrame:
    """Research-only feature indicators. No future bars, negative shifts or labels."""
    v = df.copy()
    close = v["close"]
    high, low = v["high"], v["low"]
    v["nb_ema_12"] = close.ewm(span=12, adjust=False, min_periods=12).mean()
    v["nb_ema_20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    v["nb_ema_26"] = close.ewm(span=26, adjust=False, min_periods=26).mean()
    v["nb_ema_50"] = close.ewm(span=50, adjust=False, min_periods=50).mean()
    v["nb_ema_100"] = close.ewm(span=100, adjust=False, min_periods=100).mean()
    v["nb_donchian_high"] = high.shift(1).rolling(20, min_periods=20).max()
    v["nb_donchian_low"] = low.shift(1).rolling(20, min_periods=20).min()
    v["nb_bb_mid"] = close.rolling(20, min_periods=20).mean()
    v["nb_bb_sd"] = close.rolling(20, min_periods=20).std()
    v["nb_rsi"] = _rsi(close)
    v["nb_macd"] = v["nb_ema_12"] - v["nb_ema_26"]
    v["nb_macd_signal"] = v["nb_macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    k_low = low.rolling(14, min_periods=14).min()
    k_high = high.rolling(14, min_periods=14).max()
    v["nb_stoch"] = 100 * _safe_div(close - k_low, k_high - k_low)
    v["nb_stoch_signal"] = v["nb_stoch"].rolling(3, min_periods=3).mean()
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    v["nb_atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    v["nb_atr_pct"] = _safe_div(v["nb_atr"], close)
    v["nb_volume_baseline"] = v["volume"].shift(1).rolling(24, min_periods=24).mean()
    return v

def _cross_above(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))

def _cross_below(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))

def library_signals(indicators: DataFrame, family: str,
                    *, rsi_low: int = 35, rsi_high: int = 65,
                    bb_deviation: float = 2.0,
                    atr_multiple: float = 1.2,
                    volume_multiple: float = 1.5) -> DataFrame:
    """Return two causal 5m signals for one candidate family.

    Conditions are calculated with an explicit minimum-history gate.
    Simultaneous long and short are resolved to NO TRADE, not arbitrarily
    assigned to a preferred side.
    """
    if family not in FAMILIES:
        raise ValueError("UNKNOWN_FROZEN_RESEARCH_FAMILY")
    d = indicators
    close = d["close"]
    fast, slow = d["nb_ema_20"], d["nb_ema_50"]
    up, down = fast > slow, fast < slow
    if family == "ema_cross":
        long = _cross_above(fast, slow) & (close > d["nb_ema_100"])
        short = _cross_below(fast, slow) & (close < d["nb_ema_100"])
    elif family == "donchian_breakout":
        long = up & (close > d["nb_donchian_high"])
        short = down & (close < d["nb_donchian_low"])
    elif family == "bollinger_reversion":
        lower = d["nb_bb_mid"] - bb_deviation * d["nb_bb_sd"]
        upper = d["nb_bb_mid"] + bb_deviation * d["nb_bb_sd"]
        long = (close.shift(1) < lower.shift(1)) & (close >= lower) & (d["nb_rsi"] < 50)
        short = (close.shift(1) > upper.shift(1)) & (close <= upper) & (d["nb_rsi"] > 50)
    elif family == "rsi_reversion":
        long = _cross_above(d["nb_rsi"], pd.Series(rsi_low, index=d.index)) & (close < d["nb_ema_100"])
        short = _cross_below(d["nb_rsi"], pd.Series(rsi_high, index=d.index)) & (close > d["nb_ema_100"])
    elif family == "macd_momentum":
        long = up & _cross_above(d["nb_macd"], d["nb_macd_signal"]) & (d["nb_macd"] > 0)
        short = down & _cross_below(d["nb_macd"], d["nb_macd_signal"]) & (d["nb_macd"] < 0)
    elif family == "stochastic_reversal":
        long = _cross_above(d["nb_stoch"], d["nb_stoch_signal"]) & (d["nb_stoch"].shift(1) < 20)
        short = _cross_below(d["nb_stoch"], d["nb_stoch_signal"]) & (d["nb_stoch"].shift(1) > 80)
    elif family == "atr_breakout":
        previous = d["nb_bb_mid"].shift(1)
        prior_atr = d["nb_atr"].shift(1)
        long = up & (close > previous + atr_multiple * prior_atr) & (close.shift(1) <= previous.shift(1) + atr_multiple * prior_atr.shift(1))
        short = down & (close < previous - atr_multiple * prior_atr) & (close.shift(1) >= previous.shift(1) - atr_multiple * prior_atr.shift(1))
    elif family == "volume_trend":
        enough = d["volume"] > volume_multiple * d["nb_volume_baseline"]
        long = up & enough & (close > d["nb_donchian_high"])
        short = down & enough & (close < d["nb_donchian_low"])
    needed = ["open", "high", "low", "close", "volume",
              "nb_ema_100", "nb_rsi", "nb_atr", "nb_stoch", "nb_macd_signal"]
    ready = d[needed].notna().all(axis=1)
    ready &= (d[["open", "high", "low", "close", "volume"]] > 0).all(axis=1)
    ready &= np.isfinite(d[needed]).all(axis=1)
    ready &= (d["high"] >= d[["open", "close", "low"]].max(axis=1))
    ready &= (d["low"] <= d[["open", "close", "high"]].min(axis=1))
    long = long.fillna(False) & ready
    short = short.fillna(False) & ready
    exclusive = ~(long & short)
    return DataFrame({"long": long & exclusive, "short": short & exclusive}, index=d.index)
