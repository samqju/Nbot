"""Original-source / forward raw quote / prereg policy admission smoke tests.

All event and WSS data are synthetic here. No real virtual label assertions.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest

from nbot.v5.g4_real_entry_admission import admit_research_entry
from nbot.v5.g4_prospective_policy import (
    freeze_template,ENTRY_CONVENTION,EXIT_POLICY_ID,RISK_POLICY_ID,COST_POLICY_ID,
)
from nbot.v5.g4_forward_vault import ForwardSourceVault
from tests.test_v5_g4_source_binding import db_fixture,canonical,digest,EVENT,COMMITTED
from tests.test_v5_g4_forward_vault import quote


class OriginalG4EntryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.g1=self.path/"g1_review.sqlite"
        self.ws=self.path/"g4_ws.sqlite"
        self.policy=self.path/"g4_research_template.json"
        db_fixture(self.g1)
        with sqlite3.connect(self.g1) as db:
            raw=db.execute("SELECT payload_json FROM g3_event_context").fetchone()[0]
            g3=json.loads(raw)
            for symbol in g3["feature_evidence"]["coins"]:
                g3["feature_evidence"]["coins"][symbol]["features"]={
                    "atr14_fraction":0.01}
            f=g3["feature_evidence"]
            del f["feature_sha256"]
            f["feature_sha256"]=digest(f)
            db.execute("UPDATE g3_event_context SET payload_json=?,payload_sha=?",
                       (canonical(g3),digest(g3)))
            selected=json.loads(db.execute(
                "SELECT symbols_json FROM g1f_universe_snapshots").fetchone()[0])
        with sqlite3.connect(self.ws) as db:
            w=ForwardSourceVault(db,symbols=selected)
            w.connect(route="public_bookticker",at_ms=COMMITTED-1000)
            w.ingest(route="public_bookticker",at_ms=COMMITTED-100,
                     raw=quote(symbol="BTCUSDT",bid="100.0",ask="100.1",
                               at=COMMITTED-100))
        self.spec={
            "declared_at_ms":EVENT-600000,
            "activates_at_ms":EVENT-300000,
            "horizon_ms":4*3600000,
            "max_quote_age_ms":1000,
            "atr_risk_multiple":"1.5",
            "target_r_multiple":"2.0",
            "min_risk_fraction":"0.005",
            "entry_convention":ENTRY_CONVENTION,
            "exit_policy_id":EXIT_POLICY_ID,
            "risk_policy_id":RISK_POLICY_ID,
            "cost_policy_id":COST_POLICY_ID,
            "research_authority":"OBSERVE_ONLY",
        }
        self.register()

    def register(self):
        x=freeze_template(self.spec)
        self.policy.write_text(json.dumps({
            "registry_version":"NBOT_V5_G4_PREDECLARED_POLICY_REGISTRY_V1",
            "research_only":True,
            "financial_authority":"NONE",
            "policy_sha256":x.policy_sha256,
            "spec":self.spec,
        },sort_keys=True))

    def tearDown(self):
        self.tmp.cleanup()

    def run_admission(self,side="LONG"):
        return admit_research_entry(
            g1_snapshot=self.g1,raw_source_vault=self.ws,
            registry_file=self.policy,event_open_ms=EVENT,
            symbol="BTCUSDT",side=side)

    def test_source_bound_forward_bid_ask_geometry_only(self):
        result=self.run_admission()
        self.assertEqual(result.state,"REFERENCE_GEOMETRY_RECORDED")
        self.assertEqual(result.policy_geometry["entry_reference_price"],"100.1")
        self.assertEqual(result.policy_geometry["stop_price"],"98.5985")
        self.assertEqual(result.policy_geometry["target_price"],"103.10300")
        self.assertEqual(result.original_entry_quote_sha256 and
                         len(result.original_entry_quote_sha256),64)
        self.assertEqual(result.qualified_economic_outcomes,0)
        self.assertFalse(result.funded_cost_proof)
        self.assertEqual(result.order_authority,"NONE")

    def test_short_uses_bid_reference_not_fake_execution(self):
        result=self.run_admission("SHORT")
        self.assertEqual(result.state,"REFERENCE_GEOMETRY_RECORDED")
        self.assertEqual(result.policy_geometry["entry_reference_price"],"100.0")
        self.assertEqual(result.order_authority,"NONE")

    def test_preactivation_never_joins_old_event(self):
        self.spec["activates_at_ms"]=EVENT+300000
        self.register()
        result=self.run_admission()
        self.assertIn("PREACTIVATION_EVENT_NOT_ELIGIBLE",result.reasons)
        self.assertEqual(result.qualified_economic_outcomes,0)

    def test_policy_cannot_be_changed_after_registration(self):
        saved=json.loads(self.policy.read_text())
        saved["spec"]["target_r_multiple"]="3.0"
        self.policy.write_text(json.dumps(saved))
        result=self.run_admission()
        self.assertIn("POLICY_REGISTRY_SHA_MISMATCH",result.reasons)

    def test_without_real_forward_quote_source_must_hold(self):
        with sqlite3.connect(self.ws) as db:
            db.execute("DROP TRIGGER g4_forward_receipts_no_update")
            db.execute("UPDATE g4_forward_receipts SET at_ms=? WHERE kind='FRAME'",
                       (COMMITTED-15000,))
        result=self.run_admission()
        self.assertNotEqual(result.state,"REFERENCE_GEOMETRY_RECORDED")
        self.assertEqual(result.qualified_economic_outcomes,0)

    def test_no_actual_source_mutation_by_admission(self):
        before=(hashlib.sha256(self.g1.read_bytes()).hexdigest(),
                hashlib.sha256(self.ws.read_bytes()).hexdigest(),
                hashlib.sha256(self.policy.read_bytes()).hexdigest())
        self.run_admission()
        after=(hashlib.sha256(self.g1.read_bytes()).hexdigest(),
               hashlib.sha256(self.ws.read_bytes()).hexdigest(),
               hashlib.sha256(self.policy.read_bytes()).hexdigest())
        self.assertEqual(before,after)

if __name__=="__main__":
    unittest.main()
