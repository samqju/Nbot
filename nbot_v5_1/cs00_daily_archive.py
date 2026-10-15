"""CS-00 official USD-M daily aggregate-trade archive verifier (OFFLINE).

The caller supplies locally held Binance public-data ZIP and accompanying
.CHECKSUM text. No downloads occur. Checks expected canonical symbol/date
filenames, SHA256 of the ZIP, zip member, safe CSV format and page-sized
incremental conversion for the existing HistoricalAggTradeRecovery verifier.
The digest alone does NOT sign exchange origin or historical bookTicker costs.
"""
from __future__ import annotations
import csv
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import stat
import zipfile

from .cs00_history_recovery import HistoricalAggTradeRecovery,SourceRecoveryHold
VERSION="NBOT_V5_1_CS00_PUBLIC_DAILY_AGGTRADE_ARCHIVE_V1"
HEADER=("agg_trade_id","price","quantity","first_trade_id","last_trade_id",
        "transact_time","is_buyer_maker")
MAX_COMPRESSED=256*1024*1024
MAX_UNCOMPRESSED=2*1024*1024*1024
MAX_ROWS_TO_SCAN=4_000_000

class DailyArchiveHold(ValueError):pass

def archive_paths(symbol:str,day:str):
    if (type(symbol) is not str or not re.fullmatch(r"[A-Z0-9]{3,24}USDT",symbol)
            or type(day) is not str):
        raise DailyArchiveHold("CS00_ARCHIVE_SYMBOL_DAY_INVALID")
    try:
        if date.fromisoformat(day).isoformat()!=day:raise ValueError("FORMAT")
    except ValueError as e:
        raise DailyArchiveHold("CS00_ARCHIVE_DAY_INVALID") from e
    name=f"{symbol}-aggTrades-{day}"
    return (f"https://data.binance.vision/data/futures/um/daily/aggTrades/{symbol}/{name}.zip",
            f"{name}.zip.CHECKSUM")

def _checked_zip(path:Path,checksum:bytes,symbol:str,day:str):
    url,ck=archive_paths(symbol,day)
    name=url.rsplit("/",1)[-1]
    if (not isinstance(path,Path) or not path.is_absolute()
            or path.is_symlink() or path.name!=name or not path.is_file()):
        raise DailyArchiveHold("CS00_ARCHIVE_ZIP_UNTRUSTED_PATH")
    st=path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size>MAX_COMPRESSED:
        raise DailyArchiveHold("CS00_ARCHIVE_COMPRESSED_TOO_LARGE")
    if type(checksum) is not bytes or len(checksum)>256:
        raise DailyArchiveHold("CS00_ARCHIVE_CHECKSUM_INVALID")
    try:cs=checksum.decode("ascii").strip()
    except UnicodeError as e:raise DailyArchiveHold("CS00_ARCHIVE_CHECKSUM_ENCODING") from e
    if not re.fullmatch("[a-fA-F0-9]{64}  "+re.escape(name),cs):
        raise DailyArchiveHold("CS00_ARCHIVE_CHECKSUM_FORMAT")
    h=sha256()
    with open(path,"rb") as f:
        while True:
            b=f.read(1024*1024)
            if not b:break
            h.update(b)
    if h.hexdigest().lower()!=cs[:64].lower():
        raise DailyArchiveHold("CS00_ARCHIVE_ZIP_CHECKSUM_MISMATCH")
    return name

def replay_official_daily_zip(*,zip_path:Path,checksum_bytes:bytes,
                              symbol:str,day:str,
                              recovery:HistoricalAggTradeRecovery,
                              received_at_ms:int):
    name=_checked_zip(zip_path,checksum_bytes,symbol,day)
    if (not isinstance(recovery,HistoricalAggTradeRecovery)
            or recovery.symbol!=symbol
            or type(received_at_ms) is not int
            or received_at_ms<recovery.gap_end_ms or
            received_at_ms<recovery.now_ms):
        raise DailyArchiveHold("CS00_ARCHIVE_RECOVERY_SCOPE_INVALID")
    recovery.advance_clock(received_at_ms)
    # No bare authoritative source grade: bytes and .CHECKSUM consistency
    # are necessary but not independently cryptographic exchange signatures.
    pages=0;scanned=0
    try:
        with zipfile.ZipFile(zip_path) as z:
            members=z.infolist()
            expected=name[:-4]+".csv"
            if (len(members)!=1 or members[0].filename!=expected
                    or members[0].is_dir()
                    or members[0].file_size>MAX_UNCOMPRESSED):
                raise DailyArchiveHold("CS00_ARCHIVE_UNSAFE_ZIP_LAYOUT")
            with z.open(members[0]) as binary:
                reader=csv.reader(io.TextIOWrapper(binary,encoding="utf-8",
                                                     newline="",errors="strict"))
                first=True
                page=[]
                last_seen=None
                for cols in reader:
                    if first and tuple(cols)==HEADER:
                        first=False;continue
                    first=False
                    scanned+=1
                    if scanned>MAX_ROWS_TO_SCAN:
                        raise DailyArchiveHold("CS00_ARCHIVE_REPLAY_SCAN_QUOTA_HOLD")
                    if len(cols)!=7:
                        raise DailyArchiveHold("CS00_ARCHIVE_CSV_SCHEMA")
                    try:
                        agg=int(cols[0]);f=int(cols[3]);l=int(cols[4]);tm=int(cols[5])
                        if cols[6].lower() not in ("true","false"):
                            raise ValueError("maker")
                        if last_seen is not None and agg!=last_seen+1:
                            raise DailyArchiveHold("CS00_ARCHIVE_INTERNAL_AGG_ID_GAP")
                        last_seen=agg
                        if agg<recovery.next_id:continue
                        if agg>recovery.last_id:break
                        if agg!=recovery.next_id+len(page):
                            raise DailyArchiveHold("CS00_ARCHIVE_RECOVERY_ID_GAP")
                        page.append({"a":agg,"p":cols[1],"q":cols[2],
                                     "f":f,"l":l,"T":tm,
                                     "m":cols[6].lower()=="true"})
                    except ValueError as e:
                        raise DailyArchiveHold("CS00_ARCHIVE_CSV_INVALID_NUMBER") from e
                    if len(page)==1000:
                        raw=json.dumps(page,separators=(",",":")).encode("ascii")
                        recovery.ingest_page(raw,received_at_ms=received_at_ms,
                          source="OFFICIAL_ARCHIVE_CHECKSUM_VERIFIED")
                        pages+=1;page=[]
                if page:
                    recovery.ingest_page(json.dumps(page,separators=(",",":")).encode("ascii"),
                      received_at_ms=received_at_ms,
                      source="OFFICIAL_ARCHIVE_CHECKSUM_VERIFIED")
                    pages+=1
    except (OSError,zipfile.BadZipFile,UnicodeError,SourceRecoveryHold) as e:
        raise DailyArchiveHold("CS00_ARCHIVE_SOURCE_INVALID_OR_INCOMPLETE") from e
    if recovery.state!="TRADE_PATH_RECOVERED_ONLY":
        raise DailyArchiveHold("CS00_ARCHIVE_NOT_FULLY_RECOVERED")
    return {"schema":VERSION,"zip_sha256":checksum_bytes.decode("ascii").strip()[:64].lower(),
            "daily_files_verified":1,"pages":pages,"rows_scanned":scanned,
            "source_state":recovery.state,
            "qualified_quote_cost_or_paper":False,"financial_authority":"NONE"}
