"""Synthetic-only complete 50-coin source-binding tests, no live DB."""
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from nbot.v5.g4_source_binding import bind_from_frozen_observation_copy
from nbot.v5.observation_contract import PATTERN_IDS

EVENT=1_800_000_000_000
COMMITTED=EVENT+301000


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def rawhash(x):
    return hashlib.sha256(x.encode()).hexdigest()


def db_fixture(path):
    db=sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE g1f_universe_snapshots(cohort_digest TEXT,symbols_json TEXT);
        CREATE TABLE g2_cohort_witness(cohort_digest TEXT,payload_json TEXT,payload_sha TEXT);
        CREATE TABLE g1f_event_manifest(event_open_ms INT,cohort_digest TEXT,
            committed_ms INT,state TEXT,verification_json TEXT,verification_sha TEXT);
        CREATE TABLE g1f_candidate_events(event_open_ms INT,decision_id TEXT,
            symbol TEXT,direction TEXT,status TEXT,record_json TEXT,record_sha TEXT);
        CREATE TABLE g2_quote_witness(event_open_ms INT,symbol TEXT,
            asof_ms INT,payload_json TEXT,payload_sha TEXT);
        CREATE TABLE g3_event_context(event_open_ms INT,payload_json TEXT,payload_sha TEXT);
    """)
    symbols=sorted(["BTCUSDT"]+[f"COIN{i:02d}USDT" for i in range(49)])
    sha=digest({"selection_version":"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                "symbols":symbols})
    db.execute("INSERT INTO g1f_universe_snapshots VALUES (?,?)",
               (sha,canonical(symbols)))
    cohort={"cohort_digest":sha,"ranked_selected":symbols}
    db.execute("INSERT INTO g2_cohort_witness VALUES (?,?,?)",
               (sha,canonical(cohort),digest(cohort)))
    manifest={"event_open_ms":EVENT,"committed_ms":COMMITTED}
    db.execute("INSERT INTO g1f_event_manifest VALUES (?,?,?,?,?,?)",
               (EVENT,sha,COMMITTED,"OBSERVE_ONLY",
                canonical(manifest),digest(manifest)))
    for sym in symbols:
        for side in ("LONG","SHORT"):
            did=digest({"symbol":sym,"side":side,"event":EVENT})
            record={"decision_id":did,"symbol":sym,"side":side,
                    "event_open_ms":EVENT,"decision_at_ms":COMMITTED,
                    "universe_digest":"f"*64,"status":"OBSERVED",
                    "reason_codes":[],"patterns":{k:"NO_MATCH" for k in PATTERN_IDS},
                    "source_digest":"e"*64,"btc_source_digest":"d"*64,
                    "order_authority":"NONE"}
            db.execute("INSERT INTO g1f_candidate_events VALUES (?,?,?,?,?,?,?)",
                       (EVENT,did,sym,side,"OBSERVED",canonical(record),digest(record)))
        witness={"event_open_ms":EVENT,"symbol":sym,"cohort_digest":sha,
                 "asof_ms":COMMITTED,"status":"SOURCE_RECORDED","hold_reasons":[],
                 "paper_fill_grade":"UNVERIFIED","order_authority":"NONE",
                 "source":{"market_connected":True,"public_connected":True,
                           "quote_received_ms":COMMITTED-100,
                           "trade_received_ms":COMMITTED-150}}
        db.execute("INSERT INTO g2_quote_witness VALUES (?,?,?,?,?)",
                   (EVENT,sym,COMMITTED,canonical(witness),digest(witness)))
    feature={"event_open_ms":EVENT,"valid_from_ms":COMMITTED,
             "candidate_cohort_size":50,"unknown_coin_count":0,
             "btc":{"valid":True},
             "coins":{s:{"state":"AVAILABLE"} for s in symbols}}
    feature["feature_sha256"]=digest(feature)
    g3={"event_open_ms":EVENT,"valid_from_ms":COMMITTED,
        "status":"OBSERVE_ONLY","order_authority":"NONE",
        "recommendation_authority":"NONE","feature_evidence":feature}
    db.execute("INSERT INTO g3_event_context VALUES (?,?,?)",
               (EVENT,canonical(g3),digest(g3)))
    db.commit()
    db.close()


class OfflineBindingTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/"mock_original_copy.sqlite"
        db_fixture(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def check(self, symbol="BTCUSDT",side="LONG"):
        return bind_from_frozen_observation_copy(
            db_path=self.path,event_open_ms=EVENT,symbol=symbol,side=side)

    def change(self,statement,args=()):
        with sqlite3.connect(self.path) as db:
            db.execute(statement,args)

    def test_entire_top50_100_sides_and_original_g3_sha_are_required(self):
        x=self.check()
        self.assertEqual(x.state,"SOURCE_BOUND")
        self.assertEqual(x.eligible_population,50)
        self.assertEqual(x.candidate_population,100)
        self.assertEqual(len(x.g3_feature_sha256),64)
        self.assertEqual(x.scored_outcomes,0)
        self.assertEqual(x.order_authority,"NONE")
        self.assertEqual(x.model_training_authority,"NONE")
        self.assertIn("NOT_EXCHANGE_SIGNED",x.source_grade)

    def test_short_and_other_coin_can_bind(self):
        self.assertEqual(self.check("COIN10USDT","SHORT").state,"SOURCE_BOUND")

    def test_no_write_to_readonly_source_copy(self):
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(self.check().state,"SOURCE_BOUND")
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),before)

    def test_missing_one_candidate_is_full_denominator_hold(self):
        self.change("DELETE FROM g1f_candidate_events WHERE symbol='BTCUSDT' AND direction='SHORT'")
        self.assertIn("G4_BIND_DIRECTIONAL_DENOMINATOR_INVALID",self.check().reasons)

    def test_corrupted_candidate_sha_blocks_other_coin_too(self):
        self.change("UPDATE g1f_candidate_events SET record_sha=? WHERE symbol='COIN10USDT' AND direction='SHORT'",("a"*64,))
        self.assertIn("G4_BIND_CANDIDATE_DIGEST_MISMATCH",self.check().reasons)

    def test_status_unscorable_not_accepted_as_outcome(self):
        self.change("UPDATE g1f_candidate_events SET status='UNSCORABLE' WHERE symbol='BTCUSDT' AND direction='LONG'")
        self.assertIn("G4_BIND_CANDIDATE_IDENTITY_INVALID",self.check().reasons)

    def test_missing_g2_witness_coin_fails_entire_event(self):
        self.change("DELETE FROM g2_quote_witness WHERE symbol='COIN10USDT'")
        self.assertIn("G4_BIND_G2_FULL_WITNESS_DENOMINATOR_MISSING",self.check().reasons)

    def test_g2_witness_corrupt_payload_rejected(self):
        self.change("UPDATE g2_quote_witness SET payload_sha=? WHERE symbol='COIN10USDT'",("b"*64,))
        self.assertIn("G4_BIND_G2_WITNESS_DIGEST_MISMATCH",self.check().reasons)

    def test_g2_wrong_cohort_ref_rejected(self):
        w=sqlite3.connect(self.path)
        row=w.execute("SELECT payload_json FROM g2_quote_witness WHERE symbol='COIN10USDT'").fetchone()
        obj=json.loads(row[0]); obj["cohort_digest"]="a"*64
        w.execute("UPDATE g2_quote_witness SET payload_json=?,payload_sha=? WHERE symbol='COIN10USDT'",
                  (canonical(obj),digest(obj)))
        w.commit(); w.close()
        self.assertIn("G4_BIND_G2_WITNESS_HELD_OR_INVALID",self.check().reasons)

    def test_g2_stale_quote_blocks_source_bound(self):
        w=sqlite3.connect(self.path)
        obj=json.loads(w.execute("SELECT payload_json FROM g2_quote_witness WHERE symbol='BTCUSDT'").fetchone()[0])
        obj["source"]["quote_received_ms"]=COMMITTED-6000
        w.execute("UPDATE g2_quote_witness SET payload_json=?,payload_sha=? WHERE symbol='BTCUSDT'",
                  (canonical(obj),digest(obj)))
        w.commit();w.close()
        self.assertIn("G4_BIND_G2_RECEIPT_CLOCK_INVALID",self.check().reasons)

    def test_g3_feature_sha_tamper_detected(self):
        self.change("UPDATE g3_event_context SET payload_sha=?",("0"*64,))
        self.assertIn("G4_BIND_G3_CONTEXT_DIGEST_MISSING",self.check().reasons)

    def test_g3_future_known_at_invalid(self):
        db=sqlite3.connect(self.path)
        g=json.loads(db.execute("SELECT payload_json FROM g3_event_context").fetchone()[0])
        g["valid_from_ms"]=COMMITTED+1
        db.execute("UPDATE g3_event_context SET payload_json=?,payload_sha=?",(canonical(g),digest(g)))
        db.commit();db.close()
        self.assertIn("G4_BIND_G3_CONTEXT_UNQUALIFIED",self.check().reasons)

    def test_g3_internal_feature_digest_tamper_detected(self):
        db=sqlite3.connect(self.path)
        g=json.loads(db.execute("SELECT payload_json FROM g3_event_context").fetchone()[0])
        g["feature_evidence"]["btc"]["valid"]=False
        db.execute("UPDATE g3_event_context SET payload_json=?,payload_sha=?",(canonical(g),digest(g)))
        db.commit();db.close()
        self.assertIn("G4_BIND_G3_FEATURE_NOT_REPRODUCIBLE",self.check().reasons)

    def test_manifest_corrupted_blocks(self):
        self.change("UPDATE g1f_event_manifest SET verification_sha=?",("0"*64,))
        self.assertIn("G4_BIND_EVENT_MANIFEST_INVALID",self.check().reasons)

    def test_symlink_is_rejected(self):
        symlink=Path(self.folder.name)/"alias.sqlite"
        symlink.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError,"G4_BIND_SNAPSHOT_NOT_REGULAR_FILE"):
            bind_from_frozen_observation_copy(db_path=symlink,event_open_ms=EVENT,
                                             symbol="BTCUSDT",side="LONG")

    def test_bad_event_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_BIND_EVENT_CLOCK_INVALID"):
            bind_from_frozen_observation_copy(db_path=self.path,event_open_ms=EVENT+1,
                                             symbol="BTCUSDT",side="LONG")

    def test_missing_event_is_hold_not_synthetic_record(self):
        x=bind_from_frozen_observation_copy(
            db_path=self.path,event_open_ms=EVENT+300000,
            symbol="BTCUSDT",side="LONG")
        self.assertEqual(x.state,"HOLD")
        self.assertIn("G4_BIND_ORIGINAL_EVENT_NOT_PRESENT",x.reasons)

    def test_missing_top50_member_forces_hold(self):
        self.change("DELETE FROM g1f_candidate_events WHERE symbol='COIN48USDT'")
        self.assertIn("G4_BIND_DIRECTIONAL_DENOMINATOR_INVALID",self.check().reasons)


if __name__=="__main__":
    unittest.main()
