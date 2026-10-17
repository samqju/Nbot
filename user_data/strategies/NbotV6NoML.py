"""NBOT V6 M2 — frozen NO-ML signal baseline for comparison only.

Not deployable for live trading. Uses the same 5m EMA20/EMA50 trend,
prior-20-candle breakouts and EMA pullbacks as NbotV6, but NO AI,
NO confidence/return threshold and NO AI exit overlay. Explicit
dry-run authorization on startup and every entry. Not an optimization.
"""
from __future__ import annotations

from pandas import DataFrame
from freqtrade.strategy import IStrategy


class NbotV6NoML(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 200

    stoploss = -0.02
    minimal_roi = {"0": 0.05}
    use_exit_signal = True
    exit_profit_only = False
    trailing_stop = False
    order_types = {
        "entry": "limit", "exit": "limit", "emergency_exit": "market",
        "stoploss": "market", "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
    }

    def bot_start(self, **kwargs) -> None:
        if self.config.get("dry_run") is not True:
            raise RuntimeError("NBOT_M2_NONML_BASELINE_DRY_RUN_ONLY")
        # Freqtrade lookahead-analysis forces unlimited slots and 10k stake.
        # Permit this override only in BACKTEST mode; never normal dry-run.
        mode = self.config.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        slots = self.config.get("max_open_trades")
        if slots != 1 and not (mode == "backtest" and slots == -1):
            raise RuntimeError("NBOT_M2_NONML_BASELINE_ONE_SLOT_ONLY")
        credentials = self.config.get("exchange", {})
        if credentials.get("key") or credentials.get("secret"):
            raise RuntimeError("NBOT_M2_NONML_BASELINE_NO_KEYS")

    def confirm_trade_entry(self, pair, order_type, amount, rate,
                            time_in_force, current_time, entry_tag, side,
                            **kwargs) -> bool:
        return self.config.get("dry_run") is True and not (
            self.config.get("exchange", {}).get("key")
            or self.config.get("exchange", {}).get("secret")
        )

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        close = dataframe["close"]
        dataframe["ema_fast"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
        dataframe["ema_slow"] = close.ewm(span=50, adjust=False, min_periods=50).mean()

        # Prior *completed* 20 candles; never peek into future.
        dataframe["previous_high_20"] = dataframe["high"].shift(1).rolling(
            20, min_periods=20
        ).max()
        dataframe["previous_low_20"] = dataframe["low"].shift(1).rolling(
            20, min_periods=20
        ).min()

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
        valid = (dataframe["volume"] > 0) & (dataframe["close"] > 0)
        long_entry = valid & dataframe["long_setup"].fillna(False)
        short_entry = valid & dataframe["short_setup"].fillna(False)
        dataframe.loc[long_entry, "enter_long"] = 1
        dataframe.loc[short_entry, "enter_short"] = 1
        dataframe.loc[long_entry, "enter_tag"] = "m2_nonml_long"
        dataframe.loc[short_entry, "enter_tag"] = "m2_nonml_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe.loc[
            dataframe["ema_fast"] < dataframe["ema_slow"], "exit_long"
        ] = 1
        dataframe.loc[
            dataframe["ema_fast"] > dataframe["ema_slow"], "exit_short"
        ] = 1
        return dataframe
