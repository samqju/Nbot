import unittest

from strategy.strategy import Strategy


class Phase36B1DualUniverseContractTests(unittest.TestCase):
    def test_legacy_setter_populates_both_universes(self):
        strategy = Strategy()
        strategy.set_universe(["BTCUSDT", "ETHUSDT"])

        self.assertEqual(
            strategy.get_execution_universe(),
            {"BTCUSDT", "ETHUSDT"},
        )
        self.assertEqual(
            strategy.get_observation_universe(),
            {"BTCUSDT", "ETHUSDT"},
        )

    def test_explicit_dual_universe_contract(self):
        strategy = Strategy()
        strategy.set_universes(
            execution_symbols=["BTCUSDT"],
            observation_symbols=["BTCUSDT", "ETHUSDT"],
        )

        self.assertEqual(
            strategy.get_execution_universe(),
            {"BTCUSDT"},
        )
        self.assertEqual(
            strategy.get_observation_universe(),
            {"BTCUSDT", "ETHUSDT"},
        )
        self.assertEqual(
            strategy._universe,
            {"BTCUSDT", "ETHUSDT"},
        )

    def test_execution_must_be_subset_of_observation(self):
        strategy = Strategy()

        with self.assertRaisesRegex(
            ValueError,
            "EXECUTION_UNIVERSE_NOT_SUBSET_OF_OBSERVATION",
        ):
            strategy.set_universes(
                execution_symbols=["BTCUSDT"],
                observation_symbols=["ETHUSDT"],
            )

    def test_empty_execution_universe_is_rejected(self):
        strategy = Strategy()

        with self.assertRaisesRegex(
            ValueError,
            "EXECUTION_UNIVERSE_EMPTY",
        ):
            strategy.set_universes(
                execution_symbols=[],
                observation_symbols=["BTCUSDT"],
            )

    def test_returned_sets_are_defensive_copies(self):
        strategy = Strategy()
        strategy.set_universe(["BTCUSDT"])

        execution = strategy.get_execution_universe()
        observation = strategy.get_observation_universe()
        execution.add("ETHUSDT")
        observation.add("SOLUSDT")

        self.assertEqual(
            strategy.get_execution_universe(),
            {"BTCUSDT"},
        )
        self.assertEqual(
            strategy.get_observation_universe(),
            {"BTCUSDT"},
        )


if __name__ == "__main__":
    unittest.main()
