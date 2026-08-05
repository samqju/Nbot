import unittest
from types import SimpleNamespace

from strategy.strategy import Strategy


class Log:
    def __init__(self):
        self.infos = []
    def info(self, message):
        self.infos.append(message)
    def error(self, message):
        pass


class Phase36B2ExecutionFilterTests(unittest.TestCase):
    def test_observation_only_candidates_do_not_become_paper_intents(self):
        log = Log()
        strategy = Strategy(system_log=log)
        strategy.set_universes(
            execution_symbols=["BTCUSDT"],
            observation_symbols=["BTCUSDT", "ETHUSDT"],
        )
        strategy._warmed_up = True

        candidate = SimpleNamespace(
            symbol="ETHUSDT",
            direction="LONG",
            score=0.9,
            observation_id="obs-1",
            risk_plan=None,
            score_breakdown=None,
            pattern="RANGE_BREAKOUT",
            structure_fingerprint=None,
        )
        strategy._candidate_generator = SimpleNamespace(
            generate=lambda: [candidate]
        )
        strategy._candidate_scorer = SimpleNamespace(
            score_all=lambda values: values
        )
        strategy._candidate_risk_planner = SimpleNamespace(
            plan_all=lambda values: values
        )
        strategy._virtual_trade_engine = SimpleNamespace(
            enroll_all=lambda values: len(values)
        )
        strategy._candidate_observer = SimpleNamespace(
            append=lambda *args, **kwargs: None
        )

        self.assertIsNone(strategy.propose_intent())
        self.assertTrue(
            any(
                "OBSERVATION_CANDIDATES_ONLY" in message
                for message in log.infos
            )
        )


if __name__ == "__main__":
    unittest.main()
