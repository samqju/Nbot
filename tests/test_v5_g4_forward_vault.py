"""G4 isolated RAW SOURCE vault regression suite: temp or :memory: DB only."""
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest

from nbot.v5.g4_forward_vault import ForwardSourceVault

NOW=1800000000000
SYMS=("BTCUSDT","QNTUSDT")


def trade(*,symbol="QNTUSDT",agg=100,first=500,last=502,at=NOW):
    data={"stream":symbol.lower()+"@aggTrade",
          "data":{"e":"aggTrade","E":at-30,"s":symbol,
                  "a":agg,"f":first,"l":last,"T":at-30,
                  "p":"200.5","q":"10.0","m":False,"st":1}}
    return json.dumps(data,separators=(",",":")).encode()


def quote(*,symbol="QNTUSDT",bid="200.4",ask="200.5",at=NOW):
    data={"stream":symbol.lower()+"@bookTicker",
          "data":{"e":"bookTicker","E":at-40,"s":symbol,
                  "b":bid,"B":"2.0","a":ask,"A":"3.0","st":1}}
    return json.dumps(data,separators=(",",":")).encode()


class G4VaultTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.v=ForwardSourceVault(self.db,symbols=SYMS)
    def tearDown(self):
        self.db.close()

    def connect(self):
        return self.v.connect(route="market_aggtrade",at_ms=NOW-500)

    def test_cohort_is_exact_and_hash_chain_auditable(self):
        self.connect()
        r=self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        x=self.v.audit()
        self.assertEqual(r.evidence_state,"SOURCE_RECORDED")
        self.assertEqual(x["audit"],"PASS")
        self.assertEqual(x["frozen_cohort"],2)
        self.assertEqual(x["scored_outcomes"],0)
        self.assertEqual(x["order_authority"],"NONE")
        self.assertEqual(x["counts"]["SOURCE_RECORDED"],1)

    def test_public_bid_ask_is_source_not_fill(self):
        self.v.connect(route="public_bookticker",at_ms=NOW-500)
        r=self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        self.assertEqual(r.evidence_state,"SOURCE_RECORDED")
        self.assertEqual(r.economic_outcomes,0)
        self.assertEqual(r.order_authority,"NONE")
        self.assertEqual(self.v.audit()["counts"]["SOURCE_RECORDED"],1)

    def test_agg_continuous_receipts(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        second=self.v.ingest(route="market_aggtrade",at_ms=NOW+100,
                             raw=trade(agg=101,first=503,last=504,at=NOW+100))
        self.assertEqual(second.evidence_state,"SOURCE_RECORDED")
        self.assertEqual(self.v.audit()["counts"]["SOURCE_RECORDED"],2)

    def test_gap_preserved_as_held_original(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        bad=self.v.ingest(route="market_aggtrade",at_ms=NOW+100,
                          raw=trade(agg=103,first=503,last=504,at=NOW+100))
        self.assertEqual(bad.evidence_state,"HOLD")
        self.assertIn("AGGTRADE_ID_GAP_OR_REPLAY",bad.reasons)
        self.assertEqual(self.v.audit()["counts"]["HOLD"],1)

    def test_underlying_gap_held(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        result=self.v.ingest(route="market_aggtrade",at_ms=NOW+100,
                             raw=trade(agg=101,first=504,last=505,at=NOW+100))
        self.assertIn("UNDERLYING_TRADE_ID_GAP_OR_REPLAY",result.reasons)

    def test_hold_propagates_not_silently_cleared_by_next_frame(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        self.v.ingest(route="market_aggtrade",at_ms=NOW+100,
                      raw=trade(agg=105,first=503,last=504,at=NOW+100))
        next_=self.v.ingest(route="market_aggtrade",at_ms=NOW+200,
                            raw=trade(agg=106,first=505,last=507,at=NOW+200))
        self.assertEqual(next_.evidence_state,"HOLD")
        self.assertIn("PRIOR_SYMBOL_SOURCE_HELD",next_.reasons)

    def test_quotes_recorded_separately_from_market_trades(self):
        self.connect()
        self.v.connect(route="public_bookticker",at_ms=NOW-500)
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        self.assertEqual(self.v.audit()["counts"]["SOURCE_RECORDED"],2)

    def test_disconnect_blocks_frames(self):
        self.connect()
        self.v.disconnect(route="market_aggtrade",at_ms=NOW)
        with self.assertRaisesRegex(ValueError,"G4_VAULT_ROUTE_NOT_CONNECTED"):
            self.v.ingest(route="market_aggtrade",at_ms=NOW+100,raw=trade())
        self.assertEqual(self.v.audit()["counts"]["CLOSED"],1)

    def test_clean_reconnect_new_epoch_does_not_claim_continuity(self):
        self.connect()
        self.v.disconnect(route="market_aggtrade",at_ms=NOW)
        new=self.v.connect(route="market_aggtrade",at_ms=NOW+500)
        self.assertEqual(new.epoch,2)
        self.assertEqual(new.evidence_state,"HOLD")
        self.assertEqual(self.v.audit()["counts"]["ABRUPT_RESTART_HOLD"],0)

    def test_abrupt_restart_does_not_erase_unknown_gap(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        nxt=self.v.connect(route="market_aggtrade",at_ms=NOW+10000)
        self.assertEqual(nxt.epoch,2)
        self.assertEqual(self.v.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)
        self.assertIn("INITIAL_EPOCH_CONTINUITY_UNPROVEN",nxt.reasons)

    def test_route_epoch_reopen_from_restarted_sqlite(self):
        fd,p=tempfile.mkstemp(suffix=".g4.test.sqlite")
        os.close(fd)
        try:
            a=sqlite3.connect(p)
            v=ForwardSourceVault(a,symbols=SYMS)
            v.connect(route="market_aggtrade",at_ms=NOW-500)
            v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
            original=v.audit()["head_sha256"]
            a.close()
            b=sqlite3.connect(p)
            restored=ForwardSourceVault(b,symbols=SYMS)
            self.assertEqual(restored.audit()["head_sha256"],original)
            restored.connect(route="market_aggtrade",at_ms=NOW+20000)
            self.assertEqual(restored.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)
            b.close()
        finally:
            os.unlink(p)

    def test_freeze_cohort_change_rejected(self):
        with self.assertRaisesRegex(ValueError,"G4_VAULT_FROZEN_COHORT_CONFLICT"):
            ForwardSourceVault(self.db,symbols=["BTCUSDT"])

    def test_production_sqlite_schema_never_modified(self):
        x=sqlite3.connect(":memory:")
        try:
            x.execute("CREATE TABLE g1f_event_manifest(event_open_ms INT)")
            with self.assertRaisesRegex(ValueError,"G4_VAULT_MIXED_OR_PRODUCTION_DB_FORBIDDEN"):
                ForwardSourceVault(x,symbols=SYMS)
            self.assertEqual(x.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'g4_%'").fetchone()[0],0)
        finally:
            x.close()

    def test_reject_mixed_g4_research_label_database(self):
        x=sqlite3.connect(":memory:")
        try:
            x.execute("CREATE TABLE g4_label_intents(label_id TEXT)")
            with self.assertRaisesRegex(ValueError,"G4_VAULT_MIXED_OR_PRODUCTION_DB_FORBIDDEN"):
                ForwardSourceVault(x,symbols=SYMS)
        finally:
            x.close()

    def test_immutability_triggers_protect_raw_evidence(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        with self.assertRaisesRegex(sqlite3.IntegrityError,"G4_VAULT_IMMUTABLE"):
            self.db.execute("UPDATE g4_forward_receipts SET raw_frame=?", (b"bad",))
        with self.assertRaisesRegex(sqlite3.IntegrityError,"G4_VAULT_IMMUTABLE"):
            self.db.execute("DELETE FROM g4_forward_receipts")

    def test_sha_chain_detects_direct_forgery_after_trigger_drop(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        self.db.execute("DROP TRIGGER g4_forward_receipts_no_update")
        self.db.execute("UPDATE g4_forward_receipts SET raw_frame=? WHERE kind='FRAME'",(b"fake",))
        with self.assertRaisesRegex(ValueError,"G4_VAULT_SHA_CHAIN_INVALID"):
            self.v.audit()

    def test_no_duplicates_silent_insert(self):
        self.connect()
        raw=trade()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=raw)
        again=self.v.ingest(route="market_aggtrade",at_ms=NOW+100,raw=raw)
        self.assertIn("DUPLICATE_RAW_FRAME",again.reasons)
        self.assertEqual(again.evidence_state,"HOLD")

    def test_raw_invalid_json_recorded_hold_not_profit(self):
        self.connect()
        r=self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=b"not_json")
        self.assertEqual(r.evidence_state,"HOLD")
        self.assertEqual(r.economic_outcomes,0)
        self.assertEqual(self.v.audit()["counts"]["HOLD"],1)

    def test_oversized_frame_fail_closed_before_persist(self):
        self.connect()
        with self.assertRaisesRegex(ValueError,"G4_VAULT_FRAME_OVERSIZE"):
            self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=b"x"*33000)
        self.assertEqual(self.v.audit()["counts"]["HOLD"],0)

    def test_clock_rewind_never_silent_source(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        with self.assertRaisesRegex(ValueError,"G4_VAULT_CLOCK_REWIND"):
            self.v.ingest(route="market_aggtrade",at_ms=NOW-100,raw=trade())

    def test_rejected_restart_clock_does_not_mutate_any_receipts(self):
        self.connect()
        self.v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
        head=self.v.audit()["head_sha256"]
        total=self.db.execute("SELECT count(*) FROM g4_forward_receipts").fetchone()[0]
        with self.assertRaisesRegex(ValueError,"G4_VAULT_CLOCK_REWIND"):
            self.v.connect(route="market_aggtrade",at_ms=NOW-100)
        self.assertEqual(self.v.audit()["head_sha256"],head)
        self.assertEqual(self.db.execute("SELECT count(*) FROM g4_forward_receipts").fetchone()[0],total)

    def test_private_standalone_sqlite_backup_restore_replays_identical_raw_hash(self):
        with tempfile.TemporaryDirectory() as work:
            original=os.path.join(work,"original_g4_only.sqlite")
            restored=os.path.join(work,"restored_g4_only.sqlite")
            source=sqlite3.connect(original)
            try:
                source.execute("PRAGMA journal_mode=WAL")
                v=ForwardSourceVault(source,symbols=SYMS)
                v.connect(route="market_aggtrade",at_ms=NOW-500)
                receipt=v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
                head=v.audit()["head_sha256"]
                with sqlite3.connect(restored) as destination:
                    source.backup(destination)
                with sqlite3.connect(restored) as recovered:
                    replay=ForwardSourceVault(recovered,symbols=SYMS)
                    self.assertEqual(replay.audit()["head_sha256"],head)
                    raw=recovered.execute("SELECT raw_frame FROM g4_forward_receipts "
                                          "WHERE kind='FRAME'").fetchone()[0]
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt.raw_sha256)
                    self.assertEqual(replay.audit()["scored_outcomes"],0)
            finally:
                source.close()

    def test_five_minute_candidates_are_never_trades(self):
        self.connect()
        for i in range(4):
            self.v.ingest(route="market_aggtrade",at_ms=NOW+100*i,
                          raw=trade(agg=100+i,first=500+3*i,last=502+3*i,at=NOW+100*i))
        a=self.v.audit()
        self.assertEqual(a["scored_outcomes"],0)
        self.assertEqual(a["order_authority"],"NONE")


if __name__=="__main__":
    unittest.main()
