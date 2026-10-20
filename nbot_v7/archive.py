"""Public Binance Vision nine-month archive inventory/downloader (OFFLINE ONLY).

Archive names are NOT proof of historical live contract listing/tradability.
Downloads require explicit --download and a bounded maximum byte budget.
No private exchange API, trading credentials, VPS process or orders.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime,timezone

from .experiment import month_start,add_months

ROOT="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
BASE="data/futures/um/monthly/klines/"
_SYMBOL=re.compile(r"^[A-Z0-9]+USDT$")
MAX_PUBLIC_KEYS=500_000

def keys(prefix: str, *, directories: bool=False):
    """Read paginated public S3 bucket XML. One shared source, no current-pair filter."""
    token=None
    count=0
    while True:
        params={"list-type":"2","prefix":prefix,"max-keys":1000}
        if directories:params["delimiter"]="/"
        if token:params["continuation-token"]=token
        url=ROOT+"?"+urllib.parse.urlencode(params)
        err=None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url,headers={"User-Agent":"NbotV7-public-archive-research/0.1"}),
                    timeout=45) as response:
                    if response.status!=200:
                        raise OSError(f"S3_{response.status}")
                    xml=response.read(4_000_000)
                doc=ET.fromstring(xml)
                break
            except (OSError,ET.ParseError) as ex:
                err=ex
                time.sleep(.4*(attempt+1))
        else:
            raise RuntimeError(f"PUBLIC_S3_LISTING_FAILED: {err}")
        ns="{http://s3.amazonaws.com/doc/2006-03-01/}"
        if directories:
            for item in doc.findall(f".//{ns}CommonPrefixes/{ns}Prefix"):
                if item.text:
                    yield item.text,None
                    count+=1
        else:
            for item in doc.findall(f".//{ns}Contents"):
                key=item.findtext(f"{ns}Key")
                size=item.findtext(f"{ns}Size")
                if key and size:
                    yield key,int(size)
                    count+=1
        if count>MAX_PUBLIC_KEYS:
            raise RuntimeError("EXCESSIVE_PUBLIC_OBJECT_LISTING")
        if doc.findtext(f"{ns}IsTruncated","false").lower()!="true":
            return
        token=doc.findtext(f"{ns}NextContinuationToken")
        if not token:
            raise RuntimeError("PUBLIC_S3_PAGINATION_BROKEN")

def months_after(start_month:str,n:int=9)->list[str]:
    a=month_start(start_month)
    return [datetime.fromtimestamp(add_months(a,i)/1000,timezone.utc).strftime("%Y-%m") for i in range(n)]

def inventory(start_month:str)->dict:
    months=months_after(start_month)
    symbols=[]
    rows=[]
    for prefix,_ in keys(BASE,directories=True):
        symbol=prefix[len(BASE):].strip("/")
        if not _SYMBOL.fullmatch(symbol):
            continue
        symbols.append(symbol)
        for interval in ("5m",):
            base=f"{prefix}{interval}/"
            for k,size in keys(base):
                name=k.rsplit("/",1)[-1]
                found=re.fullmatch(rf"{re.escape(symbol)}-{interval}-(\d{{4}}-\d{{2}})\.zip",name)
                if found and found.group(1) in months:
                    rows.append({"symbol":symbol,"month":found.group(1),
                                 "key":k,"bytes":size,"timeframe":interval})
    # Enumerate exchange funding settlement archives alongside candles.
    for symbol in symbols:
        funding_prefix=f"data/futures/um/monthly/fundingRate/{symbol}/"
        for k,size in keys(funding_prefix):
            name=k.rsplit("/",1)[-1]
            found=re.fullmatch(rf"{re.escape(symbol)}-fundingRate-(\d{{4}}-\d{{2}})\.zip",name)
            if found and found.group(1) in months:
                rows.append({"symbol":symbol,"month":found.group(1),
                             "key":k,"bytes":size,"timeframe":"fundingRate"})
    rows.sort(key=lambda x:(x["symbol"],x["month"],x["timeframe"]))
    return {
        "schema":"v7-public-archive-inventory-v1",
        "captured_utc":datetime.now(timezone.utc).isoformat(),
        "months":months,
        "symbol_directories_found":len(symbols),
        "available_zip_objects":len(rows),
        "klines_zip_objects":sum(r["timeframe"]=="5m" for r in rows),
        "funding_zip_objects":sum(r["timeframe"]=="fundingRate" for r in rows),
        "observed_zip_bytes":sum(r["bytes"] for r in rows),
        "source":ROOT,
        "historical_contract_active_status_verified":False,
        "no_trading_authority":True,
        "objects":rows,
    }

def download_inventory(manifest:dict, destination:Path, max_gib:float,*,resume:bool=True)->dict:
    budget=int(max_gib*1024**3)
    if budget<=0:raise ValueError("POSITIVE_DOWNLOAD_BUDGET_REQUIRED")
    planned=sum(r["bytes"] for r in manifest["objects"])
    if planned>budget:
        raise RuntimeError(f"DISK_BUDGET_EXCEEDED: {planned} > {budget}")
    destination.mkdir(parents=True,exist_ok=True)
    entries={}
    for r in manifest["objects"]:
        kind=r["timeframe"]
        filename=(r["symbol"]+"-"+("5m" if kind=="5m" else "fundingRate")+"-"+r["month"]+".zip")
        path=destination/r["symbol"]/filename
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.stat().st_size!=r["bytes"]:
                raise RuntimeError(f"EXISTING_FILE_SIZE_MISMATCH: {path}")
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            entries[r["key"]]={"sha256":digest,"bytes":r["bytes"],"cached":True}
            continue
        tmp=path.with_suffix(".partial")
        if tmp.exists():
            raise RuntimeError(f"PARTIAL_DOWNLOAD_NEEDS_REVIEW: {tmp}")
        req=urllib.request.Request(ROOT+"/"+urllib.parse.quote(r["key"],safe="/"),
                                   headers={"User-Agent":"NbotV7-public-archive-research/0.1"})
        h=hashlib.sha256()
        read=0
        try:
            with urllib.request.urlopen(req,timeout=90) as response, tmp.open("xb") as out:
                while True:
                    block=response.read(1_048_576)
                    if not block:break
                    out.write(block);h.update(block);read+=len(block)
                    if read>r["bytes"]:
                        raise RuntimeError("DOWNLOAD_EXCEEDS_LISTED_SIZE")
            if read!=r["bytes"]:
                raise RuntimeError("DOWNLOAD_INCOMPLETE")
            tmp.replace(path)
            entries[r["key"]]={"sha256":h.hexdigest(),"bytes":read,"cached":False}
        except Exception:
            # Keep explicit partial evidence for manual review, do not hide errors.
            raise
    return {"files":len(entries),"manifest_entries":entries,
            "source":"BINANCE_VISION_PUBLIC_ZIPS_UNVERIFIED_TRADING_ELIGIBILITY"}

def main(argv=None):
    p=argparse.ArgumentParser(description="Read-only Binance Vision nine-month data inventory")
    p.add_argument("--start-month",required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--download",action="store_true",help="Explicitly download public ZIPs")
    p.add_argument("--archive",type=Path)
    p.add_argument("--max-gib",type=float,default=20)
    a=p.parse_args(argv)
    if a.manifest.exists():
        raise FileExistsError("REFUSE_OVERWRITE_SOURCE_MANIFEST")
    data=inventory(a.start_month)
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    a.manifest.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    if a.download:
        if a.archive is None:raise ValueError("ARCHIVE_DESTINATION_REQUIRED")
        finished=download_inventory(data,a.archive,a.max_gib)
        finish=a.manifest.with_name(a.manifest.stem+"-download-hashes.json")
        if finish.exists():raise FileExistsError(finish)
        finish.write_text(json.dumps(finished,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in data.items() if k!="objects"},indent=2))

if __name__=="__main__":main()
