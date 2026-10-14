"""Synthetic, network-free tests for independently replayed original G4 entry quotes."""
import sqlite3
import tempfile
from pathlib import Path
import unittest

from nbot.v5.g4_forward_entry_quote import (
    independent_asof_entry_quote,policy_quote_mapping,
)
from nbot.v5.g4_forward_vault import ForwardSourceVault
from tests.test_v5_g4_forward_vault import quote,NOW,SYMS


class G4ForwardEntryQuoteTests(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.path=Path(self.work.name)/"raw.sqlite"
        self.db=sqlite3.connect(self.path)
        self.v=ForwardSourceVault(self.db,symbols=SYMS)
        self.v.connect(route="public_bookticker",at_ms=NOW-1000)

    def tearDown(self):
        self.db.close()
        self.work.cleanup()

    def check(self,decision=NOW+200,symbol="QNTUSDT",age=1000):
        return independent_asof_entry_quote(
            vault_db=self.path,symbol=symbol,decision_at_ms=decision,
            max_age_ms=age)

    def test_original_sha_chain_quote_at_decision_not_a_fill(self):
        source=self.v.ingest(route="public_bookticker",at_ms=NOW,
                             raw=quote())
        result=self.check()
        self.assertEqual(result.state,"LOCAL_SOURCE_QUOTE")
        self.assertEqual(result.bid,"200.4")
        self.assertEqual(result.ask,"200.5")
        self.assertEqual(result.receipt_sha256,source.raw_sha256)
        self.assertEqual(result.scored_outcomes,0)
        self.assertEqual(result.fills,0)
        self.assertEqual(result.order_authority,"NONE")
        policy=policy_quote_mapping(result)
        self.assertTrue(policy["source_verified"])
        self.assertEqual(policy["financial_authority"],"NONE")

    def test_quote_cannot_be_future_dated_to_old_decision(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        self.assertEqual(self.check(decision=NOW-1).state,"HOLD")

    def test_quote_later_than_freshness_limit_held(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        result=self.check(decision=NOW+2000)
        self.assertIn("G4_ENTRY_FRESH_QUOTE_MISSING",result.reasons)

    def test_foreign_symbol_not_sourced(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        result=self.check(symbol="NONUSDT")
        self.assertIn("G4_ENTRY_SYMBOL_NOT_FROZEN",result.reasons)

    def test_bad_quote_poison_sticky_epoch(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,
                      raw=quote(bid="0"))
        self.v.ingest(route="public_bookticker",at_ms=NOW+100,
                      raw=quote(at=NOW+100))
        result=self.check(decision=NOW+200)
        self.assertNotEqual(result.state,"LOCAL_SOURCE_QUOTE")
        self.assertEqual(result.scored_outcomes,0)

    def test_restarted_epoch_can_have_new_asof_quote_but_not_continuity_proof(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,
                      raw=quote(bid="0"))
        self.v.disconnect(route="public_bookticker",at_ms=NOW+10)
        self.v.connect(route="public_bookticker",at_ms=NOW+100)
        self.v.ingest(route="public_bookticker",at_ms=NOW+200,
                      raw=quote(at=NOW+200))
        result=self.check(decision=NOW+300)
        self.assertEqual(result.state,"LOCAL_SOURCE_QUOTE")
        self.assertIn("NOT_EXCHANGE_SIGNED",result.source_grade)
        self.assertEqual(result.scored_outcomes,0)

    def test_sha_tampering_refused(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        self.db.execute("DROP TRIGGER g4_forward_receipts_no_update")
        self.db.execute("UPDATE g4_forward_receipts SET raw_frame=? WHERE kind='FRAME'",
                        (b"tampered",))
        self.db.commit()
        result=self.check()
        self.assertEqual(result.state,"HOLD")
        self.assertIn("G4_ENTRY_VAULT_INTEGRITY_UNVERIFIED",result.reasons)

    def test_zero_age_requires_exact_same_ms(self):
        self.v.ingest(route="public_bookticker",at_ms=NOW,raw=quote())
        self.assertEqual(self.check(decision=NOW,age=0).state,
                         "HOLD")  # Original exchange E is 40ms earlier.
        self.assertEqual(self.check(decision=NOW+1,age=0).state,"HOLD")

    def test_unsupported_clock_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"G4_ENTRY_QUOTE_CALL_INVALID"):
            self.check(decision=-1)

if __name__=="__main__":
    unittest.main()
