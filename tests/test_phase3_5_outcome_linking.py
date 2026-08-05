import json
import tempfile
import unittest
from pathlib import Path

from strategy.candidate import StrategyCandidate
from strategy.candidate_outcome import CandidateOutcomeWriter
from strategy.features import CandidateFeatures
from strategy.trade_intent import TradeIntent
from datetime import datetime, timezone


class Phase35OutcomeLinkingTests(unittest.TestCase):
    def _features(self):
        return CandidateFeatures(
            0.01, 0.02, 7, 0.4, 0.6, 0.5, -0.01, 0.03, 4
        )

    def test_candidates_receive_unique_observation_ids(self):
        first = StrategyCandidate(
            "BTCUSDT", "LONG", 0.8, "STRUCTURE_5M", 1,
            self._features(),
        )
        second = StrategyCandidate(
            "ETHUSDT", "SHORT", 0.7, "STRUCTURE_5M", 1,
            self._features(),
        )
        self.assertTrue(first.observation_id)
        self.assertTrue(second.observation_id)
        self.assertNotEqual(
            first.observation_id,
            second.observation_id,
        )

    def test_outcome_writer_links_to_candidate_id(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "outcomes.jsonl"
            writer = CandidateOutcomeWriter(str(path))
            writer.append(
                observation_id="candidate-123",
                outcome_type="FORWARD_5_CANDLE",
                symbol="BTCUSDT",
                direction="LONG",
                payload={"target_r": 0.8, "label": 1},
            )
            row = json.loads(path.read_text())
            self.assertEqual(
                row["candidate_observation_id"],
                "candidate-123",
            )
            self.assertEqual(row["outcome_type"], "FORWARD_5_CANDLE")
            self.assertEqual(row["payload"]["label"], 1)

    def test_empty_observation_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            writer = CandidateOutcomeWriter(
                str(Path(root) / "outcomes.jsonl")
            )
            with self.assertRaisesRegex(
                ValueError,
                "CANDIDATE_OUTCOME_OBSERVATION_ID_INVALID",
            ):
                writer.append(
                    observation_id="",
                    outcome_type="EXECUTED_TRADE",
                    symbol="BTCUSDT",
                    direction="LONG",
                    payload={},
                )

    def test_trade_intent_carries_candidate_id(self):
        intent = TradeIntent(
            symbol="BTCUSDT",
            direction="LONG",
            pattern="STRUCTURE_5M",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
            candidate_observation_id="candidate-abc",
        )
        self.assertEqual(
            intent.candidate_observation_id,
            "candidate-abc",
        )

    def test_outcome_file_is_append_only(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "outcomes.jsonl"
            writer = CandidateOutcomeWriter(str(path))
            for index in range(2):
                writer.append(
                    observation_id=f"candidate-{index}",
                    outcome_type="FORWARD_5_CANDLE",
                    symbol="BTCUSDT",
                    direction="LONG",
                    payload={"label": index},
                )
            rows = [
                json.loads(line)
                for line in path.read_text().splitlines()
            ]
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                rows[1]["candidate_observation_id"],
                "candidate-1",
            )


if __name__ == "__main__":
    unittest.main()
