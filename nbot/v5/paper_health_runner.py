"""Deployable G7 zero-orders health mode. Contains no unlock or network path."""
import argparse
import json
import os
from pathlib import Path
import time
from nbot.v5.guarded_paper import GuardedPaper
from nbot.v5.science import canonical


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--policy",required=True)
    p.add_argument("--once",action="store_true")
    a=p.parse_args();root=Path(a.root)
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode&0o077:
        raise ValueError("PAPER_ROOT_NOT_PRIVATE")
    os.umask(0o077)
    engine=GuardedPaper(root/"guarded_paper.sqlite",policy=json.loads(Path(a.policy).read_text()))
    try:
        while True:
            report=engine.reconcile()
            assert report["paper_state"]=="LOCKED" and all(b["fills"]==0 and b["positions"]==0 for b in report["books"].values())
            print(canonical(report),flush=True)
            if a.once:break
            time.sleep(60)
    finally:engine.store.close()


if __name__=="__main__":main()
