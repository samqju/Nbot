#!/usr/bin/env python3
"""Bounded public-only Binance USD-M market screener, NO ORDERS OR API KEYS.

Fetches four WHOLE-MARKET read-only endpoints sequentially, timestamps each
response and stores an immutable observation. An observation outside the first
three minutes of an 8h UTC review is DIAGNOSTIC_ONLY, not a retroactive proposal.
ExchangeInfo from today MUST NEVER be used to claim historical listing status.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from m5a_universe_selector import HOUR_MS, MAX_SNAPSHOT_AGE_MS, evaluate, sha_obj

BASE="https://fapi.binance.com"
ENDPOINTS=(
    ("exchangeInfo","/fapi/v1/exchangeInfo"),
    ("tickers","/fapi/v1/ticker/24hr"),
    ("book","/fapi/v1/ticker/bookTicker"),
    ("funding","/fapi/v1/premiumIndex"),
)
MAX_BODY=8_000_000

def now_ms()->int:return int(time.time()*1000)

def get_json(path:str):
    require=path.startswith("/fapi/v1/") and "?" not in path
    if not require:raise RuntimeError("UNAPPROVED_PUBLIC_ENDPOINT")
    req=urllib.request.Request(BASE+path,headers={
        "User-Agent":"NBOT-V6-M5A-PUBLIC-SHADOW-SNAPSHOT/1.0",
        "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=22) as response:
        if response.status!=200:raise RuntimeError("PUBLIC_MARKET_HTTP_"+str(response.status))
        raw=response.read(MAX_BODY+1)
        if len(raw)>MAX_BODY:raise RuntimeError("PUBLIC_EXCHANGE_PAYLOAD_EXCEEDS_BOUND")
    return json.loads(raw),now_ms()

def capture():
    records={}
    times={}
    for label,url in ENDPOINTS:
        obj,stamp=get_json(url)
        records[label]=obj
        times[label]=stamp
    start=min(times.values());end=max(times.values())
    if end-start>MAX_SNAPSHOT_AGE_MS:raise RuntimeError("MARKET_SNAPSHOT_COLLECTION_TOO_SLOW")
    exchange=records["exchangeInfo"]
    if not isinstance(exchange,dict) or not isinstance(exchange.get("symbols"),list):
        raise RuntimeError("MISSING_EXCHANGE_CONTRACTS")
    tick={x["symbol"]:x for x in records["tickers"] if isinstance(x,dict) and x.get("symbol")}
    book={x["symbol"]:x for x in records["book"] if isinstance(x,dict) and x.get("symbol")}
    funding={x["symbol"]:x for x in records["funding"] if isinstance(x,dict) and x.get("symbol")}
    contracts=[]
    for e in exchange["symbols"]:
        symbol=e.get("symbol")
        if not isinstance(symbol,str) or not symbol.endswith("USDT"):
            continue
        t=tick.get(symbol,{})
        b=book.get(symbol,{})
        f=funding.get(symbol,{})
        x={k:e.get(k) for k in ("symbol","status","contractType","quoteAsset",
                               "marginAsset","onboardDate")}
        for k in ("quoteVolume","highPrice","lowPrice"):
            x[k]=t.get(k)
        for k in ("bidPrice","askPrice","bidQty","askQty"):
            x[k]=b.get(k)
        x["lastFundingRate"]=f.get("lastFundingRate")
        x.update(book_at_ms=times["book"],ticker_at_ms=times["tickers"],
                 funding_at_ms=times["funding"])
        # Some bookTicker responses expose trade timestamps. Reject future or
        # stale timestamps instead of misusing a current quote as historical.
        if isinstance(b.get("time"),int) and not 0<=end-b["time"]<=MAX_SNAPSHOT_AGE_MS:
            x["book_at_ms"]=b["time"]
        contracts.append(x)
    if len(contracts)<25:raise RuntimeError("NOT_ENOUGH_USDT_MARKETS_IN_SNAPSHOT")
    review=(end//(8*HOUR_MS))*(8*HOUR_MS)
    eligible_window=end-review<=MAX_SNAPSHOT_AGE_MS
    payload={
        "schema":"m5a-snapshot-v1",
        "source":"binance_public_rest",
        "asof_ms":review if eligible_window else end,
        "captured_at_ms":end,
        "endpoint_captured_at_ms":times,
        "review_boundary_aligned":eligible_window,
        "contracts":contracts,
        "observation_not_historical_market_metadata":True,
        "no_exchange_keys_used":True,
        "never_changes_active_universe":True,
    }
    payload["raw_snapshot_sha256"]=sha_obj(payload)
    return payload

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--summary-only",action="store_true")
    a=p.parse_args()
    if a.out.exists():raise SystemExit("REFUSE_OVERWRITE_PUBLIC_SNAPSHOT")
    obj=capture()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n")
    rows=[evaluate(x,obj["captured_at_ms"],set()) for x in obj["contracts"]]
    qualified=sorted((x for x in rows if x.eligible),key=lambda x:(-x.score,x.symbol))
    report={
        "saved_snapshot":str(a.out),
        "captured_utc":datetime.fromtimestamp(obj["captured_at_ms"]/1000,timezone.utc).isoformat(),
        "review_eligible":obj["review_boundary_aligned"],
        "screened_contracts":len(rows),
        "eligible_public_market_quality":len(qualified),
        "top_30_screened_quality_NOT_TRADE_READY":[
            {"symbol":x.symbol,"quality_score":x.score,
             "spread_bps":x.spread_bps,"volume_usdt":round(x.quote_volume_usdt or 0)}
            for x in qualified[:30]],
        "important":"Only a public current-market screener. Historical as-of replay, model readiness, execution profitability and 8h activation NOT proven.",
        "no_orders":True}
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
