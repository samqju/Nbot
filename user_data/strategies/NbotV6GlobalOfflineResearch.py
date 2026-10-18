"""Research-only Freqtrade native adapter for globally ranked 25x8 entries.

The offline LightGBM research generator produces at most one selected
pair/family/side per 5m candle. This adapter executes THAT trade in ONE
native Freqtrade 25-market portfolio with real built-in stop/ROI/funding/
fee mechanisms, rather than stitching together separate strategy profits.
Never usable in dry-running bot or live mode: backtest only.
"""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy

FAMILIES=(
    "ema_cross","donchian_breakout","bollinger_reversion","rsi_reversion",
    "macd_momentum","stochastic_reversal","atr_breakout","volume_trend"
)

class NbotV6GlobalOfflineResearch(IStrategy):
    INTERFACE_VERSION=3
    timeframe="5m"
    can_short=True
    startup_candle_count=250
    process_only_new_candles=True
    stoploss=-0.02
    minimal_roi={"0":0.05}
    use_exit_signal=True
    trailing_stop=False
    _cache=None

    def _guard(self):
        c=self.config
        mode=str(getattr(c.get("runmode"),"value",c.get("runmode"))).lower()
        exch=c.get("exchange",{})
        allow=(
            mode=="backtest"
            and c.get("nbot_v6_global_research_only") is True
            and c.get("nbot_live_mode") is False
            and c.get("nbot_paper_research_mode") is False
            and c.get("dry_run") is True
            and c.get("max_open_trades")==1
            and c.get("stake_amount")==1000
            and c.get("trading_mode")=="futures"
            and c.get("margin_mode")=="isolated"
            and c.get("force_entry_enable") is False
            and exch.get("key","")=="" and exch.get("secret","")==""
            and not c.get("api_server",{}).get("enabled",False)
            and not c.get("telegram",{}).get("enabled",False)
            and c.get("freqai",{}).get("enabled") is False)
        if not allow:raise RuntimeError("GLOBAL_V6_NATIVE_BACKTEST_ONLY_NO_ORDERS")

    def bot_start(self, **kwargs):
        self._guard()
        self._read()

    def _read(self):
        if self._cache is not None:return self._cache
        self._guard()
        name=self.config.get("nbot_v6_global_decisions_csv")
        if not isinstance(name,str) or not name.startswith("/results/"):
            raise RuntimeError("ONLY_ISOLATED_RESULTS_INPUT_ACCEPTED")
        path=Path(name)
        if not path.is_file():raise RuntimeError("MISSING_CANDIDATE_FORECAST_FILE")
        rows=pd.read_csv(path)
        required={"date","pair","family","side"}
        if not required.issubset(rows.columns):
            raise RuntimeError("DECISION_SCHEMA_INCOMPLETE")
        if rows.date.duplicated().any():raise RuntimeError("MULTIPLE_SELECTED_COIN_PER_CANDLE")
        if not rows.family.isin(FAMILIES).all():raise RuntimeError("UNKNOWN_STRATEGY_FAMILY")
        if not rows.side.isin(("long","short")).all():raise RuntimeError("UNKNOWN_SIDE")
        allowed=self.config["exchange"]["pair_whitelist"]
        if len(set(allowed))!=25 or len(allowed)!=25:
            raise RuntimeError("REQUIRE_EXACT_25_PAIR_UNIVERSE")
        if not rows.pair.isin(allowed).all():raise RuntimeError("UNAPPROVED_COIN")
        rows["date"]=pd.to_datetime(rows.date,utc=True)
        if (rows.date.dt.minute%5!=0).any() or (rows.date.dt.second!=0).any():
            raise RuntimeError("UNSYNCHRONIZED_FIVE_MINUTE_CANDLES")
        self._cache=rows
        return rows

    def populate_indicators(self,dataframe:DataFrame,metadata:dict)->DataFrame:
        return dataframe

    def populate_entry_trend(self,dataframe:DataFrame,metadata:dict)->DataFrame:
        self._guard()
        rows=self._read()
        pair=metadata["pair"]
        dataframe["enter_long"]=0
        dataframe["enter_short"]=0
        sub=rows.loc[rows.pair.eq(pair),["date","side","family"]]
        if sub.empty:return dataframe
        decision_dates=pd.to_datetime(dataframe.date,utc=True)
        for side in ("long","short"):
            found=sub[sub.side.eq(side)]
            positions=decision_dates.isin(found.date)
            dataframe.loc[positions,"enter_"+side]=1
            tags=dict(zip(found.date,found.family))
            dataframe.loc[positions,"enter_tag"]=[
                "global_"+tags[t]+"_"+side for t in decision_dates[positions]]
        return dataframe

    def populate_exit_trend(self,dataframe:DataFrame,metadata:dict)->DataFrame:
        dataframe["exit_long"]=0
        dataframe["exit_short"]=0
        return dataframe

    def confirm_trade_entry(self,pair,order_type,amount,rate,
                            time_in_force,current_time,entry_tag,side,**kwargs):
        self._guard()
        return entry_tag.startswith("global_")

    def leverage(self,pair,current_time,current_rate,proposed_leverage,
                 max_leverage,entry_tag,side,**kwargs)->float:
        return 1.0

    def custom_exit(self,pair,trade,current_time,current_rate,current_profit,**kwargs):
        if current_time>=trade.open_date_utc+timedelta(minutes=60):
            return "global_60m_limit"
        return None

class NbotV6GlobalTrailingOfflineResearch(NbotV6GlobalOfflineResearch):
    # Direct fixed-policy A/B. Does not claim +1% guaranteed net realized profit.
    trailing_stop=True
    trailing_stop_positive=.01
    trailing_stop_positive_offset=.02
    trailing_only_offset_is_reached=True
