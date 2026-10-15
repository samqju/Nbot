"""G7 Learning causal/sampling/uncertainty/no-scientific-data acceptance.

All fake returns are *SYNTHETIC* and the gate always NO_MODEL/NO_TRADE.
"""
import unittest
import tempfile
from pathlib import Path
from dataclasses import replace
from nbot_v5_1.learning_contract import (
    lab_row,assemble_lab,scientific_export,verified_learning_count,
    LearningHold,UNQUALIFIED_GRADE,REQUIRED_LINEAGE)
from nbot_v5_1.learning_science import (
    dependence_blocks,purged_chronological_split,quality_report,
    evaluate_lab,assert_paper_or_real_model_authority)
from nbot_v5_1.learning_snapshots import (
    save_lab_snapshot,verify_lab_snapshot,SnapshotHold)

H="a"*64
BASE=1792000000000
LINEAGE=tuple(sorted((k,H) for k in REQUIRED_LINEAGE))
DETECTORS=(("DONCHIAN_BREAKOUT_V1","MATCH"),("TREND_PULLBACK_V1","NO_MATCH"))


def fixture(i=0,*,decision=None,maturity=None,source=UNQUALIFIED_GRADE,
            channel="VIRTUAL_SYNTHETIC",state="SYNTHETIC_MODELED",net="0.1",
            symbol="BTCUSDT",side="LONG",btc="UP",market="UP",coin="UP",
            states=DETECTORS,k=1,n=2):
    t=BASE+i*600000 if decision is None else decision
    # All features known at decision; outcome long after activation.
    return lab_row(experiment_id=f"{i+1:064x}",event_ms=t-300000,
      feature_known_ms=t-1000,decision_ms=t,
      activated_ms=t+1,exit_ms=t+120000,
      matured_ms=t+125000 if maturity is None else maturity,
      symbol=symbol,side=side,btc_regime=btc,
      market_regime=market,coin_regime=coin,
      structure="RANGE_BREAKOUT",detector_states=states,
      inclusion_k=k,inclusion_n=n,channel=channel,source_grade=source,
      economic_state=state,net_r=net,provenance=LINEAGE)


class G7Learning(unittest.TestCase):
    def test_L01_empty_denominator_not_qualified(self):
        x=assemble_lab((),cutoff_ms=BASE+10000)
        self.assertEqual(verified_learning_count(x),0)
        self.assertEqual(quality_report(x).total,0)

    def test_L02_complete_lab_row_never_original(self):
        r=fixture()
        d=assemble_lab((r,),cutoff_ms=BASE+300000)
        self.assertEqual(len(d.economic_lab_rows),1)
        self.assertEqual(d.qualified_original,0)
        with self.assertRaisesRegex(LearningHold,"INDEPENDENT_ORIGINAL"):
            scientific_export(d)

    def test_L03_future_feature_leak_rejected(self):
        r=fixture()
        bad=lab_row(**{**{k:getattr(r,k) for k in r.__dataclass_fields__
               if k!="row_sha256"},"feature_known_ms":r.decision_ms+1})
        with self.assertRaises(LearningHold):
            assemble_lab((bad,),cutoff_ms=BASE+300000)

    def test_L04_maturation_later_than_cutoff_rejected(self):
        with self.assertRaises(LearningHold):
            assemble_lab((fixture(),),cutoff_ms=BASE+124999)

    def test_L05_duplicate_hypothesis_same_detectors_not_new_sample(self):
        a=fixture()
        with self.assertRaises(LearningHold):
            assemble_lab((a,a),cutoff_ms=BASE+500000)

    def test_L06_paper_real_source_claims_never_count(self):
        for channel in ("PAPER","REAL","VIRTUAL_ORIGINAL_CLAIM"):
            with self.subTest(channel=channel),self.assertRaises(LearningHold):
                assemble_lab((fixture(channel=channel),),cutoff_ms=BASE+400000)

    def test_L07_forged_original_grade_rejected(self):
        with self.assertRaises(LearningHold):
            assemble_lab((fixture(source="ORIGINAL_VERIFIED"),),cutoff_ms=BASE+400000)

    def test_L08_forged_row_sha_rejected(self):
        a=fixture()
        with self.assertRaises(LearningHold):
            assemble_lab((replace(a,net_r="20"),),cutoff_ms=BASE+400000)

    def test_L09_no_fees_cost_pending_must_remain_unscored(self):
        a=fixture(state="COST_PENDING",net=None)
        d=assemble_lab((a,),cutoff_ms=BASE+400000)
        self.assertEqual(quality_report(d).pending,1)
        with self.assertRaises(LearningHold):
            assemble_lab((fixture(state="COST_PENDING",net="0"),),cutoff_ms=BASE+400000)

    def test_L10_original_claim_hold_requires_null_net(self):
        d=assemble_lab((fixture(state="SOURCE_HOLD",net=None),),
                       cutoff_ms=BASE+400000)
        self.assertEqual(quality_report(d).held,1)

    def test_L11_invalid_missing_lineage_rejected(self):
        a=fixture()
        no=tuple(x for x in a.provenance if x[0]!="g4")
        row=lab_row(**{**{k:getattr(a,k) for k in a.__dataclass_fields__
                         if k!="row_sha256"},"provenance":no})
        with self.assertRaises(LearningHold):
            assemble_lab((row,),cutoff_ms=BASE+400000)

    def test_L12_duplicate_pattern_tags_cannot_multiply_outcomes(self):
        x=fixture(states=(("DONCHIAN_BREAKOUT_V1","MATCH"),
                          ("DONCHIAN_BREAKOUT_V1","MATCH")))
        with self.assertRaises(LearningHold):
            assemble_lab((x,),cutoff_ms=BASE+400000)

    def test_L13_inclusion_zero_cannot_make_winning_lab_record(self):
        with self.assertRaises(LearningHold):
            assemble_lab((fixture(k=0,n=40),),cutoff_ms=BASE+400000)

    def test_L14_simultaneous_long_short_dependence_one_block(self):
        a=fixture()
        b=fixture(1,decision=BASE,side="SHORT")
        d=assemble_lab((a,b),cutoff_ms=BASE+400000)
        self.assertEqual(len(dependence_blocks(d.rows)),1)

    def test_L15_wide_nonoverlap_two_independent_blocks(self):
        d=assemble_lab((fixture(0),fixture(1)),cutoff_ms=BASE+1000000)
        self.assertEqual(quality_report(d).effective_independent_blocks,2)

    def test_L16_many_correlated_wins_do_not_reach_2000_independent(self):
        rows=tuple(fixture(i,decision=BASE,side="LONG" if i%2 else "SHORT")
                   for i in range(2000))
        d=assemble_lab(rows,cutoff_ms=BASE+300000)
        q=quality_report(d)
        self.assertEqual(q.synthetic_modeled,2000)
        self.assertEqual(q.effective_independent_blocks,1)
        self.assertEqual(q.scientifically_qualified,0)
        self.assertFalse(q.ready_for_original_science)

    def test_L17_training_split_respects_maturation_embargo(self):
        rows=(fixture(0),fixture(1),fixture(2))
        d=assemble_lab(rows,cutoff_ms=BASE+2000000)
        train,test,purged=purged_chronological_split(d.rows,
                    cutoff_ms=BASE+650000,embargo_ms=100000)
        self.assertEqual(len(train),1)
        self.assertEqual(len(test),1)
        self.assertEqual(len(purged),1)

    def test_L18_no_future_leak_at_holdout_boundary(self):
        rows=(fixture(0),fixture(1))
        d=assemble_lab(rows,cutoff_ms=BASE+2000000)
        train,test,purged=purged_chronological_split(d.rows,
                         cutoff_ms=BASE+600000,embargo_ms=0)
        self.assertEqual((len(train),len(test),len(purged)),(1,0,1))

    def test_L19_positive_lab_returns_still_no_trading_model(self):
        d=assemble_lab(tuple(fixture(i,net="9.0") for i in range(100)),
                       cutoff_ms=BASE+100*600000)
        review=evaluate_lab(d,split_at_ms=BASE+50*600000,embargo_ms=0)
        self.assertEqual(review.model_status,"NO_MODEL")
        self.assertEqual(review.recommendation,"NO_TRADE")
        self.assertEqual(review.financial_authority,"NONE")
        self.assertFalse(review.scientific_advantage_proved)

    def test_L20_uncertain_regimes_do_not_force_learned_edge(self):
        rows=tuple(fixture(i,btc="UP" if i%2 else "DOWN",
                   market="RANGE" if i%3 else "TRANSITION",
                   side="SHORT" if i%2 else "LONG",net="-1.0" if i%2 else "1.0")
                   for i in range(50))
        d=assemble_lab(rows,cutoff_ms=BASE+60*600000)
        r=evaluate_lab(d,split_at_ms=BASE+26*600000,embargo_ms=0)
        self.assertGreater(len(r.findings),1)
        self.assertTrue(all(x.status=="LAB_ONLY_NOT_QUALIFIED" for x in r.findings))

    def test_L21_repeated_bootstrap_is_deterministic(self):
        d=assemble_lab(tuple(fixture(i,net=str(i%7-3)) for i in range(40)),
                       cutoff_ms=BASE+50*600000)
        a=evaluate_lab(d,split_at_ms=BASE+30*600000,embargo_ms=0)
        b=evaluate_lab(d,split_at_ms=BASE+30*600000,embargo_ms=0)
        self.assertEqual(a,b)

    def test_L22_large_invalid_floating_scientific_label_rejected(self):
        with self.assertRaises(LearningHold):
            assemble_lab((fixture(net="NaN"),),cutoff_ms=BASE+400000)
        with self.assertRaises(LearningHold):
            assemble_lab((fixture(net="200.0"),),cutoff_ms=BASE+400000)

    def test_L23_no_paper_or_real_release_even_with_good_lab_finding(self):
        d=assemble_lab(tuple(fixture(i,net="2") for i in range(20)),
                       cutoff_ms=BASE+25*600000)
        a=evaluate_lab(d,split_at_ms=BASE+10*600000,embargo_ms=0)
        with self.assertRaisesRegex(LearningHold,"NO_SCIENTIFIC"):
            assert_paper_or_real_model_authority(a)

    def test_L24_snapshot_valid_private_no_model(self):
        with tempfile.TemporaryDirectory(prefix="nbot-g7-") as root:
            d=assemble_lab((fixture(),),cutoff_ms=BASE+400000)
            r=evaluate_lab(d,split_at_ms=BASE+180000,embargo_ms=0)
            saved=save_lab_snapshot(Path(root),d,r)
            a=verify_lab_snapshot(Path(root),saved["name"],saved["sha256"])
            self.assertEqual(a["rows"],1)
            self.assertEqual(a["status"],"VERIFIED_LAB_NO_MODEL")
            self.assertEqual(save_lab_snapshot(Path(root),d,r)["status"],
                             "IDEMPOTENT_VERIFIED")

    def test_L25_snapshot_modified_bytes_refused(self):
        with tempfile.TemporaryDirectory(prefix="nbot-g7-") as root:
            d=assemble_lab((fixture(),),cutoff_ms=BASE+400000)
            r=evaluate_lab(d,split_at_ms=BASE+180000,embargo_ms=0)
            saved=save_lab_snapshot(Path(root),d,r)
            p=Path(root)/saved["name"]
            b=p.read_bytes()
            p.write_bytes(b.replace(b"NO_MODEL",b"GO_MODEL"))
            with self.assertRaises(SnapshotHold):
                verify_lab_snapshot(Path(root),saved["name"],saved["sha256"])

    def test_L26_snapshot_public_dir_denied(self):
        with tempfile.TemporaryDirectory(prefix="nbot-g7-") as root:
            p=Path(root)
            d=assemble_lab((fixture(),),cutoff_ms=BASE+400000)
            r=evaluate_lab(d,split_at_ms=BASE+180000,embargo_ms=0)
            p.chmod(0o777)
            try:
                with self.assertRaises(SnapshotHold):
                    save_lab_snapshot(p,d,r)
            finally:
                p.chmod(0o700)

    def test_L27_snapshot_quota_refused(self):
        with tempfile.TemporaryDirectory(prefix="nbot-g7-") as root:
            d=assemble_lab(tuple(fixture(i) for i in range(50)),
                           cutoff_ms=BASE+51*600000)
            r=evaluate_lab(d,split_at_ms=BASE+30*600000,embargo_ms=0)
            with self.assertRaises(SnapshotHold):
                save_lab_snapshot(Path(root),d,r,max_bytes=1024)

    def test_L28_snapshot_qualified_claim_refused(self):
        with tempfile.TemporaryDirectory(prefix="nbot-g7-") as root:
            d=assemble_lab((fixture(),),cutoff_ms=BASE+400000)
            r=evaluate_lab(d,split_at_ms=BASE+180000,embargo_ms=0)
            fake=replace(r,model_status="APPROVED")
            with self.assertRaises(SnapshotHold):
                save_lab_snapshot(Path(root),d,fake)

    def test_L29_dataset_forged_grade_and_qualified_count_rejected(self):
        d=assemble_lab((fixture(),),cutoff_ms=BASE+400000)
        for x in (replace(d,grade="ORIGINAL"),
                  replace(d,qualified_original=2000)):
            with self.assertRaises(LearningHold):
                verified_learning_count(x)

    def test_L31_manual_dataset_forgery_rejected_by_every_science_gateway(self):
        d=assemble_lab((fixture(),),cutoff_ms=BASE+400000)
        forged=replace(d,dataset_sha256="f"*64)
        with self.assertRaises(LearningHold):
            verified_learning_count(forged)
        with self.assertRaises(LearningHold):
            evaluate_lab(forged,split_at_ms=BASE+180000,embargo_ms=0)
        # A complete forged row must also be checked at the review boundary.
        bad=replace(d,rows=(replace(d.rows[0],net_r="99"),))
        with self.assertRaises(LearningHold):
            quality_report(bad)

    def test_L30_economically_unevaluated_rows_stay_denominator(self):
        rows=(fixture(0),fixture(1,state="CENSORED",net=None),
              fixture(2,state="COST_PENDING",net=None),
              fixture(3,state="RESTART_HOLD",net=None))
        d=assemble_lab(rows,cutoff_ms=BASE+3000000)
        q=quality_report(d)
        self.assertEqual((q.total,q.synthetic_modeled,q.censored,q.pending,q.held),
                         (4,1,1,1,1))

if __name__=="__main__": unittest.main()
