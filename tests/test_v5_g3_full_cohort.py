"""50-market G1/G2/G3 frozen-source integration and failure injection.

Each test constructs 97 * 50 original candle sources, two complete
five-minute candidate populations and 100 quote witnesses. Pure offline.
"""
import unittest
from nbot.v5.g2_population_audit import audit_population
from nbot.v5.g2_source_acceptance import source_acceptance
from nbot.v5.g3_context_ledger import G3ContextLedger
from tests.test_v5_g3_frozen_replay import G3FrozenSourceTests


class FiftyCoinG1G2G3PipelineTests(G3FrozenSourceTests):
    COHORT_SIZE=50

    def test_all_fifty_symbols_have_verified_original_two_sided_proofs(self):
        self.assertEqual(len(self.symbols),50)
        population=audit_population(
            self.path,now_ms=self.first+5*300000)
        self.assertEqual(population["audit"],"PASS")
        self.assertEqual(population["expected_directional_records"],200)
        self.assertEqual(population["unrepresented_time_slots"],0)
        source=source_acceptance(
            self.path,min_complete_events=2,
            now_ms=self.first+5*300000)
        self.assertEqual(source["audit"],"PASS")
        self.assertEqual(source["fully_source_verified_observation_events"],2)
        self.assertEqual(source["complete_source_witness_rows"],100)
        g3=G3ContextLedger(self.db)
        for event in (self.first,self.next):
            self.assertEqual(g3.record(
                event_open_ms=event,symbols=self.symbols)["status"],
                "OBSERVE_ONLY")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM g3_event_context").fetchone()[0],2)
        self.assertEqual(self.report()["audit"],"PASS")
        self.assertEqual(self.report()["unknown_coin_events"],0)


if __name__=="__main__":
    unittest.main()
