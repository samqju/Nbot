"""G5 read-only virtual research book with at most 40 active hypotheses.

Only explicit SYNTHETIC_OFFLINE_TEST_ONLY source, no private or paper/real
authority. A price-only synthetic first touch is PATH_ONLY/COST_PENDING,
not a qualified trade, fill, net return, or proof that G4 source is complete.

Changes to a trailing stop between durable checkpoints are deliberately NOT
regarded as restart-safe: any previously active path becomes RESTART_HOLD and
continues to occupy its slot after replay.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import threading
from typing import Callable

from .core import FiveMinuteEvent, INTERVAL_MS
from .deep_selection import DeepManifest
from .research_intent import FrozenIntent,ResearchHold,number,from_record,MAX_ACTIVE,SIDES
from .research_journal import ResearchJournal,JournalHold,ZERO

G5_SCHEMA="NBOT_V5_1_G5_VIRTUAL_BOOK_V1"
TERMINAL_REASONS=frozenset({"STOP","TARGET","TRAILING_STOP","HORIZON"})
ACTIVE_STATES=frozenset({"ACTIVE_SYNTHETIC_PATH","SOURCE_HOLD","RESTART_HOLD"})


@dataclass(frozen=True)
class SyntheticTick:
    symbol:str
    at_ms:int
    price:str
    source_epoch:int
    aggregate_id:int
    complete_since_ms:int
    source_grade:str="SYNTHETIC_OFFLINE_TEST_ONLY"
    financial_authority:str="NONE"


@dataclass
class _Path:
    intent:FrozenIntent
    stop:Decimal
    extreme:Decimal
    last_tick_at:int|None=None
    last_aggregate_id:int|None=None
    state:str="ACTIVE_SYNTHETIC_PATH"
    seen:int=0
    checkpoint_stop:str|None=None
    last_price:str|None=None


@dataclass(frozen=True)
class VirtualTerminal:
    intent_id:str
    symbol:str
    side:str
    reason:str
    at_ms:int
    reference_price:str
    path_grade:str="SYNTHETIC_PATH_ONLY_NOT_EXECUTABLE"
    economic_state:str="COST_PENDING_UNQUALIFIED"
    qualified_net_return:None=None
    financial_authority:str="NONE"


@dataclass(frozen=True)
class ReviewResult:
    event_open_ms:int
    capacity_before:int
    openings:int
    capacity_after:int
    skipped_capacity:int
    skipped_ineligible:int
    decision_denominator:int
    supplier_called:bool
    no_trading_authority:str="NONE"


class VirtualResearchBook:
    def __init__(self,journal:ResearchJournal):
        if not isinstance(journal,ResearchJournal):
            raise ResearchHold("G5_JOURNAL_REQUIRED")
        self.journal=journal
        self.lock=threading.RLock()
        self.active:dict[str,_Path]={}
        self.by_pair:dict[tuple[str,str],str]={}
        self.closed:dict[str,VirtualTerminal]={}
        self.seen_ids:set[str]=set()
        self.last_review_ms:int|None=None
        self.source_heads:dict[str,tuple[int,int,int]]={}
        self.head=ZERO
        self._recover()

    def _log(self,op,now,payload):
        self.head=self.journal.append(op,now,payload,expected_head=self.head)

    def _drop(self,id):
        p=self.active.pop(id)
        self.by_pair.pop((p.intent.symbol,p.intent.side))
        return p

    def _recover(self):
        rows,head=self.journal.replay()
        self.head=head
        for e in rows:
            op=e["action"]
            data=e["payload"]
            if op=="ADMIT":
                intent=from_record(data["intent"])
                if (intent.intent_id in self.seen_ids
                        or (intent.symbol,intent.side) in self.by_pair
                        or len(self.active)>=MAX_ACTIVE):
                    raise JournalHold("G5_REPLAY_DUPLICATE_OR_OVERCAP")
                p=_Path(intent,number(intent.stop),number(intent.entry_reference))
                self.active[intent.intent_id]=p
                self.by_pair[(intent.symbol,intent.side)]=intent.intent_id
                self.seen_ids.add(intent.intent_id)
            elif op=="TRAIL_CHECKPOINT":
                id=data.get("intent_id")
                if id not in self.active or self.active[id].state!="ACTIVE_SYNTHETIC_PATH":
                    raise JournalHold("G5_REPLAY_TRAIL_WITHOUT_ACTIVE")
                p=self.active[id]
                next_stop=number(data["stop"])
                old=p.stop
                if (p.intent.side=="LONG" and next_stop<old
                        or p.intent.side=="SHORT" and next_stop>old):
                    raise JournalHold("G5_REPLAY_TRAIL_REVERSED")
                p.stop=next_stop;p.checkpoint_stop=data["stop"]
            elif op=="PATH_HOLD":
                id=data.get("intent_id")
                if id not in self.active:
                    raise JournalHold("G5_REPLAY_HOLD_WITHOUT_ACTIVE")
                self.active[id].state=data.get("status","SOURCE_HOLD")
                if self.active[id].state not in ("SOURCE_HOLD","RESTART_HOLD"):
                    raise JournalHold("G5_REPLAY_INVALID_HOLD")
            elif op=="TERMINAL":
                id=data.get("intent_id")
                if id not in self.active:
                    raise JournalHold("G5_REPLAY_CLOSE_WITHOUT_ACTIVE")
                v=data.get("terminal")
                if type(v) is not dict or set(v)!=set(VirtualTerminal.__dataclass_fields__):
                    raise JournalHold("G5_REPLAY_TERMINAL_SCHEMA")
                t=VirtualTerminal(**v)
                if (t.intent_id!=id or t.reason not in TERMINAL_REASONS
                        or t.financial_authority!="NONE" or t.qualified_net_return is not None
                        or t.path_grade!="SYNTHETIC_PATH_ONLY_NOT_EXECUTABLE"
                        or t.economic_state!="COST_PENDING_UNQUALIFIED"):
                    raise JournalHold("G5_REPLAY_QUALIFIED_SCORE_FORBIDDEN")
                self.closed[id]=t
                self._drop(id)
            elif op=="REVIEW":
                open_ms=data.get("event_open_ms")
                if (type(open_ms) is not int or
                        self.last_review_ms is not None and open_ms<=self.last_review_ms):
                    raise JournalHold("G5_REPLAY_DUPLICATE_BOUNDARY")
                self.last_review_ms=open_ms
            elif op=="CENSOR":
                raise JournalHold("G5_UNSUPPORTED_RELEASE_OF_SOURCE_HOLD")
            else:
                raise JournalHold("G5_REPLAY_UNKNOWN_OP")
        # No restart can assert that unsynced RAM tail/trailing path was intact.
        self.source_heads={}
        for id,path in tuple(self.active.items()):
            if path.state=="ACTIVE_SYNTHETIC_PATH":
                self._log("PATH_HOLD",path.intent.declared_at_ms,
                          {"intent_id":id,"status":"RESTART_HOLD",
                           "reason":"IN_MEMORY_TAIL_NOT_RECOVERED"})
                path.state="RESTART_HOLD"

    @property
    def occupied(self)->int:
        return len(self.active)

    @property
    def vacancies(self)->int:
        return MAX_ACTIVE-len(self.active)

    def should_explore(self)->bool:
        return self.vacancies>0

    def review(self,event:FiveMinuteEvent,deep:DeepManifest,
               supplier:Callable[[],tuple[FrozenIntent,...]]|None=None)->ReviewResult:
        with self.lock:
            if type(event) is not FiveMinuteEvent or type(deep) is not DeepManifest:
                raise ResearchHold("G5_REVIEW_TYPE")
            if (len(deep.symbols)>20 or not deep.symbols or
                    "BTCUSDT" not in deep.symbols or not deep.no_trade
                    or deep.decided_at_ms>event.decision_at_ms
                    or deep.event_open_ms>event.event_open_ms):
                raise ResearchHold("G5_REVIEW_COHORT_OR_CLOCK")
            if self.last_review_ms is not None:
                if event.event_open_ms<self.last_review_ms:
                    raise ResearchHold("G5_BOUNDARY_TIME_REVERSED")
                if event.event_open_ms==self.last_review_ms:
                    return ReviewResult(event.event_open_ms,self.occupied,0,
                                        self.occupied,0,0,2*len(deep.symbols),False)
            before=self.occupied
            proposed=()
            supplier_called=False
            if self.vacancies and supplier is not None:
                supplier_called=True
                proposed=supplier()
                if type(proposed) is not tuple or len(proposed)>2*len(deep.symbols):
                    raise ResearchHold("G5_REVIEW_SUPPLIER_OUTPUT_INVALID")
            screened={}
            bad=0
            for intent in proposed:
                if type(intent) is not FrozenIntent:
                    raise ResearchHold("G5_INTENT_NOT_FROZEN")
                if from_record(intent.to_dict())!=intent:
                    raise ResearchHold("G5_INTENT_TAMPER")
                key=(intent.symbol,intent.side)
                if key in screened:
                    raise ResearchHold("G5_DUPLICATE_SYMBOL_SIDE_PROPOSAL")
                if (intent.symbol not in deep.symbols
                     or intent.cohort_sha!=deep.manifest_sha
                     or intent.event_open_ms!=event.event_open_ms
                     or intent.declared_at_ms>event.decision_at_ms
                     or intent.activates_at_ms<=event.decision_at_ms
                     ):
                    bad+=1;continue
                # The source-grade assertion is SYNTHETIC_ONLY in G5; the
                # G4 20 market WARMUP_HOLD must never become 'qualified' here.
                if (intent.source_grade!="SYNTHETIC_OFFLINE_TEST_ONLY"
                        or not intent.research_only or intent.financial_authority!="NONE"
                        or key in self.by_pair or intent.intent_id in self.seen_ids):
                    bad+=1;continue
                screened[key]=intent
            available=self.vacancies
            ordered=sorted(screened.values(),key=lambda x:(
                hashlib.sha256((str(event.event_open_ms)+x.intent_id).encode()).hexdigest(),
                x.intent_id))
            for intent in ordered[:available]:
                self._log("ADMIT",event.decision_at_ms,{"intent":intent.to_dict()})
                path=_Path(intent,number(intent.stop),number(intent.entry_reference))
                self.active[intent.intent_id]=path
                self.by_pair[(intent.symbol,intent.side)]=intent.intent_id
                self.seen_ids.add(intent.intent_id)
            opened=min(len(ordered),available)
            skipped_capacity=max(0,len(ordered)-available)
            self._log("REVIEW",event.decision_at_ms,{
                "event_open_ms":event.event_open_ms,
                "capacity_before":before,
                "opened":opened,
                "skipped_capacity":skipped_capacity,
                "skipped_ineligible":bad,
                "cohort":deep.manifest_sha,
                "synthetic_only":True})
            self.last_review_ms=event.event_open_ms
            return ReviewResult(event.event_open_ms,before,opened,self.occupied,
                   skipped_capacity,bad,2*len(deep.symbols),supplier_called)

    def _hold_symbol(self,sym,at,reason):
        for (name,side),id in tuple(self.by_pair.items()):
            if name!=sym:continue
            path=self.active[id]
            if path.state=="ACTIVE_SYNTHETIC_PATH":
                self._log("PATH_HOLD",at,{"intent_id":id,
                          "status":"SOURCE_HOLD","reason":reason})
                path.state="SOURCE_HOLD"
        self.source_heads.pop(sym,None)

    def ingest(self,tick:SyntheticTick):
        """Consume ONE shared synthetic original-shaped coin event, O(active pair).

        No per-frame SQLite writes; journal I/O only at terminal/HOLD boundary.
        Price events with a missing origin/gap never turn into favorable exit.
        """
        with self.lock:
            if (type(tick) is not SyntheticTick or type(tick.symbol) is not str
                    or type(tick.at_ms) is not int or tick.at_ms<=0
                    or type(tick.source_epoch) is not int or tick.source_epoch<=0
                    or type(tick.aggregate_id) is not int or tick.aggregate_id<0
                    or type(tick.complete_since_ms) is not int
                    or tick.source_grade!="SYNTHETIC_OFFLINE_TEST_ONLY"
                    or tick.financial_authority!="NONE"):
                raise ResearchHold("G5_UNQUALIFIED_OR_INVALID_TICK")
            price=number(tick.price)
            paths=[self.active[id] for (sym,_),id in self.by_pair.items()
                   if sym==tick.symbol and self.active[id].state=="ACTIVE_SYNTHETIC_PATH"]
            if not paths:
                return ()
            old=self.source_heads.get(tick.symbol)
            if (old is not None and (tick.source_epoch!=old[0]
                    or tick.aggregate_id!=old[1]+1 or tick.at_ms<old[2])
                    or any(tick.source_epoch!=p.intent.source_epoch
                           or tick.complete_since_ms>p.intent.activates_at_ms
                           or tick.at_ms<p.intent.activates_at_ms for p in paths)):
                self._hold_symbol(tick.symbol,tick.at_ms,"EPOCH_GAP_OR_UNKNOWN_ENTRY_PATH")
                return ()
            self.source_heads[tick.symbol]=(tick.source_epoch,tick.aggregate_id,tick.at_ms)
            events=[]
            for path in paths:
                if path.intent.intent_id not in self.active:continue
                plan=path.intent
                if path.last_tick_at is not None and tick.at_ms<path.last_tick_at:
                    self._hold_symbol(tick.symbol,tick.at_ms,"BACKWARD_TIME")
                    return tuple(events)
                reason=None
                if tick.at_ms>plan.expires_at_ms:
                    if path.last_tick_at is not None and path.last_tick_at<plan.expires_at_ms:
                        reason="HORIZON"
                        close_at=plan.expires_at_ms
                        close_price=path.last_price if path.last_price is not None else plan.entry_reference
                    else:
                        self._hold_symbol(tick.symbol,tick.at_ms,"NO_CONFIRMED_HORIZON_COVERAGE")
                        return tuple(events)
                else:
                    side=plan.side
                    stopped=(price<=path.stop) if side=="LONG" else (price>=path.stop)
                    target=(price>=number(plan.target)) if side=="LONG" else (price<=number(plan.target))
                    if stopped:reason="TRAILING_STOP" if (
                         (side=="LONG" and path.stop>number(plan.stop))
                         or (side=="SHORT" and path.stop<number(plan.stop))) else "STOP"
                    elif target:reason="TARGET"
                    close_at=tick.at_ms
                    close_price=tick.price
                if reason:
                    terminal=VirtualTerminal(plan.intent_id,plan.symbol,plan.side,
                             reason,close_at,close_price)
                    self._log("TERMINAL",tick.at_ms,{"intent_id":plan.intent_id,
                                    "terminal":terminal.__dict__.copy()})
                    self._drop(plan.intent_id)
                    self.closed[plan.intent_id]=terminal
                    events.append(terminal)
                    continue
                path.last_tick_at=tick.at_ms
                path.last_aggregate_id=tick.aggregate_id
                path.seen+=1
                path.last_price=tick.price
                if (plan.side=="LONG" and price>path.extreme
                        or plan.side=="SHORT" and price<path.extreme):
                    path.extreme=price
                risk=number(plan.risk_r)
                favorable=((path.extreme-number(plan.entry_reference))/risk
                       if plan.side=="LONG" else (number(plan.entry_reference)-path.extreme)/risk)
                if favorable>=number(plan.trail_activation_r):
                    proposed=(path.extreme-number(plan.trail_distance_r)*risk
                         if plan.side=="LONG" else
                         path.extreme+number(plan.trail_distance_r)*risk)
                    if plan.side=="LONG":
                        path.stop=max(path.stop,proposed)
                    else:
                        path.stop=min(path.stop,proposed)
                if tick.at_ms==plan.expires_at_ms:
                    terminal=VirtualTerminal(plan.intent_id,plan.symbol,plan.side,
                             "HORIZON",tick.at_ms,tick.price)
                    self._log("TERMINAL",tick.at_ms,{"intent_id":plan.intent_id,
                             "terminal":terminal.__dict__.copy()})
                    self._drop(plan.intent_id)
                    self.closed[plan.intent_id]=terminal;events.append(terminal)
            return tuple(events)

    def checkpoint(self,at_ms:int):
        with self.lock:
            if type(at_ms) is not int or at_ms<0:
                raise ResearchHold("G5_CHECKPOINT_CLOCK_INVALID")
            n=0
            for id,path in tuple(self.active.items()):
                if path.state!="ACTIVE_SYNTHETIC_PATH":
                    continue
                price=str(path.stop)
                if price!=path.checkpoint_stop:
                    self._log("TRAIL_CHECKPOINT",at_ms,
                              {"intent_id":id,"stop":price})
                    path.checkpoint_stop=price
                    n+=1
            return n

    def invalidate(self,symbol:str,*,at_ms:int,reason:str="DISCONNECTED"):
        with self.lock:
            if type(at_ms) is not int or at_ms<0 or type(reason) is not str:
                raise ResearchHold("G5_SOURCE_HOLD_ARGS")
            self._hold_symbol(symbol,at_ms,reason)

    def status(self)->dict:
        return {"schema":G5_SCHEMA,"active":self.occupied,
                "vacancies":self.vacancies,
                "held":sum(x.state!="ACTIVE_SYNTHETIC_PATH" for x in self.active.values()),
                "cost_pending":len(self.closed),
                "qualified_after_cost":0,
                "financial_authority":"NONE",
                "source_grade":"SYNTHETIC_OFFLINE_TEST_ONLY",
                "last_review_ms":self.last_review_ms}
