"""LIVE-trained inference for TESTNET only; never train in a request handler."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from nbot.communication.authorities import TESTNET_LEARNED_AUTHORITY
from nbot.communication.contracts import ExecutionProposal
from nbot.communication.validation import payload_digest
from nbot.config.profiles import get_profile
from .causal_ridge import LABEL_HORIZON_MS, STATISTICS_VERSION
from .challengers import CHALLENGER_PREFIX, MODEL_PREFIX, EVALUATION_PREFIX, EVALUATOR_VERSION
from .config import observation_config_for_profile
from .database import EvidenceDatabase
from .features import CanonicalFeatureStore, CANONICAL_FEATURE_VERSION
from .recommendation import RecommendationSnapshot
from .selection import FEATURE_VECTOR_NAMES, SELECTION_CONFIG, _feature_vector, _ridge_score, _digest
from .signals import ResearchSignalStore
from .context_learning import SELECTOR_VERSION, adjustment


SIGNAL_INPUTS = (
    "event_open_ms", "symbol", "feature_version", "ret_1h_percentile",
    "ret_4h_percentile", "ret_4h", "realized_vol_4h", "breadth_positive_1h", "ret_1h",
)


class LearnedTestnetSource:
    """Bounded inference from immutable models, with durable per-event decisions.

    The LIVE and TESTNET stores remain separate. Testnet quotes establish the
    execution reference; live features establish the model's decision inputs.
    An unproven model is permitted only under the experimental Testnet authority.
    """

    def __init__(self, testnet: EvidenceDatabase, *, release_sha: str,
                 live: EvidenceDatabase | None = None, memory_path: Path | None = None):
        if testnet.config.market_environment != "TESTNET":
            raise ValueError("LEARNED_SOURCE_TESTNET_ONLY")
        self.testnet = testnet
        self.live = live or EvidenceDatabase(observation_config_for_profile(get_profile("live-paper")))
        if self.live.config.market_environment != "LIVE":
            raise ValueError("LEARNED_SOURCE_LIVE_TRAINING_REQUIRED")
        self.memory_path = memory_path or Path("data/observation/live/research_memory.db")
        self.release_sha = release_sha
        self.features = CanonicalFeatureStore(self.live)
        self.signals = ResearchSignalStore(self.live)
        with self.testnet.connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS learned_testnet_decisions (
                event_open_ms INTEGER PRIMARY KEY, snapshot_json TEXT NOT NULL,
                snapshot_digest TEXT NOT NULL)""")

    @staticmethod
    def _artifact(conn, key):
        row = conn.execute("SELECT artifact_json,artifact_digest FROM research_memory_artifacts "
                           "WHERE artifact_key=?", (key,)).fetchone()
        if row is None:
            raise ValueError("LEARNED_MODEL_ARTIFACT_MISSING")
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValueError("LEARNED_MODEL_ARTIFACT_CORRUPT")
        return json.loads(row[0]), row[1]

    def _model(self, event_ms):
        if not self.memory_path.is_file():
            return None
        with closing(sqlite3.connect(self.memory_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
            conn.execute("BEGIN")  # model and evaluation links from one read snapshot
            # Bounded scan; a large registry must not stall the realtime path.
            keys = conn.execute("SELECT artifact_key FROM research_memory_artifacts WHERE artifact_key LIKE ? "
                                "ORDER BY recorded_at_ms DESC,artifact_key DESC LIMIT 64",
                                (CHALLENGER_PREFIX + "%",)).fetchall()
            for (key,) in keys:
                challenger, _ = self._artifact(conn, key)
                if challenger.get("release_sha") != self.release_sha:
                    continue
                if challenger.get("evaluator_version") != EVALUATOR_VERSION:
                    continue
                if challenger.get("authority") != "RESEARCH_ONLY_NO_EXECUTION":
                    raise ValueError("LEARNED_CHALLENGER_AUTHORITY_INVALID")
                evaluation_key = EVALUATION_PREFIX + challenger["challenger_version"]
                if conn.execute("SELECT 1 FROM research_memory_artifacts WHERE artifact_key=?", (evaluation_key,)).fetchone():
                    evaluation, _ = self._artifact(conn, evaluation_key)
                    if evaluation.get("status") == "REJECT_RESEARCH_GATE":
                        continue
                    if evaluation.get("status") != "PASS_RESEARCH_GATE":
                        raise ValueError("LEARNED_EVALUATION_STATUS_INVALID")
                artifact, digest = self._artifact(conn, MODEL_PREFIX + challenger["model_version"])
                if digest != challenger["model_artifact_digest"]:
                    raise ValueError("LEARNED_MODEL_LINK_MISMATCH")
                if artifact.get("release_sha") != self.release_sha or artifact.get("statistics_version") != STATISTICS_VERSION:
                    raise ValueError("LEARNED_MODEL_VERSION_MISMATCH")
                if (artifact.get("authority") != "RESEARCH_ONLY_NO_EXECUTION"
                        or artifact.get("selector_version") != SELECTOR_VERSION
                        or artifact.get("feature_names") != list(FEATURE_VECTOR_NAMES)):
                    raise ValueError("LEARNED_MODEL_CONTRACT_MISMATCH")
                if (int(artifact["model_available_at_ms"]) >= event_ms
                        or int(artifact["training_cutoff_event_ms"]) + LABEL_HORIZON_MS >= event_ms):
                    continue
                if int(artifact["training_event_count"]) < SELECTION_CONFIG.min_train_events:
                    continue
                model = artifact["model"]
                if (model.get("feature_names") != list(FEATURE_VECTOR_NAMES)
                        or model.get("selector_version") != SELECTOR_VERSION):
                    raise ValueError("LEARNED_FEATURE_SCHEMA_MISMATCH")
                if model["model_digest"] != _digest({k: v for k, v in model.items() if k != "model_digest"}):
                    raise ValueError("LEARNED_MODEL_DIGEST_MISMATCH")
                if artifact.get("model_digest") != model["model_digest"]:
                    raise ValueError("LEARNED_MODEL_DIGEST_MISMATCH")
                if "context_calibration" not in model:
                    raise ValueError("LEARNED_CONTEXT_MODEL_MISSING")
                if model["context_calibration"].get("cutoff_ms") != int(artifact["training_cutoff_event_ms"]):
                    raise ValueError("LEARNED_CONTEXT_CUTOFF_MISMATCH")
                values = [model["intercept"], *model["means"].values(),
                          *model["scales"].values(), *model["coefficients"].values()]
                if not all(math.isfinite(v) for v in values) or any(model["scales"][n] <= 0 for n in FEATURE_VECTOR_NAMES):
                    raise ValueError("LEARNED_MODEL_NUMERICAL_ERROR")
                return artifact
        return None

    @staticmethod
    def _not_ready(reason, now):
        return RecommendationSnapshot("NOT_READY", reason, None, now)

    def _saved(self, event):
        with self.testnet.connection() as conn:
            row = conn.execute("SELECT snapshot_json,snapshot_digest FROM learned_testnet_decisions "
                               "WHERE event_open_ms=?", (event,)).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if payload_digest(value) != row[1]:
            raise ValueError("LEARNED_DECISION_CORRUPT")
        proposal = ExecutionProposal.from_dict(value["proposal"]) if value["proposal"] else None
        return RecommendationSnapshot(value["status"], value["reason"], proposal, value["refreshed_at_ms"])

    def _freeze(self, event, snapshot):
        value = {"status": snapshot.status, "reason": snapshot.reason,
                 "proposal": snapshot.proposal.to_dict() if snapshot.proposal else None,
                 "refreshed_at_ms": snapshot.refreshed_at_ms}
        with self.testnet.connection() as conn:
            conn.execute("INSERT OR IGNORE INTO learned_testnet_decisions VALUES(?,?,?)",
                         (event, json.dumps(value, sort_keys=True, allow_nan=False), payload_digest(value)))
        return self._saved(event)

    def refresh(self, *, now_ms: int, ttl_ms: int):
        if not self.live.path.is_file():
            return self._not_ready("LEARNING_WAIT_FOR_LIVE_COLLECTOR", now_ms)
        with self.live.connection() as conn:
            event = conn.execute("""SELECT e.event_open_ms,e.event_close_ms,e.captured_at_ms
                FROM market_events e JOIN event_provenance p USING(event_open_ms)
                WHERE e.status='COMPLETE' AND p.evidence_mode='LIVE_POINT_IN_TIME'
                  AND p.context_complete=1 AND p.membership_quality='POINT_IN_TIME'
                ORDER BY e.event_open_ms DESC LIMIT 1""").fetchone()
        if event is None:
            return self._not_ready("LEARNING_WAIT_FOR_LIVE_EVENT", now_ms)
        event_ms, close_ms, captured_ms = map(int, event)
        if not close_ms <= captured_ms <= now_ms or now_ms - captured_ms > ttl_ms:
            return self._not_ready("LEARNED_LIVE_EVENT_STALE_OR_FUTURE", now_ms)
        artifact = self._model(event_ms)
        if artifact is None:
            return self._not_ready("LEARNING_WAIT_FOR_COMPATIBLE_MODEL", now_ms)
        saved = self._saved(event_ms)
        if saved is not None:
            # A newly rejected/replaced model cannot leave its old proposal live.
            if saved.proposal and saved.proposal.model_digest != artifact["model_digest"]:
                return self._not_ready("LEARNED_EVENT_MODEL_CHANGED_WAIT_NEXT_EVENT", now_ms)
            return saved
        with self.testnet.connection() as conn:
            quotes = conn.execute("""SELECT s.symbol,s.bid_price,s.ask_price,s.captured_at_ms
                FROM market_snapshots s JOIN market_events e USING(event_open_ms)
                JOIN event_provenance p USING(event_open_ms)
                WHERE s.event_open_ms=? AND e.status='COMPLETE'
                AND p.evidence_mode='LIVE_POINT_IN_TIME' AND p.context_complete=1""", (event_ms,)).fetchall()
        quotes = {r[0]: r for r in quotes if close_ms <= int(r[3]) <= now_ms
                  and now_ms - int(r[3]) <= ttl_ms and 0 < float(r[1]) <= float(r[2])
                  and math.isfinite(float(r[2]))}
        if not quotes:
            return self._not_ready("LEARNED_WAIT_FOR_MATCHING_TESTNET_EVENT", now_ms)
        candidates = []
        for feature in self.features.compute_event_rows(event_ms, computed_at_ms=now_ms, register_definition=False):
            if not feature["full_history_4h"] or feature["symbol"] not in quotes:
                continue
            signals = self.signals._signals_for_feature_row(
                tuple(feature[k] for k in SIGNAL_INPUTS), computed_at_ms=now_ms)
            signals = {r["signal_version"]: r for r in signals}
            for side in ("LONG", "SHORT"):
                vector = _feature_vector(feature, signals, side)
                score = _ridge_score(artifact["model"], json.dumps(vector, allow_nan=False))
                if not math.isfinite(score):
                    raise ValueError("LEARNED_SCORE_NOT_FINITE")
                candidates.append((score, feature["symbol"], side, vector))
        if not candidates:
            return self._not_ready("LEARNING_WAIT_FOR_FULL_FEATURE_HISTORY", now_ms)
        score, symbol, side, vector = sorted(candidates, key=lambda r: (-r[0], r[1], r[2]))[0]
        if score <= 0:
            return self._freeze(event_ms, RecommendationSnapshot("READY", "LEARNED_NO_POSITIVE_OPPORTUNITY", None, now_ms))
        _, bid, ask, quote_ms = quotes[symbol]
        raw_model = {k: v for k, v in artifact["model"].items() if k != "context_calibration"}
        setup_explanation = adjustment(artifact["model"]["context_calibration"], vector,
                                      _ridge_score(raw_model, json.dumps(vector)))
        generated = min(captured_ms, int(quote_ms))
        source_digest = payload_digest({"live_event": event_ms, "vector": vector,
                                        "model": artifact["model_digest"], "testnet_quote": quotes[symbol]})
        proposal = ExecutionProposal.create(
            proposal_id="PROP-" + hashlib.sha256(f"{TESTNET_LEARNED_AUTHORITY}:{event_ms}".encode()).hexdigest()[:40],
            generated_at_ms=generated, expires_at_ms=generated + ttl_ms,
            profile="testnet-trade", market_environment="TESTNET", evidence_lineage="TESTNET_OPERATIONAL_ONLY",
            symbol=symbol, side=side, market_event_id=f"ME-{event_ms}",
            data_generation_id=f"LEARNED-TESTNET-{event_ms}", feature_version=CANONICAL_FEATURE_VERSION,
            selector_version=artifact["selector_version"], entry_authority=TESTNET_LEARNED_AUTHORITY,
            exit_policy_version="INTEGER_R_STEP_CONTROL", reference_price=(float(bid) + float(ask)) / 2,
            selection_score=score, selection_rank=1, expected_after_cost_net_r=score,
            source_digest=source_digest, model_digest=artifact["model_digest"],
            experiment_context={"authority_class": "TESTNET_LEARNED_EXPERIMENT", "economic_claim": False,
                "research_evidence": False, "training_environment": "LIVE", "inference_environment": "LIVE",
                "execution_environment": "TESTNET", "model_version": artifact["model_version"],
                "training_cutoff_event_ms": artifact["training_cutoff_event_ms"],
                "live_market_event_ms": event_ms, "reference_quote_environment": "TESTNET",
                "selection_method": "CONTEXT_CALIBRATED_RIDGE", "setup_explanation": setup_explanation,
                "prediction_target": "SIMULATED_ATR_R_4H_NOT_EXECUTION_PNL",
                "candidate_count": len(candidates)},
        )
        return self._freeze(event_ms, RecommendationSnapshot("READY", None, proposal, now_ms))


def testnet_recommendation_source(database, profile, release_sha, *, mode="learned"):
    if mode not in {"learned", "mechanical"}:
        raise ValueError("TESTNET_RECOMMENDATION_MODE_INVALID")
    if profile.name != "testnet-trade" or mode == "mechanical":
        return None
    return LearnedTestnetSource(database, release_sha=release_sha)
