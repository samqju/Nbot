"""Offline Phase 4.5 model and probability-blend experiments."""

from __future__ import annotations

import json
import math
import os
import pickle
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_FEATURE_SCHEMA_VERSION,
    context_feature_vector,
    is_complete_market_context,
    market_context_from_row,
)


FEATURE_NAMES = (
    "short_range",
    "long_range",
    "trend_score",
    "wick_ratio_recent",
    "body_ratio_recent",
    "range_acceleration",
    "dist_high",
    "dist_low",
    "directional_consistency",
)
ARTIFACT_SCHEMA_VERSION = 1


class OfflineEnsembleExperiment:
    """Compare diverse learners and validation-selected probability blends."""

    MODEL_NAMES = (
        "LOGISTIC_REGRESSION",
        "RANDOM_FOREST",
        "HIST_GRADIENT_BOOSTING",
    )

    def __init__(
        self,
        *,
        train_path,
        validation_path,
        test_path,
        artifact_path,
        report_path,
        outcome_type="VIRTUAL_TRADE",
        min_train_rows=200,
        min_eval_rows=40,
        random_state=42,
        context_aware=False,
        evaluate_test=True,
    ):
        self.train_path = Path(train_path)
        self.validation_path = Path(validation_path)
        self.test_path = Path(test_path) if test_path else None
        self.artifact_path = Path(artifact_path)
        self.report_path = Path(report_path)
        self.outcome_type = str(outcome_type).upper()
        self.min_train_rows = int(min_train_rows)
        self.min_eval_rows = int(min_eval_rows)
        self.random_state = int(random_state)
        self.context_aware = bool(context_aware)
        self.evaluate_test = bool(evaluate_test)

    def run(self):
        issues = Counter()
        raw = {
            "train": self._read(self.train_path, "train", issues),
            "validation": self._read(
                self.validation_path,
                "validation",
                issues,
            ),
        }
        if self.evaluate_test:
            if self.test_path is None:
                raise ValueError("ENSEMBLE_TEST_PATH_REQUIRED")
            raw["test"] = self._read(self.test_path, "test", issues)
        filtered = {
            name: self._filter(rows, name, issues)
            for name, rows in raw.items()
        }

        status = "EXPERIMENT_COMPLETE"
        if (
            len(filtered["train"]) < self.min_train_rows
            or len(filtered["validation"]) < self.min_eval_rows
            or (
                self.evaluate_test
                and len(filtered["test"]) < self.min_eval_rows
            )
        ):
            status = "INSUFFICIENT_DATA"
        elif any(
            len({row["label_profitable"] for row in rows}) < 2
            for rows in filtered.values()
        ):
            status = "INSUFFICIENT_CLASS_DIVERSITY"

        report = {
            "schema_version": 1,
            "generated_at_ms": int(time.time() * 1000),
            "status": status,
            "outcome_type": self.outcome_type,
            "rows": {
                name: len(rows)
                for name, rows in filtered.items()
            },
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
            "artifact_path": str(self.artifact_path),
            "runtime_activation": "DISABLED",
        }
        if status != "EXPERIMENT_COMPLETE":
            self._write_json(self.report_path, report)
            return report

        patterns = tuple(sorted({
            row["pattern"]
            for row in filtered["train"]
        }))
        vector_columns = (
            tuple(FEATURE_NAMES)
            + (
                "rule_score",
                "final_score",
                "direction_long",
            )
            + tuple(f"pattern::{pattern}" for pattern in patterns)
            + (CONTEXT_FEATURE_NAMES if self.context_aware else ())
        )

        matrices = {
            name: np.asarray(
                [self._vector(row, patterns, self.context_aware) for row in rows],
                dtype=float,
            )
            for name, rows in filtered.items()
        }
        labels = {
            name: np.asarray(
                [int(row["label_profitable"]) for row in rows],
                dtype=int,
            )
            for name, rows in filtered.items()
        }

        scaler = StandardScaler()
        scaled = {
            "train": scaler.fit_transform(matrices["train"]),
            "validation": scaler.transform(matrices["validation"]),
        }
        if self.evaluate_test:
            scaled["test"] = scaler.transform(matrices["test"])

        models = self._models()
        probabilities = {"validation": {}}
        if self.evaluate_test:
            probabilities["test"] = {}

        for name, model in models.items():
            if name == "LOGISTIC_REGRESSION":
                model.fit(scaled["train"], labels["train"])
                validation_matrix = scaled["validation"]
                test_matrix = scaled.get("test")
            else:
                model.fit(matrices["train"], labels["train"])
                validation_matrix = matrices["validation"]
                test_matrix = matrices.get("test")

            probabilities["validation"][name] = (
                model.predict_proba(validation_matrix)[:, 1]
            )
            if self.evaluate_test:
                probabilities["test"][name] = (
                    model.predict_proba(test_matrix)[:, 1]
                )

        individual_metrics = {
            split: {
                name: self._metrics(
                    labels[split],
                    probability,
                )
                for name, probability in probabilities[split].items()
            }
            for split in (
                ("validation", "test")
                if self.evaluate_test
                else ("validation",)
            )
        }

        blend_candidates = self._blend_candidates(
            probabilities["validation"]
        )
        blend_validation_metrics = {
            name: self._metrics(
                labels["validation"],
                probability,
            )
            for name, probability in blend_candidates.items()
        }

        candidates = {
            **{
                name: {
                    "kind": "MODEL",
                    "validation_metrics": (
                        individual_metrics["validation"][name]
                    ),
                }
                for name in self.MODEL_NAMES
            },
            **{
                name: {
                    "kind": "BLEND",
                    "validation_metrics": metrics,
                }
                for name, metrics in blend_validation_metrics.items()
            },
        }

        winner_name = min(
            candidates,
            key=lambda name: self._selection_key(
                candidates[name]["validation_metrics"]
            ),
        )
        winner = candidates[winner_name]

        if winner["kind"] == "MODEL":
            winner_definition = {
                "kind": "MODEL",
                "name": winner_name,
            }
            winner_test_probability = (
                probabilities["test"][winner_name]
                if self.evaluate_test
                else None
            )
        else:
            weights = self._parse_blend_name(winner_name)
            winner_definition = {
                "kind": "BLEND",
                "name": winner_name,
                "weights": weights,
            }
            winner_test_probability = (
                sum(
                    weights[model_name]
                    * probabilities["test"][model_name]
                    for model_name in self.MODEL_NAMES
                )
                if self.evaluate_test
                else None
            )

        winner_test_metrics = (
            self._metrics(labels["test"], winner_test_probability)
            if self.evaluate_test
            else None
        )

        artifact = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "artifact_kind": "OFFLINE_ENSEMBLE_EXPERIMENT",
            "created_at_ms": int(time.time() * 1000),
            "outcome_type": self.outcome_type,
            "feature_schema_version": 3,
            "base_feature_names": FEATURE_NAMES,
            "pattern_categories": patterns,
            "vector_columns": vector_columns,
            "scaler": scaler,
            "models": models,
            "winner": winner_definition,
            "selection_basis": (
                "VALIDATION_LOG_LOSS_THEN_BRIER_THEN_ROC_AUC"
            ),
            "validation_metrics": (
                winner["validation_metrics"]
            ),
            "test_metrics": winner_test_metrics,
            "test_evaluated_during_training": self.evaluate_test,
            "training_rows": len(filtered["train"]),
            "runtime_activation": "DISABLED",
            "context_feature_schema_version": (
                CONTEXT_FEATURE_SCHEMA_VERSION if self.context_aware else None
            ),
            "context_feature_names": (
                CONTEXT_FEATURE_NAMES if self.context_aware else ()
            ),
            "requires_complete_market_context": self.context_aware,
        }
        self._write_pickle(self.artifact_path, artifact)

        report.update({
            "pattern_categories": list(patterns),
            "vector_columns": list(vector_columns),
            "individual_metrics": individual_metrics,
            "blend_validation_metrics": blend_validation_metrics,
            "winner": {
                **winner_definition,
                "validation_metrics": (
                    winner["validation_metrics"]
                ),
                "test_metrics": winner_test_metrics,
                "selected_using_test_data": False,
                "test_evaluated_during_training": self.evaluate_test,
                "advisory_only": True,
            },
            "class_balance": {
                split: dict(
                    sorted(
                        Counter(
                            str(value)
                            for value in labels[split].tolist()
                        ).items()
                    )
                )
                for split in labels
            },
        })
        self._write_json(self.report_path, report)
        return report

    def _models(self):
        return {
            "LOGISTIC_REGRESSION": LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                random_state=self.random_state,
            ),
            "RANDOM_FOREST": RandomForestClassifier(
                n_estimators=150,
                max_depth=8,
                min_samples_leaf=4,
                class_weight="balanced_subsample",
                random_state=self.random_state,
                n_jobs=1,
            ),
            "HIST_GRADIENT_BOOSTING": (
                HistGradientBoostingClassifier(
                    max_iter=150,
                    learning_rate=0.05,
                    max_leaf_nodes=15,
                    min_samples_leaf=10,
                    l2_regularization=1.0,
                    random_state=self.random_state,
                )
            ),
        }

    def _blend_candidates(self, validation_probabilities):
        candidates = {}
        for logistic_weight in (0.25, 0.50, 0.75):
            remaining = 1.0 - logistic_weight
            for forest_share in (0.25, 0.50, 0.75):
                forest_weight = remaining * forest_share
                gradient_weight = remaining - forest_weight
                name = (
                    "BLEND|"
                    f"LOGISTIC_REGRESSION={logistic_weight:.4f}|"
                    f"RANDOM_FOREST={forest_weight:.4f}|"
                    f"HIST_GRADIENT_BOOSTING={gradient_weight:.4f}"
                )
                candidates[name] = (
                    logistic_weight
                    * validation_probabilities[
                        "LOGISTIC_REGRESSION"
                    ]
                    + forest_weight
                    * validation_probabilities["RANDOM_FOREST"]
                    + gradient_weight
                    * validation_probabilities[
                        "HIST_GRADIENT_BOOSTING"
                    ]
                )

        equal_name = (
            "BLEND|LOGISTIC_REGRESSION=0.3333|"
            "RANDOM_FOREST=0.3333|"
            "HIST_GRADIENT_BOOSTING=0.3334"
        )
        candidates[equal_name] = (
            0.3333
            * validation_probabilities["LOGISTIC_REGRESSION"]
            + 0.3333
            * validation_probabilities["RANDOM_FOREST"]
            + 0.3334
            * validation_probabilities[
                "HIST_GRADIENT_BOOSTING"
            ]
        )
        return candidates

    @staticmethod
    def _parse_blend_name(name):
        weights = {}
        for component in name.split("|")[1:]:
            model_name, value = component.split("=", 1)
            weights[model_name] = float(value)
        return weights

    @staticmethod
    def _selection_key(metrics):
        roc_auc = metrics["roc_auc"]
        auc_key = -roc_auc if roc_auc is not None else 0.0
        return (
            metrics["log_loss"],
            metrics["brier_score"],
            auc_key,
        )

    @staticmethod
    def _metrics(labels, probabilities):
        predictions = (probabilities >= 0.5).astype(int)
        auc = None
        if len(set(labels.tolist())) == 2:
            auc = float(roc_auc_score(labels, probabilities))
        return {
            "rows": int(len(labels)),
            "roc_auc": auc,
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
        }

    @staticmethod
    def _vector(row, patterns, context_aware=False):
        features = row["features"]
        vector = (
            [float(features[name]) for name in FEATURE_NAMES]
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

    def _filter(self, rows, split, issues):
        filtered = []
        seen = set()
        for row in rows:
            if row.get("outcome_type") != self.outcome_type:
                continue
            candidate_id = str(
                row.get("candidate_observation_id") or ""
            ).strip()
            if not candidate_id:
                issues[f"{split}_candidate_id_invalid"] += 1
                continue
            if candidate_id in seen:
                issues[f"{split}_candidate_duplicate"] += 1
                continue
            if row.get("label_profitable") not in {True, False}:
                issues[f"{split}_label_invalid"] += 1
                continue
            if row.get("direction") not in {"LONG", "SHORT"}:
                issues[f"{split}_direction_invalid"] += 1
                continue
            pattern = str(row.get("pattern") or "").strip()
            if not pattern:
                issues[f"{split}_pattern_invalid"] += 1
                continue
            features = row.get("features")
            if not isinstance(features, dict):
                issues[f"{split}_features_invalid"] += 1
                continue
            try:
                values = [
                    float(features[name])
                    for name in FEATURE_NAMES
                ]
                values.extend([
                    float(row.get("rule_score", 0)),
                    float(row.get("final_score", 0)),
                ])
            except (KeyError, TypeError, ValueError):
                issues[f"{split}_feature_value_invalid"] += 1
                continue
            if not all(math.isfinite(value) for value in values):
                issues[f"{split}_feature_value_invalid"] += 1
                continue
            if self.context_aware and not is_complete_market_context(
                market_context_from_row(row)
            ):
                issues[f"{split}_market_context_incomplete"] += 1
                continue
            seen.add(candidate_id)
            filtered.append(row)
        return filtered

    @staticmethod
    def _read(path, split, issues):
        path = Path(path)
        if not path.exists():
            issues[f"{split}_file_missing"] += 1
            return []
        rows = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                issues[f"{split}_malformed_json"] += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                issues[f"{split}_row_not_object"] += 1
        return rows

    @staticmethod
    def _write_pickle(path, document):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                pickle.dump(
                    document,
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

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
