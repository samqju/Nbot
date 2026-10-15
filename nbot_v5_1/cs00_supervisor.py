"""CS-00 source-only heartbeat and emergency HOLD/restart contract.

No systemd control, subprocess, process spawn, timer, network or account APIs.
A future approved supervisor must consult this state before doing anything.
Every uncertain source epoch begins HOLD and cannot be auto-resumed.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

SCHEMA="NBOT_V5_1_CS00_SOURCE_SUPERVISOR_V1"

class SupervisorHold(ValueError):pass

@dataclass(frozen=True)
class Heartbeat:
    at_ms:int
    source_frames:int
    source_gaps:int
    queue_depth:int
    rss_kib:int
    free_disk_bytes:int
    last_five_minute_lag_ms:int
    source_grade:str="LOCAL_PUBLIC_UNQUALIFIED"
    financial_authority:str="NONE"

class SourceOnlySupervisor:
    def __init__(self,*,rss_ceiling_kib:int=256000,
                 minimum_free_disk_bytes:int=512*1024*1024,
                 max_queue:int=5000,max_boundary_lag_ms:int=1500):
        if (type(rss_ceiling_kib) is not int or rss_ceiling_kib<64000
                or type(minimum_free_disk_bytes) is not int
                or minimum_free_disk_bytes<128*1024*1024
                or type(max_queue) is not int or not 1<=max_queue<=5000
                or type(max_boundary_lag_ms) is not int
                or not 100<=max_boundary_lag_ms<=1500):
            raise SupervisorHold("CS00_SUPERVISOR_BUDGET_INVALID")
        self.rss_limit=rss_ceiling_kib
        self.disk_reserve=minimum_free_disk_bytes
        self.queue_limit=max_queue
        self.lag_limit=max_boundary_lag_ms
        self.recovery_required=True
        self.started=False
        self.state="STOPPED_OFFLINE_PRESTART_HOLD"
        self.last_heartbeat:Heartbeat|None=None
        self.incidents:tuple[tuple[int,str],...]=()

    def assess(self,h:Heartbeat):
        if not isinstance(h,Heartbeat):
            raise SupervisorHold("CS00_HEARTBEAT_FORMAT")
        vals=(h.at_ms,h.source_frames,h.source_gaps,h.queue_depth,
              h.rss_kib,h.free_disk_bytes,h.last_five_minute_lag_ms)
        if (any(type(v) is not int or v<0 for v in vals)
                or h.at_ms<=0 or h.financial_authority!="NONE"
                or h.source_grade!="LOCAL_PUBLIC_UNQUALIFIED"
                or self.last_heartbeat and h.at_ms<=self.last_heartbeat.at_ms):
            raise SupervisorHold("CS00_HEARTBEAT_INVALID_OR_REPLAY")
        old=self.last_heartbeat
        self.last_heartbeat=h
        issues=[]
        if h.rss_kib>=self.rss_limit:issues.append("MEMORY_PRESSURE_HOLD")
        if h.free_disk_bytes<self.disk_reserve:issues.append("STORAGE_PRESSURE_HOLD")
        if h.queue_depth>=self.queue_limit:issues.append("QUEUE_PRESSURE_HOLD")
        if h.last_five_minute_lag_ms>self.lag_limit:issues.append("FIVE_MINUTE_LATE_HOLD")
        if old and h.source_gaps>old.source_gaps:issues.append("NEW_SOURCE_GAP_HOLD")
        if old and h.source_frames<old.source_frames:issues.append("CURSOR_RESET_HOLD")
        if issues:
            self.recovery_required=True
            self.state="EMERGENCY_SOURCE_HOLD"
            self.incidents+=tuple((h.at_ms,x) for x in issues)
        return {"state":self.state,"alerts":tuple(issues),
                "new_virtual_admissions_allowed":False,
                "financial_authority":"NONE"}

    def emergency_stop(self,*,at_ms:int,reason:str):
        if (type(at_ms) is not int or at_ms<1
                or type(reason) is not str or not reason or len(reason)>100):
            raise SupervisorHold("CS00_EMERGENCY_STOP_ARGS")
        self.recovery_required=True
        self.state="EMERGENCY_SOURCE_HOLD"
        self.incidents+=((at_ms,reason),)
        return {"state":self.state,"must_stop_source_only_intake":True,
                "restart_without_epoch_audit":False,
                "financial_authority":"NONE"}

    def prestart_review(self):
        payload={"schema":SCHEMA,"state":self.state,
                 "last_heartbeat":self.last_heartbeat.__dict__
                     if self.last_heartbeat else None,
                 "recovery_required":self.recovery_required,
                 "incidents":self.incidents,
                 "production_started":self.started,
                 "auto_restart_permitted":False,
                 "paper_testnet_real_order_authority":"NONE"}
        payload["sha256"]=sha256(json.dumps(payload,sort_keys=True,
                   separators=(",",":")).encode("ascii")).hexdigest()
        return payload
