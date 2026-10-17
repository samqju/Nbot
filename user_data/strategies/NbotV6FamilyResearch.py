"""Breakout-only vs pullback-only after-cost LightGBM research controls.

Uses identical Freqtrade max-1 position, 2% stop / 5% target, 60-min
time exit and cost assumptions as NbotV6TradeOutcomeResearch. Each model
learns its own family's hypothetical trade labels (long and short),
including setups skipped by the baseline bot. HISTORICAL BACKTEST ONLY.
"""
from __future__ import annotations
import numpy as np
from pandas import DataFrame

from NbotV6TradeOutcomeResearch import NbotV6TradeOutcomeResearch
from nbot_trade_outcome import CostPolicy, setups, training_labels_for_family


class FamilyResearchMixin:
    family = ""

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        horizon = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        return training_labels_for_family(dataframe, self.family, CostPolicy(horizon=horizon))

    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        frame = super().feature_engineering_standard(dataframe, **kwargs)
        family_flags = setups(dataframe)
        # As-of setup identity; neither feature depends on future outcome.
        frame["%-family_long_signal"] = family_flags[self.family+"_long"].astype(float)
        frame["%-family_short_signal"] = family_flags[self.family+"_short"].astype(float)
        return frame

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        prediction = dataframe["&-trade_net_return"]
        valid = (dataframe["do_predict"] == 1) & prediction.notna() & np.isfinite(prediction)
        valid &= (dataframe["close"] > 0) & (dataframe["volume"] > 0)
        valid &= prediction > self.min_predicted_net_after_cost
        flags = setups(dataframe)
        long_ok = valid & flags[self.family+"_long"]
        short_ok = valid & flags[self.family+"_short"]
        dataframe.loc[long_ok, "enter_long"] = 1
        dataframe.loc[short_ok, "enter_short"] = 1
        dataframe.loc[long_ok, "enter_tag"] = "m2r_"+self.family+"_long"
        dataframe.loc[short_ok, "enter_tag"] = "m2r_"+self.family+"_short"
        return dataframe


class NbotV6BreakoutResearch(FamilyResearchMixin, NbotV6TradeOutcomeResearch):
    family = "breakout"


class NbotV6PullbackResearch(FamilyResearchMixin, NbotV6TradeOutcomeResearch):
    family = "pullback"
