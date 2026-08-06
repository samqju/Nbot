"""Unified offline evaluation for Phase 5.8 challenger artifacts."""

from __future__ import annotations

import json
import math
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


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
        validation = self._filter_rows(
            self._read_rows(self.validation_path), artifact
        )
        test = self._filter_rows(
            self._read_rows(self.test_path), artifact
        )
        base = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "artifact_path": str(self.artifact_path),
            "artifact_kind": self._artifact_kind(artifact),
            "outcome_type": artifact.get("outcome_type"),
            "runtime_activation": "DISABLED",
            "rows": {
                "validation": len(validation),
                "test": len(test),
            },
        }
        if not validation or not test:
            return {
                **base,
                "status": "INSUFFICIENT_DATA",
                "metrics": {},
                "calibration": {},
                "drift": {},
            }

        validation_labels, validation_probabilities = self._predict(
            artifact, validation
        )
        test_labels, test_probabilities = self._predict(artifact, test)
        validation_bins = self._calibration(
            validation_labels, validation_probabilities
        )
        test_bins = self._calibration(test_labels, test_probabilities)
        drift = self._drift(artifact, validation, test)
        return {
            **base,
            "status": "EVALUATED",
            "metrics": {
                "validation": self._metrics(
                    validation_labels, validation_probabilities
                ),
                "test": self._metrics(test_labels, test_probabilities),
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
                "max_feature_psi": max(
                    (item["psi"] for item in drift.values()),
                    default=0.0,
                ),
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

    @staticmethod
    def _read_rows(path: Path) -> list[dict]:
        if not path.exists():
            return []
        rows = []
        for raw_line in path.read_text().splitlines():
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ChallengerEvaluationError(
                    f"CHALLENGER_SPLIT_JSON_INVALID | path={path}"
                ) from exc
            if isinstance(row, dict):
                rows.append(row)
        return rows

    @staticmethod
    def _filter_rows(rows: list[dict], artifact: dict) -> list[dict]:
        outcome_type = artifact["outcome_type"]
        feature_names = tuple(artifact["base_feature_names"])
        filtered = []
        seen = set()
        for row in rows:
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
                values = [float(features[name]) for name in feature_names]
                values.extend(
                    [
                        float(row.get("rule_score", 0)),
                        float(row.get("final_score", 0)),
                    ]
                )
            except (KeyError, TypeError, ValueError):
                continue
            if not all(math.isfinite(value) for value in values):
                continue
            seen.add(candidate_id)
            filtered.append(row)
        return filtered

    def _predict(self, artifact: dict, rows: list[dict]):
        matrix = np.asarray(
            [self._vector(artifact, row) for row in rows],
            dtype=float,
        )
        labels = np.asarray(
            [int(row["label_profitable"]) for row in rows],
            dtype=int,
        )
        if self._artifact_kind(artifact) == "BASELINE":
            probabilities = artifact["model"].predict_proba(
                artifact["scaler"].transform(matrix)
            )[:, 1]
            return labels, probabilities

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
        return labels, np.asarray(probabilities, dtype=float)

    @staticmethod
    def _vector(artifact: dict, row: dict) -> list[float]:
        features = row["features"]
        return (
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
        validation: list[dict],
        test: list[dict],
    ) -> dict:
        names = list(artifact["base_feature_names"]) + [
            "rule_score",
            "final_score",
        ]
        report = {}
        for name in names:
            expected = self._column(validation, name)
            actual = self._column(test, name)
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
                "validation_mean": float(np.mean(expected)),
                "test_mean": float(np.mean(actual)),
            }
        return report

    @staticmethod
    def _column(rows: list[dict], name: str):
        if name in {"rule_score", "final_score"}:
            return np.asarray(
                [float(row.get(name, 0)) for row in rows], dtype=float
            )
        return np.asarray(
            [float(row["features"][name]) for row in rows], dtype=float
        )

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
