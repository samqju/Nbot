#!/usr/bin/env python3
"""Run the NBOT V4 clean-slate virtual research factory on Observation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, validate_role_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.v4_research import V4ResearchFactory


def _git_sha(root: Path) -> str:
    value = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    if len(value)!=40: raise ValueError("V4_RELEASE_SHA_UNAVAILABLE")
    return value


def _latest_complete_event(database) -> int | None:
    with database.connection() as conn:
        row=conn.execute(
            "SELECT MAX(event_open_ms) FROM market_events WHERE status='COMPLETE'"
        ).fetchone()
    return None if row is None or row[0] is None else int(row[0])


def main() -> int:
    root=Path(__file__).resolve().parents[2]
    os.chdir(root)
    role=detect_role(root)
    if role is not MachineRole.OBSERVATION:
        raise ValueError("V4_RESEARCH_WRONG_MACHINE_ROLE")
    profile=get_profile("live-paper")
    validate_role_profile(repo_root=root,role=role,profile=profile,environment=os.environ)
    database=EvidenceDatabase(observation_config_for_profile(profile))
    factory=V4ResearchFactory(database,release_sha=_git_sha(root))
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    print(json.dumps({"event":"V4_RESEARCH_READY",**factory.status()},sort_keys=True),flush=True)
    try:
        while not stop.wait(2.0):
            event_ms=_latest_complete_event(database)
            if event_ms is None or event_ms==factory.last_event_open_ms:
                continue
            result=factory.on_five_minute_event(event_open_ms=event_ms)
            print(json.dumps({"event":"V4_RESEARCH_CYCLE",**result},sort_keys=True),flush=True)
    finally:
        factory.stop()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
