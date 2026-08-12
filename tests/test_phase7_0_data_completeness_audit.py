import json
import tempfile
import unittest
from pathlib import Path

from learning.phase7_data_audit import Phase7DataAudit


class Phase7DataCompletenessAuditTests(unittest.TestCase):
    def _write(self, path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    @staticmethod
    def _candidate(context: dict) -> dict:
        return {
            "observation_type": "STRATEGY_CANDIDATE",
            "experiment_contract_version": 1,
            "market_context": context,
        }

    @staticmethod
    def _outcome_row(cost_breakdown: dict) -> dict:
        return {
            "observation_type": "CANDIDATE_OUTCOME",
            "experiment_contract_version": 1,
            "payload": {"cost_breakdown": cost_breakdown},
        }

    def test_partial_phase5_context_is_reported_as_incomplete(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = root / "observations.jsonl"
            outcomes = root / "outcomes.jsonl"
            self._write(
                observations,
                [
                    self._candidate({
                        "btc_regime": None,
                        "market_breadth": None,
                        "liquidity": {
                            "spread_pct": None,
                            "quote_volume_usd": None,
                        },
                        "completeness": "PARTIAL_PHASE5_5",
                    })
                ],
            )
            self._write(
                outcomes,
                [
                    self._outcome_row({
                        "spread_r": None,
                        "funding_r": None,
                        "cost_completeness": "FEES_AND_CONFIGURED_SLIPPAGE_ONLY",
                    })
                ],
            )

            report = Phase7DataAudit(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
            ).run()

            self.assertEqual(report["status"], "BLOCKED")
            missing = report["observations"]["missing_required_market_context"]
            self.assertEqual(missing["btc_regime"], 1)
            self.assertEqual(missing["market_breadth"], 1)
            self.assertEqual(missing["liquidity.spread_pct"], 1)
            self.assertEqual(missing["liquidity.quote_volume_usd"], 1)
            costs = report["outcomes"]["missing_cost_components"]
            self.assertEqual(costs["spread_r"], 1)
            self.assertEqual(costs["funding_r"], 1)

    def test_complete_context_is_not_marked_missing(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = root / "observations.jsonl"
            outcomes = root / "outcomes.jsonl"
            self._write(
                observations,
                [
                    self._candidate({
                        "btc_regime": "BULLISH",
                        "market_breadth": {
                            "advancing_fraction": 0.70,
                        },
                        "liquidity": {
                            "spread_pct": 0.03,
                            "quote_volume_usd": 25_000_000.0,
                        },
                        "completeness": "FULL_PHASE7",
                    })
                ],
            )
            self._write(outcomes, [])

            report = Phase7DataAudit(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
            ).run()

            self.assertEqual(
                report["observations"]["missing_required_market_context"],
                {},
            )
            self.assertNotIn(
                "CANDIDATE_MODEL_VECTOR_DOES_NOT_CONSUME_MARKET_CONTEXT",
                report["blockers"],
            )
            self.assertIn(
                "VIRTUAL_COST_MODEL_EXCLUDES_SPREAD",
                report["blockers"],
            )


if __name__ == "__main__":
    unittest.main()
