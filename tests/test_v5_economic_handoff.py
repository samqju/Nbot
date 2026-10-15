"""Source-linked synthetic economics; no prequalified downstream rows."""
import copy
import json
import unittest
from unittest.mock import patch

from nbot.v5.continuous_research import ContinuousResearch
from nbot.v5.science import digest
from tests import test_v5_continuous_research as fixture
from tests.test_v5_science import review


def evidence(population, intent, path, now_ms):
    at = intent["decision_at_ms"]
    end = path["exit_at_ms"]
    package = {
        "grade": "SYNTHETIC", "label_id": intent["label_id"],
        "candidate_sha256": digest(population["candidate"]),
        "policy_sha256": intent["policy_sha256"], "path_sha256": digest(path),
        "entry_quote": {"symbol": intent["symbol"], "sampled_at_ms": at-100,
                        "receipt_sha256": population["admission"]["original_entry_quote_sha256"],
                        "source_verified": True, "bid": "100.0", "ask": "100.1"},
        "exit_quote": {"symbol": intent["symbol"], "sampled_at_ms": end,
                       "receipt_sha256": digest(["synthetic-exit", end]),
                       "source_verified": True, "bid": "104.9", "ask": "105.1"},
        "economic_witness": {
            "source_grade": "SYNTHETIC_QUOTE_FEE_FUNDING_WITNESSES",
            **{k: digest(["synthetic", k]) for k in (
                "quote_source_sha256", "fee_source_sha256", "slippage_policy_sha256", "funding_source_sha256")},
            "independently_source_verified": True, "max_quote_age_ms": 1000,
            "taker_fee_rate": "0.0005", "slippage_rate": "0.0001",
            "funding_quote_per_unit": "0.01", "funding_coverage_from_ms": at,
            "funding_coverage_through_ms": end, "settled_at_ms": end+1,
            "fee_valid_from_ms": at-1000, "fee_valid_to_ms": end+1000,
            "slippage_declared_at_ms": at-1000}}
    return package, review(digest(package), "G4_ECONOMIC_EVIDENCE", now=now_ms, grade="SYNTHETIC")


class EconomicHandoffTests(unittest.TestCase):
    def setUp(self):
        self.x = fixture.ContinuousIntegrationTests(
            "test_complete_population_and_early_paths_never_fake_economics")
        self.x.setUp()
        self.x.engine.close()
        self.x.kwargs.update(grade="SYNTHETIC", economic_provider=evidence, reviewer_key=b"s"*32)
        # The fixture has not run a tick. The original-grade constructor wrote
        # its grade marker, so create a DIFFERENT disposable laboratory root.
        self.x.root = self.x.base / "synthetic-laboratory"
        self.x.root.mkdir(mode=0o700)
        self.x.kwargs["root"] = self.x.root
        self.x.engine = ContinuousResearch(**self.x.kwargs)

    def tearDown(self):
        self.x.tearDown()

    def test_automatic_source_to_net_economics_to_g5_and_duplicate(self):
        before = self.x.source.read_bytes()
        result = self.x.engine.tick(fixture.COMMITTED+300)
        self.assertEqual(result["g5"]["qualified_outcomes"], 2)
        rows = self.x.engine.verified_rows()
        self.assertEqual({r["grade"] for r in rows}, {"SYNTHETIC"})
        long = next(r for r in rows if r["side"] == "LONG")
        short = next(r for r in rows if r["side"] == "SHORT")
        self.assertGreater(long["net_r"], 0)
        self.assertLess(short["net_r"], 0)
        self.assertTrue(all(r["net_r"] < r["gross_r"] for r in rows))
        self.x.engine.tick(fixture.COMMITTED+400)
        self.assertEqual(len(self.x.engine.verified_rows()), 2)
        self.assertEqual(before, self.x.source.read_bytes())
        self.assertEqual(result["g7_paper_state"], "LOCKED")

    def test_cost_deficiencies_hold_then_delayed_evidence_recovers(self):
        for field, value in (("funding_quote_per_unit", None),
                             ("funding_coverage_from_ms", fixture.COMMITTED+1),
                             ("fee_valid_to_ms", fixture.COMMITTED-1),
                             ("slippage_declared_at_ms", fixture.COMMITTED+1)):
            def broken(pop, intent, path, now):
                package, _ = evidence(pop, intent, path, now)
                package["economic_witness"][field] = value
                return package, review(digest(package), "G4_ECONOMIC_EVIDENCE", now=now, grade="SYNTHETIC")
            self.x.engine.economic_provider = broken
            self.x.engine.tick(fixture.COMMITTED+300)
            self.assertEqual(self.x.engine.verified_rows(), [])
        self.x.engine.economic_provider = evidence
        self.x.engine.tick(fixture.COMMITTED+400)
        self.assertEqual(len(self.x.engine.verified_rows()), 2)

    def test_wrong_grade_and_bad_review_never_create_outcomes(self):
        def wrong_grade(pop, intent, path, now):
            package, _ = evidence(pop, intent, path, now)
            package["grade"] = "ORIGINAL"
            return package, review(digest(package), "G4_ECONOMIC_EVIDENCE", now=now, grade="ORIGINAL")
        self.x.engine.economic_provider = wrong_grade
        self.x.engine.tick(fixture.COMMITTED+300)
        self.assertEqual(self.x.engine.verified_rows(), [])
        self.x.engine.economic_provider = lambda *args: (evidence(*args)[0], {})
        self.x.engine.tick(fixture.COMMITTED+400)
        self.assertEqual(self.x.engine.verified_rows(), [])

    def test_crash_after_terminal_before_handoff_recovers_once(self):
        engine = self.x.engine
        original = engine.store.append
        def crash(identity, kind, at, body):
            if kind == "QUALIFIED_OUTCOME":
                raise OSError("SYNTHETIC_CRASH_BEFORE_ACK")
            return original(identity, kind, at, body)
        with patch.object(engine.store, "append", side_effect=crash):
            with self.assertRaisesRegex(OSError, "CRASH_BEFORE_ACK"):
                engine.tick(fixture.COMMITTED+300)
        engine.close()
        self.x.engine = ContinuousResearch(**self.x.kwargs)
        self.x.engine.tick(fixture.COMMITTED+300)
        self.assertEqual(len(self.x.engine.verified_rows()), 2)
        self.assertEqual(self.x.engine.labels.execute(
            "SELECT COUNT(*) FROM g4_label_terminals WHERE terminal_status='SCORED'").fetchone()[0], 2)

    def test_synthetic_journal_cannot_reopen_as_original(self):
        self.x.engine.close()
        kwargs = dict(self.x.kwargs, grade="ORIGINAL")
        with self.assertRaisesRegex(ValueError, "IDENTITY_CONFLICT"):
            ContinuousResearch(**kwargs)
        self.x.engine = ContinuousResearch(**self.x.kwargs)
