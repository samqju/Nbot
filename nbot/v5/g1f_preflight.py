"""Read-only preflight for isolated G1f observer systemd startup.

Fails closed if Observation host, branch, DB path or legacy V4 units are
unexpected. Never stops/starts other units and does not inspect secrets.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import socket

LEGACY_UNITS=(
    "nbot-observation-live.service",
    "nbot-observation-live-paper-control.service",
    "nbot-v4-research.service",
    "nbot-v4-paper-contest.service",
    "nbot-v4-training.timer",
    "nbot-research-epoch.timer",
    "nbot-observer.target",
)


def verify_startup(*, hostname=None, runner=subprocess.run,
                   path="/home/ubuntu/nbot_v5_data",
                   repo="/home/ubuntu/nbot_v5_sandbox") -> tuple[str,...]:
    reasons=[]
    if (hostname or socket.gethostname())!="base":
        reasons.append("NOT_OBSERVATION_VPS")
    folder=Path(path)
    if not folder.is_dir() or folder.is_symlink():
        reasons.append("ISOLATED_DB_DIRECTORY_INVALID")
    root=Path(repo)
    if not root.is_dir() or not (root/"nbot/v5/g1f_runner.py").is_file():
        reasons.append("ISOLATED_V5_CODE_NOT_PRESENT")
    branch=runner(
        ["git","-C",str(root),"branch","--show-current"],
        capture_output=True,text=True,timeout=5,
    )
    if branch.returncode or branch.stdout.strip()!="v5-clean-restart-20261013":
        reasons.append("ISOLATED_V5_BRANCH_INVALID")
    for unit in LEGACY_UNITS:
        result=runner(
            ["systemctl","is-active",unit],
            capture_output=True,text=True,timeout=5,
        )
        if result.stdout.strip()!="inactive":
            reasons.append("LEGACY_ACTIVE_OR_UNKNOWN_"+unit)
    return tuple(reasons)


def main():
    parser=argparse.ArgumentParser(description="G1f read-only fail-closed service preflight")
    parser.parse_args()
    try:
        reasons=verify_startup()
    except (OSError,subprocess.TimeoutExpired) as exc:
        print("G1F_PREFLIGHT_HOLD",type(exc).__name__)
        return 2
    if reasons:
        print("G1F_PREFLIGHT_HOLD",",".join(reasons))
        return 2
    print("G1F_PREFLIGHT_PASS OBSERVATION_ONLY")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
