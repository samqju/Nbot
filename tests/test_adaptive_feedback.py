import json
import unittest
from dataclasses import asdict
from unittest.mock import patch
from tests import test_paper_feedback as fixtures
from tests.communication.test_v35_control_target import NOW, SHA, seed_event
from nbot.observation.paper_feedback import PaperFeedback, BUCKET_MS
from nbot.observation.shadow import ShadowConfig, VERSION, AUTHORITY, encode, digest
from nbot.observation.candidate_setups import BY_ID, CATALOG_DIGEST
from nbot.observation.feedback_evidence import shadow_sample, COOLDOWN_MS

class AdaptiveFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PaperFeedbackTests();self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.fb=self.f.feedback;self.db=self.f.db;self.n=0
        self.candidate=next(iter(BY_ID.values())).tag()

    def shadow(self, *, entered=None, rr=-3., reason="STOP", available=None, release=SHA, **changes):
        self.n+=1
        t=entered or NOW-8*BUCKET_MS+self.n*300000
        p=dict(id=str(self.n),candidate_id=self.candidate["id"],symbol="BTCUSDT",side="LONG",
               profile="live-paper",release_sha=release,version=VERSION,authority=AUTHORITY,
               catalog_digest=CATALOG_DIGEST,config=asdict(ShadowConfig()),decision_ms=t-1000,
               event_ms=(t-1000)//300000*300000,entered_ms=t,closed_ms=t+60000,
               available_ms=available or t+61000,reason=reason,eligible=reason=="STOP",
               net_usd=rr*10,net_r=rr)
        p.update(changes)
        with self.db.connection() as conn:
            conn.execute("INSERT INTO shadow_results VALUES(?,?,?,?,?,?,?,?)",
                (p["id"],p["candidate_id"],p["release_sha"],p["profile"],p["closed_ms"],
                 int(p["eligible"]),encode(p),digest(p)))
        return p

    def test_shadow_losses_change_candidate_ranking_at_lower_weight(self):
        for i in range(8):self.shadow(entered=NOW-(10-i)*BUCKET_MS)
        m=self.fb.snapshot(cutoff_ms=NOW)
        key="CANDIDATE:"+self.candidate["id"]+"|ALL|LONG"
        self.assertEqual(m["sample_count"],0);self.assertEqual(m["shadow_sample_count"],8)
        self.assertLess(m["groups"][key]["factor"],1)
        self.assertLess(m["groups"][key]["evidence_mass"],2.01)
        score,detail=self.fb.adjust(m,{},"LONG",2.,candidate=self.candidate,symbol="BTCUSDT",now_ms=NOW)
        self.assertLess(score,2.)
        self.assertEqual(detail["evidence_sources"]["shadow"],8)
        other=next(x.tag() for x in BY_ID.values() if x.tag()!=self.candidate)
        self.assertGreater(self.fb.adjust(m,{},"LONG",1.9,candidate=other)[0],score)

    def test_parallel_shadows_do_not_manufacture_independent_support(self):
        for _ in range(30):self.shadow(entered=NOW-BUCKET_MS)
        m=self.fb.snapshot(cutoff_ms=NOW)
        self.assertTrue(all(g["buckets"]==1 and not g["supported"] and g["factor"]==1 for g in m["groups"].values()))

    def test_cancellations_only_affect_entry_feasibility_not_profit(self):
        for i in range(12):self.shadow(entered=NOW-(5-i//3)*BUCKET_MS+i%3*300000,reason="ENTRY_DRIFT_REJECTED",rr=999)
        m=self.fb.snapshot(cutoff_ms=NOW)
        self.assertEqual(m["shadow_sample_count"],0);self.assertEqual(m["groups"],{})
        score,d=self.fb.adjust(m,{},"LONG",2,candidate=self.candidate)
        self.assertLess(score,2);self.assertGreaterEqual(d["factor"],.7)
        self.assertEqual(d["status"],"ENTRY_FEASIBILITY_PENALTY")

    def test_missing_data_future_receipt_wrong_config_and_real_profile_excluded(self):
        self.shadow(reason="DATA_GAP_UNSCORABLE")
        self.shadow(available=NOW+1000)
        self.shadow(config=asdict(ShadowConfig(risk_usd=5)))
        self.shadow(profile="live-trade")
        self.assertEqual(self.fb.snapshot(cutoff_ms=NOW)["shadow_sample_count"],0)

    def test_original_context_and_legacy_broad_context_only(self):
        p=self.shadow()
        sample=shadow_sample(p,cutoff_ms=NOW,catalog_digest=CATALOG_DIGEST)
        self.assertEqual(len(sample["keys"]),1)
        p["decision_context"]="MIXED:HIGH"
        self.assertEqual(len(shadow_sample(p,cutoff_ms=NOW,catalog_digest=CATALOG_DIGEST)["keys"]),2)

    def test_compatible_old_main_evidence_reused_without_rewriting(self):
        detail=dict(self.f.proposal.experiment_context)
        detail["paper_feedback"]=dict(detail["paper_feedback"],release_sha="b"*40)
        self.f.record(proposal_changes={"experiment_context":detail})
        with patch("nbot.observation.paper_feedback.compatible_evidence_release",return_value=True):
            m=self.fb.snapshot(cutoff_ms=NOW)
        self.assertEqual(m["sample_count"],1)
        with self.db.connection() as conn:
            self.assertEqual(conn.execute("SELECT release_sha FROM paper_feedback_samples").fetchone()[0],"b"*40)

    def test_loss_pause_survives_restart_then_expires(self):
        for i in range(3):self.f.record(-1.,entered=NOW-(20-i*3)*60000)
        m=self.fb.snapshot(cutoff_ms=NOW)
        side=self.f.proposal.side;symbol=self.f.proposal.symbol
        self.assertIn(symbol+"|"+side,m["cooldowns"])
        restarted=PaperFeedback(self.db,release_sha=SHA)
        self.assertIsNotNone(restarted.cooldown(symbol,side,cutoff_ms=NOW))
        self.assertIsNone(restarted.cooldown("OTHERUSDT",side,cutoff_ms=NOW))
        score,detail=self.fb.adjust(m,{},side,2.,candidate=self.candidate,symbol=symbol,now_ms=NOW)
        self.assertEqual(score,0);self.assertEqual(detail["status"],"REPEATED_LOSS_COOLDOWN")
        self.assertIsNone(restarted.cooldown(symbol,side,cutoff_ms=NOW+COOLDOWN_MS))
        self.assertGreater(self.fb.adjust(m,{},side,2.,candidate=self.candidate,symbol=symbol,now_ms=NOW+COOLDOWN_MS)[0],0)

    def test_win_breaks_loss_streak(self):
        for i,rr in enumerate([-1.,-1.,1.,-1.]):self.f.record(rr,entered=NOW-(30-i*3)*60000)
        self.assertEqual(self.fb.snapshot(cutoff_ms=NOW)["cooldowns"],{})

    def test_saved_proposal_withheld_after_new_loss_pause(self):
        for i in range(3):self.f.record(-1.,entered=NOW-(20-i*3)*60000)
        result=self.f.target.refresh_recommendation()
        self.assertIsNone(result.proposal)
        self.assertEqual(result.reason,"PAPER_REPEATED_LOSS_COOLDOWN")

    def test_new_decision_records_before_after_and_cooldown_alternative(self):
        for i in range(3):self.f.record(-1.,entered=NOW-(20-i*3)*60000)
        self.f.now=NOW+300000;seed_event(self.db,captured_at_ms=self.f.now)
        with patch("nbot.observation.learned_recommendation._ridge_score",return_value=2.):
            result=self.f.target.refresh_recommendation()
        self.assertIsNotNone(result.proposal)
        self.assertNotEqual((result.proposal.symbol,result.proposal.side),(self.f.proposal.symbol,self.f.proposal.side))
        with self.db.connection() as conn:
            d=json.loads(conn.execute("SELECT detail_json FROM paper_feedback_checks ORDER BY decision_ms DESC LIMIT 1").fetchone()[0])
        self.assertGreater(d["cooldown_choices_blocked"],0);self.assertTrue(d["choice_changed"])

    def test_restart_does_not_double_count(self):
        self.shadow()
        a=self.fb.snapshot(cutoff_ms=NOW)
        b=PaperFeedback(self.db,release_sha=SHA).snapshot(cutoff_ms=NOW)
        self.assertEqual(a,b);self.assertEqual(a["shadow_sample_count"],1)

    def test_request_gate_catches_losses_before_supervisor_refresh(self):
        from tests.communication.test_v35_control_target import request
        for i in range(3):self.f.record(-1.,entered=NOW-(20-i*3)*60000)
        response=self.f.target.handle_trade_request(request(
            profile="live-paper",market_environment="LIVE",execution_mode="PAPER"))
        self.assertEqual(response.status,"NO_TRADE")
        self.assertEqual(response.reason,"PAPER_REPEATED_LOSS_COOLDOWN")

    def test_request_gate_blocks_while_receipt_backlog_remains(self):
        from tests.communication.test_v35_control_target import request
        for i in range(3):self.f.record(-1.,entered=NOW-(20-i*3)*60000)
        with patch("nbot.observation.paper_feedback.BATCH",1):
            response=self.f.target.handle_trade_request(request(
                profile="live-paper",market_environment="LIVE",execution_mode="PAPER"))
        self.assertEqual(response.reason,"PAPER_FEEDBACK_CATCHING_UP")
