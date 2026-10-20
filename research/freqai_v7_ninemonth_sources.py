#!/usr/bin/env python3
"""Source-preserving 3-coin 2025 warmup for full Jan-Sep 2026 daily replay.

Downloads only 3 symbols × July-Dec 2025 × [5m kline,funding] from
Binance Vision, verifying every exchange-published SHA256 checksum.
Reuses the existing *checked* Jan-Sep 2026 archives by symlink without
modifying them. This allows a 180d trailing training window at Jan 1.

Archive presence is NOT proof of historical contract tradeability. No
orders, exchange secrets or public-rest private calls.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

from nbot_v7.archive import download_inventory, ROOT
from nbot_v7.experiment import month_start,add_months
from nbot_v7.lab import build_archive_database

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
OLD_MONTHS=tuple(f"2025-{m:02d}" for m in range(7,13))
NEW_MONTHS=tuple(f"2026-{m:02d}" for m in range(1,10))
ALL_MONTHS=OLD_MONTHS+NEW_MONTHS


def source_key(symbol,kind,month):
    name=symbol+"-"+kind+"-"+month+".zip"
    if kind=="5m":
        return f"data/futures/um/monthly/klines/{symbol}/5m/{name}"
    if kind=="fundingRate":
        return f"data/futures/um/monthly/fundingRate/{symbol}/{name}"
    raise ValueError("INVALID_SOURCE_TYPE")


def head_bytes(key):
    url=ROOT+"/"+key
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,method="HEAD")
            with urllib.request.urlopen(req,timeout=40) as stream:
                if stream.status!=200:
                    raise ValueError("ARCHIVE_HEAD_NOT_HTTP_200")
                n=int(stream.headers["Content-Length"])
                if not 100<=n<=1_000_000_000:
                    raise ValueError("ARCHIVE_SIZE_UNREASONABLE")
                return n
        except Exception:
            if attempt==2:raise


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(2**20),b""):
            h.update(block)
    return h.hexdigest()


def published_sha(key):
    with urllib.request.urlopen(ROOT+"/"+key+".CHECKSUM",timeout=45) as r:
        checksum=r.read(1024).decode("ascii").split()[0].lower()
    if len(checksum)!=64 or not all(c in "0123456789abcdef" for c in checksum):
        raise ValueError("INVALID_BINANCE_CHECKSUM:"+key)
    return checksum


def prepare(previous_archive, root):
    archive=root/"archives"
    root.mkdir(parents=True,exist_ok=True)
    archive.mkdir(exist_ok=True)
    objects=[
        {"key":source_key(s,k,mo),"symbol":s,"timeframe":k,
         "month":mo,"bytes":head_bytes(source_key(s,k,mo))}
        for s in SYMBOLS for k in ("5m","fundingRate") for mo in OLD_MONTHS
    ]
    manifest={"objects":objects,"scope":"THREE_COINS_6MO_2025_WARMUP_ONLY",
              "exchange":"BINANCE_VISION_PUBLIC_ZIPS",
              "historical_listing_verified":False}
    manifest_path=root/"source_2025_manifest.json"
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if old!=manifest:raise ValueError("PREVIOUS_SOURCE_MANIFEST_CHANGED")
    else:
        manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    completed=download_inventory(manifest,archive,max_gib=2.0)
    receipts={"2025":completed["manifest_entries"],"2026":{}}
    # Jan-Sep 2026 are the old source-checked 54 ZIPs. Verify again
    # against the published Binance SHA at this exact handover, then link.
    for s in SYMBOLS:
        (archive/s).mkdir(parents=True,exist_ok=True)
        for k in ("5m","fundingRate"):
            for mo in NEW_MONTHS:
                name=f"{s}-{k}-{mo}.zip"
                existing=previous_archive/s/name
                if not existing.is_file():
                    raise FileNotFoundError("MISSING_ORIGINAL_CHECKSUM_VERIFIED_SOURCE:"+str(existing))
                expected=published_sha(source_key(s,k,mo))
                observed=digest(existing)
                if expected!=observed:
                    raise ValueError("2026_EXISTING_PUBLIC_ARCHIVE_HASH_MISMATCH:"+name)
                dst=archive/s/name
                if dst.is_symlink():
                    if dst.resolve()!=existing.resolve():
                        raise ValueError("WRONG_SOURCE_SYMLINK")
                elif dst.exists():
                    raise FileExistsError("REFUSE_EXISTING_SOURCE_REPLACEMENT")
                else:
                    dst.symlink_to(existing.resolve())
                receipts["2026"][name]={"sha256":observed,"verified_against_published_binance_checksum":True}
    csvpath=root/"three_coin_archive_observed_registry.csv"
    if csvpath.exists():raise FileExistsError("REGISTRY_ALREADY_EXISTS_DO_NOT_CLOBBER")
    with csvpath.open("x",newline="") as out:
        writer=csv.writer(out)
        writer.writerow(("symbol","from_ms","to_ms","evidence_sha256","source_grade"))
        for s in SYMBOLS:
            symbol_receipts={k:v for k,v in completed["manifest_entries"].items()
                             if f"/{s}/" in k}
            symbol_receipts.update({k:v for k,v in receipts["2026"].items() if k.startswith(s+"-")})
            evidence=hashlib.sha256(json.dumps(symbol_receipts,sort_keys=True).encode()).hexdigest()
            writer.writerow((s,month_start("2025-07"),month_start("2026-10"),
                evidence,"ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE"))
    (root/"source_receipts.json").write_text(json.dumps(receipts,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"stage":"PREPARED_WITH_CHECKSUMS","new_files":len(objects),
                     "existing_files_sha_reverified":len(receipts["2026"]),
                     "registry":str(csvpath),"total_2025_bytes":sum(x["bytes"] for x in objects)},indent=2))


def build(root, *,resume=False):
    dest=root/"labeled_2025jul_to_2026sep.sqlite"
    result=build_archive_database(
        root/"archives",root/"three_coin_archive_observed_registry.csv",
        dest,month_start("2025-07"),month_start("2026-10"),set(ALL_MONTHS),
        allow_archive_observed=True,resume=resume,max_db_gib=5.0,min_free_gib=8.0)
    if result["symbols_scanned"]!=3 or result["funding_covered_symbols"]!=3:
        raise ValueError("THREE_COIN_SOURCE_FUNDING_COVERAGE_INCOMPLETE")
    (root/"build_complete_report.json").write_text(json.dumps({
        **result,"db_sha256":digest(dest),"scope":"FULL_2026_9MONTH_WITH_2025_180DAY_HISTORY",
        "historical_listing_verified":False},indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior-archive",type=Path,required=True)
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--step",choices=("prepare","build"),required=True)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    if a.step=="prepare":prepare(a.prior_archive,a.root)
    else:build(a.root,resume=a.resume)

if __name__=="__main__":main()
