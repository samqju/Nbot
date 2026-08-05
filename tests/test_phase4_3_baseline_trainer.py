import json,tempfile,unittest,pickle
from pathlib import Path
from learning.baseline_trainer import BaselineModelTrainer,FEATURE_NAMES
class T(unittest.TestCase):
 def row(self,i,label,source="VIRTUAL_TRADE"):
  return {"candidate_observation_id":f"c{i}","outcome_type":source,"label_profitable":label,"direction":"LONG" if i%2 else "SHORT","pattern":"RANGE_BREAKOUT" if i%3 else "MEAN_REVERSION","rule_score":.6,"final_score":.7,"features":{n:float(i+j+1)/100 for j,n in enumerate(FEATURE_NAMES)}}
 def write(self,p,rows): p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
 def test_trains_offline_artifact(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); tr=d/'tr'; va=d/'va'; te=d/'te'; art=d/'m.pkl'; rep=d/'r.json'; self.write(tr,[self.row(i,i%2==0) for i in range(40)]); self.write(va,[self.row(100+i,i%2==0) for i in range(12)]); self.write(te,[self.row(200+i,i%2==0) for i in range(12)]); r=BaselineModelTrainer(train_path=tr,validation_path=va,test_path=te,artifact_path=art,report_path=rep,min_train_rows=20,min_eval_rows=5).train(); self.assertEqual(r["status"],"TRAINED"); self.assertTrue(art.exists()); a=pickle.loads(art.read_bytes()); self.assertEqual(a["runtime_activation"],"DISABLED"); self.assertIn("roc_auc",r["metrics"]["test"])
 def test_insufficient_does_not_create_artifact(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); paths=[d/x for x in ('tr','va','te')]; [self.write(p,[self.row(i,i%2==0) for i in range(4)]) for p in paths]; art=d/'m'; r=BaselineModelTrainer(train_path=paths[0],validation_path=paths[1],test_path=paths[2],artifact_path=art,report_path=d/'r',min_train_rows=20,min_eval_rows=5).train(); self.assertEqual(r["status"],"INSUFFICIENT_DATA"); self.assertFalse(art.exists())
 def test_filters_other_outcome_sources(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); p=d/'x'; self.write(p,[self.row(1,True,"FORWARD_5_CANDLE")]); t=BaselineModelTrainer(train_path=p,validation_path=p,test_path=p,artifact_path=d/'m',report_path=d/'r',min_train_rows=20,min_eval_rows=5); issues=__import__('collections').Counter(); self.assertEqual(t._filter(t._read(p,'train',issues),'train',issues),[])
if __name__=='__main__': unittest.main()
