#!/usr/bin/env python3
"""Independent verify persisted historical M5A proxy results + paired day-block uncertainty.

Historical candidate panel sampled from Oct19 surviving symbols; no market
microstructure/model readiness. This is DIAGNOSTIC not a real Freqtrade backtest.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,random
from pathlib import Path
from statistics import mean
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import m5a_historical_ohlcv_proxy_replay as study

def require(x,why):
    if not x:raise RuntimeError(why)
def perc(v,p):
    return sorted(v)[min(len(v)-1,max(0,round(p*(len(v)-1))))]
def event_win(row,policy,target):
    return int(row["comparisons"][policy][target]["status"]=="TARGET_FIRST")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--replay",type=Path,required=True)
    a=p.parse_args()
    doc=json.loads(a.replay.read_text())
    require(doc["schema"]=="m5a-historical-8h-ohlcv-proxy-replay-1"
            and doc["NEVER_PROVES_ACTUAL_DYNAMIC_25_VS_FIXED_PROFIT"] is True,
            "NOT_AN_HONEST_HISTORICAL_PROXY_REPORT")
    hist,manifest=study.load_history(a.data)
    require(len(hist)==75 and manifest["successful"]==75 and manifest["failed"]==0,
            "INCOMPLETE_75_MARKET_SHA_VERIFIED_CANDLE_PANEL")
    regenerated=study.replay(hist,manifest["initial_original_25"],study.ms(study.START),study.ms(study.END))
    require(regenerated==doc["records"],"REPLAY_NOT_REPRODUCIBLE")
    require(len(regenerated)==234,"REVIEW_COUNT_CHANGED")
    original=set(manifest["initial_original_25"])
    differences={}
    days=collections.defaultdict(list)
    for row in regenerated:
        days[row["asof_utc"][:10]].append(row)
        for policy in ("fixed25","liquidity25","quality25"):
            obj=row["comparisons"][policy]
            require(len(obj["symbols"])==25 and len(set(obj["symbols"]))==25,
                    "NOT_25_UNIQUE")
            require("BTCUSDT" in obj["symbols"] and obj["turnover"]<=10,
                    "INVALID_8H_ROTATION_OR_BTC_PIN")
            require(len(obj["symbols"])==obj["eligible_count"],
                    "SOME_SHADOW_CANDIDATE_MISSING_ASOF_CANDLES")
    days=list(days.values())
    seed=20261019
    for challenger in ("liquidity25","quality25"):
        all_selected={s for row in regenerated for s in row["comparisons"][challenger]["symbols"]}
        unique_extras=all_selected-original
        stats={"unique_selected_symbols_over_period":len(all_selected),
               "new_symbols_outside_original25":len(unique_extras),
               "new_symbols":sorted(unique_extras),
               "total_coin_replacements":sum(row["comparisons"][challenger]["turnover"] for row in regenerated)}
        for target in ("target2","target3"):
            observed=(sum(event_win(row,challenger,target)-event_win(row,"fixed25",target)
                         for row in regenerated)/len(regenerated))
            draws=[]
            rng=random.Random(seed+(1 if target=="target2" else 2)+(0 if challenger=="quality25" else 100))
            for i in range(2500):
                sample=[rng.choice(days) for _ in days]
                selected=[r for day in sample for r in day]
                draws.append(sum(event_win(r,challenger,target)-event_win(r,"fixed25",target)
                                 for r in selected)/len(selected))
            stats[target+"_paired_win_rate_delta_vs_fixed"]={
                "observed_difference_percentage_points":round(observed*100,3),
                "exploratory_daily_block_bootstrap_95pct_pp":[
                    round(100*perc(draws,.025),3),round(100*perc(draws,.975),3)],
                "method":"2500 resampled UTC day blocks; overlapping 24h opportunity labels; NOT inferential future proof"}
        differences[challenger]=stats
    result={"schema":"m5a-historical-ohlcv-proxy-independent-provenance-1",
            "75_historical_candle_files_sha256_verified":True,
            "historical_download_manifest_sha256":hashlib.sha256((a.data/"historical-download-manifest.json").read_bytes()).hexdigest(),
            "replay_sha256":hashlib.sha256(a.replay.read_bytes()).hexdigest(),
            "234_eight_hour_asof_reviews_deterministically_reproduced":True,
            "all_25_slot_and_btc_pin_checks_passed":True,
            "unique_utc_days":len(days),
            "comparisons":differences,
            "future_listing_and_orderbook_survivorship_uncontrolled":True,
            "new_unseen_period_trade_alpha_not_established":True,
            "one_real_native_freqtrade_portfolio_executed":False,
            "no_order_no_v5_update":True}
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":
    main()
