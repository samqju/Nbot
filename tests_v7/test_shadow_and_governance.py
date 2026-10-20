import json
from pathlib import Path
import tempfile
import unittest
from nbot_v7.runtime import Memory
from nbot_v7.runtime.shadow import ShadowBook
from nbot_v7.runtime.learning import BrainRegistry,PromotionPolicy,LearningLoop
from nbot_v7.data import Bar,BAR_MS
from nbot_v7.brain import BASE_KEYS,fit_head,Brain,freeze_artifacts


class ShadowAndGovernance(unittest.TestCase):
    def test_all_selected_rejected_and_outside_control_shadows_mature_without_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Memory(Path(tmp)/"memory.sqlite")
            try:
                book=ShadowBook(m)
                rows=[{"decision_ms":0,"symbol":s,"side":side,"family":"neutral_grid","regime":"up",
                       "features":"{}","source_hash":"f"*64} for s in ("BTCUSDT","ETHUSDT") for side in ("LONG","SHORT")]
                book.propose(rows,{"BTCUSDT":100,"ETHUSDT":100},0,{"BTCUSDT"},control_probability=1)
                self.assertEqual(m.conn.execute("SELECT COUNT(*) FROM shadow").fetchone()[0],4)
                for s in ("BTCUSDT","ETHUSDT"):
                    self.assertEqual(book.on_bar(s,Bar(0,100,105,95,100,10),BAR_MS),2)
                self.assertEqual(len(m.matured(BAR_MS+1)),4)
                self.assertIsNone(m.read()["position"])
            finally:m.close()

    def test_training_registers_challenger_and_holds_proxy_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);memory=Memory(root/"memory.sqlite");registry=BrainRegistry(root/"registry.sqlite")
            try:
                for i in range(45):
                    f=json.dumps({key:.001*(i%4) for key in BASE_KEYS})
                    for task in ("watch","opportunity"):
                        row={"review_ms":i*BAR_MS,"decision_ms":i*BAR_MS,"label_available_ms":i*BAR_MS+1,
                             "symbol":"BTCUSDT","side":"LONG","family":"neutral_grid","regime":"up",
                             "features":f,"net":.01,"target_net":.01}
                        memory.record_outcome(task+str(i),row["label_available_ms"],{"task":task,"row":row})
                loop=LearningLoop(memory,registry,root/"models",interval_ms=1)
                brain=loop.train_due(50*BAR_MS,"TEST_CHALLENGER")
                self.assertIsNotNone(brain)
                self.assertIsNone(registry.champion())
                self.assertEqual(registry.load("TEST_CHALLENGER").version,brain.version)
                receipt=registry.compare(brain.version,{"period_start_ms":brain.cutoff_ms},PromotionPolicy(90,100,.1))
                self.assertEqual(receipt["status"],"HOLD")
                self.assertIn("UNVERIFIED_FORWARD_SOURCE",receipt["reasons"])
                with self.assertRaisesRegex(PermissionError,"GATES"):
                    registry.approve_paper(brain.version,1,"TEST_UNAPPROVED")
                (root/"models"/brain.version/"trade.joblib").write_bytes(b"corrupt")
                with self.assertRaisesRegex(ValueError,"HASH_MISMATCH"):registry.load(brain.version)
            finally:memory.close();registry.close()

if __name__=="__main__":unittest.main()
