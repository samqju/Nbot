"""G7 Learning evidence boundary. Scientific promotion is NOT available in G7.

Synthetic G5/G6 model-only results can exercise algorithms in LAB mode but
NEVER count toward 2,000 original source-qualified matured outcomes. Source
authenticity needs an independent G4->G6 verifier; a caller's source_grade
string, receipt SHA or arbitrary 'verified=True' is not such a verifier.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import re
from .research_intent import number, ResearchHold

VERSION = "NBOT_V5_1_G7_LEARNING_INPUT_V1"
MAX_ROWS = 10000
PATTERN_VALUES = frozenset({"MATCH","NO_MATCH","UNAVAILABLE",
    "NOT_EVALUATED_SOURCE","NOT_EVALUATED_CAPACITY"})
STATES = frozenset({"COST_PENDING","SOURCE_HOLD","RESTART_HOLD",
    "CENSORED","INCOMPLETE","SYNTHETIC_MODELED","ORIGINAL_CLAIM_UNVERIFIED"})
SIDES = frozenset({"LONG","SHORT"})
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PATTERN = re.compile(r"[A-Z][A-Z0-9_]{3,55}_V1\Z")
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")
CONTEXTS = frozenset({"UP","DOWN","RANGE","TRANSITION","UNAVAILABLE"})
CHANNELS = frozenset({"VIRTUAL_SYNTHETIC","PAPER","REAL","VIRTUAL_ORIGINAL_CLAIM"})
REQUIRED_LINEAGE = frozenset({"g2","g3","g4","g5","g6","cost","path","policy"})
UNQUALIFIED_GRADE = "SYNTHETIC_OFFLINE_TEST_ONLY"


class LearningHold(ValueError):pass


def sha(value):
    return isinstance(value,str) and bool(_SHA.fullmatch(value))


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),
                      allow_nan=False,ensure_ascii=True).encode("ascii")


@dataclass(frozen=True)
class LearningRow:
    experiment_id:str
    event_ms:int
    feature_known_ms:int
    decision_ms:int
    activated_ms:int
    exit_ms:int
    matured_ms:int
    symbol:str
    side:str
    btc_regime:str
    market_regime:str
    coin_regime:str
    structure:str
    detector_states:tuple[tuple[str,str],...]
    inclusion_k:int
    inclusion_n:int
    channel:str
    source_grade:str
    economic_state:str
    net_r:str|None
    provenance:tuple[tuple[str,str],...]
    row_sha256:str


def _body(row):
    return {k:getattr(row,k) for k in LearningRow.__dataclass_fields__
            if k!="row_sha256"}


def lab_row(*,experiment_id:str,event_ms:int,feature_known_ms:int,
     decision_ms:int,activated_ms:int,exit_ms:int,matured_ms:int,
     symbol:str,side:str,btc_regime:str,market_regime:str,coin_regime:str,
     structure:str,detector_states:tuple[tuple[str,str],...],
     inclusion_k:int,inclusion_n:int,economic_state:str,net_r:str|None,
     provenance:tuple[tuple[str,str],...],
     channel:str="VIRTUAL_SYNTHETIC",source_grade:str=UNQUALIFIED_GRADE
)->LearningRow:
    body=dict(experiment_id=experiment_id,event_ms=event_ms,
        feature_known_ms=feature_known_ms,decision_ms=decision_ms,
        activated_ms=activated_ms,exit_ms=exit_ms,matured_ms=matured_ms,
        symbol=symbol,side=side,btc_regime=btc_regime,
        market_regime=market_regime,coin_regime=coin_regime,structure=structure,
        detector_states=detector_states,inclusion_k=inclusion_k,
        inclusion_n=inclusion_n,channel=channel,source_grade=source_grade,
        economic_state=economic_state,net_r=net_r,provenance=provenance)
    return LearningRow(**body,row_sha256=sha256(canonical(body)).hexdigest())


@dataclass(frozen=True)
class LearningDataset:
    version:str
    cutoff_ms:int
    rows:tuple[LearningRow,...]
    dataset_sha256:str
    qualified_original:int=0
    grade:str="OFFLINE_LAB_NONSCIENTIFIC"
    order_authority:str="NONE"

    @property
    def economic_lab_rows(self):
        return tuple(r for r in self.rows if r.economic_state=="SYNTHETIC_MODELED")


def assemble_lab(rows:tuple[LearningRow,...],*,cutoff_ms:int)->LearningDataset:
    if (type(rows) is not tuple or len(rows)>MAX_ROWS or
          type(cutoff_ms) is not int or cutoff_ms<=0):
        raise LearningHold("G7_DATASET_BOUNDS_OR_TIME")
    ids=set();items=[]
    for row in rows:
        if type(row) is not LearningRow:
            raise LearningHold("G7_ROW_TYPE")
        if not sha(row.experiment_id) or row.experiment_id in ids:
            raise LearningHold("G7_DUPLICATE_OR_MALFORMED_EXPERIMENT_ID")
        ids.add(row.experiment_id)
        if not sha(row.row_sha256) or sha256(canonical(_body(row))).hexdigest()!=row.row_sha256:
            raise LearningHold("G7_ROW_DIGEST_MISMATCH")
        clocks=(row.event_ms,row.feature_known_ms,row.decision_ms,
                row.activated_ms,row.exit_ms,row.matured_ms)
        if (any(type(x) is not int or x<0 for x in clocks) or
            not clocks[0]<=clocks[1]<=clocks[2]<clocks[3]<=clocks[4]<=clocks[5]<=cutoff_ms):
            raise LearningHold("G7_FUTURE_FEATURE_OR_UNMATURED")
        if (type(row.symbol) is not str or not _SYMBOL.fullmatch(row.symbol)
                or not row.symbol.endswith("USDT") or row.side not in SIDES
                or any(type(v) is not str or v not in CONTEXTS
                    for v in (row.btc_regime,row.market_regime,row.coin_regime))
                or type(row.structure) is not str or not 1<=len(row.structure)<=48):
            raise LearningHold("G7_CONTEXT_OR_COIN_INVALID")
        if (type(row.detector_states) is not tuple or
            len(row.detector_states)>24 or
            tuple(sorted(row.detector_states))!=row.detector_states or
            len({x[0] for x in row.detector_states})!=len(row.detector_states) or
            any(type(x) is not tuple or len(x)!=2 or
                 not isinstance(x[0],str) or not _PATTERN.fullmatch(x[0]) or
                 x[1] not in PATTERN_VALUES for x in row.detector_states)):
            raise LearningHold("G7_PATTERN_VERSION_OR_DUPLICATE")
        if (type(row.inclusion_k) is not int or
            type(row.inclusion_n) is not int or
            not 0<=row.inclusion_k<=row.inclusion_n<=200 or
            row.channel not in CHANNELS or
            row.economic_state not in STATES):
            raise LearningHold("G7_SAMPLING_OR_STATUS_INVALID")
        if (type(row.provenance) is not tuple or
            len(row.provenance)!=len(REQUIRED_LINEAGE) or
            {k for k,_ in row.provenance}!=REQUIRED_LINEAGE or
            tuple(sorted(row.provenance))!=row.provenance or
            any(not sha(v) for _,v in row.provenance)):
            raise LearningHold("G7_INDEPENDENT_LINEAGE_MISSING")
        if row.source_grade!=UNQUALIFIED_GRADE or row.channel!="VIRTUAL_SYNTHETIC":
            raise LearningHold("G7_ORIGINAL_PAPER_REAL_ADMISSION_LOCKED")
        if row.economic_state=="SYNTHETIC_MODELED":
            if row.net_r is None or row.inclusion_k<=0:
                raise LearningHold("G7_SYNTHETIC_COST_OR_SELECTION_UNKNOWN")
            try: net=number(row.net_r,strictly_positive=False)
            except ResearchHold as ex:raise LearningHold("G7_ECONOMIC_VALUE_INVALID") from ex
            if abs(net)>Decimal("100"):
                raise LearningHold("G7_ECONOMIC_R_OUTSIDE_BOUNDS")
        elif row.net_r is not None:
            raise LearningHold("G7_PENDING_OUTCOME_MUST_NOT_HAVE_RETURN")
        items.append(row)
    items.sort(key=lambda r:(r.decision_ms,r.experiment_id))
    body=[{"digest":r.row_sha256,"experiment":r.experiment_id} for r in items]
    return LearningDataset(VERSION,cutoff_ms,tuple(items),
        sha256(canonical({"version":VERSION,"cutoff":cutoff_ms,"rows":body})).hexdigest())


def scientific_export(dataset:LearningDataset)->None:
    if type(dataset) is not LearningDataset or dataset.grade!="OFFLINE_LAB_NONSCIENTIFIC":
        raise LearningHold("G7_UNTRUSTED_DATASET")
    raise LearningHold("G7_INDEPENDENT_ORIGINAL_SOURCE_AND_G6_COST_GATE_NOT_PASSED")


def verified_learning_count(dataset:LearningDataset)->int:
    if type(dataset) is not LearningDataset:
        raise LearningHold("G7_DATASET_TYPE")
    if dataset.grade!="OFFLINE_LAB_NONSCIENTIFIC" or dataset.qualified_original!=0:
        raise LearningHold("G7_FORGED_SCIENTIFIC_DATASET")
    return 0
