"""Nbot V6 FIVE-action FreqAI RL research strategy, BACKTEST ONLY.

Follows FreqAI's official neutral/enter/exit action mapping; never use a
non-research config, or promote RL policy weights to paper or live.
"""
from __future__ import annotations

from pandas import DataFrame
import numpy as np

from NbotV6 import NbotV6
from NbotV6LibraryResearch import _NbotV6ResearchLibraryBase


class NbotV6RLResearch(NbotV6):
    @property
    def protections(self):
        # These operate in native historical Freqtrade evaluation, not the
        # simplified internal RL training environment.
        return _NbotV6ResearchLibraryBase.protections.fget(self)

    def _rl_safe(self) -> bool:
        c = self.config
        e = c.get("exchange", {})
        mode = c.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        f = c.get("freqai", {})
        return bool(
            mode == "backtest"
            and c.get("dry_run") is True
            and c.get("nbot_v6_rl_research_only") is True
            and c.get("nbot_live_mode") is False
            and c.get("nbot_paper_research_mode") is False
            and c.get("max_open_trades") == 1
            and c.get("stake_amount") == 1000
            and c.get("force_entry_enable") is False
            and c.get("api_server", {}).get("enabled") is False
            and c.get("telegram", {}).get("enabled") is False
            and not e.get("key") and not e.get("secret")
            and f.get("enabled") is True
            and str(f.get("identifier", "")).startswith("nbot-v6-rl-research-")
            and f.get("continual_learning") is False
            and f.get("rl_config", {}).get("model_type") == "PPO"
        )

    def bot_start(self, **kwargs):
        if not self._rl_safe():
            raise RuntimeError("NBOT_V6_RL_BACKTEST_ONLY_NEVER_PAPER_OR_LIVE")

    def confirm_trade_entry(self, pair, order_type, amount, rate,
                            time_in_force, current_time, entry_tag, side, **kwargs):
        return self._rl_safe()

    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        for p in ("open", "high", "low", "close"):
            dataframe["%-raw_" + p] = dataframe[p]
        dataframe["%-rl_momentum_12"] = dataframe["close"].pct_change(12)
        dataframe["%-rl_volatility_24"] = dataframe["close"].pct_change().rolling(24, min_periods=24).std()
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        dataframe["&-action"] = 0
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        actions = dataframe["&-action"]
        valid = (dataframe["do_predict"] == 1) & actions.notna() & np.isfinite(actions)
        valid &= (dataframe["volume"] > 0) & (dataframe["close"] > 0)
        long = valid & (actions == 1)
        short = valid & (actions == 3)
        dataframe.loc[long, "enter_long"] = 1
        dataframe.loc[short, "enter_short"] = 1
        dataframe.loc[long, "enter_tag"] = "v6_rl_long"
        dataframe.loc[short, "enter_tag"] = "v6_rl_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        actions = dataframe["&-action"]
        valid = (dataframe["do_predict"] == 1) & actions.notna() & np.isfinite(actions)
        dataframe.loc[valid & (actions == 2), "exit_long"] = 1
        dataframe.loc[valid & (actions == 4), "exit_short"] = 1
        return dataframe
