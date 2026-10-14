"""Synthetic only. Tests cannot count as market outcomes or acceptance."""
from dataclasses import replace
import copy
import hashlib
import hmac
import tempfile
from pathlib import Path
import sqlite3
import unittest
from nbot.v5.science import *
from nbot.v5.research_store import ResearchStore

BASE = 1800000000000


def row(i, grade="SYNTHETIC"):
    at = BASE+i*3600000
    strength = (i % 17)/17
    r = {"label_id": digest(["label", i]), "grade": grade, "status": "SCORED",
         "source_grade": "QUOTE_CONSTRAINED_SIMULATION", "net_r": strength*2-0.3,
         "gross_r": strength*2-0.2, "event_ms": at-300000, "feature_known_ms": at-1,
         "decision_ms": at, "exit_ms": at+60000, "settled_ms": at+61000,
         "symbol": f"COIN{i%50:02d}USDT", "side": "LONG" if i%2 else "SHORT",
         "regime": ["UP", "DOWN", "RANGE"][i%3], "patterns": ["TREND"],
         "lineage": {k: digest([k,i]) for k in ("candidate", "g2", "g3", "policy", "path", "cost", "audit")},
         "features": {"btc_confidence": 0.8, "btc_return_1h": 0.001,
                      "coin_return_1h": strength*0.02, "atr14_fraction": 0.01,
                      "relative_strength": strength if i%2 else -strength,
                      "breadth": 0.6, "source_quality": 1.0}}
    for k in FEATURES:
        r["features"].setdefault(k, 0.0)
    r["features"]["side_long"] = float(r["side"] == "LONG")
    r["row_sha256"] = digest(r)
    return r


def data(n=2400, grade="SYNTHETIC"):
    return dataset([row(i,grade) for i in range(n)], cutoff_ms=BASE+n*3600000, grade=grade)


def protocol(n=2400):
    return Protocol(BASE-1, BASE, BASE+n*3600000)


def review(subject, purpose, now=BASE, **extra):
    body = {"reviewer": "SYNTHETIC_REVIEWER", "purpose": purpose,
            "subject_sha256": subject, "verdict": "ACCEPT", "issued_ms": now-1,
            "expires_ms": now+10000, **extra}
    key = b"s"*32
    sig = hmac.new(key, ("NBOT-V5-INDEPENDENT-REVIEW\n"+canonical(body)).encode(), hashlib.sha256).hexdigest()
    return {"body": body, "hmac_sha256": sig}


class ScienceTests(unittest.TestCase):
    def test_empty_report_locked(self):
        r = evaluate(data(0), protocol())
        self.assertEqual(r["qualified_outcomes"], 0)
        self.assertFalse(r["scientifically_accepted"])
        self.assertEqual(r["training_authority"], "NONE")

    def test_below_2000_held(self):
        self.assertIn("OUTCOMES_BELOW_2000", evaluate(data(1999), protocol())["reasons"])

    def test_many_pattern_tags_do_not_multiply_outcomes(self):
        r = row(0); r["patterns"] *= 24
        r["row_sha256"] = digest({k:v for k,v in r.items() if k != "row_sha256"})
        d = dataset([r], cutoff_ms=BASE+100000, grade="SYNTHETIC")
        self.assertEqual(evaluate(d,protocol())["qualified_outcomes"], 1)

    def test_same_window_both_sides_one_dependence_block(self):
        a,b=row(0),row(1)
        b.update(decision_ms=a["decision_ms"],exit_ms=a["exit_ms"])
        self.assertEqual(len(dependence_blocks([a,b])),1)

    def test_future_feature_rejected(self):
        r=row(0);r["feature_known_ms"]+=2
        with self.assertRaisesRegex(ValueError,"LEAKAGE"):
            dataset([r],cutoff_ms=BASE+100000,grade="SYNTHETIC")

    def test_unmatured_rejected(self):
        with self.assertRaisesRegex(ValueError,"LEAKAGE"):
            dataset([row(0)],cutoff_ms=BASE,grade="SYNTHETIC")

    def test_duplicate_label_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATED"):
            dataset([row(0),row(0)],cutoff_ms=BASE+100000,grade="SYNTHETIC")

    def test_original_cannot_include_synthetic(self):
        with self.assertRaisesRegex(ValueError,"QUALIFIED"):
            dataset([row(0)],cutoff_ms=BASE+100000)

    def test_path_only_never_training_target(self):
        r=row(0);r["source_grade"]="HISTORICAL_AGGTRADE_PATH"
        with self.assertRaisesRegex(ValueError,"QUALIFIED"):
            dataset([r],cutoff_ms=BASE+100000,grade="SYNTHETIC")

    def test_digest_tamper_rejected(self):
        r=row(0);r["net_r"]=100
        with self.assertRaisesRegex(ValueError,"TAMPER"):
            dataset([r],cutoff_ms=BASE+100000,grade="SYNTHETIC")

    def test_missing_source_lineage_rejected(self):
        r=row(0);del r["lineage"]["cost"]
        with self.assertRaisesRegex(ValueError,"LINEAGE"):
            dataset([r],cutoff_ms=BASE+100000,grade="SYNTHETIC")

    def test_nan_rejected(self):
        r=row(0);r["net_r"]=float("nan")
        with self.assertRaisesRegex(ValueError,"QUALIFIED"):
            dataset([r],cutoff_ms=BASE+100000,grade="SYNTHETIC")

    def test_protocol_no_hindsight(self):
        with self.assertRaisesRegex(ValueError,"PROSPECTIVE"):
            evaluate(data(1),replace(protocol(),declared_ms=BASE))

    def test_threshold_cannot_be_reduced(self):
        with self.assertRaisesRegex(ValueError,"WEAKENED"):
            evaluate(data(1),replace(protocol(),min_outcomes=1))

    def test_negative_edge_explicit(self):
        d=data(2100)
        for r in d["rows"]:
            r["net_r"]=-0.1
            r["row_sha256"]=digest({k:v for k,v in r.items() if k != "row_sha256"})
        d=dataset(d["rows"],cutoff_ms=d["cutoff_ms"],grade="SYNTHETIC")
        self.assertIn("NO_DEMONSTRABLE_POSITIVE_EDGE",evaluate(d,protocol())["reasons"])

    def test_bootstrap_deterministic_and_never_auto_accepts(self):
        d=data(2100)
        a=evaluate(d,protocol());b=evaluate(d,protocol())
        self.assertEqual(a,b)
        self.assertEqual(a["effective_sample_upper_bound"],2100)
        self.assertFalse(a["scientifically_accepted"])

    def test_purged_split_excludes_overlapping_or_unsettled(self):
        rows=[row(i) for i in range(30)]
        boundary=rows[20]["decision_ms"]
        train,hold=purged_split(rows,boundary)
        self.assertTrue(all(r["settled_ms"]<boundary-14400000 for r in train))
        self.assertTrue(all(r["decision_ms"]>=boundary for r in hold))

    def test_original_training_requires_independent_approval(self):
        with self.assertRaisesRegex(ValueError,"REVIEW|HOLD"):
            fit_candidate(data(2400,"ORIGINAL"),boundary_ms=BASE+2000*3600000,protocol=protocol())

    def test_synthetic_candidate_reproducible_and_abstains(self):
        d=data(100)
        kwargs=dict(boundary_ms=BASE+75*3600000,protocol=protocol(),synthetic=True,epochs=20)
        a=fit_candidate(d,**kwargs);b=fit_candidate(d,**kwargs)
        self.assertEqual(a,b)
        self.assertFalse(a["trading_eligible"])
        self.assertLess(a["fit_cutoff_ms"],a["holdout_start_ms"]-14400000)
        self.assertEqual(infer(a,row(0)["features"])["paper_authority"],"NONE")

    def test_artifact_tamper_rejected(self):
        a=fit_candidate(data(100),boundary_ms=BASE+75*3600000,protocol=protocol(),synthetic=True,epochs=10)
        a["weights"][0]=999
        with self.assertRaisesRegex(ValueError,"ARTIFACT"):
            infer(a,row(0)["features"])

    def test_reviewer_wrong_subject_and_expiry(self):
        e=review("a"*64,"G5_TRAINING")
        for subject,now in [("b"*64,BASE),("a"*64,BASE+10000)]:
            with self.assertRaisesRegex(ValueError,"REVIEW_INVALID"):
                verify_review(e,key=b"s"*32,subject_sha256=subject,purpose="G5_TRAINING",now_ms=now)

    def test_registry_restart_and_immutable_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"continuous_research.sqlite"
            s=ResearchStore(p)
            a=fit_candidate(data(100),boundary_ms=BASE+75*3600000,protocol=protocol(),synthetic=True,epochs=10)
            self.assertTrue(s.register_candidate(a,BASE))
            self.assertFalse(s.register_candidate(a,BASE+1))
            with self.assertRaises(sqlite3.IntegrityError):
                s.db.execute("DELETE FROM research_journal")
            with self.assertRaisesRegex(ValueError,"SYNTHETIC_MODEL"):
                s.record_disposition(a["model_sha256"],"PROMOTE",BASE)
            head=s.audit();s.close();s=ResearchStore(p)
            self.assertEqual(s.audit(),head);s.close()

    def test_journal_conflict_atomic(self):
        with tempfile.TemporaryDirectory() as t:
            s=ResearchStore(Path(t)/"continuous_research.sqlite")
            s.append("id","FIXTURE",BASE,{"a":1})
            with self.assertRaisesRegex(ValueError,"CONFLICT"):
                s.append("id","FIXTURE",BASE,{"a":2})
            self.assertEqual(s.audit()["records"],1);s.close()
