from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nbot.config.profiles import get_profile
from nbot.exchange.contracts import EntryPlan, Fill, ProtectiveStopRef, Quote
from nbot.exchange.paper import PaperExchange, PaperExchangeConfig
from nbot.execution.emergency import EmergencyConfig, EmergencyFlattener
from nbot.execution.entry import EntryLifecycle, EntryLifecycleConfig, EntryProposal, EntryRejected
from nbot.execution.execution import (
    ExecutionWorker,
    ExecutionWorkerError,
    OutcomeClient,
    ProposalClient,
)
from nbot.execution.models import DailyRisk, EntryInflight, OpenPosition
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.position import (
    PositionLifecycle,
    PositionManageResult,
    PositionReconciliationRequired,
)
from nbot.execution.reconciliation import (
    ReconciliationConfig,
    ReconciliationCritical,
    ReconciliationLifecycle,
    ReconciliationResult,
)
from nbot.execution.risk import RiskConfig, RiskManager

NOW = 1_800_000_000_000
AUTHORITY = "TEST_AUTHORITY"
POLICY = "INTEGER_R_STEP_CONTROL"


def proposal(*, proposal_id: str = "P-1", symbol: str = "BTCUSDT", side: str = "LONG") -> EntryProposal:
    return EntryProposal(
        proposal_id=proposal_id,
        generated_at_ms=NOW - 1_000,
        expires_at_ms=NOW + 30_000,
        profile="live-paper",
        market_environment="LIVE",
        symbol=symbol,
        side=side,
        reference_price=100.0,
        entry_authority=AUTHORITY,
        exit_policy_version=POLICY,
    )


def seed_open(state, *, proposal_id: str = "P-OPEN", side: str = "LONG") -> OpenPosition:
    stop_price = 99.0 if side == "LONG" else 101.0
    plan = EntryPlan(
        symbol="BTCUSDT",
        side=side,
        quantity=10.0,
        expected_entry_price=100.0,
        initial_stop_price=stop_price,
        initial_risk_usd=10.0,
        notional_usd=1000.0,
        leverage=5,
    )
    fill = Fill(100.0, 10.0, "ORDER-1", f"CID-{proposal_id}", NOW - 5_000)
    inflight = EntryInflight(
        proposal_id=proposal_id,
        entry_authority=AUTHORITY,
        exit_policy_version=POLICY,
        plan=plan,
        client_order_id=fill.client_order_id,
        started_at_ms=NOW - 6_000,
    )
    state.reserve_proposal(proposal_id)
    state.begin_entry(inflight)
    state.record_inflight_fill(fill)
    pos = OpenPosition(
        proposal_id=proposal_id,
        symbol="BTCUSDT",
        side=side,
        entry_fill=fill,
        initial_risk_usd=10.0,
        initial_stop_price=stop_price,
        protective_stop=ProtectiveStopRef(
            "BTCUSDT", side, 10.0, stop_price, stop_id=f"STOP-{proposal_id}"
        ),
        entry_authority=AUTHORITY,
        exit_policy_version=POLICY,
    )
    state.promote_inflight_position(pos)
    return pos


class FakeExchange:
    def connect(self):
        pass

    def __init__(self, events: list[str]):
        self.events = events
        self.tick_error: Exception | None = None

    def on_market_tick(self, *, symbol, bid, ask, timestamp_ms):
        self.events.append("market_tick")
        if self.tick_error:
            raise self.tick_error
        return None


class FakeReconciliation:
    def __init__(self, state, exchange, risk, events):
        self.state = state
        self.exchange = exchange
        self.risk = risk
        self.events = events
        self.result = ReconciliationResult(status="FLAT")
        self.error: Exception | None = None
        self.callback = None

    def reconcile(self):
        self.events.append("reconcile")
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return self.result


class FakePosition:
    def __init__(self, state, exchange, risk, events):
        self.state = state
        self.exchange = exchange
        self.risk = risk
        self.events = events
        self.result = PositionManageResult(status="POSITION_MANAGED", symbol="BTCUSDT")
        self.error: Exception | None = None

    def manage_tick(self, symbol, price, timestamp_ms):
        self.events.append("position")
        if self.error:
            raise self.error
        return self.result


class FakeEntry:
    def __init__(self, state, exchange, risk, events):
        self.state = state
        self.exchange = exchange
        self.risk = risk
        self.events = events
        self.error: Exception | None = None
        self.open_on_execute = True

    def execute(self, item, *, now_ms):
        self.events.append("entry")
        if self.error:
            raise self.error
        if self.open_on_execute:
            seed_open(self.state, proposal_id=item.proposal_id, side=item.side)
        return self.state.open_position


class FakeProposalClient:
    def __init__(self, events, value=None, error=None):
        self.events = events
        self.value = value
        self.error = error
        self.calls = []

    def request_proposal(self, **kwargs):
        self.events.append("proposal")
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.value


class FakeOutcomeClient:
    def __init__(self, events, *, ack_mode="exact", fail_on=None):
        self.events = events
        self.ack_mode = ack_mode
        self.fail_on = fail_on
        self.calls = []

    def send_outcome(self, *, outcome_id, payload):
        self.events.append(f"outcome:{outcome_id}")
        self.calls.append((outcome_id, payload))
        if self.fail_on == outcome_id:
            raise RuntimeError("offline")
        if self.ack_mode == "wrong":
            return "WRONG-ID"
        if self.ack_mode == "none":
            return None
        return outcome_id


class WorkerHarness:
    def __init__(self, root: Path):
        self.events: list[str] = []
        self.durable = ExecutionDurableStore(root, profile="live-paper")
        self.risk = RiskManager(RiskConfig())
        self.exchange = FakeExchange(self.events)
        self.entry = FakeEntry(self.durable.state, self.exchange, self.risk, self.events)
        self.position = FakePosition(self.durable.state, self.exchange, self.risk, self.events)
        self.reconciliation = FakeReconciliation(
            self.durable.state, self.exchange, self.risk, self.events
        )
        self.proposals = FakeProposalClient(self.events)
        self.outcomes = FakeOutcomeClient(self.events)
        self.worker = ExecutionWorker(
            exchange=self.exchange,
            durable=self.durable,
            risk=self.risk,
            entry=self.entry,
            position=self.position,
            reconciliation=self.reconciliation,
            proposal_client=self.proposals,
            outcome_client=self.outcomes,
            now_ms=lambda: NOW,
        )


class ExecutionWorkerShapeTests(unittest.TestCase):
    def test_fake_clients_satisfy_transport_neutral_protocols(self):
        events = []
        self.assertIsInstance(FakeProposalClient(events), ProposalClient)
        self.assertIsInstance(FakeOutcomeClient(events), OutcomeClient)

    def test_constructor_rejects_different_state_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            other = ExecutionDurableStore(Path(tmp) / "other", profile="live-paper")
            h.entry.state = other.state
            with self.assertRaisesRegex(ValueError, "EXECUTION_WORKER_STATE_IDENTITY_MISMATCH"):
                ExecutionWorker(
                    exchange=h.exchange, durable=h.durable, risk=h.risk,
                    entry=h.entry, position=h.position, reconciliation=h.reconciliation,
                )

    def test_constructor_rejects_different_exchange_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.position.exchange = FakeExchange([])
            with self.assertRaisesRegex(ValueError, "EXECUTION_WORKER_EXCHANGE_IDENTITY_MISMATCH"):
                ExecutionWorker(
                    exchange=h.exchange, durable=h.durable, risk=h.risk,
                    entry=h.entry, position=h.position, reconciliation=h.reconciliation,
                )

    def test_constructor_rejects_different_risk_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.reconciliation.risk = RiskManager(RiskConfig())
            with self.assertRaisesRegex(ValueError, "EXECUTION_WORKER_RISK_IDENTITY_MISMATCH"):
                ExecutionWorker(
                    exchange=h.exchange, durable=h.durable, risk=h.risk,
                    entry=h.entry, position=h.position, reconciliation=h.reconciliation,
                )


class ExecutionWorkerPreparationTests(unittest.TestCase):
    def test_prepare_reconciles_without_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.worker.proposal_client = None
            h.worker.outcome_client = None
            result = h.worker.prepare()
            self.assertEqual(result.status, "FLAT")
            self.assertEqual(h.events, ["reconcile"])
            self.assertTrue(h.worker.prepared)
            self.assertEqual(h.durable.state.health.prepare_calls, 1)

    def test_prepare_reloads_state_after_exclusive_exchange_connect(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            def concurrent_writer_finishes_before_lock_acquired():
                latest = ExecutionDurableStore(Path(tmp), profile="live-paper")
                latest.state.reserve_proposal("OTHER_PROCESS_COMPLETED")
            h.exchange.connect = concurrent_writer_finishes_before_lock_acquired
            h.worker.prepare()
            self.assertTrue(h.durable.state.has_processed_proposal("OTHER_PROCESS_COMPLETED"))

    def test_prepare_failure_leaves_worker_unprepared(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.reconciliation.error = ReconciliationCritical("UNMANAGED_EXCHANGE_POSITION")
            with self.assertRaises(ReconciliationCritical):
                h.worker.prepare()
            self.assertFalse(h.worker.prepared)
            self.assertNotIn("proposal", h.events)

    def test_enable_entries_reconciles_before_enabling(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self.assertFalse(h.durable.state.snapshot.entries_enabled)
            h.worker.enable_new_entries()
            self.assertEqual(h.events[0], "reconcile")
            self.assertTrue(h.durable.state.snapshot.entries_enabled)

    def test_enable_entries_fails_if_reconciliation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.reconciliation.error = ReconciliationCritical("UNMANAGED_EXCHANGE_POSITION")
            with self.assertRaises(ReconciliationCritical):
                h.worker.enable_new_entries()
            self.assertFalse(h.durable.state.snapshot.entries_enabled)

    def test_disable_entries_never_contacts_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.durable.state.set_entries_enabled(True)
            h.worker.disable_new_entries()
            self.assertFalse(h.durable.state.snapshot.entries_enabled)
            self.assertNotIn("proposal", h.events)
            self.assertFalse(any(e.startswith("outcome:") for e in h.events))

    def test_explicit_reconcile_never_contacts_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.worker.reconcile()
            self.assertEqual(h.events, ["reconcile"])


class ExecutionWorkerFlatCycleTests(unittest.TestCase):
    def _armed(self, h: WorkerHarness):
        h.durable.state.set_entries_enabled(True)

    def test_reconciliation_happens_before_entry_disabled_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            result = h.worker.process_flat_cycle()
            self.assertEqual(result, "ENTRY_DISABLED")
            self.assertEqual(h.events, ["reconcile"])

    def test_open_position_blocks_all_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_OPEN", symbol="BTCUSDT")
            result = h.worker.process_flat_cycle()
            self.assertEqual(result, "POSITION_OPEN")
            self.assertEqual(h.events, ["reconcile"])

    def test_pending_outcome_without_client_blocks_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.worker.outcome_client = None
            h.durable.outbox.enqueue("OUT-1", {"outcome_id": "OUT-1"})
            result = h.worker.process_flat_cycle()
            self.assertEqual(result, "PENDING_OUTCOME")
            self.assertNotIn("proposal", h.events)
            self.assertEqual(h.durable.outbox.pending_count(), 1)

    def test_outcome_delivery_failure_blocks_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.outcomes.fail_on = "OUT-1"
            h.durable.outbox.enqueue("OUT-1", {"outcome_id": "OUT-1"})
            self.assertEqual(h.worker.process_flat_cycle(), "PENDING_OUTCOME")
            self.assertEqual(h.events, ["reconcile", "outcome:OUT-1"])
            self.assertEqual(h.durable.outbox.pending_count(), 1)

    def test_wrong_ack_blocks_and_retains_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.outcomes.ack_mode = "wrong"
            h.durable.outbox.enqueue("OUT-1", {"outcome_id": "OUT-1"})
            self.assertEqual(h.worker.process_flat_cycle(), "PENDING_OUTCOME")
            self.assertEqual(h.durable.outbox.pending_count(), 1)
            self.assertNotIn("proposal", h.events)

    def test_exact_ack_removes_outcome_before_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.durable.outbox.enqueue("OUT-1", {"outcome_id": "OUT-1"})
            h.proposals.value = None
            self.assertEqual(h.worker.process_flat_cycle(), "NO_TRADE")
            self.assertEqual(h.events, ["reconcile", "outcome:OUT-1", "proposal"])
            self.assertEqual(h.durable.outbox.pending_count(), 0)

    def test_multiple_outcomes_are_acked_in_durable_order_before_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.durable.outbox.enqueue("OUT-A", {"outcome_id": "OUT-A"})
            h.durable.outbox.enqueue("OUT-B", {"outcome_id": "OUT-B"})
            self.assertEqual(h.worker.process_flat_cycle(), "NO_TRADE")
            self.assertEqual(h.events[0], "reconcile")
            self.assertEqual(h.events[-1], "proposal")
            self.assertEqual(len(h.outcomes.calls), 2)
            self.assertEqual(h.durable.outbox.pending_count(), 0)

    def test_second_outcome_failure_leaves_only_failed_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.durable.outbox.enqueue("OUT-A", {"outcome_id": "OUT-A"})
            h.durable.outbox.enqueue("OUT-B", {"outcome_id": "OUT-B"})
            # Sort order is by hashed filename, so discover the actual second ID.
            ordered = [row["record_id"] for row in h.durable.outbox.pending()]
            h.outcomes.fail_on = ordered[1]
            self.assertEqual(h.worker.process_flat_cycle(), "PENDING_OUTCOME")
            self.assertEqual([row["record_id"] for row in h.durable.outbox.pending()], [ordered[1]])
            self.assertNotIn("proposal", h.events)

    def test_missing_proposal_client_stays_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.worker.proposal_client = None
            self.assertEqual(h.worker.process_flat_cycle(), "PROPOSAL_UNAVAILABLE")
            self.assertIsNone(h.durable.state.open_position)

    def test_proposal_client_exception_stays_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.proposals.error = RuntimeError("offline")
            self.assertEqual(h.worker.process_flat_cycle(), "PROPOSAL_UNAVAILABLE")
            self.assertIsNone(h.durable.state.open_position)

    def test_none_proposal_is_no_trade(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            self.assertEqual(h.worker.process_flat_cycle(), "NO_TRADE")
            self.assertEqual(h.events, ["reconcile", "proposal"])

    def test_proposal_context_is_execution_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.worker.process_flat_cycle()
            call = h.proposals.calls[0]
            self.assertEqual(call["profile"], "live-paper")
            self.assertEqual(call["market_environment"], "LIVE")
            self.assertEqual(call["execution_instance_id"], h.durable.state.snapshot.execution_instance_id)
            self.assertEqual(call["requested_at_ms"], NOW)

    def test_entry_rejection_returns_reason_and_counts_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.proposals.value = proposal()
            h.entry.error = EntryRejected("SPREAD_TOO_WIDE")
            self.assertEqual(h.worker.process_flat_cycle(), "PROPOSAL_REJECTED:SPREAD_TOO_WIDE")
            self.assertEqual(h.durable.state.health.proposal_rejections, 1)
            self.assertIsNone(h.durable.state.open_position)

    def test_entry_success_requires_durable_open_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.proposals.value = proposal()
            h.entry.open_on_execute = False
            with self.assertRaisesRegex(ExecutionWorkerError, "ENTRY_RETURNED_WITHOUT_OPEN_STATE"):
                h.worker.process_flat_cycle()

    def test_entry_success_opens_exactly_one_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            h.proposals.value = proposal(proposal_id="P-ENTRY")
            self.assertEqual(h.worker.process_flat_cycle(), "ENTRY_OPENED")
            self.assertEqual(h.durable.state.open_position.proposal_id, "P-ENTRY")
            self.assertIsNone(h.durable.state.entry_inflight)
            self.assertEqual(h.events, ["reconcile", "proposal", "entry"])

    def test_daily_halt_blocks_before_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            self._armed(h)
            day = h.risk.utc_day(NOW)
            h.durable.state.set_daily_risk(DailyRisk(
                utc_day=day,
                realized_pnl_usd=-1000.0,
                peak_realized_pnl_usd=0.0,
                loss_floor_usd=-950.0,
                halted=True,
                halt_reason="DAILY_LOSS_FLOOR_BREACH",
            ))
            self.assertEqual(h.worker.process_flat_cycle(), "DAILY_BLOCKED")
            self.assertNotIn("proposal", h.events)

    def test_flat_cycle_counter_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.worker.process_flat_cycle()
            h.worker.process_flat_cycle()
            self.assertEqual(h.durable.state.health.flat_cycles, 2)


class ExecutionWorkerOpenHotPathTests(unittest.TestCase):
    def test_unprepared_open_quote_prepares_without_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_OPEN", symbol="BTCUSDT")
            result = h.worker.process_open_quote(Quote("BTCUSDT", 100.0, 100.2, NOW))
            self.assertEqual(result.status, "POSITION_MANAGED")
            self.assertEqual(h.events, ["reconcile", "market_tick", "position"])
            self.assertNotIn("proposal", h.events)
            self.assertFalse(any(e.startswith("outcome:") for e in h.events))

    def test_irrelevant_symbol_is_ignored_before_exchange_tick(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_OPEN", symbol="BTCUSDT")
            h.worker.prepare()
            h.events.clear()
            result = h.worker.process_open_quote(Quote("ETHUSDT", 100.0, 100.2, NOW))
            self.assertEqual(result.status, "IGNORED_OTHER_SYMBOL")
            self.assertEqual(h.events, [])

    def test_matching_quote_feeds_exchange_before_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_OPEN", symbol="BTCUSDT")
            h.worker.prepare()
            h.events.clear()
            h.worker.process_open_quote(Quote("BTCUSDT", 100.0, 100.2, NOW))
            self.assertEqual(h.events, ["market_tick", "position"])

    def test_market_tick_failure_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_OPEN", symbol="BTCUSDT")
            h.worker.prepare()
            h.exchange.tick_error = RuntimeError("paper corrupt")
            with self.assertRaisesRegex(ExecutionWorkerError, "EXCHANGE_MARKET_TICK_FAILED"):
                h.worker.process_open_quote(Quote("BTCUSDT", 100.0, 100.2, NOW))

    def test_position_reconciliation_required_stays_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_OPEN", symbol="BTCUSDT")
            h.worker.prepare()
            h.events.clear()
            h.position.error = PositionReconciliationRequired("PROTECTIVE_STOP_MISSING")
            result = h.worker.process_open_quote(Quote("BTCUSDT", 100.0, 100.2, NOW))
            self.assertEqual(result.status, "POSITION_OPEN")
            self.assertEqual(h.events, ["market_tick", "position", "reconcile"])
            self.assertNotIn("proposal", h.events)
            self.assertFalse(any(e.startswith("outcome:") for e in h.events))

    def test_outcome_created_during_open_reconcile_is_not_delivered_on_hot_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            seed_open(h.durable.state)
            h.reconciliation.result = ReconciliationResult(status="POSITION_CLOSE_RECOVERED", outcome_id="OUT-X")
            h.worker.prepare()
            h.events.clear()
            h.position.error = PositionReconciliationRequired("EXCHANGE_POSITION_CLOSED")
            def create_outcome():
                if h.durable.outbox.pending_count() == 0:
                    h.durable.outbox.enqueue("OUT-X", {"outcome_id": "OUT-X"})
            h.reconciliation.callback = create_outcome
            result = h.worker.process_open_quote(Quote("BTCUSDT", 100.0, 100.2, NOW))
            self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
            self.assertEqual(h.durable.outbox.pending_count(), 1)
            self.assertFalse(any(e.startswith("outcome:") for e in h.events))

    def test_flat_open_quote_does_not_contact_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            h.worker.prepare()
            h.events.clear()
            result = h.worker.process_open_quote(Quote("BTCUSDT", 100.0, 100.2, NOW))
            self.assertEqual(result.status, "FLAT")
            self.assertEqual(h.events, [])

    def test_invalid_quote_object_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = WorkerHarness(Path(tmp))
            with self.assertRaisesRegex(ExecutionWorkerError, "EXECUTION_QUOTE_CONTRACT_INVALID"):
                h.worker.process_open_quote(object())  # type: ignore[arg-type]


class MutableMarketData:
    def __init__(self):
        self.connected = False
        self.healthy = True
        self.quotes = {"BTCUSDT": Quote("BTCUSDT", 99.9, 100.0, NOW)}

    def connect(self):
        self.connected = True

    def is_healthy(self):
        return self.connected and self.healthy

    def quote(self, symbol):
        return self.quotes[symbol]


class PaperIntegrationTests(unittest.TestCase):
    def build(self, root: Path, proposal_client=None, outcome_client=None):
        profile = get_profile("live-paper")
        market = MutableMarketData()
        exchange = PaperExchange(
            repo_root=root,
            profile=profile,
            market_data=market,
            config=PaperExchangeConfig(
                starting_balance_usd=10_000.0,
                entry_slippage_pct=0.0,
                exit_slippage_pct=0.0,
                taker_fee_rate=0.0,
            ),
        )
        durable = ExecutionDurableStore(root, profile="live-paper")
        risk = RiskManager(RiskConfig())
        emergency = EmergencyFlattener(
            exchange=exchange,
            config=EmergencyConfig(max_attempts=2, verify_delay_seconds=0.0),
            sleep=lambda _: None,
        )
        entry = EntryLifecycle(
            exchange=exchange,
            state=durable.state,
            risk=risk,
            emergency=emergency,
            config=EntryLifecycleConfig(
                profile="live-paper",
                market_environment="LIVE",
                allowed_entry_authorities=frozenset({AUTHORITY}),
                allowed_exit_policies=frozenset({POLICY}),
            ),
        )
        position = PositionLifecycle(
            exchange=exchange,
            state=durable.state,
            risk=risk,
            emergency=emergency,
        )
        reconciliation = ReconciliationLifecycle(
            exchange=exchange,
            durable=durable,
            risk=risk,
            emergency=emergency,
            config=ReconciliationConfig(
                stop_trigger_grace_seconds=0.0,
                stop_trigger_poll_interval_seconds=0.01,
            ),
            now_ms=lambda: NOW,
            sleep=lambda _: None,
        )
        worker = ExecutionWorker(
            exchange=exchange,
            durable=durable,
            risk=risk,
            entry=entry,
            position=position,
            reconciliation=reconciliation,
            proposal_client=proposal_client,
            outcome_client=outcome_client,
            now_ms=lambda: NOW,
        )
        return worker, durable, exchange, market

    def test_real_components_flat_prepare_and_enable(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker, durable, _, _ = self.build(Path(tmp))
            self.assertEqual(worker.prepare().status, "FLAT")
            worker.enable_new_entries()
            self.assertTrue(durable.state.snapshot.entries_enabled)

    def test_real_entry_lifecycle_opens_paper_position_through_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = []
            client = FakeProposalClient(events, proposal(proposal_id="P-REAL"))
            worker, durable, _, _ = self.build(Path(tmp), proposal_client=client)
            worker.enable_new_entries()
            self.assertEqual(worker.process_flat_cycle(), "ENTRY_OPENED")
            self.assertEqual(durable.state.open_position.proposal_id, "P-REAL")
            self.assertEqual(len(client.calls), 1)

    def test_real_position_management_uses_execution_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeProposalClient([], proposal(proposal_id="P-MANAGE"))
            worker, durable, _, _ = self.build(Path(tmp), proposal_client=client)
            worker.enable_new_entries()
            worker.process_flat_cycle()
            result = worker.process_open_quote(Quote("BTCUSDT", 101.0, 101.1, NOW + 1_000))
            self.assertEqual(result.status, "POSITION_MANAGED")
            self.assertGreaterEqual(durable.state.open_position.mfe_r, 1.0)

    def test_paper_stop_close_is_reconciled_and_queued_without_hot_path_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            proposal_client = FakeProposalClient([], proposal(proposal_id="P-STOP"))
            outcome_client = FakeOutcomeClient([])
            worker, durable, _, _ = self.build(
                Path(tmp), proposal_client=proposal_client, outcome_client=outcome_client
            )
            worker.enable_new_entries()
            worker.process_flat_cycle()
            stop = durable.state.open_position.stop_price
            result = worker.process_open_quote(
                Quote("BTCUSDT", stop - 0.1, stop, NOW + 2_000)
            )
            self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
            self.assertIsNone(durable.state.open_position)
            self.assertEqual(durable.outbox.pending_count(), 1)
            self.assertEqual(outcome_client.calls, [])

    def test_next_flat_cycle_acks_recovered_paper_outcome_before_new_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            proposal_events = []
            proposal_client = FakeProposalClient(proposal_events, proposal(proposal_id="P-CLOSE"))
            outcome_events = []
            outcome_client = FakeOutcomeClient(outcome_events)
            worker, durable, _, _ = self.build(
                Path(tmp), proposal_client=proposal_client, outcome_client=outcome_client
            )
            worker.enable_new_entries()
            worker.process_flat_cycle()
            stop = durable.state.open_position.stop_price
            worker.process_open_quote(Quote("BTCUSDT", stop - 0.1, stop, NOW + 2_000))
            proposal_client.value = None
            self.assertEqual(worker.process_flat_cycle(), "NO_TRADE")
            self.assertEqual(durable.outbox.pending_count(), 0)
            self.assertEqual(len(outcome_client.calls), 1)
            self.assertEqual(len(proposal_client.calls), 2)

    def test_restart_adopts_existing_paper_open_without_any_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_client = FakeProposalClient([], proposal(proposal_id="P-RESTART"))
            first, first_durable, _, _ = self.build(root, proposal_client=first_client)
            first.enable_new_entries()
            self.assertEqual(first.process_flat_cycle(), "ENTRY_OPENED")
            self.assertIsNotNone(first_durable.state.open_position)

            restarted, restarted_durable, _, _ = self.build(root)
            restarted.proposal_client = None
            restarted.outcome_client = None
            result = restarted.prepare()
            self.assertEqual(result.status, "POSITION_RECONCILED")
            self.assertEqual(restarted_durable.state.open_position.proposal_id, "P-RESTART")
            managed = restarted.process_open_quote(
                Quote("BTCUSDT", 100.1, 100.2, NOW + 3_000)
            )
            self.assertEqual(managed.status, "POSITION_MANAGED")

    def test_pending_close_survives_restart_and_blocks_new_proposal_without_ack_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = FakeProposalClient([], proposal(proposal_id="P-PENDING-RESTART"))
            first, durable, _, _ = self.build(root, proposal_client=client)
            first.enable_new_entries()
            first.process_flat_cycle()
            stop = durable.state.open_position.stop_price
            first.process_open_quote(Quote("BTCUSDT", stop - 0.1, stop, NOW + 2_000))
            self.assertEqual(durable.outbox.pending_count(), 1)

            proposal_after_restart = FakeProposalClient([], proposal(proposal_id="P-MUST-NOT-RUN"))
            restarted, restarted_durable, _, _ = self.build(
                root, proposal_client=proposal_after_restart, outcome_client=None
            )
            self.assertEqual(restarted.process_flat_cycle(), "PENDING_OUTCOME")
            self.assertEqual(proposal_after_restart.calls, [])
            self.assertEqual(restarted_durable.outbox.pending_count(), 1)


if __name__ == "__main__":
    unittest.main()
