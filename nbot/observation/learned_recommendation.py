"""LIVE-trained inference with separate profile authority and paper-only feedback."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import math
import logging
import os
from pathlib import Path
import sqlite3

from nbot.communication.authorities import TESTNET_LEARNED_AUTHORITY, LIVE_PAPER_LEARNED_AUTHORITY, LIVE_LEARNED_AUTHORITY
from nbot.communication.contracts import ExecutionProposal
from nbot.communication.validation import payload_digest, symbol as protocol_symbol
from nbot.config.profiles import get_profile
from .causal_ridge import LABEL_HORIZON_MS, STATISTICS_VERSION
from .challengers import CHALLENGER_PREFIX, MODEL_PREFIX, EVALUATION_PREFIX, EVALUATOR_VERSION
from .config import observation_config_for_profile
from .database import EvidenceDatabase
from .decision_ledger import DecisionOutcomeLedger
from .features import CanonicalFeatureStore, CANONICAL_FEATURE_VERSION
from .recommendation import RecommendationSnapshot
from .selection import FEATURE_VECTOR_NAMES, SELECTION_CONFIG, _feature_vector, _ridge_score, _digest
from .signals import ResearchSignalStore
from .context_learning import SELECTOR_VERSION, adjustment, describe
from .paper_feedback import PaperFeedback
from .shadow import ShadowBook, ShadowConfig
from .model_compatibility import compatible_training_release
from .candidate_setups import load_histories, matches, FALLBACK, CATALOG_DIGEST, history_digest, tie_key
from .research_memory import ResearchMemoryStore
from .selective_ml import LOWER_SCORE_WEIGHT, MEAN_SCORE_WEIGHT
from .selective_ml_v3 import SelectiveMLManager, SelectiveMLRuntime


SIGNAL_INPUTS = (
    "event_open_ms", "symbol", "feature_version", "ret_1h_percentile",
    "ret_4h_percentile", "ret_4h", "realized_vol_4h", "breadth_positive_1h", "ret_1h",
)


def _execution_compatible_quotes(rows, *, close_ms: int, now_ms: int, ttl_ms: int):
    """Keep only fresh quotes whose symbols can cross the Execution protocol."""
    quotes = {}
    for row in rows:
        try:
            normalized_symbol = protocol_symbol(row[0])
        except ValueError:
            continue
        if (
            close_ms <= int(row[3]) <= now_ms
            and now_ms - int(row[3]) <= ttl_ms
            and 0 < float(row[1]) <= float(row[2])
            and math.isfinite(float(row[2]))
        ):
            quotes[normalized_symbol] = (
                normalized_symbol, row[1], row[2], row[3]
            )
    return quotes


class LearnedTestnetSource:
    """Bounded inference from immutable models, with durable per-event decisions.

    The LIVE and TESTNET stores remain separate. Testnet quotes establish the
    execution reference; live features establish the model's decision inputs.
    An unproven model is permitted only under the experimental Testnet authority.
    """

    def __init__(self, testnet: EvidenceDatabase, *, release_sha: str,
                 live: EvidenceDatabase | None = None, memory_path: Path | None = None,
                 profile_name: str = "testnet-trade"):
        if profile_name not in {"testnet-trade", "live-paper", "live-trade"}:
            raise ValueError("LEARNED_SOURCE_PROFILE_UNSUPPORTED")
        self.profile = get_profile(profile_name)
        self.authority = (TESTNET_LEARNED_AUTHORITY if profile_name == "testnet-trade"
                          else LIVE_PAPER_LEARNED_AUTHORITY if profile_name == "live-paper" else LIVE_LEARNED_AUTHORITY)
        self.decision_table = ("learned_testnet_decisions" if profile_name == "testnet-trade"
                               else "learned_live_paper_decisions" if profile_name == "live-paper" else "learned_live_trial_decisions")
        if testnet.config.market_environment != self.profile.market_environment:
            raise ValueError("LEARNED_SOURCE_TESTNET_ONLY" if profile_name == "testnet-trade" else "LEARNED_SOURCE_REFERENCE_ENVIRONMENT_MISMATCH")
        self.testnet = testnet
        self.live = live or (testnet if profile_name in {"live-paper", "live-trade"} else
                            EvidenceDatabase(observation_config_for_profile(get_profile("live-paper"))))
        if self.live.config.market_environment != "LIVE":
            raise ValueError("LEARNED_SOURCE_LIVE_TRAINING_REQUIRED")
        self.memory_path = memory_path or Path("data/observation/live/research_memory.db")
        self.release_sha = release_sha
        self._release_compatibility = {}
        self.paper_feedback = PaperFeedback(self.live, release_sha=release_sha) if profile_name == "live-paper" else None
        counterfactual_enabled = os.environ.get("NBOT_COUNTERFACTUAL_ENABLED", "1")
        if counterfactual_enabled not in {"0", "1"}:
            raise ValueError("NBOT_COUNTERFACTUAL_ENABLED_INVALID")
        self.decision_ledger = (
            DecisionOutcomeLedger(self.live.path.parent / "decision_outcomes.db")
            if profile_name in {"live-paper", "live-trade"} and counterfactual_enabled == "1"
            else None
        )
        self.decision_ledger_error = None
        ml_enabled = os.environ.get("NBOT_SELECTIVE_ML", "1")
        if ml_enabled not in {"0", "1"}:
            raise ValueError("NBOT_SELECTIVE_ML_INVALID")
        self.selective_ml = (
            SelectiveMLManager(ResearchMemoryStore(self.memory_path), self.live, release_sha=release_sha)
            if profile_name == "live-paper" and ml_enabled == "1" else None
        )
        self._selective_ml_runtime = None
        self._selective_ml_artifact_digest = None
        shadow_enabled = os.environ.get("NBOT_SHADOW_ENABLED", "1")
        if shadow_enabled not in {"0", "1"}:
            raise ValueError("NBOT_SHADOW_ENABLED_INVALID")
        self.shadow = None
        self.shadow_error = None
        if profile_name in {"live-paper", "live-trade"} and shadow_enabled == "1":
            shadow_config = ShadowConfig(**{
                field: float(os.environ["NBOT_SHADOW_" + field.upper()])
                for field in ShadowConfig.__dataclass_fields__
                if "NBOT_SHADOW_" + field.upper() in os.environ})
            self.shadow = ShadowBook(self.live, release_sha=release_sha, profile=profile_name, config=shadow_config)
        self.features = CanonicalFeatureStore(self.live)
        self.signals = ResearchSignalStore(self.live)
        with self.testnet.connection() as conn:
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {self.decision_table} (
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

    def _compatible_release(self, trained_sha):
        if trained_sha == self.release_sha:
            return True
        # Real-money trials still require the exact explicitly tested release.
        if self.profile.name == "live-trade":
            return False
        if trained_sha not in self._release_compatibility:
            self._release_compatibility[trained_sha] = compatible_training_release(
                Path(__file__).resolve().parents[2], trained_sha, self.release_sha)
        return self._release_compatibility[trained_sha]

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
                if not self._compatible_release(challenger.get("release_sha")):
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
                if (artifact.get("release_sha") != challenger.get("release_sha")
                        or artifact.get("statistics_version") != STATISTICS_VERSION):
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
            row = conn.execute(f"SELECT snapshot_json,snapshot_digest FROM {self.decision_table} "
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
            conn.execute(f"INSERT OR IGNORE INTO {self.decision_table} VALUES(?,?,?)",
                         (event, json.dumps(value, sort_keys=True, allow_nan=False), payload_digest(value)))
        return self._saved(event)

    def _shadow_call(self, method, **kwargs):
        try:
            getattr(self.shadow, method)(**kwargs)
            self.shadow_error = None
        except Exception as exc:
            # Simulations must never disrupt the main position/control path.
            self.shadow_error = type(exc).__name__ + ":" + str(exc)[:180]
            logging.getLogger(__name__).exception("SHADOW_SIMULATION_FAILED")

    def _record_decision_universe(
        self, *, event_ms: int, now_ms: int, quotes: dict, candidates: list,
        histories: dict, ranked: list, btc_available: dict,
        selected_symbol: str, selected_side: str,
        final_score: float, final_reason: str | None, raw_ml_gate: str | None,
        model_digest: str,
    ) -> None:
        """Freeze every eligible symbol/side decision for high-resolution replay.

        One hypothesis is stored per symbol/side/event even when multiple setup
        rules match. The setup IDs remain attribution metadata. A research-ledger
        failure is visible in diagnostics but can never alter recommendation or
        order authority.
        """
        if self.decision_ledger is None:
            return
        try:
            practical: dict[tuple[str, str], tuple[float, dict]] = {}
            for row in ranked:
                adjusted, symbol, side, _vector, _base, _ridge, detail = row
                key = (symbol, side)
                current = practical.get(key)
                if current is None or adjusted > current[0]:
                    practical[key] = (float(adjusted), detail)

            unique = []
            for selection_base, symbol, side, vector, ridge_score, ml_detail in candidates:
                key = (symbol, side)
                detail = practical.get(key)
                practical_score = float(detail[0]) if detail is not None else float(selection_base)
                setup_ids = (
                    list(detail[1].get("matched_candidates", []))
                    if detail is not None
                    else [item["id"] for item in (matches(
                        dict(vector, candidate_btc_available=float(btc_available.get(symbol, False))),
                        side, histories.get(symbol, []),
                    ) or [FALLBACK])]
                )
                unique.append((
                    practical_score, symbol, side, vector, ridge_score,
                    ml_detail or {}, setup_ids,
                ))
            raw_scores = {(item[1], item[2]): float(item[0]) for item in candidates}
            ordered = sorted(
                unique,
                key=lambda item: (-raw_scores[(item[1], item[2])], item[1], item[2]),
            )
            runner_raw = raw_scores[(ordered[1][1], ordered[1][2])] if len(ordered) > 1 else None
            for rank, (practical_score, symbol, side, vector, ridge_score, ml, setup_ids) in enumerate(ordered, start=1):
                selected = (
                    final_score > 0
                    and symbol == selected_symbol
                    and side == selected_side
                )
                if selected:
                    blocker = None
                elif rank == 1 and raw_ml_gate is not None:
                    blocker = raw_ml_gate
                elif symbol == selected_symbol and side == selected_side and final_score <= 0:
                    blocker = final_reason or "LEARNED_REJECTED"
                else:
                    blocker = "LOWER_RANKED_OR_NOT_SELECTED"
                quote = quotes[symbol]
                scores = {
                    "ridge_score_r": float(ml.get("ridge_score", ridge_score)),
                    "ml_mean_r": ml.get("ml_mean_r"),
                    "ml_lower_r": ml.get("ml_lower_r"),
                    "ensemble_mean_r": ml.get("ensemble_mean_r"),
                    "conservative_score_r": float(selection_base_for := next(
                        item[0] for item in candidates
                        if item[1] == symbol and item[2] == side
                    )),
                    "post_feedback_score_r": practical_score,
                    "raw_rank": rank,
                    "raw_edge_gap_r": (
                        raw_scores[(symbol, side)] - runner_raw
                        if rank == 1 and runner_raw is not None else None
                    ),
                    "raw_ml_gate": raw_ml_gate if rank == 1 else None,
                }
                self.decision_ledger.record(
                    release_sha=self.release_sha,
                    event_ms=event_ms,
                    decision_ms=now_ms,
                    symbol=symbol,
                    side=side,
                    bid=float(quote[1]),
                    ask=float(quote[2]),
                    selected=selected,
                    decision="APPROVED" if selected else "REJECTED",
                    blocker=blocker,
                    feature_vector=vector,
                    candidate_ids=setup_ids,
                    scores=scores,
                    rank=rank,
                    model_digest=model_digest,
                )
            self.decision_ledger_error = None
        except Exception as exc:
            self.decision_ledger_error = type(exc).__name__ + ":" + str(exc)[:180]
            logging.getLogger(__name__).exception("DECISION_LEDGER_RECORD_FAILED")

    def refresh(self, *, now_ms: int, ttl_ms: int):
        if self.shadow:
            self._shadow_call("advance", now_ms=now_ms)
        if self.paper_feedback:
            self.paper_feedback.ingest(cutoff_ms=now_ms)
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
            if self.paper_feedback and saved.proposal and self.paper_feedback.cooldown(
                    saved.proposal.symbol, saved.proposal.side, cutoff_ms=now_ms):
                return self._not_ready("PAPER_REPEATED_LOSS_COOLDOWN", now_ms)
            # A newly rejected/replaced model cannot leave its old proposal live.
            if saved.proposal and saved.proposal.model_digest != artifact["model_digest"]:
                return self._not_ready("LEARNED_EVENT_MODEL_CHANGED_WAIT_NEXT_EVENT", now_ms)
            if self.paper_feedback and saved.proposal:
                detail = (saved.proposal.experiment_context or {}).get("paper_feedback")
                if detail:
                    self.paper_feedback.record_decision(saved.proposal.proposal_id, saved.refreshed_at_ms, detail)
            return saved
        with self.testnet.connection() as conn:
            quotes = conn.execute("""SELECT s.symbol,s.bid_price,s.ask_price,s.captured_at_ms
                FROM market_snapshots s JOIN market_events e USING(event_open_ms)
                JOIN event_provenance p USING(event_open_ms)
                WHERE s.event_open_ms=? AND e.status='COMPLETE'
                AND p.evidence_mode='LIVE_POINT_IN_TIME' AND p.context_complete=1""", (event_ms,)).fetchall()
        quotes = _execution_compatible_quotes(
            quotes, close_ms=close_ms, now_ms=now_ms, ttl_ms=ttl_ms
        )
        if not quotes:
            return self._not_ready("LEARNED_WAIT_FOR_MATCHING_TESTNET_EVENT" if self.profile.name == "testnet-trade" else "LEARNED_WAIT_FOR_MATCHING_LIVE_EVENT", now_ms)
        feedback_model = self.paper_feedback.snapshot(cutoff_ms=now_ms) if self.paper_feedback else None
        ml_record = self.selective_ml.latest_for_event(event_ms) if self.selective_ml else None
        ml_runtime = None
        if ml_record is not None:
            if self._selective_ml_artifact_digest != ml_record["artifact_digest"]:
                self._selective_ml_runtime = SelectiveMLRuntime(ml_record["payload"])
                self._selective_ml_artifact_digest = ml_record["artifact_digest"]
            ml_runtime = self._selective_ml_runtime

        candidates = []
        btc_available = {}
        for feature in self.features.compute_event_rows(event_ms, computed_at_ms=now_ms, register_definition=False):
            if not feature["full_history_4h"] or feature["symbol"] not in quotes:
                continue
            btc_available[feature["symbol"]] = feature.get("btc_ret_1h") is not None
            signals = self.signals._signals_for_feature_row(
                tuple(feature[k] for k in SIGNAL_INPUTS), computed_at_ms=now_ms)
            signals = {r["signal_version"]: r for r in signals}
            for side in ("LONG", "SHORT"):
                vector = _feature_vector(feature, signals, side)
                ridge_score = _ridge_score(artifact["model"], json.dumps(vector, allow_nan=False))
                if not math.isfinite(ridge_score):
                    raise ValueError("LEARNED_SCORE_NOT_FINITE")
                selection_base = ridge_score
                ml_detail = None
                if ml_runtime is not None:
                    ml_mean, ml_lower = ml_runtime.score(vector)
                    ridge_weight = self.selective_ml.ridge_blend_weight(ml_record)
                    ensemble_mean = ridge_weight * ridge_score + (1.0 - ridge_weight) * ml_mean
                    selection_base = (
                        MEAN_SCORE_WEIGHT * ensemble_mean + LOWER_SCORE_WEIGHT * ml_lower
                    )
                    ml_detail = {
                        "artifact_key": ml_record["artifact_key"],
                        "artifact_digest": ml_record["artifact_digest"],
                        "model_digest": ml_record["payload"]["model_digest"],
                        "ridge_score": ridge_score,
                        "ml_mean_r": ml_mean,
                        "ml_lower_r": ml_lower,
                        "ensemble_mean_r": ensemble_mean,
                        "conservative_score_r": selection_base,
                        "selective_ml_version": ml_record["payload"].get("version"),
                        "target": self.selective_ml.target_for_record(ml_record),
                        "ridge_blend_weight": ridge_weight,
                        "entry_gate_mode": ml_record["payload"].get("entry_gate_mode", "EXECUTION_REALTIME_ONLY"),
                    }
                candidates.append((selection_base, feature["symbol"], side, vector, ridge_score, ml_detail))
        if not candidates:
            return self._not_ready("LEARNING_WAIT_FOR_FULL_FEATURE_HISTORY", now_ms)

        ridge_baseline = sorted(candidates, key=lambda r: (-r[4], r[1], r[2]))[0]
        selection_order = sorted(candidates, key=lambda r: (-r[0], r[1], r[2]))
        selection_baseline = selection_order[0]
        ml_gate_reason = None
        ml_selection_audit = None
        if ml_runtime is not None:
            min_confidence_r, min_edge_gap_r = self.selective_ml.gate_for_record(ml_record)
            runner_up = selection_order[1] if len(selection_order) > 1 else None
            edge_gap = (
                selection_baseline[0] - runner_up[0] if runner_up is not None else None
            )
            if selection_baseline[0] < min_confidence_r:
                ml_gate_reason = "LEARNED_ML_ABSTAIN_LOW_CONFIDENCE"
            elif edge_gap is not None and edge_gap < min_edge_gap_r:
                ml_gate_reason = "LEARNED_ML_ABSTAIN_EDGE_TOO_SMALL"
            winner_ml = selection_baseline[5] or {}
            ml_selection_audit = {
                "symbol": selection_baseline[1],
                "side": selection_baseline[2],
                "ridge_score_r": winner_ml.get("ridge_score", selection_baseline[4]),
                "ml_mean_r": winner_ml.get("ml_mean_r"),
                "ml_lower_r": winner_ml.get("ml_lower_r"),
                "ensemble_mean_r": winner_ml.get("ensemble_mean_r"),
                "conservative_score_r": selection_baseline[0],
                "min_confidence_r": min_confidence_r,
                "confidence_pass": selection_baseline[0] >= min_confidence_r,
                "runner_up_symbol": runner_up[1] if runner_up is not None else None,
                "runner_up_side": runner_up[2] if runner_up is not None else None,
                "runner_up_conservative_score_r": runner_up[0] if runner_up is not None else None,
                "edge_gap_r": edge_gap,
                "min_edge_gap_r": min_edge_gap_r,
                "edge_pass": edge_gap is None or edge_gap >= min_edge_gap_r,
                "gate_reason": ml_gate_reason,
                "entry_gate_mode": (ml_record["payload"].get("entry_gate_mode", "EXECUTION_REALTIME_ONLY") if ml_record is not None else "EXECUTION_REALTIME_ONLY"),
            }

        feedback_detail = None
        histories = {}
        shadow_history_ready = True
        if self.paper_feedback:
            histories = load_histories(self.live, quotes, event_ms)
        elif self.shadow:
            try:
                histories = load_histories(self.live, quotes, event_ms)
            except Exception as exc:
                shadow_history_ready = False
                self.shadow_error = type(exc).__name__ + ":" + str(exc)[:180]
                logging.getLogger(__name__).exception("SHADOW_HISTORY_FAILED")

        ranked = []
        if feedback_model is not None:
            for selection_base, candidate_symbol, candidate_side, candidate_vector, ridge_score, ml_detail in candidates:
                bars = histories.get(candidate_symbol, [])
                bars_digest = history_digest(bars)
                rule_vector = dict(candidate_vector, candidate_btc_available=float(btc_available[candidate_symbol]))
                rules = matches(rule_vector, candidate_side, bars) or [FALLBACK]
                for rule in rules:
                    adjusted, detail = self.paper_feedback.adjust(
                        feedback_model, candidate_vector, candidate_side, selection_base, candidate=rule,
                        symbol=candidate_symbol, now_ms=now_ms)
                    detail.update(matched_candidates=[item["id"] for item in rules],
                                  catalog_digest=CATALOG_DIGEST, history_digest=bars_digest)
                    detail["post_feedback_score_r"] = adjusted
                    if ml_detail is not None:
                        detail["selective_ml"] = {
                            **ml_detail,
                            "pre_feedback_gate": ml_gate_reason,
                            "entry_gate_mode": (ml_record["payload"].get("entry_gate_mode", "EXECUTION_REALTIME_ONLY") if ml_record is not None else "EXECUTION_REALTIME_ONLY"),
                        }
                    ranked.append((adjusted, candidate_symbol, candidate_side,
                                   candidate_vector, selection_base, ridge_score, detail))
            # Preserve the established deterministic practical-ranking order.
            # The raw Selective-ML winner is recorded separately for diagnostics.
            score, symbol, side, vector, base_score, ridge_score, feedback_detail = sorted(
                ranked, key=lambda r: (-r[0], r[1], r[2],
                    tie_key(event_ms, r[1], r[2], r[6]["candidate"]["id"])))[0]
            if ml_gate_reason is not None:
                score = 0.0
            feedback_detail["matched_candidate_count"] = len(ranked)
            baseline_candidate = min(
                (r for r in ranked if (r[1], r[2]) == (ridge_baseline[1], ridge_baseline[2])),
                key=lambda r: tie_key(event_ms, r[1], r[2], r[6]["candidate"]["id"]))
            self.paper_feedback.record_check(event_ms, now_ms, {
                "main_samples": feedback_model["sample_count"],
                "shadow_samples": feedback_model["shadow_sample_count"],
                "cooldown_choices_blocked": sum(r[6]["status"]=="REPEATED_LOSS_COOLDOWN" for r in ranked),
                "outcome_choices_adjusted": sum(r[6]["outcome_factor"]!=1 for r in ranked),
                "entry_choices_adjusted": sum(r[6]["entry_feasibility_factor"]!=1 for r in ranked),
                "baseline": {"symbol":ridge_baseline[1],"side":ridge_baseline[2],
                             "candidate":baseline_candidate[6]["candidate"]["id"],"score":ridge_baseline[4]},
                "raw_ml_winner": ml_selection_audit,
                "selected": {
                    "symbol": symbol, "side": side,
                    "candidate": feedback_detail["candidate"]["id"],
                    "score": score, "factor": feedback_detail["factor"],
                    "reason": feedback_detail["status"],
                    "post_feedback_score_r": feedback_detail.get("post_feedback_score_r"),
                    "outcome_factor": feedback_detail.get("outcome_factor"),
                    "entry_gate_mode": (ml_record["payload"].get("entry_gate_mode", "EXECUTION_REALTIME_ONLY") if ml_record is not None else "EXECUTION_REALTIME_ONLY"),
                    "next_bar_signal_decay": feedback_detail.get("next_bar_signal_decay", {}),
                },
                "choice_changed": (symbol,side,feedback_detail["candidate"]["id"]) !=
                    (ridge_baseline[1],ridge_baseline[2],baseline_candidate[6]["candidate"]["id"]),
                "no_trade": score<=0,
                "selective_ml_active": ml_runtime is not None,
                "selective_ml_gate": ml_gate_reason,
                "active_cooldowns": feedback_model.get("cooldowns",{})})
            feedback_detail.update(
                base_score=base_score, adjusted_score=score,
                ranking_changed=(symbol, side, feedback_detail["candidate"]["id"]) !=
                    (ridge_baseline[1], ridge_baseline[2], baseline_candidate[6]["candidate"]["id"]),
                baseline_symbol=ridge_baseline[1], baseline_side=ridge_baseline[2],
                baseline_score=ridge_baseline[4])
        else:
            score, symbol, side, vector, ridge_score, ml_detail = selection_baseline
            base_score = score
            if ml_gate_reason is not None:
                score = 0.0

        shadow_opportunities = []
        main_candidate = None
        if self.shadow and shadow_history_ready and any(item[0] > 0 for item in candidates):
            try:
                for candidate_score, candidate_symbol, candidate_side, candidate_vector, candidate_ridge, candidate_ml in candidates:
                    if candidate_score <= 0:
                        continue
                    rule_vector = dict(candidate_vector, candidate_btc_available=float(btc_available[candidate_symbol]))
                    rules = matches(rule_vector, candidate_side, histories.get(candidate_symbol, []))
                    if score > 0 and (candidate_symbol, candidate_side) == (symbol, side):
                        main_candidate = (feedback_detail["candidate"]["id"] if feedback_detail else
                            min((rule["id"] for rule in rules),
                                key=lambda name: tie_key(event_ms,symbol,side,name), default=None))
                    bars_digest = history_digest(histories.get(candidate_symbol, []))
                    for rule in rules:
                        shadow_opportunities.append({
                            "candidate_id": rule["id"], "symbol": candidate_symbol, "side": candidate_side,
                            "score": candidate_score, "bid": float(quotes[candidate_symbol][1]),
                            "ask": float(quotes[candidate_symbol][2]), "model_digest": artifact["model_digest"],
                            "history_digest": bars_digest,
                            "decision_context": describe(candidate_vector)["context"],
                            **({"selective_ml": candidate_ml} if candidate_ml else {})})
            except Exception as exc:
                self.shadow_error = type(exc).__name__ + ":" + str(exc)[:180]
                logging.getLogger(__name__).exception("SHADOW_CANDIDATES_FAILED")
                shadow_opportunities = []

        if score <= 0:
            if feedback_detail and feedback_detail["status"] == "REPEATED_LOSS_COOLDOWN":
                final_reason = "PAPER_REPEATED_LOSS_COOLDOWN"
            elif ml_gate_reason is not None:
                final_reason = ml_gate_reason
            else:
                final_reason = "LEARNED_NO_POSITIVE_OPPORTUNITY"
            self._record_decision_universe(
                event_ms=event_ms, now_ms=now_ms, quotes=quotes, candidates=candidates,
                histories=histories, ranked=ranked, btc_available=btc_available,
                selected_symbol=symbol,
                selected_side=side, final_score=score, final_reason=final_reason,
                raw_ml_gate=ml_gate_reason, model_digest=artifact["model_digest"],
            )
            reason = final_reason
            snapshot = self._freeze(event_ms, RecommendationSnapshot("READY", reason, None, now_ms))
            if self.shadow and shadow_opportunities:
                self._shadow_call("offer", event_ms=event_ms, now_ms=now_ms,
                                  opportunities=shadow_opportunities)
            return snapshot
        _, bid, ask, quote_ms = quotes[symbol]
        raw_model = {k: v for k, v in artifact["model"].items() if k != "context_calibration"}
        setup_explanation = adjustment(artifact["model"]["context_calibration"], vector,
                                      _ridge_score(raw_model, json.dumps(vector)))
        selected_ml = (feedback_detail or {}).get("selective_ml") if feedback_detail is not None else None
        if selected_ml is None and ml_runtime is not None:
            chosen_ml = next((item[5] for item in candidates
                              if (item[1], item[2]) == (symbol, side)), None)
            if chosen_ml is not None:
                selected_ml = dict(chosen_ml)
                selected_ml["pre_feedback_gate"] = ml_gate_reason
                selected_ml["entry_gate_mode"] = ml_record["payload"].get(
                    "entry_gate_mode", "EXECUTION_REALTIME_ONLY"
                )
        expected_net_r = selected_ml["ensemble_mean_r"] if selected_ml is not None else base_score
        generated = min(captured_ms, int(quote_ms))
        self._record_decision_universe(
            event_ms=event_ms, now_ms=now_ms, quotes=quotes, candidates=candidates,
            histories=histories, ranked=ranked, btc_available=btc_available,
            selected_symbol=symbol, selected_side=side, final_score=score, final_reason=None,
            raw_ml_gate=ml_gate_reason, model_digest=artifact["model_digest"],
        )
        source_inputs = {"live_event": event_ms, "vector": vector,
                         "model": artifact["model_digest"], "testnet_quote": quotes[symbol]}
        if feedback_detail is not None:
            source_inputs["paper_feedback"] = feedback_detail
        if selected_ml is not None:
            source_inputs["selective_ml"] = selected_ml
        source_digest = payload_digest(source_inputs)
        proposal = ExecutionProposal.create(
            proposal_id="PROP-" + hashlib.sha256(f"{self.authority}:{event_ms}".encode()).hexdigest()[:40],
            generated_at_ms=generated, expires_at_ms=generated + ttl_ms,
            profile=self.profile.name, market_environment=self.profile.market_environment,
            evidence_lineage=self.profile.evidence_lineage,
            symbol=symbol, side=side, market_event_id=f"ME-{event_ms}",
            data_generation_id=f"LEARNED-{self.profile.name.upper()}-{event_ms}", feature_version=CANONICAL_FEATURE_VERSION,
            selector_version=artifact["selector_version"], entry_authority=self.authority,
            exit_policy_version="INTEGER_R_STEP_CONTROL", reference_price=(float(bid) + float(ask)) / 2,
            selection_score=score, selection_rank=1, expected_after_cost_net_r=expected_net_r,
            source_digest=source_digest, model_digest=artifact["model_digest"],
            experiment_context={"authority_class": self.authority, "economic_claim": False,
                "research_evidence": False, "training_environment": "LIVE", "inference_environment": "LIVE",
                "execution_environment": self.profile.market_environment, "model_version": artifact["model_version"],
                "training_cutoff_event_ms": artifact["training_cutoff_event_ms"],
                "live_market_event_ms": event_ms, "reference_quote_environment": self.profile.market_environment,
                "selection_method": (
                    f"{selected_ml.get('selective_ml_version','SELECTIVE_ML')}_LIGHTGBM_REALTIME_WSS_ENTRY"
                    if selected_ml is not None else "CONTEXT_CALIBRATED_RIDGE"
                ),
                "setup_explanation": setup_explanation,
                "prediction_target": (
                    selected_ml.get("target") if selected_ml is not None
                    else "SIMULATED_ATR_R_4H_NOT_EXECUTION_PNL"
                ),
                "candidate_count": len(candidates),
                **({"selective_ml": selected_ml} if selected_ml is not None else {}),
                **({"shadow_main_candidate": main_candidate} if self.shadow else {}),
                **({"paper_feedback": feedback_detail} if feedback_detail else {})},
        )
        snapshot = self._freeze(event_ms, RecommendationSnapshot("READY", None, proposal, now_ms))
        if self.paper_feedback and snapshot.proposal:
            self.paper_feedback.record_decision(snapshot.proposal.proposal_id, now_ms,
                                                snapshot.proposal.experiment_context["paper_feedback"])
        if self.shadow and snapshot.proposal and shadow_opportunities:
            # Freeze main attribution first. No replay-generated entries after a restart.
            chosen = snapshot.proposal.experiment_context.get("shadow_main_candidate")
            self._shadow_call("offer", event_ms=event_ms, now_ms=now_ms,
                              opportunities=shadow_opportunities, excluded=[chosen] if chosen else [])
        return snapshot


def testnet_recommendation_source(database, profile, release_sha, *, mode="learned"):
    if mode not in {"learned", "mechanical"}:
        raise ValueError("TESTNET_RECOMMENDATION_MODE_INVALID")
    if profile.name != "testnet-trade" or mode == "mechanical":
        return None
    return LearnedTestnetSource(database, release_sha=release_sha)
