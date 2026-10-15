"""G7 pure scientifically cautious offline Learning ANALYSIS, never promotion.

Lab statistics may use *synthetic* modeled net-R to exercise algorithms;
the release gate is always NO_MODEL/NO_TRADE until independent G4-G6 source
qualification exists. A positive lab lower confidence bound is not edge.
No future features, no fake 2000 independent count, no multiple-detector
double counting, no paper/real pooled labels and no G8 training on lab rows.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import math
import random
import statistics
from .learning_contract import (
    LearningDataset,LearningRow,LearningHold,verified_learning_count)

VERSION="NBOT_V5_1_G7_SCIENCE_V1"
CHECKPOINT=2000
MAX_BOOTSTRAP=300
MAX_WINDOW_MS=24*3600*1000
DEFAULT_EMBARGO_MS=4*3600*1000


@dataclass(frozen=True)
class QualityReport:
    total:int
    pending:int
    held:int
    censored:int
    synthetic_modeled:int
    scientifically_qualified:int
    effective_independent_blocks:int
    symbols:int
    regimes:int
    long_rows:int
    short_rows:int
    timespan_ms:int
    unique_market_events:int
    sample_goal:int=CHECKPOINT
    ready_for_original_science:bool=False


@dataclass(frozen=True)
class LabFinding:
    context:str
    rows:int
    effective_blocks:int
    weighted_model_mean_r:str|None
    block_bootstrap_lower_bound_r:str|None
    no_trade_benchmark_r:str="0"
    status:str="LAB_ONLY_NOT_QUALIFIED"


@dataclass(frozen=True)
class LearningReview:
    version:str
    dataset_sha256:str
    cutoff_ms:int
    quality:QualityReport
    findings:tuple[LabFinding,...]
    train_blocks:int
    holdout_blocks:int
    purged_blocks:int
    model_status:str="NO_MODEL"
    recommendation:str="NO_TRADE"
    financial_authority:str="NONE"
    scientific_advantage_proved:bool=False
    reason:str="G7_G4_G6_ORIGINAL_MATURED_SOURCE_REQUIRED"


def dependence_blocks(rows:tuple[LearningRow,...],*,shock_window_ms:int=300000):
    """Connected interval union: every overlapping BTC market window shares risk.

    This deliberately merges opposites, coin tags and simultaneous events
    rather than treating thousands of correlated hypotheses independently.
    """
    if type(rows) is not tuple or type(shock_window_ms) is not int or shock_window_ms<0:
        raise LearningHold("G7_DEPENDENCY_ARGS")
    blocks=[];end=-1
    for row in sorted(rows,key=lambda r:(r.decision_ms,r.experiment_id)):
        if type(row) is not LearningRow:
            raise LearningHold("G7_UNVERIFIED_BLOCK_ROW")
        # A dependence window connects all decisions on a shared BTC clock.
        window_end=max(row.exit_ms,row.event_ms+shock_window_ms)
        if row.decision_ms>end:
            blocks.append([])
        blocks[-1].append(row)
        end=max(end,window_end)
    return tuple(tuple(x) for x in blocks)


def purged_chronological_split(rows:tuple[LearningRow,...],*,
    cutoff_ms:int,embargo_ms:int=DEFAULT_EMBARGO_MS):
    """Only matured pre-cutoff rows can train; overlapping/horizon boundary purged.

    Lab split merely audits chronology; it NEVER trains an authorized model.
    """
    if (type(cutoff_ms) is not int or cutoff_ms<0 or
        type(embargo_ms) is not int or not 0<=embargo_ms<=48*3600*1000):
        raise LearningHold("G7_CUTOFF_OR_EMBARGO")
    train=[];test=[];purged=[]
    for b in dependence_blocks(rows):
        earliest=min(x.decision_ms for x in b)
        latest=max(x.matured_ms for x in b)
        if latest<=cutoff_ms-embargo_ms:
            train.append(b)
        elif earliest>cutoff_ms+embargo_ms:
            test.append(b)
        else:
            purged.append(b)
    if any(max(x.matured_ms for x in block)>cutoff_ms-embargo_ms for block in train):
        raise LearningHold("G7_LEAKAGE_TRAIN_END")
    if any(min(x.decision_ms for x in block)<=cutoff_ms+embargo_ms for block in test):
        raise LearningHold("G7_LEAKAGE_HOLDOUT_START")
    return tuple(train),tuple(test),tuple(purged)


def quality_report(dataset:LearningDataset)->QualityReport:
    if verified_learning_count(dataset)!=0:
        raise LearningHold("G7_TRUE_QUALIFIED_ROWS_NOT_PERMITTED")
    rows=dataset.rows
    states={}
    for x in rows:states[x.economic_state]=states.get(x.economic_state,0)+1
    complete=tuple(r for r in rows if r.economic_state=="SYNTHETIC_MODELED")
    blocks=dependence_blocks(complete)
    periods=sorted(r.decision_ms for r in rows)
    return QualityReport(total=len(rows),
        pending=states.get("COST_PENDING",0)+states.get("INCOMPLETE",0),
        held=states.get("SOURCE_HOLD",0)+states.get("RESTART_HOLD",0)+
             states.get("ORIGINAL_CLAIM_UNVERIFIED",0),
        censored=states.get("CENSORED",0),
        synthetic_modeled=len(complete),scientifically_qualified=0,
        effective_independent_blocks=len(blocks),
        symbols=len({r.symbol for r in rows}),
        regimes=len({(r.btc_regime,r.market_regime,r.coin_regime) for r in rows}),
        long_rows=sum(r.side=="LONG" for r in rows),
        short_rows=sum(r.side=="SHORT" for r in rows),
        timespan_ms=(periods[-1]-periods[0]) if periods else 0,
        unique_market_events=len({r.event_ms for r in rows}))


def _weighted_block_value(block,context):
    values=[]
    for r in block:
        if r.economic_state!="SYNTHETIC_MODELED":continue
        if context!="ALL" and context!=f"{r.btc_regime}|{r.market_regime}|{r.side}":
            continue
        if r.inclusion_k<=0:continue
        w=min(Decimal(10),Decimal(r.inclusion_n)/Decimal(r.inclusion_k))
        values.append((float(Decimal(r.net_r)),float(w)))
    den=sum(v[1] for v in values)
    return (sum(v[0]*v[1] for v in values)/den if den else None),len(values)


def _finding(rows,context,seed=519,bootstrap=200):
    if not (100<=bootstrap<=MAX_BOOTSTRAP):
        raise LearningHold("G7_BOOTSTRAP_RANGE")
    blocks=dependence_blocks(rows)
    samples=[]
    n=0
    for b in blocks:
        value,size=_weighted_block_value(b,context)
        n+=size
        if value is not None:samples.append(value)
    if not samples:
        return LabFinding(context,0,0,None,None)
    mean=statistics.fmean(samples)
    rng=random.Random(hashlib.sha256((str(seed)+context).encode()).digest())
    draws=[]
    for _ in range(bootstrap):
        draws.append(statistics.fmean(samples[rng.randrange(len(samples))]
                                    for _ in range(len(samples))))
    lower=sorted(draws)[max(0,int(bootstrap*.025)-1)]
    return LabFinding(context,n,len(samples),str(round(mean,9)),
                      str(round(lower,9)))


def evaluate_lab(dataset:LearningDataset,*,split_at_ms:int,
                 embargo_ms:int=DEFAULT_EMBARGO_MS,
                 bootstrap:int=200,max_contexts:int=24)->LearningReview:
    if type(dataset) is not LearningDataset or dataset.grade!="OFFLINE_LAB_NONSCIENTIFIC":
        raise LearningHold("G7_EVAL_REQUIRES_VALID_LAB_DATASET")
    if not 1<=max_contexts<=24:
        raise LearningHold("G7_CONTEXT_BOUNDS")
    q=quality_report(dataset)
    train,test,purged=purged_chronological_split(dataset.rows,
                 cutoff_ms=split_at_ms,embargo_ms=embargo_ms)
    complete=tuple(r for r in dataset.rows if r.economic_state=="SYNTHETIC_MODELED")
    contexts=sorted({f"{r.btc_regime}|{r.market_regime}|{r.side}" for r in complete})
    findings=(_finding(complete,"ALL",bootstrap=bootstrap),)+tuple(
              _finding(complete,x,bootstrap=bootstrap) for x in contexts[:max_contexts])
    # The only valid scientific result is NO_MODEL, even if a lab
    # bootstrap discovers a startlingly positive artificial synthetic edge.
    return LearningReview(VERSION,dataset.dataset_sha256,dataset.cutoff_ms,q,
              findings,len(train),len(test),len(purged))


def assert_paper_or_real_model_authority(review:LearningReview):
    if type(review) is not LearningReview:
        raise LearningHold("G7_RELEASE_REVIEW_TYPE")
    raise LearningHold("G7_NO_SCIENTIFIC_MODEL_OR_PAPER_REAL_RELEASE")
