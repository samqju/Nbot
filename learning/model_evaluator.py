"""Offline Phase 4.4 baseline evaluation and calibration."""

from __future__ import annotations

import json
import math
import os
import pickle
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    context_feature_mapping,
    context_feature_vector,
    is_complete_market_context,
    market_context_from_row,
)
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


class ModelEvaluationError(RuntimeError):
    pass


class BaselineModelEvaluator:
    THRESHOLDS = (0.40, 0.50, 0.60, 0.70, 0.80)

    def __init__(
        self,
        *,
        artifact_path,
        validation_path,
        test_path,
        evaluation_report_path,
        calibration_report_path,
        min_subgroup_rows=20,
        calibration_bins=10,
        drift_bins=10,
    ):
        self.artifact_path = Path(artifact_path)
        self.validation_path = Path(validation_path)
        self.test_path = Path(test_path)
        self.evaluation_report_path = Path(evaluation_report_path)
        self.calibration_report_path = Path(calibration_report_path)
        self.min_subgroup_rows = int(min_subgroup_rows)
        self.calibration_bins = int(calibration_bins)
        self.drift_bins = int(drift_bins)

    def evaluate(self):
        artifact = self._load_artifact()
        validation = self._load_rows(self.validation_path, "validation")
        test = self._load_rows(self.test_path, "test")

        validation = self._filter_rows(validation, artifact)
        test = self._filter_rows(test, artifact)

        status = "EVALUATED"
        if not validation or not test:
            status = "INSUFFICIENT_DATA"
            report = self._base_report(artifact, status, validation, test)
            self._write_json(self.evaluation_report_path, report)
            self._write_json(
                self.calibration_report_path,
                {
                    "schema_version": 1,
                    "generated_at_ms": int(time.time() * 1000),
                    "status": status,
                    "runtime_activation": "DISABLED",
                    "validation": [],
                    "test": [],
                },
            )
            return report

        predictions = {
            "validation": self._predict(artifact, validation),
            "test": self._predict(artifact, test),
        }

        metrics = {
            split: self._metrics(*predictions[split])
            for split in ("validation", "test")
        }
        thresholds = {
            split: self._threshold_table(*predictions[split])
            for split in ("validation", "test")
        }
        subgroup_metrics = {
            split: self._subgroups(
                rows,
                *predictions[split],
            )
            for split, rows in (
                ("validation", validation),
                ("test", test),
            )
        }
        top_decile = {
            split: self._top_decile(*predictions[split])
            for split in ("validation", "test")
        }
        drift = self._drift_report(
            artifact,
            validation,
            test,
        )

        report = self._base_report(
            artifact,
            status,
            validation,
            test,
        )
        report.update({
            "metrics": metrics,
            "thresholds": thresholds,
            "subgroups": subgroup_metrics,
            "top_decile": top_decile,
            "drift": drift,
            "recommended_threshold": self._recommend_threshold(
                thresholds["validation"]
            ),
        })

        calibration = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "status": status,
            "runtime_activation": "DISABLED",
            "artifact_path": str(self.artifact_path),
            "bins": self.calibration_bins,
            "validation": self._calibration_bins(
                *predictions["validation"]
            ),
            "test": self._calibration_bins(
                *predictions["test"]
            ),
        }

        self._write_json(self.evaluation_report_path, report)
        self._write_json(self.calibration_report_path, calibration)
        return report

    def _base_report(self, artifact, status, validation, test):
        return {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "status": status,
            "runtime_activation": "DISABLED",
            "artifact": {
                "path": str(self.artifact_path),
                "artifact_schema_version": artifact.get(
                    "artifact_schema_version"
                ),
                "model_kind": artifact.get("model_kind"),
                "outcome_type": artifact.get("outcome_type"),
                "created_at_ms": artifact.get("created_at_ms"),
                "training_rows": artifact.get("training_rows"),
            },
            "rows": {
                "validation": len(validation),
                "test": len(test),
            },
        }

    def _load_artifact(self):
        if not self.artifact_path.exists():
            raise ModelEvaluationError(
                "MODEL_EVALUATION_ARTIFACT_MISSING"
            )
        try:
            artifact = pickle.loads(self.artifact_path.read_bytes())
        except Exception as exc:
            raise ModelEvaluationError(
                f"MODEL_EVALUATION_ARTIFACT_LOAD_FAILED | {exc}"
            ) from exc

        required = {
            "artifact_schema_version",
            "model_kind",
            "outcome_type",
            "base_feature_names",
            "pattern_categories",
            "vector_columns",
            "scaler",
            "model",
            "runtime_activation",
        }
        if not isinstance(artifact, dict) or not required.issubset(
            artifact
        ):
            raise ModelEvaluationError(
                "MODEL_EVALUATION_ARTIFACT_SCHEMA_INVALID"
            )
        if artifact["runtime_activation"] != "DISABLED":
            raise ModelEvaluationError(
                "MODEL_EVALUATION_RUNTIME_FLAG_INVALID"
            )
        return artifact

    @staticmethod
    def _load_rows(path, split):
        path = Path(path)
        if not path.exists():
            return []
        rows = []
        for raw_line in path.read_text().splitlines():
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ModelEvaluationError(
                    f"MODEL_EVALUATION_{split.upper()}_JSON_INVALID"
                ) from exc
            if not isinstance(row, dict):
                raise ModelEvaluationError(
                    f"MODEL_EVALUATION_{split.upper()}_ROW_INVALID"
                )
            rows.append(row)
        return rows

    @staticmethod
    def _filter_rows(rows, artifact):
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
                values = [
                    float(features[name])
                    for name in feature_names
                ]
                values.extend([
                    float(row.get("rule_score", 0)),
                    float(row.get("final_score", 0)),
                ])
                if not all(math.isfinite(value) for value in values):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            if artifact.get("requires_complete_market_context") and not is_complete_market_context(
                market_context_from_row(row)
            ):
                continue
            seen.add(candidate_id)
            filtered.append(row)
        return filtered

    def _predict(self, artifact, rows):
        patterns = tuple(artifact["pattern_categories"])
        feature_names = tuple(artifact["base_feature_names"])
        matrix = np.asarray([
            self._vector(
                row,
                feature_names,
                patterns,
                artifact.get("requires_complete_market_context", False),
            )
            for row in rows
        ], dtype=float)
        labels = np.asarray([
            int(row["label_profitable"])
            for row in rows
        ], dtype=int)
        probabilities = artifact["model"].predict_proba(
            artifact["scaler"].transform(matrix)
        )[:, 1]
        return labels, probabilities

    @staticmethod
    def _vector(row, feature_names, patterns, context_aware=False):
        features = row["features"]
        vector = (
            [float(features[name]) for name in feature_names]
            + [
                float(row.get("rule_score", 0)),
                float(row.get("final_score", 0)),
                1.0 if row["direction"] == "LONG" else 0.0,
            ]
            + [
                1.0 if row["pattern"] == pattern else 0.0
                for pattern in patterns
            ]
        )
        if context_aware:
            vector += context_feature_vector(market_context_from_row(row))
        return vector

    @staticmethod
    def _metrics(labels, probabilities):
        predictions = (probabilities >= 0.5).astype(int)
        roc_auc = None
        if len(set(labels.tolist())) == 2:
            roc_auc = float(roc_auc_score(labels, probabilities))
        matrix = confusion_matrix(
            labels,
            predictions,
            labels=[0, 1],
        )
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
            "accuracy": float(
                accuracy_score(labels, predictions)
            ),
            "precision": float(
                precision_score(
                    labels,
                    predictions,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    labels,
                    predictions,
                    zero_division=0,
                )
            ),
            "f1": float(
                f1_score(
                    labels,
                    predictions,
                    zero_division=0,
                )
            ),
            "confusion_matrix": {
                "tn": int(matrix[0, 0]),
                "fp": int(matrix[0, 1]),
                "fn": int(matrix[1, 0]),
                "tp": int(matrix[1, 1]),
            },
        }

    def _threshold_table(self, labels, probabilities):
        rows = []
        for threshold in self.THRESHOLDS:
            selected = probabilities >= threshold
            count = int(np.sum(selected))
            if count:
                win_rate = float(np.mean(labels[selected]))
                average_probability = float(
                    np.mean(probabilities[selected])
                )
            else:
                win_rate = None
                average_probability = None
            rows.append({
                "threshold": threshold,
                "selected_rows": count,
                "coverage": float(count / len(labels)),
                "win_rate": win_rate,
                "average_probability": average_probability,
            })
        return rows

    def _calibration_bins(self, labels, probabilities):
        edges = np.linspace(0.0, 1.0, self.calibration_bins + 1)
        bins = []
        for index in range(self.calibration_bins):
            lower = float(edges[index])
            upper = float(edges[index + 1])
            if index == self.calibration_bins - 1:
                mask = (
                    (probabilities >= lower)
                    & (probabilities <= upper)
                )
            else:
                mask = (
                    (probabilities >= lower)
                    & (probabilities < upper)
                )
            count = int(np.sum(mask))
            bins.append({
                "lower": lower,
                "upper": upper,
                "rows": count,
                "mean_probability": (
                    float(np.mean(probabilities[mask]))
                    if count else None
                ),
                "observed_rate": (
                    float(np.mean(labels[mask]))
                    if count else None
                ),
                "calibration_gap": (
                    float(
                        np.mean(probabilities[mask])
                        - np.mean(labels[mask])
                    )
                    if count else None
                ),
            })
        return bins

    def _subgroups(self, rows, labels, probabilities):
        result = {
            "pattern": {},
            "direction": {},
        }
        for field in ("pattern", "direction"):
            grouped = defaultdict(list)
            for index, row in enumerate(rows):
                grouped[row[field]].append(index)
            for value, indices in sorted(grouped.items()):
                if len(indices) < self.min_subgroup_rows:
                    result[field][value] = {
                        "status": "INSUFFICIENT_DATA",
                        "rows": len(indices),
                    }
                    continue
                idx = np.asarray(indices, dtype=int)
                result[field][value] = {
                    "status": "EVALUATED",
                    **self._metrics(
                        labels[idx],
                        probabilities[idx],
                    ),
                }
        return result

    @staticmethod
    def _top_decile(labels, probabilities):
        count = max(1, int(math.ceil(len(labels) * 0.10)))
        order = np.argsort(probabilities)[::-1][:count]
        base_rate = float(np.mean(labels))
        top_rate = float(np.mean(labels[order]))
        return {
            "rows": int(count),
            "base_positive_rate": base_rate,
            "top_decile_positive_rate": top_rate,
            "lift": (
                float(top_rate / base_rate)
                if base_rate > 0 else None
            ),
            "minimum_probability": float(
                np.min(probabilities[order])
            ),
        }

    def _drift_report(self, artifact, validation, test):
        feature_names = (
            list(artifact["base_feature_names"])
            + ["rule_score", "final_score"]
        )
        if artifact.get("requires_complete_market_context"):
            feature_names.extend(
                artifact.get("context_feature_names") or CONTEXT_FEATURE_NAMES
            )
        report = {}
        for name in feature_names:
            validation_values = self._column(validation, name)
            test_values = self._column(test, name)
            psi = self._psi(validation_values, test_values)
            report[name] = {
                "psi": psi,
                "severity": (
                    "HIGH" if psi >= 0.25
                    else "MODERATE" if psi >= 0.10
                    else "LOW"
                ),
                "validation_mean": float(
                    np.mean(validation_values)
                ),
                "test_mean": float(np.mean(test_values)),
            }
        return report

    @staticmethod
    def _column(rows, name):
        if name in {"rule_score", "final_score"}:
            return np.asarray([
                float(row.get(name, 0))
                for row in rows
            ], dtype=float)
        if name in CONTEXT_FEATURE_NAMES:
            return np.asarray([
                context_feature_mapping(market_context_from_row(row))[name]
                for row in rows
            ], dtype=float)
        return np.asarray([
            float(row["features"][name])
            for row in rows
        ], dtype=float)

    def _psi(self, expected, actual):
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
            expected_counts / max(1, len(expected)),
            1e-6,
        )
        actual_pct = np.maximum(
            actual_counts / max(1, len(actual)),
            1e-6,
        )
        return float(np.sum(
            (actual_pct - expected_pct)
            * np.log(actual_pct / expected_pct)
        ))

    @staticmethod
    def _recommend_threshold(rows):
        candidates = [
            row for row in rows
            if row["selected_rows"] > 0
            and row["win_rate"] is not None
        ]
        if not candidates:
            return None
        best = max(
            candidates,
            key=lambda row: (
                row["win_rate"],
                row["coverage"],
                -row["threshold"],
            ),
        )
        return {
            "threshold": best["threshold"],
            "validation_win_rate": best["win_rate"],
            "validation_coverage": best["coverage"],
            "advisory_only": True,
        }

    @staticmethod
    def _write_json(path, document):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(
                    document,
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
