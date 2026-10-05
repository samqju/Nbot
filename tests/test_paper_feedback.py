import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from tests import test_learned_testnet as fixtures
from tests.communication.test_v35_control_target import NOW, SHA, seed_event, outcome_from, request
from nbot.config.profiles import get_profile
from nbot.communication.validation import payload_digest
from nbot.observation.learned_recommendation import LearnedTestnetSource
from nbot.observation.recommendation import ObservationControlTarget
from nbot.observation.paper_feedback import PaperFeedback, DAY_MS, BUCKET_MS, group_keys
from nbot.observation.paper_learning_report import paper_learning_report


class PaperFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LearnedTestnetTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.live
        self.now = NOW
        self.source = LearnedTestnetSource(self.db, release_sha=SHA, profile_name="live-paper",
                                           memory_path=self.fixture.training.memory.path)
        self.target = ObservationControlTarget(self.db, get_profile("live-paper"), release_sha=SHA,
                                               now_ms=lambda: self.now, learned_source=self.source)
        self.proposal = self.target.refresh_recommendation().proposal
        self.assertIsNotNone(self.proposal)
        self.feedback = self.source.paper_feedback
        self.next_id = 0

    def record(self, r=-2., *, entered=None, received=None, outcome_changes=None, proposal_changes=None):
        self.next_id += 1
        t = entered if entered is not None else NOW-2*DAY_MS+self.next_id*BUCKET_MS
        p = replace(self.proposal, proposal_id=f"PROP-FEEDBACK-{self.next_id}",
                    generated_at_ms=t, expires_at_ms=t+30000, **(proposal_changes or {}))
        self.target._serve_proposal(p, t)
        args = dict(execution_mode="PAPER", entry_timestamp_ms=t+1000, closed_timestamp_ms=t+61000,
                    realized_pnl_usd=10*r, r_multiple=r)
        args.update(outcome_changes or {})
        out = outcome_from(p, request_id=f"REQ-FEEDBACK-{self.next_id}",
                           outcome_id=f"OUT-FEEDBACK-{self.next_id}", **args)
        received = t+62000 if received is None else received
        with self.db.connection() as conn:
            conn.execute("INSERT INTO received_execution_outcomes VALUES (?,?,?,?,?,?,?,?,?)",
                         (out.outcome_id,p.proposal_id,out.request_id,out.profile,out.market_environment,
                          out.evidence_lineage,received,json.dumps(out.to_dict()),payload_digest(out.to_dict())))
        return out

    def populate(self, r=-2., count=12):
        for i in range(count):
            self.record(r, entered=NOW-3*DAY_MS+i*BUCKET_MS)

    def test_losses_reduce_supported_setup_weight(self):
        self.populate()
        model = self.feedback.snapshot(cutoff_ms=NOW)
        key = group_keys(self.proposal.experiment_context["setup_explanation"], self.proposal.side,
                         self.proposal.experiment_context["paper_feedback"]["candidate"])[0]
        self.assertLess(model["groups"][key]["factor"], 1)
        self.assertGreaterEqual(model["groups"][key]["factor"], .25)

    def test_winners_raise_bounded_preference_without_changing_negative_score(self):
        self.populate(3.)
        model = self.feedback.snapshot(cutoff_ms=NOW)
        group = next(iter(model["groups"].values()))
        self.assertGreater(group["factor"],1)
        self.assertLessEqual(group["factor"],1.5)
        score, _ = self.feedback.adjust(model, {}, "LONG", -1.)
        self.assertEqual(score,-1.)

    def test_too_few_samples_leave_weights_unchanged(self):
        self.populate(count=3)
        model = self.feedback.snapshot(cutoff_ms=NOW)
        self.assertTrue(all(g["factor"]==1 and not g["supported"] for g in model["groups"].values()))

    def test_supported_feedback_is_shrunk_toward_neutral(self):
        self.populate(3., count=8)
        model = self.feedback.snapshot(cutoff_ms=NOW)
        group = next(iter(model["groups"].values()))
        self.assertAlmostEqual(group["raw_mean_clipped_r"], 3.0)
        self.assertGreater(group["shrinkage_factor"], 0)
        self.assertLess(group["shrinkage_factor"], 1)
        self.assertGreater(group["mean_clipped_r"], 0)
        self.assertLess(group["mean_clipped_r"], group["raw_mean_clipped_r"])
        self.assertGreater(group["factor"], 1)

    def test_many_trades_in_one_time_bucket_do_not_create_support(self):
        t = (NOW-2*DAY_MS)//BUCKET_MS*BUCKET_MS+1000
        for i in range(20):
            self.record(3.,entered=t+i*65000)
        model = self.feedback.snapshot(cutoff_ms=NOW)
        self.assertTrue(all(g["buckets"]==1 and g["factor"]==1 for g in model["groups"].values()))

    def test_restart_and_repeated_delivery_never_double_count(self):
        self.populate()
        first = self.feedback.snapshot(cutoff_ms=NOW)
        again = PaperFeedback(self.db,release_sha=SHA).snapshot(cutoff_ms=NOW)
        self.assertEqual(first,again)
        self.assertEqual(first["sample_count"],12)

    def test_late_receipt_cannot_leak_into_earlier_decision(self):
        self.record(received=NOW+10000)
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW+20000)["sample_count"],1)
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)

    def test_future_or_inconsistent_outcomes_are_excluded(self):
        t=NOW-DAY_MS
        closed=NOW+60000
        self.record(entered=t, received=NOW-1,
                    outcome_changes={"closed_timestamp_ms":closed, "holding_seconds":(closed-t-1000)//1000})
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)

    def test_corrupt_outcome_is_quarantined(self):
        out=self.record()
        with self.db.connection() as conn:
            conn.execute("UPDATE received_execution_outcomes SET payload_digest=? WHERE outcome_id=?",("0"*64,out.outcome_id))
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM paper_feedback_rejections").fetchone()[0],1)

    def test_bad_r_is_quarantined(self):
        self.record(outcome_changes={"r_multiple":99.})
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)

    def test_outcome_setup_metadata_cannot_override_original_proposal(self):
        self.record(outcome_changes={"experiment_context":{"setup_explanation":{"setup":"INVENTED"}}})
        model=self.feedback.snapshot(cutoff_ms=NOW)
        self.assertFalse(any("INVENTED" in key for key in model["groups"]))

    def test_other_release_cannot_train_current_cohort(self):
        detail=dict(self.proposal.experiment_context)
        detail["paper_feedback"]=dict(detail["paper_feedback"], release_sha="b"*40)
        self.record(proposal_changes={"experiment_context":detail})
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)

    def test_untagged_old_paper_outcomes_are_not_silently_imported(self):
        self.record(proposal_changes={"experiment_context":None})
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],0)

    def test_testnet_database_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"LIVE_DATABASE_REQUIRED"):
            PaperFeedback(self.fixture.testnet, release_sha=SHA)

    def test_overlapping_positions_are_excluded(self):
        t=NOW-DAY_MS
        self.record(entered=t)
        self.record(entered=t+10000)
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],1)

    def test_old_results_expire_from_training_but_remain_stored(self):
        self.record(entered=NOW-31*DAY_MS)
        self.record(entered=NOW-DAY_MS)
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW)["sample_count"],1)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM paper_feedback_samples").fetchone()[0],2)

    def test_training_and_ingestion_are_bounded(self):
        self.populate(count=5)
        with patch("nbot.observation.paper_feedback.BATCH",2), patch("nbot.observation.paper_feedback.MAX_SAMPLES",1):
            model=self.feedback.snapshot(cutoff_ms=NOW)
        self.assertEqual(model["sample_count"],1)
        self.assertTrue(model["sample_cap_reached"])
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM paper_feedback_samples").fetchone()[0],2)

    def test_report_is_read_only_and_does_not_claim_profitability(self):
        self.populate()
        self.feedback.snapshot(cutoff_ms=NOW)
        # setUp() refreshes a real recommendation and may already freeze a check
        # for this event. Clear only the synthetic test database's check rows so
        # this test can insert one deliberate changed-choice audit record.
        with self.db.connection() as conn:
            conn.execute("DELETE FROM paper_feedback_checks")
        self.feedback.record_check(NOW-300000, NOW-299000, {
            "baseline": {"symbol": "BTCUSDT", "side": "LONG", "candidate": "MODEL_ONLY", "score": 1.0},
            "selected": {"symbol": "ETHUSDT", "side": "LONG", "candidate": "MODEL_ONLY", "score": 0.8,
                         "factor": 0.8, "reason": "PAPER_FEEDBACK_APPLIED"},
            "choice_changed": True, "no_trade": False,
        })
        with self.db.connection() as conn:
            counts=conn.execute("SELECT COUNT(*) FROM paper_feedback_models").fetchone()
        report=paper_learning_report(self.db,release_sha=SHA,now_ms=NOW+1)
        self.assertIn("Completed eligible paper trades: 12",report)
        self.assertIn("Frozen baseline decision audit",report)
        self.assertIn("Adaptive choice differed from frozen base ranking: 1 / 1",report)
        self.assertIn("INSUFFICIENT",report)
        self.assertIn("funding",report)
        with self.db.connection() as conn:
            self.assertEqual(counts,conn.execute("SELECT COUNT(*) FROM paper_feedback_models").fetchone())

    def test_real_outcome_ack_then_feedback_ingestion(self):
        response=self.target.handle_trade_request(request(profile="live-paper",market_environment="LIVE",execution_mode="PAPER"))
        outcome=outcome_from(response.proposal,execution_mode="PAPER")
        self.now=NOW+62000
        self.assertEqual(self.target.receive_execution_outcome(outcome).status,"RECORDED")
        self.assertEqual(self.target.receive_execution_outcome(outcome).status,"ALREADY_RECORDED")
        self.assertEqual(self.feedback.snapshot(cutoff_ms=NOW+63000)["sample_count"],1)

    def test_losses_change_next_recommendation_without_future_data(self):
        self.populate()
        self.now=NOW+300000
        seed_event(self.db,captured_at_ms=self.now)
        with patch("nbot.observation.learned_recommendation._ridge_score",return_value=2.):
            changed=self.target.refresh_recommendation().proposal
        self.assertIsNotNone(changed)
        self.assertNotEqual(changed.side,self.proposal.side)
        self.assertTrue(changed.experiment_context["paper_feedback"]["ranking_changed"])
        self.assertEqual(changed.experiment_context["paper_feedback"]["release_sha"],SHA)

    def test_recent_recovery_changes_preference_and_preserves_old_losses(self):
        for i in range(12):
            self.record(-3.,entered=NOW-40*DAY_MS+i*BUCKET_MS)
        for i in range(12):
            self.record(3.,entered=NOW-3*DAY_MS+i*BUCKET_MS)
        model=self.feedback.snapshot(cutoff_ms=NOW)
        self.assertEqual(model["sample_count"],12)
        self.assertTrue(all(g["factor"]>1 for g in model["groups"].values()))
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM paper_feedback_samples").fetchone()[0],24)

    def test_mainnet_source_has_no_feedback_learner(self):
        source=LearnedTestnetSource(self.db,release_sha=SHA,profile_name="live-trade",
                                   memory_path=self.fixture.training.memory.path)
        self.assertIsNone(source.paper_feedback)
        self.assertIsNone(self.fixture.source.paper_feedback)

    def test_http_paper_execution_restart_close_ack_feeds_learner(self):
        import run_execution
        from nbot.communication.client import RemoteObservationClient
        from nbot.communication.server import ObservationControlServer
        from nbot.communication.integration import V37IntegratedObservationClient
        from nbot.communication.authorities import LIVE_PAPER_LEARNED_AUTHORITY
        from nbot.exchange.paper import PaperExchange
        from nbot.exchange.contracts import Quote
        from tests.communication.test_v35_http_client import TOKEN
        test=self
        class Market:
            def connect(self): pass
            def is_healthy(self): return True
            def quote(self,symbol):
                return Quote(symbol=symbol,bid=100.4,ask=100.6,timestamp_ms=test.now)
        server=ObservationControlServer(target=self.target,auth_token=TOKEN,port=0)
        host,port=server.start()
        self.addCleanup(server.stop)
        remote=RemoteObservationClient(base_url=f"http://{host}:{port}",profile="live-paper",
            auth_token=TOKEN,receipt_directory=self.fixture.root/"paper-receipts",execution_release_sha=SHA)
        client=V37IntegratedObservationClient(remote=remote,profile_name="live-paper",release_sha=SHA)
        def build():
            exchange=PaperExchange(repo_root=self.fixture.root,profile=get_profile("live-paper"),market_data=Market())
            return run_execution.build_execution_worker(repo_root=self.fixture.root,profile_name="live-paper",
                exchange=exchange,proposal_client=client,outcome_client=client,
                allowed_entry_authorities=frozenset({LIVE_PAPER_LEARNED_AUTHORITY}))
        with patch("time.time",side_effect=lambda:self.now/1000):
            worker=build()
            worker.prepare()
            worker.enable_new_entries()
            self.assertEqual(worker.process_flat_cycle(),"ENTRY_OPENED")
            restarted=build()
            with patch.object(client,"health",side_effect=AssertionError("recovery contacted Learning")):
                restarted.prepare()
            self.assertIsNotNone(restarted.state.open_position)
            self.now+=61000
            restarted.force_close_open_position(reason="PAPER_FEEDBACK_TEST")
            self.assertEqual(restarted.durable.outbox.pending_count(),1)
            restarted.process_flat_cycle()
            self.assertEqual(restarted.durable.outbox.pending_count(),0)
            model=self.feedback.snapshot(cutoff_ms=self.now+1)
        self.assertEqual(model["sample_count"],1)
        self.assertEqual(self.target.audit()["received_outcomes"],1)
        with self.db.connection() as conn:
            sample=json.loads(conn.execute("SELECT sample_json FROM paper_feedback_samples").fetchone()[0])
        self.assertLess(sample["net_usd"],0)  # Flat price round trip still pays spread, fees and slippage.
