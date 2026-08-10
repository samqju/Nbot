import json
import tempfile
import unittest
from pathlib import Path

from communication.responses import OutcomeAcknowledgement
from execution.outcome_builder import build_execution_outcome
from execution.outcome_outbox import ExecutionOutcomeOutbox
from execution.outcome_publisher import ExecutionOutcomePublisher
from observation.execution_outcome_receiver import LocalExecutionOutcomeReceiver
from strategy.candidate_outcome import CandidateOutcomeWriter
from strategy.experiment_contract import build_experiment_context


class CaptureLog:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def error(self, message):
        self.errors.append(message)


class Phase6A03ExecutionOutcomeDeliveryTests(unittest.TestCase):
    def _position(self, **overrides):
        position = {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": 100.0,
            "qty": 2.0,
            "entry_timestamp": 1_786_170_000_000,
            "entry_order_id": "ORDER-1",
            "entry_client_order_id": "CLIENT-1",
            "initial_stop_loss": 95.0,
            "stop_loss": 101.0,
            "initial_risk_usd": 10.0,
            "risk_usd": 10.0,
            "mae": -3.0,
            "mfe": 14.0,
            "candidate_observation_id": "candidate-1",
            "decision_batch_id": "batch-1",
            "market_event_id": "event-1",
            "pattern": "RANGE_BREAKOUT",
            "strategy_version": "STRUCTURE_RULES_V1",
            "strategy_variant_id": "VARIANT-1",
            "model_version": "RULE_SYSTEM_V1",
            "selection_authority": "RULES",
            "experiment_context": build_experiment_context(
                decision_batch_id="batch-1",
                market_event_id="event-1",
                strategy_version="STRUCTURE_RULES_V1",
                strategy_variant_id="VARIANT-1",
                selection_model_version="RULE_SYSTEM_V1",
                environment="LIVE",
                execution_mode="SHADOW",
                candle_bucket=12345,
                structure_fingerprint={"trend": "UP"},
                paper_taker_fee_rate=0.0005,
                paper_entry_slippage_pct=0.02,
                paper_exit_slippage_pct=0.02,
                virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
                virtual_target_r=2.0,
                virtual_max_candles=24,
                paper_variant_id="PAPER_TRAILING_SL_V1",
            ),
        }
        position.update(overrides)
        return position

    def make_outcome(self, **position_overrides):
        return build_execution_outcome(
            open_position=self._position(**position_overrides),
            environment="LIVE",
            execution_mode="SHADOW",
            exit_price=106.0,
            realized_pnl_usd=12.0,
            exit_reason="STOP_LOSS",
            closed_timestamp=1_786_170_060_000,
            holding_seconds=60,
        )

    def test_builder_creates_deterministic_retry_safe_ids(self):
        first = self.make_outcome()
        second = self.make_outcome()
        self.assertEqual(first.outcome_id, second.outcome_id)
        self.assertEqual(first.proposal_id, second.proposal_id)
        self.assertEqual(first.proposal_id, "LEGACY-candidate-1")
        self.assertEqual(first.r_multiple, 1.2)
        self.assertEqual(first.mae_r, -0.3)
        self.assertEqual(first.mfe_r, 1.4)

    def test_builder_preserves_explicit_proposal_id(self):
        outcome = self.make_outcome(proposal_id="PROP-123")
        self.assertEqual(outcome.proposal_id, "PROP-123")

    def test_outbox_survives_reopen_and_acknowledge(self):
        with tempfile.TemporaryDirectory() as root:
            first = ExecutionOutcomeOutbox(root)
            outcome = self.make_outcome()
            first.enqueue(outcome)
            self.assertEqual(first.pending_count(), 1)

            reopened = ExecutionOutcomeOutbox(root)
            pending = reopened.pending()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0], outcome)
            self.assertTrue(reopened.acknowledge(outcome.outcome_id))
            self.assertEqual(reopened.pending_count(), 0)

    def test_outbox_same_id_keeps_first_durable_payload(self):
        with tempfile.TemporaryDirectory() as root:
            outbox = ExecutionOutcomeOutbox(root)
            first = self.make_outcome()
            second = build_execution_outcome(
                open_position=self._position(),
                environment="LIVE",
                execution_mode="SHADOW",
                exit_price=107.0,
                realized_pnl_usd=14.0,
                exit_reason="RECONCILIATION",
                closed_timestamp=1_786_170_061_000,
                holding_seconds=61,
            )
            self.assertEqual(first.outcome_id, second.outcome_id)
            stored_first = outbox.enqueue(first)
            stored_second = outbox.enqueue(second)
            self.assertEqual(stored_first, first)
            self.assertEqual(stored_second, first)
            self.assertEqual(outbox.pending_count(), 1)

    def test_publisher_failure_keeps_durable_pending_outcome(self):
        class FailingReceiver:
            def receive(self, outcome):
                raise ConnectionError("observer unavailable")

        with tempfile.TemporaryDirectory() as root:
            outbox = ExecutionOutcomeOutbox(root)
            publisher = ExecutionOutcomePublisher(
                outbox=outbox,
                receiver=FailingReceiver(),
                system_log=CaptureLog(),
            )
            self.assertFalse(publisher.publish(self.make_outcome()))
            self.assertEqual(outbox.pending_count(), 1)

    def test_publisher_deletes_only_after_valid_ack(self):
        class RecordingReceiver:
            def receive(self, outcome):
                return OutcomeAcknowledgement.create(
                    outcome_id=outcome.outcome_id,
                    acknowledged_at=1_786_170_061_000,
                    status="RECORDED",
                )

        with tempfile.TemporaryDirectory() as root:
            outbox = ExecutionOutcomeOutbox(root)
            publisher = ExecutionOutcomePublisher(
                outbox=outbox,
                receiver=RecordingReceiver(),
            )
            self.assertTrue(publisher.publish(self.make_outcome()))
            self.assertEqual(outbox.pending_count(), 0)

    def test_publisher_bad_ack_keeps_outcome(self):
        class WrongAckReceiver:
            def receive(self, outcome):
                return OutcomeAcknowledgement.create(
                    outcome_id="OUT-WRONG",
                    acknowledged_at=1_786_170_061_000,
                    status="RECORDED",
                )

        with tempfile.TemporaryDirectory() as root:
            outbox = ExecutionOutcomeOutbox(root)
            publisher = ExecutionOutcomePublisher(
                outbox=outbox,
                receiver=WrongAckReceiver(),
            )
            self.assertFalse(publisher.publish(self.make_outcome()))
            self.assertEqual(outbox.pending_count(), 1)

    def test_local_receiver_preserves_executed_trade_learning_payload(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes.jsonl"
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            outcome = self.make_outcome(proposal_id="PROP-123")
            ack = receiver.receive(outcome)
            self.assertEqual(ack.status, "RECORDED")

            row = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(row["outcome_type"], "EXECUTED_TRADE")
            self.assertEqual(row["candidate_observation_id"], "candidate-1")
            self.assertEqual(row["environment"], "LIVE")
            self.assertEqual(row["execution_mode"], "SHADOW")
            self.assertEqual(row["payload"]["entry_price"], 100.0)
            self.assertEqual(row["payload"]["exit_price"], 106.0)
            self.assertEqual(row["payload"]["qty"], 2.0)
            self.assertEqual(row["payload"]["realized_pnl_usd"], 12.0)
            self.assertEqual(row["payload"]["r_multiple"], 1.2)
            self.assertEqual(row["payload"]["mae_r"], -0.3)
            self.assertEqual(row["payload"]["mfe_r"], 1.4)
            self.assertEqual(row["payload"]["holding_seconds"], 60)
            self.assertEqual(row["payload"]["exit_reason"], "STOP_LOSS")
            self.assertEqual(row["payload"]["proposal_id"], "PROP-123")
            self.assertEqual(
                row["payload"]["execution_outcome_id"], outcome.outcome_id
            )
            self.assertEqual(
                row["outcome_variant_id"], "PAPER_TRAILING_SL_V1"
            )

    def test_receiver_duplicate_is_acknowledged_without_second_row(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes.jsonl"
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            outcome = self.make_outcome()
            first = receiver.receive(outcome)
            second = receiver.receive(outcome)
            self.assertEqual(first.status, "RECORDED")
            self.assertEqual(second.status, "ALREADY_RECORDED")
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_receiver_restart_remains_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes.jsonl"
            outcome = self.make_outcome()
            first = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            first.receive(outcome)

            restarted = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            ack = restarted.receive(outcome)
            self.assertEqual(ack.status, "ALREADY_RECORDED")
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_receiver_recognizes_legacy_executed_candidate_row(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes.jsonl"
            CandidateOutcomeWriter(
                str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            ).append(
                observation_id="candidate-1",
                outcome_type="EXECUTED_TRADE",
                symbol="BTCUSDT",
                direction="LONG",
                payload={"r_multiple": 1.0},
            )
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            ack = receiver.receive(self.make_outcome())
            self.assertEqual(ack.status, "ALREADY_RECORDED")
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_receiver_rejects_wrong_environment_or_mode(self):
        with tempfile.TemporaryDirectory() as root:
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(Path(root) / "outcomes.jsonl"),
                environment="TESTNET",
                execution_mode="SHADOW",
            )
            with self.assertRaisesRegex(ValueError, "ENVIRONMENT_MISMATCH"):
                receiver.receive(self.make_outcome())

            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(Path(root) / "other.jsonl"),
                environment="LIVE",
                execution_mode="TRADE",
            )
            with self.assertRaisesRegex(ValueError, "EXECUTION_MODE_MISMATCH"):
                receiver.receive(self.make_outcome())

    def test_outcome_without_candidate_is_acked_without_learning_row(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes.jsonl"
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            ack = receiver.receive(
                self.make_outcome(candidate_observation_id=None)
            )
            self.assertEqual(ack.status, "RECORDED")
            self.assertFalse(path.exists())

    def test_execution_lifecycles_no_longer_import_learning_writer(self):
        for filename in (
            "engine/position_lifecycle.py",
            "engine/reconciliation.py",
        ):
            source = Path(filename).read_text(encoding="utf-8")
            self.assertNotIn("strategy.candidate_outcome", source)
            self.assertNotIn("CandidateOutcomeWriter", source)
            self.assertNotIn("CANDIDATE_OUTCOMES_PATH", source)
            self.assertIn("build_execution_outcome", source)

    def test_execution_worker_injects_one_outcome_publisher_into_both_close_paths(self):
        source = Path("workers/execution_worker.py").read_text(encoding="utf-8")
        self.assertIn("ExecutionOutcomeOutbox", source)
        reconciliation_block = source[
            source.index("ReconciliationLifecycle("):source.index("PositionLifecycle(")
        ]
        position_block = source[
            source.index("PositionLifecycle("):source.index("if position_lifecycle is not None")
        ]
        self.assertIn(
            "outcome_publisher=self.execution_outcome_publisher",
            reconciliation_block,
        )
        self.assertIn(
            "outcome_publisher=self.execution_outcome_publisher",
            position_block,
        )
        self.assertIn("NEW_ENTRY_BLOCKED_PENDING_EXECUTION_OUTCOME", source)


if __name__ == "__main__":
    unittest.main()
