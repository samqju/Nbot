import ast
import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

import nbot.execution as execution_module
from nbot.execution import (
    AccountSnapshot,
    CloseFill,
    ExchangePosition,
    ExecutionConfig,
    ExecutionInstanceLock,
    ExecutionSafetyError,
    ExecutionStateStore,
    ExecutionWorker,
    Fill,
    INTEGER_R_STEP_CONTROL,
    ProtectiveStopRef,
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
        self.stop_trigger_override = None
        self.stop_updates = []
        self.ensure_stop_calls = 0
        self.fail_protection = False
        self.open_calls = 0
        self.open_market_probe = None
        self.fill_price = None
        self.fill_quantity = None
        self.recover_inflight_calls = 0
        self.inflight_fill = None
        self.inflight_recovery_error = None
        self.close_calls = 0
        self.close_leave_open_attempts = 0
        self.recover_calls = 0
        self.recovery_error = None
        self.recovery_close = CloseFill(98.0, now_ms + 2_000, "EXCHANGE_FLAT_RECOVERED_AFTER_RESTART", -2.0, ("CLOSE-1",), "FAKE_RECOVERY")
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
        if self.open_market_probe is not None:
            self.open_market_probe(plan, client_order_id)
        fill_price = plan.expected_entry_price if self.fill_price is None else float(self.fill_price)
        fill_quantity = plan.quantity if self.fill_quantity is None else float(self.fill_quantity)
        fill = Fill(fill_price, fill_quantity, "ORDER-1", client_order_id, self.now_ms)
        self.position = ExchangePosition(plan.symbol, plan.side, fill.quantity, fill.price)
        return fill

    def recover_inflight_entry(self, plan, *, client_order_id):
        self.recover_inflight_calls += 1
        if self.inflight_recovery_error is not None:
            raise self.inflight_recovery_error
        return self.inflight_fill

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        self.ensure_stop_calls += 1
        if self.fail_protection:
            raise RuntimeError("stop failed")
        trigger = float(stop_price) if self.stop_trigger_override is None else float(self.stop_trigger_override)
        self.stop = trigger
        return ProtectiveStopRef(trigger, "STOP-1", "STOP-CID-1")

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        self.stop = stop_price
        self.stop_updates.append(stop_price)
        return ProtectiveStopRef(stop_price, f"STOP-{len(self.stop_updates)+1}", f"STOP-CID-{len(self.stop_updates)+1}")

    def close_position(self, symbol, side, *, reason):
        self.close_calls += 1
        price = self.quote_value.bid if side == "LONG" else self.quote_value.ask
        if self.close_calls > self.close_leave_open_attempts:
            self.position = None
        return CloseFill(price, self.now_ms + 1_000, reason)

    def recover_closed_position(self, local_position):
        self.recover_calls += 1
        if self.recovery_error is not None:
            raise self.recovery_error
        return self.recovery_close


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


    def test_execution_instance_lock_is_single_process_and_released(self):
        lock_path = Path(self.tmp.name) / "execution.lock"
        first = ExecutionInstanceLock(lock_path).acquire()
        try:
            with self.assertRaisesRegex(ExecutionSafetyError, "EXECUTION_INSTANCE_LOCK_HELD"):
                ExecutionInstanceLock(lock_path).acquire()
        finally:
            first.release()
        with ExecutionInstanceLock(lock_path):
            self.assertTrue(lock_path.exists())

    def test_default_config_has_no_entry_or_exit_authority(self):
        cfg = ExecutionConfig(state_path=self.path)
        cfg.validate()
        self.assertEqual(cfg.allowed_entry_authorities, ())
        self.assertEqual(cfg.allowed_exit_policies, ())
        worker = ExecutionWorker(cfg, FakeExchange(self.now), FakeProposalClient(), now_ms=lambda: self.now)
        self.assertEqual(worker.entry_authority, NO_ENTRY_AUTHORITY)
        self.assertEqual(worker.status()["phase"], "V2.8")

    def test_entry_requires_local_validation_and_duplicate_reservation(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.assertEqual(self.exchange.open_calls, 1)
        self.assertIsNotNone(self.worker.state.open_position)
        self.assertTrue(self.worker.state.has_processed("PROP-001"))
        self.assertIsNotNone(self.exchange.stop)

    def test_entry_journal_is_durable_before_market_order_call(self):
        observed = {}

        def probe(_plan, client_order_id):
            payload = json.loads(self.path.read_text())
            observed.update(payload)
            self.assertEqual(payload["entry_inflight"]["client_order_id"], client_order_id)
            self.assertEqual(payload["entry_inflight"]["proposal"]["proposal_id"], "PROP-001")
            self.assertIsNone(payload["entry_inflight"]["fill"])
            self.assertIn("PROP-001", payload["processed_proposal_ids"])

        self.exchange.open_market_probe = probe
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.assertTrue(observed)
        self.assertIsNone(self.worker.state.entry_inflight)

    def test_restart_recovers_inflight_filled_entry_without_duplicate_order_and_uses_persisted_risk(self):
        path = Path(self.tmp.name) / "inflight.json"
        cfg1 = replace(self.cfg, state_path=path, risk_per_trade_usd=10.0)
        state = ExecutionStateStore(path)
        proposal = make_proposal(self.now, proposal_id="PROP-INFLIGHT")
        worker1 = ExecutionWorker(cfg1, self.exchange, self.proposals, self.outcomes, state=state, now_ms=lambda: self.now)
        plan = worker1._build_plan(proposal, 100.0)
        cid = "NBV28-PROP-INFLIGHT"
        self.assertTrue(state.reserve(proposal.proposal_id))
        state.begin_entry(proposal=proposal, plan=plan, client_order_id=cid, started_at_ms=self.now)

        fill = Fill(100.2, plan.quantity, "ENTRY-RECOVERED", cid, self.now + 50)
        self.exchange.inflight_fill = fill
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", plan.quantity, fill.price)

        # Simulate a config change after the crash. Recovery must retain the
        # exact risk contract that was persisted with the original entry.
        cfg2 = replace(cfg1, risk_per_trade_usd=50.0)
        worker2 = ExecutionWorker(
            cfg2, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(path), now_ms=lambda: self.now + 1_000,
        )
        self.assertEqual(worker2.prepare(), "POSITION_OPEN")
        self.assertEqual(self.exchange.open_calls, 0)
        self.assertEqual(self.exchange.recover_inflight_calls, 1)
        self.assertIsNone(worker2.state.entry_inflight)
        self.assertAlmostEqual(worker2.state.open_position["initial_risk_usd"], 10.0)
        expected_stop = fill.price - 10.0 / fill.quantity
        self.assertAlmostEqual(worker2.state.open_position["stop_price"], expected_stop)

    def test_restart_recovers_inflight_entry_that_closed_before_local_open_was_persisted(self):
        path = Path(self.tmp.name) / "inflight-closed.json"
        cfg = replace(self.cfg, state_path=path)
        state = ExecutionStateStore(path)
        proposal = make_proposal(self.now, proposal_id="PROP-INFLIGHT-CLOSED")
        worker1 = ExecutionWorker(cfg, self.exchange, self.proposals, self.outcomes, state=state, now_ms=lambda: self.now)
        plan = worker1._build_plan(proposal, 100.0)
        cid = "NBV28-PROP-INFLIGHT-CLOSED"
        state.reserve(proposal.proposal_id)
        state.begin_entry(proposal=proposal, plan=plan, client_order_id=cid, started_at_ms=self.now)
        fill = Fill(100.0, plan.quantity, "ENTRY-CLOSED", cid, self.now + 10)
        state.record_inflight_fill(fill)
        self.exchange.position = None
        self.exchange.recovery_close = CloseFill(
            101.0, self.now + 500, "PROTECTIVE_STOP_TRIGGERED", 9.75,
            ("STOP-CLOSE",), "EXCHANGE_RECOVERY", 10.0, -0.25,
        )

        worker2 = ExecutionWorker(
            cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(path), now_ms=lambda: self.now + 1_000,
        )
        self.assertEqual(worker2.prepare(), "RECOVERED_CLOSED_POSITION")
        self.assertIsNone(worker2.state.open_position)
        self.assertIsNone(worker2.state.entry_inflight)
        self.assertEqual(len(worker2.state.data["pending_outcomes"]), 1)
        self.assertAlmostEqual(worker2.state.data["pending_outcomes"][0]["realized_pnl_usd"], 9.75)

    def test_restart_clears_known_unfilled_inflight_entry_when_exchange_is_flat(self):
        path = Path(self.tmp.name) / "inflight-unfilled.json"
        cfg = replace(self.cfg, state_path=path)
        state = ExecutionStateStore(path)
        proposal = make_proposal(self.now, proposal_id="PROP-NOFILL")
        worker1 = ExecutionWorker(cfg, self.exchange, self.proposals, self.outcomes, state=state, now_ms=lambda: self.now)
        plan = worker1._build_plan(proposal, 100.0)
        state.reserve(proposal.proposal_id)
        state.begin_entry(proposal=proposal, plan=plan, client_order_id="NBV28-NOFILL", started_at_ms=self.now)
        self.exchange.inflight_fill = None
        self.exchange.position = None
        worker2 = ExecutionWorker(cfg, self.exchange, self.proposals, self.outcomes, state=ExecutionStateStore(path))
        self.assertEqual(worker2.prepare(), "FLAT")
        self.assertIsNone(worker2.state.entry_inflight)
        self.assertEqual(self.exchange.open_calls, 0)

    def test_restart_keeps_ambiguous_inflight_entry_fail_closed(self):
        path = Path(self.tmp.name) / "inflight-ambiguous.json"
        cfg = replace(self.cfg, state_path=path)
        state = ExecutionStateStore(path)
        proposal = make_proposal(self.now, proposal_id="PROP-AMB")
        worker1 = ExecutionWorker(cfg, self.exchange, self.proposals, self.outcomes, state=state, now_ms=lambda: self.now)
        plan = worker1._build_plan(proposal, 100.0)
        state.reserve(proposal.proposal_id)
        state.begin_entry(proposal=proposal, plan=plan, client_order_id="NBV28-AMB", started_at_ms=self.now)
        self.exchange.inflight_recovery_error = RuntimeError("exchange order identity unresolved")
        worker2 = ExecutionWorker(cfg, self.exchange, self.proposals, self.outcomes, state=ExecutionStateStore(path))
        with self.assertRaisesRegex(ExecutionSafetyError, "ENTRY_INFLIGHT_RECOVERY_FAILED"):
            worker2.prepare()
        self.assertIsNotNone(ExecutionStateStore(path).entry_inflight)

    def test_state_with_open_position_and_entry_inflight_is_rejected(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        payload = json.loads(self.path.read_text())
        payload["entry_inflight"] = {
            "proposal": make_proposal(self.now, proposal_id="PROP-IMPOSSIBLE").to_dict(),
            "plan": {}, "client_order_id": "x", "started_at_ms": self.now, "fill": None,
        }
        self.path.write_text(json.dumps(payload))
        worker2 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(self.path),
        )
        with self.assertRaisesRegex(ExecutionSafetyError, "OPEN_AND_ENTRY_INFLIGHT"):
            worker2.prepare()

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

    def test_restart_recovers_exchange_side_close_and_queues_exactly_one_outcome(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        original = dict(self.worker.state.open_position)
        self.exchange.position = None
        self.exchange.recovery_close = CloseFill(99.0, self.now + 6_000, "PROTECTIVE_STOP_TRIGGERED", -1.25, ("STOP-FILL-1",), "USER_TRADES_RECOVERY")

        worker2 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(self.path), now_ms=lambda: self.now + 7_000,
        )
        self.assertEqual(worker2.prepare(), "RECOVERED_CLOSED_POSITION")
        self.assertIsNone(worker2.state.open_position)
        self.assertEqual(self.exchange.recover_calls, 1)
        rows = worker2.state.data["pending_outcomes"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["realized_pnl_usd"], -1.25)
        self.assertEqual(rows[0]["exit_reason"], "PROTECTIVE_STOP_TRIGGERED")
        expected_id = worker2._deterministic_outcome_id(original)
        self.assertEqual(rows[0]["outcome_id"], expected_id)

    def test_recovered_close_delivery_is_idempotent_across_restart(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.worker.disable_new_entries()
        self.exchange.position = None
        self.exchange.recovery_close = CloseFill(99.0, self.now + 6_000, "PROTECTIVE_STOP_TRIGGERED", -1.0, ("STOP-FILL-1",), "USER_TRADES_RECOVERY")
        worker2 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(self.path), now_ms=lambda: self.now + 7_000,
        )
        self.assertEqual(worker2.prepare(), "RECOVERED_CLOSED_POSITION")
        outcome_id = worker2.state.data["pending_outcomes"][0]["outcome_id"]
        calls_before = self.proposals.calls
        self.assertEqual(worker2.process_flat_cycle(), "ENTRY_DISABLED")
        self.assertEqual(self.proposals.calls, calls_before)
        self.assertEqual(len(self.outcomes.outcomes), 1)
        self.assertEqual(self.outcomes.outcomes[0].outcome_id, outcome_id)
        self.assertEqual(worker2.state.data["pending_outcomes"], [])

        worker3 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(self.path), now_ms=lambda: self.now + 8_000,
        )
        self.assertEqual(worker3.prepare(), "FLAT")
        self.assertEqual(worker3.process_flat_cycle(), "ENTRY_DISABLED")
        self.assertEqual(len(self.outcomes.outcomes), 1)
        self.assertEqual(self.proposals.calls, calls_before)
        history = worker3.state.data["execution_outcome_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["outcome_id"], outcome_id)

    def test_exchange_realized_pnl_is_authoritative_and_local_variance_is_audit_only(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.worker.disable_new_entries()
        self.exchange.position = None
        self.exchange.recovery_close = CloseFill(
            101.0, self.now + 6_000, "PROTECTIVE_STOP_TRIGGERED",
            4.808575, ("STOP-FILL-ACCOUNTING",), "ALGO_ACTUAL_ORDER_INCOME_RECOVERY",
            4.806393, 0.002182,
        )
        worker2 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(self.path), now_ms=lambda: self.now + 7_000,
        )
        self.assertEqual(worker2.prepare(), "RECOVERED_CLOSED_POSITION")
        outcome = worker2.state.data["pending_outcomes"][0]
        self.assertAlmostEqual(outcome["realized_pnl_usd"], 4.808575)
        self.assertAlmostEqual(outcome["r_multiple"], 4.808575 / 10.0)
        audit = worker2.state.data["last_close_audit"]
        self.assertAlmostEqual(audit["exchange_realized_pnl_usd"], 4.808575)
        self.assertAlmostEqual(audit["theoretical_pnl_usd"], 4.806393)
        self.assertAlmostEqual(audit["pnl_variance_usd"], 0.002182)

    def test_external_close_recovery_failure_preserves_local_open_state(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        proposal_id = self.worker.state.open_position["proposal_id"]
        self.exchange.position = None
        self.exchange.recovery_error = RuntimeError("trade history unavailable")
        worker2 = ExecutionWorker(
            self.cfg, self.exchange, self.proposals, self.outcomes,
            state=ExecutionStateStore(self.path), now_ms=lambda: self.now + 7_000,
        )
        with self.assertRaisesRegex(ExecutionSafetyError, "EXTERNAL_CLOSE_RECOVERY_FAILED"):
            worker2.prepare()
        self.assertEqual(worker2.state.open_position["proposal_id"], proposal_id)
        self.assertEqual(worker2.state.data["pending_outcomes"], [])

    def test_stop_identity_is_persisted_on_entry_and_trailing_replacement(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        position = self.worker.state.open_position
        self.assertEqual(position["protective_stop_algo_id"], "STOP-1")
        self.assertEqual(position["protective_stop_client_algo_id"], "STOP-CID-1")
        self.worker.process_open_price("BTCUSDT", 102.20, self.now + 2_000)
        position = self.worker.state.open_position
        self.assertEqual(position["protective_stop_algo_id"], "STOP-2")
        self.assertEqual(position["protective_stop_client_algo_id"], "STOP-CID-2")

    def test_protection_failure_emergency_closes_and_queues_outcome(self):
        self.exchange.fail_protection = True
        with self.assertRaisesRegex(ExecutionSafetyError, "PROTECTION_FAILED_EMERGENCY_CLOSED"):
            self.worker.process_flat_cycle()
        self.assertIsNone(self.exchange.position)
        self.assertEqual(self.exchange.close_calls, 1)
        self.assertEqual(len(self.worker.state.data["pending_outcomes"]), 1)

    def test_operator_force_close_finalizes_locally_without_observer(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        calls_after_entry = self.proposals.calls
        self.proposals.fail = True
        self.assertEqual(
            self.worker.force_close_open_position(reason="OPERATOR_TESTNET_FLATTEN"),
            "POSITION_CLOSED",
        )
        self.assertEqual(self.proposals.calls, calls_after_entry)
        self.assertIsNone(self.worker.state.open_position)
        self.assertEqual(len(self.worker.state.data["pending_outcomes"]), 1)
        self.assertEqual(self.exchange.close_calls, 1)

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

    def test_corrupt_execution_state_fails_closed_instead_of_resetting(self):
        corrupt = Path(self.tmp.name) / "corrupt.json"
        corrupt.write_text('{"state_version":')
        with self.assertRaisesRegex(ExecutionSafetyError, "EXECUTION_STATE_CORRUPT"):
            ExecutionStateStore(corrupt)


    def test_v1_execution_policy_parity_defaults_are_explicit(self):
        cfg = ExecutionConfig(state_path=self.path)
        self.assertEqual(cfg.risk_per_trade_usd, 10.0)
        self.assertEqual(cfg.max_notional_usd, 1000.0)
        self.assertEqual(cfg.leverage, 5)
        self.assertEqual(cfg.risk_tolerance_pct, 10.0)
        self.assertEqual(cfg.notional_tolerance_pct, 1.0)
        self.assertEqual(cfg.max_entry_slippage_pct, 1.0)
        self.assertEqual(cfg.daily_profit_lock_trigger_r, 100.0)
        self.assertEqual(cfg.daily_normal_giveback_r, 95.0)
        self.assertEqual(cfg.daily_profit_giveback_r, 3.0)
        self.assertEqual(cfg.emergency_flatten_attempts, 2)

    def test_daily_risk_floor_preserves_v1_parity_default(self):
        daily = self.worker.status()["daily_risk"]
        self.assertEqual(daily["realized_pnl_usd"], 0.0)
        self.assertEqual(daily["peak_realized_pnl_usd"], 0.0)
        self.assertEqual(daily["loss_floor_usd"], -950.0)
        self.assertFalse(daily["halted"])

    def test_daily_profit_lock_halts_after_giveback_from_100r_peak(self):
        daily = dict(self.worker.state.data["daily_risk"])
        daily.update({
            "realized_pnl_usd": 1000.0,
            "peak_realized_pnl_usd": 1000.0,
            "loss_floor_usd": 970.0,
            "halted": False,
        })
        self.worker.state.set_daily_risk(daily)
        # A $40 giveback from +$1000 leaves +$960, below the V1-parity +$970 floor.
        outcome = type("Outcome", (), {"realized_pnl_usd": -40.0, "closed_timestamp_ms": self.now})()
        after = self.worker._daily_after_close(outcome)
        self.assertEqual(after["realized_pnl_usd"], 960.0)
        self.assertEqual(after["peak_realized_pnl_usd"], 1000.0)
        self.assertEqual(after["loss_floor_usd"], 970.0)
        self.assertTrue(after["halted"])
        self.assertEqual(after["halt_reason"], "DAILY_LOSS_FLOOR_BREACH")
        self.worker.state.set_daily_risk(after)
        self.worker.state.save()
        self.worker.disable_new_entries()
        with self.assertRaisesRegex(ExecutionSafetyError, "DAILY_RISK_HALT_ACTIVE"):
            self.worker.enable_new_entries()

    def test_utc_day_rollover_resets_daily_accounting_and_halt(self):
        daily = dict(self.worker.state.data["daily_risk"])
        daily.update({
            "realized_pnl_usd": -950.01,
            "peak_realized_pnl_usd": 0.0,
            "loss_floor_usd": -950.0,
            "halted": True,
            "halt_reason": "DAILY_LOSS_FLOOR_BREACH",
            "trades_closed": 7,
        })
        self.worker.state.set_daily_risk(daily)
        self.worker.state.save()
        next_day = self.now + 86_400_000
        self.worker._roll_daily(next_day)
        rolled = self.worker.state.data["daily_risk"]
        self.assertNotEqual(rolled["utc_day"], daily["utc_day"])
        self.assertEqual(rolled["realized_pnl_usd"], 0.0)
        self.assertEqual(rolled["peak_realized_pnl_usd"], 0.0)
        self.assertEqual(rolled["loss_floor_usd"], -950.0)
        self.assertEqual(rolled["trades_closed"], 0)
        self.assertFalse(rolled["halted"])

    def test_close_updates_daily_realized_peak_and_trade_count(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.exchange.quote_value = Quote("BTCUSDT", 101.0, 101.02, self.now + 1_000)
        self.assertEqual(self.worker.force_close_open_position(reason="OPERATOR_TEST"), "POSITION_CLOSED")
        daily = self.worker.state.data["daily_risk"]
        expected = (101.0 - 100.01) * (1000.0 / 100.01)
        self.assertAlmostEqual(daily["realized_pnl_usd"], expected)
        self.assertAlmostEqual(daily["peak_realized_pnl_usd"], expected)
        self.assertEqual(daily["trades_closed"], 1)
        self.assertAlmostEqual(daily["loss_floor_usd"], expected - 950.0)

    def test_risk_contract_breach_verified_emergency_flattens(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        # $10 initial risk with 10% tolerance means worse than -$11 is an emergency.
        self.exchange.quote_value = Quote("BTCUSDT", 98.8, 98.82, self.now + 2_000)
        self.assertEqual(self.worker.process_open_price("BTCUSDT", 98.8, self.now + 2_000), "POSITION_CLOSED")
        self.assertIsNone(self.exchange.position)
        self.assertIsNone(self.worker.state.open_position)
        self.assertEqual(self.exchange.close_calls, 1)
        self.assertEqual(self.worker.state.data["pending_outcomes"][-1]["exit_reason"], "RISK_CONTRACT_BREACH")

    def test_emergency_flatten_retries_and_verifies_exchange_flat(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.exchange.close_leave_open_attempts = 1
        self.assertEqual(self.worker.force_close_open_position(reason="EMERGENCY_TEST"), "POSITION_CLOSED")
        self.assertEqual(self.exchange.close_calls, 2)
        self.assertIsNone(self.exchange.position)
        self.assertIsNone(self.worker.state.open_position)

    def test_emergency_failure_keeps_local_position_fail_closed(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.exchange.close_leave_open_attempts = 99
        with self.assertRaisesRegex(ExecutionSafetyError, "EMERGENCY_EXIT_FAILED_NOT_FLAT"):
            self.worker.force_close_open_position(reason="EMERGENCY_TEST")
        self.assertIsNotNone(self.exchange.position)
        self.assertIsNotNone(self.worker.state.open_position)

    def test_post_fill_slippage_breach_is_protected_then_emergency_closed(self):
        self.exchange.fill_price = 102.0
        self.exchange.fill_quantity = 1000.0 / 102.0
        with self.assertRaisesRegex(ExecutionSafetyError, "POST_FILL_SLIPPAGE_BREACH_EMERGENCY_CLOSED"):
            self.worker.process_flat_cycle()
        self.assertGreaterEqual(self.exchange.ensure_stop_calls, 1)
        self.assertIsNone(self.exchange.position)
        self.assertIsNone(self.worker.state.open_position)
        self.assertEqual(self.worker.state.data["pending_outcomes"][-1]["exit_reason"], "POST_FILL_SLIPPAGE_BREACH")

    def test_post_fill_notional_breach_is_protected_then_emergency_closed(self):
        self.exchange.fill_quantity = 10.2
        with self.assertRaisesRegex(ExecutionSafetyError, "POST_FILL_NOTIONAL_BREACH_EMERGENCY_CLOSED"):
            self.worker.process_flat_cycle()
        self.assertGreaterEqual(self.exchange.ensure_stop_calls, 1)
        self.assertIsNone(self.exchange.position)
        self.assertEqual(self.worker.state.data["pending_outcomes"][-1]["exit_reason"], "POST_FILL_NOTIONAL_BREACH")

    def test_post_fill_risk_breach_is_protected_then_emergency_closed(self):
        self.exchange.stop_trigger_override = 98.0
        with self.assertRaisesRegex(ExecutionSafetyError, "POST_FILL_RISK_BREACH_EMERGENCY_CLOSED"):
            self.worker.process_flat_cycle()
        self.assertGreaterEqual(self.exchange.ensure_stop_calls, 1)
        self.assertIsNone(self.exchange.position)
        self.assertEqual(self.worker.state.data["pending_outcomes"][-1]["exit_reason"], "POST_FILL_RISK_BREACH")

    def test_health_status_tracks_hot_path_and_emergency_activity(self):
        self.assertEqual(self.worker.process_flat_cycle(), "ENTRY_OPENED")
        self.assertEqual(self.worker.process_open_price("BTCUSDT", 100.2, self.now + 1_000), "POSITION_MANAGED")
        status = self.worker.status()
        self.assertGreaterEqual(status["health"]["flat_cycles"], 1)
        self.assertGreaterEqual(status["health"]["open_position_ticks"], 1)
        self.assertGreaterEqual(status["health"]["last_position_manage_ms"], 0.0)
        self.assertEqual(status["risk_policy"]["risk_per_trade_usd"], 10.0)
        self.assertEqual(status["risk_policy"]["risk_tolerance_pct"], 10.0)

    def test_old_v284_state_without_daily_risk_migrates_safely(self):
        state = ExecutionStateStore(self.path)
        state.save()
        payload = json.loads(self.path.read_text())
        payload.pop("daily_risk", None)
        self.path.write_text(json.dumps(payload))
        migrated = ExecutionStateStore(self.path)
        self.assertIn("daily_risk", migrated.data)
        self.assertEqual(migrated.data["daily_risk"]["realized_pnl_usd"], 0.0)
        self.assertFalse(migrated.data["daily_risk"]["halted"])

    def test_v284_migration_reconstructs_current_day_from_durable_history(self):
        old_path = Path(self.tmp.name) / "old-v284.json"
        state = ExecutionStateStore(old_path)
        now_ms = int(time.time() * 1000)
        state.data["execution_outcome_history"] = [
            {
                "outcome_id": "OUT-MIGRATE",
                "closed_timestamp_ms": now_ms,
                "realized_pnl_usd": 12.5,
                "mfe_r": 2.0,
                "initial_risk_usd": 10.0,
            }
        ]
        state.save()
        payload = json.loads(old_path.read_text())
        payload.pop("daily_risk", None)
        old_path.write_text(json.dumps(payload))
        migrated = ExecutionStateStore(old_path)
        daily = migrated.data["daily_risk"]
        self.assertAlmostEqual(daily["realized_pnl_usd"], 12.5)
        self.assertAlmostEqual(daily["peak_realized_pnl_usd"], 12.5)
        self.assertAlmostEqual(daily["highest_unrealized_usd"], 20.0)
        self.assertEqual(daily["trades_closed"], 1)
        self.assertEqual(daily["utc_day"], ExecutionStateStore.utc_day(now_ms))


if __name__ == "__main__":
    unittest.main()
