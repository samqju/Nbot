"""G4 immutable 100->20 *source-warmup-only* deep cohort decision.

No pattern counts, future outcomes or matched-looking setups used to select.
Selection is a deterministic public-as-of, stratified audit/sampling policy;
K/N is the prospective inclusion probability within each declared priority
stratum across hash seeds. It is NOT a probability of profitable trades.
Every new name is WARMUP_HOLD until independent G4 source custody qualifies.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json

from .universe import UniverseManifest
from .exploration import ExplorationBatch

SCHEMA="NBOT_V5_1_G4_DEEP_COHORT_V1"
BTC="BTCUSDT"
MAX_DEEP=20
MAX_BROAD=100


class DeepSelectionHold(ValueError):
    pass


def _digest(body):
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),
              ensure_ascii=True,allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class DeepCandidate:
    symbol: str
    groups: tuple[str,...]
    state: str
    stratum: str
    inclusion_probability: str
    decision_reason: str
    source_grade: str = "WARMUP_HOLD_NOT_ORIGINAL_VERIFIED"


@dataclass(frozen=True)
class DeepManifest:
    schema: str
    event_open_ms: int
    decided_at_ms: int
    broad_manifest_sha: str
    exploration_batch_sha: str
    algorithm: str
    entries: tuple[DeepCandidate,...]
    excluded: tuple[DeepCandidate,...]
    manifest_sha: str
    no_trade: bool = True

    @property
    def symbols(self):
        return tuple(e.symbol for e in self.entries)


def choose_deep(
    universe: UniverseManifest, exploration: ExplorationBatch,
    *, count: int = 20,
    seed: str = "NBOT_V5_1_G4_STRATIFIED_ROTATION_V1",
) -> DeepManifest:
    if type(universe) is not UniverseManifest or type(exploration) is not ExplorationBatch:
        raise DeepSelectionHold("G4_INPUT_TYPE")
    if type(count) is not int or not 1<=count<=MAX_DEEP:
        raise DeepSelectionHold("G4_COUNT")
    if type(seed) is not str or len(seed)<8 or len(seed)>90:
        raise DeepSelectionHold("G4_SEED")
    if (len(universe.entries)>MAX_BROAD or len(universe.entries)<count
        or len(set(universe.symbols))!=len(universe.entries) or BTC not in universe.symbols):
        raise DeepSelectionHold("G4_BROAD_DENOMINATOR")
    if (exploration.universe_sha!=universe.selection_digest or
        len(exploration.rows)!=2*len(universe.entries) or
        exploration.event_open_ms+300_000>exploration.decision_at_ms or
        exploration.decision_at_ms<universe.selected_at_ms or
        exploration.decision_at_ms-universe.selected_at_ms>90*60_000):
        raise DeepSelectionHold("G4_ASOF_OR_COHORT_MISMATCH")
    pairs={(r.symbol,r.side) for r in exploration.rows}
    if len(pairs)!=2*len(universe.entries) or any(
      (e.symbol,side) not in pairs for e in universe.entries for side in ("LONG","SHORT")):
        raise DeepSelectionHold("G4_DIRECTION_MISSING")
    for r in exploration.rows:
        if r.authority.value!="NONE" or r.disposition.value!="NO_TRADE":
            raise DeepSelectionHold("G4_UNAUTHORIZED_G3")
    # Only the actual G2 source-qualified frozen universe is eligible.
    # G3 pattern outcomes and apparent performance must not influence choice.
    elig={e.symbol:e for e in universe.entries}
    classes={"GAINER":[],"LOSER":[],"TURNOVER":[],"CONTROL":[]}
    for e in universe.entries:
        if e.symbol==BTC:
            continue
        groups=set(e.groups)
        primary=("GAINER" if "GAINER" in groups else
                 "LOSER" if "LOSER" in groups else
                 "TURNOVER" if "TURNOVER" in groups else "CONTROL")
        classes[primary].append(e.symbol)
    # Precommitted diversity quotas; use 100% eligible breadth as controls.
    # If one bucket underflows, redistribute without falsely granting certainty.
    quotas={"GAINER":min(4,count-1),"LOSER":min(4,count-1),
            "TURNOVER":min(7,count-1),"CONTROL":0}
    left=count-1
    allocations={k:0 for k in classes}
    for name in ("GAINER","LOSER","TURNOVER"):
        n=min(left,quotas[name],len(classes[name]))
        allocations[name]=n; left-=n
    # Additional slots are allocated proportionally to remaining eligible
    # counts via deterministic largest remainder, not matches/profits.
    while left:
        available=[k for k in classes if allocations[k]<len(classes[k])]
        if not available:
            raise DeepSelectionHold("G4_INSUFFICIENT_CANDIDATES")
        # Each remaining eligible population has a fair claim.
        name=max(available,key=lambda k:(len(classes[k])-allocations[k],
                 k=="CONTROL",k))
        allocations[name]+=1;left-=1
    selected={BTC}
    strata={BTC:("BTC_MANDATORY",Decimal(1))}
    for k in sorted(classes):
        pool=classes[k]
        n=allocations[k]
        chosen=sorted(pool,key=lambda s:(_digest({"seed":seed,"event":exploration.event_open_ms,
                    "stratum":k,"symbol":s}),s))[:n]
        selected.update(chosen)
        p=Decimal(n)/Decimal(len(pool)) if pool else Decimal(0)
        for s in pool:
            strata[s]=(k,p)
    if len(selected)!=count:
        raise DeepSelectionHold("G4_COHORT_SIZE_INVALID")
    included=[];excluded=[]
    for symbol in universe.symbols:
        info=elig[symbol];group,p=strata[symbol]
        item=DeepCandidate(symbol,info.groups,
          "SELECTED_WARMUP_HOLD" if symbol in selected else "EXCLUDED_NO_WARMUP",
          group,format(p,"f"),
          "MANDATORY_BTC" if symbol==BTC else
          "HASH_ROTATED_STRATUM" if symbol in selected else
          "NOT_SAMPLED_THIS_COHORT")
        (included if symbol in selected else excluded).append(item)
    included.sort(key=lambda x:x.symbol);excluded.sort(key=lambda x:x.symbol)
    payload={"schema":SCHEMA,"event":exploration.event_open_ms,
             "decision":exploration.decision_at_ms,
             "universe":universe.selection_digest,"g3":exploration.batch_id,
             "policy":seed,
             "included":[x.__dict__ for x in included],
             "excluded":[x.__dict__ for x in excluded]}
    return DeepManifest(SCHEMA,exploration.event_open_ms,
         exploration.decision_at_ms,universe.selection_digest,
         exploration.batch_id,seed,tuple(included),tuple(excluded),_digest(payload))
