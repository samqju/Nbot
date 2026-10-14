"""G4 forward-only bounded market capture runner; NEVER production-autostart.

Builds a separate 50-market, public-only, two-route data acquisition pilot,
with explicit operator --enable-network, finite duration, resource limits and
private independent SQLite. Zero account/order/train/backfill functionality.

IMPORTANT: even a flawless run produces raw original WSS RECEIPTS, not an
exchange-signed quote, complete trade-path replay or matured economic label.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Callable

from nbot.v5.g4_forward_stream_contract import forward_stream_endpoints
from nbot.v5.g4_forward_vault import ForwardSourceVault

RUNNER_CONTRACT = "NBOT_V5_G4_FORWARD_CAPTURE_ISOLATED_V1"
MAX_RUN_SECONDS = 3600
MAX_FRAMES = 100000
MAX_DB_MIB = 256
DEFAULT_RECONNECTS = 2
_ROUTES = ("market_aggtrade", "public_bookticker")


class G4CollectorHold(ValueError):
    pass


def source_cohort_file(raw: bytes) -> tuple[str,...]:
    """Require literal frozen G1 cohort SHA proof in independent read-only JSON.

    Does not and cannot authenticate the origin of the manifest. Operators must
    independently compare the SHA to accepted G1/G2 original cohort proof.
    """
    from nbot.v5.g1f_journal import digest
    if not isinstance(raw,bytes) or len(raw)>8000:
        raise G4CollectorHold("G4_COHORT_MANIFEST_INVALID")
    try:
        data=json.loads(raw)
    except (TypeError,ValueError,UnicodeError) as exc:
        raise G4CollectorHold("G4_COHORT_MANIFEST_INVALID") from exc
    if not isinstance(data,dict) or set(data)!={"symbols","cohort_digest"}:
        raise G4CollectorHold("G4_COHORT_MANIFEST_SHAPE_INVALID")
    symbols=data["symbols"]
    if (not isinstance(symbols,list) or len(symbols)!=50
            or "BTCUSDT" not in symbols or symbols!=sorted(set(symbols))):
        raise G4CollectorHold("G4_COHORT_NOT_APPROVED_FIFTY")
    try:
        forward_stream_endpoints(symbols)
    except ValueError as exc:
        raise G4CollectorHold("G4_COHORT_MARKET_INVALID") from exc
    expected=digest({"selection_version":"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                     "symbols":tuple(symbols)})
    if expected!=data["cohort_digest"]:
        raise G4CollectorHold("G4_COHORT_SHA_NOT_REPRODUCIBLE")
    return tuple(symbols)


def _validate_isolation(root: Path, db: Path):
    """Reject production-linked and symlink paths. Caller decides location.

    Require exact direct child of operator-specified separate G4 root; no
    auto-creation or modifications to any original production directories.
    """
    if root.is_symlink() or not root.is_dir():
        raise G4CollectorHold("G4_SOURCE_ROOT_NOT_EXISTING_DIRECTORY")
    if (not root.name.startswith("g4-forward-")
            or db.name not in ("g4_raw_source.sqlite",)
            or db.parent.resolve()!=root.resolve() or db.is_symlink()):
        raise G4CollectorHold("G4_SOURCE_DB_PATH_NOT_ISOLATED")
    if any("nbot_v5_integrated_data" in p or "nbot_v5_data" in p
           for p in root.resolve().parts):
        raise G4CollectorHold("G4_SOURCE_PRODUCTION_PATH_FORBIDDEN")
    if root.stat().st_mode & 0o077:
        raise G4CollectorHold("G4_SOURCE_ROOT_PERMISSIONS_UNSAFE")


def _bytes_in_db(db_path: Path) -> int:
    return sum(Path(str(db_path)+suffix).stat().st_size
               for suffix in ("","-wal","-shm")
               if Path(str(db_path)+suffix).exists())


async def capture_route(*, route: str, endpoint: str, vault: ForwardSourceVault,
                        connector: Callable, clock_ms: Callable,
                        stop: asyncio.Event, budget: dict,
                        max_reconnects: int = DEFAULT_RECONNECTS) -> None:
    """Receive and durably commit bounded original bytes; no source backfill.

    Following disconnect/restart, the vault always records an explicit epoch
    change / unverified continuity. No reconnection can silently promote
    source-contiguous evidence.
    """
    if route not in _ROUTES or type(max_reconnects) is not int or not 0<=max_reconnects<=5:
        raise G4CollectorHold("G4_FORWARD_ROUTE_OR_RETRY_INVALID")
    tries=0
    while not stop.is_set() and tries<=max_reconnects:
        try:
            async with connector(endpoint) as socket:
                vault.connect(route=route,at_ms=clock_ms())
                async for payload in socket:
                    if stop.is_set():
                        break
                    if isinstance(payload,str):
                        raw=payload.encode("utf8")
                    elif isinstance(payload,bytes):
                        raw=payload
                    else:
                        raise G4CollectorHold("G4_FORWARD_NON_BYTES_FRAME")
                    if len(raw)>32768:
                        raise G4CollectorHold("G4_FORWARD_FRAME_OVERFLOW")
                    receipt=vault.ingest(route=route,at_ms=clock_ms(),raw=raw)
                    budget["frames"]+=1
                    if budget["frames"]>=budget["max_frames"]:
                        budget["reached"]="MAX_FRAMES"
                        stop.set()
                        break
                    if budget["db_path"] is not None and (
                            _bytes_in_db(budget["db_path"])>budget["max_db_bytes"]):
                        budget["reached"]="MAX_DB_SIZE"
                        stop.set()
                        break
                if vault._last(route)[3] in ("FRAME","OPEN"):
                    vault.disconnect(route=route,at_ms=clock_ms())
            if stop.is_set():
                return
            # An ordinary remote close still breaks chronological source.
            tries+=1
        except asyncio.CancelledError:
            raise
        except (OSError,TimeoutError,ValueError,RuntimeError) as exc:
            # Do not mark a clean socket close when it did not occur. Next
            # OPEN writes ABRUPT_RESTART_HOLD if prior epoch was left active.
            budget["source_errors"].append(route+":"+type(exc).__name__)
            tries+=1
        if not stop.is_set() and tries<=max_reconnects:
            await asyncio.sleep(min(tries,3))
    if not stop.is_set():
        budget["reached"]="SOURCE_ROUTE_RETRIES_EXHAUSTED_"+route
        stop.set()


async def run_bounded(*, vault: ForwardSourceVault, endpoints: dict,
                      connector: Callable, duration_s: float,
                      max_frames: int, max_db_mib: int,
                      db_path: Path|None = None,
                      clock_ms: Callable|None = None) -> dict:
    """Supervise 2 public-only routes with explicit finite caps.

    Unit tests inject a zero-network connector, deterministic frames/clocks.
    If one route fails, no other stream grants scientific continuity.
    """
    if (not isinstance(duration_s,(int,float)) or
            not 0<duration_s<=MAX_RUN_SECONDS or
            type(max_frames) is not int or not 1<=max_frames<=MAX_FRAMES or
            type(max_db_mib) is not int or not 1<=max_db_mib<=MAX_DB_MIB):
        raise G4CollectorHold("G4_FORWARD_RESOURCE_BOUNDS_INVALID")
    clock_ms=clock_ms or (lambda:time.time_ns()//1000000)
    stop=asyncio.Event()
    budget={"frames":0,"max_frames":max_frames,
            "db_path":db_path,"max_db_bytes":max_db_mib*1024*1024,
            "source_errors":[],"reached":None}
    tasks=[
        asyncio.create_task(capture_route(
            route=route,endpoint=endpoints[route],
            vault=vault,connector=connector,clock_ms=clock_ms,
            stop=stop,budget=budget))
        for route in _ROUTES
    ]
    try:
        async with asyncio.timeout(duration_s):
            await asyncio.gather(*tasks)
    except TimeoutError:
        budget["reached"]=budget["reached"] or "TIME_BUDGET"
        stop.set()
    finally:
        stop.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        # If cancellation or forced timeout interrupted an open socket,
        # source-vault OPEN remains open and restart creates explicit gap.
    report=vault.audit()
    return {**report,"run_contract":RUNNER_CONTRACT,
            "frames_seen":budget["frames"],
            "stop_reason":budget["reached"] or "SOURCE_STREAM_ENDED",
            "source_errors":tuple(budget["source_errors"]),
            "source_coverage_grade":"UNVERIFIED_UNTIL_INDEPENDENT_REPLAY",
            "model_training_authority":"NONE","order_authority":"NONE"}


class _RealConnector:
    def __call__(self, endpoint):
        # Construct context manager synchronously, no socket until __aenter__.
        import websockets
        return websockets.connect(endpoint,open_timeout=15,
                                  close_timeout=5,ping_interval=20,ping_timeout=20,
                                  max_size=32768,max_queue=32,compression=None)


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="Isolated bounded G4 source capture ONLY")
    p.add_argument("--cohort-manifest",required=True)
    p.add_argument("--source-root",required=True)
    p.add_argument("--max-seconds",type=int,default=600)
    p.add_argument("--max-frames",type=int,default=50000)
    p.add_argument("--max-db-mib",type=int,default=128)
    p.add_argument("--enable-network",action="store_true",
                   help="Explicitly permit public WSS acquisition; no order APIs exist")
    a=p.parse_args(argv)
    try:
        symbols=source_cohort_file(Path(a.cohort_manifest).read_bytes())
        if not 1<=a.max_seconds<=MAX_RUN_SECONDS or not 1<=a.max_frames<=MAX_FRAMES or not 1<=a.max_db_mib<=MAX_DB_MIB:
            raise G4CollectorHold("G4_FORWARD_RESOURCE_BOUNDS_INVALID")
        root=Path(a.source_root)
        target=root/"g4_raw_source.sqlite"
        endpoints=forward_stream_endpoints(symbols)
        _validate_isolation(root,target)
        if not a.enable_network:
            print(json.dumps({
                "status":"DRY_RUN_NO_NETWORK","symbols":len(symbols),
                "source_contract":RUNNER_CONTRACT,
                "db_path":str(target),"max_seconds":a.max_seconds,
                "max_frames":a.max_frames,"max_db_mib":a.max_db_mib,
                "order_authority":"NONE","model_training_authority":"NONE",
            },sort_keys=True))
            return 0
        if target.exists():
            if target.is_symlink():
                raise G4CollectorHold("G4_SOURCE_DB_SYMLINK_FORBIDDEN")
            uri=target.resolve().as_uri()+"?mode=rw"
        else:
            uri=target.absolute().as_uri()+"?mode=rwc"
        os.umask(0o077)
        with sqlite3.connect(uri,uri=True,timeout=10) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA journal_mode=WAL")
            vault=ForwardSourceVault(db,symbols=symbols)
            vault.audit()  # Before any new receipt, verify previous storage.
            report=asyncio.run(run_bounded(
                vault=vault,endpoints=endpoints,connector=_RealConnector(),
                duration_s=a.max_seconds,max_frames=a.max_frames,
                max_db_mib=a.max_db_mib,db_path=target))
        print(json.dumps(report,sort_keys=True))
        return 0 if not report["source_errors"] and report["stop_reason"] != "MAX_DB_SIZE" else 2
    except (ValueError,sqlite3.DatabaseError,OSError) as exc:
        print(json.dumps({"status":"HOLD","reason":str(exc),
                          "economic_outcomes":0,
                          "order_authority":"NONE"},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
