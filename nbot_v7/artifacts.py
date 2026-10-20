"""Content-addressed offline evidence; no exchange or deployment authority."""
from hashlib import sha256
from pathlib import Path
import importlib.metadata
import json
import platform


def file_hash(path):
    h=sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def dataset_hash(conn):
    """Stable logical content digest, independent of SQLite page/WAL layout."""
    h=sha256()
    for table in ("meta","candidate","watch_candidate","opportunity","watch","outcome_context"):
        h.update(table.encode())
        info=list(conn.execute(f"PRAGMA table_info({table})"))
        cols=[r[1] for r in info]
        if not cols:
            raise ValueError("MISSING_DATASET_TABLE:"+table)
        ordering=[r[1] for r in sorted(info,key=lambda r:r[5]) if r[5]] or cols
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY "+",".join(ordering)):
            h.update(json.dumps(tuple(row),separators=(",",":"),ensure_ascii=True).encode()+b"\n")
    return h.hexdigest()


class EventLog:
    def __init__(self,path):
        self.stream=Path(path).open("x",encoding="utf-8",newline="\n")
        self.previous="0"*64
        self.count=0

    def write(self,event):
        body={"sequence":self.count,"previous_sha256":self.previous,**event}
        digest=sha256(json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        self.stream.write(json.dumps({**body,"sha256":digest},sort_keys=True,allow_nan=False)+"\n")
        self.previous=digest
        self.count+=1

    def close(self):
        self.stream.close()


def seal_run(folder, dataset_digest, config):
    folder=Path(folder)
    packages={dist.metadata["Name"]:dist.version for dist in importlib.metadata.distributions()}
    root=Path(__file__).parent
    manifest={"schema":"NBOT_V7_REPRODUCIBLE_RUN_V1","dataset_sha256":dataset_digest,
              "config":config,"python":platform.python_version(),"dependencies":packages,
              "source_sha256":{p.relative_to(root).as_posix():file_hash(p) for p in sorted(root.rglob("*.py"))},
              "files_sha256":{p.relative_to(folder).as_posix():file_hash(p)
                              for p in sorted(folder.rglob("*")) if p.is_file()},
              "authority":"OFFLINE_RESEARCH_ONLY"}
    (folder/"run_manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return manifest


def verify_run(folder):
    folder=Path(folder).resolve()
    manifest=json.loads((folder/"run_manifest.json").read_text(encoding="utf-8"))
    for name,digest in manifest["files_sha256"].items():
        path=(folder/name).resolve()
        if not path.is_relative_to(folder) or not path.is_file() or file_hash(path)!=digest:
            raise ValueError("ARTIFACT_HASH_MISMATCH:"+name)
    return manifest
