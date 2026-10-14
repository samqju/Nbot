"""Integrated V5 G1-G3 production safety and restart regression."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import Mock

from nbot.v5.g1f_runner import ObservationOnlyRunner
from nbot.v5.g3_context_ledger import G3ContextLedger, G3LedgerHold
from nbot.v5.g3_prod_preflight import verify
from nbot.v5.g3_prod_health import audit
from tests.test_v5_g3_frozen_replay import G3FrozenSourceTests


class IntegratedLedgerTests(unittest.TestCase):
    setUp=G3FrozenSourceTests.setUp
    write_event=G3FrozenSourceTests.write_event
    report=G3FrozenSourceTests.report

    def test_two_real_source_events_produce_immutable_g3_context_rows(self):
        journal=G3ContextLedger(self.db)
        first=journal.record(event_open_ms=self.first,symbols=self.symbols)
        second=journal.record(event_open_ms=self.next,symbols=self.symbols)
        self.assertEqual(first["status"],"OBSERVE_ONLY")
        self.assertEqual(second["status"],"OBSERVE_ONLY")
        self.assertFalse(first["idempotent"])
        self.assertTrue(journal.record(event_open_ms=self.first,symbols=self.symbols)["idempotent"])
        rows=self.db.execute("SELECT event_open_ms,payload_sha,payload_json "
                             "FROM g3_event_context").fetchall()
        self.assertEqual(len(rows),2)
        for when,sha,raw in rows:
            self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),sha)
            parsed=json.loads(raw)
            self.assertEqual(parsed["order_authority"],"NONE")
            self.assertEqual(parsed["training_labels_created"],0)
            self.assertEqual(parsed["status"],"OBSERVE_ONLY")
            self.assertEqual(len(parsed["feature_evidence"]["coins"]),len(self.symbols))

    def test_g3_context_missing_original_source_cannot_synthesize_context(self):
        self.db.execute("DROP TRIGGER g2_quote_immutable_d")
        self.db.execute("DELETE FROM g2_quote_witness WHERE event_open_ms=?",
                        (self.next,))
        self.db.commit()
        with self.assertRaisesRegex(G3LedgerHold,"SOURCE_REPLAY"):
            G3ContextLedger(self.db).record(event_open_ms=self.next,symbols=self.symbols)

    def test_g3_context_table_immutable(self):
        G3ContextLedger(self.db).record(event_open_ms=self.first,symbols=self.symbols)
        with self.assertRaisesRegex(Exception,"G3_IMMUTABLE"):
            self.db.execute("DELETE FROM g3_event_context")
        self.db.rollback()

    def test_held_g2_events_are_recorded_unknown_never_classified(self):
        self.db.execute("DROP TRIGGER g1f_manifest_no_update")
        rec=self.db.execute(
            "SELECT verification_json FROM g1f_event_manifest WHERE event_open_ms=?",
            (self.next,)
        ).fetchone()[0]
        from nbot.v5.g1f_journal import canonical,digest
        payload=json.loads(rec)
        payload["status"]="HOLD"
        self.db.execute("UPDATE g1f_event_manifest "
                        "SET state=?, verification_json=?, verification_sha=? "
                        "WHERE event_open_ms=?",
                        ("HOLD",canonical(payload),digest(payload),self.next))
        self.db.commit()
        result=G3ContextLedger(self.db).record(
            event_open_ms=self.next,symbols=self.symbols)
        self.assertEqual(result["status"],"HOLD")
        actual=json.loads(self.db.execute(
            "SELECT payload_json FROM g3_event_context WHERE event_open_ms=?",
            (self.next,)).fetchone()[0])
        self.assertIsNone(actual["feature_evidence"])
        self.assertIn("G2_EVENT_HELD",actual["reasons"])


class ProductionGuardsTests(unittest.TestCase):
    def test_g3_mode_requires_original_g2(self):
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"REQUIRES_G2"):
                ObservationOnlyRunner(
                    top=50,path=Path(temp)/"data.sqlite",max_seconds=0,
                    g3_context=True,g2_source_witness=False)

    def test_original_legacy_v5_mode_remains_disabled_for_g3(self):
        with TemporaryDirectory() as temp:
            runner=ObservationOnlyRunner(
                top=50,path=Path(temp)/"data.sqlite",max_seconds=0)
            self.assertFalse(runner.g2_source_witness)
            self.assertFalse(runner.g3_context)

    def test_production_preflight_rejects_unapproved_git_head(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"code"
            (root/"nbot/v5").mkdir(parents=True)
            (root/"nbot/v5/g3_market_context.py").write_text("x")
            data=Path(tmp)/"data"
            data.mkdir()
            approval=data/"approved.txt"
            approval.write_text("a"*40)
            def fake(cmd,**kwargs):
                if cmd[0]=="git":
                    return types.SimpleNamespace(returncode=0,
                      stdout="b"*40+"\n" if "rev-parse" in cmd else "")
                return types.SimpleNamespace(returncode=3,stdout="inactive\n")
            errors=verify(repo=str(root),approved_sha_file=str(approval),
                          data_dir=str(data),hostname="base",runner=fake)
            self.assertIn("PRODUCTION_CODE_NOT_PINNED_CLEAN",errors)

    def test_integrated_health_refuses_other_systemd_service(self):
        with self.assertRaisesRegex(Exception,"UNKNOWN_PRODUCTION_SERVICE"):
            audit(db_path="/tmp/not-real.sqlite",service="nbot-execution-live-paper.service")


if __name__=="__main__":
    unittest.main()
