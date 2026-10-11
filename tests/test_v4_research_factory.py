import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.observation.v4_research import (
    AUTHORITY, BATCH_SIZE, CAPACITY, ORDER_AUTHORITY,
    V4ResearchStore,
)
from nbot.observation.v4_generation import V4GenerationStore


class V4ResearchContractTests(unittest.TestCase):
    def test_fixed_capacity_and_batch_contract(self):
        self.assertEqual(CAPACITY,100)
        self.assertEqual(BATCH_SIZE,1000)
        self.assertEqual(ORDER_AUTHORITY,"NONE")
        self.assertIn("NO_EXECUTION",AUTHORITY)

    def test_batches_close_only_at_each_1000_resolved(self):
        with tempfile.TemporaryDirectory() as td:
            store=V4ResearchStore(Path(td)/"meta.db")
            self.assertEqual(store.close_ready_batches(999,now_ms=1),[])
            self.assertEqual(store.close_ready_batches(1000,now_ms=2),[1])
            self.assertEqual(store.close_ready_batches(1999,now_ms=3),[])
            self.assertEqual(store.close_ready_batches(2000,now_ms=4),[2])
            self.assertEqual(store.close_ready_batches(2500,now_ms=5),[])
            status=store.status()
            self.assertEqual([b["batch_no"] for b in status["batches"]],[1,2])

    def test_generation_state_starts_without_champion(self):
        with tempfile.TemporaryDirectory() as td:
            store=V4GenerationStore(Path(td)/"generations.db")
            self.assertEqual(store.state(),{
                "champion_generation":None,
                "challenger_generation":None,
            })
            store.set_state("challenger_generation",1)
            self.assertEqual(store.state()["challenger_generation"],1)

    def test_generation_artifact_digest_is_checked(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"generations.db"
            store=V4GenerationStore(path)
            generation=store.save_generation(
                batch_no=1,artifact={"x":1},training_rows=100,
                training_events=40,validation_events=10,
                validation_mean=.1,validation_positive=.6,
                qualification="BASELINE_READY",now_ms=1,
            )
            self.assertEqual(generation,1)
            self.assertEqual(store.generation(1)["artifact"],{"x":1})
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE generations SET artifact_json=? WHERE generation=1",
                             (json.dumps({"x":2}),))
            with self.assertRaisesRegex(ValueError,"ARTIFACT_CORRUPT"):
                store.generation(1)


if __name__=="__main__":
    unittest.main()
