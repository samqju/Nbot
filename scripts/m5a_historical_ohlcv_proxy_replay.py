#!/usr/bin/env python3
"""Historical 8h 25-of-75 M5A *OHLCV PROXY* comparison (NOT native P&L).

Only hourly CLOSED candles available to the selector. Selection score is a
transparent 24h quote-turnover + observed 24h candle-range stability proxy.
This is NOT the actual M5A (which requires historical spread, depth, funding,
listing/contract status and model readiness). Candidate symbol sample was
chosen from OCT 19 observable markets: serious historical survivorship bias.

Researcher-predeclared probe: for the strongest as-of absolute 8h momentum
within each of three universes, evaluate +2% or +3% target FIRST against
-2% protective stop for the following 24h, with stop-first if both touch
in the same hourly candle. Report equal-time/one-per-8h hypothetical
opportunities only; these OVERLAP in forward time and are NOT a single
capital-constrained portfolio. Do not claim profitability or execution.
"""
from __future__ import annotations
from bisect import bisect_left
from datetime import datetime,timezone
from math import isfinite,log10
import argparse
import collections
import hashlib
import json
from pathlib import Path
from statistics import mean,median

HOUR=3_600_000
DAY=24*HOUR
REVIEW=8*HOUR
START="2026-08-01T00:00:00+00:00"
END="2026-10-18T00:00:00+00:00"
MIN_HISTORY_HOURS=45*24
MIN_QUOTE_TURNOVER_24H=2_000_000
MAX_RANGES_PCT=65
MAX_CHANGES=10
MIN_TENURE=24*HOUR
MIN_QUALITY_EDGE=0.09

def ms(s):
    dt=datetime.fromisoformat(s)
    if dt.utcoffset().total_seconds()!=0:raise ValueError("UTC_ONLY")
    return int(dt.timestamp()*1000)
def require(condition,error):
    if not condition:raise RuntimeError(error)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_history(root:Path):
    manifest=json.loads((root/"historical-download-manifest.json").read_text())
    require(manifest.get("schema")=="m5a-1h-public-ohlcv-sampled-history-v1","BAD_MANIFEST")
    require(manifest["currently_listed_top_volume_sampling_causes_survivorship_bias"] is True,"MISSING_BIAS_LABEL")
    result={}
    for entry in manifest["symbols"]:
        if entry["status"]!="OK":continue
        f=root/entry["file"]
        require(f.is_file() and sha(f)==entry["sha256"],"HOURLY_SHA256_MISMATCH_"+entry["symbol"])
        raw=json.loads(f.read_text())
        require(len(raw)==entry["bars"],"ROW_COUNT_MISMATCH")
        ts=[x[0] for x in raw]
        require(len(ts)==len(set(ts)) and ts==sorted(ts),"DUPLICATE_NONMONOTONIC_CANDLES")
        for x in raw:
            require(len(x)==6 and
              x[1]>0 and x[2]>=max(x[1],x[4]) and
              x[3]<=min(x[1],x[4]) and x[3]>0 and
              x[5]>=0 and all(isfinite(v) for v in x[1:]),
              "INVALID_HISTORICAL_CANDLE_"+entry["symbol"])
        result[entry["symbol"]]=(ts,raw)
    return result,manifest

def features(history,t):
    out={}
    for sym,(ts,bars) in history.items():
        k=bisect_left(ts,t)
        if k<MIN_HISTORY_HOURS or k+24>len(bars):continue
        # No missing candles in entire preceding 45-day age check; all
        # features at the START of the next 8h decision, never at/after t.
        if ts[k-1]!=t-HOUR or ts[k-MIN_HISTORY_HOURS]!=t-MIN_HISTORY_HOURS*HOUR:
            continue
        prev24=bars[k-24:k]
        prev8=bars[k-8:k]
        last=bars[k-1][4]
        earlier=bars[k-9][4]
        if earlier<=0:continue
        vol24=sum(row[5] for row in prev24)
        high24=max(row[2] for row in prev24)
        low24=min(row[3] for row in prev24)
        rng=100*(high24-low24)/low24
        if vol24<MIN_QUOTE_TURNOVER_24H or not 0.1<=rng<=MAX_RANGES_PCT:
            continue
        # Quoted turnover is OBSERVED in completed 1h candles, NOT
        # orderbook liquidity or bid/ask spread.
        liq=min(1,max(0,log10(vol24/MIN_QUOTE_TURNOVER_24H)/2))
        volquality=max(0,1-abs(rng-5.0)/25)
        trend=(last/earlier)-1
        # Strict as-of price only; prefer non-extreme realized volatility.
        quality=round(.65*liq+.35*volquality,6)
        out[sym]={"liquidity":round(liq,6),"quality":quality,
                  "momentum8":trend,"close":last,"index":k,
                  "volume24":vol24,"range24":rng}
    return out

def choose(old,feat,score_field,known_since,t):
    require(len(old)==25 and len(set(old))==25 and "BTCUSDT" in old,"BAD_25_UNIVERSE")
    available=set(feat)
    excluded=[s for s in old if s not in available]
    safe_outgoing=[s for s in old if s in available and s!="BTCUSDT"
                   and t-known_since.get(s,t)>=MIN_TENURE]
    fresh=sorted((s for s in available if s not in old),
                 key=lambda s:(-feat[s][score_field],s))
    original=old[:]
    switches=[]
    reason=[]
    if "BTCUSDT" not in available:
        reason.append("BTC_HISTORY_MISSING")
    if len(available)<25:
        reason.append("FEWER_THAN_25_CANDLE_READY")
    if len(excluded)>MAX_CHANGES:
        reason.append("OVER_TEN_CURRENTLY_UNAVAILABLE")
    if len(fresh)<len(excluded):
        reason.append("NOT_ENOUGH_HISTORY_READY_ALTERNATIVES")
    if reason:
        return original,[],reason
    # Replace any data-unavailable incumbents before discretionary changes.
    for old_sym,new in zip(sorted(excluded),fresh[:len(excluded)]):
        original[original.index(old_sym)]=new
        switches.append({"out":old_sym,"in":new,"why":"MISSING_HISTORICAL_CANDLES"})
    used={v["out"] for v in switches}
    for new in fresh[len(excluded):]:
        if len(switches)>=MAX_CHANGES:break
        replaceable=sorted((s for s in safe_outgoing if s not in used),
                           key=lambda s:(feat[s][score_field],s))
        if not replaceable:break
        poorest=replaceable[0]
        if feat[new][score_field] < feat[poorest][score_field]+MIN_QUALITY_EDGE:
            continue
        original[original.index(poorest)]=new
        switches.append({"out":poorest,"in":new,"why":"ASOF_PROXY_SCORE"})
        used.add(poorest)
    require(len(original)==25 and len(set(original))==25 and "BTCUSDT" in original
            and len(switches)<=MAX_CHANGES
            and len(set(original)&set(old))>=15,
            "M5A_PROXY_ROTATION_CONTRACT_VIOLATED")
    return original,switches,[]

def outcome(history,t,entry,side,target,stop=.02,horizon=24):
    ts,bars=history
    k=bisect_left(ts,t)
    if k+horizon>len(bars):return None
    if ts[k]!=t or ts[k+horizon-1]!=t+(horizon-1)*HOUR:return None
    upper=entry*(1+target if side=="long" else 1+stop)
    lower=entry*(1-stop if side=="long" else 1-target)
    for h,row in enumerate(bars[k:k+horizon],start=1):
        high,low=row[2],row[3]
        adverse=(low<=lower if side=="long" else high>=upper)
        good=(high>=upper if side=="long" else low<=lower)
        if adverse and good:return {"kind":"LOSS_SAME_HOUR_AMBIGUOUS_STOP_FIRST","hours":h}
        if adverse:return {"kind":"LOSS_STOP_FIRST","hours":h}
        if good:return {"kind":"TARGET_FIRST","hours":h}
    return {"kind":"UNRESOLVED_AT_24H","hours":horizon}

def signal_opportunity(universe,feat,history,t,target):
    # Single as-of long/short momentum probe, same rule for each comparator.
    # Does NOT call any Nbot library family, FreqAI or native Freqtrade.
    eligible=[(abs(feat[s]["momentum8"]),s) for s in universe if s in feat
              and s!="BTCUSDT" and abs(feat[s]["momentum8"])>=.007]
    if not eligible:return {"status":"NO_MOMENTUM_SIGNAL"}
    strength,sym=sorted(eligible,key=lambda x:(-x[0],x[1]))[0]
    side="long" if feat[sym]["momentum8"]>0 else "short"
    result=outcome(history[sym],t,feat[sym]["close"],side,target)
    if result is None:return {"status":"NO_FUTURE_DATA"}
    return {"status":result["kind"],"symbol":sym,"side":side,
            "score_abs_momentum8":round(strength,6),
            "hours_to_outcome":result["hours"]}

def replay(history,original,start_ms,end_ms):
    # One review per 8h; no further response-adaptive threshold changes.
    states={p:{"symbols":list(original),"since":{s:start_ms-48*HOUR for s in original}}
            for p in ("fixed25","liquidity25","quality25")}
    records=[]
    for t in range(start_ms,end_ms,REVIEW):
        feat=features(history,t)
        if len(feat)<25:continue
        row={"asof_utc":datetime.fromtimestamp(t/1000,timezone.utc).isoformat(),
             "available_candle_eligible":len(feat),"comparisons":{}}
        for p,state in states.items():
            old=state["symbols"]
            if p=="fixed25":
                new=list(old);swaps=[];holds=[]
            else:
                field="liquidity" if p=="liquidity25" else "quality"
                new,swaps,holds=choose(old,feat,field,state["since"],t)
            require(len(new)==25,"BROKEN_COIN_COUNT")
            for s in old:
                if s not in new:state["since"].pop(s,None)
            for s in new:
                if s not in old:state["since"][s]=t
            state["symbols"]=new
            row["comparisons"][p]={
              "turnover":len(swaps),"changes":swaps,"holds":holds,
              "eligible_count":sum(s in feat for s in new),
              "mean_proxy_market_quality":round(
                   mean(feat[s]["quality"] for s in new if s in feat),6),
              "symbols":new,
              "target2":signal_opportunity(new,feat,history,t,.02),
              "target3":signal_opportunity(new,feat,history,t,.03)}
        records.append(row)
    return records

def aggregate(records,group_key):
    groups=collections.defaultdict(list)
    for row in records:
        name=row["asof_utc"][0:7] if group_key=="month" else "all"
        groups[name].append(row)
    result={}
    for period,rows in sorted(groups.items()):
        stats={}
        for policy in ("fixed25","liquidity25","quality25"):
            col=[r["comparisons"][policy] for r in rows]
            summary={
               "reviews":len(col),
               "total_virtual_coin_rotations":sum(c["turnover"] for c in col),
               "reviews_on_hold":sum(bool(c["holds"]) for c in col),
               "mean_public_ohlcv_quality_proxy":round(mean(c["mean_proxy_market_quality"] for c in col),5),
               "mean_candle_eligible_count":round(mean(c["eligible_count"] for c in col),3)}
            for key in ("target2","target3"):
                outcomes=collections.Counter(c[key]["status"] for c in col)
                signals=sum(v for k,v in outcomes.items() if k not in
                            ("NO_MOMENTUM_SIGNAL","NO_FUTURE_DATA"))
                wins=outcomes["TARGET_FIRST"]
                stops=outcomes["LOSS_STOP_FIRST"]+outcomes["LOSS_SAME_HOUR_AMBIGUOUS_STOP_FIRST"]
                summary[key]={"signals":signals,"target_before_stop":wins,
                              "stop_before_target":stops,
                              "unresolved_within_24h":outcomes["UNRESOLVED_AT_24H"],
                              "target_first_rate_on_signals":round(wins/signals,4) if signals else None,
                              "outcome_counts":dict(outcomes)}
            stats[policy]=summary
        result[period]=stats
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    require(not a.out.exists(),"REFUSE_OVERWRITE_FINAL_PROXY_REPLAY")
    hist,source=load_history(a.data)
    baseline=source["initial_original_25"]
    require(len(hist)>=35 and all(s in hist for s in baseline),
            "NOT_ENOUGH_HISTORICAL_MARKETS")
    rows=replay(hist,baseline,ms(START),ms(END))
    require(len(rows)>150,"INSUFFICIENT_ASOF_EIGHT_HOUR_REVIEWS")
    output={
       "schema":"m5a-historical-8h-ohlcv-proxy-replay-1",
       "scope":"SURVIVOR_BIASED_75_MARKET_1H_HISTORICAL_PROXY_ONLY",
       "all_current_assets_historical_survivorship_bias":True,
       "NO_HISTORICAL_SPREAD_DEPTH_FUNDING_OR_MODEL_READINESS":True,
       "NEVER_PROVES_ACTUAL_DYNAMIC_25_VS_FIXED_PROFIT":True,
       "no_5m_strategies_or_native_portfolio_executed":True,
       "one_candidate_per_review_PROBES_OVERLAP_IN_24H_LABEL_WINDOW":True,
       "target2_and_target3_are_not_realized_fills_or_backtested_equity":True,
       "only_completed_hourly_candles_enter_asof_scores":True,
       "stop_first_when_same_hour_ambiguous":True,
       "no_paper_live_or_autotrading":True,
       "sampled_current_symbols":len(hist),
       "start_utc":START,"end_utc":END,
       "source_download_manifest_sha256":sha(a.data/"historical-download-manifest.json"),
       "reviews":len(rows),"summary_by_month":aggregate(rows,"month"),
       "summary_all":aggregate(rows,"all")["all"],
       "records":rows}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    concise={"reviews":len(rows),"sampled_symbols":len(hist),
             "monthly":output["summary_by_month"],
             "all":output["summary_all"],
             "not_native_trading_pnl":True}
    print(json.dumps(concise,indent=2,sort_keys=True))
if __name__=="__main__":main()
