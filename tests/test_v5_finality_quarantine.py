"""G1e remediation: immutable staged-finality audit, BTC gate, and quarantine."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.finality_quarantine import (
    FinalityQuarantine, POLICY, STAGES, fingerprint, single_closed_rest,
)
from nbot.v5.observation_contract import INTERVAL_MS

EVENT = INTERVAL_MS*1000000
WSS = (EVENT, 100., 101., 99., 100., 10.)
DIFFERENT = (EVENT, 100., 101., 99., 100.75, 10.5)


def rest_row(bar=WSS):
    t,o,h,l,c,v=bar
    return [[t,str(o),str(h),str(l),str(c),str(v),t+INTERVAL_MS-1]]


class FinalityQuarantineTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"v5_test.db"
        self.db=sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.policy=FinalityQuarantine(self.db)

    def stages(self, symbol, *, wss=WSS, rests=(WSS,WSS,WSS)):
        out=[]
        for i,stage in enumerate(STAGES):
            out.append(self.policy.check(
                symbol,EVENT,stage,observed_ms=EVENT+INTERVAL_MS+1000+i*9000,
                wss_candle=wss,rest_candle=rests[i]))
        return out

    def test_50_coin_single_discrepancy_keeps_49_eligible_for_review(self):
        symbols=["BTCUSDT"]+[f"COIN{i:02}USDT" for i in range(49)]
        for symbol in symbols:
            if symbol=="COIN00USDT":
                self.stages(symbol, rests=(DIFFERENT,DIFFERENT,DIFFERENT))
            else:
                self.stages(symbol)
        report=self.policy.finalize_directional_observations(symbols,EVENT)
        self.assertEqual(len(report["verified_symbols"]),49)
        self.assertEqual(report["quarantined_symbols"],["COIN00USDT"])
        self.assertTrue(report["btc_verified"])
        self.assertTrue(report["evidence_cohort_eligible_for_future_review"])
        self.assertEqual(report["directional_observation_states"],{
            "verified_observe_only":98,
            "quarantined_unscorable":2,
            "unverified_unscorable":0,
        })
        self.assertEqual(report["recorded_directional_observations"],100)
        rows=self.db.execute("SELECT evidence_state,COUNT(*) FROM "
                             "v5_directional_evidence GROUP BY evidence_state").fetchall()
        self.assertEqual(dict(rows),{"UNSCORABLE":2,"VERIFIED_OBSERVE_ONLY":98})
        self.assertFalse(report["research_ready"])
        self.assertEqual(report["training_labels_created"],0)
        self.assertEqual(report["order_authority"],"NONE")
        self.db.close()
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM v5_directional_evidence").fetchone()[0],100)

    def test_early_discrepancy_then_later_agreement_remains_quarantined(self):
        steps=self.stages("ADAUSDT", rests=(DIFFERENT,WSS,WSS))
        self.assertEqual(steps[0]["changed_fields"],["close","volume"])
        self.assertTrue(steps[1]["rest_revised_since_previous"])
        self.assertEqual(steps[2]["changed_fields"],[])
        self.assertTrue(steps[2]["quarantined"])
        self.assertEqual(self.policy.reasons("ADAUSDT",EVENT),
                         ("REST_REVISED","WSS_REST_MISMATCH"))

    def test_rest_revision_even_if_all_stages_eventually_match_stays_held(self):
        steps=self.stages("ADAUSDT", rests=(WSS,DIFFERENT,WSS))
        self.assertFalse(steps[0]["quarantined"])
        self.assertTrue(steps[1]["rest_revised_since_previous"])
        self.assertEqual(steps[2]["changed_fields"],[])
        self.assertTrue(steps[2]["quarantined"])

    def test_bad_btc_makes_all_directions_unscorable(self):
        symbols=["BTCUSDT"]+[f"COIN{i:02}USDT" for i in range(12)]
        for symbol in symbols:
            self.stages(symbol,rests=(DIFFERENT,)*3 if symbol=="BTCUSDT" else (WSS,)*3)
        outcome=self.policy.finalize_directional_observations(symbols,EVENT)
        self.assertFalse(outcome["btc_verified"])
        self.assertFalse(outcome["evidence_cohort_eligible_for_future_review"])
        self.assertEqual(outcome["recorded_directional_observations"],26)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM v5_directional_evidence "
            "WHERE evidence_state='UNSCORABLE'").fetchone()[0],26)

    def test_maturity_missing_stage_refuses_any_directional_entries(self):
        self.policy.check("BTCUSDT",EVENT,"FIRST_REST",
                          observed_ms=EVENT+INTERVAL_MS+1000,
                          wss_candle=WSS,rest_candle=WSS)
        with self.assertRaisesRegex(ValueError,"NOT_MATURED"):
            self.policy.finalize_directional_observations(["BTCUSDT"],EVENT,
                                                           min_valid=1)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM v5_directional_evidence").fetchone()[0],0)

    def test_duplicate_out_of_order_and_nonmonotonic_rest_stages_refused(self):
        with self.assertRaisesRegex(ValueError,"STAGE_ORDER"):
            self.policy.check("BTCUSDT",EVENT,"DELAYED_REST",
                              observed_ms=EVENT+INTERVAL_MS+1000,
                              wss_candle=WSS,rest_candle=WSS)
        self.stages("BTCUSDT")
        with self.assertRaisesRegex(ValueError,"DUPLICATE_STAGE"):
            self.policy.check("BTCUSDT",EVENT,"FIRST_REST",
                              observed_ms=EVENT+INTERVAL_MS+1000,
                              wss_candle=WSS,rest_candle=WSS)
        with self.assertRaises(sqlite3.IntegrityError):
            self.policy.finalize_directional_observations(
                ["BTCUSDT"],EVENT,min_valid=1) if False else self._dup_directions()

    def _dup_directions(self):
        self.policy.finalize_directional_observations(["BTCUSDT"],EVENT,min_valid=1)
        self.policy.finalize_directional_observations(["BTCUSDT"],EVENT,min_valid=1)

    def test_cross_event_future_and_bad_rest_format_refuse_before_append(self):
        with self.assertRaisesRegex(ValueError,"CROSS_EVENT"):
            self.policy.check("BTCUSDT",EVENT,"FIRST_REST",
                              observed_ms=EVENT+INTERVAL_MS+1000,
                              wss_candle=WSS,
                              rest_candle=(EVENT+INTERVAL_MS,*WSS[1:]))
        for bad in ([],rest_row()+rest_row(),
                    [[EVENT,*rest_row()[0][1:6],EVENT+INTERVAL_MS]],
                    [[EVENT,"nan","101","99","100","10",EVENT+INTERVAL_MS-1]]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                single_closed_rest(bad,event_open_ms=EVENT)
        self.assertEqual(single_closed_rest(rest_row(),event_open_ms=EVENT),WSS)

    def test_all_evidence_tables_are_immutable(self):
        self.stages("BTCUSDT",rests=(DIFFERENT,WSS,WSS))
        self.policy.finalize_directional_observations(["BTCUSDT"],EVENT,min_valid=1)
        for table in ("v5_finality_checks","v5_quarantine_events",
                      "v5_directional_evidence"):
            for stmt in (f"DELETE FROM {table}",
                         f"UPDATE {table} SET rowid=rowid"):
                with self.subTest(stmt=stmt),self.assertRaises(sqlite3.IntegrityError):
                    self.db.execute(stmt)
        self.db.rollback()
        self.assertEqual(self.policy.reasons("BTCUSDT",EVENT),
                         ("REST_REVISED","WSS_REST_MISMATCH"))

    def test_quarantine_survives_sqlite_restart_without_auto_release(self):
        self.stages("ARBUSDT",rests=(DIFFERENT,WSS,WSS))
        self.db.close()
        self.db=sqlite3.connect(self.path)
        reopened=FinalityQuarantine(self.db)
        self.assertEqual(reopened.reasons("ARBUSDT",EVENT),
                         ("REST_REVISED","WSS_REST_MISMATCH"))
        self.assertFalse(reopened.evidence_status(
            ["ARBUSDT","BTCUSDT"],EVENT,min_valid=1)["btc_verified"])


if __name__=="__main__":
    unittest.main()
