"""Eight independent FreqAI LightGBM after-cost candidate-model strategies.

These are NOT aliases for the existing breakout/pullback candidates: each
class has an independent market signal family and its own supervised target.
Run one native backtest per family, with a distinct freqai.identifier and
independent train/validation/test chronology. All future candles enter only
the &-trade_net_return label and are embargoed by the existing research-only
PurgedLightGBMRegressor; no future trade outcomes become inference features.
Never use a generic FreqAI model identifier across different families.
"""
from __future__ import annotations

import numpy as np
from pandas import DataFrame

from NbotV6TradeOutcomeResearch import NbotV6TradeOutcomeResearch
from NbotV6LibraryResearch import FAMILIES, library_indicators, library_signals, _NbotV6ResearchLibraryBase
from nbot_trade_outcome import CostPolicy, outcome


class _NbotV6LibraryLightGBMResearchBase(NbotV6TradeOutcomeResearch):
    family = ""

    @property
    def protections(self):
        # Same native trade-ledger drawdown/stoploss protection as no-ML peers.
        return _NbotV6ResearchLibraryBase.protections.fget(self)

    def _assert_family_research(self):
        cfg = self.config
        if self.family not in FAMILIES:
            raise RuntimeError("UNKNOWN_LIBRARY_ML_FAMILY")
        if cfg.get("nbot_v6_library_ml_research_only") is not True:
            raise RuntimeError("NBOT_V6_LIBRARY_ML_OPT_IN_REQUIRED")
        freqai = cfg.get("freqai", {})
        if not freqai.get("enabled"):
            raise RuntimeError("LIBRARY_ML_REQUIRES_FREQAI")
        identifier = str(freqai.get("identifier", ""))
        if not identifier.startswith("nbot-v6-library-" + self.family + "-"):
            raise RuntimeError("LIBRARY_ML_REQUIRES_ISOLATED_FAMILY_MODEL_ID")
        if cfg.get("nbot_m2r_purge_internal") is not True:
            raise RuntimeError("LIBRARY_ML_REQUIRES_STRICT_LABEL_EMBARGO")
        if freqai.get("feature_parameters", {}).get("label_period_candles") != 12:
            raise RuntimeError("LIBRARY_ML_REQUIRES_12_CANDLE_HORIZON")

    def bot_start(self, **kwargs):
        self._assert_family_research()
        return super().bot_start(**kwargs)

    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        # Existing native/LightGBM %-features, plus this family's own current
        # signal identity. Indicator values are causal and do NOT enter target.
        frame = super().feature_engineering_standard(dataframe, **kwargs)
        flags = library_signals(library_indicators(dataframe), self.family)
        frame["%-library_long"] = flags["long"].astype(float)
        frame["%-library_short"] = flags["short"].astype(float)
        return frame

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        self._assert_family_research()
        # Same conservative research reward horizon/cost proxy as the existing
        # aftercost candidate, NOT proof that fills really happen at this price.
        costs = CostPolicy(horizon=12)
        flags = library_signals(library_indicators(dataframe), self.family)
        labels = np.full(len(dataframe), np.nan, dtype=float)
        for i in range(len(dataframe) - costs.horizon):
            side = 1 if bool(flags["long"].iloc[i]) else (-1 if bool(flags["short"].iloc[i]) else 0)
            if side == 0:
                continue
            sample = outcome(dataframe, i, side, costs)
            if sample is not None:
                labels[i] = sample["net_return"]
        result = dataframe.copy()
        result["&-trade_net_return"] = labels
        return result

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        self._assert_family_research()
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        flags = library_signals(library_indicators(dataframe), self.family)
        pred = dataframe["&-trade_net_return"]
        valid = (dataframe["do_predict"] == 1) & pred.notna() & np.isfinite(pred)
        valid &= (dataframe["volume"] > 0) & (dataframe["close"] > 0)
        valid &= pred > self.min_predicted_net_after_cost
        long = valid & flags["long"]
        short = valid & flags["short"]
        dataframe.loc[long, "enter_long"] = 1
        dataframe.loc[short, "enter_short"] = 1
        dataframe.loc[long, "enter_tag"] = "library_lgbm_" + self.family + "_long"
        dataframe.loc[short, "enter_tag"] = "library_lgbm_" + self.family + "_short"
        return dataframe


class NbotV6EmaCrossLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "ema_cross"

class NbotV6DonchianLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "donchian_breakout"

class NbotV6BollingerLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "bollinger_reversion"

class NbotV6RsiLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "rsi_reversion"

class NbotV6MacdLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "macd_momentum"

class NbotV6StochasticLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "stochastic_reversal"

class NbotV6AtrBreakoutLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "atr_breakout"

class NbotV6VolumeTrendLightGBMResearch(_NbotV6LibraryLightGBMResearchBase):
    family = "volume_trend"
