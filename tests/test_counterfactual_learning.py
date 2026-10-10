import json
import gc
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from types import SimpleNamespace
import os

from nbot.observation.counterfactual_learning import (
    CONTRACT, FEATURE_SCHEMA, VERSION, TARGET, MODEL_PREFIX, REVIEW_PREFIX,
    ACTIVATION_PREFIX, HORIZON_MS, SPACING_MS, CounterfactualLearner,
    PaperLearningManager, load_samples, purged_split, digest, portfolio_metrics,
    evaluate_window, runtime_from_payload,
    CANONICAL_FEATURE_VERSION,
)
from nbot.observation.selection import FEATURE_VECTOR_NAMES
from nbot.observation.decision_ledger import FrozenDecision, MaturedOutcome, DecisionLedger
from nbot.observation.research_memory import ResearchMemoryStore
from nbot.observation.chronological_replay import TradeEvent
from nbot.observation.research_replay import ReplayHypothesis
from nbot.observation.redesign_runtime import V3ResearchRuntime
from nbot.observation.counterfactual import TrailPolicy, ReplayCosts


def vector(signal=.01):
    v = dict.fromkeys(FEATURE_VECTOR_NAMES, 0.)
    v.update(atr14_frac=.01, ret_4h_side=signal, ret_1h_side=signal/2,
             realized_vol_4h=.01, liquidity_percentile=.5, volatility_percentile=.5)
    return v


def decision(key, event=100_000, approved=False):
    return FrozenDecision(key, f"e{event}", event, "BTCUSDT", "LONG", "TREND",
        "a"*40, "model", digest(vector()), 0., None, None, 0., 1, 0., 0.,
        approved, "ABOVE" if approved else "BELOW", 99.99, 100., "WSS_BOOK",
        "TICK_INTEGER_R_V1", 1., True)


def extras(event=100_000):
    return {"training_contract": CONTRACT, "feature_schema": FEATURE_SCHEMA,
        "canonical_feature_version": CANONICAL_FEATURE_VERSION,
        "feature_vector": vector(), "entry_time_ms": event,
        "entry_price": 100., "one_r_price": 1., "horizon_ms": HORIZON_MS,
        "costs": {"taker_fee_rate": .0005, "entry_slippage_bps": 1.,
                  "exit_slippage_bps": 1., "funding_r": 0.}}


def sample(key, event, signal=1., end=None):
    return {"id": key, "event_ms": event, "entry_ms": event,
        "end_ms": end or event+1000, "available_ms": event+2000,
        "symbol": key.upper()+"USDT", "side": "LONG", "approved": signal>0,
        "feature_vector_json": json.dumps(vector(signal/100)),
        "target_net_r": signal, "ridge_score": 0., "source_digest": key}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = Path(self.td.name)/"ledger.db"
        self.rt = V3ResearchRuntime(self.path)
    def tearDown(self):
        gc.collect()
        self.td.cleanup()
    def complete(self, key="rejected", x=None):
        d = decision(key)
        h = ReplayHypothesis(key, "BTCUSDT", "LONG", 100., 1., 100_000,
            TrailPolicy.TICK_INTEGER_R, costs=ReplayCosts(entry_slippage_bps=1., exit_slippage_bps=1.))
        self.rt.submit(d, h, extras=x or extras())
        self.rt.ingest_trade(TradeEvent("BTCUSDT", 1, 100_010, 100.1))
        self.rt.ingest_trade(TradeEvent("BTCUSDT", 2, 100_020, 98.9))
        self.rt.mature_due(now_ms=100_030)
    def test_rejected_forward_trade_is_training_evidence(self):
        self.complete()
        rows, excluded = load_samples(self.path, now_ms=HORIZON_MS+500_000)
        self.assertFalse(excluded)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["approved"])
        self.assertAlmostEqual(rows[0]["target_net_r"], -1.22)
        self.assertEqual(len(self.rt.replays._results), 0)
    def test_duplicate_trade_does_not_destroy_path(self):
        key="dup"
        self.rt.submit(decision(key),ReplayHypothesis(key,"BTCUSDT","LONG",100,1,100_000,
            TrailPolicy.TICK_INTEGER_R,costs=ReplayCosts(entry_slippage_bps=1.,exit_slippage_bps=1.)),extras=extras())
        event=TradeEvent("BTCUSDT",1,100_010,100.1)
        self.rt.ingest_trade(event); self.rt.ingest_trade(event)
        self.rt.ingest_trade(TradeEvent("BTCUSDT",2,100_020,98.9))
        self.rt.mature_due(now_ms=100_030)
        self.assertEqual(len(load_samples(self.path,now_ms=HORIZON_MS+500_000)[0]),1)
    def test_late_outcome_is_not_available_before_receipt(self):
        self.complete()
        self.assertEqual(load_samples(self.path, now_ms=100_020)[0], [])
    def test_legacy_missing_features_are_not_reconstructed(self):
        self.complete(x={"entry_time_ms":100_000})
        rows, excluded = load_samples(self.path, now_ms=HORIZON_MS+500_000)
        self.assertFalse(rows)
        self.assertTrue(excluded)
    def test_changed_cost_contract_is_excluded(self):
        x=extras(); x["costs"]["funding_r"] = .1
        self.complete(x=x)
        self.assertFalse(load_samples(self.path, now_ms=HORIZON_MS+500_000)[0])
    def test_gap_and_disconnect_are_not_training_losses(self):
        d = decision("gap")
        self.rt.submit(d, ReplayHypothesis("gap","BTCUSDT","LONG",100,1,100_000,TrailPolicy.TICK_INTEGER_R), extras=extras())
        self.rt.ingest_trade(TradeEvent("BTCUSDT",1,100_010,100))
        self.rt.replays.invalidate_paths(["BTCUSDT"])
        self.rt.mature_due(now_ms=200_000)
        self.assertEqual(self.rt.ledger.counts()["unresolved"], 1)
        self.assertFalse(load_samples(self.path, now_ms=HORIZON_MS+500_000)[0])
    def test_missing_horizon_boundary_is_excluded(self):
        self.rt.submit(decision("quiet"), ReplayHypothesis("quiet","BTCUSDT","LONG",100,1,100_000,TrailPolicy.TICK_INTEGER_R), extras=extras())
        self.rt.ingest_trade(TradeEvent("BTCUSDT",1,100_010,100))
        self.rt.ingest_trade(TradeEvent("BTCUSDT",2,100_020,100))
        self.rt.mature_due(now_ms=HORIZON_MS+100_000)
        self.assertFalse(load_samples(self.path, now_ms=HORIZON_MS+500_000)[0])
    def test_actual_execution_never_enters_training(self):
        self.rt.ledger.record_decision(decision("actual"), extras=extras())
        self.rt.record_actual_execution(MaturedOutcome("actual","ACTUAL",100_100,"ACTUAL","STOP",1,1,0,"x",True,"trade"))
        self.assertFalse(load_samples(self.path, now_ms=HORIZON_MS+500_000)[0])
    def test_corrupted_decision_fails_digest(self):
        self.complete()
        with self.rt.ledger._connect() as c:
            c.execute("DROP TRIGGER frozen_decisions_no_update")
            c.execute("UPDATE frozen_decisions SET digest='invalid'")
        self.assertIn("DIGEST", load_samples(self.path, now_ms=HORIZON_MS+500_000)[1])


class EvaluationTests(unittest.TestCase):
    def test_dense_row_cap_still_reserves_ten_disjoint_diagnostics(self):
        rows=[sample(str(i),i*300_000,end=i*300_000+HORIZON_MS) for i in range(1500)]
        train, valid=purged_split(rows)
        self.assertGreaterEqual(len(train),80)
        self.assertGreaterEqual(len(valid),10)

    def test_purge_removes_overlapping_or_late_received_labels(self):
        rows = [sample(str(i), i*300_000, end=i*300_000+HORIZON_MS) for i in range(200)]
        train, valid=purged_split(rows)
        self.assertTrue(train and valid)
        self.assertLess(max(r["end_ms"]+300_000 for _, rs in train for r in rs), valid[0][0])
        self.assertTrue(all(b[0]-a[0]>=SPACING_MS for a,b in zip(valid,valid[1:])))
    def test_one_position_skips_overlapping_signals(self):
        groups=[(100,[sample("a",100,end=1000)]),(200,[sample("b",200,end=2000)]),
                (2100,[sample("c",2100,end=3000)])]
        r=portfolio_metrics(groups, {"a":1,"b":1,"c":1})
        self.assertEqual(r["trades"],2)
        self.assertEqual(r["selected_ids"],["a","c"])
    def test_prediction_accuracy_alone_cannot_promote_losing_policy(self):
        groups=[(i*SPACING_MS,[sample(str(i),i*SPACING_MS,signal=-1)]) for i in range(10)]
        perfect={str(i):-1 for i in range(10)}
        trade_scores={str(i):1 for i in range(10)}
        zeros={str(i):0 for i in range(10)}
        r=evaluate_window(groups,perfect,trade_scores,zeros,zeros)
        self.assertFalse(r["passed"])
        self.assertTrue(r["checks"]["prediction_beats_zero"])
        self.assertFalse(r["checks"]["positive_after_cost"])
    def test_supported_positive_policy_can_pass(self):
        groups=[(i*SPACING_MS,[sample(str(i),i*SPACING_MS)]) for i in range(10)]
        ones={str(i):1 for i in range(10)}; zeros={str(i):0 for i in range(10)}
        self.assertTrue(evaluate_window(groups,ones,ones,zeros,zeros)["passed"])

    def test_tied_policy_cannot_replace_incumbent(self):
        groups=[(i*SPACING_MS,[sample(str(i),i*SPACING_MS)]) for i in range(10)]
        ones={str(i):1 for i in range(10)}
        result=evaluate_window(groups,ones,ones,ones,ones)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["net_improvement_at_least_0_1r"])


class ModelLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.memory=ResearchMemoryStore(Path(self.td.name)/"memory.db")
        self.memory.persist_artifact("seed",{})
        self.learner=CounterfactualLearner(self.memory, release_sha="a"*40)
        self.ridge = self.memory.persist_artifact("ridge-fixture", {"model": {}})
        self.ridge_patch = patch.object(CounterfactualLearner, "_ridge_record", return_value=self.ridge)
        self.ridge_patch.start()
        self.score_patch = patch("nbot.observation.selection._ridge_score", return_value=0.)
        self.score_patch.start()
    def tearDown(self):
        self.ridge_patch.stop()
        self.score_patch.stop()
        gc.collect()
        self.td.cleanup()
    def test_wait_with_no_ledger_does_not_replace_model(self):
        self.assertEqual(self.learner.train_if_needed()["status"],"WAIT_FOR_HIGH_RES_HISTORY")
        self.assertIsNone(self.learner.active(event_ms=10**15))
    def test_train_real_boosters_freeze_then_wait_for_future(self):
        rows=[]
        for i in range(180):
            for j in range(8):
                rows.append(sample(f"{i}-{j}", 1_000_000+i*SPACING_MS, signal=((i+j)%21-10)/10))
        with patch("nbot.observation.counterfactual_learning.load_samples",return_value=(rows,{})):
            result=self.learner.train_if_needed()
            self.assertEqual(result["status"],"CANDIDATE_FROZEN_WAIT_FUTURE")
            saved=self.memory.artifact(result["candidate"])
            self.assertEqual(saved["payload"]["target"],TARGET)
            self.assertEqual(runtime_from_payload(saved["payload"]).score(vector())[0],
                             runtime_from_payload(saved["payload"]).score(vector())[0])
            self.assertEqual(self.learner.train_if_needed()["status"],"WAIT_FOR_FUTURE_EVALUATION")
            self.assertIsNone(self.learner.active(event_ms=10**15))
    def fake_candidate(self):
        p={"version":VERSION,"target":TARGET,"release_sha":"a"*40,
           "trained_at_ms":1_000_000,"training_available_ms":900_000,"incumbent_key":None,
           "incumbent":self.learner.paper_incumbent(1_000_000)}
        return self.memory.persist_artifact(MODEL_PREFIX+"fixture",p)
    def test_future_pass_activation_restart_and_rollback(self):
        candidate=self.fake_candidate()
        rows=[sample(str(i),1_000_001+(i+1)*SPACING_MS) for i in range(20)]
        class Runtime:
            def score(self, v): return 1.,1.
        with patch("nbot.observation.counterfactual_learning.runtime_from_payload",return_value=Runtime()):
            result=self.learner._evaluate(candidate,rows,10**12)
        self.assertEqual(result["status"],"PASS_PAPER_GATE")
        fresh=CounterfactualLearner(self.memory,release_sha="a"*40)
        self.assertEqual(fresh.active(event_ms=10**12+1)["artifact_key"],candidate["artifact_key"])
        self.assertIsNone(CounterfactualLearner(self.memory,release_sha="b"*40).active(event_ms=10**12+1))
        with patch("nbot.observation.counterfactual_learning.time.time",return_value=10**9+1):
            self.assertEqual(fresh.rollback()["status"],"ROLLED_BACK")
        self.assertIsNone(fresh.active(event_ms=10**12+2000))
    def test_insufficient_future_and_failed_model_keep_fallback(self):
        candidate=self.fake_candidate()
        rows=[sample(str(i),1_000_001+(i+1)*SPACING_MS,signal=-1) for i in range(20)]
        self.assertEqual(self.learner._evaluate(candidate,rows[:19],10**12)["status"],"WAIT_FOR_FUTURE_EVALUATION")
        class Runtime:
            def score(self,v): return 1.,1.
        with patch("nbot.observation.counterfactual_learning.runtime_from_payload",return_value=Runtime()):
            self.assertEqual(self.learner._evaluate(candidate,rows,10**12)["status"],"REJECT_PAPER_GATE")
        self.assertIsNone(self.learner.active(event_ms=10**15))
    def test_serialized_v3_contract_does_not_accept_changed_target(self):
        with self.assertRaises(ValueError):
            runtime_from_payload({"version":VERSION,"target":"ACTUAL_PNL"})

    def test_disabled_learner_never_fits_or_activates(self):
        with patch.dict(os.environ,{"NBOT_COUNTERFACTUAL_LEARNING":"0"}):
            self.assertEqual(self.learner.train_if_needed()["status"],"DISABLED_KEEP_V2_FALLBACK")

    def test_review_activation_recovered_after_crash_only_once(self):
        candidate=self.fake_candidate()
        review={"status":"PASS_PAPER_GATE","through_event_ms":500_000}
        self.memory.persist_artifact(REVIEW_PREFIX+candidate["artifact_digest"], review)
        with patch("nbot.observation.counterfactual_learning.load_samples",return_value=([],{})):
            self.assertEqual(self.learner.train_if_needed()["status"],"RECOVERED_PAPER_ACTIVATION")
            self.assertEqual(self.learner.train_if_needed()["status"],"WAIT_FOR_NEW_TRAINING_EVIDENCE")
        self.assertEqual(len(self.learner._records(ACTIVATION_PREFIX)),1)

    def test_v3_beats_ridge_but_loses_to_v2_must_not_activate(self):
        from nbot.observation.selective_ml import ARTIFACT_PREFIX, VERSION as V2
        v2=self.memory.persist_artifact(ARTIFACT_PREFIX+"old", {"version":V2,
            "release_sha":"a"*40,"trained_at_ms":1,"training_cutoff_event_ms":1,"eligible":True})
        candidate=self.fake_candidate()
        rows=[]
        for i in range(20):
            event=1_000_001+(i+1)*SPACING_MS
            rows.extend([sample(f"good-{i}",event,signal=1.),sample(f"better-{i}",event,signal=2.)])
        class Runtime:
            def __init__(self,v2): self.v2=v2
            def score(self,v):
                target=v["ret_4h_side"]*100
                score=target if self.v2 else (1. if target==1 else .2)
                return score,score
        with patch("nbot.observation.counterfactual_learning.runtime_from_payload",
                   side_effect=lambda p:Runtime(p["version"]==V2)):
            report=self.learner._evaluate(candidate,rows,10**12)
        self.assertEqual(candidate["payload"]["incumbent"]["key"],v2["artifact_key"])
        self.assertEqual(report["status"],"REJECT_PAPER_GATE")
        self.assertGreater(report["validation"]["candidate"]["net_r"],0)
        self.assertGreater(report["validation"]["incumbent"]["net_r"],report["validation"]["candidate"]["net_r"])
        self.assertIsNone(self.learner.active(event_ms=10**15))

    def test_v2_changes_during_future_testing_blocks_promotion(self):
        from nbot.observation.selective_ml import ARTIFACT_PREFIX, VERSION as V2
        def save(name,stamp):
            return self.memory.persist_artifact(ARTIFACT_PREFIX+name,{"version":V2,
                "release_sha":"a"*40,"trained_at_ms":stamp,"training_cutoff_event_ms":stamp,"eligible":True},recorded_at_ms=stamp)
        save("old",1)
        candidate=self.fake_candidate()
        save("new",2)
        rows=[sample(str(i),1_000_001+(i+1)*SPACING_MS) for i in range(20)]
        report=self.learner._evaluate(candidate,rows,10**12)
        self.assertEqual(report["status"],"REJECT_PAPER_GATE")
        self.assertTrue(report["incumbent_changed_during_evaluation"])
        self.assertFalse(self.learner._activate(candidate,{"status":"PASS_PAPER_GATE"},10**12))
        self.assertIsNone(self.learner.active(event_ms=10**15))

    def test_legacy_candidate_without_exact_comparator_cannot_activate(self):
        candidate=self.fake_candidate()
        candidate["payload"].pop("incumbent")
        self.assertFalse(self.learner._activate(candidate,{"status":"PASS_PAPER_GATE"},10**12))

    def test_ridge_digest_change_blocks_activation(self):
        candidate=self.fake_candidate()
        replacement=self.memory.persist_artifact("ridge-new",{"model":{"changed":True}})
        with patch.object(self.learner,"_ridge_record",return_value=replacement):
            self.assertFalse(self.learner._activate(candidate,{"status":"PASS_PAPER_GATE"},10**12))

    def test_inference_ridge_resolver_preserves_exact_artifact_digest(self):
        from nbot.observation.learned_recommendation import LearnedTestnetSource
        record=self.memory.persist_artifact("ridge-negative-zero",{"model":{"value":-0.0}})
        with patch.object(LearnedTestnetSource,"_model",return_value=record["payload"]):
            actual=LearnedTestnetSource.ridge_record_for_memory(self.memory,release_sha="a"*40,event_ms=10**12)
        self.assertEqual(actual["artifact_key"],record["artifact_key"])
        self.assertEqual(actual["artifact_digest"],record["artifact_digest"])

    def test_disabled_selective_ml_cannot_promote_hidden_v3(self):
        candidate=self.fake_candidate()
        with patch.dict(os.environ,{"NBOT_SELECTIVE_ML":"0"}):
            self.assertFalse(self.learner._activate(candidate,{"status":"PASS_PAPER_GATE"},10**12))


class LiveCollectionTests(unittest.TestCase):
    def test_shared_stream_pool_is_held_until_active_paths_drain(self):
        from nbot.observation.two_tier_runtime import TwoTierV3ResearchRuntime
        from nbot.observation.watch_planner import WatchCandidate
        with tempfile.TemporaryDirectory() as td:
            runtime=TwoTierV3ResearchRuntime(Path(td)/"ledger.db",broad_target=3,high_res_cap=2)
            runtime.replays.add(ReplayHypothesis("still-open","BTCUSDT","LONG",100,1,100_000,TrailPolicy.TICK_INTEGER_R))
            plan=runtime.refresh_watch_plan(broad_symbols=("BTCUSDT","ETHUSDT","SOLUSDT"),
                candidates=[WatchCandidate("SOLUSDT",1.,.08,"TREND",approved=True)],
                holding_symbols=("BTCUSDT","ETHUSDT"))
            self.assertEqual(plan.high_res_symbols,("BTCUSDT","ETHUSDT"))
            self.assertFalse(plan.newly_admitted_symbols)
            self.assertIn("SOLUSDT",plan.rejected_for_capacity)

    def test_feed_stop_timeout_does_not_create_a_second_live_thread(self):
        from nbot.observation.live_two_tier import ResearchWssFeed
        from unittest.mock import Mock
        feed=ResearchWssFeed(Mock())
        thread=Mock()
        thread.is_alive.return_value=True
        feed.thread=thread
        with self.assertRaisesRegex(RuntimeError,"WSS_THREAD_STOP_TIMEOUT"):
            feed.stop()
        self.assertIs(feed.thread,thread)
        thread.join.assert_called_once_with(timeout=8)

    def test_broken_feed_restarts_without_reusing_interrupted_paths(self):
        from nbot.observation.live_two_tier import ResearchWssFeed
        from unittest.mock import Mock
        runtime=Mock()
        feed=ResearchWssFeed(runtime)
        feed.symbols=("BTCUSDT",)
        feed.thread=Mock()
        feed.thread.is_alive.return_value=True
        feed.state=Mock()
        feed.state.health.return_value=SimpleNamespace(gap_unresolved=True)
        with patch.object(feed,"stop") as stop, \
             patch("nbot.observation.live_two_tier.threading.Thread") as thread:
            feed.update(("BTCUSDT",),())
            stop.assert_called_once()
            runtime.replays.invalidate_paths.assert_called_once_with(("BTCUSDT",))
            thread.return_value.start.assert_called_once()

    def test_both_sides_and_overlapping_rejected_decisions_are_observed(self):
        from nbot.observation.live_two_tier import LiveTwoTierResearchSupervisor, ResearchCandidate
        from nbot.observation.watch_planner import WatchCandidate
        class Scanner:
            last_reason=None
            last_model_source="fixture"
            def scan(self, *, event_open_ms, now_ms):
                rows=[]
                for side in ("LONG","SHORT"):
                    d=replace(decision(f"{event_open_ms}-{side}",now_ms),side=side)
                    rows.append(ResearchCandidate(d,100,1,
                        WatchCandidate("BTCUSDT",-.1,.08,"TREND",approved=False),-.1,vector()))
                return rows
        class Feed:
            def update(self,*args): pass
            def stop(self): pass
            def snapshot(self): return {}
            def wait_quotes(self,symbols):
                return {s:SimpleNamespace(bid=99.99,ask=100.,receipt_time_ms=100_000) for s in symbols}
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as td:
            try:
                os.chdir(td)
                with patch("nbot.observation.live_two_tier.BroadResearchScanner",return_value=Scanner()), \
                     patch("nbot.observation.live_two_tier.ResearchWssFeed",return_value=Feed()), \
                     patch("nbot.observation.live_two_tier.time.time",return_value=100.):
                    supervisor=LiveTwoTierResearchSupervisor(object(),release_sha="a"*40,
                        ledger_path=Path(td)/"ledger.db",broad_target=2,high_res_cap=1)
                    supervisor.on_completed_cycle(event_open_ms=100_000,now_ms=100_000)
                    self.assertIsNone(supervisor.last_error)
                    self.assertEqual(supervisor.runtime.replays.active_count,2)
                    supervisor.on_completed_cycle(event_open_ms=400_000,now_ms=400_000)
                    self.assertEqual(supervisor.runtime.replays.active_count,4)
                    self.assertEqual(supervisor.runtime.ledger.counts()["rejected"],4)
                    supervisor.on_completed_cycle(event_open_ms=4_000_000,now_ms=4_000_000)
                    self.assertEqual(supervisor.runtime.replays.active_count,4)
                    self.assertEqual(supervisor.runtime.ledger.counts()["unresolved"],2)
                    self.assertEqual(len(supervisor.runtime.ledger.pending_decisions()),4)
            finally:
                os.chdir(previous)
                gc.collect()


if __name__ == "__main__":
    unittest.main()
