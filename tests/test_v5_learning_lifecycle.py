"""Learning boundary unit tests; generated rows are not end-to-end evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.learning_lifecycle import LearningLifecycle
from nbot.v5.research_store import ResearchStore
from nbot.v5.science import Protocol, digest
from tests.test_v5_science import row, BASE
from tests.v5_linked_lab import laboratory_reviewer


class LearningLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.store=ResearchStore(Path(self.temp.name)/"continuous_research.sqlite")
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.store.close)
        self.protocol=Protocol(BASE-1,BASE,BASE+5000*3600000)
        self.now=BASE+4500*3600000

    def populate(self, count=2200, change=None):
        for i in range(count):
            item=row(i)
            if change:
                change(item)
                item["row_sha256"]=digest({k:v for k,v in item.items() if k!="row_sha256"})
            self.store.append("qualified:"+item["label_id"],"QUALIFIED_OUTCOME",item["settled_ms"],{"row":item})

    def lifecycle(self, reviewer=laboratory_reviewer):
        return LearningLifecycle(self.store,protocol=self.protocol,grade="SYNTHETIC",
                                 reviewer=reviewer,reviewer_key=b"s"*32)

    def test_two_thousand_rows_do_not_bypass_no_edge(self):
        self.populate(change=lambda r:r.update(net_r=-.3))
        result=self.lifecycle().advance(self.now,epochs=2)
        self.assertEqual(result["state"],"SCIENCE_HOLD")
        self.assertEqual(self.lifecycle()._approved(),[])

    def test_positive_edge_still_requires_independent_review(self):
        self.populate()
        result=self.lifecycle(reviewer=None).advance(self.now,epochs=2)
        self.assertEqual(result["state"],"AWAITING_G5_REVIEW")

    def test_mixed_grade_is_rejected_before_training(self):
        self.populate(count=2,change=lambda r:r.update(grade="ORIGINAL"))
        with self.assertRaisesRegex(ValueError,"MIXED_EVIDENCE_GRADE"):
            self.lifecycle().advance(self.now)

    def test_corrupted_dataset_rejected(self):
        item=row(0);item["net_r"]+=1
        self.store.append("qualified:"+item["label_id"],"QUALIFIED_OUTCOME",BASE,{"row":item})
        with self.assertRaisesRegex(ValueError,"ROW_TAMPER"):
            self.lifecycle().advance(self.now)

    def test_invalid_review_never_fits_or_registers_model(self):
        self.populate()
        with self.assertRaisesRegex(ValueError,"REVIEW_INVALID"):
            self.lifecycle(reviewer=lambda *args:{}).advance(self.now,epochs=2)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM research_journal WHERE kind='MODEL_CANDIDATE'").fetchone()[0],0)

    def test_insufficient_diversity_and_correlated_windows_hold(self):
        self.populate(change=lambda r:r.update(symbol="BTCUSDT",regime="RANGE",
                     decision_ms=BASE,feature_known_ms=BASE-1,event_ms=BASE-300000,
                     exit_ms=BASE+60000,settled_ms=BASE+61000))
        result=self.lifecycle().advance(self.now,epochs=2)
        for reason in ("COIN_DIVERSITY","REGIME_DIVERSITY","DEPENDENT_SAMPLE"):
            self.assertIn(reason,result["report"]["reasons"])
