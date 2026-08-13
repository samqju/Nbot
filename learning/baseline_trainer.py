"""Offline Phase 4.3 baseline model trainer."""
from __future__ import annotations
import json, math, os, pickle, tempfile, time
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from learning.context_features import (
 CONTEXT_FEATURE_NAMES,
 CONTEXT_FEATURE_SCHEMA_VERSION,
 context_feature_vector,
 is_complete_market_context,
 market_context_from_row,
)

FEATURE_NAMES=("short_range","long_range","trend_score","wick_ratio_recent","body_ratio_recent","range_acceleration","dist_high","dist_low","directional_consistency")
ARTIFACT_SCHEMA_VERSION=1
MATRIX_BUILD_MODE="STREAMING_COMPACT_NUMPY"

class BaselineModelTrainer:
 def __init__(self,*,train_path,validation_path,test_path,artifact_path,report_path,outcome_type="VIRTUAL_TRADE",min_train_rows=100,min_eval_rows=20,random_state=42,context_aware=False,evaluate_test=True):
  self.train_path=Path(train_path); self.validation_path=Path(validation_path); self.test_path=Path(test_path) if test_path else None; self.artifact_path=Path(artifact_path); self.report_path=Path(report_path); self.outcome_type=outcome_type.upper(); self.min_train_rows=int(min_train_rows); self.min_eval_rows=int(min_eval_rows); self.random_state=int(random_state); self.context_aware=bool(context_aware); self.evaluate_test=bool(evaluate_test)
 def train(self):
  issues=Counter(); paths={"train":self.train_path,"validation":self.validation_path}
  if self.evaluate_test:
   if self.test_path is None: raise ValueError("BASELINE_TEST_PATH_REQUIRED")
   paths["test"]=self.test_path
  summaries={name:self._scan(path,name,issues,collect_patterns=(name=="train")) for name,path in paths.items()}
  status="TRAINED"
  if summaries["train"]["count"]<self.min_train_rows or summaries["validation"]["count"]<self.min_eval_rows or (self.evaluate_test and summaries["test"]["count"]<self.min_eval_rows): status="INSUFFICIENT_DATA"
  elif any(len(summary["labels"])<2 for summary in summaries.values()): status="INSUFFICIENT_CLASS_DIVERSITY"
  report={"schema_version":1,"generated_at_ms":int(time.time()*1000),"status":status,"outcome_type":self.outcome_type,"rows":{k:v["count"] for k,v in summaries.items()},"issues":dict(sorted(issues.items())),"issue_count":sum(issues.values()),"artifact_path":str(self.artifact_path),"runtime_activation":"DISABLED","matrix_build_mode":MATRIX_BUILD_MODE}
  if status!="TRAINED": self._write_json(self.report_path,report); return report
  patterns=sorted(summaries["train"]["patterns"]); columns=list(FEATURE_NAMES)+["rule_score","final_score","direction_long"]+[f"pattern::{p}" for p in patterns]+(list(CONTEXT_FEATURE_NAMES) if self.context_aware else [])
  matrices={}; labels={}
  for name,path in paths.items():
   matrices[name],labels[name]=self._matrix(path,name,patterns,summaries[name]["count"])
  scaler=StandardScaler(); Xtr=scaler.fit_transform(matrices["train"])
  model=LogisticRegression(max_iter=1000,class_weight="balanced",random_state=self.random_state); model.fit(Xtr,labels["train"])
  metric_splits=("validation","test") if self.evaluate_test else ("validation",); metrics={k:self._metrics(labels[k],model.predict_proba(scaler.transform(matrices[k]))[:,1]) for k in metric_splits}
  artifact={"artifact_schema_version":ARTIFACT_SCHEMA_VERSION,"model_kind":"LOGISTIC_REGRESSION_BASELINE","created_at_ms":int(time.time()*1000),"outcome_type":self.outcome_type,"feature_schema_version":3,"base_feature_names":FEATURE_NAMES,"pattern_categories":tuple(patterns),"vector_columns":tuple(columns),"scaler":scaler,"model":model,"metrics":metrics,"training_rows":summaries["train"]["count"],"runtime_activation":"DISABLED","context_feature_schema_version":(CONTEXT_FEATURE_SCHEMA_VERSION if self.context_aware else None),"context_feature_names":(CONTEXT_FEATURE_NAMES if self.context_aware else ()),"requires_complete_market_context":self.context_aware,"test_evaluated_during_training":self.evaluate_test,"matrix_build_mode":MATRIX_BUILD_MODE}
  self._write_pickle(self.artifact_path,artifact); report.update({"metrics":metrics,"vector_columns":columns,"pattern_categories":patterns,"test_evaluated_during_training":self.evaluate_test,"class_balance":{k:dict(Counter(map(str,labels[k].tolist()))) for k in labels}}); self._write_json(self.report_path,report); return report
 def _read(self,path,name,issues):
  path=Path(path)
  if not path.exists(): issues[f"{name}_file_missing"]+=1; return []
  out=[]
  with path.open("r") as handle:
   for raw_line in handle:
    line=raw_line.strip()
    if not line: continue
    try:r=json.loads(line)
    except json.JSONDecodeError: issues[f"{name}_malformed_json"]+=1; continue
    if isinstance(r,dict): out.append(r)
    else: issues[f"{name}_row_not_object"]+=1
  return out
 def _filter(self,rows,name,issues):
  out=[]; seen=set()
  for r in rows:
   if r.get("outcome_type")!=self.outcome_type: continue
   cid=str(r.get("candidate_observation_id") or "").strip()
   if not cid or cid in seen: issues[f"{name}_duplicate_or_invalid_candidate"]+=1; continue
   if r.get("label_profitable") not in {True,False}: issues[f"{name}_invalid_label"]+=1; continue
   f=r.get("features")
   try:
    if not isinstance(f,dict) or any(not math.isfinite(float(f[n])) for n in FEATURE_NAMES): raise ValueError
    if not math.isfinite(float(r.get("rule_score",0))) or not math.isfinite(float(r.get("final_score",0))): raise ValueError
   except (KeyError,TypeError,ValueError): issues[f"{name}_invalid_features"]+=1; continue
   if r.get("direction") not in {"LONG","SHORT"} or not str(r.get("pattern") or "").strip(): issues[f"{name}_invalid_identity"]+=1; continue
   if self.context_aware and not is_complete_market_context(market_context_from_row(r)): issues[f"{name}_market_context_incomplete"]+=1; continue
   seen.add(cid); out.append(r)
  return out
 def _scan(self,path,name,issues,collect_patterns=False):
  count=0; labels=Counter(); patterns=set()
  for r in self._iter_filtered(path,name,issues):
   count+=1; labels[str(r["label_profitable"])]+=1
   if collect_patterns: patterns.add(r["pattern"])
  return {"count":count,"labels":labels,"patterns":patterns}
 def _matrix(self,path,name,patterns,count):
  width=len(FEATURE_NAMES)+3+len(patterns)+(len(CONTEXT_FEATURE_NAMES) if self.context_aware else 0)
  matrix=np.empty((count,width),dtype=float); labels=np.empty(count,dtype=int); index=0
  for r in self._iter_filtered(path,name,None):
   if index>=count: raise RuntimeError("BASELINE_SPLIT_CHANGED_DURING_LOAD")
   matrix[index,:]=self._vector(r,patterns,self.context_aware); labels[index]=int(r["label_profitable"]); index+=1
  if index!=count: raise RuntimeError("BASELINE_SPLIT_CHANGED_DURING_LOAD")
  return matrix,labels
 def _iter_filtered(self,path,name,issues):
  path=Path(path)
  if not path.exists():
   if issues is not None: issues[f"{name}_file_missing"]+=1
   return
  seen=set()
  with path.open("r") as handle:
   for raw_line in handle:
    line=raw_line.strip()
    if not line: continue
    try:r=json.loads(line)
    except json.JSONDecodeError:
     if issues is not None: issues[f"{name}_malformed_json"]+=1
     continue
    if not isinstance(r,dict):
     if issues is not None: issues[f"{name}_row_not_object"]+=1
     continue
    if r.get("outcome_type")!=self.outcome_type: continue
    cid=str(r.get("candidate_observation_id") or "").strip()
    if not cid or cid in seen:
     if issues is not None: issues[f"{name}_duplicate_or_invalid_candidate"]+=1
     continue
    if r.get("label_profitable") not in {True,False}:
     if issues is not None: issues[f"{name}_invalid_label"]+=1
     continue
    f=r.get("features")
    try:
     if not isinstance(f,dict) or any(not math.isfinite(float(f[n])) for n in FEATURE_NAMES): raise ValueError
     if not math.isfinite(float(r.get("rule_score",0))) or not math.isfinite(float(r.get("final_score",0))): raise ValueError
    except (KeyError,TypeError,ValueError):
     if issues is not None: issues[f"{name}_invalid_features"]+=1
     continue
    if r.get("direction") not in {"LONG","SHORT"} or not str(r.get("pattern") or "").strip():
     if issues is not None: issues[f"{name}_invalid_identity"]+=1
     continue
    if self.context_aware and not is_complete_market_context(market_context_from_row(r)):
     if issues is not None: issues[f"{name}_market_context_incomplete"]+=1
     continue
    seen.add(cid); yield r
 @staticmethod
 def _vector(r,patterns,context_aware=False):
  f=r["features"]; vector=[float(f[n]) for n in FEATURE_NAMES]+[float(r.get("rule_score",0)),float(r.get("final_score",0)),1.0 if r["direction"]=="LONG" else 0.0]+[1.0 if r["pattern"]==p else 0.0 for p in patterns]
  if context_aware: vector += context_feature_vector(market_context_from_row(r))
  return vector
 @staticmethod
 def _metrics(y,p):
  pred=(p>=0.5).astype(int); return {"roc_auc":float(roc_auc_score(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1])),"brier_score":float(brier_score_loss(y,p)),"accuracy":float(accuracy_score(y,pred)),"positive_rate":float(np.mean(y)),"rows":int(len(y))}
 @staticmethod
 def _write_json(path,doc):
  path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=f'.{path.name}.',suffix='.tmp',dir=str(path.parent));
  try:
   with os.fdopen(fd,'w') as h: json.dump(doc,h,indent=2,sort_keys=True); h.write('\n'); h.flush(); os.fsync(h.fileno())
   os.replace(tmp,path)
  except Exception:
   try: os.unlink(tmp)
   except FileNotFoundError: pass
   raise
 @staticmethod
 def _write_pickle(path,obj):
  path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix=f'.{path.name}.',suffix='.tmp',dir=str(path.parent));
  try:
   with os.fdopen(fd,'wb') as h: pickle.dump(obj,h); h.flush(); os.fsync(h.fileno())
   os.replace(tmp,path)
  except Exception:
   try: os.unlink(tmp)
   except FileNotFoundError: pass
   raise
