"""G4 in-memory / temporary standalone SQLite regression suite. No live DB."""
import os
import sqlite3
import tempfile
import unittest

from nbot.v5.g4_research_ledger import (
    append_terminal, freeze_label_intent, init_offline_ledger,
    qualified_economic_label_count, status_breakdown, maturity_calendar,
)
from tests.test_v5_g4_price_path import EVENT, DECISION, MATURITY


def fixtures():
    candidate={
        "decision_id":"a"*64,"status":"OBSERVED","side":"LONG",
        "symbol":"BTCUSDT","event_open_ms":EVENT,"decision_at_ms":DECISION,
        "source_digest":"b"*64,"btc_source_digest":"c"*64
    }
    policy={
        "policy_sha256":"d"*64, "horizon_ms":600_000,
        "declared_at_ms":DECISION,"exit_policy_id":"V1",
    }
    return candidate,policy


def terminal(status="SCORED"):
    base={"status":status,"settled_at_ms":MATURITY+100,
          "order_authority":"NONE"}
    if status=="SCORED":
        base.update({"source_grade":"QUOTE_CONSTRAINED_SIMULATION",
                     "original_sources_independently_verified":True,
                     "path_sha256":"e"*64,"quote_cost_sha256":"f"*64,
                     "label_sha256":"1"*64,
                     "net_r":"-0.123","gross_r":"0.12"})
    elif status=="PATH_ONLY":
        base.update({"source_grade":"HISTORICAL_AGGTRADE_PATH",
                     "path_sha256":"e"*64, "gross_r":"0.12",
                     "net_r":None})
    else:
        base.update({"source_grade":"NONE","gross_r":None,"net_r":None,
                     "reason_codes":["MISSING_OR_AMBIGUOUS_PRICE_PATH"]})
    return base


class G4ImmutableLedgerTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        init_offline_ledger(self.db)
        self.c,self.p=fixtures()
        self.key=freeze_label_intent(self.db,self.c,self.p)

    def tearDown(self):
        self.db.close()

    def test_intent_frozen_idempotent(self):
        self.assertEqual(freeze_label_intent(self.db,self.c,self.p),self.key)
        self.assertEqual(self.db.execute("select count(*) from g4_label_intents").fetchone()[0],1)

    def test_changed_same_id_rejected(self):
        self.p["exit_policy_id"]="CHANGED"
        with self.assertRaisesRegex(ValueError,"G4_INTENT_CHANGED_SAME_ID"):
            freeze_label_intent(self.db,self.c,self.p)

    def test_missing_frozen_policy_rejected(self):
        self.p["declared_at_ms"]=DECISION+1
        with self.assertRaisesRegex(ValueError,"G4_INTENT_NOT_PREDECLARED_OR_CAUSAL"):
            freeze_label_intent(self.db,self.c,self.p)

    def test_scored_quote_grade_only_when_explicit_verified_after_cost(self):
        self.assertTrue(append_terminal(self.db,self.key,terminal()))
        self.assertEqual(qualified_economic_label_count(self.db),1)

    def test_scored_replay_is_idempotent(self):
        self.assertTrue(append_terminal(self.db,self.key,terminal()))
        self.assertFalse(append_terminal(self.db,self.key,terminal()))

    def test_scored_cannot_use_trade_path_price_only(self):
        p=terminal("PATH_ONLY")
        p["status"]="SCORED"
        with self.assertRaisesRegex(ValueError,"G4_SCORED_REQUIRES_INDEPENDENT_AFTER_COST_SOURCE"):
            append_terminal(self.db,self.key,p)

    def test_scored_requires_original_independent_qualification(self):
        p=terminal()
        p["original_sources_independently_verified"]=False
        with self.assertRaisesRegex(ValueError,"G4_SCORED_REQUIRES_INDEPENDENT_AFTER_COST_SOURCE"):
            append_terminal(self.db,self.key,p)

    def test_path_only_never_counts_training_outcome(self):
        self.assertTrue(append_terminal(self.db,self.key,terminal("PATH_ONLY")))
        self.assertEqual(qualified_economic_label_count(self.db),0)

    def test_censored_not_trainable(self):
        append_terminal(self.db,self.key,terminal("CENSORED"))
        self.assertEqual(qualified_economic_label_count(self.db),0)
        self.assertEqual(status_breakdown(self.db)["CENSORED"],1)

    def test_unresolved_not_trainable(self):
        append_terminal(self.db,self.key,terminal("UNRESOLVED"))
        self.assertEqual(qualified_economic_label_count(self.db),0)

    def test_dual_terminal_scored_unresolved_refused(self):
        append_terminal(self.db,self.key,terminal("SCORED"))
        with self.assertRaisesRegex(ValueError,"G4_CONFLICTING_TERMINAL_REJECTED"):
            append_terminal(self.db,self.key,terminal("UNRESOLVED"))
        self.assertEqual(status_breakdown(self.db),{"SCORED":1})

    def test_unresolved_cannot_be_backfilled_as_scored_in_place(self):
        append_terminal(self.db,self.key,terminal("UNRESOLVED"))
        with self.assertRaisesRegex(ValueError,"G4_CONFLICTING_TERMINAL_REJECTED"):
            append_terminal(self.db,self.key,terminal("SCORED"))

    def test_immovable_intent_via_sql_triggers(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError,"G4_IMMUTABLE_INTENT"):
            self.db.execute("UPDATE g4_label_intents SET policy_sha256='x'")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"G4_IMMUTABLE_INTENT"):
            self.db.execute("DELETE FROM g4_label_intents")

    def test_immovable_terminal_via_sql_triggers(self):
        append_terminal(self.db,self.key,terminal())
        with self.assertRaisesRegex(sqlite3.IntegrityError,"G4_IMMUTABLE_TERMINAL"):
            self.db.execute("UPDATE g4_label_terminals SET terminal_status='CENSORED'")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"G4_IMMUTABLE_TERMINAL"):
            self.db.execute("DELETE FROM g4_label_terminals")

    def test_censored_rejects_fabricated_profit(self):
        p=terminal("CENSORED")
        p["gross_r"]="10"
        with self.assertRaisesRegex(ValueError,"G4_UNRESOLVED_OR_CENSORED_CANNOT_SCORE"):
            append_terminal(self.db,self.key,p)

    def test_unresolved_requires_reason(self):
        p=terminal("UNRESOLVED")
        p["reason_codes"]=[]
        with self.assertRaisesRegex(ValueError,"G4_MISSING_TERMINAL_REASON"):
            append_terminal(self.db,self.key,p)

    def test_path_only_rejects_net_r(self):
        p=terminal("PATH_ONLY")
        p["net_r"]="100"
        with self.assertRaisesRegex(ValueError,"G4_PATH_ONLY_NEVER_ECONOMIC_SCORE"):
            append_terminal(self.db,self.key,p)

    def test_scored_requires_mature_economic_outcome(self):
        p=terminal()
        p["settled_at_ms"]=MATURITY-1
        with self.assertRaisesRegex(ValueError,"G4_TERMINAL_PREMATURE"):
            append_terminal(self.db,self.key,p)

    def test_model_counter_one_even_with_many_matched_pattern_tags(self):
        append_terminal(self.db,self.key,terminal())
        self.assertEqual(qualified_economic_label_count(self.db),1)

    def test_invalid_order_authority_rejected(self):
        p=terminal()
        p["order_authority"]="BINANCE"
        with self.assertRaisesRegex(ValueError,"G4_FINANCIAL_AUTHORITY_FORBIDDEN"):
            append_terminal(self.db,self.key,p)

    def test_an_undeclared_intent_cannot_terminalize(self):
        with self.assertRaisesRegex(ValueError,"G4_UNDECLARED_INTENT"):
            append_terminal(self.db,"9"*64,terminal())


    def test_maturation_calendar_before_horizon_is_pending_not_score(self):
        r=maturity_calendar(self.db,asof_ms=MATURITY-1)
        self.assertEqual(r["status_counts"]["PENDING"],1)
        self.assertEqual(r["qualified_economic_outcomes"],0)
        self.assertFalse(r["training_gate_unlocked"])

    def test_maturation_calendar_after_horizon_without_source_not_loss(self):
        r=maturity_calendar(self.db,asof_ms=MATURITY+1)
        self.assertEqual(r["status_counts"]["MATURE_BUT_UNRESOLVED"],1)
        self.assertEqual(r["qualified_economic_outcomes"],0)

    def test_maturation_calendar_one_event_not_independent_tag_count(self):
        append_terminal(self.db,self.key,terminal("SCORED"))
        r=maturity_calendar(self.db,asof_ms=MATURITY+1)
        self.assertEqual(r["total_frozen_intents"],1)
        self.assertEqual(r["distinct_scored_five_minute_events"],1)
        self.assertEqual(r["qualified_economic_outcomes"],1)
        self.assertEqual(r["automatic_paper_or_live_authority"],"NONE")

    def test_reject_initialize_on_original_g1_or_g2_schema(self):
        db=sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE g1f_event_manifest(event_open_ms INTEGER)")
            with self.assertRaisesRegex(ValueError,"G4_LIVE_OR_HISTORICAL_DB_MUTATION_FORBIDDEN"):
                init_offline_ledger(db)
            self.assertNotIn("g4_label_intents",{
                row[0] for row in db.execute("select name from sqlite_master where type='table'")})
        finally:
            db.close()

    def test_reject_initialize_on_original_g3_schema(self):
        db=sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE g3_event_context(event_open_ms INTEGER)")
            with self.assertRaisesRegex(ValueError,"G4_LIVE_OR_HISTORICAL_DB_MUTATION_FORBIDDEN"):
                init_offline_ledger(db)
        finally:
            db.close()

    def test_restart_reopens_same_standalone_database_without_duplicate(self):
        fd,path=tempfile.mkstemp(suffix="_g4_synthetic.sqlite")
        os.close(fd)
        try:
            x=sqlite3.connect(path)
            init_offline_ledger(x)
            key=freeze_label_intent(x,self.c,self.p)
            append_terminal(x,key,terminal())
            x.close()
            y=sqlite3.connect(path)
            init_offline_ledger(y)
            self.assertEqual(freeze_label_intent(y,self.c,self.p),key)
            self.assertFalse(append_terminal(y,key,terminal()))
            self.assertEqual(qualified_economic_label_count(y),1)
            y.close()
        finally:
            os.unlink(path)


if __name__=="__main__":
    unittest.main()
