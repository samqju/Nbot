import unittest

from nbot.observation.decision_policy import GateCalibrationConfig, GatePolicyCalibrator


class _Ledger:
    def __init__(self, rows):
        self.rows = rows

    def decision_policy_rows(self):
        return self.rows


def row(event, score, edge, outcome, exit_offset=10):
    return {
        "event_ms": event, "rank": 1, "symbol": "XUSDT", "side": "LONG",
        "scores": {"conservative_score_r": score, "raw_edge_gap_r": edge},
        "target_net_r": outcome, "exit_time_ms": event + exit_offset,
    }


class GatePolicyTests(unittest.TestCase):
    def test_insufficient_evidence_keeps_current_gate(self):
        result = GatePolicyCalibrator(
            _Ledger([row(i*100, .1, .1, 1) for i in range(10)]),
            GateCalibrationConfig(min_events=50),
        ).calibrate()
        self.assertFalse(result["qualified"])
        self.assertEqual(result["recommended_gate"]["min_confidence_r"], .08)

    def test_capacity_skips_overlapping_hypotheses(self):
        rows = [row(100, .1, .1, 1, exit_offset=1000), row(200, .1, .1, 50)]
        prepared = GatePolicyCalibrator._top_rows(rows)
        result = GatePolicyCalibrator._evaluate(prepared, .08, .05)
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["total_net_r"], 1)
        self.assertEqual(result["skipped_capacity"], 1)

    def test_oos_gate_can_qualify_only_after_chronological_support(self):
        rows = []
        for i in range(120):
            score = .06 if i % 2 == 0 else .10
            outcome = .5 if score == .06 else -.2
            rows.append(row(i*1000, score, .10, outcome, exit_offset=1))
        cfg = GateCalibrationConfig(
            min_events=100, min_train_accepted=10, min_validation_accepted=5,
            min_validation_gain_r_per_event=.001,
        )
        result = GatePolicyCalibrator(_Ledger(rows), cfg).calibrate()
        self.assertTrue(result["qualified"])
        self.assertLessEqual(result["recommended_gate"]["min_confidence_r"], .06)


if __name__ == "__main__":
    unittest.main()
