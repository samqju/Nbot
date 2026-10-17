"""Separate after-cost LightGBM FreqAI Challenger — historical research ONLY.

Not the current V6 production strategy. NO paper/live trading, API keys,
model auto-promotion or dynamic order execution. The core NbotV6 remains
unchanged. This trains on hypothetical next-open trade outcomes, not raw
future price movement, with the SAME causal EMA breakout/pullback setups.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame

from NbotV6 import NbotV6
from nbot_trade_outcome import CostPolicy, decision_features, training_labels


class NbotV6TradeOutcomeResearch(NbotV6):
    # High-impact research strategy must never acquire live trading authority.
    # Inherits original one-slot risk envelope, stoploss and 1x leverage.
    min_predicted_net_after_cost = 0.004

    def bot_start(self, **kwargs) -> None:
        mode = self.config.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        e = self.config.get("exchange", {})
        if not (
            self.config.get("nbot_m2r_research_only") is True
            and mode == "backtest"
            and self.config.get("dry_run") is True
            and self.config.get("max_open_trades") == 1
            and not e.get("key")
            and not e.get("secret")
            and self.config.get("freqai", {}).get("enabled") is True
            and self.config.get("nbot_paper_research_mode") is not True
            and self.config.get("nbot_live_mode") is not True
            and self.config.get("api_server", {}).get("enabled") is False
            and self.config.get("telegram", {}).get("enabled") is False
        ):
            raise RuntimeError("NBOT_M2R_HISTORICAL_ONLY_NO_PAPER_NO_LIVE")

    def confirm_trade_entry(self, pair, order_type, amount, rate,
                            time_in_force, current_time, entry_tag, side,
                            **kwargs) -> bool:
        # Backtest-only test. Even a mistaken dry-run/paper startup cannot
        # pass this entry hook.
        mode = self.config.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        return bool(mode == "backtest"
                    and self.config.get("nbot_m2r_research_only") is True
                    and self.config.get("dry_run") is True
                    and self.config.get("max_open_trades") == 1
                    and not self.config.get("exchange", {}).get("key")
                    and not self.config.get("exchange", {}).get("secret"))

    def feature_engineering_standard(self, dataframe: DataFrame,
                                     **kwargs) -> DataFrame:
        return decision_features(dataframe)

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        horizon = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        costs = CostPolicy(horizon=horizon)
        # All future OHLCV is used here solely as a FreqAI &-label.
        return training_labels(dataframe, costs)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        pred = dataframe["&-trade_net_return"]
        valid = (dataframe["do_predict"] == 1) & pred.notna() & np.isfinite(pred)
        valid &= (dataframe["volume"] > 0) & (dataframe["close"] > 0)
        valid &= pred > self.min_predicted_net_after_cost
        long_ok = valid & dataframe["long_setup"].fillna(False)
        short_ok = valid & dataframe["short_setup"].fillna(False)
        dataframe.loc[long_ok, "enter_long"] = 1
        dataframe.loc[short_ok, "enter_short"] = 1
        dataframe.loc[long_ok, "enter_tag"] = "m2r_after_cost_long"
        dataframe.loc[short_ok, "enter_tag"] = "m2r_after_cost_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exits remain fixed/trend-only until a fully aligned 12-candle
        # horizon execution comparison is independently tested.
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe.loc[dataframe["ema_fast"] < dataframe["ema_slow"], "exit_long"] = 1
        dataframe.loc[dataframe["ema_fast"] > dataframe["ema_slow"], "exit_short"] = 1
        return dataframe
