"""CS-00 OFFLINE SOURCE-ONLY G2/G3/G4 integration. No network/start/orders."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import threading
import os
import json
from contextlib import nullcontext
from .cs00_state_writer import SourceOnlyStateWriter, state_gate
from .core import FiveMinuteEvent
from .observation import ObservationBook,ClosedBar
from .exploration import explore_event
from .deep_selection import choose_deep
from .deep_segments import DeepSegmentRecorder,DeepSegmentHold
from .cs00_source_runtime import SourceOnlyIntake,CollectorHold
from .cs00_supervisor import SourceOnlySupervisor,Heartbeat
from .cs00_commissioning import CommissioningHold

VERSION="NBOT_V5_1_CS00_SOURCE_PIPELINE_V1"

@dataclass(frozen=True)
class SourceBoundary:
    event_open_ms:int
    broad:int
    directions:int
    deep:int
    deep_sha256:str
    metadata_healthy:int
    metadata_holds:int
    raw_gaps:int
    source_class:str="LOCAL_UNQUALIFIED_NO_ORIGINAL_RELEASE"
    action:str="NO_TRADE"
    financial_authority:str="NONE"

class SourceOnlyPipeline:
    """Injected finalized bars and raw public-shaped frames; never opens sockets."""
    def __init__(self,observation:ObservationBook,*,recorder_root:Path|None=None,
                 quota_bytes:int=64*1024*1024,
                 state_root:Path|None=None):
        if type(observation) is not ObservationBook or len(observation.manifest.symbols)!=100:
            raise CommissioningHold("CS00_PIPELINE_BROAD100_REQUIRED")
        self.observation=observation;self.recorder_root=recorder_root
        self.state_writer=SourceOnlyStateWriter(state_root) if state_root is not None else None
        self.quota=quota_bytes;self.last_event_ms=None
        self.deep=None;self.recorder=None;self.intake=None
        self.supervisor=SourceOnlySupervisor()
        self.lock=threading.RLock();self.boundaries=0
        self.source_frames=0;self.source_gap_count=0
        self.hard_source_gap_count=0
        self.soft_source_skip_count=0
        self.active=False

    def on_closed_bar(self,bar:ClosedBar,*,decision_at_ms:int):
        with self.lock:
            if self.last_event_ms is not None and bar.open_ms<=self.last_event_ms:
                raise CommissioningHold("CS00_PIPELINE_BAR_RETROACTIVE")
            return self.observation.ingest(bar,decision_at_ms=decision_at_ms)

    def on_boundary(self,event:FiveMinuteEvent)->SourceBoundary:
        with self.lock:
            if (type(event) is not FiveMinuteEvent or
                    self.last_event_ms is not None and
                    event.event_open_ms<=self.last_event_ms):
                raise CommissioningHold("CS00_PIPELINE_BOUNDARY_REPLAY")
            snap=self.observation.snapshot(event)
            e=explore_event(self.observation,event,capacity_slots=0)
            c=choose_deep(self.observation.manifest,e,count=20)
            if (len(snap.rows)!=100 or len(e.rows)!=200 or
                    len(c.symbols)!=20 or "BTCUSDT" not in c.symbols or
                    not c.no_trade or e.evaluated_pairs):
                raise CommissioningHold("CS00_PIPELINE_100_200_20_INVALID")
            if self.deep is None:
                self.deep=c
                self.intake=SourceOnlyIntake(tuple(c.symbols))
                if self.recorder_root is not None:
                    self.recorder=DeepSegmentRecorder(self.recorder_root,
                       symbols=tuple(c.symbols),quota_bytes=self.quota)
                    if self.state_writer is not None:
                        replayed=self.recorder.attach()
                        if replayed:
                            # Recover file custody, but do not pretend an
                            # unapproved post-restart network epoch is continuous.
                            raise CommissioningHold("CS00_SOURCE_RESTART_EPOCH_REVIEW_REQUIRED")
            elif c.symbols!=self.deep.symbols:
                self.source_gap_count+=1
            # Persist complete G2/G3 first, then publish a final shared
            # checkpoint receipt. If any component fails, do not advance
            # the in-memory event cursor, and back up only after review.
            if self.state_writer is not None:
                self.state_writer.record_boundary(self.observation,snap,e)
            self.last_event_ms=event.event_open_ms;self.boundaries+=1
            return SourceBoundary(event.event_open_ms,100,200,20,
                                  self.deep.manifest_sha,snap.healthy_count,
                                  snap.hold_count,self.source_gap_count)

    def _journal_source_anomaly(self,*,kind:str,symbol:str,epoch:int,
                                received_ms:int,reason:str,source_sha256:str|None):
        if self.state_writer is None:
            return
        root=self.state_writer.root
        folder=root/"research"
        if (not folder.is_dir() or folder.is_symlink()
                or folder.stat().st_mode&0o077):
            raise CommissioningHold("CS00_SOURCE_ANOMALY_LEDGER_UNSAFE")
        record={"schema":"NBOT_V5_1_CS01_SOURCE_ANOMALY_V1",
                "kind":kind,"symbol":symbol,"epoch":epoch,
                "received_at_ms":received_ms,"reason":reason,
                "source_sha256":source_sha256,
                "grade":"UNQUALIFIED_SOURCE_EVENT",
                "financial_authority":"NONE"}
        raw=(json.dumps(record,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
        with state_gate(root):
            fd=os.open(folder/"source_anomalies.jsonl",
                       os.O_WRONLY|os.O_CREAT|os.O_APPEND|
                       getattr(os,"O_NOFOLLOW",0),0o600)
            try:
                buf=memoryview(raw)
                while buf:
                    n=os.write(fd,buf)
                    if n<=0:raise CommissioningHold("CS00_SOURCE_ANOMALY_SHORT_WRITE")
                    buf=buf[n:]
                os.fsync(fd)
            finally:os.close(fd)

    def ingest_offline_frame(self,*,kind:str,raw:bytes,received_ms:int,epoch:int):
        with self.lock:
            if self.intake is None or self.recorder is None:
                raise CommissioningHold("CS00_PIPELINE_SOURCE_NOT_FROZEN")
            try:
                status=self.intake.observe(kind=kind,raw=raw,
                                          epoch=epoch,received_ms=received_ms)
                if status.state!="LOCAL_FRAME_NOT_INDEPENDENTLY_QUALIFIED":
                    self.source_gap_count+=1
                    if status.state=="STALE_SOURCE_EVENT_SKIPPED":
                        self.soft_source_skip_count+=1
                    else:
                        self.hard_source_gap_count+=1
                    self._journal_source_anomaly(kind=kind,symbol=status.symbol,
                       epoch=epoch,received_ms=received_ms,
                       reason=status.reason or status.state,
                       source_sha256=status.raw_sha256)
                    return status
                with (state_gate(self.state_writer.root)
                      if self.state_writer is not None else nullcontext()):
                    self.recorder.append(kind=kind,raw=raw,
                                         received_at_ms=received_ms,epoch=epoch)
                self.source_frames+=1
                return status
            except (CollectorHold,DeepSegmentHold) as exc:
                self.source_gap_count+=1
                self.hard_source_gap_count+=1
                if kind in ("TRADE","QUOTE","MARK") and type(received_ms) is int and received_ms>0:
                    self.intake.mark_disconnect(kind=kind,at_ms=received_ms)
                raise CommissioningHold("CS00_PIPELINE_SOURCE_QUARANTINE:"+str(exc)[:140]) from exc

    def seal(self):
        with self.lock:
            if self.recorder is None:
                raise CommissioningHold("CS00_PIPELINE_NO_RECORDER")
            with (state_gate(self.state_writer.root)
                  if self.state_writer is not None else nullcontext()):
                return self.recorder.flush()

    def heartbeat(self,*,at_ms:int,rss_kib:int,free_disk_bytes:int,
                  queue_depth:int,boundary_lag_ms:int)->dict:
        with self.lock:
            return self.supervisor.assess(Heartbeat(
                at_ms,self.source_frames,self.source_gap_count,
                queue_depth,rss_kib,free_disk_bytes,boundary_lag_ms))

    def emergency_hold(self,*,at_ms:int,reason:str):
        with self.lock:
            if self.intake:
                for k in ("TRADE","QUOTE","MARK"):
                    self.intake.mark_disconnect(kind=k,at_ms=at_ms)
            self.source_gap_count+=1
            return self.supervisor.emergency_stop(at_ms=at_ms,reason=reason)

    def status(self):
        return {"schema":VERSION,"boundaries":self.boundaries,
                "source_frames":self.source_frames,
                "source_gap_count":self.source_gap_count,
                "hard_source_gap_count":self.hard_source_gap_count,
                "soft_stale_quote_mark_skips":self.soft_source_skip_count,
                "underlying_trade_id_review_events":(self.recorder.underlying_id_gap_reviews if self.recorder else 0),
                "source_grade":"LOCAL_UNQUALIFIED_NO_ORIGINAL_RELEASE",
                "active":self.active,"durable_state_root_attached":self.state_writer is not None,
                "original_virtual_allowed":False,
                "paper_enabled":False,"testnet_enabled":False,
                "real_enabled":False,"financial_authority":"NONE"}
