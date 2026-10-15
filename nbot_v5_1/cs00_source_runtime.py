"""NBOT V5.1 CS-00 frozen *public only* Observation collector boundary.

The program is intentionally a non-starting preflight transport coordinator:
WSS, REST, supervisor installation and network are separate explicit future
CS-01 operations. No constructor imports order clients or contacts any host.
Injection of verified raw public WSS frames is only an OFFLINE rehearsal.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from hashlib import sha256
import json
import re
from .deep_source import stream_urls, verify_frame, DeepSourceHold
from .cs00_history_recovery import HistoricalAggTradeRecovery,SourceRecoveryHold
from .research_intent import number
from .core import INTERVAL_MS

VERSION="NBOT_V5_1_CS00_COLLECTOR_CONTRACT_V1"
_SYMBOL=re.compile(r"[A-Z0-9]{3,24}\Z")
LIMIT_STREAMS=20

class CollectorHold(ValueError):pass

@dataclass(frozen=True)
class RoutePlan:
    kind:str
    uri:str
    deep_symbols:tuple[str,...]
    financial_authority:str="NONE"
    enabled:bool=False

@dataclass(frozen=True)
class SourceStatus:
    symbol:str
    kind:str
    epoch:int
    aggregate_id:int|None
    received_ms:int
    state:str
    reason:str|None
    raw_sha256:str|None
    source_qualified:bool=False
    financial_authority:str="NONE"

def public_routes(symbols:tuple[str,...])->tuple[RoutePlan,...]:
    if (type(symbols) is not tuple or len(symbols)!=20
            or len(set(symbols))!=20 or "BTCUSDT" not in symbols):
        raise CollectorHold("CS00_EXACT_20_AND_BTC_REQUIRED")
    urls=stream_urls(symbols)
    for kind,url in urls.items():
        if (not url.startswith("wss://fstream.binance.com/")
                or "/private" in url or "/user" in url
                or "/api" in url or not url.endswith(
                    tuple(f"{x.lower()}@"+suffix for x in symbols
                          for suffix in ("aggTrade","bookTicker","markPrice@1s")))):
            raise CollectorHold("CS00_PUBLIC_WSS_ROUTE_ONLY")
    return tuple(RoutePlan(kind,urls[kind],symbols) for kind in ("TRADE","QUOTE","MARK"))

class SourceOnlyIntake:
    """OFFLINE injected raw frames. Holds an epoch on any unexpected gap.

    Not a live WebSocket client, not a durable archive, not source scientific
    qualification. A future runner must durably append each raw byte receipt
    and heartbeat before advancing this cursor. The separate G4 recorder
    maintains the immutable data custody; this is an additional source monitor.
    """
    def __init__(self,symbols:tuple[str,...]):
        self.routes=public_routes(symbols)
        self.symbols=symbols
        self.cursor:dict[tuple[str,str],SourceStatus]={}
        self.quarantine:set[tuple[str,str]]=set()
        self.transitions=deque(maxlen=256)  # bounded telemetry, not a second tick vault
        self._epochs:dict[str,int]={}
        self.processed=0
        self.authority="NONE"

    def observe(self,*,kind:str,raw:bytes,epoch:int,received_ms:int)->SourceStatus:
        if (kind not in ("TRADE","QUOTE","MARK") or type(epoch) is not int
                or epoch<1 or type(received_ms) is not int or received_ms<=0
                or type(raw) is not bytes or not 0<len(raw)<=65536):
            raise CollectorHold("CS00_INTAKE_ARGUMENT_INVALID")
        if epoch < self._epochs.get(kind,0):
            raise CollectorHold("CS00_OLD_SOURCE_EPOCH")
        if epoch>self._epochs.get(kind,0):
            # A reconnect does not certify lost tail continuity.
            self._epochs[kind]=epoch
            if epoch>1:
                for symbol in self.symbols:
                    self.quarantine.add((kind,symbol))
        prior=None
        symbol=None
        try:
            # Envelope routes must be validated, then validated again against
            # the actual per-symbol cursor.
            def strict_pairs(pairs):
                d={}
                for k,v in pairs:
                    if k in d:raise CollectorHold("CS00_INTAKE_DUPLICATE_JSON_FIELD")
                    d[k]=v
                return d
            body=json.loads(raw,object_pairs_hook=strict_pairs)
            if type(body) is not dict or type(body.get("data")) is not dict:
                raise CollectorHold("CS00_INTAKE_BAD_ENVELOPE")
            symbol=body["data"].get("s")
            if symbol not in self.symbols:
                raise CollectorHold("CS00_INTAKE_OUTSIDE_COHORT")
            prior=self.cursor.get((kind,symbol))
            frame=verify_frame(kind=kind,raw=raw,received_at_ms=received_ms,
                source_epoch=epoch,selected_symbols=self.symbols,
                prior_agg_id=prior.aggregate_id if prior and kind=="TRADE" else None)
            if frame.state!="RECEIVED_UNQUALIFIED_LOCAL_WSS":
                self.quarantine.add((kind,symbol))
            if prior is not None and (epoch!=prior.epoch or received_ms<prior.received_ms):
                self.quarantine.add((kind,symbol))
            if kind=="TRADE" and prior and frame.agg_id is not None:
                if prior.aggregate_id is None or frame.agg_id != prior.aggregate_id+1:
                    self.quarantine.add((kind,symbol))
            state="SOURCE_HOLD" if (kind,symbol) in self.quarantine else "LOCAL_FRAME_NOT_INDEPENDENTLY_QUALIFIED"
            reason=((frame.reason or "AGG_ID_OR_EPOCH_CONTINUITY_HOLD") if state=="SOURCE_HOLD" else None)
            status=SourceStatus(symbol,kind,epoch,frame.agg_id,received_ms,
                state,reason,sha256(raw).hexdigest())
        except (DeepSourceHold,KeyError,ValueError,TypeError) as exc:
            if symbol in self.symbols:
                self.quarantine.add((kind,symbol))
            raise CollectorHold("CS00_INTAKE_INVALID_OR_HOLD") from exc
        self.cursor[(kind,symbol)]=status
        self.transitions.append(status)
        self.processed+=1
        return status

    def mark_disconnect(self,*,kind:str,at_ms:int):
        if kind not in ("TRADE","QUOTE","MARK") or type(at_ms) is not int or at_ms<=0:
            raise CollectorHold("CS00_DISCONNECT_ARGUMENT")
        self._epochs[kind]=self._epochs.get(kind,0)+1
        for symbol in self.symbols:
            self.quarantine.add((kind,symbol))
        return {"kind":kind,"epoch":self._epochs[kind],
                "source_state":"DISCONNECTED_RESTART_HOLD",
                "financial_authority":"NONE"}

    def status(self)->dict:
        return {"schema":VERSION,"frames_processed":self.processed,
                "quarantined_pairs":len(self.quarantine),
                "source_qualified":0,"actual_order_capability":False,
                "service_started":False,"financial_authority":"NONE",
                "last_receipts":len(self.cursor)}
