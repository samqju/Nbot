import tempfile
import unittest
from pathlib import Path
from unittest import mock
from nbot.exchange.binance_live import LiveExchangeConfig
from nbot.execution.state import ExecutionStateStore
from nbot.execution.risk import RiskManager, RiskConfig
from nbot.execution.entry import EntryLifecycle, EntryLifecycleConfig, EntryProposal
from nbot.execution.emergency import EmergencyFlattener
from tests.test_mainnet_adapter import LiveHarness, armed

class MainnetLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self):
        clock = mock.patch("nbot.exchange.binance_testnet.time.time", return_value=1_800_000_001)
        clock.start()
        self.addCleanup(clock.stop)
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.cfg = LiveExchangeConfig(
            api_key="key",
            api_secret="secret",
            repo_root=self.root,
            max_session_entries=5,
            max_entry_notional_usd=100.0,
            entry_resolution_timeout_seconds=0.01,
            stop_resolution_timeout_seconds=0.01,
            close_settlement_retries=1,
            close_settlement_retry_seconds=0.0,
        )
        armed(self.cfg)

    def tearDown(self):
        self.td.cleanup()

    def _execute(self, side: str):
        ex = LiveHarness(self.cfg)
        ex.bid = 99.9
        ex.ask = 100.1
        ex.connect()
        self.addCleanup(ex.disconnect)
        state = ExecutionStateStore(
            self.root / "data/execution/real/execution_state.json",
            profile="live-trade",
            market_environment="LIVE",
        )
        state.set_entries_enabled(True)
        lifecycle = EntryLifecycle(
            exchange=ex,
            state=state,
            risk=RiskManager(RiskConfig(risk_per_trade_usd=.25, max_notional_usd=25, leverage=1)),
            emergency=EmergencyFlattener(exchange=ex, sleep=lambda _: None),
            config=EntryLifecycleConfig(
                profile="live-trade",
                market_environment="LIVE",
                allowed_entry_authorities=frozenset({"LIVE_LEARNED_EXPLICIT_TRIAL_V1"}),
                allowed_exit_policies=frozenset({"INTEGER_R_STEP_CONTROL"}),
            ),
        )
        proposal = EntryProposal(
            proposal_id=f"proposal-testnet-integration-{side.lower()}",
            generated_at_ms=1_799_999_999_900,
            expires_at_ms=1_800_000_001_000,
            profile="live-trade",
            market_environment="LIVE",
            symbol="BTCUSDT",
            side=side,
            reference_price=100.0,
            entry_authority="LIVE_LEARNED_EXPLICIT_TRIAL_V1",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
        )
        opened = lifecycle.execute(proposal, now_ms=1_800_000_000_000)
        return ex, state, opened

    def test_real_entry_lifecycle_long_against_testnet_adapter(self):
        ex, state, opened = self._execute("LONG")
        self.assertEqual(state.open_position, opened)
        self.assertIsNone(state.entry_inflight)
        self.assertEqual(ex.position_snapshot().side, "LONG")
        stop = ex.protective_stop_snapshot("BTCUSDT")
        self.assertIsNotNone(stop)
        self.assertEqual(stop.side, "LONG")

    def test_real_entry_lifecycle_short_against_testnet_adapter(self):
        ex, state, opened = self._execute("SHORT")
        self.assertEqual(state.open_position, opened)
        self.assertIsNone(state.entry_inflight)
        self.assertEqual(ex.position_snapshot().side, "SHORT")
        stop = ex.protective_stop_snapshot("BTCUSDT")
        self.assertIsNotNone(stop)
        self.assertEqual(stop.side, "SHORT")

    def test_restart_recovers_protection_then_records_close_exactly_once(self):
        from nbot.execution.outcomes import ExecutionDurableStore
        from nbot.execution.reconciliation import ReconciliationLifecycle
        ex, state, opened = self._execute("LONG")
        # Recreate all local persistence/lifecycle objects, keeping only
        # simulated exchange truth, just as after a process crash.
        durable = ExecutionDurableStore(self.root, profile="live-trade")
        lifecycle = ReconciliationLifecycle(
            exchange=ex, durable=durable, risk=RiskManager(RiskConfig(risk_per_trade_usd=.25, max_notional_usd=25, leverage=1)),
            emergency=EmergencyFlattener(exchange=ex, sleep=lambda _: None),
            now_ms=lambda: 1_800_000_000_200,
        )
        self.assertEqual(lifecycle.reconcile().status, "POSITION_RECONCILED")
        self.assertEqual(durable.state.open_position.proposal_id, opened.proposal_id)
        entries_before = len([c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order"])
        ex.close_position("BTCUSDT", "LONG", reason="TEST_RESTART")
        result = lifecycle.reconcile()
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        self.assertEqual(durable.outbox.pending_count(), 1)
        reloaded = ExecutionDurableStore(self.root, profile="live-trade")
        self.assertIsNone(reloaded.state.open_position)
        self.assertFalse(reloaded.state.reserve_proposal(opened.proposal_id))
        self.assertEqual(reloaded.outbox.pending_count(), 1)
        self.assertEqual(lifecycle.reconcile().status, "FLAT")
        posts = [c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order"]
        self.assertEqual(len(posts), entries_before + 1)  # only the explicit close
