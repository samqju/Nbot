"""G1–G3 integrated V5 production preflight; read-only and fail closed."""
from __future__ import annotations
import argparse
from pathlib import Path
import socket
import subprocess

from nbot.v5.g1f_preflight import LEGACY_UNITS

class DeploymentHold(ValueError):
    pass

def verify(*, repo:str, approved_sha_file:str, data_dir:str,
           hostname:str|None=None, runner=subprocess.run) -> tuple[str,...]:
    errors=[]
    if (hostname or socket.gethostname())!="base":
        errors.append("NOT_OBSERVATION_HOST")
    source=Path(repo)
    if source.is_symlink() or not source.is_dir() or not (source/"nbot/v5/g3_market_context.py").is_file():
        errors.append("G3_CODE_NOT_IN_VERIFIED_DIRECTORY")
    folder=Path(data_dir)
    if folder.is_symlink() or not folder.is_dir():
        errors.append("PRODUCTION_DB_DIRECTORY_NOT_ISOLATED")
    sha_file=Path(approved_sha_file)
    if sha_file.is_symlink() or not sha_file.is_file():
        errors.append("APPROVED_GIT_SHA_MISSING")
    else:
        approved=sha_file.read_text(encoding="utf-8").strip()
        if len(approved)!=40 or any(c not in "0123456789abcdef" for c in approved):
            errors.append("APPROVED_GIT_SHA_INVALID")
        else:
            try:
                head=runner(["git","-C",str(source),"rev-parse","HEAD"],
                            capture_output=True,text=True,timeout=8)
                status=runner(["git","-C",str(source),"status","--porcelain"],
                              capture_output=True,text=True,timeout=8)
                if (head.returncode or status.returncode or
                        head.stdout.strip()!=approved or status.stdout.strip()):
                    errors.append("PRODUCTION_CODE_NOT_PINNED_CLEAN")
            except (OSError,subprocess.TimeoutExpired):
                errors.append("GIT_STATE_UNVERIFIABLE")
    for unit in LEGACY_UNITS:
        try:
            r=runner(["systemctl","is-active",unit],
                     capture_output=True,text=True,timeout=8)
            if r.stdout.strip()!="inactive":
                errors.append("LEGACY_UNIT_ACTIVE_OR_UNKNOWN_"+unit)
        except (OSError,subprocess.TimeoutExpired):
            errors.append("LEGACY_UNIT_UNVERIFIABLE_"+unit)
    return tuple(sorted(set(errors)))

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--approved-sha-file",required=True)
    p.add_argument("--data-dir",required=True)
    args=p.parse_args()
    try:
        reasons=verify(repo=args.repo,approved_sha_file=args.approved_sha_file,
                       data_dir=args.data_dir)
    except (OSError,ValueError) as exc:
        reasons=("PREFLIGHT_EXCEPTION_"+type(exc).__name__,)
    if reasons:
        print("V5_G1_G3_PREFLIGHT_HOLD",",".join(reasons),flush=True)
        return 2
    print("V5_G1_G3_PREFLIGHT_PASS NO_ORDER_AUTHORITY",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
