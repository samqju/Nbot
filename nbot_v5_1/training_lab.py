"""G8 bounded deterministic frozen LAB training; never a deployable Champion.

G7 permits zero independently original-qualified outcomes. This module can
stress-test simple conditional after-cost R estimators only using synthetic
evidence. A generated "model" is LAB-ONLY, can never submit an order, cannot
unlock paper, and cannot become a scientific G8 Champion without a new
independently audited real-evidence release design.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from decimal import Decimal
from hashlib import sha256
import math
import statistics

from .learning_contract import (
    LearningDataset,LearningRow,LearningHold,verified_learning_count,canonical)
from .learning_science import dependence_blocks

VERSION="NBOT_V5_1_G8_LAB_TRAINING_V1"
MAX_ROWS=10000
MAX_CONTEXTS=32
MAX_EXPERIMENTS=1
MAX_POLICY_EMBARGO=48*3600*1000


class TrainingHold(ValueError):pass


@dataclass(frozen=True)
class LabProtocol:
    declared_at_ms:int
    train_cutoff_ms:int
    holdout_start_ms:int
    holdout_end_ms:int
    embargo_ms:int=300000
    min_train_blocks:int=8
    min_test_blocks:int=5
    min_context_blocks:int=5
    cost_buffer_r:str="0.10"
    context_family:str="BTC_MARKET_SIDE_V1"
    random_search_attempts:int=1

    def validate(self):
        vals=(self.declared_at_ms,self.train_cutoff_ms,
            self.holdout_start_ms,self.holdout_end_ms,self.embargo_ms,
            self.min_train_blocks,self.min_test_blocks,self.min_context_blocks,
            self.random_search_attempts)
        if (any(type(x) is not int for x in vals) or
                not 0<=self.declared_at_ms<self.train_cutoff_ms
                or not self.train_cutoff_ms+2*self.embargo_ms<self.holdout_start_ms
                or self.holdout_start_ms>=self.holdout_end_ms
                or not 300000<=self.embargo_ms<=MAX_POLICY_EMBARGO
                or not 5<=self.min_train_blocks<=500
                or not 3<=self.min_test_blocks<=200
                or not 3<=self.min_context_blocks<=100
                or self.context_family!="BTC_MARKET_SIDE_V1"
                or self.random_search_attempts!=MAX_EXPERIMENTS):
            raise TrainingHold("G8_PROTOCOL_UNFROZEN_OR_UNSAFE")
        try:
            buf=Decimal(self.cost_buffer_r)
        except (ValueError,TypeError):
            raise TrainingHold("G8_BUFFER_INVALID")
        if (type(self.cost_buffer_r) is not str or
                not buf.is_finite() or not Decimal("0.01")<=buf<=Decimal("3")):
            raise TrainingHold("G8_UNREALISTIC_OR_ZERO_ECONOMIC_BUFFER")

    def digest(self):
        self.validate()
        return sha256(canonical({"v":VERSION,"policy":asdict(self)})).hexdigest()


@dataclass(frozen=True)
class FrozenLabModel:
    schema:str
    policy:LabProtocol
    policy_sha256:str
    dataset_sha256:str
    train_experiment_sha256:str
    trained_at_ms:int
    train_blocks:int
    trained_rows:int
    estimates:tuple[tuple[str,str,str,int],...] # context, expected shrink R, conservative lower R, blocks
    model_sha256:str
    state:str="LAB_ONLY_NOT_SCIENTIFIC"
    economic_grade:str="SYNTHETIC_OFFLINE_TEST_ONLY"
    order_authority:str="NONE"
    champion_authority:str="NONE"
    qualified_original:int=0


@dataclass(frozen=True)
class LabForecast:
    disposition:str
    would_select_in_lab:bool
    expected_net_r:str|None
    lower_bound_r:str|None
    reason:str
    authority:str="NONE"


@dataclass(frozen=True)
class LabBacktest:
    model_sha256:str
    dataset_sha256:str
    protocol_sha256:str
    train_blocks:int
    test_blocks:int
    purged_blocks:int
    selected_events:int
    abstained_events:int
    unknown_context_events:int
    model_net_r:str
    no_trade_net_r:str
    max_drawdown_r:str
    worst_observed_r:str|None
    status:str="LAB_ONLY_HOLD"
    scientific_advantage_proved:bool=False
    qualified_original:int=0
    release_authority:str="NONE"


def _context(r):
    return f"{r.btc_regime}|{r.market_regime}|{r.side}"


def _model_body(m):
    data=asdict(m)
    data.pop("model_sha256")
    return data


def verify_model(m:FrozenLabModel,dataset:LearningDataset|None=None):
    if type(m) is not FrozenLabModel or m.schema!=VERSION:
        raise TrainingHold("G8_UNTRUSTED_MODEL_SHAPE")
    m.policy.validate()
    if (m.policy_sha256!=m.policy.digest() or
        m.model_sha256!=sha256(canonical(_model_body(m))).hexdigest() or
        m.state!="LAB_ONLY_NOT_SCIENTIFIC" or
        m.economic_grade!="SYNTHETIC_OFFLINE_TEST_ONLY" or
        m.order_authority!="NONE" or m.champion_authority!="NONE" or
        m.qualified_original!=0 or type(m.trained_rows) is not int or
        type(m.train_blocks) is not int or m.train_blocks<0 or
        m.trained_rows<0 or m.trained_rows>MAX_ROWS or
        len(m.estimates)>MAX_CONTEXTS):
        raise TrainingHold("G8_MODEL_TAMPER_OR_FALSE_AUTHORITY")
    if tuple(sorted(m.estimates))!=m.estimates:
        raise TrainingHold("G8_ESTIMATES_NOT_CANONICAL")
    for key,mean,lower,count in m.estimates:
        if (type(key) is not str or len(key)>60 or
            type(mean) is not str or type(lower) is not str or
            type(count) is not int or count<1):
            raise TrainingHold("G8_MODEL_WEIGHT_INVALID")
        try:
            if not all(Decimal(x).is_finite() for x in (mean,lower)):
                raise ValueError("nonfinite")
        except (ValueError,TypeError) as e:
            raise TrainingHold("G8_MODEL_WEIGHT_NONFINITE") from e
    if dataset is not None:
        if (verified_learning_count(dataset)!=0 or
            dataset.dataset_sha256!=m.dataset_sha256):
            raise TrainingHold("G8_WRONG_OR_UNQUALIFIED_DATASET")
    return True


def _split(dataset:LearningDataset,protocol:LabProtocol):
    verified_learning_count(dataset)
    protocol.validate()
    if (dataset.cutoff_ms<protocol.holdout_end_ms or
        len(dataset.rows)>MAX_ROWS or
        (dataset.rows and protocol.declared_at_ms>=min(
            r.decision_ms for r in dataset.rows))):
        raise TrainingHold("G8_PROTOCOL_PREDECLARATION_OR_SNAPSHOT")
    training=[];testing=[];purged=[]
    for block in dependence_blocks(dataset.rows):
        first=min(x.decision_ms for x in block)
        last=max(x.matured_ms for x in block)
        if last<=protocol.train_cutoff_ms-protocol.embargo_ms:
            training.append(block)
        elif (first>=protocol.holdout_start_ms
              and last<=protocol.holdout_end_ms):
            testing.append(block)
        else:
            purged.append(block)
    if any(x.matured_ms>protocol.train_cutoff_ms-protocol.embargo_ms
            for b in training for x in b):
        raise TrainingHold("G8_TRAIN_FUTURE_OUTCOME_LEAK")
    if any(x.decision_ms<protocol.holdout_start_ms
            for b in testing for x in b):
        raise TrainingHold("G8_HOLDOUT_CUTOFF_LEAK")
    return tuple(training),tuple(testing),tuple(purged)


def _collapsed(block,*,context:str):
    vals=[Decimal(r.net_r) for r in block
          if r.economic_state=="SYNTHETIC_MODELED" and
          r.net_r is not None and _context(r)==context]
    return sum(vals)/len(vals) if vals else None


def train_lab(dataset:LearningDataset,protocol:LabProtocol)->FrozenLabModel:
    train,test,purged=_split(dataset,protocol)
    if len(train)<protocol.min_train_blocks:
        raise TrainingHold("G8_INSUFFICIENT_LAB_TRAIN_BLOCKS")
    if len(test)<protocol.min_test_blocks:
        raise TrainingHold("G8_INSUFFICIENT_UNTOUCHED_LAB_HOLDOUT")
    contexts=sorted({_context(r) for b in train for r in b
                     if r.economic_state=="SYNTHETIC_MODELED"})
    if len(contexts)>MAX_CONTEXTS:
        raise TrainingHold("G8_TOO_MANY_CONTEXTS")
    estimates=[]
    for context in contexts:
        values=[v for block in train
                if (v:=_collapsed(block,context=context)) is not None]
        n=len(values)
        if n<protocol.min_context_blocks:
            continue
        avg=sum(values)/n
        # Conservative downside: shrink against 0 and incorporate dispersion.
        shrunk=avg*(Decimal(n)/(Decimal(n)+Decimal(5)))
        if n>1:
            variance=sum((x-avg)**2 for x in values)/Decimal(n-1)
            conservative=shrunk-Decimal(2)*variance.sqrt()/Decimal(n).sqrt()
        else:
            conservative=shrunk-abs(shrunk)
        estimates.append((context,str(round(shrunk,9)),
                          str(round(conservative,9)),n))
    seen=sorted(r.row_sha256 for b in train for r in b)
    frozen=FrozenLabModel(
        VERSION,protocol,protocol.digest(),dataset.dataset_sha256,
        sha256(canonical(seen)).hexdigest(),protocol.train_cutoff_ms,
        len(train),len(seen),tuple(sorted(estimates)),"")
    frozen=FrozenLabModel(**{**asdict(frozen),
         "policy":protocol,
         "model_sha256":sha256(canonical(_model_body(frozen))).hexdigest()})
    verify_model(frozen,dataset)
    return frozen


def predict_lab(m:FrozenLabModel,r:LearningRow)->LabForecast:
    verify_model(m)
    if type(r) is not LearningRow:
        raise TrainingHold("G8_PREDICTION_ROW_TYPE")
    # Never inspect net_r, exit_ms or future funding for a prediction.
    if (r.feature_known_ms>r.decision_ms or
        r.decision_ms<m.policy.holdout_start_ms or
        r.decision_ms>m.policy.holdout_end_ms or
        any(v=="UNAVAILABLE" for v in (r.btc_regime,r.market_regime))):
        return LabForecast("NO_TRADE",False,None,None,"UNKNOWN_OR_OUTSIDE_DECISION_CONTEXT")
    match=next((v for v in m.estimates if v[0]==_context(r)),None)
    if match is None:
        return LabForecast("NO_TRADE",False,None,None,"UNSEEN_OR_UNQUALIFIED_CONTEXT")
    _,mean,lower,n=match
    permitted=Decimal(lower)>Decimal(m.policy.cost_buffer_r)
    return LabForecast("NO_TRADE",permitted,mean,lower,
                       "HYPOTHETICAL_CONDITIONAL_ONLY" if permitted else
                       "LOW_CONFIDENCE_OR_AFTER_COST_BUFFER")


def evaluate_frozen_lab(m:FrozenLabModel,
                        dataset:LearningDataset)->LabBacktest:
    verify_model(m,dataset)
    train,test,purged=_split(dataset,m.policy)
    if (len(train)!=m.train_blocks or len(test)<m.policy.min_test_blocks or
        sha256(canonical(sorted(r.row_sha256 for b in train
                               for r in b))).hexdigest()!=m.train_experiment_sha256):
        raise TrainingHold("G8_FROZEN_TRAIN_HEAD_CHANGED")
    by_event={}
    for b in test:
        for r in b:
            by_event.setdefault(r.event_ms,[]).append(r)
    selected=[]; abstain=unknown=0; held_until=-1
    for event in sorted(by_event):
        candidates=[]
        for r in by_event[event]:
            forecast=predict_lab(m,r)
            if (forecast.reason=="UNSEEN_OR_UNQUALIFIED_CONTEXT" or
                forecast.reason=="UNKNOWN_OR_OUTSIDE_DECISION_CONTEXT"):
                unknown+=1
            if forecast.would_select_in_lab and r.economic_state=="SYNTHETIC_MODELED":
                candidates.append((Decimal(forecast.lower_bound_r),
                                   r.symbol,r.side,r.experiment_id,r))
        if not candidates or event<=held_until:
            abstain+=1
            continue
        # Selection is only model/frozen, NEVER an outcome-informed rank.
        pick=sorted(candidates,key=lambda x:(-x[0],x[1],x[2],x[3]))[0][4]
        held_until=pick.exit_ms
        selected.append(pick)
    equity=peak=drawdown=Decimal(0)
    for r in selected:
        equity+=Decimal(r.net_r)
        peak=max(peak,equity)
        drawdown=max(drawdown,peak-equity)
    worst=min((Decimal(r.net_r) for r in selected),default=None)
    return LabBacktest(m.model_sha256,dataset.dataset_sha256,m.policy_sha256,
        len(train),len(test),len(purged),len(selected),abstain,unknown,
        str(equity),"0",str(drawdown),str(worst) if worst is not None else None)


def require_authorized_champion(model:FrozenLabModel)->None:
    verify_model(model)
    raise TrainingHold("G8_G7_ORIGINAL_SCIENCE_AND_OWNER_PAPER_RELEASE_NOT_APPROVED")
