import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nbot.observation.model_compatibility import compatible_training_release
from nbot.operator.status_proxy import _activity_summary, _activity_text
from tests.test_learned_testnet import LearnedTestnetTests
from tests.communication.test_v35_control_target import NOW
from nbot.observation.challengers import CHALLENGER_PREFIX, EVALUATION_PREFIX

class CompatibilityTests(unittest.TestCase):
    def test_git_training_changes_block_but_operator_changes_allow_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            r=Path(td)
            def git(*args):
                return subprocess.check_output(["git",*args],cwd=r,stderr=subprocess.DEVNULL,text=True).strip()
            git("init")
            git("config","user.name","Test");git("config","user.email","test@example.invalid")
            p=r/"nbot/observation/features.py";p.parent.mkdir(parents=True);p.write_text("features = 1")
            git("add",".");git("commit","-m","train");trained=git("rev-parse","HEAD")
            q=r/"nbot/operator/status.py";q.parent.mkdir(parents=True);q.write_text("labels = 1")
            git("add",".");git("commit","-m","ui");ui=git("rev-parse","HEAD")
            self.assertTrue(compatible_training_release(r,trained,ui))
            p.write_text("features = 2");git("add",".");git("commit","-m","features")
            self.assertFalse(compatible_training_release(r,trained,git("rev-parse","HEAD")))
            self.assertFalse(compatible_training_release(r,"0"*40,ui))
            self.assertFalse(compatible_training_release(r,"--bad",ui))

    def test_reusable_model_still_obeys_rejection_and_real_money_release_gate(self):
        f=LearnedTestnetTests();f.setUp()
        try:
            source=f.source
            source.release_sha="b"*40
            with patch("nbot.observation.learned_recommendation.compatible_training_release",return_value=True) as compat:
                self.assertIsNotNone(source._model(NOW))
                self.assertIsNotNone(source._model(NOW))
                self.assertEqual(compat.call_count,1)
                ch=f.training.memory.list_artifacts(prefix=CHALLENGER_PREFIX)[0]["payload"]
                f.training.memory.persist_artifact(EVALUATION_PREFIX+ch["challenger_version"],{"status":"REJECT_RESEARCH_GATE"})
                self.assertIsNone(source._model(NOW))
            from nbot.config.profiles import get_profile
            source.profile=get_profile("live-trade")
            self.assertFalse(source._compatible_release("a"*40))
        finally:f.doCleanups()

class ShadowVisibilityTests(unittest.TestCase):
    def test_read_only_counts_separate_releases_and_pending_from_open(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"db.sqlite"
            from nbot.observation.shadow import SCHEMA
            c=sqlite3.connect(p);c.executescript(SCHEMA)
            for i,status in enumerate(["OPEN","PENDING"]):
                c.execute("INSERT INTO shadow_positions VALUES(?,?,?,?,?,?)",
                          (str(i),str(i),"old","live-paper",json.dumps({"status":status}),"fixture"))
            for i,(sha,eligible,net) in enumerate([("old",1,10),("new",1,-2),("new",0,99)]):
                c.execute("INSERT INTO shadow_results VALUES(?,?,?,?,?,?,?,?)",
                          (str(i),str(i),sha,"live-paper",1000+i,eligible,json.dumps({"net_usd":net}),"fixture"))
            c.commit();c.close()
            result=_activity_summary(p,"live-paper","new")
            self.assertEqual((result["open"],result["pending"]),(1,1))
            self.assertEqual((result["completed"],result["excluded"]),(2,1))
            self.assertEqual(result["current_completed"],1)
            self.assertEqual(result["current_net_usd"],-2)
            self.assertIn("separate simulations",_activity_text({"shadow_activity":result}))

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"absent"
            self.assertIn("No shadow",_activity_summary(p,"live-paper","new")["status"])
            self.assertFalse(p.exists())
