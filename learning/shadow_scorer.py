"""Read-only shadow scoring for Phase 4.6 ensemble artifacts."""

from __future__ import annotations

import json
import math
import os
import pickle
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from strategy.experiment_contract import (
    EXPERIMENT_CONTRACT_VERSION,
    build_model_version_from_bytes,
)


class ShadowModelError(RuntimeError):
    pass


class ShadowModelScorer:
    """Score candidates without mutating ranking or execution decisions."""

    def __init__(
        self,
        *,
        enabled: bool,
        artifact_path: str,
        predictions_path: str,
        refresh_seconds: int = 300,
        system_log=None,
    ):
        self.enabled = bool(enabled)
        self.artifact_path = Path(artifact_path)
        self.predictions_path = Path(predictions_path)
        self.refresh_seconds = int(refresh_seconds)
        self.system_log = system_log
        self._artifact = None
        self._artifact_mtime_ns = None
        self._artifact_model_version = None
        self._last_load_attempt = 0.0
        self._lock = threading.Lock()

    def score_candidates(
        self,
        candidates,
        *,
        rule_selected_candidate=None,
    ) -> list[dict]:
        if not self.enabled:
            return []

        artifact = self._get_artifact()
        if artifact is None:
            return []

        predictions = []
        for rule_rank, candidate in enumerate(candidates, start=1):
            try:
                probability = self._predict(artifact, candidate)
            except Exception as exc:
                if self.system_log:
                    self.system_log.error(
                        "SHADOW_MODEL_CANDIDATE_FAILED | "
                        f"id={candidate.observation_id} | error={exc}"
                    )
                continue
            predictions.append({
                "candidate_observation_id": candidate.observation_id,
                "symbol": candidate.symbol,
                "direction": candidate.direction,
                "pattern": candidate.pattern,
                "rule_rank": rule_rank,
                "rule_score": float(candidate.score),
                "shadow_probability": probability,
                "decision_batch_id": candidate.decision_batch_id,
                "market_event_id": candidate.market_event_id,
                "strategy_version": candidate.strategy_version,
                "strategy_variant_id": candidate.strategy_variant_id,
                "rule_model_version": candidate.model_version,
                "experiment_contract_version": (
                    EXPERIMENT_CONTRACT_VERSION
                    if candidate.experiment_context else 0
                ),
                "shadow_model_version": self._artifact_model_version,
                "rule_selected": bool(
                    rule_selected_candidate is not None
                    and candidate is rule_selected_candidate
                ),
            })

        shadow_sorted = sorted(
            predictions,
            key=lambda row: (
                -row["shadow_probability"],
                row["symbol"],
                row["direction"],
                row["candidate_observation_id"],
            ),
        )
        for shadow_rank, row in enumerate(shadow_sorted, start=1):
            row["shadow_rank"] = shadow_rank
            row["shadow_selected"] = shadow_rank == 1
            row["ranking_changed"] = (
                row["shadow_rank"] != row["rule_rank"]
            )
            row["runtime_effect"] = "NONE"

        self._append_rows(shadow_sorted)

        if self.system_log and shadow_sorted:
            rule_selected = next(
                (
                    row
                    for row in shadow_sorted
                    if row["rule_selected"]
                ),
                None,
            )
            shadow_selected = shadow_sorted[0]
            self.system_log.info(
                "SHADOW_MODEL_BATCH_SCORED | "
                f"candidates={len(shadow_sorted)} | "
                f"shadow_symbol={shadow_selected['symbol']} | "
                f"shadow_direction={shadow_selected['direction']} | "
                f"shadow_probability="
                f"{shadow_selected['shadow_probability']:.6f} | "
                f"rule_symbol="
                f"{rule_selected['symbol'] if rule_selected else 'NONE'} | "
                f"rule_direction="
                f"{rule_selected['direction'] if rule_selected else 'NONE'} | "
                "runtime_effect=NONE"
            )
        return shadow_sorted

    def _get_artifact(self):
        now = time.monotonic()
        with self._lock:
            if (
                self._artifact is not None
                and now - self._last_load_attempt < self.refresh_seconds
            ):
                return self._artifact

            self._last_load_attempt = now
            if not self.artifact_path.is_file():
                if self.system_log:
                    self.system_log.warning(
                        "SHADOW_MODEL_ARTIFACT_UNAVAILABLE | "
                        f"path={self.artifact_path}"
                    )
                return None

            mtime_ns = self.artifact_path.stat().st_mtime_ns
            if (
                self._artifact is not None
                and self._artifact_mtime_ns == mtime_ns
            ):
                return self._artifact

            try:
                artifact_bytes = self.artifact_path.read_bytes()
                artifact = pickle.loads(artifact_bytes)
                self._validate_artifact(artifact)
                artifact_model_version = (
                    build_model_version_from_bytes(artifact_bytes)
                )
            except Exception as exc:
                if self.system_log:
                    self.system_log.error(
                        "SHADOW_MODEL_LOAD_FAILED | "
                        f"path={self.artifact_path} | error={exc}"
                    )
                return None

            self._artifact = artifact
            self._artifact_mtime_ns = mtime_ns
            self._artifact_model_version = artifact_model_version
            if self.system_log:
                self.system_log.info(
                    "SHADOW_MODEL_LOADED | "
                    f"path={self.artifact_path} | "
                    f"winner={artifact['winner']['name']} | "
                    f"model_version={artifact_model_version} | "
                    "runtime_effect=NONE"
                )
            return self._artifact

    @staticmethod
    def _validate_artifact(artifact):
        required = {
            "artifact_schema_version",
            "artifact_kind",
            "base_feature_names",
            "pattern_categories",
            "vector_columns",
            "scaler",
            "models",
            "winner",
            "runtime_activation",
        }
        if not isinstance(artifact, dict) or not required.issubset(
            artifact
        ):
            raise ShadowModelError(
                "SHADOW_MODEL_ARTIFACT_SCHEMA_INVALID"
            )
        if artifact["artifact_kind"] != "OFFLINE_ENSEMBLE_EXPERIMENT":
            raise ShadowModelError(
                "SHADOW_MODEL_ARTIFACT_KIND_INVALID"
            )
        if artifact["runtime_activation"] != "DISABLED":
            raise ShadowModelError(
                "SHADOW_MODEL_RUNTIME_FLAG_INVALID"
            )
        winner = artifact["winner"]
        if not isinstance(winner, dict):
            raise ShadowModelError("SHADOW_MODEL_WINNER_INVALID")
        if winner.get("kind") not in {"MODEL", "BLEND"}:
            raise ShadowModelError("SHADOW_MODEL_WINNER_KIND_INVALID")
        if not isinstance(artifact["models"], dict):
            raise ShadowModelError("SHADOW_MODEL_MODELS_INVALID")

    def _predict(self, artifact, candidate) -> float:
        vector = np.asarray(
            [self._vector(artifact, candidate)],
            dtype=float,
        )
        probabilities = {}
        for name, model in artifact["models"].items():
            matrix = (
                artifact["scaler"].transform(vector)
                if name == "LOGISTIC_REGRESSION"
                else vector
            )
            probabilities[name] = float(
                model.predict_proba(matrix)[0][1]
            )

        winner = artifact["winner"]
        if winner["kind"] == "MODEL":
            probability = probabilities[winner["name"]]
        else:
            weights = winner.get("weights")
            if not isinstance(weights, dict):
                raise ShadowModelError(
                    "SHADOW_MODEL_BLEND_WEIGHTS_INVALID"
                )
            probability = sum(
                float(weights[name]) * probabilities[name]
                for name in weights
            )

        if not math.isfinite(probability):
            raise ShadowModelError(
                "SHADOW_MODEL_PROBABILITY_INVALID"
            )
        return min(1.0, max(0.0, probability))

    @staticmethod
    def _vector(artifact, candidate):
        features = candidate.features.as_dict()
        breakdown = candidate.score_breakdown
        rule_score = (
            float(breakdown.rule_score)
            if breakdown is not None
            else float(candidate.score)
        )
        return (
            [
                float(features[name])
                for name in artifact["base_feature_names"]
            ]
            + [
                rule_score,
                float(candidate.score),
                1.0 if candidate.direction == "LONG" else 0.0,
            ]
            + [
                1.0 if candidate.pattern == pattern else 0.0
                for pattern in artifact["pattern_categories"]
            ]
        )

    def _append_rows(self, rows):
        if not rows:
            return
        self.predictions_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        observed_at_ms = int(time.time() * 1000)
        lines = []
        for row in rows:
            document = {
                "schema_version": 2,
                "observation_type": "SHADOW_MODEL_PREDICTION",
                "observed_at_ms": observed_at_ms,
                **row,
            }
            lines.append(
                json.dumps(document, sort_keys=True, default=str)
            )

        descriptor = os.open(
            self.predictions_path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(
                descriptor,
                ("\n".join(lines) + "\n").encode("utf-8"),
            )
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
