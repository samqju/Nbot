"""Matured-outcome challenger lifecycle; training never grants promotion authority."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import math
import sqlite3
from ..artifacts import file_hash
from ..brain import Brain,fit_head,freeze_artifacts,MODEL_SCHEMA


@dataclass(frozen=True)
class PromotionPolicy:
    min_forward_days:int
    min_portfolio_trades:int
    max_drawdown_fraction:float
    min_uplift_lower_bound:float=0

    def __post_init__(self):
        if self.min_forward_days<=0 or self.min_portfolio_trades<=0 or not 0<self.max_drawdown_fraction<1:
            raise ValueError("INVALID_PROMOTION_POLICY")


class BrainRegistry:
    def __init__(self,path):
        self.conn=sqlite3.connect(str(path),isolation_level=None)
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS model(version TEXT PRIMARY KEY,folder TEXT,manifest_hash TEXT,cutoff_ms INTEGER,schema TEXT,parent TEXT,status TEXT);
        CREATE TABLE IF NOT EXISTS receipt(id INTEGER PRIMARY KEY,version TEXT,body TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS one_champion ON model(status) WHERE status='CHAMPION';
        """)

    def register(self,folder,parent=None,bootstrap=False):
        folder=Path(folder).resolve()
        path=folder/"manifest.json"
        manifest=json.loads(path.read_text())
        for name,digest in manifest["files_sha256"].items():
            asset=(folder/(name+".joblib")).resolve()
            if not asset.is_relative_to(folder) or file_hash(asset)!=digest:
                raise ValueError("MODEL_COMPONENT_HASH_MISMATCH")
        if manifest["schema"]!=MODEL_SCHEMA:raise ValueError("INCOMPATIBLE_FEATURE_SCHEMA")
        if bootstrap and self.conn.execute("SELECT 1 FROM model LIMIT 1").fetchone():
            raise ValueError("BOOTSTRAP_ONLY_EMPTY_REGISTRY")
        self.conn.execute("INSERT INTO model VALUES(?,?,?,?,?,?,?)",
            (manifest["brain_version"],str(folder),file_hash(path),manifest["training_cutoff_ms"],manifest["schema"],parent,
             "CHAMPION" if bootstrap else "CHALLENGER"))
        return manifest["brain_version"]

    def compare(self,version,evidence,policy,*,paper_authorized=False):
        row=self.conn.execute("SELECT cutoff_ms FROM model WHERE version=? AND status='CHALLENGER'",(version,)).fetchone()
        if row is None:raise ValueError("UNKNOWN_CHALLENGER")
        reasons=[]
        if evidence.get("period_start_ms",-1)<row[0]:reasons.append("TRAIN_EVALUATION_OVERLAP")
        if evidence.get("source_authority")!="INDEPENDENT_FORWARD_EXECUTION_VERIFIED":reasons.append("UNVERIFIED_FORWARD_SOURCE")
        if evidence.get("forward_days",0)<policy.min_forward_days:reasons.append("INSUFFICIENT_FORWARD_DAYS")
        if evidence.get("portfolio_trades",0)<policy.min_portfolio_trades:reasons.append("INSUFFICIENT_PORTFOLIO_TRADES")
        lower=evidence.get("uplift_lower_bound",float("nan"))
        dd=evidence.get("max_drawdown_fraction",float("nan"))
        if not math.isfinite(lower) or lower<=policy.min_uplift_lower_bound:reasons.append("UPLIFT_NOT_ESTABLISHED")
        if not math.isfinite(dd) or dd>policy.max_drawdown_fraction:reasons.append("DRAWDOWN_GATE")
        if not paper_authorized:reasons.append("PAPER_PROMOTION_NOT_AUTHORIZED")
        # This method issues a review receipt. It never trusts caller metrics
        # sufficiently to switch the champion by itself.
        receipt={"version":version,"status":"HOLD" if reasons else "ELIGIBLE_FOR_INDEPENDENT_REVIEW",
                 "reasons":reasons,"evidence":evidence,"automatic_promotion":False}
        self.conn.execute("INSERT INTO receipt(version,body) VALUES(?,?)",(version,json.dumps(receipt,sort_keys=True,allow_nan=False)))
        return receipt

    def champion(self):
        row=self.conn.execute("SELECT version FROM model WHERE status='CHAMPION'").fetchone()
        return row[0] if row else None

    def approve_paper(self,version,receipt_id,approval_reference):
        if not approval_reference:raise PermissionError("EXPLICIT_PROMOTION_APPROVAL_REQUIRED")
        receipt=self.conn.execute("SELECT body FROM receipt WHERE id=? AND version=?",(receipt_id,version)).fetchone()
        if receipt is None or json.loads(receipt[0])["status"]!="ELIGIBLE_FOR_INDEPENDENT_REVIEW":
            raise PermissionError("PROMOTION_GATES_NOT_MET")
        self.load(version)  # Verify immutable artifacts again before switching.
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            previous=self.champion()
            self.conn.execute("UPDATE model SET status='RETIRED' WHERE status='CHAMPION'")
            self.conn.execute("UPDATE model SET status='CHAMPION',parent=? WHERE version=?",(previous,version))
            self.conn.execute("INSERT INTO receipt(version,body) VALUES(?,?)",(version,json.dumps({"action":"PAPER_PROMOTION","previous":previous,"approval_reference":approval_reference,"live_authority":False})))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def rollback(self,reason):
        current=self.champion()
        row=self.conn.execute("SELECT parent FROM model WHERE version=?",(current,)).fetchone()
        if row is None or row[0] is None:raise ValueError("NO_APPROVED_ROLLBACK_PARENT")
        parent=row[0]
        self.load(parent)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute("UPDATE model SET status='ROLLED_BACK' WHERE version=?",(current,))
            self.conn.execute("UPDATE model SET status='CHAMPION' WHERE version=?",(parent,))
            self.conn.execute("INSERT INTO receipt(version,body) VALUES(?,?)",(parent,json.dumps({"action":"ROLLBACK","from":current,"reason":reason})))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        return parent

    def load(self,version=None):
        # joblib is only loaded from locally registered, hash-verified artifacts.
        import joblib
        version=version or self.champion()
        row=self.conn.execute("SELECT folder,manifest_hash FROM model WHERE version=?",(version,)).fetchone()
        if row is None:raise ValueError("UNKNOWN_REGISTERED_MODEL")
        folder=Path(row[0])
        if file_hash(folder/"manifest.json")!=row[1]:raise ValueError("MODEL_MANIFEST_CHANGED")
        manifest=json.loads((folder/"manifest.json").read_text())
        heads={}
        for name,digest in manifest["files_sha256"].items():
            path=(folder/(name+".joblib")).resolve()
            if not path.is_relative_to(folder.resolve()) or file_hash(path)!=digest:
                raise ValueError("MODEL_COMPONENT_HASH_MISMATCH")
            heads[name]=joblib.load(path)
        return Brain(version,heads["watch"],heads["trade"],
                     {k.removeprefix("regime_"):v for k,v in heads.items() if k.startswith("regime_")},
                     manifest["training_cutoff_ms"])

    def close(self):self.conn.close()


class LearningLoop:
    def __init__(self,memory,registry,artifact_root,interval_ms=86400000):
        if interval_ms<=0:raise ValueError("INVALID_TRAINING_INTERVAL")
        self.memory=memory
        self.registry=registry
        self.artifact_root=Path(artifact_root)
        self.interval_ms=interval_ms

    def train_due(self,cutoff_ms,version):
        state=self.memory.read()
        if cutoff_ms-state.get("last_training_ms",0)<self.interval_ms:return None
        # Memory includes selected, rejected and outside-universe shadow paths.
        # Each outcome supplies a causal training row in a separate namespace.
        rows=self.memory.matured(cutoff_ms)
        watch=[r["row"] for r in rows if r.get("task")=="watch"]
        trade=[r["row"] for r in rows if r.get("task")=="opportunity"]
        if len(watch)<40 or len(trade)<40:return None
        w=fit_head(watch,"watch",cutoff_ms,"target_net")
        t=fit_head(trade,"opportunity",cutoff_ms,"net")
        experts={}
        for regime in ("up","down","range"):
            group=[r for r in trade if r["regime"]==regime]
            if len(group)>=200 and len({r["decision_ms"] for r in group})>=40:
                experts[regime]=fit_head(group,"opportunity",cutoff_ms,"net")
        brain=Brain(version,w,t,experts,cutoff_ms)
        folder=self.artifact_root/version
        freeze_artifacts(brain,folder)
        self.registry.register(folder,parent=self.registry.champion())
        self.memory.transition("CHALLENGER_TRAINED",lambda s:s.update(last_training_ms=cutoff_ms),
                               {"version":version,"cutoff_ms":cutoff_ms,"automatic_promotion":False})
        return brain
