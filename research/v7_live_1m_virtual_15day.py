#!/usr/bin/env python3
"""15-hour PUBLIC-MARKET-DATA ONLY FreqAI 1m virtual-trade research.

STRICT SCOPE: BTCUSDT ETHUSDT SOLUSDT, one-minute completed USD-M futures
candles, previous 15d supervised matured labels, FreqAI LightGBMRegressor.fit
via the installed custom upstream V7 research bridge. NO ACCOUNT ACCESS,
NO API KEYS, NO EXCHANGE ORDERS, NO dry-run trading platform.

The 1m experiment is a new, documented feature/target adaptation. It is NOT
the prior 5m 20-family RAW model, not native FreqAI training scheduler and
not a production-ready strategy. Simple LONG/SHORT choices per symbol,
highest positive predicted net after proxy fee+slippage or NO TRADE.
At most THREE TOTAL new virtual entries for this one 15-hour study.
All positions close via stop 2%, target 3% or max 60min; at most one
per symbol and at most three concurrent; cap 3 *total* not guaranteed 3.
One-minute OHLC stop-first; entry only at the NEXT minute OPEN after
a complete decision candle. This is not a bid/ask/exchange fill.
Funding is NOT included in economic labels or PnL; log prominently.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import csv
import io
import json
import logging
import math
import os
import sqlite3
import statistics
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from zipfile import ZipFile

import joblib
import numpy as np
import pandas as pd

from nbot_v7.data import Bar
from nbot_v7.runtime.broker import PaperBroker
from nbot_v7.runtime.risk import RiskPolicy
from research.freqai_v7_net_fit_and_replay import actual_freqai_fit

S=("BTCUSDT","ETHUSDT","SOLUSDT")
ONE=60000
# REST source may revise recently completed 1m OHLCV. To avoid trading
# on provisional prices, wait 90 seconds AFTER the bar closes.
CONFIRM_DELAY_MS=90000
# Score after delay, then enter only at later 3rd candle OPEN.
ENTRY_LAG_BARS=3
DAY=86400000
DAYS=15
HORIZON=60
MAX_ENTRIES=3
HOURS=15
FEATURE_NAMES=(
    "r3","r12","r48","atr","volume_ratio","range_12","body",
    "btc_r3","btc_r12","btc_r48","btc_atr","vs_btc","utc_hour",
    "side_short","coin_btc","coin_eth","coin_sol",
)
API="https://fapi.binance.com/fapi/v1/klines"
VIS="https://data.binance.vision/data/futures/um/daily/klines"
USER_AGENT="NBOT-V7-PUBLIC-RESEARCH-1MIN-NO-ORDERS/1.0"
STOP_POLICY=RiskPolicy()
LOG=logging.getLogger("v7_1m_public_virtual")
EXPERIMENT="V7_LIVE_PUBLIC_1M_FREQAI_15DAY_TRAIN_RAW_THREE_COIN_3TOTAL_ENTRIES_V1"


def now_ms():
    return int(time.time()*1000)


def sha(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def get(url,*,timeout=35):
    req=Request(url,headers={"User-Agent":USER_AGENT})
    with urlopen(req,timeout=timeout) as res:
        if res.status!=200:raise RuntimeError("PUBLIC_HTTP_NON_200_"+str(res.status))
        payload=res.read(12_000_000)
        if len(payload)>=12_000_000:raise RuntimeError("SOURCE_RESPONSE_OVERSIZE")
        return payload


def rest_klines(symbol,limit=12,*,start=None,end=None):
    if symbol not in S:raise ValueError("OUTSIDE_THREE_COINS")
    args={"symbol":symbol,"interval":"1m","limit":limit}
    if start is not None:args["startTime"]=start
    if end is not None:args["endTime"]=end
    rows=json.loads(get(API+"?"+urlencode(args),timeout=20))
    if not isinstance(rows,list):raise ValueError("BINANCE_PUBLIC_KLINES_INVALID:"+str(rows)[:120])
    return [parse_ohlc(r) for r in rows]


def parse_ohlc(r):
    if len(r)<6:raise ValueError("INVALID_CANDLE_SHAPE")
    t=int(r[0])
    if t>=10**15:t//=1000
    if t%ONE:raise ValueError("NON_1M_CANDLE_TIME")
    a=list(map(float,r[1:6]))
    o,h,l,c,v=a
    if not all(math.isfinite(k) for k in a) or min(o,h,l,c)<=0 or v<0 or h<max(o,l,c) or l>min(o,h,c):
        raise ValueError("INVALID_MARKET_CANDLE")
    return Bar(t,o,h,l,c,v)


def archive_day(root,symbol,day):
    key=day.strftime("%Y-%m-%d")
    if symbol not in S:raise ValueError("OUTSIDE_THREE_COINS")
    name=f"{symbol}-1m-{key}.zip"
    url=f"{VIS}/{symbol}/1m/{name}"
    dest=root/"sources"/symbol/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    checksum=(get(url+".CHECKSUM",timeout=40).decode("ascii").split()[0]).lower()
    if len(checksum)!=64 or not all(c in "0123456789abcdef" for c in checksum):
        raise ValueError("BINANCE_PUBLISHED_CHECKSUM_NOT_SHA256")
    if not dest.exists():
        download=get(url,timeout=75)
        tmp=dest.with_suffix(".zip.partial")
        tmp.write_bytes(download)
        if sha(tmp)!=checksum:
            tmp.unlink(missing_ok=True)
            raise ValueError("BINANCE_PUBLIC_ARCHIVE_SHA256_MISMATCH")
        tmp.replace(dest)
    if sha(dest)!=checksum:
        raise ValueError("EXISTING_PUBLIC_ARCHIVE_INTEGRITY_MISMATCH")
    with ZipFile(dest) as z:
        members=[m for m in z.namelist() if m.endswith(".csv") and not m.startswith("__MACOSX")]
        if len(members)!=1:raise ValueError("INVALID_ARCHIVE_MEMBER_COUNT")
        with z.open(members[0]) as stream:
            records=[parse_ohlc(row) for row in csv.reader(io.TextIOWrapper(stream,encoding="utf-8-sig"))
                     if row and row[0].strip().isdigit()]
    if len(records)!=1440 or records[0].t!=int(datetime.combine(day,datetime.min.time(),timezone.utc).timestamp()*1000):
        raise ValueError("INCOMPLETE_SOURCE_DAY_1MIN_"+key)
    if any(b.t-a.t!=ONE for a,b in zip(records,records[1:])):
        raise ValueError("MISSING_CANDLE_IN_VERIFIED_ARCHIVE")
    return records,{"day":key,"symbol":symbol,"source_sha256":checksum,"bars":len(records)}


def connect(root):
    root.mkdir(parents=True,exist_ok=True)
    db=root/"virtual_1m.sqlite"
    c=sqlite3.connect(db,timeout=30)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS bars(symbol TEXT NOT NULL,t INTEGER NOT NULL,
        o REAL NOT NULL,h REAL NOT NULL,l REAL NOT NULL,c REAL NOT NULL,v REAL NOT NULL,
        PRIMARY KEY(symbol,t));
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        time_ms INTEGER NOT NULL,type TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS model_history(
        cutoff_ms INTEGER PRIMARY KEY, artifact_sha TEXT NOT NULL,
        label_rows INTEGER NOT NULL,trained_at_ms INTEGER NOT NULL);
    """)
    c.commit()
    return c


def meta_get(c,k,default=None):
    a=c.execute("SELECT v FROM meta WHERE k=?",(k,)).fetchone()
    return json.loads(a[0]) if a else default


def meta_set(c,k,v):
    c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)",(k,json.dumps(v,sort_keys=True)))


def event(c,kind,**data):
    c.execute("INSERT INTO events(time_ms,type,payload) VALUES(?,?,?)",
              (now_ms(),kind,json.dumps(data,sort_keys=True,allow_nan=False)))
    if kind in ("VIRTUAL_OPEN","VIRTUAL_CLOSE","FAIL_CLOSED_SOURCE","MODEL_FITTED","RESEARCH_END"):
        LOG.info("%s %s",kind,json.dumps(data,sort_keys=True))


def add_bars(c,symbol,bars):
    count=0
    for b in bars:
        if b.t+ONE>now_ms()-CONFIRM_DELAY_MS:continue
        x=c.execute("SELECT o,h,l,c,v FROM bars WHERE symbol=? AND t=?",(symbol,b.t)).fetchone()
        if x:
            if any(abs(float(x[k])-getattr(b,k))>max(1e-6,abs(getattr(b,k))*1e-10)
                   for k in ("o","h","l","c","v")):
                raise ValueError("PUBLIC_SOURCE_CANDLE_REWRITE_CONFLICT")
        else:
            c.execute("INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
                      (symbol,b.t,b.o,b.h,b.l,b.c,b.v))
            count+=1
    return count


def bootstrap(root):
    c=connect(root)
    if meta_get(c,"bootstrapped",False):
        c.close()
        LOG.info("EXISTING_CHECKSUM_VERIFIED_SOURCE_BOOTSTRAP_REUSED")
        return root
    if c.execute("SELECT COUNT(*) FROM events").fetchone()[0] != 0:
        raise RuntimeError("EXISTING_RUN_UNINITIALIZED_REFUSE_OVERWRITE")
    d=datetime.now(timezone.utc).date()
    evidence=[]
    for delta in range(16,0,-1):
        day=d-timedelta(days=delta)
        for symbol in S:
            bars,receipt=archive_day(root,symbol,day)
            with c:
                count=add_bars(c,symbol,bars)
            evidence.append(receipt)
            LOG.info("ARCHIVE_VERIFIED symbol=%s day=%s bars=%d new=%d",
                     symbol,day,len(bars),count)
    # Use current public REST candles to avoid training on stale yesterday.
    # A single 1m page spans > today's 00:00 until max 16h from midnight.
    for symbol in S:
        today_start=int(datetime.combine(d,datetime.min.time(),timezone.utc).timestamp()*1000)
        candles=rest_klines(symbol,limit=1500,start=today_start)
        if candles:
            with c:add_bars(c,symbol,candles)
    common=min(c.execute("SELECT max(t) FROM bars WHERE symbol=?",(s,)).fetchone()[0] for s in S)
    if common is None or now_ms()-(common+ONE)>300000:
        raise RuntimeError("PUBLIC_1M_FEED_NOT_FRESH_AT_BOOTSTRAP")
    c.executescript("PRAGMA wal_checkpoint(TRUNCATE)")
    meta_set(c,"source_receipts",evidence)
    meta_set(c,"bootstrapped",True)
    meta_set(c,"launch_cutoff_ms",common+ONE)
    meta_set(c,"last_processed_open_ms",common)
    meta_set(c,"new_entry_count",0)
    meta_set(c,"positions",{})
    meta_set(c,"pending",None)
    meta_set(c,"realized_usdt",0.0)
    meta_set(c,"max_drawdown",0.0)
    meta_set(c,"peak_usdt",10000.0)
    meta_set(c,"stop_reason_counts",{})
    meta_set(c,"started_utc",datetime.now(timezone.utc).isoformat())
    meta_set(c,"allowed_symbols",list(S))
    meta_set(c,"experiment",EXPERIMENT)
    meta_set(c,"source_candle_ms",ONE)
    meta_set(c,"training_days",DAYS)
    meta_set(c,"exit_policy",{"stop":.02,"target":.03,"max_hold_minutes":60,"fee_each":.0005,"slippage_each":.0001,"funding":"NOT_MODELED","confirmed_candle_age_ms":CONFIRM_DELAY_MS,"entry_lag_candles":ENTRY_LAG_BARS})
    event(c,"SOURCE_BOOTSTRAPPED",last_common_candle=common,archives=len(evidence),
          min_symbol_bars=min(c.execute("SELECT count(*) FROM bars WHERE symbol=?",(s,)).fetchone()[0] for s in S))
    c.commit()
    c.close()
    return root


def contiguous_bars(c,s,limit=180):
    rows=c.execute("SELECT t,o,h,l,c,v FROM bars WHERE symbol=? ORDER BY t DESC LIMIT ?",(s,limit)).fetchall()
    bars=[Bar(*r) for r in reversed(rows)]
    if any(b.t-a.t!=ONE for a,b in zip(bars,bars[1:])):
        raise RuntimeError("GAP_IN_PUBLIC_1M_MARKET_HISTORY")
    return bars


def feat(bars,btc,at_idx=None):
    if at_idx is None:at_idx=len(bars)-1
    if at_idx<50:raise ValueError("CAUSAL_FEATURE_WARMUP_INCOMPLETE")
    if btc[at_idx].t!=bars[at_idx].t:
        raise ValueError("BTC_CONTEXT_NOT_SAME_MINUTE")
    x=bars[at_idx]
    b=btc[at_idx]
    av=sum((b0.h-b0.l)/b0.c for b0 in bars[at_idx-13:at_idx+1])/14
    bv=sum((b0.h-b0.l)/b0.c for b0 in btc[at_idx-13:at_idx+1])/14
    r3=x.c/bars[at_idx-3].c-1
    r12=x.c/bars[at_idx-12].c-1
    r48=x.c/bars[at_idx-48].c-1
    br3=b.c/btc[at_idx-3].c-1
    br12=b.c/btc[at_idx-12].c-1
    br48=b.c/btc[at_idx-48].c-1
    xout=[
        r3,r12,r48,av,x.v/max(sum(q.v for q in bars[at_idx-20:at_idx])/20,1e-12),
        (max(q.h for q in bars[at_idx-11:at_idx+1])-min(q.l for q in bars[at_idx-11:at_idx+1]))/x.c,
        (x.c-x.o)/x.c,br3,br12,br48,bv,r12-br12,
        float(((x.t+ONE)//3600000)%24),
    ]
    if len(xout)!=13 or not all(math.isfinite(v) for v in xout):
        raise RuntimeError("MISSING_OR_NONFINITE_MODEL_FEATURES")
    return xout


def full_vector(agg,symbol,side):
    return agg+[float(side=="SHORT")]+[float(symbol==s) for s in S]


def train(c,root,*,cutoff_ms):
    """Training never sees candles or labels after as-of cutoff."""
    if cutoff_ms<=0 or cutoff_ms%ONE:raise ValueError("FIT_NOT_ON_COMPLETED_UTC_MINUTE")
    bars={}
    start=cutoff_ms-(DAYS+1)*DAY
    for s in S:
        records=c.execute(
            "SELECT t,o,h,l,c,v FROM bars WHERE symbol=? AND t>=? AND t<? ORDER BY t",
            (s,start,cutoff_ms)).fetchall()
        bars[s]=[Bar(*r) for r in records]
    n=len(bars["BTCUSDT"])
    if n<15*1400 or any(len(bars[s])!=n for s in S):
        raise RuntimeError("NOT_15_DAYS_OF_DENSE_1M_PREHISTORY")
    if any(bars[s][0].t!=bars["BTCUSDT"][0].t or
           bars[s][-1].t!=bars["BTCUSDT"][-1].t for s in S):
        raise RuntimeError("MULTICOIN_CANDLE_CLOCK_ALIGNMENT_FAILURE")
    for s in S:
        if any(b.t-a.t!=ONE for a,b in zip(bars[s],bars[s][1:])):
            raise RuntimeError("TRAINING_1M_ARCHIVE_HAS_GAPS")
    xs=[]
    ys=[]
    examples_by_coin={}
    last_label_finish=0
    first_asof=cutoff_ms-DAYS*DAY
    broker=PaperBroker()
    for s in S:
        v=bars[s]
        first=max(50,(first_asof-v[0].t)//ONE)
        count=0
        for i in range(first,n-HORIZON-ENTRY_LAG_BARS,5):
            # decision is close of i; virtual entry only at next candle open.
            if v[i].t+ONE>=cutoff_ms:break
            ag=feat(v,bars["BTCUSDT"],i)
            for side in ("LONG","SHORT"):
                pos=broker.submit({"id":"OFFLINE_SUPERVISED_TRAINING_ONLY",
                   "symbol":s,"side":side,"time_ms":v[i+ENTRY_LAG_BARS].t,
                   "quote":v[i+ENTRY_LAG_BARS].o},STOP_POLICY)
                fill=None
                for j in range(i+ENTRY_LAG_BARS,i+ENTRY_LAG_BARS+HORIZON):
                    fill,pos=broker.on_bar(pos,v[j],v[j].t+ONE,STOP_POLICY)
                    if fill is not None:break
                if fill is None or fill["available_ms"]>cutoff_ms:
                    continue
                xs.append(full_vector(ag,s,side))
                ys.append(float(fill["net_usdt"])/STOP_POLICY.notional_usdt)
                last_label_finish=max(last_label_finish,int(fill["available_ms"]))
                count+=1
        examples_by_coin[s]=count
    if len(xs)<8000 or len(xs)>80000:
        raise RuntimeError("UNEXPECTED_15DAY_TRAINING_EXAMPLE_COUNT")
    if last_label_finish>cutoff_ms:
        raise RuntimeError("MODEL_FIT_CONTAINS_FUTURE_OUTCOMES")
    path=root/"models"/datetime.fromtimestamp(cutoff_ms/1000,timezone.utc).strftime("%Y%m%dT%H%MZ")
    if path.exists():raise FileExistsError("NO_REPLACE_EXISTING_DAILY_MODEL")
    path.mkdir(parents=True)
    model=actual_freqai_fit(pd.DataFrame(np.asarray(xs,dtype="float32"),columns=FEATURE_NAMES),
                            ys,path)
    model_path=path/"freqai_1m_raw_aftercost.joblib"
    joblib.dump(model,model_path)
    manifest={"train_cutoff_ms":cutoff_ms,
              "source":"CHECKSUM_VERIFIED_BINANCE_VISION_1M_PLUS_PUBLIC_REST",
              "experiment":EXPERIMENT,"trainer":"UPSTREAM_FREQAI_LIGHTGBMREGRESSOR_FIT_V7_CUSTOM_1M_HARNESS",
              "features":list(FEATURE_NAMES),"target":"NET_PNL_USDT_DIVIDED_BY_1000",
              "lookback_days":15,"sample_stride_minutes":5,
              "first_available_history_candle_ms":bars["BTCUSDT"][0].t,
              "last_observed_candle_close_ms":bars["BTCUSDT"][-1].t+ONE,
              "last_matured_label_ms":last_label_finish,
              "examples_by_coin_side":examples_by_coin,
              "label_exit":"PAPER_1M_STOP_FIRST_2STOP_3TAKE_60MIN",
              "fees_slippage":asdict(STOP_POLICY),
              "funding":"NOT_MODELED",
              "model_sha256":sha(model_path)}
    (path/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    with c:
        c.execute("INSERT INTO model_history VALUES(?,?,?,?)",
                  (cutoff_ms,manifest["model_sha256"],len(xs),now_ms()))
        meta_set(c,"current_model_path",str(model_path))
        meta_set(c,"last_model_train_ms",cutoff_ms)
        event(c,"MODEL_FITTED",**{k:manifest[k] for k in
            ("train_cutoff_ms","last_matured_label_ms","model_sha256","examples_by_coin_side")})
    return model,manifest


def status(c,root,extra=None):
    pos=meta_get(c,"positions",{})
    summary={"experiment":EXPERIMENT,
        "updated_at_utc":datetime.now(timezone.utc).isoformat(),
        "start_utc":meta_get(c,"started_utc"),
        "cutoff_utc":datetime.fromtimestamp(meta_get(c,"end_ms",0)/1000,timezone.utc).isoformat() if meta_get(c,"end_ms") else None,
        "last_market_candle_ms":meta_get(c,"last_processed_open_ms"),
        "model_fitted_asof_ms":meta_get(c,"last_model_train_ms"),
        "virtual_trades_started":meta_get(c,"new_entry_count",0),
        "max_ever_new_trades":MAX_ENTRIES,
        "virtual_positions":{k:{"side":v["side"],"entry_price":v["entry_price"],"stop":v["stop"],"target":v["target"],"deadline_ms":v["deadline_ms"]} for k,v in pos.items()},
        "realized_pnl_usdt_without_funding":round(meta_get(c,"realized_usdt",0),4),
        "virtual_equity_usdt_without_funding":round(STOP_POLICY.initial_equity_usdt+meta_get(c,"realized_usdt",0),4),
        "source":"PUBLIC_BINANCE_FUTURES_1M_KLINES_ONLY",
        "orders_sent":0,"api_credentials_used":False,
        "fees_and_slippage":"0.05pct_fee_and_0.01pct_slippage_per_side_PROXY",
        "funding":"NOT_MODELED",
        "status":meta_get(c,"status","BOOTSTRAPPED")}
    if extra:summary.update(extra)
    tmp=root/"status.partial.json"
    tmp.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    tmp.replace(root/"status.json")
    return summary


def handle_minute(c,root,t,model,manifest):
    if t<=meta_get(c,"last_processed_open_ms",t-ONE):return
    pos=meta_get(c,"positions",{})
    pending=meta_get(c,"pending")
    # All 3 must be present and exactly one 1m bar aligned; no data gaps.
    bars={}
    histories={}
    for s in S:
        q=c.execute("SELECT t,o,h,l,c,v FROM bars WHERE symbol=? AND t=?",(s,t)).fetchone()
        if q is None:raise ValueError("INCOMPLETE_THREE_COIN_MINUTE")
        bars[s]=Bar(*q)
        histories[s]=contiguous_bars(c,s,55)
        if histories[s][-1].t < t:
            raise ValueError("NO_CURRENT_BAR_IN_HISTORY")
        if histories[s][-1].t!=t:
            # must score exact minute, not a later known point in history
            histories[s]=[Bar(*r) for r in c.execute(
                "SELECT t,o,h,l,c,v FROM bars WHERE symbol=? AND t<=? "
                "ORDER BY t DESC LIMIT 55",(s,t)).fetchall()][::-1]
        if histories[s][-1].t!=t:raise ValueError("CURRENT_MINUTE_FEATURE_TIME_MISMATCH")
    if pending is not None:
        sym=pending["symbol"]
        if pending["entry_time_ms"]>t:
            # Keep unexecuted recommendation pending until the first causal
            # entry-minute OPEN; do NOT discard it in the interim bars.
            pass
        elif pending["entry_time_ms"]==t and sym not in pos and meta_get(c,"new_entry_count",0)<MAX_ENTRIES:
            spot=bars[sym].o
            p=PaperBroker().submit({
                "id":f"PUBLIC_ONLY_VIRTUAL_{meta_get(c,'new_entry_count',0)+1}",
                "symbol":sym,"side":pending["side"],"time_ms":t,
                "quote":spot,"decision_ms":pending["decision_ms"],
                "predicted_net":pending["predicted_net"]},STOP_POLICY)
            pos[sym]=p
            meta_set(c,"new_entry_count",meta_get(c,"new_entry_count",0)+1)
            event(c,"VIRTUAL_OPEN",symbol=sym,side=p["side"],
                  entry_time_ms=t,entry_price=p["entry_price"],
                  stop=p["stop"],target=p["target"],
                  predicted_aftercost_return=pending["predicted_net"],
                  model_sha256=manifest["model_sha256"])
            pending=None
        else:
            event(c,"PENDING_DISCARDED",reason="MISSED_ENTRY_MINUTE_OR_SLOT_CAP",
                  original=pending)
            pending=None
    # Process minute using stop-first OHLC for every currently open symbol.
    for sym in list(pos):
        fill,p=PaperBroker().on_bar(pos[sym],bars[sym],t+ONE,STOP_POLICY)
        if fill is not None:
            pnl=float(fill["net_usdt"])
            meta_set(c,"realized_usdt",meta_get(c,"realized_usdt",0)+pnl)
            event(c,"VIRTUAL_CLOSE",symbol=sym,side=p["side"],
                  entered_at_ms=p["time_ms"],exit_time_ms=t+ONE,
                  exit_reason=fill["reason"],pnl_usdt_without_funding=pnl,
                  actual_aftercost_net_fraction=pnl/STOP_POLICY.notional_usdt,
                  predicted_net_fraction=p.get("predicted_net"),
                  entry_price=fill["entry_price"],exit_price=fill["exit_price"],
                  fees_usdt=fill["fees_usdt"])
            del pos[sym]
        else:
            pos[sym]=p
    equity=STOP_POLICY.initial_equity_usdt+meta_get(c,"realized_usdt",0)
    peak=max(meta_get(c,"peak_usdt",10000),equity)
    meta_set(c,"peak_usdt",peak)
    meta_set(c,"max_drawdown",max(meta_get(c,"max_drawdown",0),
                                  (peak-equity)/peak if peak>0 else 0))
    # RAW only: max(score) > 0, no uncertainty margin. Delayed next-open
    # entries must persist for the full 90s finality + 3-candle lag.
    candidates=[]
    if (pending is None and meta_get(c,"new_entry_count",0)<MAX_ENTRIES
            and t+ENTRY_LAG_BARS*ONE<meta_get(c,"last_new_entry_deadline_ms",0)
            and meta_get(c,"status")=="RUNNING"):
        for sym in S:
            if sym in pos:continue
            x=feat(histories[sym],histories["BTCUSDT"])
            for side in ("LONG","SHORT"):
                candidates.append((sym,side,full_vector(x,sym,side)))
        if candidates:
            matrix=pd.DataFrame(np.asarray([v for _,_,v in candidates],dtype="float32"),
                                columns=FEATURE_NAMES)
            predictions=np.asarray(model.predict(matrix)).reshape(-1)
            if len(predictions)!=len(candidates) or not np.all(np.isfinite(predictions)):
                raise RuntimeError("NONFINITE_FREQAI_LIVE_PREDICTION_HOLD")
            ranked=sorted(
                [{"symbol":sym,"side":side,"predicted_net":float(value)}
                 for (sym,side,_),value in zip(candidates,predictions)],
                 key=lambda x:(-x["predicted_net"],x["symbol"],x["side"]))
            chosen=ranked[0] if ranked and ranked[0]["predicted_net"]>0 else None
            event(c,"RAW_DECISION",decision_candle_open_ms=t,
                  available_at_ms=t+ONE+CONFIRM_DELAY_MS,
                  model_sha256=manifest["model_sha256"],
                  ranks=ranked,chosen=chosen,
                  reason="BEST_PREDICTED_AFTERCOST_POSITIVE" if chosen else "NO_TRADE_RAW_SCORE_NOT_POSITIVE")
            if chosen:
                pending={**chosen,"decision_ms":t+ONE+CONFIRM_DELAY_MS,
                         "entry_time_ms":t+ENTRY_LAG_BARS*ONE}
    else:
        event(c,"RAW_DECISION",decision_candle_open_ms=t,chosen=None,
              reason="PENDING_OR_CAP_REACHED_OR_FINAL_HOUR_OR_STOPPED")
    meta_set(c,"positions",pos)
    meta_set(c,"pending",pending)
    meta_set(c,"last_processed_open_ms",t)


def poll_new(c):
    # Fail-closed collection: all three successful public responses before
    # writing a new common minute. API has no credentials at all.
    n=now_ms()
    pages={s:rest_klines(s,limit=8) for s in S}
    for s,p in pages.items():
        if len(p)<2:raise ValueError("PUBLIC_PRICE_DATA_MISSING")
        if p[-1].t>n+ONE:raise ValueError("EXCHANGE_TIME_AHEAD_OF_LOCAL_CLOCK")
        with c:add_bars(c,s,p)
    common=min(max(x.t for x in p if x.t+ONE<n-CONFIRM_DELAY_MS) for p in pages.values())
    return common


def service(root,*,hours=15):
    c=connect(root)
    if meta_get(c,"experiment")!=EXPERIMENT or not meta_get(c,"bootstrapped"):
        raise ValueError("CANNOT_RUN_WITHOUT_VERIFIED_PUBLIC_SOURCE_BOOTSTRAP")
    if not 12<=hours<=16:raise ValueError("ONLY_OWNER_AUTHORIZED_12_TO_16H_WINDOW")
    with c:
        if not meta_get(c,"end_ms"):
            start=now_ms()
            meta_set(c,"end_ms",start+int(hours*3600*1000))
            meta_set(c,"last_new_entry_deadline_ms",start+int((hours-1.2)*3600*1000))
            meta_set(c,"status","RUNNING")
            event(c,"RESEARCH_STARTED",start_ms=start,end_ms=start+hours*3600000,
                  max_total_entries=3,training_days=15,market_candle_seconds=60,
                  mode="PUBLIC_FEED_ONLY_NO_ORDERS")
    model=None
    manifest=None
    fails=0
    while now_ms()<meta_get(c,"end_ms"):
        try:
            latest=poll_new(c)
            if now_ms()-(latest+ONE)>300000:
                raise RuntimeError("CANDLE_FEED_STALE_FAIL_CLOSED")
            train_asof=meta_get(c,"last_model_train_ms",0)
            today=datetime.now(timezone.utc).date()
            modeldate=datetime.fromtimestamp(train_asof/1000,timezone.utc).date() if train_asof else None
            if modeldate!=today:
                # Training as-of minute is most recent COMMON closed candle;
                # no label outcome later than model fit cutoff.
                model,manifest=train(c,root,cutoff_ms=latest+ONE)
            elif model is None:
                p=Path(meta_get(c,"current_model_path"))
                manifest=json.loads((p.parent/"manifest.json").read_text())
                if sha(p)!=manifest["model_sha256"]:
                    raise RuntimeError("SAVED_DAILY_MODEL_HASH_MISMATCH")
                model=joblib.load(p) # Only own exact verified local artifact.
            last=meta_get(c,"last_processed_open_ms")
            if latest-last>ONE*10:
                raise RuntimeError("CANDLE_DATA_GAP_OVER_10MIN_FAIL_CLOSED")
            for t in range(last+ONE,latest+ONE,ONE):
                with c:handle_minute(c,root,t,model,manifest)
            with c:
                meta_set(c,"source_last_verified_at_ms",now_ms())
            status(c,root)
            fails=0
        except Exception as ex:
            fails+=1
            LOG.exception("PUBLIC_FEED_OR_MODEL_RESEARCH_HOLD")
            with c:event(c,"FAIL_CLOSED_SOURCE",error=repr(ex),consecutive_errors=fails)
            status(c,root,{"last_error":str(ex),"consecutive_errors":fails})
            if fails>=8:
                with c:meta_set(c,"status","SOURCE_HALTED_NO_NEW_ENTRIES")
                status(c,root,{"status":"SOURCE_HALTED_NO_NEW_ENTRIES"})
                # The process ends; preserve open positions in JSON and
                # audit log rather than inventing terminal fills.
                raise RuntimeError("PUBLIC_FEED_FAILED_EIGHT_POLLS_HALTED") from ex
        time.sleep(12)
    with c:
        pos=meta_get(c,"positions",{})
        meta_set(c,"pending",None)
        if pos:
            # Stop new entries early enough for normal 60min exits.
            event(c,"RESEARCH_END_OPEN_POSITIONS_UNVERIFIED",positions=list(pos))
            meta_set(c,"status","ENDS_WITH_UNRESOLVED_POSITION")
        else:
            meta_set(c,"status","COMPLETE")
            event(c,"RESEARCH_END",virtual_trades=meta_get(c,"new_entry_count"),
                  net_pnl_without_funding=meta_get(c,"realized_usdt"))
    status(c,root)
    c.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--bootstrap",action="store_true")
    p.add_argument("--serve",action="store_true")
    p.add_argument("--hours",type=float,default=15)
    a=p.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    if a.bootstrap==a.serve:raise ValueError("CHOOSE_EXACTLY_BOOTSTRAP_OR_SERVE")
    if a.bootstrap:bootstrap(a.run)
    else:service(a.run,hours=a.hours)


if __name__=="__main__":main()
