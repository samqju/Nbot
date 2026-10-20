"""Public-only USD-M observation feed for the reusable paper runtime.

Current exchangeInfo is explicitly NOT a historical universe registry. This
adapter has no signed endpoints, API keys, account calls or live order methods.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
import json
import time
import urllib.parse
import urllib.request
from ..data import Bar,BAR_MS
from ..features import market_features,proposals,btc_regime,legacy_proposals


class PublicFeed:
    def __init__(self,root="https://fapi.binance.com",workers=3):
        if root!="https://fapi.binance.com" or not 1<=workers<=4:
            raise ValueError("PUBLIC_FEED_SCOPE_INVALID")
        self.root=root
        self.workers=workers

    def get(self,path,params=None):
        if path not in ("/fapi/v1/time","/fapi/v1/exchangeInfo","/fapi/v1/klines","/fapi/v1/ticker/bookTicker"):
            raise PermissionError("PUBLIC_ENDPOINT_ONLY")
        url=self.root+path+("?"+urllib.parse.urlencode(params) if params else "")
        with urllib.request.urlopen(url,timeout=20) as response:
            data=response.read(8*1024*1024)
            return json.loads(data)

    def snapshot(self):
        clock=int(self.get("/fapi/v1/time")["serverTime"])
        decision=clock//BAR_MS*BAR_MS
        info=self.get("/fapi/v1/exchangeInfo")
        symbols=sorted(s["symbol"] for s in info["symbols"] if s["contractType"]=="PERPETUAL"
                       and s["quoteAsset"]=="USDT" and s["marginAsset"]=="USDT" and s["status"]=="TRADING")
        if not symbols or len(symbols)>2000:raise ValueError("INVALID_CURRENT_UNIVERSE_SIZE")
        bars={};holds={}
        def fetch(symbol):
            raw=self.get("/fapi/v1/klines",{"symbol":symbol,"interval":"5m",
                "startTime":decision-151*BAR_MS,"endTime":decision-1,"limit":200})
            series=[Bar(int(r[0]),*(float(v) for v in r[1:6])) for r in raw if int(r[0])+BAR_MS<=decision]
            if len(series)<51 or series[-1].t!=decision-BAR_MS:
                raise ValueError("CAUSAL_HISTORY_NOT_READY")
            if any(b.t-a.t!=BAR_MS for a,b in zip(series,series[1:])):
                raise ValueError("HISTORICAL_CANDLE_GAP")
            return series
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            jobs={pool.submit(fetch,s):s for s in symbols}
            for job in as_completed(jobs):
                symbol=jobs[job]
                try:bars[symbol]=job.result()
                except Exception as exc:holds[symbol]=type(exc).__name__
        if "BTCUSDT" not in bars:raise ValueError("BTC_SOURCE_HOLD")
        book=self.get("/fapi/v1/ticker/bookTicker")
        quotes={r["symbol"]:(float(r["bidPrice"])+float(r["askPrice"]))/2 for r in book
                if r["symbol"] in bars and float(r["bidPrice"])>0 and float(r["askPrice"])>=float(r["bidPrice"])}
        now=int(self.get("/fapi/v1/time")["serverTime"])
        digest=sha256(json.dumps({"decision":decision,"bars":{s:[vars(b) for b in bs] for s,bs in sorted(bars.items())},
                                  "exchange_info":info,"book":book},sort_keys=True).encode()).hexdigest()
        btc=bars["BTCUSDT"];bt=[b.t for b in btc]
        candidates=[];watch=[]
        for symbol,series in sorted(bars.items()):
            x=market_features(series,len(series)-1,btc,bt)
            base={"symbol":symbol,"regime":btc_regime(x),"features":json.dumps(x,sort_keys=True),"source_hash":digest}
            watch.append({**base,"review_ms":decision})
            for family,side in proposals(series,len(series)-1,x)+legacy_proposals(series).get(len(series)-1,[]):
                candidates.append({**base,"decision_ms":decision,"family":family,"side":side})
        return {"decision_ms":decision,"now_ms":now,"candidates":candidates,"watch":watch,
                "quotes":quotes,"bars":bars,"observed_symbols":symbols,"source_holds":holds,
                "authority":"CURRENT_PUBLIC_PAPER_INPUT_NOT_HISTORICAL_ELIGIBILITY_OR_FILL_PROOF"}
