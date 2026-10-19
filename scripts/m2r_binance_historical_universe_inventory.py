"""Read-only Binance Vision archive *object metadata* discovery for V6.

No private API / no orders / no OHLCV files downloaded. Does not infer exact
historical Binance contract status or spreads from an archive filename.
Historical symbols with no 1h candles are NOT assumed to be actively traded.
This is a preliminary broad-market inventory for an as-of universe study.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json,re,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from time import sleep
BASE="https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
PREFIX="data/futures/um/monthly/klines/"
SYMBOL_RE=re.compile(r"^[A-Z0-9]+USDT$")


def xml_get(params):
    url=BASE+"?"+urllib.parse.urlencode(params)
    last=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"NbotV6-historical-readonly-research/1.0"})
            with urllib.request.urlopen(req,timeout=20) as response:
                if response.status!=200:
                    raise RuntimeError(f"ARCHIVE_HTTP_{response.status}")
                data=response.read(3000000)
            return ET.fromstring(data)
        except (OSError,ET.ParseError) as exc:
            last=exc
            sleep(0.4*(2**attempt))
    raise RuntimeError(f"S3_ARCHIVE_METADATA_UNAVAILABLE {last}")


def objects(prefix,delimiter=None):
    marker=None
    loops=0
    while True:
        params={"list-type":"2","prefix":prefix,"max-keys":"1000"}
        if delimiter:params["delimiter"]=delimiter
        if marker:params["continuation-token"]=marker
        root=xml_get(params)
        if delimiter:
            yield from (n.text for n in root.findall(".//{*}CommonPrefixes/{*}Prefix") if n.text)
        else:
            yield from (n.text for n in root.findall(".//{*}Contents/{*}Key") if n.text)
        truncated=root.findtext(".//{*}IsTruncated","false")
        if truncated.lower()!="true":break
        marker=root.findtext(".//{*}NextContinuationToken")
        loops+=1
        if not marker or loops>100:
            raise RuntimeError("S3_DIRECTORY_PAGINATION_BROKEN")


def symbol_1h_listing(sym):
    prefix=PREFIX+sym+"/1h/"
    keys=list(objects(prefix))
    wanted=[]
    for x in keys:
        pattern=sym+"-1h-2026-"
        if not x.startswith(prefix+pattern) or not x.endswith(".zip"):
            continue
        yyyymm=x[len(prefix+sym+"-1h-"):][:7]
        if re.fullmatch(r"2026-(0[1-9])",yyyymm):
            wanted.append(yyyymm)
    return sorted(set(wanted))


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--out",required=True,type=Path)
    a.add_argument("--threads",type=int,default=8)
    args=a.parse_args()
    if not 1<=args.threads<=12: raise RuntimeError("MAX_12_PUBLIC_ARCHIVE_METADATA_THREADS")
    prefixes=list(objects(PREFIX,delimiter="/"))
    names=sorted(set(
        p[len(PREFIX):].strip("/")
        for p in prefixes
        if p.startswith(PREFIX) and SYMBOL_RE.fullmatch(p[len(PREFIX):].strip("/"))
    ))
    rows={}
    errors={}
    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        jobs={ex.submit(symbol_1h_listing,n):n for n in names}
        for future in as_completed(jobs):
            name=jobs[future]
            try:
                months=future.result()
                if months:rows[name]=months
            except Exception as exc:
                errors[name]=str(exc)[:250]
    report={
        "scope":"Public Binance Vision S3 USD-M monthly 1h ZIP *metadata* only, not fetched market history or tradeability snapshots",
        "fetched_at_utc":datetime.now(timezone.utc).isoformat(),
        "all_ever_archived_usdt_suffix_candidate_directory_count":len(names),
        "candidate_directory_symbols_with_any_Jan_Sep_2026_1h_zip":len(rows),
        "archive_directories_failed_to_audit":errors,
        "no_historical_point_in_time_contract_status_certified":True,
        "no_real_spread_or_order_book_data_present":True,
        "no_asof_market_whitelist_activation":True,
        "no_trading_orders_paper_or_live":True,
        "candidates_and_archive_months":dict(sorted(rows.items())),
    }
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print("BINANCE_VISION_SYMBOL_ARCHIVE_METADATA",
          "all_USDT_dirs",len(names),"2026_archived",len(rows),
          "metadata_failures",len(errors),flush=True)


if __name__=="__main__":main()
