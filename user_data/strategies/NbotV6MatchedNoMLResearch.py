"""Matched-exit NO-ML research controls for after-cost FreqAI tests.

The original M2 no-ML strategy uses EMA exit signals. These separate
test-only controls use the same 2% stop, 5% ROI target and 60-minute
timeout as the new trade-outcome AI, to isolate the value of *filtering*
trading setups from the value of changing exit rules. No FreqAI,
no exchange credentials, and NO persistent paper or live use.
"""
from __future__ import annotations
from datetime import timedelta
from pandas import DataFrame
from NbotV6NoML import NbotV6NoML
from nbot_trade_outcome import setups


class MatchedResearchMixin:
    family = "combined"

    def bot_start(self, **kwargs) -> None:
        mode = self.config.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        ex = self.config.get("exchange",{})
        if not (
            mode=="backtest"
            and self.config.get("nbot_m2r_research_only") is True
            and self.config.get("dry_run") is True
            and type(self.config.get("max_open_trades")) is int
            and self.config.get("max_open_trades")==1
            and not ex.get("key")
            and not ex.get("secret")
            and self.config.get("nbot_live_mode") is not True
            and self.config.get("nbot_paper_research_mode") is not True
            and self.config.get("api_server",{}).get("enabled") is False
            and self.config.get("telegram",{}).get("enabled") is False
        ):
            raise RuntimeError("NBOT_M2R_MATCHED_HISTORICAL_ONLY")

    def confirm_trade_entry(self,pair,order_type,amount,rate,time_in_force,
                            current_time,entry_tag,side,**kwargs)->bool:
        m=self.config.get("runmode")
        m=str(getattr(m,"value",m)).lower()
        ex=self.config.get("exchange",{})
        return bool(m=="backtest"
                    and self.config.get("nbot_m2r_research_only") is True
                    and self.config.get("dry_run") is True
                    and self.config.get("max_open_trades")==1
                    and not ex.get("key") and not ex.get("secret"))

    def populate_entry_trend(self, dataframe:DataFrame, metadata:dict)->DataFrame:
        dataframe["enter_long"]=0
        dataframe["enter_short"]=0
        flags=setups(dataframe)
        kinds=(
            ("breakout_long","breakout_short"),
            ("pullback_long","pullback_short")
        )
        if self.family=="breakout": kinds=kinds[:1]
        elif self.family=="pullback": kinds=kinds[1:]
        elif self.family!="combined": raise RuntimeError("INVALID_FAMILY")
        long_mask=flags[kinds[0][0]]
        short_mask=flags[kinds[0][1]]
        for ln,sh in kinds[1:]:
            long_mask=long_mask|flags[ln]
            short_mask=short_mask|flags[sh]
        dataframe.loc[long_mask,"enter_long"]=1
        dataframe.loc[short_mask,"enter_short"]=1
        dataframe.loc[long_mask,"enter_tag"]="matched_"+self.family+"_long"
        dataframe.loc[short_mask,"enter_tag"]="matched_"+self.family+"_short"
        return dataframe

    def populate_exit_trend(self,dataframe:DataFrame,metadata:dict)->DataFrame:
        dataframe["exit_long"]=0
        dataframe["exit_short"]=0
        return dataframe

    def custom_exit(self,pair,trade,current_time,current_rate,current_profit,**kwargs):
        if current_time>=trade.open_date_utc+timedelta(minutes=60):
            return "m2r_matched_60minute_exit"
        return None


class NbotV6MatchedNoMLResearch(MatchedResearchMixin,NbotV6NoML):
    family="combined"


class NbotV6MatchedBreakoutNoMLResearch(MatchedResearchMixin,NbotV6NoML):
    family="breakout"


class NbotV6MatchedPullbackNoMLResearch(MatchedResearchMixin,NbotV6NoML):
    family="pullback"
