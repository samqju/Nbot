"""Early stop/target maturity requires original bounded path and costs."""
import hashlib
import json
import sqlite3
import unittest
from nbot.v5.g4_price_path import replay_aggtrade_price_path
from nbot.v5.g4_research_ledger import *
from tests.test_v5_g4_price_path import make,DECISION,MATURITY
from tests.test_v5_g4_research_ledger import fixtures,terminal


class EarlyMaturityTests(unittest.TestCase):
    def replay(self, prices=None):
        c,p,r,m=make()
        r=r[:5]
        if prices:
            for raw,price in zip(r,prices):raw["p"]=price
        m["last_agg_id"]=r[-1]["a"]
        m["rows_sha256"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        return replay_aggtrade_price_path(candidate=c,policy=p,original_rows=r,source_manifest=m,audit_at_ms=DECISION+250,allow_early_exit=True)

    def test_target_can_mature_before_four_hour_horizon(self):
        x=self.replay();self.assertEqual(x.state,"PATH_REPLAYED")
        self.assertEqual(x.exit_at_ms,DECISION+200)
        self.assertEqual(x.scored_outcomes,0)

    def test_unresolved_path_stays_pending(self):
        self.assertEqual(self.replay(["99","100","100","101","102"]).state,"PENDING")

    def test_early_terminal_requires_path_proof(self):
        db=sqlite3.connect(":memory:");init_offline_ledger(db)
        c,p=fixtures();key=freeze_label_intent(db,c,p)
        t=terminal();t.update(settled_at_ms=DECISION+300,exit_reason="TARGET_PRICE_CROSSED",exit_at_ms=DECISION+200)
        with self.assertRaisesRegex(ValueError,"PREMATURE"):append_terminal(db,key,t)
        t["early_exit_source_proof_sha256"]="4"*64
        self.assertTrue(append_terminal(db,key,t));db.close()

    def test_horizon_cannot_use_early_exception(self):
        db=sqlite3.connect(":memory:");init_offline_ledger(db)
        c,p=fixtures();key=freeze_label_intent(db,c,p)
        t=terminal();t.update(settled_at_ms=DECISION+300,exit_reason="HORIZON_LAST_TRADE",exit_at_ms=DECISION+200,early_exit_source_proof_sha256="4"*64)
        with self.assertRaisesRegex(ValueError,"PREMATURE"):append_terminal(db,key,t)
        db.close()
