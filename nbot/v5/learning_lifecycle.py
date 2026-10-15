"""Reviewed G5/G6 lifecycle over the source-linked outcome outbox.

No service, scheduling, networking or paper submission. Reviews are supplied
by an independent caller; no default keys or automatic scientific approval.
"""
from nbot.v5.science import MAX_ROWS, dataset, digest, evaluate, fit_candidate, verify_review
import json


class LearningLifecycle:
    def __init__(self, store, *, protocol, grade, reviewer=None, reviewer_key=None):
        protocol.validate()
        if grade not in ("ORIGINAL", "SYNTHETIC"):
            raise ValueError("LEARNING_GRADE_INVALID")
        self.store, self.protocol, self.grade = store, protocol, grade
        self.reviewer, self.reviewer_key = reviewer, reviewer_key
        self.store.append("learning-grade", "LEARNING_GRADE", protocol.declared_ms,
                          {"grade": grade, "protocol_sha256": digest(protocol.__dict__)})

    def _approved(self):
        return [json.loads(raw) for (raw,) in self.store.db.execute(
            "SELECT body FROM research_journal WHERE kind='LEARNING_ROLE_APPROVED' ORDER BY seq")]

    def _review(self, subject, purpose, context, now_ms):
        if self.reviewer is None:
            return None
        envelope = self.reviewer(subject, purpose, context, now_ms)
        if envelope is None:
            return None
        body = verify_review(envelope, key=self.reviewer_key, subject_sha256=subject,
                             purpose=purpose, now_ms=now_ms)
        if body.get("grade") != self.grade or body.get("role") != context["role"]:
            raise ValueError("LEARNING_REVIEW_GRADE_OR_ROLE")
        return envelope

    def advance(self, now_ms, *, epochs=100):
        approved = self._approved()
        if len(approved) >= 2:
            return {"state": "TWO_REVIEWED_ARTIFACTS", "grade": self.grade,
                    "models": {item["role"]: item["model_sha256"] for item in approved},
                    "paper_authority": "NONE", "real_money_authority": "NONE"}
        role = "CHAMPION" if not approved else "CHALLENGER"
        lower = approved[0]["max_settled_ms"] + self.protocol.embargo_ms if approved else -1
        frozen=None
        for (raw,) in self.store.db.execute(
                "SELECT body FROM research_journal WHERE kind='LEARNING_COHORT_FROZEN' ORDER BY seq DESC"):
            candidate=json.loads(raw)
            if candidate["role"]==role:
                if not self.store.db.execute("SELECT 1 FROM research_journal WHERE identity=?",
                        ("learning-rejected-cohort:"+candidate["data"]["dataset_sha256"],)).fetchone():
                    frozen=candidate
                break
        # Bounded scientific snapshot, never an unbounded historical list.
        rows = []
        for (raw,) in (() if frozen else self.store.db.execute(
                "SELECT body FROM research_journal WHERE kind='QUALIFIED_OUTCOME' ORDER BY seq")):
            row = json.loads(raw)["row"]
            if row["grade"] != self.grade:
                raise ValueError("LEARNING_MIXED_EVIDENCE_GRADE")
            if row["decision_ms"] > lower:
                rows.append(row)
                if len(rows) > MAX_ROWS:
                    raise ValueError("LEARNING_COHORT_CAPACITY_HOLD")
        if frozen:
            rows=frozen["data"]["rows"]
            epochs=frozen["epochs"]
        data = dataset(rows, cutoff_ms=now_ms, grade=self.grade)
        if frozen and data["dataset_sha256"]!=frozen["data"]["dataset_sha256"]:
            raise ValueError("LEARNING_FROZEN_COHORT_TAMPER")
        report = evaluate(data, self.protocol)
        self.store.append("learning-report:"+report["report_sha256"],"LEARNING_REPORT",now_ms,
                          {"role":role,"report":report,"grade":self.grade})
        if report["status"] != "REVIEW_REQUIRED":
            return {"state":"SCIENCE_HOLD","role":role,"report":report,"paper_authority":"NONE"}
        if self.store.db.execute("SELECT 1 FROM research_journal WHERE identity=?",
                ("learning-rejected-cohort:"+data["dataset_sha256"],)).fetchone():
            return {"state":"HOLDOUT_REJECTED","role":role,"paper_authority":"NONE"}
        if frozen is None:
            self.store.append("learning-cohort:"+data["dataset_sha256"],"LEARNING_COHORT_FROZEN",now_ms,
                              {"role":role,"data":data,"epochs":epochs,"paper_authority":"NONE"})
        context = {"role":role,"grade":self.grade,"dataset_sha256":data["dataset_sha256"],
                   "qualified_training_outcomes":len(rows),"report":report}
        training = self._review(report["report_sha256"],"G5_TRAINING",context,now_ms)
        if training is None:
            return {"state":"AWAITING_G5_REVIEW","role":role,
                    "report_sha256":report["report_sha256"],"paper_authority":"NONE"}
        # Chronological train/calibration/holdout, with the existing 4h embargo.
        ordered = data["rows"]
        boundary = ordered[int(len(ordered)*0.7)]["decision_ms"]
        model = fit_candidate(data,boundary_ms=boundary,protocol=self.protocol,
                              review=training,reviewer_key=self.reviewer_key,now_ms=now_ms,
                              synthetic=self.grade=="SYNTHETIC",epochs=epochs)
        self.store.register_candidate(model,now_ms)
        # A model with no demonstrated holdout edge cannot be blessed by row
        # count or a reviewer alone. Preserve failed candidates for audit.
        score = model["model_selector"]
        if (score["entries"] < 5 or score["net_r"] <= 0
                or score["max_drawdown_r"] > self.protocol.max_drawdown_r
                or model["holdout_mse"] >= model["no_trade_mse"]):
            self.store.append("learning-rejected:"+model["model_sha256"],"LEARNING_MODEL_REJECTED",now_ms,
                              {"role":role,"model_sha256":model["model_sha256"],
                               "reason":"HOLDOUT_EDGE_OR_RISK","paper_authority":"NONE"})
            self.store.append("learning-rejected-cohort:"+data["dataset_sha256"],"LEARNING_COHORT_REJECTED",now_ms,
                              {"dataset_sha256":data["dataset_sha256"],"model_sha256":model["model_sha256"]})
            return {"state":"HOLDOUT_REJECTED","role":role,"paper_authority":"NONE"}
        context.update(model=model,additional_nonoverlapping_outcomes=len(rows) if approved else 0)
        release = self._review(model["model_sha256"],"G6_PROMOTE",context,now_ms)
        if release is None:
            return {"state":"AWAITING_MODEL_REVIEW","role":role,"paper_authority":"NONE"}
        gates = release["body"]
        if (not all(gates.get(k) is True for k in (
                "g5_accepted","g6_accepted","holdout_source_audit_accepted"))
                or gates.get("qualified_training_outcomes",0) < 2000
                or (approved and gates.get("additional_nonoverlapping_outcomes",0) < 2000)):
            raise ValueError("LEARNING_QUALIFICATION_HOLD")
        if self.grade == "ORIGINAL":
            self.store.record_disposition(model["model_sha256"],"PROMOTE",now_ms,
                                          envelope=release,reviewer_key=self.reviewer_key)
        self.store.append("learning-role:"+role,"LEARNING_ROLE_APPROVED",now_ms,
                          {"role":role,"grade":self.grade,"model_sha256":model["model_sha256"],
                           "dataset_sha256":data["dataset_sha256"],
                           "max_settled_ms":max(r["settled_ms"] for r in rows),
                           "labels_sha256":digest(sorted(r["label_id"] for r in rows)),
                           "independent_review":release,"paper_authority":"NONE",
                           "scientific_acceptance":self.grade=="ORIGINAL"})
        return {"state":"REVIEWED_"+role,"model_sha256":model["model_sha256"],
                "grade":self.grade,"paper_authority":"NONE","real_money_authority":"NONE"}
