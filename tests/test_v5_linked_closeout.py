"""Single source-generated G1->G7 synthetic lifecycle, never genuine science."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.continuous_research import ContinuousResearch
from nbot.v5.g4_prospective_policy import freeze_template, ENTRY_CONVENTION, EXIT_POLICY_ID, RISK_POLICY_ID, COST_POLICY_ID
from nbot.v5.guarded_paper import GuardedPaper, BOOKS, sign
from nbot.v5.learning_lifecycle import LearningLifecycle
from nbot.v5.science import Protocol, digest
from tests.test_v5_g4_source_binding import EVENT
from tests.test_v5_science import review
from tests.test_v5_guarded_paper import POLICY, quote, economics
from tests.v5_linked_lab import build_lab, laboratory_reviewer


def registry(root):
    spec={"declared_at_ms":EVENT-600000,"activates_at_ms":EVENT-300000,"horizon_ms":14400000,
          "max_quote_age_ms":1000,"atr_risk_multiple":"1.5","target_r_multiple":"2.0",
          "min_risk_fraction":"0.005","entry_convention":ENTRY_CONVENTION,"exit_policy_id":EXIT_POLICY_ID,
          "risk_policy_id":RISK_POLICY_ID,"cost_policy_id":COST_POLICY_ID,"research_authority":"OBSERVE_ONLY"}
    template=freeze_template(spec)
    path=root/"policy.json"
    path.write_text(json.dumps({"registry_version":"NBOT_V5_G4_PREDECLARED_POLICY_REGISTRY_V1",
                               "research_only":True,"financial_authority":"NONE","spec":spec,
                               "policy_sha256":template.policy_sha256}))
    return path


class LinkedCloseoutAcceptance(unittest.TestCase):
    def test_raw_synthetic_patterns_to_6000_net_outcomes_to_reviewed_models_to_paper(self):
        with TemporaryDirectory(prefix="nbot-v5-linked-synthetic-") as temp:
            root=Path(temp)
            source,segments,provider,regimes,archive=build_lab(root)
            self.assertGreaterEqual(len(regimes),3)
            source_before=source.read_bytes()
            private=root/"research"; private.mkdir(mode=0o700)
            now=EVENT+61*8*3600000
            protocol=Protocol(EVENT-1,EVENT,now)
            kwargs=dict(source=source,vault=segments,registry=registry(root),root=private,
                        protocol=protocol,start_event_ms=EVENT,grade="SYNTHETIC",
                        economic_provider=provider,reviewer_key=b"s"*32)
            engine=ContinuousResearch(**kwargs)
            try:
                # Full 100-side events go through the same durable processing
                # queues. No row or prequalified G5 dataset is injected here.
                for _ in range(12):
                    result=engine.tick(now,max_events=3)
                self.assertEqual(result["g5"]["qualified_outcomes"],3000)
                engine.learning=LearningLifecycle(engine.store,protocol=protocol,grade="SYNTHETIC",
                                                  reviewer=laboratory_reviewer,reviewer_key=b"s"*32)
                first=engine.learning.advance(now,epochs=30)
                self.assertEqual(first["state"],"REVIEWED_CHAMPION")
                for _ in range(12):
                    result=engine.tick(now,max_events=3)
                state=engine.learning.advance(now,epochs=30)
                self.assertEqual(state["state"],"TWO_REVIEWED_ARTIFACTS")
                self.assertEqual(result["candidate_population"],6000)
                rows=engine.verified_rows()
                self.assertEqual(len(rows),6000)
                self.assertEqual({r["grade"] for r in rows},{"SYNTHETIC"})
                self.assertFalse(result["g5"]["scientifically_accepted"])
                self.assertEqual(engine.store.db.execute(
                    "SELECT COUNT(*) FROM research_journal WHERE kind='MODEL_PROMOTE'").fetchone()[0],0)
                self.assertEqual(source.read_bytes(),source_before)
                models={BOOKS[0]:state["models"]["CHAMPION"],BOOKS[1]:state["models"]["CHALLENGER"]}
                self.assertNotEqual(*models.values())
                role_records=engine.learning._approved()
                self.assertLess(role_records[0]["max_settled_ms"],
                                min(r["decision_ms"] for r in rows if r["decision_ms"]>role_records[0]["max_settled_ms"]+protocol.embargo_ms))
            finally:
                engine.close()
            keys={BOOKS[0]:b"c"*32,BOOKS[1]:b"d"*32}
            path=root/"guarded_paper.sqlite"
            paper=GuardedPaper(path,policy=POLICY,models=models,keys=keys,reviewer_key=b"s"*32,synthetic=True)
            subject=digest({"models":models,"policy":POLICY,"grade":"SYNTHETIC"})
            paper.unlock(review(subject,"G7_PAPER_RELEASE",now=now,grade="SYNTHETIC",
                                g5_accepted=True,g6_accepted=True,g7_accepted=True,
                                champion_qualified=True,challenger_qualified=True),now)
            try:
                for book in BOOKS:
                    body={"version":"NBOT_V5_PAPER_V2","authority":"PAPER","book":book,
                          "model_sha256":models[book],"decision_id":digest([book,"linked-source"]),
                          "at_ms":now,"expires_ms":now+5000,"side":"LONG","symbol":"BTCUSDT",
                          "risk_group":"BTC","stop":"95","target":"110","lower_net_r":"0.2",
                          "source_quality_ok":True,"regime_gate_ok":True}
                    self.assertEqual(paper.submit({"body":body,"signature":sign(body,keys[book])},
                                                  quote(at=now),economics(),now)["status"],"PAPER_FILLED")
                before=paper.reconcile()["books"]
            finally:
                paper.store.close()
            paper=GuardedPaper(path,policy=POLICY,models=models,keys=keys,reviewer_key=b"s"*32,synthetic=True)
            try:
                self.assertEqual(paper.reconcile()["paper_state"],"LOCKED")
                self.assertEqual(paper.reconcile()["books"],before)
                costs=economics()
                costs.update(funding_coverage_from_ms=now,funding_coverage_to_ms=now+1000)
                for book in BOOKS:
                    self.assertEqual(paper.exit(book,"BTCUSDT",quote(now+1000,"110","110.02"),
                                                costs,now+1000)["status"],"PAPER_SETTLED")
                self.assertTrue(all(b["positions"]==0 for b in paper.reconcile()["books"].values()))
            finally:
                paper.store.close()
