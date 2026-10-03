"""Bounded, paper-only feedback from settled execution outcomes.

No exchange access, new positions, research-label mutation or mainnet authority.
Ranking weights are experimental heuristics, not calibrated win probabilities.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict

from nbot.communication.authorities import LIVE_PAPER_LEARNED_AUTHORITY
from nbot.communication.contracts import ExecutionOutcome, ExecutionProposal
from nbot.communication.validation import payload_digest
from .context_learning import describe
from .candidate_setups import BY_ID, FALLBACK

VERSION = "PAPER_EXECUTION_FEEDBACK_V2_CANDIDATES"
DAY_MS = 86_400_000
WINDOW_MS = 30 * DAY_MS
BUCKET_MS = 49 * 300_000
MIN_BUCKETS = 8
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
                            or tag.get("version") != VERSION):
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

    def snapshot(self, *, cutoff_ms):
        self.ingest(cutoff_ms=cutoff_ms)
        with self.database.connection() as conn:
            rows = conn.execute("""
                SELECT sample_json,sample_digest FROM paper_feedback_samples
                WHERE release_sha=? AND available_ms<? AND closed_ms>=?
                ORDER BY closed_ms DESC,outcome_id DESC LIMIT ?
                """, (self.release_sha, cutoff_ms, cutoff_ms-WINDOW_MS, MAX_SAMPLES+1)).fetchall()
        capped = len(rows) > MAX_SAMPLES
        samples = [_verified(*row) for row in rows[:MAX_SAMPLES]]
        # Stable identity across refreshes and restarts; age is updated daily.
        identity = {"version": VERSION, "release_sha": self.release_sha,
                    "day": cutoff_ms // DAY_MS, "samples": sorted((s["outcome_id"], payload_digest(s)) for s in samples)}
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
                values.append(statistics.fmean(s["learning_r"] for s in items))
                age = max(0, cutoff_ms-max(s["closed_ms"] for s in items))
                weights.append(2 ** (-age / (14*DAY_MS)))
            total = sum(weights)
            effective = total*total / sum(w*w for w in weights)
            mean = sum(w*v for w,v in zip(weights, values)) / total
            variance = sum(w*(v-mean)**2 for w,v in zip(weights,values)) / total
            margin = 2*math.sqrt(max(variance, .25)/effective)
            supported = len(values) >= MIN_BUCKETS and effective >= MIN_BUCKETS
            factor = 1.
            if supported:
                if mean + margin < 0:
                    factor = max(.25, 1 + (mean+margin)/2)
                elif mean - margin > 0:
                    factor = min(1.5, 1 + (mean-margin)/4)
            groups[key] = {"buckets": len(values), "effective_buckets": effective,
                           "trades": sum(len(items) for items in cells.values()),
                           "mean_clipped_r": mean, "caution_margin": margin,
                           "supported": supported, "factor": factor}
        value = {"version": VERSION, "model_id": model_id, "release_sha": self.release_sha,
                 "cutoff_ms": cutoff_ms, "sample_count": len(samples), "window_days": 30,
                 "sample_cap_reached": capped, "groups": groups,
                 "cost_basis": "PAPER_AFTER_SIMULATED_FEES_NO_FUNDING"}
        with self.database.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO paper_feedback_models VALUES (?,?,?,?,?)",
                         (model_id, self.release_sha, cutoff_ms, _json(value), payload_digest(value)))
            saved = conn.execute("SELECT model_json,model_digest FROM paper_feedback_models WHERE model_id=?",
                                 (model_id,)).fetchone()
        return _verified(*saved)

    @staticmethod
    def adjust(model, vector, side, base_score, candidate=None):
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
        # Feedback never turns a negative research score into a paper entry.
        return (base_score * result["factor"] if base_score > 0 else base_score), result

    def record_decision(self, proposal_id, decision_ms, detail):
        with self.database.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO paper_feedback_decisions VALUES (?,?,?,?,?)",
                         (proposal_id, self.release_sha, decision_ms, _json(detail), payload_digest(detail)))
