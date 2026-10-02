import unittest
from unittest import mock
from tests import test_learned_testnet as fixtures
from nbot.communication.authorities import LIVE_LEARNED_AUTHORITY
from nbot.config.profiles import get_profile
from nbot.observation.learned_recommendation import LearnedTestnetSource
from nbot.observation.recommendation import ObservationControlTarget
from nbot.execution.risk import RiskConfig
from tests.communication.test_v35_control_target import NOW, SHA

class MainnetLearnedEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LearnedTestnetTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        source = LearnedTestnetSource(self.fixture.live, release_sha=SHA,
            profile_name="live-trade", memory_path=self.fixture.training.memory.path)
        self.target = ObservationControlTarget(self.fixture.live, get_profile("live-trade"),
            release_sha=SHA, now_ms=lambda: NOW, learned_source=source)

    def test_learned_http_order_stop_restart_close_and_ack_end_to_end(self):
        import run_execution
        from nbot.communication.client import RemoteObservationClient
        from nbot.communication.server import ObservationControlServer
        from nbot.communication.integration import V37IntegratedObservationClient
        from tests.test_mainnet_adapter import loaded as loaded_exchange, armed as arm
        from tests.communication.test_v35_http_client import TOKEN

        self.target.refresh_recommendation()
        server = ObservationControlServer(target=self.target, auth_token=TOKEN, port=0)
        host, port = server.start()
        self.addCleanup(server.stop)
        remote = RemoteObservationClient(base_url=f"http://{host}:{port}", profile="live-trade",
            auth_token=TOKEN, receipt_directory=self.root / "receipts", execution_release_sha=SHA)
        client = V37IntegratedObservationClient(remote=remote, profile_name="live-trade", release_sha=SHA)
        exchange = loaded_exchange(self.root)
        exchange.bid, exchange.ask = 100.4, 100.6
        arm(exchange.config)
        self.addCleanup(exchange.disconnect)
        def build():
            return run_execution.build_execution_worker(repo_root=self.root, profile_name="live-trade",
                exchange=exchange, proposal_client=client, outcome_client=client,
                allowed_entry_authorities=frozenset({LIVE_LEARNED_AUTHORITY}),
                risk_config=RiskConfig(risk_per_trade_usd=.25, max_notional_usd=25, leverage=1))
        with mock.patch("time.time", return_value=NOW / 1000):
            worker = build()
            worker.prepare()
            worker.enable_new_entries()
            self.assertEqual(worker.process_flat_cycle(), "ENTRY_OPENED")
            self.assertIsNotNone(worker.state.open_position)
            self.assertTrue(exchange.algos)
            # Rebuild the worker from disk while retaining simulated exchange truth.
            exchange.disconnect()
            restarted = build()
            with mock.patch.object(client, "health", side_effect=AssertionError("restart contacted Observation")):
                restarted.prepare()
            self.assertIsNotNone(restarted.state.open_position)
            restarted.force_close_open_position(reason="LEARNED_TEST_CLOSE")
            self.assertIsNone(restarted.state.open_position)
            self.assertEqual(restarted.durable.outbox.pending_count(), 1)
            restarted.process_flat_cycle()
            self.assertEqual(restarted.durable.outbox.pending_count(), 0)
            self.assertEqual(self.target.audit()["received_outcomes"], 1)
            entries = [c for c in exchange.calls if c[0:2] == ("POST", "/fapi/v1/order") and not c[2].get("reduceOnly")]
            self.assertEqual(len(entries), 1)
