"""Disposable synthetic fixtures only; zero real market-driven orders."""
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from nbot.v5.guarded_paper import *
from tests.test_v5_science import review, BASE

POLICY = {"capital": "10000", "risk_fraction": "0.005", "max_open_risk": "0.02",
          "max_exposure_multiple": "1", "max_positions": 2, "max_drawdown_fraction": "0.1",
          "min_lower_net_r": "0.1", "max_quote_age_ms": 1000, "max_message_age_ms": 5000}
MODELS = {BOOKS[0]: "a"*64, BOOKS[1]: "b"*64}
KEYS = {BOOKS[0]: b"c"*32, BOOKS[1]: b"d"*32}


def quote(at=BASE, bid="99.99", ask="100.01"):
    return {"symbol": "BTCUSDT", "bid": bid, "ask": ask, "at_ms": at,
            "source_verified": True, "grade": "SYNTHETIC", "receipt_sha256": "e"*64}


def economics():
    return {"grade": "SYNTHETIC", "independently_verified": True,
            "fee_receipt_sha256": "f"*64, "slippage_policy_sha256": "1"*64,
            "funding_receipt_sha256": "2"*64, "fee_rate": "0.0005", "slippage_rate": "0.0001",
            "funding_coverage_from_ms": BASE, "funding_coverage_to_ms": BASE+20000,
            "funding_quote": "0.03"}


def proposal(book=BOOKS[0], at=BASE, **changes):
    body = {"version": "NBOT_V5_PAPER_V2", "authority": "PAPER", "book": book,
            "model_sha256": MODELS[book], "decision_id": digest([book, at]),
            "at_ms": at, "expires_ms": at+5000, "side": "LONG", "symbol": "BTCUSDT",
            "risk_group": "BTC_CORRELATED", "stop": "95", "target": "110",
            "lower_net_r": "0.2", "source_quality_ok": True, "regime_gate_ok": True, **changes}
    return {"body": body, "signature": sign(body, KEYS[book])}


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/"guarded_paper.sqlite"
        self.engine = GuardedPaper(self.path, policy=POLICY, models=MODELS, keys=KEYS, reviewer_key=b"s"*32, synthetic=True)

    def tearDown(self):
        self.engine.store.close();self.temp.cleanup()

    def unlock(self):
        subject = digest({"models": MODELS, "policy": POLICY, "grade": "SYNTHETIC"})
        e=review(subject,"G7_PAPER_RELEASE",g5_accepted=True,g6_accepted=True,g7_accepted=True,
                 champion_qualified=True,challenger_qualified=True,grade="SYNTHETIC")
        self.engine.unlock(e,BASE)

    def submit(self,p=None,q=None,e=None,at=BASE):
        return self.engine.submit(p or proposal(),q or quote(),e or economics(),at)

    def test_default_locked_zero_fills(self):
        self.assertEqual(self.submit()["reason"],"G7_PAPER_LOCKED")
        self.assertTrue(all(x["fills"]==0 for x in self.engine.reconcile()["books"].values()))

    def test_release_requires_independent_gate_signature(self):
        with self.assertRaisesRegex(ValueError,"REVIEW"):
            self.engine.unlock({},BASE)

    def test_two_books_account_independently(self):
        self.unlock()
        a=self.submit();b=self.submit(proposal(BOOKS[1]))
        self.assertEqual(a["status"],"PAPER_FILLED");self.assertEqual(b["status"],"PAPER_FILLED")
        self.engine.exit(BOOKS[0],"BTCUSDT",quote(BASE+1000,"110","110.02"),economics(),BASE+1000)
        r=self.engine.reconcile()["books"]
        self.assertEqual(r[BOOKS[0]]["positions"],0)
        self.assertEqual(r[BOOKS[1]]["positions"],1)
        self.assertNotEqual(r[BOOKS[0]]["cash"],r[BOOKS[1]]["cash"])

    def test_exact_replay_idempotent(self):
        self.unlock();a=self.submit();b=self.submit()
        self.assertTrue(b["duplicate"])
        self.assertEqual(self.engine.reconcile()["books"][BOOKS[0]]["fills"],1)

    def test_same_decision_changed_body_rejected(self):
        self.unlock();self.submit()
        self.assertEqual(self.submit(proposal(target="111"))["reason"],"PAPER_REPLAY_DECISION")

    def test_invalid_signature_no_order(self):
        self.unlock();p=proposal();p["signature"]="0"*64
        self.assertEqual(self.submit(p)["reason"],"PAPER_AUTHENTICATION_FAILED")

    def test_wrong_model_rejected(self):
        self.unlock()
        self.assertEqual(self.submit(proposal(model_sha256="0"*64))["status"],"REJECTED")

    def test_authenticated_real_money_request_is_rejected_without_any_fill(self):
        self.unlock()
        self.assertEqual(self.submit(proposal(authority="REAL_MONEY"))["status"],"REJECTED")
        self.assertTrue(all(b["fills"]==0 for b in self.engine.reconcile()["books"].values()))

    def test_future_and_expired_message_no_order(self):
        self.unlock()
        for p in (proposal(at=BASE+1),proposal(expires_ms=BASE)):
            self.assertEqual(self.submit(p)["status"],"REJECTED")

    def test_stale_and_future_quote_rejected(self):
        self.unlock()
        self.assertEqual(self.submit(q=quote(BASE-1001))["status"],"REJECTED")

    def test_crossed_quote_rejected(self):
        self.unlock();self.assertEqual(self.submit(q=quote(bid="101",ask="100"))["status"],"REJECTED")

    def test_missing_cost_evidence_rejected(self):
        self.unlock();e=economics();del e["funding_receipt_sha256"]
        self.assertEqual(self.submit(e=e)["reason"],"PAPER_COST_PROOF_MISSING")

    def test_nonpositive_and_bad_source_abstain(self):
        self.unlock()
        for c in ({"lower_net_r":"0"},{"source_quality_ok":False},{"regime_gate_ok":False}):
            self.assertEqual(self.submit(proposal(**c))["status"],"REJECTED")

    def test_high_leverage_exposure_veto(self):
        self.unlock()
        self.assertEqual(self.submit(proposal(stop="99.999"))["reason"],"PAPER_EXPOSURE_VETO")

    def test_restart_locks_and_recovers_exact_book(self):
        self.unlock();self.submit();before=self.engine.reconcile()["books"]
        self.engine.store.close()
        self.engine=GuardedPaper(self.path,policy=POLICY,models=MODELS,keys=KEYS,reviewer_key=b"s"*32,synthetic=True)
        self.assertEqual(self.engine.reconcile()["books"],before)
        self.assertEqual(self.engine.reconcile()["paper_state"],"LOCKED")

    def test_exit_requires_settled_funding(self):
        self.unlock();self.submit();e=economics();e["funding_coverage_to_ms"]=BASE
        with self.assertRaisesRegex(ValueError,"FUNDING"):
            self.engine.exit(BOOKS[0],"BTCUSDT",quote(BASE+1000,"110","110.02"),e,BASE+1000)
        self.assertEqual(self.engine.reconcile()["books"][BOOKS[0]]["positions"],1)

    def test_stop_exit_costs_and_reconciliation(self):
        self.unlock();a=self.submit()
        closed=self.engine.exit(BOOKS[0],"BTCUSDT",quote(BASE+1000,"94.99","95.01"),economics(),BASE+1000)
        r=self.engine.reconcile()["books"][BOOKS[0]]
        self.assertEqual(closed["status"],"PAPER_SETTLED")
        self.assertLess(Decimal(r["realized"]),-50)
        self.assertEqual(r["fills"],2)

    def test_horizon_cannot_be_shrunk(self):
        self.unlock();self.submit()
        with self.assertRaisesRegex(ValueError,"HORIZON"):
            self.engine.exit(BOOKS[0],"BTCUSDT",quote(BASE+1),economics(),BASE+1,horizon_ms=1)

    def test_exit_cannot_rewind(self):
        self.unlock();self.submit()
        with self.assertRaisesRegex(ValueError,"FORWARD"):
            self.engine.exit(BOOKS[0],"BTCUSDT",quote(),economics(),BASE)

    def test_immutable_ledger_and_emergency_kill(self):
        self.unlock();self.engine.kill("SYNTHETIC_KILL",BASE)
        self.assertEqual(self.submit()["reason"],"G7_PAPER_LOCKED")
        with self.assertRaises(sqlite3.IntegrityError):
            self.engine.store.db.execute("DELETE FROM research_journal")

    def test_production_cannot_reopen_synthetic_database(self):
        with self.assertRaisesRegex(ValueError,"CONFLICT"):
            GuardedPaper(self.path,policy=POLICY)

    def test_release_expiry_locks_action(self):
        self.unlock()
        self.assertEqual(self.submit(proposal(at=BASE+10000),quote(BASE+10000),at=BASE+10000)["status"],"REJECTED")
