"""Recompute reviewed G4 economics and construct the G5 row, never a fill.

The independent evidence provider supplies authenticated source/cost receipts.
It cannot supply prequalified G5 labels or retrospective candidate features.
Synthetic laboratories use their own grade and keys, never original authority.
"""
from dataclasses import asdict

from nbot.v5.g4_economics import assess_quote_constrained_net
from nbot.v5.g4_price_path import PathReplay
from nbot.v5.science import dataset, digest, verify_review


def economic_row(*, population, intent, path, package, review, reviewer_key,
                 now_ms, grade):
    if grade not in ("ORIGINAL", "SYNTHETIC"):
        raise ValueError("G4_ECONOMIC_GRADE_INVALID")
    verify_review(review, key=reviewer_key, subject_sha256=digest(package),
                  purpose="G4_ECONOMIC_EVIDENCE", now_ms=now_ms)
    candidate = population["candidate"]
    if (package.get("grade") != grade
            or review["body"].get("grade") != grade
            or package.get("label_id") != intent["label_id"]
            or package.get("candidate_sha256") != digest(candidate)
            or package.get("path_sha256") != digest(path)
            or package.get("policy_sha256") != intent["policy_sha256"]):
        raise ValueError("G4_ECONOMIC_SOURCE_BINDING")
    witness = package["economic_witness"]
    if package["entry_quote"].get("receipt_sha256") != population["admission"]["original_entry_quote_sha256"]:
        raise ValueError("G4_ECONOMIC_ENTRY_RECEIPT_MISMATCH")
    decision, exit_ms = intent["decision_at_ms"], path["exit_at_ms"]
    # A fee schedule must apply at BOTH clocks. Funding coverage must include
    # the whole holding interval, including explicit evidence for zero funding.
    clocks = (witness.get("fee_valid_from_ms"), witness.get("fee_valid_to_ms"),
              witness.get("funding_coverage_from_ms"),
              witness.get("funding_coverage_through_ms"),
              witness.get("settled_at_ms"), witness.get("slippage_declared_at_ms"))
    if (any(type(t) is not int for t in clocks)
            or not clocks[0] <= decision <= exit_ms <= clocks[1]
            or not clocks[2] <= decision <= exit_ms <= clocks[3]
            or not exit_ms <= clocks[4] <= now_ms
            or not clocks[5] <= decision):
        raise ValueError("G4_ECONOMIC_ASOF_OR_SETTLEMENT_HOLD")
    replay = assess_quote_constrained_net(
        path=PathReplay(**path), candidate=candidate,
        policy=intent["frozen_policy"], entry_quote=package["entry_quote"],
        exit_quote=package["exit_quote"], economic_witness=witness,
        audit_at_ms=now_ms, evidence_grade=grade)
    if replay.state != "COST_REPLAYED":
        raise ValueError("G4_ECONOMIC_HOLD:" + ",".join(replay.reasons))
    row = {
        "label_id": intent["label_id"], "grade": grade, "status": "SCORED",
        "source_grade": "QUOTE_CONSTRAINED_SIMULATION",
        "net_r": float(replay.modeled_net_r),
        "gross_r": float(replay.modeled_gross_r),
        "event_ms": candidate["event_open_ms"],
        "feature_known_ms": population["g3_feature_known_ms"],
        "decision_ms": decision, "exit_ms": exit_ms,
        "settled_ms": witness["settled_at_ms"],
        "symbol": intent["symbol"], "side": intent["side"],
        "regime": population["regime"], "features": population["features"],
        "patterns": sorted(k for k, v in candidate["patterns"].items() if v == "MATCH"),
        "lineage": {
            "candidate": population["admission"]["original_candidate_sha256"],
            "g2": population["g2_quote_sha256"],
            "g3": population["admission"]["original_g3_feature_sha256"],
            "policy": intent["policy_sha256"], "path": digest(path),
            "cost": digest({"evidence": package, "calculation": asdict(replay)}),
            "audit": digest(review)},
    }
    row["row_sha256"] = digest(row)
    dataset([row], cutoff_ms=now_ms, grade=grade)
    return row, asdict(replay)
