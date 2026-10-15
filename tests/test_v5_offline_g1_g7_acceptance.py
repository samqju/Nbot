"""G1-G7 offline engineering acceptance: isolated, synthetic, safety-locked.

Contract:
  * No Binance sockets, service management, real account, or production DB.
  * G1-G4 uses ONE original-format synthetic frozen 50-coin source fixture.
  * G5/G6 uses a DIFFERENT synthetic-outcome laboratory, never G4 training data.
  * G7 is signed SYNTHETIC-only paper simulation; restart returns LOCKED.
  * An accepted offline test is not scientific qualification or permission to run.
The separation is essential: the operational G4->independently reviewed
after-cost G5->G6->G7 handoff is not implemented end to end yet.
"""
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g4_source_binding import bind_from_frozen_observation_copy
from nbot.v5.science import (
    Protocol, dataset, evaluate, fit_candidate, infer, digest,
)
from nbot.v5.guarded_paper import (
    BOOKS, GuardedPaper, sign,
)
from nbot.v5.observation_contract import PATTERN_IDS
from tests.test_v5_continuous_research import (
    ContinuousIntegrationTests, COMMITTED, EVENT,
)
from tests.test_v5_science import BASE, row, review
from tests.test_v5_guarded_paper import POLICY, quote, economics


class OfflineFullLifecycleAcceptance(unittest.TestCase):
    """Tests what can genuinely be proven, not scientific market outcomes."""

    def test_one_frozen_50_coin_g1_to_g4_original_chain_g5_g6_g7_hold(self):
        x=ContinuousIntegrationTests(
            "test_complete_population_and_early_paths_never_fake_economics")
        x.setUp()
        try:
            self.assertEqual(len(PATTERN_IDS),24)
            frozen=x.source.read_bytes()
            bound=bind_from_frozen_observation_copy(
                db_path=x.source,event_open_ms=EVENT,
                symbol="BTCUSDT",side="LONG")
            self.assertEqual(bound.state,"SOURCE_BOUND")
            self.assertEqual(bound.eligible_population,50)
            self.assertEqual(bound.candidate_population,100)
            self.assertEqual(bound.scored_outcomes,0)
            result=x.engine.tick(COMMITTED+300)
            self.assertEqual(result["candidate_population"],100)
            self.assertEqual(result["g4_maturity"]["total_frozen_intents"],100)
            self.assertGreater(result["original_price_paths"],0)
            self.assertEqual(
                result["qualified_independently_reviewed_outcomes"],0)
            self.assertEqual(result["g5"]["qualified_outcomes"],0)
            self.assertIn("OUTCOMES_BELOW_2000",result["g5"]["reasons"])
            self.assertFalse(result["g5"]["scientifically_accepted"])
            self.assertEqual(result["g5"]["training_authority"],"NONE")
            self.assertEqual(result["g7_paper_state"],"LOCKED")
            self.assertEqual(result["real_money_authority"],"NONE")
            with self.assertRaisesRegex(ValueError,"G6_G5_SCIENCE_HOLD"):
                fit_candidate(
                    dataset(x.engine.verified_rows(),
                            cutoff_ms=COMMITTED+300,grade="ORIGINAL"),
                    boundary_ms=COMMITTED+300,protocol=x.kwargs["protocol"])
            self.assertEqual(frozen,x.source.read_bytes())
            self.assertEqual(
                x.engine.store.db.execute(
                    "SELECT COUNT(*) FROM research_journal "
                    "WHERE kind='QUALIFIED_OUTCOME'").fetchone()[0],0)
        finally:
            x.tearDown()

    def test_synthetic_2200_plus_2200_g5_g6_model_to_g7_books_and_restart(self):
        # This deliberately uses synthetic generated economic labels, *not*
        # the G1-G4 source above. No scientific or live data is manufactured.
        first=[row(i) for i in range(2200)]
        second=[row(i) for i in range(2200,4400)]
        self.assertFalse({r["label_id"] for r in first} &
                         {r["label_id"] for r in second})
        proto=Protocol(BASE-1,BASE,BASE+4500*3600000)
        d1=dataset(first,cutoff_ms=BASE+2200*3600000,grade="SYNTHETIC")
        d2=dataset(second,cutoff_ms=BASE+4400*3600000,grade="SYNTHETIC")
        g5=evaluate(d1,proto)
        g6_evidence=evaluate(d2,proto)
        for report in (g5,g6_evidence):
            self.assertEqual(report["qualified_outcomes"],2200)
            self.assertFalse(report["scientifically_accepted"])
            self.assertEqual(report["training_authority"],"NONE")
            self.assertEqual(report["paper_authority"],"NONE")
        champion=fit_candidate(
            d1,boundary_ms=BASE+1600*3600000,protocol=proto,
            synthetic=True,epochs=10)
        challenger=fit_candidate(
            d2,boundary_ms=BASE+3800*3600000,protocol=proto,
            synthetic=True,epochs=10)
        self.assertNotEqual(champion["model_sha256"],challenger["model_sha256"])
        for model,features in ((champion,first[-1]["features"]),
                               (challenger,second[-1]["features"])):
            prediction=infer(model,features)
            self.assertIn(prediction["action"],("REVIEW_ONLY","ABSTAIN"))
            self.assertEqual(prediction["paper_authority"],"NONE")
            self.assertFalse(model["trading_eligible"])
            self.assertEqual(
                model["status"],"CANDIDATE_REQUIRES_INDEPENDENT_HOLDOUT_REVIEW")
        models={BOOKS[0]:champion["model_sha256"],
                BOOKS[1]:challenger["model_sha256"]}
        keys={BOOKS[0]:b"c"*32,BOOKS[1]:b"d"*32}
        with TemporaryDirectory(prefix="nbot-v5-offline-acceptance-") as temp:
            path=Path(temp)/"synthetic_paper.sqlite"
            paper=GuardedPaper(path,policy=POLICY,models=models,keys=keys,
                               reviewer_key=b"s"*32,synthetic=True)
            try:
                self.assertEqual(paper.reconcile()["paper_state"],"LOCKED")
                subject=digest({"models":models,"policy":POLICY,
                                "grade":"SYNTHETIC"})
                # A synthetic reviewer signs *only* an isolated simulation.
                signed=review(
                    subject,"G7_PAPER_RELEASE",now=BASE,
                    g5_accepted=True,g6_accepted=True,g7_accepted=True,
                    champion_qualified=True,challenger_qualified=True,
                    grade="SYNTHETIC")
                paper.unlock(signed,BASE)
                for i,book in enumerate(BOOKS):
                    body={
                        "version":"NBOT_V5_PAPER_V2","authority":"PAPER",
                        "book":book,"model_sha256":models[book],
                        "decision_id":digest(["offline",i]),
                        "at_ms":BASE,"expires_ms":BASE+5000,
                        "side":"LONG","symbol":"BTCUSDT",
                        "risk_group":"BTC_CORRELATED","stop":"95",
                        "target":"110","lower_net_r":"0.2",
                        "source_quality_ok":True,"regime_gate_ok":True}
                    result=paper.submit(
                        {"body":body,"signature":sign(body,keys[book])},
                        quote(at=BASE),economics(),BASE)
                    self.assertEqual(result["status"],"PAPER_FILLED")
                books=paper.reconcile()["books"]
                self.assertEqual([books[b]["fills"] for b in BOOKS],[1,1])
            finally:
                paper.store.close()
            reopened=GuardedPaper(
                path,policy=POLICY,models=models,keys=keys,
                reviewer_key=b"s"*32,synthetic=True)
            try:
                self.assertEqual(reopened.reconcile()["paper_state"],"LOCKED")
                self.assertEqual(
                    [reopened.reconcile()["books"][b]["fills"] for b in BOOKS],
                    [1,1])
                with self.assertRaisesRegex(ValueError,"REVIEW"):
                    reopened.unlock({},BASE)
            finally:
                reopened.store.close()
            with self.assertRaisesRegex(ValueError,"CONFLICT"):
                GuardedPaper(path,policy=POLICY,synthetic=False)

    def test_no_cost_evidence_no_real_paper_release(self):
        x=ContinuousIntegrationTests(
            "test_complete_population_and_early_paths_never_fake_economics")
        x.setUp()
        try:
            x.engine.tick(COMMITTED+300)
            with self.assertRaisesRegex(ValueError,"REVIEW"):
                x.engine.accept_verified_export(
                    {"rows":[]},review={},reviewer_key=None,
                    now_ms=COMMITTED+300)
            self.assertEqual(x.engine.telemetry(COMMITTED+300)[
                "qualified_independently_reviewed_outcomes"],0)
            with TemporaryDirectory(
                    prefix="nbot-v5-real-grade-denial-") as tmp:
                locked=GuardedPaper(Path(tmp)/"locked.sqlite",
                                    policy=POLICY)
                try:
                    self.assertEqual(locked.reconcile()["paper_state"],"LOCKED")
                    with self.assertRaisesRegex(ValueError,
                                                "TWO_QUALIFIED_MODELS_REQUIRED"):
                        locked.unlock({},COMMITTED)
                finally:
                    locked.store.close()
        finally:
            x.tearDown()

    def test_negative_2200_synthetic_results_never_grant_model_promotion(self):
        losses=[row(i) for i in range(2200)]
        for item in losses:
            item["net_r"]=-0.3
            item["row_sha256"]=digest(
                {k:v for k,v in item.items() if k!="row_sha256"})
        d=dataset(losses,cutoff_ms=BASE+2200*3600000,grade="SYNTHETIC")
        report=evaluate(d,Protocol(BASE-1,BASE,BASE+2300*3600000))
        self.assertEqual(report["qualified_outcomes"],2200)
        self.assertIn("NO_DEMONSTRABLE_POSITIVE_EDGE",report["reasons"])
        self.assertFalse(report["scientifically_accepted"])
        self.assertEqual(report["paper_authority"],"NONE")


if __name__=="__main__":
    unittest.main()
