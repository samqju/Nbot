import unittest

from strategy.research_strategy_catalog import (
    LEGACY_SETUP_IDS,
    LEGACY_SHELVED,
    RESEARCH_STRATEGY_CATALOG,
    legacy_setup_status,
)


class Phase75D2BResearchStrategyCatalogTests(unittest.TestCase):
    def test_catalog_has_three_initial_research_families(self):
        self.assertEqual(len(RESEARCH_STRATEGY_CATALOG), 3)
        self.assertEqual(
            {spec.family for spec in RESEARCH_STRATEGY_CATALOG},
            {
                "CROSS_SECTIONAL_MOMENTUM_WITH_LIQUIDITY",
                "TIME_SERIES_MOMENTUM_TREND",
                "CONDITIONAL_INTRADAY_MOMENTUM_REVERSAL",
            },
        )

    def test_every_strategy_is_fail_closed_and_has_sources(self):
        for spec in RESEARCH_STRATEGY_CATALOG:
            self.assertEqual(spec.authority, "NONE")
            self.assertEqual(spec.runtime_activation, "DISABLED")
            self.assertEqual(spec.implementation_status, "CATALOG_ONLY_NOT_IMPLEMENTED")
            self.assertTrue(spec.source_refs)
            self.assertTrue(spec.required_data)

    def test_strategy_ids_are_unique(self):
        ids = [spec.strategy_id for spec in RESEARCH_STRATEGY_CATALOG]
        self.assertEqual(len(ids), len(set(ids)))

    def test_legacy_setups_are_shelved_for_new_research_only(self):
        self.assertEqual(len(LEGACY_SETUP_IDS), 10)
        status = legacy_setup_status()
        self.assertEqual(set(status), set(LEGACY_SETUP_IDS))
        self.assertTrue(all(value == LEGACY_SHELVED for value in status.values()))

    def test_catalog_does_not_claim_exact_replication_where_nbot_adapts(self):
        cross_sectional = next(
            spec for spec in RESEARCH_STRATEGY_CATALOG
            if spec.family == "CROSS_SECTIONAL_MOMENTUM_WITH_LIQUIDITY"
        )
        self.assertIn("must not be claimed as an exact paper replication", cross_sectional.nbot_adaptation)

        tsmom = next(
            spec for spec in RESEARCH_STRATEGY_CATALOG
            if spec.family == "TIME_SERIES_MOMENTUM_TREND"
        )
        self.assertIn("NBOT must validate the exact implementation itself", tsmom.nbot_adaptation)


if __name__ == "__main__":
    unittest.main()
