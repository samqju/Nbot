"""CS-00 installation-free future PUBLIC-ONLY observation service skeleton.

IMPORTANT: NO network or service starts at import/construction. A future
CS-01 owner-approved release (exact git/config SHA plus owner approval ID)
must be explicitly supplied to run_foreground, and is separately reviewed.
No order/account/private endpoints; no virtual or PAPER activation.

When a worker loses source, reject new admissions and stop acquisition with
an explicit epoch HOLD. No reconnect "smooths over" missing market data.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import os
import resource
from pathlib import Path
import re
import threading
import time

from .core import FiveMinuteEvent,INTERVAL_MS
from .observation import rest_closed_bar
from .public_market import PublicUsdMClient, PublicMarketHold
from .cs00_source_pipeline import SourceOnlyPipeline
from .cs00_public_ws import PublicTlsSocket,PublicSocketHold
from .cs00_recovery_worker import BudgetedPublicRest,RecoveryScheduler
from .cs00_history_recovery import HistoricalAggTradeRecovery,SourceRecoveryHold
from .cs00_compact_backup import CompactBackupHold

VERSION="NBOT_V5_1_CS00_FOREGROUND_PUBLIC_ONLY_SERVICE_V1"
SHA=re.compile(r"[a-f0-9]{40}\Z")
ACTION=re.compile(r"CS01-OWNER-[A-Za-z0-9-]{8,80}\Z")

class PublicServiceHold(ValueError):pass

@dataclass(frozen=True)
class FutureCs01Permit:
    """Owner approval receipt (external authorization reviewed separately)."""
    project:str
    branch:str
    exact_commit_sha:str
    release_action_id:str
    approved_mode:str
    expires_at_ms:int

    def validate(self,*,expected_sha:str,now_ms:int):
        if (self.project!="NBOT_V5.1" or self.branch!="nbot-v5.1"
                or self.approved_mode!="PUBLIC_OBSERVATION_ONLY"
                or type(expected_sha) is not str or not SHA.fullmatch(expected_sha)
                or type(self.exact_commit_sha) is not str
                or self.exact_commit_sha!=expected_sha
                or type(self.release_action_id) is not str
                or not ACTION.fullmatch(self.release_action_id)
                or type(self.expires_at_ms) is not int
                or self.expires_at_ms<=now_ms or self.expires_at_ms>now_ms+86400000):
            raise PublicServiceHold("CS00_CS01_EXPLICIT_APPROVAL_SHA_MODE_OR_EXPIRY")
        return self

class FuturePublicObservationService:
    """Only run_foreground starts network; normal status always STOPPED.

    This opt-in class is a code artifact, *not installed*. It is not a
    production approval and has never been exercised with live feeds in CS-00.
    """
    def __init__(self,*,source_root:Path,code_sha:str):
        if (type(code_sha) is not str or not SHA.fullmatch(code_sha)
                or not isinstance(source_root,Path) or not source_root.is_absolute()
                or source_root.is_symlink()):
            raise PublicServiceHold("CS00_SERVICE_CONFIG_INVALID")
        self.root=source_root
        self.code_sha=code_sha
        self.stop_event=threading.Event()
        self.pipeline=None
        self.recovery_scheduler=None
        self.workers=[]
        self.started=False
        self.exit_reason="NOT_STARTED_CS00"
        self.errs=[]
        self.last_feed_received_ms={}
        self.launch_ms=None

    def status(self):
        return {"schema":VERSION,"source_process_started":self.started,
                "mode":"PUBLIC_OBSERVATION_ONLY" if self.started else "STOPPED_CS00",
                "owner_cs01_release_required":True,
                "no_public_network_without_release":True,
                "virtual_research_enabled":False,"paper_enabled":False,
                "testnet_enabled":False,"real_trading_enabled":False,
                "model_promotion_enabled":False,
                "exchange_order_capability":False,"financial_authority":"NONE",
                "stop_reason":self.exit_reason}

    def request_stop(self,reason:str="MANUAL_OWNER_STOP"):
        if type(reason) is not str or not 1<=len(reason)<=100:
            raise PublicServiceHold("CS00_SERVICE_STOP_REASON")
        self.exit_reason=reason;self.stop_event.set()

    def _worker(self,kind:str,url:str,epoch:int):
        ws=PublicTlsSocket(url)
        try:
            ws.connect(approved_cs01_public_only=True)
            while not self.stop_event.is_set():
                data=ws.read_message()
                received=int(time.time()*1000)
                self.last_feed_received_ms[kind]=received
                before=None
                try:
                    frame=json.loads(data)
                    symbol=frame["data"]["s"]
                    before=self.pipeline.intake.cursor.get((kind,symbol))
                except (KeyError,TypeError,ValueError):
                    pass
                current=self.pipeline.ingest_offline_frame(kind=kind,raw=data,
                                                        received_ms=received,epoch=epoch)
                if kind=="TRADE" and current.state=="SOURCE_HOLD" and before:
                    # A recovered traded-price path is NOT automatically a
                    # healthy live epoch/quote/mark or scientific label.
                    if (before.aggregate_id is not None and
                            current.aggregate_id is not None and
                            current.aggregate_id>before.aggregate_id+1):
                        try:
                            gap=HistoricalAggTradeRecovery(
                                experiment_id=sha256(
                                    f"{symbol}:{epoch}:{before.aggregate_id}:{current.aggregate_id}"
                                    .encode()).hexdigest(),
                                symbol=symbol,
                                first_agg_id=before.aggregate_id+1,
                                last_agg_id=current.aggregate_id-1,
                                gap_start_ms=before.received_ms,
                                gap_end_ms=received,
                                now_ms=received)
                            self.recovery_scheduler.admit(gap,now_ms=received)
                        except (SourceRecoveryHold,ValueError) as e:
                            self.errs.append("RECOVERY_TASK_HOLD:"+str(e)[:60])
                if current.state=="SOURCE_HOLD":
                    # A retrospective recovery task never repairs a live
                    # decision-time source epoch. Stop any new intake now.
                    self.pipeline.emergency_hold(
                        at_ms=received,reason="LIVE_SOURCE_GAP_FORCED_HOLD")
                    self.request_stop("LIVE_SOURCE_GAP_NO_UNQUALIFIED_CONTINUATION")
                    break
            ws.close()
        except (PublicSocketHold,OSError,ValueError) as e:
            self.errs.append("PUBLIC_SOURCE_HOLD:"+str(e)[:80])
            self.pipeline.emergency_hold(
                at_ms=max(1,int(time.time()*1000)),reason="PUBLIC_SOCKET_UNKNOWN")
            self.request_stop("SOURCE_DISCONNECT_NO_AUTO_RESTART")
        finally:
            ws.close()

    def _update_100_closed_bars(self,*,event_open_ms:int):
        """Acquire finished public GET-only 5m metadata, never invent candles."""
        c=PublicUsdMClient(allow_public_network=True,weight_budget=350)
        for symbol in self.pipeline.observation.manifest.symbols:
            if self.stop_event.is_set():break
            try:
                r=c.closed_klines(symbol,limit=100)
                target=next((v for v in r.body
                    if type(v) is list and len(v)>6
                    and v[0]==event_open_ms and v[6]+1<=r.received_at_ms),None)
                if target is None:raise PublicServiceHold("CS00_FINAL_CANDLE_MISSING")
                b=rest_closed_bar(symbol,target,known_at_ms=r.received_at_ms,
                                  epoch=0,route="public_rest")
                if not self.pipeline.on_closed_bar(b,decision_at_ms=r.received_at_ms):
                    raise PublicServiceHold("CS00_UNVERIFIED_NEW_FINAL_BAR")
            except (ValueError,TypeError,PublicMarketHold,PublicServiceHold) as e:
                self.pipeline.observation.mark_gap(symbol,reason="SOURCE_GAP")

    def run_foreground(self,*,permit:FutureCs01Permit,expected_exact_sha:str):
        """Manual foreground source-only service, not invoked by CS-00 tests.

        SOURCE CONTINUITY and off-host archive verification are future
        CS-01/G4 gates. No persistent service or auto-restart is created.
        """
        if self.started or self.stop_event.is_set():
            raise PublicServiceHold("CS00_SERVICE_ALREADY_USED")
        if type(permit) is not FutureCs01Permit:
            raise PublicServiceHold("CS00_CS01_OWNER_AUTH_REQUIRED")
        permit.validate(expected_sha=expected_exact_sha,
                        now_ms=int(time.time()*1000))
        if self.code_sha!=expected_exact_sha:
            raise PublicServiceHold("CS00_CODE_SHA_MISMATCH")
        # Source directory must already have been reviewed/created under
        # a separate owner-approved deployment change. No implicit mkdir.
        if (not self.root.is_dir() or self.root.is_symlink()
                or self.root.stat().st_mode & 0o077):
            raise PublicServiceHold("CS00_SOURCE_ROOT_NOT_PRIVATE")
        from scripts.g2_readonly_probe import probe
        slot={}
        def on_event(book,event):
            app=SourceOnlyPipeline(book,recorder_root=self.root/"evidence",
                                   state_root=self.root)
            app.on_boundary(event)
            slot["pipeline"]=app
            return {"source_only":True,"financial_authority":"NONE"}
        self.started=True
        try:
            probe(enabled=True,on_event=on_event)
            if "pipeline" not in slot:raise PublicServiceHold("CS00_BOOTSTRAP_UNAVAILABLE")
            self.pipeline=slot["pipeline"]
            self.pipeline.active=True
            self.pipeline.supervisor.started=True
            self.pipeline.supervisor.state="PUBLIC_SOURCE_HOLD_UNQUALIFIED"
            self.launch_ms=int(time.time()*1000)
            self.recovery_scheduler=RecoveryScheduler(
                BudgetedPublicRest(allow_public_network=True,
                                   weight_budget=MAX_SERVICE_REST_WEIGHT))
            from .cs00_source_runtime import public_routes
            for route in public_routes(tuple(self.pipeline.deep.symbols)):
                t=threading.Thread(target=self._worker,
                        args=(route.kind,route.uri,1),daemon=True)
                self.workers.append(t);t.start()
            last_boundary=self.pipeline.last_event_ms
            last_health_ms=0
            last_boundary_lag_ms=0
            while not self.stop_event.is_set():
                if any(not t.is_alive() for t in self.workers):
                    self.request_stop("PUBLIC_WORKER_DIED")
                    break
                now=int(time.time()*1000)
                if now%INTERVAL_MS<3000:
                    event_open_ms=(now//INTERVAL_MS-1)*INTERVAL_MS
                    if event_open_ms>last_boundary:
                        self._update_100_closed_bars(event_open_ms=event_open_ms)
                        self.pipeline.on_boundary(FiveMinuteEvent(event_open_ms,now))
                        last_boundary=event_open_ms
                        last_boundary_lag_ms=max(0,now-(event_open_ms+INTERVAL_MS))
                self.pipeline.seal()
                if now-last_health_ms>=1000:
                    st=os.statvfs(self.root)
                    free=st.f_bavail*st.f_frsize
                    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    depth=len(self.pipeline.recorder.queue) if self.pipeline.recorder else 0
                    h=self.pipeline.heartbeat(at_ms=now,rss_kib=rss,
                        free_disk_bytes=free,queue_depth=depth,
                        boundary_lag_ms=last_boundary_lag_ms)
                    last_health_ms=now
                    if h["state"]=="EMERGENCY_SOURCE_HOLD":
                        self.request_stop("RESOURCE_SOURCE_HEALTH_HOLD")
                        break
                    if (now-self.launch_ms>120000 and
                            any(now-self.last_feed_received_ms.get(k,self.launch_ms)>120000
                                for k in ("TRADE","QUOTE","MARK"))):
                        self.pipeline.emergency_hold(
                            at_ms=now,reason="WSS_ROUTE_STALE_HOLD")
                        self.request_stop("SOURCE_STALE_NO_AUTO_RESTART")
                        break
                if self.recovery_scheduler.tasks:
                    self.recovery_scheduler.step(now_ms=now)
                self.stop_event.wait(1)
        except Exception:
            self.request_stop("SOURCE_SERVICE_EXCEPTION_HOLD")
            raise
        finally:
            self.stop_event.set()
            for t in self.workers:t.join(timeout=12)
            if self.pipeline:
                try:self.pipeline.seal()
                except Exception:self.exit_reason="SHUTDOWN_SEAL_UNCERTAIN_HOLD"
            if self.pipeline:
                self.pipeline.active=False
                self.pipeline.supervisor.started=False
            self.started=False

MAX_SERVICE_REST_WEIGHT=300
