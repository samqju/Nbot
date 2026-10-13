"""G1f isolated V5 observation-only collector.

Manual/optionally supervised long-running process. Public Binance WSS-first,
REST closed-candle recovery ONLY, immutable source/audit/candidate records.
No private API, orders, training, recommendations, models or V4 services.

Safe operations: one cohort per new V5 DB, 50 symbols max, 96 REST candles per
coin, bounded reconnect/backoff, bounded WSS frames, resource guards, and
explicit restart gaps rendered UNSCORABLE rather than invisible.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import resource
import signal
import time

from nbot.v5.candle_ledger import EvidenceHold
from nbot.v5.finality_quarantine import FinalityQuarantine
from nbot.v5.g1f_engine import audit_event
from nbot.v5.g1f_journal import CandidateJournal, JournalHold
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.public_market import (
    closed_event_from_server_time, public_get, select_universe,
)
from nbot.v5.reconnect_policy import ReconnectPolicy, FeedRecoveryHold
from nbot.v5.ws_contract import UnsafeStream, stream_urls

MAX_RSS_MIB=192
MAX_DB_MIB=256
MAX_FRAMES_PER_5M=250000
MAX_CATCHUP_EVENTS=96
METRICS_EVERY_SECONDS=15
CLOSE_GRACE_MS=12000


def wall_ms():
    return int(time.time()*1000)


def db_size_mib(path: Path) -> float:
    return sum(
        Path(str(path)+suffix).stat().st_size
        for suffix in ("","-wal","-shm")
        if Path(str(path)+suffix).exists()
    )/(1024*1024)


def resource_guard(path):
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
    size=db_size_mib(path)
    if rss>MAX_RSS_MIB or size>MAX_DB_MIB:
        raise EvidenceHold("G1F_RESOURCE_LIMIT_EXCEEDED")
    return {"peak_rss_mib":round(rss,2),"db_mib":round(size,2)}


def _get_rest_96(symbol, event, getter):
    return getter("/fapi/v1/klines",{
        "symbol":symbol,"interval":"5m",
        "startTime":str(event-95*INTERVAL_MS),
        "endTime":str(event+INTERVAL_MS-1),
        "limit":"96",
    })


async def rest_seed(session, symbols, event, *, getter=public_get):
    semaphore=asyncio.Semaphore(6)
    async def get(symbol):
        async with semaphore:
            try:
                payload=await asyncio.to_thread(_get_rest_96,symbol,event,getter)
                # All SQLite writes occur on main event loop thread only.
                return symbol,payload,None
            except Exception as exc:
                return symbol,None,type(exc).__name__+":"+str(exc)[:75]
    fetched=await asyncio.gather(*(get(s) for s in symbols))
    now=wall_ms()
    if now<event+INTERVAL_MS:
        raise EvidenceHold("G1F_REST_SEED_EVENT_NOT_CLOSED")
    result={}
    for symbol,payload,error in fetched:
        if error:
            raise EvidenceHold("G1F_REST_SEED_"+symbol+"_"+error)
        label,count=session.restore_rest(
            symbol,payload,event_open_ms=event,observed_ms=now)
        result[symbol]={"status":label,"inserted":count}
    return result


class ObservationOnlyRunner:
    def __init__(self, *, top: int, path: Path, max_seconds: int,
                 getter=public_get):
        if (type(top) is not int or not 2<=top<=50
                or type(max_seconds) is not int
                or not (max_seconds==0 or 30<=max_seconds<=3600)):
            raise ValueError("G1F_ARGUMENTS_INVALID")
        path=Path(path).expanduser()
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise EvidenceHold("G1F_DB_PARENT_MISSING_OR_LINK")
        self.top=top
        self.path=path
        self.max_seconds=max_seconds
        self.getter=getter
        self.stop=asyncio.Event()
        self.failed_reason=None
        self.interrupted=False
        self.stats={"market_frames":0,"public_frames":0,
                    "committed_events":0,"restart_missing_events":0,
                    "reconnect_attempts":0}
        self.last_log=time.monotonic()

    def fault(self, reason):
        self.failed_reason=str(reason)[:150]
        self.stop.set()

    async def start(self):
        now_response=await asyncio.to_thread(self.getter,"/fapi/v1/time")
        event,binance_ms=closed_event_from_server_time(now_response)
        if abs(wall_ms()-binance_ms)>90000:
            raise EvidenceHold("G1F_BINANCE_CLOCK_SKEW")
        exchange=await asyncio.to_thread(self.getter,"/fapi/v1/exchangeInfo")
        ticker=await asyncio.to_thread(self.getter,"/fapi/v1/ticker/24hr")
        eligible=select_universe(exchange,ticker,limit=self.top)
        symbols=tuple(sorted(set(eligible)|{"BTCUSDT"}))
        uri=stream_urls(eligible,quote_mode="depth5@500ms")
        started=time.monotonic()
        deadline=(started+self.max_seconds
                  if self.max_seconds else float("inf"))
        with ObservationContinuity(eligible,self.path) as session:
            journal=CandidateJournal(session.ledger.db)
            finality=FinalityQuarantine(session.ledger.db)
            identity=journal.begin_cohort(
                eligible,selected_ms=binance_ms,event_open_ms=event)
            # REST historical sync before any WebSocket frame can enter.
            await rest_seed(session,symbols,event,getter=self.getter)
            # Previous recorded events are not silently skipped on restart.
            previous=journal.latest_event()
            if previous is not None and previous<event:
                missing=(event-previous)//INTERVAL_MS
                if missing>MAX_CATCHUP_EVENTS:
                    raise EvidenceHold("G1F_RESTART_GAP_OVER_96_EVENTS")
                for i in range(1,missing+1):
                    opened=previous+i*INTERVAL_MS
                    journal.commit_event(
                        cohort_digest=identity,event_open_ms=opened,
                        observed_ms=wall_ms(),eligible_symbols=eligible,
                        candles_by_symbol={},
                        quarantine={},
                        health_holds={s:("PROCESS_WAS_OFFLINE",)
                                      for s in eligible},
                        btc_valid=False,coverage_valid=False,
                    )
                    self.stats["restart_missing_events"]+=1
            self.policy=ReconnectPolicy()
            tasks=[
                asyncio.create_task(self._route(
                    route,uri[route],session,deadline))
                for route in ("market","public")
            ]
            coordinator=asyncio.create_task(self._events(
                session,journal,finality,identity,eligible,symbols,
                event+INTERVAL_MS,deadline))
            monitor=asyncio.create_task(self._metrics(
                session,journal,deadline))
            tasks.extend([coordinator,monitor])
            try:
                while not self.stop.is_set() and time.monotonic()<deadline:
                    await asyncio.sleep(.5)
                self.stop.set()
                await asyncio.gather(*tasks,return_exceptions=False)
            finally:
                self.stop.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
            summary={
                "result":"HOLD" if self.failed_reason else "OBSERVATION_ONLY_RUN_COMPLETED",
                "reason":self.failed_reason,
                "universe_count":len(eligible),
                "cohort_digest":identity,
                "metrics":self.stats,
                "resource":resource_guard(self.path),
                "journal":journal.inspect(),
                "source_epochs":session.sources.overview(),
                "research_ready":False,
                "training_labels_created":0,
                "order_authority":"NONE",
                "persistent_daemon_enabled":False,
            }
            return summary

    async def _route(self,route,uri,session,deadline):
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            self.fault("G1F_WSS_DEPENDENCY_NOT_INSTALLED")
            return
        tries=0
        while not self.stop.is_set() and time.monotonic()<deadline:
            connected=False
            try:
                async with connect(
                    uri,open_timeout=9,close_timeout=2,
                    ping_interval=20,ping_timeout=20,
                    max_size=64000,max_queue=16,
                ) as socket:
                    session.connect(route)
                    self.policy.on_connect(route)
                    connected=True
                    tries=0
                    # Fresh socket does not reset trade/quote source continuity.
                    if self.interrupted and route=="market":
                        now=await asyncio.to_thread(self.getter,"/fapi/v1/time")
                        event,_=closed_event_from_server_time(now)
                        await rest_seed(session,session.symbols,event,
                                        getter=self.getter)
                    while not self.stop.is_set() and time.monotonic()<deadline:
                        try:
                            frame=await asyncio.wait_for(socket.recv(),timeout=1)
                        except asyncio.TimeoutError:
                            continue
                        self.stats[route+"_frames"]+=1
                        if self.stats[route+"_frames"]>MAX_FRAMES_PER_5M*2:
                            raise EvidenceHold("G1F_WSS_FRAME_CAP")
                        classified=session.consume(
                            route,frame,received_ms=wall_ms())
                        if classified.startswith("HOLD_"):
                            self.interrupted=True
                            self.policy.global_incidents+=1
                        if session.store.health.trade_gaps:
                            self.interrupted=True
            except asyncio.CancelledError:
                raise
            except (UnsafeStream,EvidenceHold,JournalHold) as exc:
                self.fault(route+"_SOURCE_HOLD_"+str(exc))
                break
            except Exception as exc:
                self.interrupted=True
                self.policy.on_disconnect(route,"WSS_CONNECTION_FAULT")
                self.stats["reconnect_attempts"]+=1
                tries+=1
                if tries>3:
                    self.fault(route+"_RETRY_BUDGET_EXHAUSTED")
                    break
                try:
                    wait=self.policy.retry_delay(route)
                except FeedRecoveryHold as error:
                    self.fault(str(error))
                    break
                await asyncio.sleep(wait)
            finally:
                if connected:
                    session.disconnect(route)
                    self.policy.on_disconnect(route,"ROUTE_CLOSED")
                    if not self.stop.is_set():
                        self.interrupted=True

    async def _events(self,session,journal,finality,identity,eligible,symbols,
                      start,deadline):
        event=start
        while not self.stop.is_set() and time.monotonic()<deadline:
            due=event+INTERVAL_MS+CLOSE_GRACE_MS
            if wall_ms()<due:
                await asyncio.sleep(min(1,(due-wall_ms())/1000))
                continue
            try:
                summary=await audit_event(
                    session,journal,finality,symbols=eligible,
                    cohort_digest=identity,event_open_ms=event,
                    getter=self.getter,interrupted=self.interrupted)
                self.stats["committed_events"]+=1
                print("G1F_EVENT",json.dumps(summary,sort_keys=True),flush=True)
                resource_guard(self.path)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.fault("G1F_EVENT_HOLD_"+type(exc).__name__+"_"+str(exc))
                return
            event+=INTERVAL_MS

    async def _metrics(self,session,journal,deadline):
        while not self.stop.is_set() and time.monotonic()<deadline:
            try:
                state=resource_guard(self.path)
                if time.monotonic()-self.last_log>=METRICS_EVERY_SECONDS:
                    self.last_log=time.monotonic()
                    print("G1F_HEARTBEAT",json.dumps({
                        **state,"frames":self.stats,
                        "stream_connected": {
                            "market":session.store.health.market_connected,
                            "public":session.store.health.public_connected,
                        },
                        "trade_gaps":len(session.store.health.trade_gaps),
                        "journal_last_event":journal.latest_event(),
                        "research_ready":False,"order_authority":"NONE",
                    },sort_keys=True),flush=True)
            except Exception as exc:
                self.fault("G1F_RESOURCE_HOLD_"+str(exc))
                return
            await asyncio.sleep(2)


def main():
    parser=argparse.ArgumentParser(
        description="G1f isolated persistent OBSERVATION-ONLY; NO trading"
    )
    parser.add_argument("--db",required=True)
    parser.add_argument("--top",type=int,default=50)
    parser.add_argument("--max-seconds",type=int,default=300)
    args=parser.parse_args()
    collector=ObservationOnlyRunner(
        top=args.top,path=Path(args.db),
        max_seconds=args.max_seconds)
    async def run():
        loop=asyncio.get_running_loop()
        for name in (signal.SIGINT,signal.SIGTERM):
            try:
                loop.add_signal_handler(name,collector.stop.set)
            except NotImplementedError:
                pass
        return await collector.start()
    try:
        report=asyncio.run(run())
    except Exception as exc:
        print("G1F_HOLD",type(exc).__name__,str(exc)[:200],flush=True)
        return 2
    print("G1F_RESULT",json.dumps(report,sort_keys=True),flush=True)
    return 2 if report["result"]=="HOLD" else 0


if __name__=="__main__":
    raise SystemExit(main())
