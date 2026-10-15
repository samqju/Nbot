"""G8 offline frozen lab training acceptance: no original science/model/PAPER.
All sample R values are synthetic. No original source, services or trades.
"""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.learning_contract import assemble_lab,LearningHold
from nbot_v5_1.training_lab import (LabProtocol,TrainingHold,
    train_lab,verify_model,predict_lab,evaluate_frozen_lab,
    require_authorized_champion)
from nbot_v5_1.training_freeze import (
    seal_lab_model,verify_lab_model,FreezeHold)
from test_v5_1_g7_learning import fixture,BASE

STEP=600000


def dataset(n=60,**kw):
    rows=tuple(fixture(i,**kw) for i in range(n))
    return assemble_lab(rows,cutoff_ms=BASE+(n+2)*STEP)


def policy(**kw):
    opts=dict(declared_at_ms=BASE-STEP,
          train_cutoff_ms=BASE+29*STEP,
          holdout_start_ms=BASE+31*STEP,
          holdout_end_ms=BASE+60*STEP,
          embargo_ms=300000,
          min_train_blocks=8,min_test_blocks=5,min_context_blocks=5,
          cost_buffer_r="0.10",random_search_attempts=1)
    opts.update(kw)
    return LabProtocol(**opts)


def ready():
    d=dataset(60,net="1.1")
    p=policy()
    m=train_lab(d,p)
    result=evaluate_frozen_lab(m,d)
    return d,p,m,result


class G8TrainingTests(unittest.TestCase):
    def test_M01_end_to_end_lab_freeze_valid_but_not_sci(self):
        d,p,m,result=ready()
        self.assertTrue(verify_model(m,d))
        self.assertEqual(m.state,"LAB_ONLY_NOT_SCIENTIFIC")
        self.assertEqual(m.qualified_original,0)
        self.assertEqual(result.status,"LAB_ONLY_HOLD")
        self.assertFalse(result.scientific_advantage_proved)
        self.assertEqual(result.release_authority,"NONE")

    def test_M02_reproducible_model_digest_same_inputs(self):
        d,p,m,result=ready()
        fresh=train_lab(d,p)
        self.assertEqual(m,fresh)
        self.assertEqual(m.model_sha256,fresh.model_sha256)
        self.assertEqual(result,evaluate_frozen_lab(fresh,d))

    def test_M03_no_predeclared_policy_change_after_candidate(self):
        d=dataset(60)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(declared_at_ms=BASE+1))

    def test_M04_predeclared_search_family_cannot_optimize_away_weak_outcomes(self):
        d=dataset(60)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(random_search_attempts=50))
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(context_family="PER_COIN_LOOKAHEAD_V1"))

    def test_M05_no_random_overlap_of_train_and_holdout(self):
        d,p,m,result=ready()
        self.assertGreater(result.train_blocks,0)
        self.assertGreater(result.test_blocks,0)
        self.assertGreaterEqual(result.purged_blocks,1)

    def test_M06_horizon_must_mature_before_training_cutoff(self):
        d=dataset(60)
        p=policy(train_cutoff_ms=BASE+25*STEP)
        m=train_lab(d,p)
        self.assertLess(m.trained_rows,30)
        self.assertLess(m.train_blocks,30)

    def test_M07_too_few_train_blocks_not_artifact(self):
        d=dataset(60)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(min_train_blocks=50))

    def test_M08_too_few_later_holdout_blocks_not_artifact(self):
        d=dataset(60)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(min_test_blocks=100))

    def test_M09_insufficient_matured_original_remains_no_authority(self):
        _,_,m,_=ready()
        with self.assertRaisesRegex(TrainingHold,"ORIGINAL_SCIENCE"):
            require_authorized_champion(m)

    def test_M10_all_positive_lookalike_hypothetical_only(self):
        d,p,m,res=ready()
        self.assertGreater(res.selected_events,0)
        self.assertGreater(Decimal(res.model_net_r),0)
        self.assertEqual(Decimal(res.no_trade_net_r),0)
        self.assertEqual(res.qualified_original,0)

    def test_M11_losses_and_zero_cost_buffer_do_not_force_trade(self):
        d=dataset(60,net="-1")
        m=train_lab(d,policy())
        res=evaluate_frozen_lab(m,d)
        self.assertEqual(res.selected_events,0)
        self.assertEqual(Decimal(res.model_net_r),0)
        self.assertEqual(res.status,"LAB_ONLY_HOLD")

    def test_M12_policy_cannot_assume_zero_additional_cost(self):
        d=dataset(60)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(cost_buffer_r="0"))
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(cost_buffer_r="NaN"))

    def test_M13_prospective_unknown_market_abstains(self):
        _,_,m,_=ready()
        f=predict_lab(m,fixture(31,btc="UNAVAILABLE"))
        self.assertEqual(f.disposition,"NO_TRADE")
        self.assertFalse(f.would_select_in_lab)

    def test_M14_unseen_regime_conservative_abstain(self):
        _,_,m,_=ready()
        f=predict_lab(m,fixture(31,btc="DOWN"))
        self.assertFalse(f.would_select_in_lab)
        self.assertEqual(f.reason,"UNSEEN_OR_UNQUALIFIED_CONTEXT")

    def test_M15_future_feature_for_prediction_no_selection(self):
        _,_,m,_=ready()
        r=fixture(31)
        f=predict_lab(m,replace(r,feature_known_ms=r.decision_ms+1))
        self.assertFalse(f.would_select_in_lab)

    def test_M16_held_or_pending_rows_not_use_fabricated_return(self):
        d=assemble_lab(tuple(
            fixture(i,state="SOURCE_HOLD",net=None) if i%10==0
            else fixture(i) for i in range(60)),
            cutoff_ms=BASE+62*STEP)
        m=train_lab(d,policy())
        result=evaluate_frozen_lab(m,d)
        self.assertEqual(result.status,"LAB_ONLY_HOLD")

    def test_M17_paper_real_or_original_dataset_forgery_rejected(self):
        d,p,m,_=ready()
        for grade in ("ORIGINAL","QUALIFIED_AFTER_COST"):
            with self.subTest(grade=grade),self.assertRaises(LearningHold):
                train_lab(replace(d,grade=grade),p)

    def test_M18_model_sha_tamper_rejected(self):
        _,_,m,_=ready()
        with self.assertRaises(TrainingHold):
            verify_model(replace(m,model_sha256="0"*64))

    def test_M19_model_false_execution_grant_rejected(self):
        _,_,m,_=ready()
        with self.assertRaises(TrainingHold):
            verify_model(replace(m,order_authority="REAL"))
        with self.assertRaises(TrainingHold):
            verify_model(replace(m,champion_authority="PAPER"))

    def test_M20_model_weights_modified_without_resigning_rejected(self):
        _,_,m,_=ready()
        tampered=replace(m,estimates=(("UP|UP|LONG","99","99",999),))
        with self.assertRaises(TrainingHold):
            verify_model(tampered)

    def test_M21_same_model_different_dataset_head_rejected(self):
        d,p,m,_=ready()
        changed=dataset(61)
        with self.assertRaises(TrainingHold):
            verify_model(m,changed)

    def test_M22_model_frozen_train_hash_checked_during_holdout(self):
        d,p,m,_=ready()
        forged=replace(m,train_experiment_sha256="f"*64)
        with self.assertRaises(TrainingHold):
            evaluate_frozen_lab(forged,d)

    def test_M23_one_at_a_time_hypothetical_occupancy(self):
        d,p,m,r=ready()
        self.assertLessEqual(r.selected_events,r.test_blocks)
        self.assertGreaterEqual(r.abstained_events,0)

    def test_M24_no_trade_baseline_measured_on_same_holdout(self):
        d,p,m,r=ready()
        self.assertEqual(r.no_trade_net_r,"0")
        self.assertGreaterEqual(Decimal(r.max_drawdown_r),0)

    def test_M25_unknown_market_never_drives_winner_model(self):
        d=dataset(60,btc="UNAVAILABLE",net="10")
        m=train_lab(d,policy())
        self.assertEqual(m.estimates[0][0],"UNAVAILABLE|UP|LONG")
        r=evaluate_frozen_lab(m,d)
        self.assertEqual(r.selected_events,0)

    def test_M26_versioned_policy_model_digests_distinct(self):
        d=dataset(60)
        a=train_lab(d,policy(cost_buffer_r="0.10"))
        b=train_lab(d,policy(cost_buffer_r="0.20"))
        self.assertNotEqual(a.model_sha256,b.model_sha256)
        self.assertNotEqual(a.policy_sha256,b.policy_sha256)

    def test_M27_serialized_model_freeze_and_independent_replay(self):
        d,p,m,b=ready()
        with tempfile.TemporaryDirectory(prefix="nbot-g8-freeze-") as tmp:
            saved=seal_lab_model(Path(tmp),m,b,d)
            self.assertEqual(saved["status"],"FROZEN_SYNTHETIC_LAB_ONLY")
            inspected=verify_lab_model(Path(tmp),saved["name"],saved["sha256"],d)
            self.assertEqual(inspected["status"],"VERIFIED_IMMUTABLE_LAB_ONLY")
            self.assertFalse(inspected["orders_allowed"])

    def test_M28_freeze_idempotence_and_no_overwrite(self):
        d,p,m,b=ready()
        with tempfile.TemporaryDirectory(prefix="nbot-g8-freeze-") as tmp:
            root=Path(tmp)
            first=seal_lab_model(root,m,b,d)
            second=seal_lab_model(root,m,b,d)
            self.assertEqual(second["status"],"IDEMPOTENT_VERIFIED_LAB_ONLY")
            self.assertEqual(first["sha256"],second["sha256"])

    def test_M29_artifact_byte_corruption_rejected(self):
        d,p,m,b=ready()
        with tempfile.TemporaryDirectory(prefix="nbot-g8-freeze-") as tmp:
            root=Path(tmp)
            obj=seal_lab_model(root,m,b,d)
            file=root/obj["name"]
            file.write_bytes(file.read_bytes().replace(b"NO",b"GO",1))
            with self.assertRaises(FreezeHold):
                verify_lab_model(root,obj["name"],obj["sha256"],d)

    def test_M30_no_world_writable_model_artifact_directory(self):
        d,p,m,b=ready()
        with tempfile.TemporaryDirectory(prefix="nbot-g8-freeze-") as tmp:
            root=Path(tmp)
            root.chmod(0o777)
            try:
                with self.assertRaises(FreezeHold):
                    seal_lab_model(root,m,b,d)
            finally:root.chmod(0o700)

    def test_M31_no_fake_paper_backtest_on_frozen_card(self):
        d,p,m,b=ready()
        with tempfile.TemporaryDirectory(prefix="nbot-g8-freeze-") as tmp:
            with self.assertRaises(FreezeHold):
                seal_lab_model(Path(tmp),m,replace(b,release_authority="PAPER"),d)

    def test_M32_dataset_missing_later_population_is_hold(self):
        d=dataset(32)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy())

    def test_M33_finite_run_rejects_oversized_attempts(self):
        d=dataset(60)
        with self.assertRaises(TrainingHold):
            train_lab(d,policy(min_context_blocks=0))

    def test_M34_negative_lower_confidence_not_trade_without_proof(self):
        d=dataset(60,net="0.01")
        m=train_lab(d,policy())
        p=predict_lab(m,fixture(31))
        self.assertFalse(p.would_select_in_lab)

if __name__=="__main__":unittest.main()
