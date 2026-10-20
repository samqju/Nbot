"""Explicit provisional archive cohort. Never fabricates SOURCE_ATTESTED status."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
from .data import discover,load_bars,BAR_MS
from .archive import months_after
from .experiment import nine_month_bounds


def observed_registry(archive,start_month,output):
    if output.exists():raise FileExistsError(output)
    start,_,_,end=nine_month_bounds(start_month)
    files=discover(archive,set(months_after(start_month)))
    output.parent.mkdir(parents=True,exist_ok=True)
    entries=[]
    for symbol,paths in sorted(files.items()):
        bars,hashes=load_bars(paths,start,end)
        if not bars:continue
        evidence=sha256(json.dumps({Path(p).name:h for p,h in hashes.items()},sort_keys=True).encode()).hexdigest()
        entries.append({"symbol":symbol,"from_ms":bars[0].t+BAR_MS,
                        "to_ms":bars[-1].t+BAR_MS+1,"evidence_sha256":evidence,
                        "source_grade":"ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE"})
    with output.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=("symbol","from_ms","to_ms","evidence_sha256","source_grade"))
        writer.writeheader();writer.writerows(entries)
    return {"symbols":len(entries),"historical_lifecycle_verified":False,
            "scope":"ALL_DOWNLOADED_ARCHIVE_SYMBOLS_INCLUDING_NON_SURVIVORS_NOT_CURRENT_EXCHANGE_FILTERED",
            "status":"EXPLORATORY_COHORT_ONLY","registry_sha256":sha256(output.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--start-month",required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(observed_registry(args.archive,args.start_month,args.out),indent=2))

if __name__=="__main__":main()
