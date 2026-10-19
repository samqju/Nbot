"""Point-in-time 25-market universe-selection diagnostics; no market data downloads.

Does NOT represent a full historical 25-of-entire-Binance-USDT-M comparison:
we have only the fixed 25 histories, no historical exchange-wide delisted
contracts or order-book snapshots. Never call this an economically executable
pairlist. Input is read-only public historical 1h OHLCV and funding rate data.

Exactly 8h decisions and 24h volume liquidity ranks are determined without
future candles. Follow-up 8h market volatility is ONLY an evaluation label,
never part of eligibility or ranking.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd


def load_pair(base:Path,pair:str):
    prefix=pair.replace("/","_").replace(":","_")
    path=base/f"{prefix}-1h-futures.feather"
    funding=base/f"{prefix}-1h-funding_rate.feather"
    if not (path.is_file() and funding.is_file()):
        raise RuntimeError(f"PAIR_HISTORICAL_FEEDS_MISSING {pair}")
    data=pd.read_feather(path)
    data["date"]=pd.to_datetime(data["date"],utc=True)
    if not data["date"].is_monotonic_increasing or data["date"].duplicated().any():
        raise RuntimeError(f"PAST_DATA_INVALID {pair}")
    data=data.set_index("date")
    assert all(x in data.columns for x in ["open","high","low","close","volume"])
    data["turnover_hourly_proxy_usdt"]=data.close*data.volume
    if not ((data.close>0).all() and (data.volume>=0).all()):
        raise RuntimeError(f"NONPOSITIVE_PRICE_OR_VOLUME {pair}")
    data["past_24h_quote_volume_proxy_usdt"]=data.turnover_hourly_proxy_usdt.rolling(24,min_periods=24).sum()
    data["past_7d_quote_volume_proxy_usdt"]=data.turnover_hourly_proxy_usdt.rolling(168,min_periods=168).sum()
    data["past_24h_momentum"]=data.close.pct_change(24)
    data["past_7d_hourly_log_return_std"]=np.log(data.close).diff().rolling(168,min_periods=168).std()
    events=pd.read_feather(funding)
    events["date"]=pd.to_datetime(events["date"],utc=True)
    if not events.date.is_monotonic_increasing or events.date.duplicated().any():
        raise RuntimeError(f"FUNDING_SERIES_INVALID {pair}")
    events=events.set_index("date")["funding_rate"]
    return data,events


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",required=True,type=Path)
    ap.add_argument("--config",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    cfg=json.loads(args.config.read_text())
    assert cfg["dry_run"] and not cfg["exchange"]["key"] and not cfg["exchange"]["secret"]
    pairs=cfg["exchange"]["pair_whitelist"]
    if len(pairs)!=25 or len(set(pairs))!=25 or "BTC/USDT:USDT" not in pairs:
        raise RuntimeError("REQUIRES_FIXED_ORIGINAL_25_AND_BTC_CONTEXT")
    feeds={pair:load_pair(args.data,pair) for pair in pairs}
    selected_before=None
    result=[]
    failures={}
    reviews=pd.date_range("2026-02-15T00:00:00Z",
                          "2026-09-30T16:00:00Z",freq="8h",tz="UTC")
    cutoff=reviews[0]
    for date in reviews:
        asof=date-pd.Timedelta(hours=1)
        eligible=[]
        for pair,(feed,fund) in feeds.items():
            if asof not in feed.index:
                failures["no_current_completed_hour"]=failures.get("no_current_completed_hour",0)+1
                continue
            row=feed.loc[asof]
            vol=float(row.past_24h_quote_volume_proxy_usdt)
            vol7=float(row.past_7d_quote_volume_proxy_usdt)
            hour_std=float(row.past_7d_hourly_log_return_std)
            if not (math.isfinite(vol) and vol>0 and math.isfinite(vol7) and vol7>0
                    and math.isfinite(hour_std) and hour_std>0):
                failures["insufficient_asof_liquidity_history"]=failures.get("insufficient_asof_liquidity_history",0)+1
                continue
            # The ONLY ranking is past 24-hour quote-volume proxy, with BTC
            # permanently pinned. No future PnL, forward return, order-book
            # spread or October 2026 volume determines rank.
            future=feed.loc[date:date+pd.Timedelta(hours=7)]
            if len(future)!=8 or (future.index[-1]!=date+pd.Timedelta(hours=7)):
                failures["incomplete_future_label"]=failures.get("incomplete_future_label",0)+1
                continue
            future_return=float(future.close.iloc[-1]/float(row.close)-1)
            future_range=float((future.high.max()-future.low.min())/float(row.close))
            # No funding event can be read at date or after for as-of ranking.
            trailing=fund.loc[(fund.index>=date-pd.Timedelta(hours=24))&(fund.index<date)]
            avg_abs_funding=float(trailing.abs().sum())
            eligible.append({
                "pair":pair,
                "past_24h_quote_volume_proxy_usdt":vol,
                "past_7d_quote_volume_proxy_usdt":vol7,
                "past_7d_hourly_log_return_std":hour_std,
                "past_24h_momentum":float(row.past_24h_momentum),
                "past_24h_abs_funding_rate_sum":avg_abs_funding,
                "next_8h_abs_return_evaluation_only":abs(future_return),
                "next_8h_high_low_range_evaluation_only":future_range,
            })
        # No off-universe candidates; this is 25 historical symbol descriptions
        # not the complete Binance USDT-M exchange over these months.
        ranked=sorted(eligible,key=lambda e:(-e["past_24h_quote_volume_proxy_usdt"],e["pair"]))
        if len(ranked)!=25:
            failures["not_all_25_research_pairs_ready"]=failures.get("not_all_25_research_pairs_ready",0)+1
        btc=next((r for r in ranked if r["pair"]=="BTC/USDT:USDT"),None)
        top10=([btc] if btc else [])+[r for r in ranked if r["pair"]!="BTC/USDT:USDT"][:9]
        names={r["pair"] for r in top10}
        bottom10=[r for r in ranked if r["pair"] not in names][-10:]
        def mean_field(pool,k):
            return round(float(np.mean([r[k] for r in pool])),10) if pool else None
        changes=None if selected_before is None else len(names.symmetric_difference(selected_before))//2
        result.append({
            "review_utc":date.isoformat(),
            "last_completed_candle_utc":asof.isoformat(),
            "eligible_from_existing_fixed_25":len(ranked),
            "top10_pinned_btc_liquidity_rank":[r["pair"] for r in top10],
            "bottom10_asof_liquidity_rank":[r["pair"] for r in bottom10],
            "top10_members_replaced_since_prior_review":changes,
            "top10_avg_past24h_quote_volume_usdt":mean_field(top10,"past_24h_quote_volume_proxy_usdt"),
            "bottom10_avg_past24h_quote_volume_usdt":mean_field(bottom10,"past_24h_quote_volume_proxy_usdt"),
            "top10_next8h_abs_return_DIAGNOSTIC":mean_field(top10,"next_8h_abs_return_evaluation_only"),
            "bottom10_next8h_abs_return_DIAGNOSTIC":mean_field(bottom10,"next_8h_abs_return_evaluation_only"),
            "top10_next8h_range_DIAGNOSTIC":mean_field(top10,"next_8h_high_low_range_evaluation_only"),
            "bottom10_next8h_range_DIAGNOSTIC":mean_field(bottom10,"next_8h_high_low_range_evaluation_only"),
            "fixed25_vs_dynamic25_membership_can_differ":False if len(ranked)==25 else None,
        })
        selected_before=names
    def av(k,which):
        v=[x[k] for x in result if x[k] is not None]
        return round(float(np.mean(v)),8) if v else None
    out={
        "experiment":"HISTORICAL_CAUSAL_LIQUIDITY_ONLY_RANKING_DIAGNOSTIC",
        "release":"NO-GO",
        "raw_input_is_only_original_25_october_configured_markets":True,
        "historical_delisted_perpetuals_and_other_binance_contracts_available":False,
        "historical_bid_ask_spreads_or_depth_observed":False,
        "asof_market_quote_volume_is_candle_close_times_base_volume_proxy_not_exchange_observed_quote_trade_fills":True,
        "selection_at_each_timestamp_uses_ONLY_completed_past_candles":True,
        "next8h_absolute_returns_and_ranges_are_evaluation_only_not_trade_profits":True,
        "full_historical_25_of_entire_exchange_rotation_proven":False,
        "fixed25_to_top25_using_only_25_candidates_has_identical_membership_by_construction":True,
        "real_strategy_pnl_comparison_completed":False,
        "first_review_utc":reviews[0].isoformat(),
        "last_review_utc":reviews[-1].isoformat(),
        "eight_hour_research_review_count":len(result),
        "all_25_asof_data_ready_fraction":round(sum(x["eligible_from_existing_fixed_25"]==25 for x in result)/len(result),6),
        "observed_source_quality_gates":failures,
        "avg_top10_past24h_quote_volume_proxy_usdt":av("top10_avg_past24h_quote_volume_usdt","top"),
        "avg_bottom10_past24h_quote_volume_proxy_usdt":av("bottom10_avg_past24h_quote_volume_usdt","bottom"),
        "avg_top10_next8h_abs_return_evaluation_only":av("top10_next8h_abs_return_DIAGNOSTIC","top"),
        "avg_bottom10_next8h_abs_return_evaluation_only":av("bottom10_next8h_abs_return_DIAGNOSTIC","bottom"),
        "avg_top10_next8h_range_evaluation_only":av("top10_next8h_range_DIAGNOSTIC","top"),
        "avg_bottom10_next8h_range_evaluation_only":av("bottom10_next8h_range_DIAGNOSTIC","bottom"),
        "avg_top10_members_replaced_per_review":av("top10_members_replaced_since_prior_review","top"),
        "review_samples":result,
    }
    args.output.write_text(json.dumps(out,indent=2)+"\n")
    print("ASOF_REVIEW_COMPLETED",out["eight_hour_research_review_count"],
          "all25_ready_ratio",out["all_25_asof_data_ready_fraction"],
          "top10_future_abs",out["avg_top10_next8h_abs_return_evaluation_only"],
          "bottom10_future_abs",out["avg_bottom10_next8h_abs_return_evaluation_only"],
          "BROAD_MARKET_COUNTERFACTUAL_UNAVAILABLE",flush=True)


if __name__=="__main__":
    main()
