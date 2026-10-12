"""V4 generation registry: 1,000 new outcomes initially, 5,000 from Gen-4.

This is intentionally separate from the real-time research process.  Training
may be CPU/RAM heavy; research/WSS capture must remain responsive.

A generation is created only from immutable completed V4 virtual trades.
Generation 1 is the baseline model. Later generations are candidate models and
must qualify before they may enter Champion-vs-Challenger paper evaluation.
No model in this module has order authority.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from typing import Any

from .selective_ml import ML_FEATURE_NAMES, augment_vector, _ml_imports
from .v4_research import BATCH_SIZE, VERSION as RESEARCH_VERSION
from .v4_promotion import connect

VERSION = "NBOT_V4_GENERATION_V1"
AUTHORITY = "V4_MODEL_RESEARCH_ONLY_NO_ORDER_AUTHORITY"
MODEL_PREFIX = "V4_MODEL_GEN_"
MIN_EVENTS = 40
VALIDATION_FRACTION = 0.20
MAX_TRAIN_ROWS = 50_000


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _relevance(net_r: float) -> int:
    if net_r >= 1.0: return 4
    if net_r >= 0.5: return 3
    if net_r > 0.0: return 2
    if net_r > -0.5: return 1
    return 0


def _qualification_status(existing_generations: int, metrics: dict[str, float]) -> str:
    if int(existing_generations) == 0:
        return "BASELINE_READY"
    if float(metrics["mean_net_r"]) > 0 and float(metrics["positive_rate"]) >= .50:
        return "CHALLENGER_READY"
    return "RESEARCH_REJECTED"


@dataclass(frozen=True)
class ResearchRow:
    decision_id: str
    event_ms: int
    symbol: str
    side: str
    vector: dict[str, Any]
    net_r: float
    matured_at_ms: int


class V4GenerationStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self.path) as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS generations(
                generation INTEGER PRIMARY KEY,
                batch_no INTEGER UNIQUE NOT NULL,
                trained_at_ms INTEGER NOT NULL,
                training_rows INTEGER NOT NULL,
                training_events INTEGER NOT NULL,
                validation_events INTEGER NOT NULL,
                validation_mean_net_r REAL NOT NULL,
                validation_positive_rate REAL NOT NULL,
                qualification_status TEXT NOT NULL,
                artifact_json TEXT NOT NULL,
                artifact_digest TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS state(
                key TEXT PRIMARY KEY,
                value TEXT
            );
            INSERT OR IGNORE INTO state VALUES('champion_generation', NULL);
            INSERT OR IGNORE INTO state VALUES('challenger_generation', NULL);
            CREATE TABLE IF NOT EXISTS paper_review_outbox(
                contest_path TEXT NOT NULL,
                contest_id INTEGER NOT NULL,
                decision TEXT NOT NULL,
                reviewed_at_ms INTEGER NOT NULL,
                report_json TEXT NOT NULL,
                champion_generation INTEGER,
                applied INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(contest_path,contest_id)
            );
            """)
    def existing_batches(self) -> set[int]:
        self.initialize()
        with connect(self.path) as conn:
            return {int(r[0]) for r in conn.execute("SELECT batch_no FROM generations")}
    def save_generation(self, *, batch_no: int, artifact: dict[str, Any],
                        training_rows: int, training_events: int, validation_events: int,
                        validation_mean: float, validation_positive: float,
                        qualification: str, now_ms: int) -> int:
        self.initialize()
        encoded = json.dumps(artifact, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with connect(self.path) as conn:
            generation = int(conn.execute("SELECT COALESCE(MAX(generation),0)+1 FROM generations").fetchone()[0])
            conn.execute(
                """INSERT INTO generations VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (generation, int(batch_no), int(now_ms), int(training_rows), int(training_events),
                 int(validation_events), float(validation_mean), float(validation_positive),
                 str(qualification), encoded, digest),
            )
        return generation
    def set_state(self, key: str, generation: int | None) -> None:
        if key not in {"champion_generation", "challenger_generation"}:
            raise ValueError("V4_STATE_KEY_INVALID")
        self.initialize()
        with connect(self.path) as conn:
            conn.execute("UPDATE state SET value=? WHERE key=?",
                         (None if generation is None else str(int(generation)), key))
    def state(self) -> dict[str, int | None]:
        self.initialize()
        with connect(self.path) as conn:
            rows = dict(conn.execute("SELECT key,value FROM state"))
        return {k: None if v is None else int(v) for k,v in rows.items()}
    def assign_challenger_if_empty(self, generation: int) -> bool:
        self.initialize()
        with connect(self.path) as conn:
            changed = conn.execute(
                """UPDATE state SET value=? WHERE key='challenger_generation'
                   AND value IS NULL
                   AND NOT EXISTS(SELECT 1 FROM paper_review_outbox WHERE applied=0)""",
                (str(int(generation)),),
            ).rowcount
        return bool(changed)
    def generation(self, generation: int) -> dict[str, Any] | None:
        self.initialize()
        with connect(self.path) as conn:
            row = conn.execute(
                "SELECT artifact_json,artifact_digest,qualification_status FROM generations WHERE generation=?",
                (int(generation),),
            ).fetchone()
        if row is None: return None
        artifact = json.loads(row[0])
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValueError("V4_GENERATION_ARTIFACT_CORRUPT")
        return {"artifact": artifact, "artifact_digest": row[1], "qualification_status": row[2]}


def load_rows(ledger_path: str | Path, *, through_outcome: int) -> list[ResearchRow]:
    path = Path(ledger_path)
    if not path.is_file():
        return []
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT d.decision_id,d.event_id,d.symbol,d.side,d.payload_json,
                      o.payload_json,o.matured_at_ms
               FROM matured_outcomes o
               JOIN frozen_decisions d USING(decision_id)
               WHERE o.actual_execution=0
               ORDER BY o.matured_at_ms,o.decision_id
               LIMIT ?""",
            (int(through_outcome),),
        ).fetchall()
    result = []
    for decision_id,event_id,symbol,side,decision_json,outcome_json,matured_at in rows:
        try:
            d = json.loads(decision_json); o = json.loads(outcome_json)
            extras = d.get("extras") or {}
            if extras.get("v4_contract") != RESEARCH_VERSION:
                continue
            vector = extras["feature_vector"]
            net_r = float(o["net_r"])
            event_ms = int(str(event_id).split(":")[-1])
            augment_vector(vector)  # contract/finite validation
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if not math.isfinite(net_r):
            continue
        result.append(ResearchRow(str(decision_id),event_ms,str(symbol),str(side),vector,net_r,int(matured_at)))
    return result[-MAX_TRAIN_ROWS:]


def _groups(rows: list[ResearchRow]):
    grouped = defaultdict(list)
    for row in rows: grouped[row.event_ms].append(row)
    return sorted(grouped.items())


def _matrix(groups, np):
    x=[]; y=[]; w=[]; sizes=[]; meta=[]
    for event,rows in groups:
        usable=[]
        for row in rows:
            try:
                v=augment_vector(row.vector)
                values=[float(v[name]) for name in ML_FEATURE_NAMES]
            except (KeyError,TypeError,ValueError):
                continue
            if not all(math.isfinite(z) for z in values): continue
            usable.append((row,values))
        if len(usable)<2: continue
        sizes.append(len(usable)); weight=1.0/len(usable)
        for row,values in usable:
            x.append(values); y.append(_relevance(row.net_r)); w.append(weight); meta.append(row)
    return np.asarray(x,dtype="float32"),np.asarray(y,dtype="int32"),np.asarray(w,dtype="float32"),sizes,meta


def _train_ranker(lgb, train, valid):
    tx,ty,tw,tg,_=train; vx,vy,vw,vg,_=valid
    params={"objective":"lambdarank","metric":"ndcg","ndcg_eval_at":[1,3,5],
            "label_gain":[0,1,3,7,15],"learning_rate":.04,"num_leaves":15,
            "max_depth":4,"min_data_in_leaf":30,"feature_fraction":.85,
            "bagging_fraction":.8,"bagging_freq":1,"lambda_l2":1.0,
            "verbosity":-1,"num_threads":1,"seed":417,"deterministic":True,
            "force_col_wise":True}
    a=lgb.Dataset(tx,label=ty,weight=tw,group=tg,feature_name=list(ML_FEATURE_NAMES),free_raw_data=False)
    b=lgb.Dataset(vx,label=vy,weight=vw,group=vg,reference=a,feature_name=list(ML_FEATURE_NAMES),free_raw_data=False)
    return lgb.train(params,a,num_boost_round=180,valid_sets=[b],valid_names=["validation"],
                     callbacks=[lgb.early_stopping(20,verbose=False)])


def _top1_metrics(matrix, predictions):
    *_,sizes,meta=matrix
    offset=0; selected=[]
    for size in sizes:
        stop=offset+size
        winner=max(range(offset,stop),key=lambda i:(float(predictions[i]),meta[i].decision_id))
        selected.append(meta[winner].net_r); offset=stop
    if not selected: return {"events":0,"mean_net_r":-999.,"positive_rate":0.}
    return {"events":len(selected),"mean_net_r":sum(selected)/len(selected),
            "positive_rate":sum(v>0 for v in selected)/len(selected)}


class V4GenerationTrainer:
    def __init__(self, *, ledger_path="data/observation/v4/research_ledger.db",
                 research_meta_path="data/observation/v4/research_meta.db",
                 generation_path="data/observation/v4/generations.db") -> None:
        self.ledger_path=Path(ledger_path); self.research_meta_path=Path(research_meta_path)
        self.store=V4GenerationStore(generation_path); self.store.initialize()

    def schedule(self) -> dict[str,Any]:
        from .v4_policy import training_schedule
        with connect(self.store.path) as conn:
            last=conn.execute('SELECT generation,batch_no FROM generations ORDER BY generation DESC LIMIT 1').fetchone()
        resolved=0
        if self.ledger_path.is_file():
            with connect(self.ledger_path.resolve().as_uri()+'?mode=ro',uri=True) as conn:
                resolved=int(conn.execute('SELECT COUNT(*) FROM matured_outcomes WHERE actual_execution=0').fetchone()[0])
        return training_schedule(*(last or (0,0)), resolved=resolved)

    def ready_batches(self) -> list[int]:
        if not self.research_meta_path.is_file(): return []
        with connect(self.research_meta_path) as conn:
            rows=conn.execute("SELECT batch_no FROM v4_batches WHERE status='READY_FOR_TRAINING' ORDER BY batch_no").fetchall()
        done=self.store.existing_batches()
        target=self.schedule()['target_batch']
        return [int(r[0]) for r in rows if int(r[0])==target and int(r[0]) not in done]

    def train_next(self) -> dict[str,Any]:
        ready=self.ready_batches()
        if not ready: return {"status":"NO_READY_BATCH","version":VERSION,**self.schedule()}
        batch=ready[0]
        rows=load_rows(self.ledger_path,through_outcome=batch*BATCH_SIZE)
        groups=_groups(rows)
        if len(groups)<MIN_EVENTS:
            return {"status":"WAIT_FOR_EVENT_DIVERSITY","batch_no":batch,"events":len(groups)}
        cut=max(1,int(len(groups)*(1-VALIDATION_FRACTION)))
        train_groups,valid_groups=groups[:cut],groups[cut:]
        if len(valid_groups)<5:
            return {"status":"WAIT_FOR_VALIDATION_EVENTS","batch_no":batch}
        lgb,np=_ml_imports()
        train=_matrix(train_groups,np); valid=_matrix(valid_groups,np)
        if not train[3] or not valid[3]:
            return {"status":"WAIT_FOR_RANKABLE_DATA","batch_no":batch}
        model=_train_ranker(lgb,train,valid)
        metrics=_top1_metrics(valid,model.predict(valid[0]))

        state=self.store.state()
        existing_generations = len(self.store.existing_batches())
        # Generation 1 alone is the provisional baseline. Every later generation
        # must pass the held-out gate even while the first baseline is still in
        # paper examination. This prevents a newer training batch from replacing
        # the frozen active challenger merely because no Champion exists yet.
        qualification = _qualification_status(existing_generations, metrics)
        artifact={"version":VERSION,"research_version":RESEARCH_VERSION,"batch_no":batch,
                  "research_outcome_cutoff":batch*BATCH_SIZE,
                  "training_interval_outcomes":self.schedule()['training_interval_outcomes'],
                  "trained_at_ms":int(time.time()*1000),"training_cutoff_event_ms":train_groups[-1][0],
                  "feature_names":list(ML_FEATURE_NAMES),"ranking_model":model.model_to_string(),
                  "validation":metrics,"authority":AUTHORITY,"order_authority":"NONE",
                  "automatic_real_money_promotion":False}
        artifact["model_digest"]=_digest(artifact)
        generation=self.store.save_generation(
            batch_no=batch,artifact=artifact,training_rows=len(train[1]),
            training_events=len(train[3]),validation_events=metrics["events"],
            validation_mean=metrics["mean_net_r"],validation_positive=metrics["positive_rate"],
            qualification=qualification,now_ms=artifact["trained_at_ms"])
        if qualification=="BASELINE_READY":
            # Gen-1 is eligible for the first paper-validation stage; this is not
            # live-money authority.
            self.store.assign_challenger_if_empty(generation)
        elif qualification=="CHALLENGER_READY" and state["challenger_generation"] is None:
            # An active paper exam is frozen. Qualified newer generations remain
            # durable in the registry and are picked up by the paper-contest queue
            # after the current Challenger leaves that slot.
            self.store.assign_challenger_if_empty(generation)
        return {"status":qualification,"generation":generation,"batch_no":batch,
                "validation":metrics,"order_authority":"NONE"}

    def status(self) -> dict[str,Any]:
        return {"version":VERSION,"state":self.store.state(),"ready_batches":self.ready_batches(),
                **self.schedule(),
                "order_authority":"NONE"}
