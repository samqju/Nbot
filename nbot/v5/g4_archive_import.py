"""Offline Binance USD-M *daily archive* aggTrade integrity and CSV importer.

Only caller-supplied ZIP bytes and companion .CHECKSUM bytes. No network, WSS,
SQLite, exchange accounts or disk mutation. This module authenticates byte
integrity relative to the supplied CHECKSUM; downloading both artifacts from
an authenticated original Binance endpoint and retaining transport receipts
is a separate independent evidence gate. Intended for bounded pilot chunks.
"""
from __future__ import annotations

import csv
from datetime import date as date_type, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, TextIOWrapper
import json
import re
from typing import Mapping
from zipfile import BadZipFile, ZipFile

_MAX_COMPRESSED=50_000_000
_MAX_UNCOMPRESSED=250_000_000
_MAX_ROWS=500_000
_SYMBOL=re.compile(r"[A-Z0-9]{3,24}\Z")
_SHA=re.compile(r"[a-f0-9]{64}\Z")
_HEADER={"agg_trade_id","price","quantity","first_trade_id","last_trade_id",
        "transact_time","is_buyer_maker"}


def _norm_date(date: str) -> str:
    if not isinstance(date,str):
        raise ValueError("G4_ARCHIVE_DATE_INVALID")
    try:
        v=date_type.fromisoformat(date)
    except ValueError as exc:
        raise ValueError("G4_ARCHIVE_DATE_INVALID") from exc
    if v.isoformat()!=date:
        raise ValueError("G4_ARCHIVE_DATE_INVALID")
    return date


def _name(symbol: str, on_date: str) -> str:
    if not isinstance(symbol,str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("G4_ARCHIVE_SYMBOL_INVALID")
    return f"{symbol}-aggTrades-{_norm_date(on_date)}"


def _digest_records(rows: list[dict]) -> str:
    return sha256(json.dumps(rows,sort_keys=True,separators=(",",":"),
                             ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def ingest_verified_um_daily_zip(*, archive_bytes: bytes,
                                  checksum_bytes: bytes,
                                  symbol: str, on_date: str,
                                  captured_at_ms: int) -> tuple[dict,list[dict]]:
    name=_name(symbol,on_date)
    if type(captured_at_ms) is not int or captured_at_ms<=0:
        raise ValueError("G4_ARCHIVE_CAPTURE_CLOCK_INVALID")
    day_start=int(datetime.combine(date_type.fromisoformat(on_date),
                 datetime.min.time(),timezone.utc).timestamp()*1000)
    day_end=day_start+86400000
    if captured_at_ms<day_end:
        raise ValueError("G4_ARCHIVE_NOT_YET_FINALIZED")
    if not isinstance(archive_bytes,bytes) or not 0<len(archive_bytes)<=_MAX_COMPRESSED:
        raise ValueError("G4_ARCHIVE_SIZE_UNSUPPORTED")
    if not isinstance(checksum_bytes,bytes) or not 0<len(checksum_bytes)<500:
        raise ValueError("G4_CHECKSUM_SOURCE_MISSING")
    expected_filename=name+".zip"
    try:
        checks=checksum_bytes.decode("ascii").strip().splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("G4_CHECKSUM_INVALID") from exc
    if len(checks)!=1:
        raise ValueError("G4_CHECKSUM_INVALID")
    parts=checks[0].strip().split()
    if len(parts)!=2 or not _SHA.fullmatch(parts[0].lower()) or parts[1].lstrip("*")!=expected_filename:
        raise ValueError("G4_CHECKSUM_IDENTITY_INVALID")
    actual=sha256(archive_bytes).hexdigest()
    if actual!=parts[0].lower():
        raise ValueError("G4_ARCHIVE_SHA256_MISMATCH")
    try:
        with ZipFile(BytesIO(archive_bytes)) as z:
            members=z.infolist()
            if (len(members)!=1 or members[0].filename!=name+".csv"
                    or members[0].is_dir() or members[0].file_size>_MAX_UNCOMPRESSED
                    or members[0].flag_bits & 1):
                raise ValueError("G4_ARCHIVE_UNSUPPORTED_CONTENT")
            with z.open(members[0]) as inp:
                with TextIOWrapper(inp,encoding="utf-8-sig",newline="") as stream:
                    parsed=csv.reader(stream)
                    out=[]
                    previous_agg=previous_last=previous_time=None
                    underlying_gaps=[]
                    for i,values in enumerate(parsed):
                        if len(values)!=7:
                            raise ValueError("G4_ARCHIVE_CSV_SHAPE_INVALID")
                        if i==0 and (values[0] in ("agg_trade_id","aggTradeId","Aggregate tradeId")):
                            continue
                        if len(out)>=_MAX_ROWS:
                            raise ValueError("G4_ARCHIVE_ROW_LIMIT")
                        try:
                            a,first,last,time=(int(values[j]) for j in (0,3,4,5))
                        except (ValueError,TypeError) as exc:
                            raise ValueError("G4_ARCHIVE_CSV_INTEGER_INVALID") from exc
                        if not (day_start <= time < day_end):
                            raise ValueError("G4_ARCHIVE_TRADE_DATE_MISMATCH")
                        try:
                            price,qty=Decimal(values[1]),Decimal(values[2])
                        except InvalidOperation as exc:
                            raise ValueError("G4_ARCHIVE_PRICE_QTY_INVALID") from exc
                        if (not price.is_finite() or price<=0 or
                                not qty.is_finite() or qty<=0 or
                                max(len(values[1]),len(values[2]))>80):
                            raise ValueError("G4_ARCHIVE_PRICE_QTY_INVALID")
                        truth=values[6].strip().lower()
                        if truth not in ("true","false"):
                            raise ValueError("G4_ARCHIVE_CSV_MAKER_FLAG_INVALID")
                        row={"a":a,"p":values[1],"q":values[2],"f":first,
                             "l":last,"T":time,"m":truth=="true"}
                        if min(a,first,last,time)<0 or first>last:
                            raise ValueError("G4_ARCHIVE_CSV_SEQUENCE_INVALID")
                        if previous_agg is not None:
                            if a!=previous_agg+1 or time<previous_time or first<=previous_last:
                                raise ValueError("G4_ARCHIVE_CSV_SEQUENCE_INVALID")
                            if first>previous_last+1:
                                underlying_gaps.append({
                                    "csv_data_row":len(out)+1,
                                    "previous_last_trade_id":previous_last,
                                    "next_first_trade_id":first,
                                    "missing_trade_ids":first-previous_last-1,
                                })
                        out.append(row)
                        previous_agg,previous_last,previous_time=a,last,time
    except (BadZipFile,RuntimeError,UnicodeError) as exc:
        raise ValueError("G4_ARCHIVE_BAD_ZIP_OR_ENCODING") from exc
    if len(out)<2:
        raise ValueError("G4_ARCHIVE_TOO_FEW_TRADES")

    root="https://data.binance.vision/data/futures/um/daily/aggTrades"
    url=f"{root}/{symbol}/{expected_filename}"
    manifest={
        "source_grade":"ORIGINAL_BINANCE_PUBLIC_AGGTRADES",
        "symbol":symbol,"archive_date_utc":on_date,
        "archive_url":url,"checksum_url":url+".CHECKSUM",
        "captured_at_ms":captured_at_ms,
        "archive_sha256":actual,
        "checksum_source_sha256":sha256(checksum_bytes).hexdigest(),
        "rows_sha256":_digest_records(out),
        "first_agg_id":out[0]["a"],"last_agg_id":out[-1]["a"],
        "row_count":len(out),
        "agg_id_continuity_verified":True,
        "underlying_trade_id_gap_count":len(underlying_gaps),
        "underlying_trade_ids_missing":sum(g["missing_trade_ids"] for g in underlying_gaps),
        "underlying_gap_examples":underlying_gaps[:10],
        "underlying_gap_manifest_sha256":_digest_records(underlying_gaps),
        "all_underlying_trade_ids_contiguous":not underlying_gaps,
        "research_path_grade":"HOLD_UNDERLYING_TRADE_ID_GAPS" if underlying_gaps
                          else "SOURCE_ONLY_NEEDS_INDEPENDENT_ORIGIN",
        # Only source-byte integrity checked relative to checksum; caller must
        # independently attest original HTTPS download origin and custody.
        "original_archive_verified":False,
        "origin_and_custody_independently_verified":False,
    }
    return manifest,out


def main() -> int:
    """CLI verifies an existing OFFLINE archive pair; read-only, never downloads."""
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser(description="G4 original public archive integrity (OFFLINE)")
    p.add_argument("--zip",required=True)
    p.add_argument("--checksum",required=True)
    p.add_argument("--symbol",required=True)
    p.add_argument("--date",required=True)
    p.add_argument("--captured-at-ms",required=True,type=int)
    args=p.parse_args()
    try:
        manifest,rows=ingest_verified_um_daily_zip(
            archive_bytes=Path(args.zip).read_bytes(),
            checksum_bytes=Path(args.checksum).read_bytes(),
            symbol=args.symbol,on_date=args.date,captured_at_ms=args.captured_at_ms)
        manifest["first_trade_time_ms"]=rows[0]["T"]
        manifest["last_trade_time_ms"]=rows[-1]["T"]
        manifest["historical_price_only"]=True
        manifest["economic_outcomes"]=0
        manifest["order_authority"]="NONE"
        print(json.dumps(manifest,sort_keys=True))
        return 0
    except (OSError,ValueError) as exc:
        print(json.dumps({"state":"HOLD","reason":str(exc),
                          "economic_outcomes":0,"order_authority":"NONE"},
                         sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
