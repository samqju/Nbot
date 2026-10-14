"""Bounded offline G6 job. Independent original G5 release is mandatory.

No timer by default and no live-feed processing in this worker.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time
from nbot.v5.research_store import ResearchStore
from nbot.v5.science import Protocol,dataset,fit_candidate,canonical


def main():
    p=argparse.ArgumentParser()
    for name in ("root","protocol","independent-review","reviewer-key-file"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--boundary-ms",type=int,required=True)
    a=p.parse_args();root=Path(a.root)
    os.umask(0o077)
    keypath=Path(a.reviewer_key_file)
    if keypath.is_symlink() or keypath.stat().st_mode&0o077:
        raise ValueError("INDEPENDENT_KEY_NOT_PRIVATE")
    store=ResearchStore(root/"continuous_research.sqlite")
    try:
        now=time.time_ns()//1000000
        rows=[json.loads(r[0])["row"] for r in store.db.execute("SELECT body FROM research_journal WHERE kind='QUALIFIED_OUTCOME'")]
        data=dataset(rows,cutoff_ms=now,grade="ORIGINAL")
        artifact=fit_candidate(data,boundary_ms=a.boundary_ms,protocol=Protocol(**json.loads(Path(a.protocol).read_text())),
                               review=json.loads(Path(a.independent_review).read_text()),reviewer_key=keypath.read_bytes(),now_ms=now)
        output=root/(artifact["model_sha256"]+".model.json")
        raw=canonical(artifact)
        if output.exists():
            if output.read_text()!=raw:raise ValueError("IMMUTABLE_ARTIFACT_CONFLICT")
        else:
            fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        store.register_candidate(artifact,now)
        print(canonical({"state":"CANDIDATE_ONLY","model_sha256":artifact["model_sha256"],"artifact":str(output),"paper_authority":"NONE"}))
    finally:store.close()


if __name__=="__main__":main()
