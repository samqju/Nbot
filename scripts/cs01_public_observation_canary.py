#!/usr/bin/env python3
"""CS-01 one-shot explicitly owner-authorized PUBLIC USD-M Observation canary.

No API keys or order clients. No daemon or auto-restart. The operator must
supply --wss-smoke or --observe-public-only; omitted means NO NETWORK.
The 20-market Observation run has a strict wall-clock stop and snapshots
its status before exiting, without claiming G4 scientific qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from nbot_v5_1.cs00_public_ws import PublicTlsSocket,PublicSocketHold
from nbot_v5_1.deep_source import verify_frame
from nbot_v5_1.cs00_public_service import FutureCs01Permit,FuturePublicObservationService

URLS={
    "TRADE":"wss://fstream.binance.com/market/stream?streams=btcusdt@aggTrade",
    "QUOTE":"wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker",
    "MARK":"wss://fstream.binance.com/market/stream?streams=btcusdt@markPrice@1s",
}
ACTION="CS01-OWNER-PUBLIC-ONLY-CANARY-20261015"
def emit(event,**kw):
    print(json.dumps({"event":event,**kw},sort_keys=True),flush=True)

def main():
    p=argparse.ArgumentParser()
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--wss-smoke",action="store_true")
    modes.add_argument("--observe-public-only",action="store_true")
    p.add_argument("--seconds",type=int,default=120)
    p.add_argument("--state-root",type=Path,default=Path.home()/"nbot-v5.1-state")
    args=p.parse_args()
    if not 15<=args.seconds<=180:
        p.error("seconds must be between 15 and 180")
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    emit("CS01_PUBLIC_CANARY_START",at_utc=datetime.now(timezone.utc).isoformat(),
         mode="WSS_SMOKE" if args.wss_smoke else "PUBLIC_OBSERVATION_ONLY",
         seconds_cap=args.seconds,source_sha=commit,
         no_accounts=True,no_orders=True,financial_authority="NONE")
    if args.wss_smoke:
        got={}
        for kind,url in URLS.items():
            conn=PublicTlsSocket(url,timeout_sec=12)
            try:
                conn.connect(approved_cs01_public_only=True)
                raw=conn.read_message()
                now=int(time.time()*1000)
                receipt=verify_frame(kind=kind,raw=raw,received_at_ms=now,
                      source_epoch=1,selected_symbols=("BTCUSDT",))
                got[kind]={"event_state":receipt.state,"reason":receipt.reason,
                           "symbol":receipt.symbol,"bytes":len(raw),
                           "financial_authority":receipt.order_authority}
                emit("WSS_PUBLIC_FRAME",kind=kind,**got[kind])
                if receipt.state!="RECEIVED_UNQUALIFIED_LOCAL_WSS":
                    raise RuntimeError("PUBLIC_SOURCE_FRAME_HOLD_"+kind)
            finally:conn.close()
        emit("CS01_WSS_SMOKE_PASS",streams=len(got),source_qualified=False,no_orders=True)
        return 0
    state=args.state_root.expanduser().resolve()
    app=FuturePublicObservationService(source_root=state,code_sha=commit)
    # Operator's time-bounded public-only CS-01 authorization is not
    # a signed account permit, cannot enable original virtual or PAPER/REAL.
    now=int(time.time()*1000)
    permit=FutureCs01Permit(
        project="NBOT_V5.1",branch="nbot-v5.1",exact_commit_sha=commit,
        release_action_id=ACTION,approved_mode="PUBLIC_OBSERVATION_ONLY",
        expires_at_ms=now+min(12*60*1000,args.seconds*1000+180000))
    timer=threading.Timer(args.seconds,lambda:app.request_stop("CS01_TIMED_CANARY_COMPLETED"))
    timer.daemon=True
    timer.start()
    error=None
    try:app.run_foreground(permit=permit,expected_exact_sha=commit)
    except Exception as exc:
        error=type(exc).__name__+":"+str(exc)[:200]
    finally:timer.cancel()
    pipe=app.pipeline
    result={
        "source_sha":commit,
        "status":app.status(),
        "error":error,
        "errors":app.errs[-20:],
        "source_only":True,"no_orders":True,
        "financial_authority":"NONE",
        "pipeline":pipe.status() if pipe else None,
        "deep_symbols":list(pipe.deep.symbols) if pipe and pipe.deep else None,
        "source_cursor_pairs":len(pipe.intake.cursor) if pipe and pipe.intake else None,
        "source_receipt_files": len(list((state/"evidence").glob("segment-*.json"))),
    }
    emit("CS01_PUBLIC_OBSERVATION_CANARY_RESULT",**result)
    if (error or not pipe or pipe.source_frames<3 or pipe.hard_source_gap_count>0
            or app.exit_reason!="CS01_TIMED_CANARY_COMPLETED"
            or app.errs):
        return 2
    # A finite canary is NOT independent 20/20 source continuity qualification.
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        emit("CS01_PUBLIC_CANARY_HOLD",reason=type(exc).__name__+":"+str(exc)[:200],
             no_orders=True)
        sys.exit(2)
