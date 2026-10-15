"""CS-00: public USD-M historical gap-recovery scheduler and budgeted REST client.

No order paths, credentials, account requests, daemon or network on import.
Client network is opt-in and its fixed HTTPS origin/path can never be changed.
For CS-00 tests supply a callable transport; operator must separately approve
a future public-only collector start in CS-01.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .cs00_history_recovery import HistoricalAggTradeRecovery, SourceRecoveryHold

VERSION="NBOT_V5_1_CS00_PUBLIC_RECOVERY_WORKER_V1"
HOST="https://fapi.binance.com"
MAX_RETRIES=4
WEIGHT_PER_PAGE=20
MAX_WEIGHT_PER_MIN=600

class RecoveryTransportHold(ValueError):pass

class _NeverRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RecoveryTransportHold("CS00_REST_REDIRECT_DENIED")

@dataclass(frozen=True)
class RecoveryTaskState:
    symbol:str
    status:str
    next_attempt_ms:int
    pages:int
    attempts:int
    reason:str|None
    trade_path_only:bool=True
    cost_qualified:bool=False
    order_authority:str="NONE"

class BudgetedPublicRest:
    """Fixed public REST path, global rolling request weight, no credentials."""
    def __init__(self,*,allow_public_network:bool=False,transport=None,
                 timeout_sec:int=8,weight_budget:int=MAX_WEIGHT_PER_MIN):
        if (type(allow_public_network) is not bool
                or type(timeout_sec) is not int or not 1<=timeout_sec<=20
                or type(weight_budget) is not int or
                not WEIGHT_PER_PAGE<=weight_budget<=MAX_WEIGHT_PER_MIN):
            raise RecoveryTransportHold("CS00_REST_CONFIGURATION_INVALID")
        if transport is not None and not callable(transport):
            raise RecoveryTransportHold("CS00_REST_TRANSPORT_MUST_BE_CALLABLE")
        self.allowed=allow_public_network
        self.transport=transport
        self.timeout=timeout_sec
        self.budget=weight_budget
        self.entries:list[tuple[int,int]]=[]
        self.requests=0

    def get_page(self,path:str,*,now_ms:int)->bytes:
        if (type(now_ms) is not int or now_ms<=0 or
                type(path) is not str or
                not path.startswith("/fapi/v1/aggTrades?") or
                len(path)>200 or
                "@" in path or "#" in path or
                urlsplit(path).path!="/fapi/v1/aggTrades"):
            raise RecoveryTransportHold("CS00_REST_NOT_PUBLIC_AGGTRADES")
        # Require exclusively the three bounded expected parameters.
        from urllib.parse import parse_qs
        q=parse_qs(urlsplit(path).query,keep_blank_values=True)
        if (set(q)!={"symbol","fromId","limit"} or any(len(v)!=1 for v in q.values())
                or not q["symbol"][0].endswith("USDT")
                or not q["symbol"][0].isalnum()
                or not q["fromId"][0].isdigit() or not q["limit"][0].isdigit()
                or not 1<=int(q["limit"][0])<=1000):
            raise RecoveryTransportHold("CS00_REST_QUERY_INVALID")
        self.entries=[e for e in self.entries if e[0]>now_ms-60000]
        if sum(x[1] for x in self.entries)+WEIGHT_PER_PAGE>self.budget:
            raise RecoveryTransportHold("CS00_REST_GLOBAL_WEIGHT_HOLD")
        if not self.allowed:
            raise RecoveryTransportHold("CS00_REST_NO_NETWORK_PERMISSION")
        self.entries.append((now_ms,WEIGHT_PER_PAGE))
        self.requests+=1
        try:
            if self.transport:
                result=self.transport(HOST+path,self.timeout)
            else:
                opener=urllib.request.build_opener(_NeverRedirect)
                request=urllib.request.Request(HOST+path,headers={
                    "Accept":"application/json","User-Agent":"NBOT-V5.1-Public-Research"})
                with opener.open(request,timeout=self.timeout) as response:
                    if response.status!=200:
                        raise RecoveryTransportHold("CS00_REST_STATUS_HOLD")
                    if response.headers.get("Content-Type","").split(";")[0]!="application/json":
                        raise RecoveryTransportHold("CS00_REST_MIME_HOLD")
                    result=response.read(2*1024*1024+1)
            if type(result) is not bytes or not 0<len(result)<=2*1024*1024:
                raise RecoveryTransportHold("CS00_REST_RESPONSE_SIZE_OR_TYPE")
            return result
        except (urllib.error.URLError,TimeoutError,OSError) as e:
            raise RecoveryTransportHold("CS00_REST_TIMEOUT_OR_NETWORK_HOLD") from e

class RecoveryScheduler:
    """Bounded fair-share multi-symbol recovery. Never silently 'win' or drop."""
    def __init__(self,client:BudgetedPublicRest,*,max_tasks:int=40):
        if not isinstance(client,BudgetedPublicRest) or type(max_tasks) is not int or not 1<=max_tasks<=40:
            raise RecoveryTransportHold("CS00_SCHEDULER_CONFIG")
        self.client=client
        self.max_tasks=max_tasks
        self.tasks:dict[str,HistoricalAggTradeRecovery]={}
        self.next_at:dict[str,int]={}
        self.attempts:dict[str,int]={}
        self.pages:dict[str,int]={}
        self.hold_reasons:dict[str,str]={}

    def admit(self,recovery:HistoricalAggTradeRecovery,*,now_ms:int):
        if (not isinstance(recovery,HistoricalAggTradeRecovery) or
                type(now_ms) is not int or now_ms<recovery.now_ms or
                recovery.experiment_id in self.tasks or len(self.tasks)>=self.max_tasks):
            raise RecoveryTransportHold("CS00_RECOVERY_TASK_ADMISSION_HOLD")
        self.tasks[recovery.experiment_id]=recovery
        self.next_at[recovery.experiment_id]=now_ms
        self.attempts[recovery.experiment_id]=0
        self.pages[recovery.experiment_id]=0

    def step(self,*,now_ms:int):
        if type(now_ms) is not int or now_ms<=0:
            raise RecoveryTransportHold("CS00_RECOVERY_CLOCK")
        # At most one network request per step. Schedule due tasks fairly.
        due=[key for key,r in self.tasks.items() if key not in self.hold_reasons
             and r.state=="RECOVERY_PENDING" and now_ms>=self.next_at[key]]
        if not due:
            return None
        due.sort(key=lambda k:(self.pages[k],self.next_at[k],k))
        key=due[0]
        recovery=self.tasks[key]
        path=recovery.next_rest_request()
        if not path:
            self.hold_reasons[key]="CS00_RECOVERY_NOT_ELIGIBLE_FOR_REST"
            return self.status(key)
        try:
            raw=self.client.get_page(path,now_ms=now_ms)
            state=recovery.ingest_page(raw,received_at_ms=now_ms)
            self.pages[key]+=1
            self.attempts[key]=0
            self.next_at[key]=now_ms+1000
            if state=="RECOVERY_HOLD":
                self.hold_reasons[key]="CS00_RECOVERY_DATA_UNVERIFIABLE"
        except (RecoveryTransportHold,SourceRecoveryHold) as ex:
            self.attempts[key]+=1
            if self.attempts[key]>=MAX_RETRIES:
                self.hold_reasons[key]="CS00_RECOVERY_RETRIES_EXHAUSTED_REVIEW_NOT_AUTOCENSOR"
            else:
                self.next_at[key]=now_ms+min(60000,1000*(2**self.attempts[key]))
        return self.status(key)

    def status(self,key:str)->RecoveryTaskState:
        if key not in self.tasks:
            raise RecoveryTransportHold("CS00_RECOVERY_UNKNOWN_TASK")
        rec=self.tasks[key]
        state=rec.state
        if key in self.hold_reasons:
            state="RECOVERY_HOLD"
        return RecoveryTaskState(rec.symbol,state,self.next_at[key],
                                 self.pages[key],self.attempts[key],
                                 self.hold_reasons.get(key))
