"""Safe candidate scoring for registered Phase 5.8 model artifacts.

The scorer accepts the two artifact families produced by the automatic
training orchestrator: the logistic baseline and the offline ensemble. It is
strictly observational and rejects any artifact that claims runtime authority.
"""

from __future__ import annotations

import hashlib
import math
import pickle
from pathlib import Path
from typing import Iterable

import numpy as np

from strategy.features import CANDIDATE_FEATURE_SCHEMA_VERSION


class RegisteredModelScoringError(RuntimeError):
    pass


class RegisteredModelArtifactScorer:
    """Load one immutable registered artifact and score strategy candidates."""

    def __init__(
        self,
        *,
        model_id: str,
        artifact_path: str,
        expected_checksum_sha256: str | None = None,
        expected_feature_schema_version: int | None = None,
    ):
        self.model_id = str(model_id or "").strip()
        self.artifact_path = Path(str(artifact_path or ""))
        self.expected_checksum_sha256 = str(
            expected_checksum_sha256 or ""
        ).strip().lower()
        self.expected_feature_schema_version = (
            int(expected_feature_schema_version)
            if expected_feature_schema_version is not None
            else None
        )
        if not self.model_id:
            raise ValueError("REGISTERED_MODEL_ID_REQUIRED")
        if not str(self.artifact_path):
            raise ValueError("REGISTERED_MODEL_ARTIFACT_PATH_REQUIRED")
        self._artifact = self._load()

    @property
    def artifact(self) -> dict:
        return dict(self._artifact)

    @property
    def feature_schema_version(self) -> int:
        return int(
            self._artifact.get(
                "feature_schema_version",
                CANDIDATE_FEATURE_SCHEMA_VERSION,
            )
        )

    def score_candidates(self, candidates: Iterable) -> dict[str, float]:
        result: dict[str, float] = {}
        for candidate in candidates:
            try:
                probability = self._predict(candidate)
            except KeyError as exc:
                feature = str(exc.args[0]) if exc.args else "UNKNOWN"
                raise RegisteredModelScoringError(
                    "REGISTERED_MODEL_REQUIRED_FEATURE_MISSING | "
                    f"model_id={self.model_id} | feature={feature}"
                ) from exc
            except RegisteredModelScoringError:
                raise
            except Exception as exc:
                raise RegisteredModelScoringError(
                    "REGISTERED_MODEL_PREDICTION_FAILED | "
                    f"model_id={self.model_id} | error={type(exc).__name__}"
                ) from exc
            result[str(candidate.observation_id)] = probability
        return result

    def _load(self) -> dict:
        if not self.artifact_path.is_file():
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_ARTIFACT_MISSING | "
                f"model_id={self.model_id} | path={self.artifact_path}"
            )
        artifact_bytes = self.artifact_path.read_bytes()
        checksum = hashlib.sha256(artifact_bytes).hexdigest()
        if (
            self.expected_checksum_sha256
            and checksum != self.expected_checksum_sha256
        ):
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_ARTIFACT_CHECKSUM_MISMATCH | "
                f"model_id={self.model_id}"
            )
        try:
            artifact = pickle.loads(artifact_bytes)
        except Exception as exc:
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_ARTIFACT_UNPICKLE_FAILED | "
                f"model_id={self.model_id}"
            ) from exc
        self._validate(artifact)
        return artifact

    def _validate(self, artifact) -> None:
        if not isinstance(artifact, dict):
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_ARTIFACT_SCHEMA_INVALID"
            )
        if artifact.get("runtime_activation") != "DISABLED":
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_RUNTIME_AUTHORITY_INVALID"
            )
        artifact_model_id = str(artifact.get("model_id") or "").strip()
        if artifact_model_id and artifact_model_id != self.model_id:
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_ID_MISMATCH | "
                f"expected={self.model_id} | actual={artifact_model_id}"
            )
        required_common = {
            "base_feature_names",
            "pattern_categories",
            "scaler",
        }
        if not required_common.issubset(artifact):
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_FEATURE_SCHEMA_INVALID"
            )
        raw_schema = artifact.get("feature_schema_version")
        if raw_schema is None:
            if self.expected_feature_schema_version is not None:
                raise RegisteredModelScoringError(
                    "REGISTERED_MODEL_FEATURE_SCHEMA_MISSING"
                )
            artifact_schema = CANDIDATE_FEATURE_SCHEMA_VERSION
        else:
            try:
                artifact_schema = int(raw_schema)
            except (TypeError, ValueError) as exc:
                raise RegisteredModelScoringError(
                    "REGISTERED_MODEL_FEATURE_SCHEMA_INVALID"
                ) from exc
        if artifact_schema != CANDIDATE_FEATURE_SCHEMA_VERSION:
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_FEATURE_SCHEMA_MISMATCH | "
                f"artifact={artifact_schema} | "
                f"runtime={CANDIDATE_FEATURE_SCHEMA_VERSION}"
            )
        if (
            self.expected_feature_schema_version is not None
            and artifact_schema != self.expected_feature_schema_version
        ):
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_REGISTRY_SCHEMA_MISMATCH | "
                f"artifact={artifact_schema} | "
                f"registry={self.expected_feature_schema_version}"
            )
        if artifact.get("model_kind") == "LOGISTIC_REGRESSION_BASELINE":
            if "model" not in artifact:
                raise RegisteredModelScoringError(
                    "REGISTERED_BASELINE_MODEL_MISSING"
                )
            return
        if artifact.get("artifact_kind") == "OFFLINE_ENSEMBLE_EXPERIMENT":
            if not isinstance(artifact.get("models"), dict):
                raise RegisteredModelScoringError(
                    "REGISTERED_ENSEMBLE_MODELS_INVALID"
                )
            winner = artifact.get("winner")
            if not isinstance(winner, dict) or winner.get("kind") not in {
                "MODEL",
                "BLEND",
            }:
                raise RegisteredModelScoringError(
                    "REGISTERED_ENSEMBLE_WINNER_INVALID"
                )
            return
        raise RegisteredModelScoringError(
            "REGISTERED_MODEL_ARTIFACT_KIND_UNSUPPORTED"
        )

    def _predict(self, candidate) -> float:
        artifact = self._artifact
        vector = np.asarray(
            [self._vector(artifact, candidate)],
            dtype=float,
        )
        if artifact.get("model_kind") == "LOGISTIC_REGRESSION_BASELINE":
            probability = float(
                artifact["model"].predict_proba(
                    artifact["scaler"].transform(vector)
                )[0][1]
            )
        else:
            probabilities = {}
            for name, model in artifact["models"].items():
                model_matrix = (
                    artifact["scaler"].transform(vector)
                    if name == "LOGISTIC_REGRESSION"
                    else vector
                )
                probabilities[name] = float(
                    model.predict_proba(model_matrix)[0][1]
                )
            winner = artifact["winner"]
            if winner["kind"] == "MODEL":
                probability = probabilities[winner["name"]]
            else:
                weights = winner.get("weights")
                if not isinstance(weights, dict):
                    raise RegisteredModelScoringError(
                        "REGISTERED_MODEL_BLEND_WEIGHTS_INVALID"
                    )
                probability = sum(
                    float(weight) * probabilities[name]
                    for name, weight in weights.items()
                )
        if not math.isfinite(probability):
            raise RegisteredModelScoringError(
                "REGISTERED_MODEL_PROBABILITY_INVALID"
            )
        return min(1.0, max(0.0, probability))

    @staticmethod
    def _vector(artifact: dict, candidate) -> list[float]:
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
