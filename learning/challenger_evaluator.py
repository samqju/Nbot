"""Unified offline evaluation for Phase 5.8 challenger artifacts."""

from __future__ import annotations

import json
import math
import pickle
import time
from pathlib import Path

import numpy as np

from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_FEATURE_SCHEMA_VERSION,
    context_feature_vector,
    is_complete_market_context,
    market_context_from_row,
)
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

REGIME_CONTEXT_DRIFT_FEATURES = frozenset({
    "ctx_btc_change_pct_24h",
    "ctx_market_advancing_fraction",
    "ctx_market_declining_fraction",
    "ctx_market_unchanged_fraction",
    "ctx_market_median_change_pct_24h",
    "ctx_market_median_abs_change_pct_24h",
})
REGIME_CONTEXT_DRIFT_PREFIXES = (
    "ctx_market_regime::",
    "ctx_volatility_regime::",
    "ctx_btc_regime::",
)
DRIFT_SCOPE_MODEL_STABILITY = "MODEL_STABILITY_GATE"
DRIFT_SCOPE_REGIME_CONTEXT = "REGIME_CONTEXT_DIAGNOSTIC"


def drift_scope_for_feature(name: str) -> str:
    """Classify PSI features by whether drift itself should fail the model.

    Broad/BTC/volatility regime descriptors are expected to move when the
    market changes.  They remain measured and reported, but model quality is
    judged by performance across that change instead of rejecting solely
    because the regime descriptor moved.  Candidate features, scores, market
    coverage, spread, and liquidity remain part of the stability PSI gate.
    """
    normalized = str(name or "").strip()
    if normalized in REGIME_CONTEXT_DRIFT_FEATURES:
        return DRIFT_SCOPE_REGIME_CONTEXT
    if any(normalized.startswith(prefix) for prefix in REGIME_CONTEXT_DRIFT_PREFIXES):
        return DRIFT_SCOPE_REGIME_CONTEXT
    return DRIFT_SCOPE_MODEL_STABILITY


class ChallengerEvaluationError(RuntimeError):
    pass


class ChallengerArtifactEvaluator:
    """Evaluate baseline or ensemble artifacts on untouched split files."""

    def __init__(
        self,
        *,
        artifact_path: str,
        validation_path: str,
        test_path: str,
        calibration_bins: int = 10,
        drift_bins: int = 10,
    ):
        self.artifact_path = Path(artifact_path)
        self.validation_path = Path(validation_path)
        self.test_path = Path(test_path)
        self.calibration_bins = int(calibration_bins)
        self.drift_bins = int(drift_bins)
        if not (5 <= self.calibration_bins <= 50):
            raise ValueError("CHALLENGER_CALIBRATION_BINS_INVALID")
        if not (5 <= self.drift_bins <= 50):
            raise ValueError("CHALLENGER_DRIFT_BINS_INVALID")

    def evaluate(self) -> dict:
        artifact = self._load_artifact()
        validation_matrix, validation_labels = self._load_matrix(
            self.validation_path, artifact
        )
        test_matrix, test_labels = self._load_matrix(
            self.test_path, artifact
        )
        base = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "artifact_path": str(self.artifact_path),
            "artifact_kind": self._artifact_kind(artifact),
            "outcome_type": artifact.get("outcome_type"),
            "runtime_activation": "DISABLED",
            "matrix_build_mode": "STREAMING_COMPACT_NUMPY",
            "rows": {
                "validation": int(len(validation_labels)),
                "test": int(len(test_labels)),
            },
        }
        if not len(validation_labels) or not len(test_labels):
            return {
                **base,
                "status": "INSUFFICIENT_DATA",
                "metrics": {},
                "calibration": {},
                "drift": {},
            }

        validation_probabilities = self._predict(
            artifact, validation_matrix
        )
        test_probabilities = self._predict(artifact, test_matrix)
        validation_bins = self._calibration(
            validation_labels, validation_probabilities
        )
        test_bins = self._calibration(test_labels, test_probabilities)
        drift = self._drift(
            artifact, validation_matrix, test_matrix
        )
        drift_summary = self._drift_summary(drift)
        return {
            **base,
            "status": "EVALUATED",
            "metrics": {
                "validation": self._metrics(
                    validation_labels, validation_probabilities
                ),
                "test": self._metrics(
                    test_labels, test_probabilities
                ),
            },
            "calibration": {
                "validation": validation_bins,
                "test": test_bins,
                "validation_max_abs_gap": self._max_abs_gap(
                    validation_bins
                ),
                "test_max_abs_gap": self._max_abs_gap(test_bins),
            },
            "drift": {
                "features": drift,
                **drift_summary,
            },
        }

    def _load_artifact(self) -> dict:
        if not self.artifact_path.exists():
            raise ChallengerEvaluationError(
                "CHALLENGER_ARTIFACT_MISSING"
            )
        try:
            artifact = pickle.loads(self.artifact_path.read_bytes())
        except Exception as exc:
            raise ChallengerEvaluationError(
                f"CHALLENGER_ARTIFACT_LOAD_FAILED | {exc}"
            ) from exc
        if not isinstance(artifact, dict):
            raise ChallengerEvaluationError(
                "CHALLENGER_ARTIFACT_SCHEMA_INVALID"
            )
        if artifact.get("runtime_activation") != "DISABLED":
            raise ChallengerEvaluationError(
                "CHALLENGER_RUNTIME_AUTHORITY_INVALID"
            )
        kind = self._artifact_kind(artifact)
        if kind == "BASELINE":
            required = {
                "base_feature_names",
                "pattern_categories",
                "scaler",
                "model",
                "outcome_type",
            }
        else:
            required = {
                "base_feature_names",
                "pattern_categories",
                "scaler",
                "models",
                "winner",
                "outcome_type",
            }
        if not required.issubset(artifact):
            raise ChallengerEvaluationError(
                "CHALLENGER_ARTIFACT_FIELDS_MISSING"
            )
        if artifact.get("requires_complete_market_context"):
            if int(artifact.get("context_feature_schema_version", 0) or 0) != CONTEXT_FEATURE_SCHEMA_VERSION:
                raise ChallengerEvaluationError(
                    "CHALLENGER_CONTEXT_FEATURE_SCHEMA_INVALID"
                )
            if tuple(artifact.get("context_feature_names") or ()) != CONTEXT_FEATURE_NAMES:
                raise ChallengerEvaluationError(
                    "CHALLENGER_CONTEXT_FEATURE_NAMES_INVALID"
                )
        return artifact

    @staticmethod
    def _artifact_kind(artifact: dict) -> str:
        if artifact.get("artifact_kind") == "OFFLINE_ENSEMBLE_EXPERIMENT":
            return "ENSEMBLE"
        if artifact.get("model_kind") == "LOGISTIC_REGRESSION_BASELINE":
            return "BASELINE"
        raise ChallengerEvaluationError(
            "CHALLENGER_ARTIFACT_KIND_UNSUPPORTED"
        )

    def _load_matrix(self, path: Path, artifact: dict):
        count = sum(1 for _ in self._iter_filtered(path, artifact))
        width = (
            len(artifact["base_feature_names"])
            + 3
            + len(artifact["pattern_categories"])
            + (
                len(artifact.get("context_feature_names") or CONTEXT_FEATURE_NAMES)
                if artifact.get("requires_complete_market_context")
                else 0
            )
        )
        matrix = np.empty((count, width), dtype=float)
        labels = np.empty(count, dtype=int)
        index = 0
        for row in self._iter_filtered(path, artifact):
            if index >= count:
                raise ChallengerEvaluationError(
                    "CHALLENGER_SPLIT_CHANGED_DURING_LOAD"
                )
            matrix[index, :] = self._vector(artifact, row)
            labels[index] = int(row["label_profitable"])
            index += 1
        if index != count:
            raise ChallengerEvaluationError(
                "CHALLENGER_SPLIT_CHANGED_DURING_LOAD"
            )
        return matrix, labels

    def _iter_filtered(self, path: Path, artifact: dict):
        if not path.exists():
            return
        outcome_type = artifact["outcome_type"]
        feature_names = tuple(artifact["base_feature_names"])
        seen = set()
        with path.open("r") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                try:
                    row = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise ChallengerEvaluationError(
                        f"CHALLENGER_SPLIT_JSON_INVALID | path={path}"
                    ) from exc
                if not isinstance(row, dict):
                    continue
                if row.get("outcome_type") != outcome_type:
                    continue
                candidate_id = str(
                    row.get("candidate_observation_id") or ""
                ).strip()
                if not candidate_id or candidate_id in seen:
                    continue
                if row.get("label_profitable") not in {True, False}:
                    continue
                if row.get("direction") not in {"LONG", "SHORT"}:
                    continue
                if not str(row.get("pattern") or "").strip():
                    continue
                features = row.get("features")
                if not isinstance(features, dict):
                    continue
                try:
                    values = [
                        float(features[name])
                        for name in feature_names
                    ]
                    values.extend([
                        float(row.get("rule_score", 0)),
                        float(row.get("final_score", 0)),
                    ])
                except (KeyError, TypeError, ValueError):
                    continue
                if not all(math.isfinite(value) for value in values):
                    continue
                if artifact.get("requires_complete_market_context") and not is_complete_market_context(
                    market_context_from_row(row)
                ):
                    continue
                seen.add(candidate_id)
                yield row

    def _predict(self, artifact: dict, matrix):
        if self._artifact_kind(artifact) == "BASELINE":
            return artifact["model"].predict_proba(
                artifact["scaler"].transform(matrix)
            )[:, 1]

        model_probabilities = {}
        for name, model in artifact["models"].items():
            model_matrix = (
                artifact["scaler"].transform(matrix)
                if name == "LOGISTIC_REGRESSION"
                else matrix
            )
            model_probabilities[name] = model.predict_proba(
                model_matrix
            )[:, 1]
        winner = artifact["winner"]
        if winner.get("kind") == "MODEL":
            probabilities = model_probabilities[winner["name"]]
        elif winner.get("kind") == "BLEND":
            weights = winner.get("weights")
            if not isinstance(weights, dict):
                raise ChallengerEvaluationError(
                    "CHALLENGER_BLEND_WEIGHTS_INVALID"
                )
            probabilities = sum(
                float(weight) * model_probabilities[name]
                for name, weight in weights.items()
            )
        else:
            raise ChallengerEvaluationError(
                "CHALLENGER_WINNER_INVALID"
            )
        return np.asarray(probabilities, dtype=float)

    @staticmethod
    def _vector(artifact: dict, row: dict) -> list[float]:
        features = row["features"]
        vector = (
            [
                float(features[name])
                for name in artifact["base_feature_names"]
            ]
            + [
                float(row.get("rule_score", 0)),
                float(row.get("final_score", 0)),
                1.0 if row["direction"] == "LONG" else 0.0,
            ]
            + [
                1.0 if row["pattern"] == pattern else 0.0
                for pattern in artifact["pattern_categories"]
            ]
        )
        if artifact.get("requires_complete_market_context"):
            vector += context_feature_vector(market_context_from_row(row))
        return vector

    @staticmethod
    def _metrics(labels, probabilities) -> dict:
        predictions = (probabilities >= 0.5).astype(int)
        roc_auc = None
        if len(set(labels.tolist())) == 2:
            roc_auc = float(roc_auc_score(labels, probabilities))
        return {
            "rows": int(len(labels)),
            "positive_rate": float(np.mean(labels)),
            "roc_auc": roc_auc,
            "log_loss": float(
                log_loss(labels, probabilities, labels=[0, 1])
            ),
            "brier_score": float(
                brier_score_loss(labels, probabilities)
            ),
            "accuracy": float(accuracy_score(labels, predictions)),
            "precision": float(
                precision_score(labels, predictions, zero_division=0)
            ),
            "recall": float(
                recall_score(labels, predictions, zero_division=0)
            ),
            "f1": float(f1_score(labels, predictions, zero_division=0)),
        }

    def _calibration(self, labels, probabilities) -> list[dict]:
        edges = np.linspace(0.0, 1.0, self.calibration_bins + 1)
        result = []
        for index in range(self.calibration_bins):
            lower = float(edges[index])
            upper = float(edges[index + 1])
            mask = (
                (probabilities >= lower) & (probabilities <= upper)
                if index == self.calibration_bins - 1
                else (probabilities >= lower) & (probabilities < upper)
            )
            rows = int(np.sum(mask))
            mean_probability = (
                float(np.mean(probabilities[mask])) if rows else None
            )
            observed_rate = float(np.mean(labels[mask])) if rows else None
            result.append(
                {
                    "lower": lower,
                    "upper": upper,
                    "rows": rows,
                    "mean_probability": mean_probability,
                    "observed_rate": observed_rate,
                    "calibration_gap": (
                        mean_probability - observed_rate
                        if rows else None
                    ),
                }
            )
        return result

    @staticmethod
    def _max_abs_gap(rows: list[dict]) -> float:
        return max(
            (
                abs(float(row["calibration_gap"]))
                for row in rows
                if row.get("calibration_gap") is not None
            ),
            default=0.0,
        )

    def _drift(
        self,
        artifact: dict,
        validation_matrix,
        test_matrix,
    ) -> dict:
        base_names = list(artifact["base_feature_names"])
        patterns = tuple(artifact["pattern_categories"])
        index_by_name = {
            name: index for index, name in enumerate(base_names)
        }
        index_by_name["rule_score"] = len(base_names)
        index_by_name["final_score"] = len(base_names) + 1
        if artifact.get("requires_complete_market_context"):
            context_names = tuple(
                artifact.get("context_feature_names")
                or CONTEXT_FEATURE_NAMES
            )
            context_start = len(base_names) + 3 + len(patterns)
            for offset, name in enumerate(context_names):
                index_by_name[name] = context_start + offset
        names = base_names + ["rule_score", "final_score"]
        if artifact.get("requires_complete_market_context"):
            names.extend(
                artifact.get("context_feature_names")
                or CONTEXT_FEATURE_NAMES
            )
        report = {}
        for name in names:
            column = index_by_name[name]
            expected = validation_matrix[:, column]
            actual = test_matrix[:, column]
            psi = self._psi(expected, actual)
            report[name] = {
                "psi": psi,
                "severity": (
                    "HIGH"
                    if psi >= 0.25
                    else "MODERATE"
                    if psi >= 0.10
                    else "LOW"
                ),
                "gate_scope": drift_scope_for_feature(name),
                "validation_mean": float(np.mean(expected)),
                "test_mean": float(np.mean(actual)),
            }
        return report

    @staticmethod
    def _drift_summary(report: dict[str, dict]) -> dict:
        def maximum(scope: str | None = None) -> tuple[str | None, float]:
            candidates = [
                (name, row)
                for name, row in report.items()
                if scope is None or row.get("gate_scope") == scope
            ]
            if not candidates:
                return None, 0.0
            name, row = max(
                candidates,
                key=lambda item: float(item[1]["psi"]),
            )
            return name, float(row["psi"])

        max_name, max_psi = maximum()
        stability_name, stability_psi = maximum(
            DRIFT_SCOPE_MODEL_STABILITY
        )
        regime_name, regime_psi = maximum(
            DRIFT_SCOPE_REGIME_CONTEXT
        )
        return {
            "max_feature_psi": max_psi,
            "max_feature_name": max_name,
            "max_stability_feature_psi": stability_psi,
            "max_stability_feature_name": stability_name,
            "max_regime_context_psi": regime_psi,
            "max_regime_context_feature_name": regime_name,
            "stability_feature_count": sum(
                1
                for row in report.values()
                if row.get("gate_scope") == DRIFT_SCOPE_MODEL_STABILITY
            ),
            "regime_context_feature_count": sum(
                1
                for row in report.values()
                if row.get("gate_scope") == DRIFT_SCOPE_REGIME_CONTEXT
            ),
        }

    def _psi(self, expected, actual) -> float:
        quantiles = np.linspace(0.0, 1.0, self.drift_bins + 1)
        edges = np.unique(np.quantile(expected, quantiles))
        if len(edges) < 3:
            low = min(float(np.min(expected)), float(np.min(actual)))
            high = max(float(np.max(expected)), float(np.max(actual)))
            if high <= low:
                return 0.0
            edges = np.linspace(low, high, self.drift_bins + 1)
        edges[0] = -np.inf
        edges[-1] = np.inf
        expected_counts, _ = np.histogram(expected, bins=edges)
        actual_counts, _ = np.histogram(actual, bins=edges)
        expected_pct = np.maximum(
            expected_counts / max(1, len(expected)), 1e-6
        )
        actual_pct = np.maximum(
            actual_counts / max(1, len(actual)), 1e-6
        )
        return float(
            np.sum(
                (actual_pct - expected_pct)
                * np.log(actual_pct / expected_pct)
            )
        )
