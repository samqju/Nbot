"""NBOT V6: deliberately small Freqtrade + FreqAI research/dry-run strategy.

This is a prototype, not an economically validated trading strategy.
No custom order execution, networking, portfolio accounting, or ML model framework.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy


class NbotV6(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 200

    # Baseline safety envelopes, NOT optimized/validated parameters.
    stoploss = -0.03
    minimal_roi = {"0": 0.05}
    use_exit_signal = True
    exit_profit_only = False
    trailing_stop = False

    # This is a decision-time proxy, not a measured transaction cost.
    # Freqtrade backtests/dry-run model fills separately. Funding and severe
    # slippage can make realized economics worse than this threshold suggests.
    roundtrip_cost_proxy = 0.002
    min_predicted_net_return = 0.004
    prediction_exit_threshold = 0.003

    def bot_start(self, **kwargs) -> None:
        """Fail closed if someone tries to turn the V6 prototype into a live bot."""
        mode = self.config.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        if mode not in {"backtest", "hyperopt", "edge"}:
            if self.config.get("dry_run") is not True:
                raise RuntimeError("NBOT_V6_LIVE_ORDERS_FORBIDDEN: dry_run must be true")
            if self.config.get("max_open_trades") != 1:
                raise RuntimeError("NBOT_V6_REQUIRES_ONE_GLOBAL_POSITION")
            if not self.config.get("freqai", {}).get("enabled", False):
                raise RuntimeError("NBOT_V6_REQUIRES_FREQAI")

    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        """Force 1x even on leveraged futures exchanges."""
        return 1.0

    def feature_engineering_expand_all(self, dataframe: DataFrame,
                                       period: int, **kwargs) -> DataFrame:
        """Past-only features for each configured pair, timeframe and period.

        FreqAI applies this to BTC as well via include_corr_pairlist.
        """
        close = dataframe["close"]
        ema = close.ewm(span=period, adjust=False, min_periods=period).mean()
        dataframe["%-ema_distance"] = close / ema - 1.0
        dataframe["%-volatility"] = close.pct_change().rolling(period, min_periods=period).std()
        dataframe["%-volume_ratio"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period, min_periods=period).mean() - 1.0
        )
        dataframe["%-momentum"] = close.pct_change(periods=period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        dataframe["%-body_fraction"] = (
            (dataframe["close"] - dataframe["open"]) / dataframe["close"].replace(0, np.nan)
        )
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        # Avoid new feature families until the first end-to-end baseline works.
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """Predict raw 12-candle close-to-close return (not realized trade PnL).

        Future data is used here *only* as the training label. FreqAI excludes
        the label from decision-time features. The last 12 rows remain NaN.
        """
        horizon = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        if horizon <= 0:
            raise ValueError("LABEL_HORIZON_MUST_BE_POSITIVE")
        dataframe["&-forward_return"] = dataframe["close"].shift(-horizon) / dataframe["close"] - 1.0
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Official FreqAI entry point: triggers training/inference and supplies
        # '&-forward_return' prediction plus 'do_predict'. Never called in a
        # feature_engineering_* method.
        dataframe = self.freqai.start(dataframe, metadata, self)

        close = dataframe["close"]
        dataframe["ema_fast"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
        dataframe["ema_slow"] = close.ewm(span=50, adjust=False, min_periods=50).mean()

        # Previous 20 completed candles only, no current-bar future high/low.
        dataframe["previous_high_20"] = dataframe["high"].shift(1).rolling(20, min_periods=20).max()
        dataframe["previous_low_20"] = dataframe["low"].shift(1).rolling(20, min_periods=20).min()

        uptrend = dataframe["ema_fast"] > dataframe["ema_slow"]
        downtrend = dataframe["ema_fast"] < dataframe["ema_slow"]
        previous_close = close.shift(1)
        previous_fast = dataframe["ema_fast"].shift(1)
        long_breakout = close > dataframe["previous_high_20"]
        short_breakout = close < dataframe["previous_low_20"]
        long_pullback = (previous_close <= previous_fast) & (close > dataframe["ema_fast"])
        short_pullback = (previous_close >= previous_fast) & (close < dataframe["ema_fast"])
        dataframe["long_setup"] = uptrend & (long_breakout | long_pullback)
        dataframe["short_setup"] = downtrend & (short_breakout | short_pullback)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        # FreqAI marks stale/outlier/unavailable model predictions by do_predict != 1.
        pred = dataframe["&-forward_return"]
        valid = (dataframe["do_predict"] == 1) & pred.notna() & np.isfinite(pred)
        valid &= (dataframe["volume"] > 0) & (dataframe["close"] > 0)
        min_return = self.roundtrip_cost_proxy + self.min_predicted_net_return
        long_ok = valid & dataframe["long_setup"].fillna(False) & (pred > min_return)
        short_ok = valid & dataframe["short_setup"].fillna(False) & (pred < -min_return)
        dataframe.loc[long_ok, "enter_long"] = 1
        dataframe.loc[short_ok, "enter_short"] = 1
        dataframe.loc[long_ok, "enter_tag"] = "v6_trend_setup_long"
        dataframe.loc[short_ok, "enter_tag"] = "v6_trend_setup_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        pred = dataframe["&-forward_return"]
        valid = (dataframe["do_predict"] == 1) & pred.notna() & np.isfinite(pred)
        # Trend reversal can exit even if model confidence has disappeared;
        # exchange-managed stoploss remains the primary downside protection.
        long_exit = (dataframe["ema_fast"] < dataframe["ema_slow"]) | (
            valid & (pred < -self.prediction_exit_threshold)
        )
        short_exit = (dataframe["ema_fast"] > dataframe["ema_slow"]) | (
            valid & (pred > self.prediction_exit_threshold)
        )
        dataframe.loc[long_exit.fillna(False), "exit_long"] = 1
        dataframe.loc[short_exit.fillna(False), "exit_short"] = 1
        return dataframe
