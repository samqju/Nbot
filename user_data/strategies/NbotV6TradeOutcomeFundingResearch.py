"""Opt-in V6 M2R offline experiment with actual historical funding event labels.

No live/paper, no exchange credentials, no promotion: inherits original
after-cost challenger setup/entry/time-exit behavior, but replaces its
constant 1bp funding target with a signed per-event estimate from Binance
funding-rate history and last COMPLETED hourly mark close proxy.

Never mistake this for observed spreads/order fills or an approved model.
"""
from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd
from pandas import DataFrame

from NbotV6TradeOutcomeResearch import NbotV6TradeOutcomeResearch
from nbot_trade_outcome import CostPolicy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from m2r_event_cost_labels import FundingSchedule, event_funding_training_labels


class NbotV6TradeOutcomeFundingResearch(NbotV6TradeOutcomeResearch):
    def set_freqai_targets(self, dataframe:DataFrame, **kwargs)->DataFrame:
        config=self.config
        mode=config.get("runmode")
        mode=str(getattr(mode,"value",mode)).lower()
        if not (
            mode=="backtest"
            and config.get("nbot_m2r_research_only") is True
            and config.get("nbot_m2r_event_funding_labels") is True
            and config.get("dry_run") is True
            and config.get("nbot_live_mode") is not True
            and config.get("nbot_paper_research_mode") is not True
            and not config.get("exchange",{}).get("key")
            and not config.get("exchange",{}).get("secret")
        ):
            raise RuntimeError("V6_FUNDING_TARGET_ONLY_IN_OFFLINE_HISTORICAL_RESEARCH")
        metadata=kwargs.get("metadata") or {}
        pair=metadata.get("pair")
        if pair not in config.get("exchange",{}).get("pair_whitelist",[]):
            raise RuntimeError("V6_FUNDING_TARGET_UNKNOWN_PAIR")
        token=pair.replace("/","_").replace(":","_")
        directory=Path(config.get("datadir",""))/"futures"
        funding_file=directory/(token+"-1h-funding_rate.feather")
        mark_file=directory/(token+"-1h-mark.feather")
        if not funding_file.is_file() or not mark_file.is_file():
            raise RuntimeError("V6_FUNDING_AND_MARK_HISTORY_REQUIRED")
        cache=getattr(self,"_nbot_funding_label_schedules",None)
        if cache is None:
            cache={}
            self._nbot_funding_label_schedules=cache
        if pair not in cache:
            funding=pd.read_feather(funding_file)
            mark=pd.read_feather(mark_file)
            funding["date"]=pd.to_datetime(funding["date"],utc=True)
            mark["date"]=pd.to_datetime(mark["date"],utc=True)
            # Any event with no prior COMPLETED hourly mark is discarded ONLY
            # from the global cache start; the complete training period must
            # still be wholly covered by event history (checked below).
            first_valid_mark=mark.date.iloc[0]+pd.Timedelta(hours=1)
            funding=funding.loc[funding.date>=first_valid_mark].reset_index(drop=True)
            schedule=FundingSchedule.from_candles(funding,mark)
            cache[pair]=(schedule, funding.date.iloc[0],funding.date.iloc[-1])
        schedule,first,last=cache[pair]
        date=pd.to_datetime(dataframe["date"],utc=True)
        horizon=int(self.freqai_info["feature_parameters"]["label_period_candles"])
        if horizon!=12:
            raise RuntimeError("V6_FUNDING_TARGET_12_CANDLE_HORIZON_REQUIRED")
        # If any *required* event in the train/outcome horizon has not been
        # downloaded, prohibit silently treating absence of events as zero.
        # Funding is episodic; exact event-time prediction is not presumed.
        if not (date.iloc[0] >= first and date.iloc[-1] <= last+pd.Timedelta(hours=8)):
            raise RuntimeError("V6_FUNDING_HISTORY_DOES_NOT_COVER_LABEL_WINDOW")
        return event_funding_training_labels(dataframe,schedule,CostPolicy(horizon=horizon))
