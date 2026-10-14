"""Forensic-only diagnostic of an original Binance aggTrades ZIP: never accepts/scorers.

Reports only bounded anomaly summaries. Must not substitute for G4 source audit.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter
from datetime import datetime,timezone
from zipfile import ZipFile

def main():
    p=argparse.ArgumentParser()
    p.add_argument("file")
    a=p.parse_args()
    failures=Counter()
    examples={}
    total=0
    start=end=None
    previous=None
    with ZipFile(a.file) as z:
        print("MEMBERS",z.namelist())
        with z.open(z.namelist()[0]) as f:
            import io
            records=csv.reader(io.TextIOWrapper(f,encoding="utf-8-sig",newline=""))
            for row in records:
                total+=1
                if len(row)!=7:
                    failures["WIDTH"]+=1;continue
                try:
                    agg,first,last,clock=[int(row[k]) for k in (0,3,4,5)]
                except ValueError:
                    failures["HEADER_OR_INTEGER"]+=1
                    if len(examples.get("HEADER_OR_INTEGER",[]))<3:
                        examples.setdefault("HEADER_OR_INTEGER",[]).append(row)
                    continue
                data=(agg,first,last,clock)
                if start is None:start=data
                end=data
                if previous is not None:
                    old,oldfirst,oldlast,oldclock=previous
                    for name,bad in [
                        ("AGG_ID_SKIP",agg!=old+1),
                        ("UNDERLYING_TRADE_ID_GAP",first!=oldlast+1),
                        ("TIME_BACKWARD",clock<oldclock),
                        ("ID_REWIND",agg<=old)]:
                        if bad:
                            failures[name]+=1
                            if len(examples.get(name,[]))<4:
                                examples.setdefault(name,[]).append({
                                   "previous":previous,"current":data,
                                   "agg_id_delta":agg-old,
                                   "trade_id_delta":first-oldlast,
                                   "csv_row":total})
                previous=data
    print("TOTAL_ROWS",total)
    print("ANOMALY_COUNTS",dict(failures))
    print("EXAMPLES",repr(examples))
    print("START",start)
    print("END",end)
    if start is not None:
        print("DATE_RANGE_UTC",datetime.fromtimestamp(start[-1]/1000,timezone.utc),
              datetime.fromtimestamp(end[-1]/1000,timezone.utc))
    print("ECONOMIC_LABELS",0)
    print("TRADE_AUTHORITY","NONE")

if __name__=="__main__":
    main()
