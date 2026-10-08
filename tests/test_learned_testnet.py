from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import nbot_admin
from nbot.communication.authorities import TESTNET_LEARNED_AUTHORITY
from nbot.communication.integration import _validate_health
from nbot.communication.client import ObservationClientError
from nbot.config.profiles import get_profile
from nbot.observation.challengers import ContinuousChallengerCycle, CHALLENGER_PREFIX, MODEL_PREFIX, EVALUATION_PREFIX
from nbot.observation.learned_recommendation import LearnedTestnetSource, _execution_compatible_quotes, testnet_recommendation_source
from nbot.observation.recommendation import ObservationControlTarget
from nbot.observation.selection import RidgeSufficientStatistics, _digest
from tests import test_v391_continuous_challengers as training_fixture
from tests.communication.test_v35_control_target import database, seed_event, request, outcome_from, NOW, SHA


class LearnedTestnetTests(unittest.TestCase):
    def setUp(self):
        self.training = training_fixture.V391ContinuousChallengerTests()
        self.training.setUp()
        self.addCleanup(self.training.doCleanups)
        self.addCleanup(self.training.tearDown)
        self.root = Path(self.training.tmp.name)
        self.training.next_event = NOW - 200 * 300_000
        self.training._append_events(25, RidgeSufficientStatistics.empty(), target=2.0)
        self.cycle = ContinuousChallengerCycle(self.training.memory, release_sha=SHA)
        self.cycle.cycle()
        self.live = database(self.root, "live-paper")
        self.testnet = database(self.root, "testnet-trade")
        for i in range(50):
            seed_event(self.live, captured_at_ms=NOW - i * 300_000)
        self.event = seed_event(self.testnet)
        self.now = NOW
        self.source = self.new_source()
        self.target = ObservationControlTarget(self.testnet, get_profile("testnet-trade"),
            release_sha=SHA, now_ms=lambda: self.now, learned_source=self.source)

    def new_source(self):
        return LearnedTestnetSource(self.testnet, release_sha=SHA, live=self.live,
                                   memory_path=self.training.memory.path)

    def change_model(self, **changes):
        # Re-sign the fixture to test semantic checks independently of hash checks.
        record = self.training.memory.list_artifacts(prefix=MODEL_PREFIX)[0]
        artifact = record["payload"]
        artifact.update(changes)
        artifact["model"]["model_digest"] = _digest({k: v for k, v in artifact["model"].items() if k != "model_digest"})
        artifact["model_digest"] = artifact["model"]["model_digest"]
        def encode(value):
            text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            return text, hashlib.sha256(text.encode()).hexdigest()
        text, digest = encode(artifact)
        challenger = self.training.memory.list_artifacts(prefix=CHALLENGER_PREFIX)[0]
        challenger["payload"]["model_artifact_digest"] = digest
        with self.training.memory._connect() as conn:
            conn.execute("UPDATE research_memory_artifacts SET artifact_json=?,artifact_digest=? WHERE artifact_key=?",
                         (text, digest, record["artifact_key"]))
            text, digest = encode(challenger["payload"])
            conn.execute("UPDATE research_memory_artifacts SET artifact_json=?,artifact_digest=? WHERE artifact_key=?",
                         (text, digest, challenger["artifact_key"]))

    def test_real_training_features_and_inference_make_model_based_proposal(self):
        snapshot = self.target.refresh_recommendation()
        self.assertEqual(snapshot.status, "READY", snapshot.reason)
        p = snapshot.proposal
        self.assertEqual(p.entry_authority, TESTNET_LEARNED_AUTHORITY)
        self.assertAlmostEqual(p.expected_after_cost_net_r, 2.0)
        self.assertEqual(p.symbol, "BTCUSDT")
        self.assertEqual(p.side, "LONG")
        self.assertEqual(p.reference_price, 100.5)
        self.assertIsNotNone(p.model_digest)
        self.assertFalse(p.experiment_context["economic_claim"])
        _validate_health(health=self.target.health_snapshot(), profile_name="testnet-trade", release_sha=SHA)

    def test_restart_preserves_exact_decision_and_expiry_without_rescoring(self):
        first = self.target.refresh_recommendation()
        second = self.new_source()
        with mock.patch.object(second.features, "compute_event_rows", side_effect=AssertionError("rescored")):
            replay = second.refresh(now_ms=NOW + 1000, ttl_ms=30_000)
        self.assertEqual(first, replay)

    def test_negative_model_returns_no_trade_not_random_fallback(self):
        model = self.training.memory.list_artifacts(prefix=MODEL_PREFIX)[0]["payload"]["model"]
        model["intercept"] = -2.0
        self.change_model(model=model)
        self.target.refresh_recommendation()
        response = self.target.handle_trade_request(request())
        self.assertEqual(response.status, "NO_TRADE")
        self.assertEqual(response.reason, "LEARNED_NO_POSITIVE_OPPORTUNITY")

    def test_model_coefficients_choose_short_instead_of_hash_side(self):
        model = self.training.memory.list_artifacts(prefix=MODEL_PREFIX)[0]["payload"]["model"]
        model["coefficients"]["side_sign"] = -3.0
        self.change_model(model=model)
        snapshot = self.target.refresh_recommendation()
        self.assertEqual(snapshot.proposal.side, "SHORT")

    def test_missing_training_memory_stays_not_ready(self):
        self.source.memory_path = self.root / "missing.db"
        result = self.target.refresh_recommendation()
        self.assertEqual(result.reason, "LEARNING_WAIT_FOR_COMPATIBLE_MODEL")
        self.assertIsNone(result.proposal)
        self.assertFalse(self.source.memory_path.exists())

    def test_model_available_after_decision_is_not_used(self):
        self.change_model(model_available_at_ms=NOW)
        self.assertIsNone(self.target.refresh_recommendation().proposal)

    def test_unmature_training_labels_are_not_used(self):
        self.change_model(training_cutoff_event_ms=NOW - 300_000)
        self.assertIsNone(self.target.refresh_recommendation().proposal)

    def test_corrupt_model_invalidates_already_ready_proposal(self):
        self.assertIsNotNone(self.target.refresh_recommendation().proposal)
        with self.training.memory._connect() as conn:
            conn.execute("UPDATE research_memory_artifacts SET artifact_digest='bad' WHERE artifact_key LIKE ?", (MODEL_PREFIX + "%",))
        result = self.target.refresh_recommendation()
        self.assertEqual(result.status, "NOT_READY")
        self.assertIn("CORRUPT", result.reason)
        self.assertIsNone(self.target.recommendations.current().proposal)

    def test_rejected_model_cannot_keep_serving_earlier_proposal(self):
        self.target.refresh_recommendation()
        challenger = self.training.memory.list_artifacts(prefix=CHALLENGER_PREFIX)[0]["payload"]
        self.training.memory.persist_artifact(EVALUATION_PREFIX + challenger["challenger_version"],
                                              {"status": "REJECT_RESEARCH_GATE"})
        self.assertIsNone(self.target.refresh_recommendation().proposal)

    def test_nonfinite_or_zero_scale_model_fails_closed(self):
        model = self.training.memory.list_artifacts(prefix=MODEL_PREFIX)[0]["payload"]["model"]
        model["scales"]["side_sign"] = 0
        self.change_model(model=model)
        result = self.target.refresh_recommendation()
        self.assertIsNone(result.proposal)
        self.assertIn("NUMERICAL_ERROR", result.reason)

    def test_stale_live_event_blocks_before_model_or_feature_work(self):
        self.now += 31_000
        with mock.patch.object(self.source, "_model", side_effect=AssertionError("unnecessary work")):
            result = self.target.refresh_recommendation()
        self.assertIsNone(result.proposal)
        self.assertIn("STALE", result.reason)

    def test_stale_testnet_quote_is_not_replaced_by_live_price(self):
        with self.testnet.connection() as conn:
            conn.execute("UPDATE market_snapshots SET captured_at_ms=?", (NOW - 40_000,))
        result = self.target.refresh_recommendation()
        self.assertIsNone(result.proposal)
        self.assertIn("MATCHING_TESTNET_EVENT", result.reason)

    def test_execution_incompatible_symbols_are_filtered_before_ranking(self):
        rows = [
            ("龙虾USDT", 200.0, 200.2, NOW),
            ("btcusdt", 100.0, 100.2, NOW),
        ]
        quotes = _execution_compatible_quotes(
            rows, close_ms=NOW - 1, now_ms=NOW, ttl_ms=30_000
        )
        self.assertNotIn("龙虾USDT", quotes)
        self.assertEqual(tuple(quotes), ("BTCUSDT",))
        self.assertEqual(quotes["BTCUSDT"][0], "BTCUSDT")

    def test_incomplete_feature_history_waits(self):
        with self.live.connection() as conn:
            conn.execute("DELETE FROM candles_5m WHERE event_open_ms<?", (self.event,))
        self.assertEqual(self.target.refresh_recommendation().reason, "LEARNING_WAIT_FOR_FULL_FEATURE_HISTORY")

    def test_testnet_outcomes_are_idempotent_and_never_change_live_training(self):
        before = self.training.memory.status()
        self.target.refresh_recommendation()
        response = self.target.handle_trade_request(request())
        closed = outcome_from(response.proposal)
        self.assertEqual(self.target.receive_execution_outcome(closed).status, "RECORDED")
        self.assertEqual(self.target.receive_execution_outcome(closed).status, "ALREADY_RECORDED")
        self.assertEqual(self.training.memory.status(), before)
        self.assertEqual(self.target.handle_trade_request(request(request_id="REQ-2")).status, "NO_TRADE")

    def test_learned_authority_cannot_cross_into_live_paper(self):
        with self.assertRaisesRegex(ValueError, "TESTNET_ONLY"):
            LearnedTestnetSource(self.live, release_sha=SHA)
        health = self.target.health_snapshot()
        health.update(profile="live-paper", market_environment="LIVE", evidence_lineage="LIVE_PAPER_OPERATIONAL")
        with self.assertRaises(ObservationClientError):
            _validate_health(health=health, profile_name="live-paper", release_sha=SHA)

    def test_inference_leaves_live_evidence_and_research_tables_untouched(self):
        with self.live.connection() as conn:
            before = list(conn.iterdump())
        self.target.refresh_recommendation()
        with self.live.connection() as conn:
            self.assertEqual(before, list(conn.iterdump()))

    def test_unknown_evaluation_state_is_not_treated_as_approved(self):
        challenger = self.training.memory.list_artifacts(prefix=CHALLENGER_PREFIX)[0]["payload"]
        self.training.memory.persist_artifact(EVALUATION_PREFIX + challenger["challenger_version"],
                                              {"status": "CORRUPT_UNKNOWN"})
        result = self.target.refresh_recommendation()
        self.assertIsNone(result.proposal)
        self.assertIn("EVALUATION_STATUS_INVALID", result.reason)

    def test_fresh_memory_initialization_reserves_history_and_is_idempotent(self):
        from contextlib import nullcontext
        from nbot.observation.research_memory import ResearchMemoryStore
        memory = ResearchMemoryStore(self.root / "new-memory.db")
        with mock.patch.object(nbot_admin, "_research_epoch_command_lock", side_effect=nullcontext), \
             mock.patch.object(nbot_admin, "_db", return_value=self.live), \
             mock.patch.object(nbot_admin, "_memory", return_value=memory), \
             mock.patch.object(nbot_admin, "_emit", return_value=0):
            nbot_admin.cmd_research_memory_init(None)
            first = memory.metadata()
            nbot_admin.cmd_research_memory_init(None)
        self.assertEqual(memory.metadata(), first)
        self.assertEqual(int(first["generation_floor_ms"]), self.event - 300_000)

    def test_expired_proposal_is_not_advertised_ready(self):
        self.target.refresh_recommendation()
        self.now += 31_000
        self.assertEqual(self.target.health_snapshot()["status"], "NOT_READY")

    @unittest.skipIf(os.name == "nt", "Governance artifact directory fsync requires Linux")
    def test_epoch_evaluation_wait_does_not_block_future_training_data(self):
        from nbot.observation.governance import ModelGovernanceRegistry
        from nbot.observation.market_regimes import MarketRegimeEvidence, CONFIG
        with self.training.memory._connect() as conn:
            conn.execute("UPDATE research_memory_meta SET value=? WHERE key='generation_floor_ms'",
                         (str(CONFIG.calibration_cutoff_event_ms + 300_000),))
        regimes = MarketRegimeEvidence(self.training.memory)
        cutoff = self.training.next_event - 300_000
        target_end = cutoff + 96 * 300_000
        self.training._seed_pending_epoch_transition(epoch_id="NEXT-EPOCH", target_end_ms=target_end)
        with mock.patch.object(nbot_admin, "_memory", return_value=self.training.memory), \
             mock.patch.object(nbot_admin, "_challenger_cycle", return_value=self.cycle), \
             mock.patch.object(nbot_admin, "_governance", return_value=ModelGovernanceRegistry(self.training.memory, self.root / "models")), \
             mock.patch.object(nbot_admin, "_market_regimes", return_value=regimes):
            result = nbot_admin._run_epoch_challenger_transition()
        self.assertEqual(result["cycle"]["action"], "EVALUATE_WAIT")
        self.assertIsNone(self.training.memory.pending_challenger_transition())
        self.assertEqual(result["market_regime_sync"]["status"], "UNAVAILABLE_HISTORICAL_CALIBRATION")
        self.assertFalse(regimes.audit()["healthy"])
        self.assertEqual(regimes.status()["status"], "UNAVAILABLE_HISTORICAL_CALIBRATION")

    @unittest.skipIf(os.name == "nt", "Testnet process/session locks require Linux")
    def test_learned_http_order_stop_restart_close_and_ack_end_to_end(self):
        import run_execution
        from nbot.communication.client import RemoteObservationClient
        from nbot.communication.server import ObservationControlServer
        from nbot.communication.integration import V37IntegratedObservationClient
        from tests.test_v319_testnet import loaded_exchange, arm
        from tests.communication.test_v35_http_client import TOKEN

        self.target.refresh_recommendation()
        server = ObservationControlServer(target=self.target, auth_token=TOKEN, port=0)
        host, port = server.start()
        self.addCleanup(server.stop)
        remote = RemoteObservationClient(base_url=f"http://{host}:{port}", profile="testnet-trade",
            auth_token=TOKEN, receipt_directory=self.root / "receipts", execution_release_sha=SHA)
        client = V37IntegratedObservationClient(remote=remote, profile_name="testnet-trade", release_sha=SHA)
        exchange = loaded_exchange(self.root)
        exchange.bid, exchange.ask = 100.4, 100.6
        arm(exchange.config)
        self.addCleanup(exchange.disconnect)
        def build():
            return run_execution.build_execution_worker(repo_root=self.root, profile_name="testnet-trade",
                exchange=exchange, proposal_client=client, outcome_client=client,
                allowed_entry_authorities=frozenset({TESTNET_LEARNED_AUTHORITY}))
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


if __name__ == "__main__":
    unittest.main()
