"""Roadmap Champion-first stage requires explicit synthetic signed release."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.guarded_paper import GuardedPaper, BOOKS
from nbot.v5.science import digest
from tests.test_v5_guarded_paper import POLICY, MODELS, KEYS, proposal, quote, economics
from tests.test_v5_science import review, BASE


class ReleaseStagesTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.path=Path(self.temp.name)/"guarded_paper.sqlite"
        self.models={BOOKS[0]:MODELS[BOOKS[0]]}
        self.keys={BOOKS[0]:KEYS[BOOKS[0]]}
        self.kwargs=dict(policy=POLICY,models=self.models,keys=self.keys,
                         reviewer_key=b"s"*32,synthetic=True)
        self.paper=GuardedPaper(self.path,**self.kwargs)

    def tearDown(self):
        self.paper.store.close()
        self.temp.cleanup()

    def release(self, **changes):
        flags=dict(release_stage="CHAMPION_ONLY",grade="SYNTHETIC",
                   g5_accepted=True,g7_accepted=True,champion_qualified=True,
                   owner_paper_authorized=True,g6_champion_validation_accepted=True)
        flags.update(changes)
        return review(digest({"models":self.models,"policy":POLICY,"grade":"SYNTHETIC"}),
                      "G7_PAPER_RELEASE",**flags)

    def test_champion_first_and_challenger_rejected(self):
        self.paper.unlock(self.release(),BASE)
        self.assertEqual(self.paper.submit(proposal(),quote(),economics(),BASE)["status"],"PAPER_FILLED")
        self.assertEqual(self.paper.submit(proposal(BOOKS[1]),quote(),economics(),BASE)["status"],"REJECTED")
        state=self.paper.reconcile()["books"]
        self.assertEqual(state[BOOKS[0]]["fills"],1)
        self.assertEqual(state[BOOKS[1]]["fills"],0)

    def test_omitted_owner_or_validation_flag_remains_locked(self):
        for field in ("owner_paper_authorized","g6_champion_validation_accepted"):
            with self.assertRaisesRegex(ValueError,"SCIENTIFIC_GATES_LOCKED"):
                self.paper.unlock(self.release(**{field:False}),BASE)
        self.assertEqual(self.paper.reconcile()["paper_state"],"LOCKED")

    def test_comparison_cannot_fall_back_to_one_model(self):
        with self.assertRaisesRegex(ValueError,"TWO_QUALIFIED_MODELS_REQUIRED"):
            self.paper.unlock(self.release(release_stage="COMPARISON"),BASE)

    def test_revocation_is_durable_and_restart_reconciles_open_position(self):
        self.paper.unlock(self.release(),BASE)
        self.paper.submit(proposal(),quote(),economics(),BASE)
        model=self.models[BOOKS[0]]
        revoked=review(model,"G7_MODEL_REVOCATION",grade="SYNTHETIC")
        self.paper.revoke_model(model,revoked,BASE)
        self.paper.store.close()
        self.paper=GuardedPaper(self.path,**self.kwargs)
        self.assertEqual(self.paper.reconcile()["books"][BOOKS[0]]["positions"],1)
        with self.assertRaisesRegex(ValueError,"MODEL_INVALID_OR_REVOKED"):
            self.paper.unlock(self.release(),BASE)
        self.assertEqual(self.paper.reconcile()["paper_state"],"LOCKED")
