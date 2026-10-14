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
import hashlib
import os
from pathlib import Path
import resource
import signal
import time

from nbot.v5.candle_ledger import EvidenceHold
from nbot.v5.finality_quarantine import FinalityQuarantine
from nbot.v5.g1f_engine import audit_event, feed_holds
from nbot.v5.g1f_journal import CandidateJournal, JournalHold
from nbot.v5.g2_source_witness import SourceWitness, WitnessHold
from nbot.v5.g3_context_ledger import G3ContextLedger
from nbot.v5.g1f_journal import digest as cohort_digest
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.public_market import (
    closed_event_from_server_time, public_get, select_universe,
)
from nbot.v5.reconnect_policy import ReconnectPolicy, FeedRecoveryHold
from nbot.v5.ws_contract import UnsafeStream, stream_urls

MAX_RSS_MIB=192
MAX_DB_MIB=256
MAX_FRAMES_PER_5M=750000  # bounded HOLD; no automatic restart
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



def record_restart_hold_events(session, journal, cohort_digest, eligible,
                               *, current_closed_event_ms: int,
                               observed_ms: int) -> int:
    """Persist every missed/unfinalized 5m window as UNSCORABLE on restart.

    Never infer hypothetical trades or retroactive trade/quote health.
    Limit repair markers to 96 events; larger gaps require owner review.
    """
    # A test or first-ever startup may not have created finality tables yet.
    # Their schema is append-only; reinitialization never rewrites evidence.
    FinalityQuarantine(session.ledger.db)
    previous=journal.latest_event()
    unfinished=session.ledger.db.execute("""
        SELECT event_open_ms FROM v5_wss_final_proof
        WHERE event_open_ms NOT IN (
            SELECT event_open_ms FROM g1f_event_manifest
        )
        UNION
        SELECT event_open_ms FROM v5_finality_checks
        WHERE event_open_ms NOT IN (
            SELECT event_open_ms FROM g1f_event_manifest
        )
        UNION
        SELECT open_ms FROM candle_rows
        WHERE first_source='WSS_FINAL'
          AND open_ms NOT IN (
              SELECT event_open_ms FROM g1f_event_manifest
          )
        ORDER BY event_open_ms
    """).fetchall()
    if unfinished and unfinished[-1][0]>current_closed_event_ms:
        raise EvidenceHold("G1F_RESTART_FUTURE_SOURCE_EVENT")
    if previous is None and unfinished:
        previous=unfinished[0][0]-INTERVAL_MS
    if previous is None or previous>=current_closed_event_ms:
        return 0
    delta=current_closed_event_ms-previous
    if delta%INTERVAL_MS:
        raise EvidenceHold("G1F_RESTART_EVENT_NOT_ALIGNED")
    missing=delta//INTERVAL_MS
    if missing>MAX_CATCHUP_EVENTS:
        raise EvidenceHold("G1F_RESTART_GAP_OVER_96_EVENTS")
    for i in range(1,missing+1):
        opened=previous+i*INTERVAL_MS
        journal.commit_event(
            cohort_digest=cohort_digest,event_open_ms=opened,
            observed_ms=observed_ms,eligible_symbols=eligible,
            candles_by_symbol={},quarantine={},
            health_holds={s:("PROCESS_WAS_OFFLINE",) for s in eligible},
            btc_valid=False,coverage_valid=False,
        )
    return missing

class ObservationOnlyRunner:
    def __init__(self, *, top: int, path: Path, max_seconds: int,
                 getter=public_get, g2_source_witness: bool = False,
                 g3_context: bool = False):
        if (type(top) is not int or not 2<=top<=50
                or type(max_seconds) is not int
                or not (max_seconds==0 or 30<=max_seconds<=3600)):
            raise ValueError("G1F_ARGUMENTS_INVALID")
        path=Path(path).expanduser()
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise EvidenceHold("G1F_DB_PARENT_MISSING_OR_LINK")
        if type(g2_source_witness) is not bool:
            raise ValueError("G2_WITNESS_MODE_INVALID")
        if type(g3_context) is not bool or (g3_context and not g2_source_witness):
            raise ValueError("G3_REQUIRES_G2_WITNESSED_COHORT")
        self.g2_source_witness=g2_source_witness
        self.g3_context=g3_context
        self.top=top
        self.path=path
        self.max_seconds=max_seconds
        self.getter=getter
        self.stop=asyncio.Event()
        self.failed_reason=None
        self.interrupted=False
        self.stats={"market_frames":0,"public_frames":0,
                    "committed_events":0,"restart_missing_events":0,
                    "reconnect_attempts":0,"reverified_epochs":0}
        self.last_log=time.monotonic()
        self.route_window_started={"market":time.monotonic(),
                                   "public":time.monotonic()}
        self.route_window_frames={"market":0,"public":0}

    def fault(self, reason):
        self.failed_reason=str(reason)[:150]
        self.stop.set()

    def _source_epoch_candidate(self, session, eligible, event_open_ms):
        """Only fresh per-coin WSS data may request epoch rehabilitation.

        This does NOT clear the interruption or bypass the three REST
        finality stages. A failed candidate remains a recorded HOLD.
        """
        if not self.interrupted:
            return False
        holds=feed_holds(
            session,eligible,event_open_ms=event_open_ms,
            measured_ms=wall_ms(),interrupted=False)
        return all(not holds.get(symbol,("SOURCE_WITNESS_MISSING",))
                   for symbol in eligible)

    def _accept_source_epoch(self, session, event_open_ms):
        """Accept NEW epoch only after its complete 5m event is committed.

        The original interrupted epoch and every earlier HOLD are retained.
        """
        if not self.interrupted:
            return False
        for route in ("market","public"):
            if not self.policy.routes[route].connected:
                raise FeedRecoveryHold("G1F_RECOVERY_ROUTE_DISCONNECTED")
        for route in ("market","public"):
            self.policy.accept_reverified(route)
        self.interrupted=False
        self.stats["reverified_epochs"]+=1
        print("G1F_SOURCE_EPOCH_REVERIFIED",json.dumps({
            "event_open_ms":event_open_ms,
            "market_epoch":session.generations["market"],
            "public_epoch":session.generations["public"],
            "prior_gap_remains_recorded":True,
        },sort_keys=True),flush=True)
        return True

    async def start(self):
        now_response=await asyncio.to_thread(self.getter,"/fapi/v1/time")
        event,binance_ms=closed_event_from_server_time(now_response)
        if abs(wall_ms()-binance_ms)>90000:
            raise EvidenceHold("G1F_BINANCE_CLOCK_SKEW")
        exchange=await asyncio.to_thread(self.getter,"/fapi/v1/exchangeInfo")
        ticker=await asyncio.to_thread(self.getter,"/fapi/v1/ticker/24hr")
        eligible=select_universe(exchange,ticker,limit=self.top)
        selection_received_ms=wall_ms()
        symbols=tuple(sorted(set(eligible)|{"BTCUSDT"}))
        uri=stream_urls(eligible,quote_mode="depth5@500ms")
        started=time.monotonic()
        deadline=(started+self.max_seconds
                  if self.max_seconds else float("inf"))
        # For a witnessed operational restart, reuse ORIGINAL cohort members.
        # Never re-rank with fresh 24h volumes or replace old source evidence.
        # SQLite is read-only here; every old record stays immutable.
        existing=None
        if self.g2_source_witness and self.path.is_file():
            import sqlite3
            with sqlite3.connect(self.path.resolve().as_uri()+"?mode=ro",uri=True) as previous:
                present=previous.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='g1f_universe_snapshots'").fetchone()
                if present:
                    cohorts=previous.execute(
                        "SELECT cohort_digest,symbols_json FROM g1f_universe_snapshots").fetchall()
                    if len(cohorts)!=1:
                        raise EvidenceHold("G2_RESTART_COHORT_NOT_UNIQUE")
                    prev_digest,original_symbols=cohorts[0]
                    previous_witness=previous.execute(
                        "SELECT payload_json,payload_sha FROM g2_cohort_witness "
                        "WHERE cohort_digest=?",(prev_digest,)).fetchone()
                    if not previous_witness:
                        raise EvidenceHold("G2_RESTART_ORIGINAL_WITNESS_MISSING")
                    raw,sha=previous_witness
                    if hashlib.sha256(raw.encode()).hexdigest()!=sha:
                        raise EvidenceHold("G2_RESTART_ORIGINAL_SHA_CHANGED")
                    data=json.loads(raw)
                    frozen=tuple(json.loads(original_symbols))
                    if (tuple(sorted(data["ranked_selected"]))!=frozen
                            or data["cohort_digest"]!=prev_digest
                            or prev_digest!=cohort_digest({
                                "selection_version":"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                                "symbols":frozen
                            })):
                        raise EvidenceHold("G2_RESTART_ORIGINAL_COHORT_CONFLICT")
                    eligible=frozen
                    symbols=frozen
                    uri=stream_urls(eligible,quote_mode="depth5@500ms")
                    existing=prev_digest
        with ObservationContinuity(eligible,self.path) as session:
            journal=CandidateJournal(session.ledger.db)
            finality=FinalityQuarantine(session.ledger.db)
            identity=journal.begin_cohort(
                eligible,selected_ms=binance_ms,event_open_ms=event)
            witness=None
            if self.g2_source_witness:
                # This intentionally fails closed for historical, unwitnessed
                # DBs: a new source snapshot CANNOT authenticate past events.
                prior_events=session.ledger.db.execute(
                    "SELECT COUNT(*) FROM g1f_event_manifest").fetchone()[0]
                prior_witness=session.ledger.db.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                    "AND name='g2_cohort_witness'").fetchone()[0]
                if prior_events and not prior_witness:
                    raise EvidenceHold("G2_UNWITNESSED_LEGACY_DB_FORBIDDEN")
                witness=SourceWitness(session.ledger.db)
                if existing is not None:
                    witness_digest=existing
                else:
                    witness_digest=witness.witness_cohort(
                        exchange=exchange,ticker=ticker,selected=eligible,
                        received_ms=selection_received_ms,
                        first_event_open_ms=event,
                        exchange_server_ms=binance_ms)
                if witness_digest!=identity:
                    raise EvidenceHold("G2_SOURCE_COHORT_HASH_MISMATCH")
            # REST historical sync before any WebSocket frame can enter.
            await rest_seed(session,symbols,event,getter=self.getter)
            # Old G1f operational mode has explicit UNSCORABLE offline
            # markers. Strict G2 mode cannot fabricate at-event quote
            # witnesses for offline periods; preserve real temporal gaps,
            # flag the first resumed interval, and let acceptance audit
            # distinguish explicitly unobserved history from observations.
            if self.g2_source_witness:
                earlier=journal.latest_event()
                if earlier is not None:
                    delta=event-earlier
                    if delta<0 or delta%INTERVAL_MS:
                        raise EvidenceHold("G2_RESTART_EVENT_CLOCK_REWIND")
                    if delta//INTERVAL_MS>MAX_CATCHUP_EVENTS:
                        raise EvidenceHold("G2_RESTART_GAP_OVER_96_WINDOWS")
                    self.stats["restart_missing_events"]=max(0,delta//INTERVAL_MS)
            else:
                self.stats["restart_missing_events"]+=record_restart_hold_events(
                    session,journal,identity,eligible,
                    current_closed_event_ms=event,observed_ms=wall_ms(),
                )
            context=G3ContextLedger(session.ledger.db) if self.g3_context else None
            if context:
                pending=session.ledger.db.execute(
                    "SELECT m.event_open_ms FROM g1f_event_manifest m "
                    "LEFT JOIN g3_event_context g ON m.event_open_ms=g.event_open_ms "
                    "WHERE g.event_open_ms IS NULL ORDER BY m.event_open_ms LIMIT 97"
                ).fetchall()
                if len(pending)>96:
                    raise EvidenceHold("G3_UNRECONCILED_CONTEXT_OVER_96_EVENTS")
                for (prior_event,) in pending:
                    print("G3_RECOVERY",json.dumps(context.record(
                        event_open_ms=prior_event,symbols=tuple(eligible)
                    ),sort_keys=True),flush=True)
            self.policy=ReconnectPolicy()
            tasks=[
                asyncio.create_task(self._route(
                    route,uri[route],session,deadline))
                for route in ("market","public")
            ]
            coordinator=asyncio.create_task(self._events(
                session,journal,finality,identity,eligible,symbols,
                event+INTERVAL_MS,deadline,source_witness=witness,
                g3_ledger=context))
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
                "g2_source_witness_enabled":self.g2_source_witness,
                "g3_context_enabled":self.g3_context,
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
        while not self.stop.is_set() and time.monotonic()<deadline:
            connected=False
            retry=False
            try:
                async with connect(
                    uri,open_timeout=9,close_timeout=2,
                    ping_interval=20,ping_timeout=20,
                    max_size=64000,max_queue=16,
                ) as socket:
                    session.connect(route)
                    self.policy.on_connect(route)
                    connected=True
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
                        if time.monotonic()-self.route_window_started[route]>=300:
                            self.route_window_started[route]=time.monotonic()
                            self.route_window_frames[route]=0
                        self.route_window_frames[route]+=1
                        if self.route_window_frames[route]>MAX_FRAMES_PER_5M:
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
                # Disconnect exactly once, before consulting retry_delay.
                self.interrupted=True
                retry=True
                self.stats["reconnect_attempts"]+=1
            finally:
                if connected:
                    session.disconnect(route)
                    self.policy.on_disconnect(
                        route,"WSS_CONNECTION_FAULT" if retry else "ROUTE_CLOSED")
                    if not self.stop.is_set():
                        self.interrupted=True
            if retry and not self.stop.is_set():
                try:
                    wait=self.policy.retry_delay(route)
                except FeedRecoveryHold as error:
                    self.fault(str(error))
                    break
                await asyncio.sleep(wait)

    async def _events(self,session,journal,finality,identity,eligible,symbols,
                      start,deadline, *, source_witness=None,g3_ledger=None):
        event=start
        while not self.stop.is_set() and time.monotonic()<deadline:
            due=event+INTERVAL_MS+CLOSE_GRACE_MS
            if wall_ms()<due:
                await asyncio.sleep(min(1,(due-wall_ms())/1000))
                continue
            try:
                recovery_candidate=self._source_epoch_candidate(
                    session,eligible,event)
                summary=await audit_event(
                    session,journal,finality,symbols=eligible,
                    cohort_digest=identity,event_open_ms=event,
                    getter=self.getter,
                    interrupted=self.interrupted and not recovery_candidate,
                    source_witness=source_witness)
                self.stats["committed_events"]+=1
                if recovery_candidate and summary.get("status")=="OBSERVE_ONLY":
                    self._accept_source_epoch(session,event)
                print("G1F_EVENT",json.dumps(summary,sort_keys=True),flush=True)
                if g3_ledger is not None:
                    recorded=g3_ledger.record(
                        event_open_ms=event,symbols=tuple(eligible))
                    print("G3_EVENT",json.dumps(recorded,sort_keys=True),flush=True)
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
    parser.add_argument("--g2-source-witness",action="store_true",
                        help="Opt-in complete as-of source witnesses (fresh or frozen DB)")
    parser.add_argument("--g3-context",action="store_true",
                        help="Append-only causal G3 BTC and 50-coin contexts (requires G2)")
    args=parser.parse_args()
    collector=ObservationOnlyRunner(
        top=args.top,path=Path(args.db),
        max_seconds=args.max_seconds,
        g2_source_witness=args.g2_source_witness,
        g3_context=args.g3_context)
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
