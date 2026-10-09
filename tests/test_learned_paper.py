import json
import unittest
from unittest.mock import patch
from nbot.communication.authorities import LIVE_PAPER_LEARNED_AUTHORITY
from nbot.communication.integration import _validate_health
from nbot.exchange.contracts import Quote
from nbot.exchange.binance_stream import QuoteUpdate
from nbot.config.profiles import get_profile
from nbot.observation.learned_recommendation import LearnedTestnetSource
from nbot.observation.recommendation import ObservationControlTarget
from tests import test_learned_testnet as fixture_module
from tests.communication.test_v35_control_target import NOW, SHA


class LearnedPaperTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.LearnedTestnetTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source = LearnedTestnetSource(
            self.fixture.live, release_sha=SHA, profile_name="live-paper",
            memory_path=self.fixture.source.memory_path)
        self.target = ObservationControlTarget(
            self.fixture.live, get_profile("live-paper"), release_sha=SHA,
            now_ms=lambda: NOW, learned_source=self.source)

    def test_paper_proposal_has_live_quotes_and_separate_authority(self):
        paper = self.target.refresh_recommendation()
        testnet = self.fixture.target.refresh_recommendation()
        self.assertEqual(paper.status, "READY", paper.reason)
        self.assertEqual(paper.proposal.profile, "live-paper")
        self.assertEqual(paper.proposal.market_environment, "LIVE")
        self.assertEqual(paper.proposal.entry_authority, LIVE_PAPER_LEARNED_AUTHORITY)
        self.assertEqual(paper.proposal.model_digest, testnet.proposal.model_digest)
        self.assertNotEqual(paper.proposal.proposal_id, testnet.proposal.proposal_id)
        self.assertEqual(paper.proposal.experiment_context["reference_quote_environment"], "LIVE")
        self.assertFalse(paper.proposal.experiment_context["research_evidence"])
        _validate_health(health=self.target.health_snapshot(), profile_name="live-paper", release_sha=SHA)

    def test_selective_ml_check_persists_raw_winner_and_entry_diagnostics(self):
        class FakeRuntime:
            def score(self, _vector):
                return 0.05, 0.01

        record = {
            "artifact_digest": "d" * 64,
            "artifact_key": "selective-ml:test",
            "payload": {"model_digest": "m" * 64},
        }
        with patch.object(self.source.selective_ml, "latest_for_event", return_value=record), \
             patch("nbot.observation.learned_recommendation.SelectiveMLRuntime", return_value=FakeRuntime()):
            result = self.target.refresh_recommendation()

        self.assertIsNone(result.proposal)
        with self.fixture.live.connection() as conn:
            raw = conn.execute(
                "SELECT detail_json FROM paper_feedback_checks ORDER BY decision_ms DESC LIMIT 1"
            ).fetchone()[0]
        detail = json.loads(raw)
        self.assertTrue(detail["selective_ml_active"])
        self.assertEqual(detail["raw_ml_winner"]["symbol"], "BTCUSDT")
        self.assertIn("conservative_score_r", detail["raw_ml_winner"])
        self.assertEqual(detail["selected"]["entry_gate_mode"], "EXECUTION_REALTIME_ONLY")
        self.assertIn("post_feedback_score_r", detail["selected"])
        self.assertNotIn("next_bar_entry_probability", detail["selected"])

    def test_restart_reuses_frozen_paper_decision(self):
        first = self.target.refresh_recommendation()
        source = LearnedTestnetSource(self.fixture.live, release_sha=SHA,
            profile_name="live-paper", memory_path=self.fixture.source.memory_path)
        with patch.object(source.features, "compute_event_rows", side_effect=AssertionError("rescored")):
            self.assertEqual(first, source.refresh(now_ms=NOW+1000, ttl_ms=30000))

    def test_testnet_source_cannot_be_attached_to_paper_target(self):
        with self.assertRaisesRegex(ValueError, "PROFILE_MISMATCH"):
            ObservationControlTarget(self.fixture.live, get_profile("live-paper"),
                                     release_sha=SHA, learned_source=self.fixture.source)

    def test_live_trial_has_separate_identity_and_does_not_arm_execution(self):
        from nbot.communication.authorities import LIVE_LEARNED_AUTHORITY
        source = LearnedTestnetSource(self.fixture.live, release_sha=SHA, profile_name="live-trade",
                                     memory_path=self.fixture.source.memory_path)
        target = ObservationControlTarget(self.fixture.live, get_profile("live-trade"), release_sha=SHA,
                                         now_ms=lambda: NOW, learned_source=source)
        proposal = target.refresh_recommendation().proposal
        paper = self.target.refresh_recommendation().proposal
        self.assertEqual(proposal.entry_authority, LIVE_LEARNED_AUTHORITY)
        self.assertEqual(proposal.evidence_lineage, "LIVE_REAL_CAPITAL")
        self.assertNotEqual(proposal.proposal_id, paper.proposal_id)
        self.assertEqual(target.health_snapshot()["order_authority"], "NONE")
        self.assertFalse((self.fixture.root/"runtime/execution/real/LIVE_TRADING_ARMED").exists())


class LearnedPaperRuntimeTests(unittest.TestCase):
    def run_once(self, *, open_position):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        import run_execution as runtime
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exchange, market, client, worker, operator = [MagicMock() for _ in range(5)]
            worker.prepare.return_value = SimpleNamespace(status="RECOVERED")
            worker.state.open_position = SimpleNamespace(symbol="BTCUSDT") if open_position else None
            worker.state.snapshot.entries_enabled = False
            worker.process_flat_cycle.return_value = "NO_TRADE"
            stop = {}
            def register(signum, handler):
                stop["handler"] = handler
            def sleep(_seconds):
                stop["handler"](None, None)
            if open_position:
                def next_quote(*_args, **_kwargs):
                    stop["handler"](None, None)
                    quote = Quote("BTCUSDT", 100.0, 100.1, 1_800_000_000_000)
                    return QuoteUpdate(1, quote, quote.timestamp_ms)
                exchange.wait_quote.side_effect = next_quote
            with patch.object(runtime, "build_live_paper_exchange", return_value=(exchange, market)), \
                 patch.object(runtime, "build_integrated_control_client", return_value=client), \
                 patch.object(runtime, "build_execution_worker", return_value=worker) as builder, \
                 patch.object(runtime, "_operator_surface", return_value=operator), \
                 patch.object(runtime.signal, "signal", side_effect=register), \
                 patch.object(runtime.time, "sleep", side_effect=sleep):
                result = runtime.run_learned_paper_runtime(
                    repo_root=root, environment={}, idle_poll_seconds=.01, open_poll_seconds=.01)
            self.assertEqual(result, 0)
            self.assertEqual(builder.call_args.kwargs["allowed_entry_authorities"],
                             frozenset({LIVE_PAPER_LEARNED_AUTHORITY}))
            worker.disable_new_entries.assert_called()
            worker.enable_new_entries.assert_not_called()
            market.disconnect.assert_called_once()
            operator.stop.assert_called_once()
            return exchange, client, worker

    def test_restart_starts_with_entries_disabled(self):
        _exchange, _client, worker = self.run_once(open_position=False)
        worker.process_flat_cycle.assert_called_once()

    def test_open_management_has_no_observation_dependency(self):
        exchange, client, worker = self.run_once(open_position=True)
        exchange.wait_quote.assert_called_once()
        worker.process_open_quote.assert_called_once()
        client.health.assert_not_called()
        client.request_proposal.assert_not_called()
        worker.process_flat_cycle.assert_not_called()
