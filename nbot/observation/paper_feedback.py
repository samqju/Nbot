"""Bounded, paper-only feedback from settled execution outcomes.

No exchange access, new positions, research-label mutation or mainnet authority.
Ranking weights are experimental heuristics, not calibrated win probabilities.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import os
from dataclasses import asdict
from collections import defaultdict

from nbot.communication.authorities import LIVE_PAPER_LEARNED_AUTHORITY
from nbot.communication.contracts import ExecutionOutcome, ExecutionProposal
from nbot.communication.validation import payload_digest
from .context_learning import describe
from .candidate_setups import BY_ID, FALLBACK, CATALOG_DIGEST
from .feedback_evidence import compatible_evidence_release, loss_cooldowns, shadow_sample

VERSION = "PAPER_EXECUTION_FEEDBACK_V5_REALTIME_ENTRY"
ACCEPTED_VERSIONS = {
    VERSION,
    "PAPER_EXECUTION_FEEDBACK_V4_SHRINKAGE",
    "PAPER_EXECUTION_FEEDBACK_V3_SHADOW",
    "PAPER_EXECUTION_FEEDBACK_V2_CANDIDATES",
}
DAY_MS = 86_400_000
WINDOW_MS = 30 * DAY_MS
BUCKET_MS = 49 * 300_000
MIN_BUCKETS = 4
# Neutral prior mass prevents a handful of noisy buckets from causing large ranking moves.
# This is deliberately lightweight for the 1 CPU / 1 GB learner.
PRIOR_EVIDENCE_MASS = 4.0
MAX_SAMPLES = 2048
BATCH = 256
SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_feedback_samples (
    outcome_id TEXT PRIMARY KEY, proposal_id TEXT UNIQUE NOT NULL,
    release_sha TEXT NOT NULL, available_ms INTEGER NOT NULL,
    entered_ms INTEGER NOT NULL, closed_ms INTEGER NOT NULL,
    sample_json TEXT NOT NULL, sample_digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS paper_feedback_window
ON paper_feedback_samples(release_sha, available_ms, closed_ms);
CREATE TABLE IF NOT EXISTS paper_feedback_rejections (
    outcome_id TEXT PRIMARY KEY, reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS paper_feedback_recent ON paper_feedback_samples(closed_ms);
CREATE TABLE IF NOT EXISTS paper_feedback_checks (
 release_sha TEXT NOT NULL, event_ms INTEGER NOT NULL, decision_ms INTEGER NOT NULL,
 detail_json TEXT NOT NULL, PRIMARY KEY(release_sha,event_ms)
);
CREATE TABLE IF NOT EXISTS paper_feedback_progress (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_rowid INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_feedback_models (
    model_id TEXT PRIMARY KEY, release_sha TEXT NOT NULL,
    cutoff_ms INTEGER NOT NULL, model_json TEXT NOT NULL, model_digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS paper_feedback_model_release
ON paper_feedback_models(release_sha, cutoff_ms);
CREATE TABLE IF NOT EXISTS paper_feedback_decisions (
    proposal_id TEXT PRIMARY KEY, release_sha TEXT NOT NULL,
    decision_ms INTEGER NOT NULL, decision_json TEXT NOT NULL, decision_digest TEXT NOT NULL
);
"""


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _verified(text, digest):
    value = json.loads(text)
    if payload_digest(value) != digest:
        raise ValueError("PAPER_FEEDBACK_DIGEST_MISMATCH")
    return value


def group_keys(info, side, candidate=None):
    if candidate is not None:
        if not isinstance(candidate, dict):
            raise ValueError("PAPER_CANDIDATE_INVALID")
        expected = FALLBACK if candidate.get("id") == "MODEL_ONLY" else (
            BY_ID[candidate["id"]].tag() if candidate.get("id") in BY_ID else None)
        if candidate != expected:
            raise ValueError("PAPER_CANDIDATE_INVALID")
        if candidate["id"] != "MODEL_ONLY":
            info = dict(info, setup="CANDIDATE:" + candidate["id"])
    return (info["setup"] + "|" + info["context"] + "|" + side,
            info["setup"] + "|ALL|" + side)


class PaperFeedback:
    def __init__(self, database, *, release_sha):
        if database.config.market_environment != "LIVE":
            raise ValueError("PAPER_FEEDBACK_LIVE_DATABASE_REQUIRED")
        self.database, self.release_sha = database, release_sha
        self._compatible_releases = {}
        from .shadow import ShadowConfig
        self._shadow_config = asdict(ShadowConfig(**{
            field: float(os.environ["NBOT_SHADOW_"+field.upper()])
            for field in ShadowConfig.__dataclass_fields__
            if "NBOT_SHADOW_"+field.upper() in os.environ}))
        with database.connection() as conn:
            conn.executescript(SCHEMA)

    def ingest(self, *, cutoff_ms):
        """Copy at most 256 already-acknowledged outcomes; atomic/idempotent cursor.

        Evidence comes from the stored proposal, never outcome-supplied setup tags.
        A late receipt becomes eligible only after it was actually available.
        """
        with self.database.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='received_execution_outcomes'").fetchone() is None:
                return
            row = conn.execute("SELECT last_rowid FROM paper_feedback_progress WHERE singleton=1").fetchone()
            cursor = 0 if row is None else int(row[0])
            rows = conn.execute("""
                SELECT o.rowid,o.outcome_id,o.received_at_ms,o.payload_json,o.payload_digest,
                       p.proposal_json,p.proposal_digest
                FROM received_execution_outcomes o
                LEFT JOIN served_execution_proposals p USING(proposal_id)
                WHERE o.rowid>? ORDER BY o.rowid LIMIT ?
                """, (cursor, BATCH)).fetchall()
            if not rows:
                return
            for rowid, outcome_id, received, raw, digest, proposal_raw, proposal_digest in rows:
                if int(received) >= cutoff_ms:
                    break
                try:
                    outcome = ExecutionOutcome.from_dict(_verified(raw, digest))
                    if proposal_raw is None:
                        raise ValueError("PROPOSAL_MISSING")
                    proposal = ExecutionProposal.from_dict(_verified(proposal_raw, proposal_digest))
                    tag = (proposal.experiment_context or {}).get("paper_feedback", {})
                    if (outcome.profile != "live-paper" or outcome.execution_mode != "PAPER"
                            or proposal.profile != "live-paper"
                            or proposal.entry_authority != LIVE_PAPER_LEARNED_AUTHORITY
                            or tag.get("version") not in ACCEPTED_VERSIONS):
                        raise ValueError("NOT_THIS_PAPER_EXPERIMENT")
                    if (outcome.proposal_id != proposal.proposal_id
                            or outcome.proposal_source_digest != proposal.source_digest
                            or outcome.proposal_model_digest != proposal.model_digest
                            or outcome.symbol != proposal.symbol or outcome.side != proposal.side
                            or outcome.entry_authority != proposal.entry_authority):
                        raise ValueError("PROPOSAL_OUTCOME_MISMATCH")
                    if outcome.closed_timestamp_ms >= cutoff_ms:
                        raise ValueError("OUTCOME_TIME_INVALID")
                    if (outcome.entry_timestamp_ms < proposal.generated_at_ms
                            or outcome.entry_timestamp_ms > proposal.expires_at_ms
                            or outcome.closed_timestamp_ms > int(received)):
                        raise ValueError("OUTCOME_TIME_INVALID")
                    if not math.isclose(outcome.r_multiple, outcome.realized_pnl_usd / outcome.initial_risk_usd,
                                        rel_tol=1e-6, abs_tol=1e-8):
                        raise ValueError("OUTCOME_R_INCONSISTENT")
                    info = (proposal.experiment_context or {})["setup_explanation"]
                    if not isinstance(tag.get("candidate"), dict):
                        raise ValueError("PAPER_CANDIDATE_INVALID")
                    keys = group_keys(info, proposal.side, tag["candidate"])
                    cohort = tag["release_sha"]
                    if not isinstance(cohort, str) or len(cohort) != 40:
                        raise ValueError("COHORT_INVALID")
                    sample = {
                        "outcome_id": outcome_id, "symbol": outcome.symbol, "side": outcome.side,
                        "candidate_id": tag["candidate"]["id"],
                        "keys": list(keys), "net_usd": outcome.realized_pnl_usd,
                        "risk_usd": outcome.initial_risk_usd, "net_r": outcome.r_multiple,
                        "learning_r": max(-3., min(3., outcome.r_multiple)),
                        "entered_ms": outcome.entry_timestamp_ms, "closed_ms": outcome.closed_timestamp_ms,
                        "available_ms": max(int(received), outcome.closed_timestamp_ms),
                        "predicted_r": tag.get("predicted_paper_r"),
                        "factor": tag["factor"], "feedback_model": tag["model_id"],
                        "base_model": proposal.model_digest, "exit_reason": outcome.exit_reason,
                        "ranking_changed": tag["ranking_changed"],
                    }
                    # More than one concurrent position is not valid one-position evidence.
                    overlap = conn.execute("""
                        SELECT 1 FROM paper_feedback_samples
                        WHERE proposal_id<>? AND entered_ms<? AND closed_ms>? LIMIT 1
                        """, (outcome.proposal_id, outcome.closed_timestamp_ms, outcome.entry_timestamp_ms)).fetchone()
                    if overlap:
                        raise ValueError("OVERLAPPING_PAPER_POSITIONS")
                    conn.execute("INSERT OR IGNORE INTO paper_feedback_samples VALUES (?,?,?,?,?,?,?,?)",
                                 (outcome_id, outcome.proposal_id, cohort, sample["available_ms"],
                                  sample["entered_ms"], sample["closed_ms"], _json(sample), payload_digest(sample)))
                except (ValueError, KeyError, TypeError, OverflowError) as exc:
                    conn.execute("INSERT OR IGNORE INTO paper_feedback_rejections VALUES (?,?)",
                                 (outcome_id, type(exc).__name__ + ":" + str(exc)[:160]))
                cursor = int(rowid)
            conn.execute("INSERT OR REPLACE INTO paper_feedback_progress VALUES (1,?)", (cursor,))

    def _compatible(self, release):
        if release not in self._compatible_releases:
            self._compatible_releases[release] = compatible_evidence_release(release, self.release_sha)
        return self._compatible_releases[release]

    def _main_samples(self, cutoff_ms):
        with self.database.connection() as conn:
            rows = conn.execute("""SELECT release_sha,sample_json,sample_digest FROM paper_feedback_samples
                WHERE available_ms<? AND closed_ms>=? ORDER BY closed_ms DESC,outcome_id DESC LIMIT ?""",
                (cutoff_ms, cutoff_ms-WINDOW_MS, MAX_SAMPLES+1)).fetchall()
        samples = [dict(_verified(raw, digest), source="MAIN_PAPER", weight=1.)
                   for release, raw, digest in rows[:MAX_SAMPLES] if self._compatible(release)]
        return samples, len(rows)>MAX_SAMPLES

    def cooldown(self, symbol, side, *, cutoff_ms):
        samples, _ = self._main_samples(cutoff_ms)
        return loss_cooldowns(samples, cutoff_ms).get(symbol+"|"+side)

    def entry_block_reason(self, symbol, side, *, now_ms):
        # A close ACK can arrive between supervisor refreshes. The flat-side
        # request gate consumes those receipts before serving another proposal.
        # Include receipts already committed in this same millisecond.
        self.ingest(cutoff_ms=now_ms+1)
        with self.database.connection() as conn:
            row=conn.execute("SELECT last_rowid FROM paper_feedback_progress WHERE singleton=1").fetchone()
            cursor=row[0] if row else 0
            if conn.execute("""SELECT 1 FROM received_execution_outcomes
                    WHERE rowid>? AND received_at_ms<=? LIMIT 1""",(cursor,now_ms)).fetchone():
                return "PAPER_FEEDBACK_CATCHING_UP"
        if self.cooldown(symbol,side,cutoff_ms=now_ms+1):
            return "PAPER_REPEATED_LOSS_COOLDOWN"
        return None

    def _shadow_samples(self, cutoff_ms):
        from .shadow import verified
        with self.database.connection() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_results'").fetchone():
                return [], {}, []
            conn.execute("CREATE INDEX IF NOT EXISTS shadow_feedback_recent ON shadow_results(profile,closed_ms)")
            rows=conn.execute("""SELECT release_sha,result_json,digest FROM shadow_results
                WHERE profile='live-paper' AND closed_ms>=? AND closed_ms<?
                ORDER BY closed_ms DESC,id DESC LIMIT 2049""",
                (cutoff_ms-WINDOW_MS,cutoff_ms)).fetchall()
        samples, feasibility, identities = [], defaultdict(dict), []
        for release, raw, check in rows[:2048]:
            if not self._compatible(release):
                continue
            p=verified(raw,check)
            if (p.get("candidate_id") not in BY_ID or p.get("profile")!="live-paper"
                    or p.get("authority")!="SHADOW_ONLY_NO_EXECUTION"
                    or p.get("catalog_digest")!=CATALOG_DIGEST
                    or p.get("config")!=self._shadow_config
                    or not isinstance(p.get("available_ms"),int)
                    or p["available_ms"]>=cutoff_ms):
                continue
            sample=shadow_sample(p,cutoff_ms=cutoff_ms,catalog_digest=CATALOG_DIGEST)
            if sample:
                samples.append(sample)
            # Next-bar drift is retained only as a signal-decay diagnostic.
            # It must not penalize immediate market-order entry ranking.
            if sample or p.get("reason")=="ENTRY_DRIFT_REJECTED":
                key=p["candidate_id"]+"|"+p["side"]
                event=int(p["event_ms"])
                feasibility[key][event]=bool(sample)
                identities.append((p["id"],check))
        groups={}
        for key, events in feasibility.items():
            attempted=len(events); filled=sum(events.values())
            blocks=len({event//BUCKET_MS for event in events})
            factor=1.
            if attempted>=8 and blocks>=3:
                factor=max(.7,1-.3*(1-filled/attempted))
            groups[key]={"attempts":attempted,"filled":filled,"drift_cancelled":attempted-filled,
                         "blocks":blocks,"factor":factor}
        return samples, groups, identities

    def snapshot(self, *, cutoff_ms):
        self.ingest(cutoff_ms=cutoff_ms)
        main_samples, capped = self._main_samples(cutoff_ms)
        shadow_samples, signal_decay, signal_decay_identity = self._shadow_samples(cutoff_ms)
        samples = main_samples + shadow_samples
        # Stable identity across refreshes and restarts; age is updated daily.
        identity = {"version": VERSION, "release_sha": self.release_sha,
                    "day": cutoff_ms // DAY_MS, "next_bar_signal_decay": sorted(signal_decay_identity),
                    "samples": sorted((s["outcome_id"], payload_digest(s)) for s in samples)}
        model_id = hashlib.sha256(_json(identity).encode()).hexdigest()
        with self.database.connection() as conn:
            saved = conn.execute("SELECT model_json,model_digest FROM paper_feedback_models WHERE model_id=?",
                                 (model_id,)).fetchone()
            if saved:
                value = _verified(*saved)
                if value["cutoff_ms"] > cutoff_ms:
                    raise ValueError("PAPER_FEEDBACK_FUTURE_MODEL")
                return value
        buckets = defaultdict(lambda: defaultdict(list))
        for sample in samples:
            for key in sample["keys"]:
                buckets[key][sample["entered_ms"] // BUCKET_MS].append(sample)
        groups = {}
        for key, cells in sorted(buckets.items()):
            values, weights = [], []
            for _bucket, items in sorted(cells.items()):
                main=[s["learning_r"] for s in items if s["source"]=="MAIN_PAPER"]
                shadow=[s["learning_r"] for s in items if s["source"]=="SHADOW"]
                # Ten simultaneous shadow trades never become ten independent observations.
                mass=(1. if main else 0.)+(.25 if shadow else 0.)
                value=((statistics.fmean(main) if main else 0.)
                       +(.25*statistics.fmean(shadow) if shadow else 0.))/mass
                values.append(value)
                age = max(0, cutoff_ms-max(s["available_ms"] for s in items))
                weights.append(mass * 2 ** (-age / (14*DAY_MS)))
            total = sum(weights)
            effective = total*total / sum(w*w for w in weights)
            raw_mean = sum(w*v for w,v in zip(weights, values)) / total
            # Empirical-Bayes-style shrinkage toward a neutral 0R prior.  The prior
            # contributes no fabricated wins/losses; it only limits how far sparse
            # evidence can move ranking before more independent buckets arrive.
            shrinkage = total / (total + PRIOR_EVIDENCE_MASS)
            mean = raw_mean * shrinkage
            variance = sum(w*(v-raw_mean)**2 for w,v in zip(weights,values)) / total
            margin = 2*math.sqrt(max(variance, .25)/max(1., min(effective,total)))
            supported = len(values) >= MIN_BUCKETS and effective >= MIN_BUCKETS-1
            factor = 1.
            if supported:
                if mean + margin < 0:
                    factor = max(.25, 1 + (mean+margin)/2)
                elif len(values)>=8 and mean - margin > 0:
                    factor = min(1.5, 1 + (mean-margin)/4)
            groups[key] = {"buckets": len(values), "effective_buckets": effective,
                           "trades": sum(len(items) for items in cells.values()),
                           "evidence_mass": total,
                           "raw_mean_clipped_r": raw_mean,
                           "mean_clipped_r": mean, "shrinkage_factor": shrinkage,
                           "prior_evidence_mass": PRIOR_EVIDENCE_MASS,
                           "caution_margin": margin,
                           "supported": supported, "factor": factor}
        value = {"version": VERSION, "model_id": model_id, "release_sha": self.release_sha,
                 "cutoff_ms": cutoff_ms, "sample_count": len(main_samples), "window_days": 30,
                  "shadow_sample_count": len(shadow_samples), "shadow_weight": .25,
                  "next_bar_signal_decay": signal_decay,
                  "entry_gate_mode": "EXECUTION_REALTIME_ONLY",
                  "cooldowns": loss_cooldowns(main_samples,cutoff_ms),
                 "sample_cap_reached": capped, "groups": groups,
                 "cost_basis": "PAPER_AFTER_SIMULATED_FEES_NO_FUNDING"}
        with self.database.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO paper_feedback_models VALUES (?,?,?,?,?)",
                         (model_id, self.release_sha, cutoff_ms, _json(value), payload_digest(value)))
            saved = conn.execute("SELECT model_json,model_digest FROM paper_feedback_models WHERE model_id=?",
                                 (model_id,)).fetchone()
        return _verified(*saved)

    @staticmethod
    def adjust(model, vector, side, base_score, candidate=None, symbol=None, now_ms=None):
        info = describe(vector)
        result = {"version": VERSION, "release_sha": model["release_sha"],
                  "model_id": model["model_id"], "trained_before_ms": model["cutoff_ms"],
                  "factor": 1., "predicted_paper_r": None,
                  "support_buckets": 0, "group": None, "status": "INSUFFICIENT_PAPER_EVIDENCE"}
        if candidate is not None:
            result["candidate"] = dict(candidate)
        for key in group_keys(info, side, candidate):
            group = model["groups"].get(key)
            if group and group["supported"]:
                result.update(factor=group["factor"], predicted_paper_r=group["mean_clipped_r"],
                              support_buckets=group["buckets"], group=key, status="PAPER_FEEDBACK_APPLIED")
                break
        result["evidence_sources"] = {"main_paper": model.get("sample_count",0),
                                      "shadow": model.get("shadow_sample_count",0)}
        result["outcome_factor"] = result["factor"]
        # Legacy field remains neutral so old operator/report consumers do not
        # mistake next-bar drift for immediate market-order feasibility.
        result["entry_feasibility_factor"] = 1.0
        result["entry_gate_mode"] = "EXECUTION_REALTIME_ONLY"
        result["next_bar_signal_decay"] = model.get("next_bar_signal_decay",{}).get(
            (candidate or {}).get("id","")+"|"+side, {}
        )
        cooldown=model.get("cooldowns",{}).get(str(symbol)+"|"+side)
        if cooldown and cooldown["until_ms"]>(now_ms if now_ms is not None else model["cutoff_ms"]):
            result.update(factor=0.,status="REPEATED_LOSS_COOLDOWN",cooldown_until_ms=cooldown["until_ms"])
        # Feedback never turns a negative research score into a paper entry.
        return (base_score * result["factor"] if base_score > 0 else base_score), result

    def record_decision(self, proposal_id, decision_ms, detail):
        with self.database.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO paper_feedback_decisions VALUES (?,?,?,?,?)",
                         (proposal_id, self.release_sha, decision_ms, _json(detail), payload_digest(detail)))

    def record_check(self, event_ms, decision_ms, detail):
        with self.database.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO paper_feedback_checks VALUES(?,?,?,?)",
                         (self.release_sha,event_ms,decision_ms,_json(detail)))
