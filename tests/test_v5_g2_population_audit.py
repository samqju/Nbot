"""G2 full-denominator candidate audit regression; synthetic, no order service."""
from pathlib import Path
import hashlib
import json
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g1f_journal import CandidateJournal, canonical, digest
from nbot.v5.g2_population_audit import audit_population, PopulationHold
from nbot.v5.observation_contract import SCHEMA_VERSION, INTERVAL_MS, PATTERN_IDS, SIDES


class G2PopulationAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"g2_synthetic.sqlite"
        self.first=INTERVAL_MS*1234
        self.symbols=("BTCUSDT","ETHUSDT")
        self.db=sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        CandidateJournal(self.db)
        self.cohort=CandidateJournal(self.db).begin_cohort(
            self.symbols,selected_ms=self.first-500,
            event_open_ms=self.first,
        )
        self.add_event(self.first)

    def add_event(self,event, *,held=False,gap=False,selected=None):
        selected=set(self.symbols if selected is None else selected)
        states={}
        records=[]
        for symbol in self.symbols:
            for side in SIDES:
                status="UNSCORABLE" if held else "OBSERVED"
                rec={
                    "schema_version":SCHEMA_VERSION,
                    "event_open_ms":event,
                    "decision_at_ms":event+INTERVAL_MS+1000,
                    "symbol":symbol,"side":side,
                    "status":status,
                    "reason_codes":["QUOTES_STALE"] if held else [],
                    "action":"OBSERVE_ONLY","order_authority":"NONE",
                    "patterns":{p:"UNAVAILABLE" if held else "NO_MATCH" for p in PATTERN_IDS}
                }
                rec["decision_id"]=digest({
                    "schema":SCHEMA_VERSION,"event_open_ms":event,
                    "symbol":symbol,"side":side,
                })
                if symbol in selected:
                    records.append(rec)
        summary={
            "cohort_digest":self.cohort,
            "event_open_ms":event,
            "status":"HOLD" if held else "OBSERVE_ONLY",
            "observed":0 if held else 4,
            "unscorable":4 if held else 0,
            "btc_valid":True,"coverage_valid":True,"gap":gap,
            "research_ready":False,"training_labels_created":0,
            "order_authority":"NONE",
        }
        with self.db:
            self.db.execute(
                "INSERT INTO g1f_event_manifest VALUES (?,?,?,?,?,?)",
                (event,self.cohort,event+INTERVAL_MS+1000,
                 summary["status"],canonical(summary),digest(summary)),
            )
            for r in records:
                raw=canonical(r)
                self.db.execute(
                    "INSERT INTO g1f_candidate_events VALUES (?,?,?,?,?,?,?)",
                    (r["decision_id"],event,r["symbol"],r["side"],
                     r["status"],hashlib.sha256(raw.encode()).hexdigest(),raw),
                )

    def inspect(self):
        return audit_population(self.path,now_ms=self.first+10*INTERVAL_MS)

    def test_two_sided_coverage_proofs_and_no_model_authority(self):
        out=self.inspect()
        self.assertEqual(out["audit"],"PASS")
        self.assertEqual(out["expected_directional_records"],4)
        self.assertEqual(out["observed_directional_records"],4)
        self.assertEqual(out["training_labels_created"],0)
        self.assertFalse(out["research_ready"])
        self.assertEqual(out["recommendation_authority"],"NONE")

    def test_accounted_partial_health_hold_stays_denominator_visible(self):
        self.add_event(self.first+INTERVAL_MS,held=True)
        out=self.inspect()
        self.assertEqual(out["audit"],"PASS")
        self.assertEqual(out["held_events"],1)
        self.assertEqual(out["unscorable_directional_records"],4)
        self.assertEqual(out["unscorable_reasons"]["QUOTES_STALE"],4)

    def test_one_initial_rest_bootstrap_slot_is_explicit_not_hidden(self):
        self.db.execute("DROP TRIGGER g1f_cohort_no_update")
        self.db.execute("UPDATE g1f_universe_snapshots SET first_event_open_ms=?",
                        (self.first - INTERVAL_MS,))
        self.db.commit()
        out=self.inspect()
        self.assertEqual(out["audit"],"PASS")
        self.assertEqual(out["cohort_bootstrap_offset_slots"],1)

    def test_more_than_one_initial_unobserved_slot_is_hold(self):
        self.db.execute("DROP TRIGGER g1f_cohort_no_update")
        self.db.execute("UPDATE g1f_universe_snapshots SET first_event_open_ms=?",
                        (self.first - 2*INTERVAL_MS,))
        self.db.commit()
        self.assertIn("COHORT_FIRST_OBSERVATION_INVALID",self.inspect()["violations"])

    def test_missing_symbol_direction_fails(self):
        self.add_event(self.first+INTERVAL_MS,selected={"BTCUSDT"})
        self.assertIn("CANDIDATE_DENOMINATOR_MISSING",self.inspect()["violations"])

    def test_event_gap_requires_manifest_gap_proof(self):
        self.add_event(self.first+2*INTERVAL_MS)
        self.assertIn("UNDECLARED_EVENT_GAP",self.inspect()["violations"])

    def test_explicit_gap_reported_without_manufactured_records(self):
        self.add_event(self.first+3*INTERVAL_MS,held=True,gap=True)
        out=self.inspect()
        self.assertEqual(out["audit"],"PASS")
        self.assertEqual(out["unrepresented_time_slots"],2)
        self.assertEqual(out["explicit_event_gaps"],1)

    def test_changed_candidate_payload_fails_digest(self):
        self.db.execute("DROP TRIGGER g1f_candidate_no_update")
        self.db.execute(
            "UPDATE g1f_candidate_events SET record_sha='bad' "
            "WHERE symbol='BTCUSDT' AND direction='LONG'"
        )
        self.db.commit()
        self.assertIn("CANDIDATE_PROOF_INVALID",self.inspect()["violations"])

    def test_symlink_and_missing_file_refused(self):
        link=Path(self.tmp.name)/"redirect.sqlite"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(PopulationHold,"SYMLINK"):
            audit_population(link)
        with self.assertRaisesRegex(PopulationHold,"MISSING"):
            audit_population(Path(self.tmp.name)/"missing.sqlite")


if __name__=="__main__":
    unittest.main()
