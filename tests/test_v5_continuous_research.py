"""End-to-end synthetic source fixtures; never scientific acceptance."""
from contextlib import closing
import gc
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from nbot.v5.continuous_research import ContinuousResearch
from nbot.v5.g4_forward_vault import ForwardSourceVault
from nbot.v5.g4_forward_entry_quote import IndependentSourceAudit,independent_asof_entry_quote
from nbot.v5.g4_prospective_policy import *
from nbot.v5.science import Protocol
from tests.test_v5_g4_source_binding import db_fixture,canonical,digest,EVENT,COMMITTED
from tests.test_v5_g4_forward_vault import quote,trade


class ContinuousIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.source=self.base/"g1g2g3.sqlite";db_fixture(self.source)
        self.vault=self.base/"vault.sqlite"
        with closing(sqlite3.connect(self.source)) as db:
            g=json.loads(db.execute("SELECT payload_json FROM g3_event_context").fetchone()[0])
            f=g["feature_evidence"]
            f["btc"].update(valid=True,confidence_score=.8,regime="RANGE",features={"return_1h":.01})
            f.update(breadth_available=True,breadth_1h=.4)
            for coin in f["coins"].values():
                coin.update(structure="TREND_UP",relative_momentum_1h=.002,
                            features={"atr14_fraction":.01,"return_1h":.012})
            del f["feature_sha256"];f["feature_sha256"]=digest(f)
            db.execute("UPDATE g3_event_context SET payload_json=?,payload_sha=?",(canonical(g),digest(g)))
            syms=json.loads(db.execute("SELECT symbols_json FROM g1f_universe_snapshots").fetchone()[0]);db.commit()
        with closing(sqlite3.connect(self.vault)) as db:
            v=ForwardSourceVault(db,symbols=syms)
            v.connect(route="public_bookticker",at_ms=COMMITTED-1000)
            for sym in syms:v.ingest(route="public_bookticker",at_ms=COMMITTED-100,raw=quote(symbol=sym,bid="100.0",ask="100.1",at=COMMITTED-100))
            v.connect(route="market_aggtrade",at_ms=COMMITTED-99)
            v.ingest(route="market_aggtrade",at_ms=COMMITTED-1,raw=trade(symbol="BTCUSDT",at=COMMITTED-1))
            raw=json.loads(trade(symbol="BTCUSDT",agg=101,first=503,last=505,at=COMMITTED+200))
            raw["data"]["p"]="105"
            v.ingest(route="market_aggtrade",at_ms=COMMITTED+200,raw=json.dumps(raw).encode())
        self.registry=self.base/"policy.json"
        spec={"declared_at_ms":EVENT-600000,"activates_at_ms":EVENT-300000,"horizon_ms":14400000,
              "max_quote_age_ms":1000,"atr_risk_multiple":"1.5","target_r_multiple":"2.0",
              "min_risk_fraction":"0.005","entry_convention":ENTRY_CONVENTION,"exit_policy_id":EXIT_POLICY_ID,
              "risk_policy_id":RISK_POLICY_ID,"cost_policy_id":COST_POLICY_ID,"research_authority":"OBSERVE_ONLY"}
        frozen=freeze_template(spec)
        self.registry.write_text(json.dumps({"registry_version":"NBOT_V5_G4_PREDECLARED_POLICY_REGISTRY_V1",
                                             "research_only":True,"financial_authority":"NONE","spec":spec,"policy_sha256":frozen.policy_sha256}))
        self.root=self.base/"research";self.root.mkdir(mode=0o700)
        self.kwargs=dict(source=self.source,vault=self.vault,registry=self.registry,root=self.root,
                         protocol=Protocol(EVENT-1000,EVENT-500,EVENT+10*86400000),start_event_ms=EVENT)
        self.engine=ContinuousResearch(**self.kwargs)

    def tearDown(self):
        self.engine.close();gc.collect();self.tmp.cleanup()

    def test_complete_population_and_early_paths_never_fake_economics(self):
        r=self.engine.tick(COMMITTED+300)
        self.assertEqual(r["candidate_population"],100)
        self.assertEqual(r["g4_maturity"]["total_frozen_intents"],100)
        self.assertEqual(r["original_price_paths"],2)
        self.assertEqual(r["qualified_independently_reviewed_outcomes"],0)
        self.assertEqual(r["g7_paper_state"],"LOCKED")

    def test_v4_bounded_catchup_does_not_replay_completed_event(self):
        from nbot.v5.continuous_research import bounded_research_catchup
        first=bounded_research_catchup(self.engine,COMMITTED+300)
        self.assertEqual(first["candidate_population"],100)
        self.assertEqual(first["catchup_processed_events"],1)
        self.assertEqual(first["catchup_status"],"CAUGHT_UP")
        self.assertEqual(first["qualified_independently_reviewed_outcomes"],0)
        again=bounded_research_catchup(self.engine,COMMITTED+400)
        self.assertEqual(again["catchup_processed_events"],0)
        self.assertEqual(again["candidate_population"],100)
        self.assertEqual(self.engine.store.db.execute(
            "SELECT COUNT(*) FROM research_journal WHERE kind='EVENT_COMPLETE'"
        ).fetchone()[0],1)

    def test_v4_crash_halfway_through_event_recovers_original_100(self):
        from nbot.v5.continuous_research import bounded_research_catchup
        from unittest.mock import patch
        original=self.engine.store.append
        seen=[0]
        def interrupt(identity,kind,at_ms,body):
            if kind=="CANDIDATE":
                seen[0]+=1
                if seen[0]==23:
                    raise OSError("SYNTHETIC_PROCESS_CRASH")
            return original(identity,kind,at_ms,body)
        source_bytes=self.source.read_bytes()
        with patch.object(self.engine.store,"append",side_effect=interrupt):
            with self.assertRaisesRegex(OSError,"SYNTHETIC_PROCESS_CRASH"):
                bounded_research_catchup(self.engine,COMMITTED+300)
        self.assertEqual(self.engine.store.db.execute(
            "SELECT COUNT(*) FROM research_journal WHERE kind='EVENT_COMPLETE'"
        ).fetchone()[0],0)
        self.engine.close()
        self.engine=ContinuousResearch(**self.kwargs)
        result=bounded_research_catchup(self.engine,COMMITTED+400)
        self.assertEqual(result["candidate_population"],100)
        self.assertEqual(result["catchup_processed_events"],1)
        self.assertEqual(result["catchup_status"],"CAUGHT_UP")
        self.assertEqual(self.engine.store.db.execute(
            "SELECT COUNT(*) FROM research_journal WHERE kind='CANDIDATE'"
        ).fetchone()[0],100)
        self.assertEqual(self.source.read_bytes(),source_bytes)
        self.assertEqual(result["g7_paper_state"],"LOCKED")

    def test_path_queue_cycles_550_origins_with_only_250_rows_in_ram(self):
        from nbot.v5.continuous_research import bounded_pending_path_page
        # 550 synthetic *unmatured* label ids. This is an isolated research DB.
        with self.engine.labels as db:
            for j in range(550):
                label=f"extra-{j:05d}"
                db.execute("INSERT INTO g4_label_intents VALUES (?,?,?,?,?,?,?,?)",
                           (label,label,"f"*64,EVENT,COMMITTED+1000+j,
                            COMMITTED+14401000+j,"0"*64,"{}"))
        page=bounded_pending_path_page(self.engine.labels,self.engine.store)
        self.assertEqual(len(page),250)
        self.assertEqual(len({p[0] for p in page}),250)
        for i,expected in enumerate((250,50,250)):
            tail=page[-1]
            self.engine.store.append("cursor-test:"+str(i),"PATH_SCAN_CURSOR",COMMITTED,
                                     {"decision_at_ms":tail[2],"label_id":tail[0]})
            page=bounded_pending_path_page(self.engine.labels,self.engine.store)
            self.assertEqual(len(page),expected)
        # The seek cursor wraps safely after the final 50 unprocessed rows.
        self.assertLessEqual(len(page),250)

    def test_restart_replays_without_duplicate_and_source_unchanged(self):
        before=self.source.read_bytes()
        a=self.engine.tick(COMMITTED+300)
        self.engine.close();self.engine=ContinuousResearch(**self.kwargs)
        b=self.engine.tick(COMMITTED+400)
        self.assertEqual(a["candidate_population"],b["candidate_population"])
        self.assertEqual(a["g4_maturity"],b["g4_maturity"])
        self.assertEqual(before,self.source.read_bytes())

    def test_held_g3_context_keeps_entire_population_as_hold(self):
        # The original G3 event can be source-held with null features.
        # G4 must preserve the 100-direction denominator without a crash,
        # fake BTC regime or synthesized economic outcomes.
        with closing(sqlite3.connect(self.source)) as db:
            g=json.loads(db.execute(
                "SELECT payload_json FROM g3_event_context").fetchone()[0])
            g["status"]="HOLD"
            g["reasons"]=["G3_UNKNOWN_OR_INCOMPLETE_CROSS_SECTION"]
            g["feature_evidence"]=None
            db.execute("UPDATE g3_event_context SET payload_json=?,payload_sha=?",
                       (canonical(g),digest(g)))
            db.commit()
        original=self.source.read_bytes()
        report=self.engine.tick(COMMITTED+300)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["admission_states"],{"HOLD":100})
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)
        self.assertEqual(report["g4_maturity"]["total_frozen_intents"],0)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual(report["g7_paper_state"],"LOCKED")

    def test_missing_forward_vault_cannot_block_held_denominator(self):
        self.vault.unlink()
        report=self.engine.tick(COMMITTED+300)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["admission_states"],{"HOLD":100})
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)
        self.assertEqual(report["g4_maturity"]["total_frozen_intents"],0)
        self.assertEqual(report["g7_paper_state"],"LOCKED")
        self.assertFalse(self.vault.exists())

    def test_corrupt_forward_vault_cannot_fabricate_economics(self):
        with closing(sqlite3.connect(self.vault)) as db:
            # Deliberate corruption bypasses the immutability trigger, as an
            # offline malicious-storage fixture; production never drops it.
            db.execute("DROP TRIGGER g4_forward_receipts_no_update")
            db.execute("UPDATE g4_forward_receipts SET raw_sha256=? WHERE seq=1",
                       ("0"*64,))
            db.commit()
        report=self.engine.tick(COMMITTED+300)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["admission_states"],{"HOLD":100})
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)

    def test_missing_policy_tracks_held_full_population(self):
        self.registry.unlink()
        r=self.engine.tick(COMMITTED+300)
        self.assertEqual(r["candidate_population"],100)
        self.assertEqual(r["admission_states"],{"HOLD":100})
        self.assertEqual(r["g4_maturity"]["total_frozen_intents"],0)

    def test_missing_independent_export_review_cannot_score(self):
        with self.assertRaisesRegex(ValueError,"REVIEW"):
            self.engine.accept_verified_export({"rows":[]},{},None,COMMITTED+300)

    def test_expired_unresolved_paths_never_become_losses(self):
        a=self.engine.tick(COMMITTED+14401000)
        b=self.engine.tick(COMMITTED+14402000)
        self.assertEqual(b["qualified_independently_reviewed_outcomes"],0)
        self.assertEqual(a["candidate_population"],b["candidate_population"])

    def test_cached_quote_cannot_read_beyond_audited_prefix(self):
        audit=IndependentSourceAudit(self.vault)
        with closing(sqlite3.connect(self.vault)) as db:
            v=ForwardSourceVault(db,symbols=["BTCUSDT"]+[f"COIN{i:02d}USDT" for i in range(49)])
            v.ingest(route="public_bookticker",at_ms=COMMITTED+500,raw=quote(symbol="BTCUSDT",at=COMMITTED+500))
        q=independent_asof_entry_quote(vault_db=self.vault,symbol="BTCUSDT",decision_at_ms=COMMITTED+500,audit_cache=audit)
        self.assertEqual(q.at_ms,COMMITTED-100)

    def test_full_g1_g7_missing_original_economics_stays_locked(self):
        from nbot.v5.science import dataset, evaluate, fit_candidate
        from nbot.v5.guarded_paper import GuardedPaper
        from tests.test_v5_guarded_paper import POLICY
        now=COMMITTED+300
        report=self.engine.tick(now)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)
        orig=dataset(self.engine.verified_rows(),cutoff_ms=now,grade="ORIGINAL")
        science=evaluate(orig,self.kwargs["protocol"])
        self.assertEqual(science["qualified_outcomes"],0)
        self.assertFalse(science["scientifically_accepted"])
        self.assertIn("OUTCOMES_BELOW_2000",science["reasons"])
        with self.assertRaisesRegex(ValueError,"G6_G5_SCIENCE_HOLD"):
            fit_candidate(orig,boundary_ms=now,protocol=self.kwargs["protocol"])
        paper=GuardedPaper(self.base/"guarded_paper.sqlite",policy=POLICY)
        try:
            state=paper.reconcile()
            self.assertEqual(state["paper_state"],"LOCKED")
            self.assertTrue(all(b["fills"]==0 for b in state["books"].values()))
            with self.assertRaisesRegex(ValueError,"TWO_QUALIFIED_MODELS_REQUIRED"):
                paper.unlock({},now)
        finally:
            paper.store.close()

    def test_compressed_g4_archive_replays_original_sources_with_no_order(self):
        from nbot.v5.g4_segmented_source import SegmentedForwardSource
        segment_root=self.base/"segments"
        segment_root.mkdir(mode=0o700)
        with closing(sqlite3.connect(self.source)) as src:
            syms=json.loads(src.execute(
                "SELECT symbols_json FROM g1f_universe_snapshots").fetchone()[0])
        recorder=SegmentedForwardSource(segment_root,symbols=syms)
        with closing(sqlite3.connect(self.vault)) as old:
            for route,kind,at,raw in old.execute(
                "SELECT route,kind,at_ms,raw_frame FROM g4_forward_receipts ORDER BY seq"):
                if kind=="OPEN":
                    recorder.connect(route=route,at_ms=at)
                elif kind=="FRAME":
                    recorder.ingest(route=route,at_ms=at,raw=raw)
                elif kind=="CLOSED":
                    recorder.disconnect(route=route,at_ms=at)
                else:
                    self.fail("unexpected fixture source marker")
        recorder.flush()
        self.assertEqual(recorder.audit()["audit"],"PASS")
        self.engine.vault=segment_root
        report=self.engine.tick(COMMITTED+300)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["g4_maturity"]["total_frozen_intents"],100)
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)
        self.assertEqual(report["g7_paper_state"],"LOCKED")
        self.assertFalse(list(segment_root.glob("*.sqlite*")))

    def test_streaming_quote_and_trade_path_when_ram_view_exceeds_cap(self):
        from unittest.mock import patch
        from nbot.v5.g4_segmented_source import SegmentedForwardSource
        segment_root=self.base/"segments"
        segment_root.mkdir(mode=0o700)
        with closing(sqlite3.connect(self.source)) as src:
            syms=json.loads(src.execute(
                "SELECT symbols_json FROM g1f_universe_snapshots").fetchone()[0])
        recorder=SegmentedForwardSource(segment_root,symbols=syms)
        with closing(sqlite3.connect(self.vault)) as old:
            for route,kind,at,raw in old.execute(
                "SELECT route,kind,at_ms,raw_frame FROM g4_forward_receipts ORDER BY seq"):
                if kind=="OPEN":recorder.connect(route=route,at_ms=at)
                elif kind=="FRAME":recorder.ingest(route=route,at_ms=at,raw=raw)
                elif kind=="CLOSED":recorder.disconnect(route=route,at_ms=at)
        recorder.flush()
        self.engine.vault=segment_root
        # The production bridge has a finite 100k-frame/128MiB RAM view.
        # Fail that view deliberately: the original source must remain usable
        # via streaming, without data-loss reclassification or SQL tick writes.
        with patch("nbot.v5.continuous_research.verified_ram_vault",
                   side_effect=ValueError("G4_BRIDGE_FRAME_OR_BYTES_CAP_HOLD")):
            report=self.engine.tick(COMMITTED+300)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["g4_maturity"]["total_frozen_intents"],100)
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)
        self.assertEqual(report["g7_paper_state"],"LOCKED")
        self.assertFalse(list(segment_root.rglob("*.sqlite*")))

    def test_corrupted_compressed_g4_vault_holds_all_candidates(self):
        from nbot.v5.g4_segmented_source import SegmentedForwardSource
        segment_root=self.base/"segments"
        segment_root.mkdir(mode=0o700)
        with closing(sqlite3.connect(self.source)) as src:
            syms=json.loads(src.execute(
                "SELECT symbols_json FROM g1f_universe_snapshots").fetchone()[0])
        recorder=SegmentedForwardSource(segment_root,symbols=syms)
        recorder.connect(route="public_bookticker",at_ms=COMMITTED-1000)
        recorder.flush()
        path=next(segment_root.glob("segment-*.gz"))
        path.write_bytes(b"corruption"+path.read_bytes())
        self.engine.vault=segment_root
        report=self.engine.tick(COMMITTED+300)
        self.assertEqual(report["candidate_population"],100)
        self.assertEqual(report["admission_states"],{"HOLD":100})
        self.assertEqual(report["qualified_independently_reviewed_outcomes"],0)

    def test_untrusted_cache_is_rejected(self):
        q=independent_asof_entry_quote(vault_db=self.vault,symbol="BTCUSDT",decision_at_ms=COMMITTED,audit_cache={"integrity_audit":"PASS"})
        self.assertEqual(q.state,"HOLD")
