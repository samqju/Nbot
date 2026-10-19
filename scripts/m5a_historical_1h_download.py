#!/usr/bin/env python3
"""Download PUBLIC Binance 1h futures candles for a limited historical M5A proxy.

RESEARCH ONLY; not an authenticated exchange client; never places orders.
Current-day liquid symbol universe is a *survivor-biased convenience sample*:
it must NOT be represented as all markets listed in the historical period.
Output uses one atomic, per-symbol historical JSON and SHA256 manifest entry.
Only CLOSED 1h candles are retained. Request bounded historical dates.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

BASE="https://fapi.binance.com/fapi/v1/klines"
HOUR=3_600_000
MAX_SYMBOLS=110
START="2026-06-01T00:00:00+00:00"
END="2026-10-19T00:00:00+00:00"

def utc_ms(value:str)->int:
    d=datetime.fromisoformat(value)
    if d.utcoffset().total_seconds()!=0:raise ValueError("UTC_REQUIRED")
    return int(d.timestamp()*1000)
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def save_new(path:Path,payload:object):
    if path.exists():raise FileExistsError("NO_RESEARCH_OVERWRITE_"+str(path))
    raw=(json.dumps(payload,separators=(",",":"),sort_keys=True)+"\n").encode()
    temp=path.with_suffix(path.suffix+".tmp")
    with temp.open("xb") as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    return {"file":path.name,"sha256":digest(raw),"bytes":len(raw)}
def choose(snapshot:dict,original:list[str],cap:int)->list[str]:
    valid=[]
    for row in snapshot["contracts"]:
        if(row.get("contractType")=="PERPETUAL" and row.get("status")=="TRADING"
           and row.get("quoteAsset")=="USDT" and row.get("marginAsset")=="USDT"
           and isinstance(row.get("symbol"),str)
           and row["symbol"].endswith("USDT")):
            try:v=float(row["quoteVolume"])
            except (ValueError,TypeError):continue
            if v>0:valid.append((v,row["symbol"]))
    valid.sort(key=lambda x:(-x[0],x[1]))
    samples=list(dict.fromkeys(original+[v[1] for v in valid]))
    if len(samples)>cap:
        # Baseline symbols always retained, remaining chosen from future-
        # observed ranking: THIS IS AN EXPLICIT SELECTION BIAS.
        samples=samples[:cap]
    if len(set(original)-set(samples)):raise RuntimeError("BASELINE_25_MISSING")
    return samples

def fetch(symbol:str,start_ms:int,end_ms:int)->list[list]:
    now=start_ms;result=[];calls=0
    while now<end_ms:
        query=urllib.parse.urlencode({"symbol":symbol,"interval":"1h",
                                      "startTime":now,"endTime":end_ms-1,
                                      "limit":1500})
        req=urllib.request.Request(BASE+"?"+query,headers={
            "User-Agent":"Nbot-V6-public-historical-proxy-research/1.0"})
        for retry in range(5):
            try:
                with urllib.request.urlopen(req,timeout=28) as response:
                    if response.status!=200:raise RuntimeError("HTTP_"+str(response.status))
                    data=json.loads(response.read(1_800_000))
                if not isinstance(data,list):raise RuntimeError("API_NOT_CANDLES")
                break
            except Exception:
                if retry==4:raise
                time.sleep(1.3*(retry+1))
        if not data:break
        for bar in data:
            ts=int(bar[0])
            if ts<start_ms or ts>=end_ms:continue
            # 0=open time,1=open,2=high,3=low,4=close,5=base volume,
            # 7=quote turnover. Both quote and price are market observations
            # as of the candle close only.
            result.append([ts,float(bar[1]),float(bar[2]),float(bar[3]),
                           float(bar[4]),float(bar[7])])
        prev=now
        now=int(data[-1][0])+HOUR
        if now<=prev:raise RuntimeError("NON_ADVANCING_HOURLY_PAGINATION")
        calls+=1
        if calls>20:raise RuntimeError("UNEXPECTEDLY_MANY_API_REQUESTS")
        time.sleep(0.065)
    result.sort(key=lambda r:r[0])
    if len(set(r[0] for r in result))!=len(result):
        raise RuntimeError("DUPLICATE_HOURLY_TIMESTAMPS")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,default=75)
    a=p.parse_args()
    if not 26<=a.limit<=MAX_SYMBOLS:raise SystemExit("BOUNDED_SYMBOL_CAP_REQUIRED")
    from m5a_universe_selector import incumbent_symbols
    cfg=json.loads(a.config.read_text())
    base=incumbent_symbols(cfg)
    snap=json.loads(a.snapshot.read_text())
    symbols=choose(snap,base,a.limit)
    a.out.mkdir(parents=True,exist_ok=True)
    manifest=a.out/"historical-download-manifest.json"
    if manifest.exists():raise SystemExit("STUDY_ALREADY_HAS_FINAL_MANIFEST")
    started=time.time()
    statuses=[]
    for i,symbol in enumerate(symbols,1):
        path=a.out/(symbol+"-1h.json")
        if path.exists():
            # Resume ONLY immutable completed files; partial new temp files
            # are never read as valid historical evidence.
            rows=json.loads(path.read_text())
            checked={"file":path.name,"sha256":digest(path.read_bytes()),
                     "bytes":path.stat().st_size}
        else:
            try:
                rows=fetch(symbol,utc_ms(START),utc_ms(END))
                checked=save_new(path,rows)
            except Exception as e:
                print(json.dumps({"index":i,"symbol":symbol,"error":str(e)}),flush=True)
                statuses.append({"symbol":symbol,"status":"ERROR","error":str(e)})
                continue
        expected_closed=all(r[0]+HOUR<=utc_ms(END) for r in rows)
        statuses.append({"symbol":symbol,"status":"OK",
                         "bars":len(rows),"valid_closed_bars":expected_closed,
                         "first_bar_ms":rows[0][0] if rows else None,
                         "last_bar_ms":rows[-1][0] if rows else None,**checked})
        print(json.dumps({"index":i,"total":len(symbols),"symbol":symbol,
                          "bars":len(rows),"ok":expected_closed}),flush=True)
    summary={
      "schema":"m5a-1h-public-ohlcv-sampled-history-v1",
      "start_utc":START,"end_utc":END,
      "download_completed_at_utc":datetime.now(timezone.utc).isoformat(),
      "elapsed_seconds":round(time.time()-started,1),
      "source":"Binance fapi/v1/klines public historical OHLCV; closed 1h",
      "current_day_snapshot_sha256":digest(a.snapshot.read_bytes()),
      "currently_listed_top_volume_sampling_causes_survivorship_bias":True,
      "no_historical_orderbook_bidask_spreads_or_funding":True,
      "cannot_run_actual_live_M5A_score_or_verify_model_ready":True,
      "not_an_executable_backtest":True,
      "initial_original_25":base,
      "sampled_symbols":symbols,
      "symbols":statuses,
      "successful":sum(x["status"]=="OK" for x in statuses),
      "failed":sum(x["status"]=="ERROR" for x in statuses),
      "no_orders_or_live_config_changes":True
    }
    save_new(manifest,summary)
    print(json.dumps({"study":"COMPLETE_DOWNLOAD","success":summary["successful"],
                      "failed":summary["failed"],"elapsed_seconds":summary["elapsed_seconds"]}),flush=True)
if __name__=="__main__":
    main()
