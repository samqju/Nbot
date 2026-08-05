import json
import tempfile
import unittest
from pathlib import Path

from learning.shadow_promotion import ShadowPromotionEvaluator


class Phase47ShadowPromotionTests(unittest.TestCase):
    @staticmethod
    def _write(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )

    @staticmethod
    def _prediction(
        batch,
        candidate_id,
        probability,
        *,
        rule_selected=False,
        shadow_selected=False,
        rule_rank=1,
        shadow_rank=1,
    ):
        return {
            "schema_version": 1,
            "observation_type": "SHADOW_MODEL_PREDICTION",
            "observed_at_ms": batch,
            "candidate_observation_id": candidate_id,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "rule_rank": rule_rank,
            "shadow_rank": shadow_rank,
            "rule_score": 0.7,
            "shadow_probability": probability,
            "rule_selected": rule_selected,
            "shadow_selected": shadow_selected,
            "ranking_changed": rule_rank != shadow_rank,
            "runtime_effect": "NONE",
        }

    @staticmethod
    def _make_outcome(candidate_id, exit_r):
        return {
            "schema_version": 1,
            "observation_type": "CANDIDATE_OUTCOME",
            "recorded_at_ms": 100000,
            "candidate_observation_id": candidate_id,
            "outcome_type": "VIRTUAL_TRADE",
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "payload": {
                "exit_r": exit_r,
                "profitable": exit_r > 0,
            },
        }

    def _evaluation_report(self, path, psi=0.05):
        path.write_text(json.dumps({
            "drift": {
                "short_range": {
                    "psi": psi,
                    "severity": "LOW",
                }
            }
        }))

    def _run(
        self,
        root,
        predictions,
        outcomes,
        *,
        min_matched=4,
        min_paired=2,
    ):
        root = Path(root)
        predictions_path = root / "predictions.jsonl"
        outcomes_path = root / "outcomes.jsonl"
        evaluation_path = root / "evaluation.json"
        report_path = root / "promotion.json"
        self._write(predictions_path, predictions)
        self._write(outcomes_path, outcomes)
        self._evaluation_report(evaluation_path)
        return ShadowPromotionEvaluator(
            predictions_path=predictions_path,
            outcomes_path=outcomes_path,
            model_evaluation_report_path=evaluation_path,
            report_path=report_path,
            min_matched_candidates=min_matched,
            min_paired_batches=min_paired,
            min_avg_r_lift=0.10,
            max_win_rate_drop=0.05,
            max_brier_score=0.30,
            max_calibration_gap=0.20,
            max_feature_psi=0.25,
        ).evaluate()

    def test_promote_when_shadow_outperforms(self):
        with tempfile.TemporaryDirectory() as root:
            predictions = []
            outcomes = []
            for batch in range(3):
                rule_id = f"rule-{batch}"
                shadow_id = f"shadow-{batch}"
                predictions.extend([
                    self._prediction(
                        batch,
                        rule_id,
                        0.20,
                        rule_selected=True,
                        rule_rank=1,
                        shadow_rank=2,
                    ),
                    self._prediction(
                        batch,
                        shadow_id,
                        0.90,
                        shadow_selected=True,
                        rule_rank=2,
                        shadow_rank=1,
                    ),
                ])
                outcomes.extend([
                    self._make_outcome(rule_id, -1.0),
                    self._make_outcome(shadow_id, 2.0),
                ])

            report = self._run(
                root,
                predictions,
                outcomes,
                min_matched=4,
                min_paired=2,
            )
            self.assertEqual(report["decision"], "PROMOTE")
            self.assertEqual(
                report["runtime_activation"],
                "DISABLED",
            )
            self.assertTrue(report["advisory_only"])
            self.assertGreater(
                report["selection_comparison"][
                    "average_r_lift"
                ],
                0,
            )

    def test_hold_when_sample_is_insufficient(self):
        with tempfile.TemporaryDirectory() as root:
            predictions = [
                self._prediction(
                    1,
                    "rule",
                    0.4,
                    rule_selected=True,
                    shadow_selected=True,
                )
            ]
            outcomes = [self._make_outcome("rule", 1.0)]
            report = self._run(
                root,
                predictions,
                outcomes,
                min_matched=10,
                min_paired=5,
            )
            self.assertEqual(report["decision"], "HOLD")
            self.assertIn(
                "matched_candidate_sample",
                report["reasons"],
            )

    def test_reject_when_shadow_is_materially_worse(self):
        with tempfile.TemporaryDirectory() as root:
            predictions = []
            outcomes = []
            for batch in range(3):
                rule_id = f"rule-{batch}"
                shadow_id = f"shadow-{batch}"
                predictions.extend([
                    self._prediction(
                        batch,
                        rule_id,
                        0.8,
                        rule_selected=True,
                        rule_rank=1,
                        shadow_rank=2,
                    ),
                    self._prediction(
                        batch,
                        shadow_id,
                        0.9,
                        shadow_selected=True,
                        rule_rank=2,
                        shadow_rank=1,
                    ),
                ])
                outcomes.extend([
                    self._make_outcome(rule_id, 2.0),
                    self._make_outcome(shadow_id, -1.0),
                ])
            report = self._run(
                root,
                predictions,
                outcomes,
                min_matched=4,
                min_paired=2,
            )
            self.assertEqual(report["decision"], "REJECT")

    def test_duplicate_outcome_fails_closed_for_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            predictions = [
                self._prediction(
                    1,
                    "candidate",
                    0.8,
                    rule_selected=True,
                    shadow_selected=True,
                )
            ]
            outcome = self._make_outcome("candidate", 2.0)
            report = self._run(
                root,
                predictions,
                [outcome, dict(outcome)],
                min_matched=2,
                min_paired=1,
            )
            self.assertEqual(
                report["coverage"]["matched_candidates"],
                0,
            )
            self.assertEqual(
                report["issues"]["duplicate_candidate_outcome"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
