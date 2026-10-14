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

    def test_restart_replays_without_duplicate_and_source_unchanged(self):
        before=self.source.read_bytes()
        a=self.engine.tick(COMMITTED+300)
        self.engine.close();self.engine=ContinuousResearch(**self.kwargs)
        b=self.engine.tick(COMMITTED+400)
        self.assertEqual(a["candidate_population"],b["candidate_population"])
        self.assertEqual(a["g4_maturity"],b["g4_maturity"])
        self.assertEqual(before,self.source.read_bytes())

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

    def test_untrusted_cache_is_rejected(self):
        q=independent_asof_entry_quote(vault_db=self.vault,symbol="BTCUSDT",decision_at_ms=COMMITTED,audit_cache={"integrity_audit":"PASS"})
        self.assertEqual(q.state,"HOLD")
