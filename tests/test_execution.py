import ast
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import nbot.execution as execution_module
from nbot.execution import (
    AccountSnapshot,
    CloseFill,
    ExchangePosition,
    ExecutionConfig,
    ExecutionSafetyError,
    ExecutionStateStore,
    ExecutionWorker,
    Fill,
    INTEGER_R_STEP_CONTROL,
    NO_ENTRY_AUTHORITY,
    Quote,
)
from nbot.execution_protocol import (
    ExecutionProposal,
    PROTOCOL_VERSION,
    ProtocolValidationError,
    TradeResponse,
)


class FakeProposalClient:
    def __init__(self, response=None):
        self.response = response or TradeResponse.no_trade()
        self.calls = 0
        self.fail = False
        self.requests = []

    def request_trade(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.fail:
            raise ConnectionError("observer down")
        return self.response


class FakeOutcomeClient:
    def __init__(self):
        self.calls = 0
        self.outcomes = []
        self.fail = False

    def send_outcome(self, outcome):
        self.calls += 1
        if self.fail:
            raise ConnectionError("observer down")
        self.outcomes.append(outcome)
        return "RECORDED"


class FakeExchange:
    def __init__(self, now_ms=1_000_000):
        self.now_ms = now_ms
        self.connected = False
        self.healthy = True
        self.quote_value = Quote("BTCUSDT", 99.99, 100.01, now_ms)
        self.balance = 10_000.0
        self.position = None
        self.stop = None
        self.stop_updates = []
        self.ensure_stop_calls = 0
        self.fail_protection = False
        self.open_calls = 0
        self.close_calls = 0
        self.leverage = None

    def connect(self):
        self.connected = True

    def is_healthy(self):
        return self.healthy

    def quote(self, symbol):
        q = self.quote_value
        return Quote(symbol, q.bid, q.ask, q.timestamp_ms)

    def account_snapshot(self):
        return AccountSnapshot(self.balance)

    def position_snapshot(self):
        return self.position

    def validate_protective_stop(self, symbol, side, stop_price):
        return stop_price > 0

    def set_leverage(self, symbol, leverage):
        self.leverage = leverage

    def open_market(self, plan, *, client_order_id):
        self.open_calls += 1
        fill = Fill(plan.expected_entry_price, plan.quantity, "ORDER-1", client_order_id, self.now_ms)
        self.position = ExchangePosition(plan.symbol, plan.side, plan.quantity, fill.price)
        return fill

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        self.ensure_stop_calls += 1
        if self.fail_protection:
            raise RuntimeError("stop failed")
        self.stop = stop_price

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        self.stop = stop_price
        self.stop_updates.append(stop_price)

    def close_position(self, symbol, side, *, reason):
        self.close_calls += 1
        price = self.quote_value.bid if side == "LONG" else self.quote_value.ask
        self.position = None
        return CloseFill(price, self.now_ms + 1_000, reason)


def make_proposal(now_ms=1_000_000, **overrides):
    values = dict(
        proposal_id="PROP-001",
        environment="TESTNET",
        symbol="BTCUSDT",
        direction="LONG",
        generated_at_ms=now_ms - 1_000,
        expires_at_ms=now_ms + 30_000,
        reference_price=100.0,
        entry_authority="RESEARCH_CHAMPION_V1",
        model_version="RIDGE_EXPECTED_NET_R_V1",
        exit_policy_version=INTEGER_R_STEP_CONTROL,
        feature_version="CANONICAL_FEATURES_V1",
        data_generation_id="NBOT_V2_MARKET_EVIDENCE_V2_6",
        market_event_id="EVENT-001",
        advisory_initial_risk={"risk_unit": "ATR14_1X_RESEARCH_R_V1"},
        selection_score=0.5,
    )
    values.update(overrides)
    return ExecutionProposal.create(**values)


class ExecutionProtocolTests(unittest.TestCase):
    def test_proposal_round_trip_and_unknown_fields_rejected(self):
        proposal = make_proposal()
        parsed = ExecutionProposal.from_dict(proposal.to_dict())
        self.assertEqual(parsed, proposal)
        payload = proposal.to_dict()
        payload["unexpected"] = True
        with self.assertRaises(ProtocolValidationError):
            ExecutionProposal.from_dict(payload)

    def test_protocol_rejects_bad_expiry_and_environment(self):
        with self.assertRaises(ProtocolValidationError):
            make_proposal(expires_at_ms=998_999)
        with self.assertRaises(ProtocolValidationError):
            make_proposal(environment="LIVE_PUBLIC")
        self.assertEqual(PROTOCOL_VERSION, "NBOT_V2_EXECUTION_V1")


class ExecutionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1_000_000
        self.path = Path(self.tmp.name) / "execution.json"
        self.cfg = ExecutionConfig(
            environment="TESTNET",
            state_path=self.path,
            allowed_entry_authorities=("RESEARCH_CHAMPION_V1",),
            allowed_exit_policies=(INTEGER_R_STEP_CONTROL,),
        )
        self.exchange = FakeExchange(self.now)
        self.proposals = FakeProposalClient(TradeResponse.proposal_response(make_proposal(self.now)))
        self.outcomes = FakeOutcomeClient()
        self.worker = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            now_ms=lambda: self.now,
        )
        self.worker.prepare()
        self.worker.enable_new_entries()

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_config_has_no_entry_or_exit_authority(self):
        cfg = ExecutionConfig(state_path=self.path)
        cfg.validate()
        self.assertEqual(cfg.allowed_entry_authorities, ())
        self.assertEqual(cfg.allowed_exit_policies, ())
        worker = ExecutionWorker(cfg, FakeExchange(self.now), FakeProposalClient(), now_ms=lambda: self.now)
        self.assertEqual(worker.entry_authority, NO_ENTRY_AUTHORITY)

    def test_entry_requires_local_validation_and_duplicate_reservation(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.assertEqual(self.exchange.open_calls, 1)
        self.assertIsNotNone(self.worker.state.open_position)
        self.assertTrue(self.worker.state.has_processed("PROP-001"))
        self.assertIsNotNone(self.exchange.stop)

    def test_unapproved_authority_is_rejected_without_order(self):
        bad = make_proposal(self.now, proposal_id="PROP-BAD", entry_authority="UNAPPROVED_MODEL")
        self.proposals.response = TradeResponse.proposal_response(bad)
        result = self.worker.process_flat_cycle()
        self.assertEqual(result, "PROPOSAL_REJECTED:ENTRY_AUTHORITY_NOT_APPROVED")
        self.assertEqual(self.exchange.open_calls, 0)

    def test_observation_can_die_while_open_and_local_policy_still_closes(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        calls_after_entry = self.proposals.calls
        self.proposals.fail = True

        # >2R MFE moves the integer-R control stop to +1R.
        self.assertEqual(self.worker.process_open_price("BTCUSDT", 102.20, self.now + 2_000), "POSITION_MANAGED")
        self.assertEqual(self.proposals.calls, calls_after_entry)
        self.assertTrue(self.exchange.stop_updates)
        self.assertGreater(self.exchange.stop_updates[-1], self.worker.state.open_position["entry_price"])

        # Falling through that locally managed stop closes without Observation.
        self.exchange.quote_value = Quote("BTCUSDT", 100.50, 100.52, self.now + 3_000)
        self.assertEqual(self.worker.process_open_price("BTCUSDT", 100.50, self.now + 3_000), "POSITION_CLOSED")
        self.assertEqual(self.proposals.calls, calls_after_entry)
        self.assertIsNone(self.worker.state.open_position)
        self.assertEqual(len(self.worker.state.data["pending_outcomes"]), 1)

    def test_restart_recovers_and_reprotects_open_position_without_observer(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.proposals.fail = True
        state2 = ExecutionStateStore(self.path)
        worker2 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=state2, now_ms=lambda: self.now + 5_000,
        )
        calls = self.proposals.calls
        self.assertEqual(worker2.prepare(), "POSITION_OPEN")
        self.assertEqual(self.proposals.calls, calls)
        self.assertGreaterEqual(self.exchange.ensure_stop_calls, 2)
        self.assertEqual(worker2.reconcile_open_position(), "POSITION_RECONCILED")

    def test_protection_failure_emergency_closes_and_queues_outcome(self):
        self.exchange.fail_protection = True
        with self.assertRaisesRegex(ExecutionSafetyError, "PROTECTION_FAILED_EMERGENCY_CLOSED"):
            self.worker.process_flat_cycle()
        self.assertIsNone(self.exchange.position)
        self.assertEqual(self.exchange.close_calls, 1)
        self.assertEqual(len(self.worker.state.data["pending_outcomes"]), 1)

    def test_pending_outcome_is_delivered_before_next_request(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.exchange.quote_value = Quote("BTCUSDT", 98.50, 98.52, self.now + 2_000)
        self.worker.process_open_price("BTCUSDT", 98.50, self.now + 2_000)
        proposal_calls = self.proposals.calls
        self.outcomes.fail = True
        self.assertEqual(self.worker.process_flat_cycle(), "PENDING_OUTCOME")
        self.assertEqual(self.proposals.calls, proposal_calls)
        self.outcomes.fail = False
        self.proposals.response = TradeResponse.no_trade()
        self.assertEqual(self.worker.process_flat_cycle(), "NO_TRADE")
        self.assertEqual(len(self.worker.state.data["pending_outcomes"]), 0)
        self.assertEqual(self.outcomes.calls, 2)

    def test_reconciliation_fails_closed_on_unmanaged_exchange_position(self):
        path = Path(self.tmp.name) / "fresh.json"
        exchange = FakeExchange(self.now)
        exchange.position = ExchangePosition("BTCUSDT", "LONG", 1.0, 100.0)
        worker = ExecutionWorker(
            replace(self.cfg, state_path=path), exchange, FakeProposalClient(), now_ms=lambda: self.now,
        )
        with self.assertRaisesRegex(ExecutionSafetyError, "UNMANAGED_EXCHANGE_POSITION"):
            worker.prepare()

    def test_execution_module_imports_no_research_stack(self):
        tree = ast.parse(Path(execution_module.__file__).read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        forbidden = {"nbot.research", "nbot.selection", "nbot.champion", "nbot.observer"}
        self.assertFalse(imported & forbidden)

    def test_state_file_is_separate_from_observer_database(self):
        self.assertNotEqual(self.cfg.state_path.name, "observer.db")
        self.worker.state.save()
        payload = json.loads(self.path.read_text())
        self.assertEqual(payload["state_version"], "NBOT_V2_EXECUTION_STATE_V1")


if __name__ == "__main__":
    unittest.main()
