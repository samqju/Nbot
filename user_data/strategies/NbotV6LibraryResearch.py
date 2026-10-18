"""NBOT V6 offline-only strategy candidates, adapted from public-domain TA ideas.

No external strategy source files are copied. The indicators are independently
implemented with pandas/numpy from standard EMA, Donchian, Bollinger, RSI,
MACD, Stochastic, ATR, and volume-breakout definitions. Every market feature
uses only the current fully CLOSED candle and earlier candles. No performance
or economic validity is asserted by being included in this library.

One Freqtrade strategy class per candidate gives independent NATIVE backtests
and a Freqtrade Hyperopt interface; all share one 5-minute exit/risk envelope.
This module is NOT imported by the running original V6 historical backtest.
"""
from __future__ import annotations

from datetime import timedelta
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter


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


class _NbotV6ResearchLibraryBase(IStrategy):
    """One candidate = one official-engine Freqtrade strategy.

    No research-only class can open live or paper positions, even if started
    with the wrong command. Hyperopt/search results require frozen OOS test.
    """
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 250
    stoploss = -0.02
    minimal_roi = {"0": 0.05}
    use_exit_signal = True
    exit_profit_only = False
    trailing_stop = False

    family = ""  # mandatory explicit child class

    # Hyperopt *entry* space. Indicator calculation is fixed; values are
    # used only in populate_entry_trend and retain native Hyperopt semantics.
    rsi_low = IntParameter(25, 45, default=35, space="buy", optimize=True)
    rsi_high = IntParameter(55, 75, default=65, space="buy", optimize=True)
    bb_deviation = DecimalParameter(1.5, 3.0, decimals=1, default=2.0, space="buy", optimize=True)
    atr_multiple = DecimalParameter(0.8, 2.5, decimals=1, default=1.2, space="buy", optimize=True)
    volume_multiple = DecimalParameter(1.2, 3.0, decimals=1, default=1.5, space="buy", optimize=True)

    @property
    def protections(self):
        # Native Freqtrade support; must pass --enable-protections in
        # backtest and hyperopt. Applied to historical simulated trade ledger.
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 48,
             "trade_limit": 3, "stop_duration_candles": 24,
             "only_per_pair": False},
            {"method": "MaxDrawdown", "calculation_mode": "equity",
             "lookback_period_candles": 288, "trade_limit": 8,
             "stop_duration_candles": 48, "max_allowed_drawdown": 0.06},
        ]

    def _research_allowed(self) -> bool:
        cfg = self.config
        mode = cfg.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        exchange = cfg.get("exchange", {})
        return bool(
            self.family in FAMILIES
            and mode in ("backtest", "hyperopt")
            and cfg.get("dry_run") is True
            and cfg.get("nbot_v6_library_research_only") is True
            and cfg.get("nbot_live_mode") is False
            and cfg.get("nbot_paper_research_mode") is False
            and cfg.get("max_open_trades") == 1
            and cfg.get("stake_amount") == 1000
            and cfg.get("trading_mode") == "futures"
            and cfg.get("margin_mode") == "isolated"
            and cfg.get("force_entry_enable") is False
            and not exchange.get("key") and not exchange.get("secret")
            and cfg.get("api_server", {}).get("enabled") is False
            and cfg.get("telegram", {}).get("enabled") is False
        )

    def bot_start(self, **kwargs) -> None:
        if not self._research_allowed():
            raise RuntimeError("NBOT_V6_LIBRARY_OFFLINE_NATIVE_RESEARCH_ONLY")

    def confirm_trade_entry(self, pair, order_type, amount, rate,
                            time_in_force, current_time, entry_tag,
                            side, **kwargs) -> bool:
        return self._research_allowed()

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return library_indicators(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        valid = library_signals(
            dataframe, self.family,
            rsi_low=int(self.rsi_low.value), rsi_high=int(self.rsi_high.value),
            bb_deviation=float(self.bb_deviation.value),
            atr_multiple=float(self.atr_multiple.value),
            volume_multiple=float(self.volume_multiple.value),
        )
        dataframe.loc[valid["long"], "enter_long"] = 1
        dataframe.loc[valid["short"], "enter_short"] = 1
        dataframe.loc[valid["long"], "enter_tag"] = "library_" + self.family + "_long"
        dataframe.loc[valid["short"], "enter_tag"] = "library_" + self.family + "_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_exit(self, pair, trade, current_time, current_rate,
                    current_profit, **kwargs):
        if current_time >= trade.open_date_utc + timedelta(minutes=60):
            return "v6_library_60m_exit"
        return None


class NbotV6EmaCrossResearch(_NbotV6ResearchLibraryBase):
    family = "ema_cross"

class NbotV6DonchianResearch(_NbotV6ResearchLibraryBase):
    family = "donchian_breakout"

class NbotV6BollingerResearch(_NbotV6ResearchLibraryBase):
    family = "bollinger_reversion"

class NbotV6RsiResearch(_NbotV6ResearchLibraryBase):
    family = "rsi_reversion"

class NbotV6MacdResearch(_NbotV6ResearchLibraryBase):
    family = "macd_momentum"

class NbotV6StochasticResearch(_NbotV6ResearchLibraryBase):
    family = "stochastic_reversal"

class NbotV6AtrBreakoutResearch(_NbotV6ResearchLibraryBase):
    family = "atr_breakout"

class NbotV6VolumeTrendResearch(_NbotV6ResearchLibraryBase):
    family = "volume_trend"


# Controlled research-only exit-rule A/B comparison: same indicator entries,
# same nominal -2% initial safety stop, same 5% ROI, same one-hour limit.
# Trailing begins ONLY once a trade reaches +2% and follows with a 1%
# trail thereafter. Those figures are FROZEN exploratory assumptions;
# V1-V5 original trailing parameters have not been recovered and this is
# NOT claimed to reproduce the old bot. Native Freqtrade candles determine
# actual hypothetical fills; results can improve OR worsen after costs.
class _NbotV6TrailingResearchBase(_NbotV6ResearchLibraryBase):
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True


class NbotV6EmaCrossTrailingResearch(_NbotV6TrailingResearchBase):
    family = "ema_cross"

class NbotV6DonchianTrailingResearch(_NbotV6TrailingResearchBase):
    family = "donchian_breakout"

class NbotV6BollingerTrailingResearch(_NbotV6TrailingResearchBase):
    family = "bollinger_reversion"

class NbotV6RsiTrailingResearch(_NbotV6TrailingResearchBase):
    family = "rsi_reversion"

class NbotV6MacdTrailingResearch(_NbotV6TrailingResearchBase):
    family = "macd_momentum"

class NbotV6StochasticTrailingResearch(_NbotV6TrailingResearchBase):
    family = "stochastic_reversal"

class NbotV6AtrBreakoutTrailingResearch(_NbotV6TrailingResearchBase):
    family = "atr_breakout"

class NbotV6VolumeTrendTrailingResearch(_NbotV6TrailingResearchBase):
    family = "volume_trend"
