"""Replaceable, source-aware offline V7 brain. LightGBM LambdaRank is the
groupwise selection model; net-return head is separately calibrated conceptually.
This is an engineering baseline, not a certified edge or a trading signal API.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from math import ceil
import json
import math

from .features import FAMILIES, btc_regime

BASE_KEYS = ("r3","r12","r48","atr","volume_ratio","range_12","body",
             "btc_r3","btc_r12","btc_r48","btc_atr","vs_btc","utc_hour")
MODEL_SCHEMA = "NBOT_V7_BRAIN_V2_CAUSAL_CANDIDATES_CONTEXTUAL_5M_PROXY"

def vector(row, kind: str) -> list[float]:
    features = json.loads(row["features"])
    if not all(k in features and isinstance(features[k],(float,int))
               and math.isfinite(features[k]) for k in BASE_KEYS):
        raise ValueError("MISSING_OR_INVALID_PAST_ONLY_FEATURE")
    v=[float(features[k]) for k in BASE_KEYS]
    if kind == "opportunity":
        v.append(1.0 if row["side"] == "SHORT" else 0.0)
        v += [1.0 if row["family"] == fam else 0.0 for fam in FAMILIES]
    elif kind != "watch":
        raise ValueError("UNKNOWN_BRAIN_TASK")
    return v

def relevance(net:float)->int:
    return 4 if net >=.02 else 3 if net >=.005 else 2 if net > 0 else 1 if net > -.005 else 0

def rows_before(conn, kind:str, cutoff_ms:int, *, max_groups:int=4000, max_rows:int=175000):
    if kind not in ("watch","opportunity"):
        raise ValueError("UNKNOWN_BRAIN_TASK")
    col="review_ms" if kind=="watch" else "decision_ms"
    table=kind
    # Both deterministic stop-first and ordinary proxy labels are admitted.
    # Excluding ambiguity would condition the learning cohort on future paths.
    admissible = ""
    times=[int(t[0]) for t in conn.execute(
        f"SELECT DISTINCT {col} FROM {table} WHERE {col}<? AND label_available_ms<?{admissible} ORDER BY {col}",
        (cutoff_ms,cutoff_ms))]
    if not times:
        return []
    stride=max(1,ceil(len(times)/max_groups))
    selected=times[::stride]
    rows=[]
    for x in range(0,len(selected),450):
        batch=selected[x:x+450]
        values=",".join("?" for _ in batch)
        rs=conn.execute(
            f"SELECT * FROM {table} WHERE {col} IN ({values}) AND label_available_ms<?{admissible} ORDER BY {col},symbol",
            batch+[cutoff_ms]).fetchall()
        rows.extend(rs)
        if len(rows)>max_rows:
            raise RuntimeError("TOO_MANY_TRAINING_ROWS_REQUIRE_PREREGISTERED_SAMPLING")
    return rows

@dataclass
class ModelHead:
    kind:str
    reg:object
    rank:object|None
    training_cutoff:int
    n_training:int
    n_rank_groups:int
    schema:str=MODEL_SCHEMA

    def predict(self, rows):
        if not rows:return []
        import numpy as np
        x=np.asarray([vector(row,self.kind) for row in rows],dtype='float32')
        mean=self.reg.booster_.predict(x,num_threads=1)
        ranked=self.rank.booster_.predict(x,num_threads=1) if self.rank is not None else mean
        return [(float(a),float(b)) for a,b in zip(mean,ranked)]

def fit_head(rows, kind: str, cutoff_ms: int, label_column: str):
    if len(rows)<40:
        raise ValueError(f"INSUFFICIENT_{kind.upper()}_TRAINING_ROWS")
    if any(int(row["label_available_ms"])>=cutoff_ms or
           int(row["review_ms" if kind=="watch" else "decision_ms"])>=cutoff_ms for row in rows):
        raise RuntimeError("FUTURE_LABEL_LEAKAGE")
    try:
        from lightgbm import LGBMRegressor, LGBMRanker
    except ImportError as exc:
        raise RuntimeError("LIGHTGBM_REQUIRED_FOR_V7_RANKING") from exc
    if any(int(row["label_available_ms"])>=cutoff_ms for row in rows):
        raise RuntimeError("FUTURE_LABEL_LEAKAGE")
    # Group strictly by decision instant; preserve entire comparisons.
    col="review_ms" if kind=="watch" else "decision_ms"
    indexed=sorted(rows,key=lambda r:(r[col],r["symbol"]))
    import numpy as np
    x=np.asarray([vector(r,kind) for r in indexed],dtype='float32')
    y=[float(r[label_column]) for r in indexed]
    reg=LGBMRegressor(n_estimators=120,max_depth=5,num_leaves=15,
                      learning_rate=.04,min_child_samples=20,reg_lambda=2,
                      n_jobs=1,random_state=72026,verbosity=-1)
    reg.fit(x,y)
    groups=defaultdict(list)
    for i,row in enumerate(indexed):
        groups[row[col]].append(i)
    use=[ids for ids in groups.values() if len(ids)>=2]
    rank=None
    if len(use)>=15:
        xx=[x[i] for ids in use for i in ids]
        yy=[relevance(y[i]) for ids in use for i in ids]
        rank=LGBMRanker(objective="lambdarank",metric="ndcg",n_estimators=100,
                         max_depth=4,num_leaves=15,learning_rate=.04,
                         min_child_samples=20,reg_lambda=2,n_jobs=1,
                         random_state=72026,verbosity=-1,
                         label_gain=[0,1,3,7,15])
        rank.fit(xx,yy,group=[len(ids) for ids in use])
    return ModelHead(kind,reg,rank,cutoff_ms,len(indexed),len(use))

@dataclass
class Brain:
    version:str
    watch:ModelHead
    trade:ModelHead
    context_experts:dict[str,ModelHead]
    cutoff_ms:int
    feature_schema:str=MODEL_SCHEMA

    def score(self, rows,kind:str):
        main=self.watch if kind=="watch" else self.trade
        if not rows:return []
        # Optional context-expert routing is learned by separate fits on past
        # market regimes; no frozen strategy-family veto.
        if kind!="opportunity" or not self.context_experts:
            return main.predict(rows)
        predictions=main.predict(rows)
        idx_by_regime=defaultdict(list)
        for i,row in enumerate(rows):
            idx_by_regime[str(row["regime"])].append(i)
        for regime,ix in idx_by_regime.items():
            if regime not in self.context_experts:continue
            specialist=self.context_experts[regime].predict([rows[i] for i in ix])
            for pos,score in zip(ix,specialist):
                predictions[pos]=score
        return predictions

def train(conn,version:str,cutoff_ms:int,*,adaptive:bool=False)->Brain:
    wr=rows_before(conn,"watch",cutoff_ms)
    tr=rows_before(conn,"opportunity",cutoff_ms)
    watch=fit_head(wr,"watch",cutoff_ms,"target_net")
    trade=fit_head(tr,"opportunity",cutoff_ms,"net")
    experts={}
    if adaptive:
        for regime in ("up","down","range"):
            subset=[r for r in tr if r["regime"]==regime]
            # Regime models only when reasonably supported in history.
            if len(subset)>=200 and len({r["decision_ms"] for r in subset})>=40:
                experts[regime]=fit_head(subset,"opportunity",cutoff_ms,"net")
    return Brain(version,watch,trade,experts,cutoff_ms)

def freeze_artifacts(brain: Brain,folder:Path)->dict:
    import joblib
    folder.mkdir(parents=True,exist_ok=False)
    components={"watch":brain.watch,"trade":brain.trade,**{
        "regime_"+k:v for k,v in brain.context_experts.items()}}
    hashes={}
    for key,obj in components.items():
        path=folder/(key+".joblib")
        joblib.dump(obj,path)
        hashes[key]=sha256(path.read_bytes()).hexdigest()
    manifest={"brain_version":brain.version,"schema":brain.feature_schema,
              "training_cutoff_ms":brain.cutoff_ms,"files_sha256":hashes,
              "watch_train_rows":brain.watch.n_training,
              "trade_train_rows":brain.trade.n_training,
              "grouped_rank_training_events":brain.trade.n_rank_groups,
              "has_context_experts":sorted(brain.context_experts),
              "order_authority":"NONE","source_economic_authority":"OFFLINE_5M_PROXY"}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest
