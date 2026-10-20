"""No deployment and no exchange credentials: build research data and compare brains."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .experiment import nine_month_bounds,experiment
from .lab import build_archive_database

def main(argv=None):
    p=argparse.ArgumentParser(description="NBOT V7 offline nine-month research")
    sub=p.add_subparsers(dest="command",required=True)
    b=sub.add_parser("build",help="Create source-hashed, 5m-proxy labeled nine-month database")
    b.add_argument("--archive",type=Path,required=True)
    b.add_argument("--registry",type=Path,required=True)
    b.add_argument("--db",type=Path,required=True)
    b.add_argument("--start-month",required=True,help="e.g. 2026-01")
    q=sub.add_parser("experiment",help="A train 3m, B frozen exam 3m, C A/B1/B2 exam 3m")
    q.add_argument("--db",type=Path,required=True)
    q.add_argument("--out",type=Path,required=True)
    q.add_argument("--start-month",required=True)
    args=p.parse_args(argv)
    a,b,c,d=nine_month_bounds(args.start_month)
    if args.command=="build":
        import datetime
        months=set()
        for start,end in [(a,b),(b,c),(c,d)]:
            while start<end:
                months.add(datetime.datetime.fromtimestamp(start/1000,datetime.timezone.utc).strftime("%Y-%m"))
                from .experiment import add_months
                start=add_months(start,1)
        result=build_archive_database(args.archive,args.registry,args.db,a,d,months)
    else:
        result=experiment(args.db,args.start_month,args.out)
        result={"experiment":result["experiment"],"output":str(args.out),
                "stage_b":result["stage_b"],"stage_c":result["stage_c"],
                "economic_approval":result["economic_approval"]}
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
