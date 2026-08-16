"""Phase 7.5D research-only R-ranking challenger experiment.

This module deliberately has no runtime or promotion integration.  It learns a
single fixed Ridge ranking model from execution-eligible virtual outcomes and
evaluates it directly against RULE_SYSTEM_V1 within independent market events.
"""

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
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_FEATURE_SCHEMA_VERSION,
    context_feature_vector,
    is_complete_market_context,
    market_context_from_row,
)
from learning.ensemble_experiment import FEATURE_NAMES


RANKING_ARTIFACT_SCHEMA_VERSION = 1
RANKING_REPORT_SCHEMA_VERSION = 1
RANKING_MODEL_FAMILY = "RANKING_R_V1"
RANKING_TARGET = "EVENT_RELATIVE_NET_R"
RANKING_POPULATION = "EXECUTION_ELIGIBLE_ONLY"
RANKING_CHAMPION_BASELINE = "RULE_SYSTEM_V1"
RANKING_PHASE = "7.5D.1"


class OfflineRankingChallengerExperiment:
    """Train/evaluate a fixed event-relative-R Ridge ranking experiment.

    The experiment is intentionally research-only in Phase 7.5D.1:
    - training population is execution-eligible virtual outcomes only;
    - training target is each candidate's net R minus its event mean net R;
    - validation/test selection is highest predicted relative R per event;
    - comparison baseline is RULE_SYSTEM_V1's highest final_score candidate;
    - no gate, registry update, shadow activation, or paper authority is granted.
    """

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
        min_train_events=20,
        min_eval_events=10,
        ridge_alpha=10.0,
        context_aware=True,
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
        self.min_train_events = int(min_train_events)
        self.min_eval_events = int(min_eval_events)
        self.ridge_alpha = float(ridge_alpha)
        self.context_aware = bool(context_aware)
        self.evaluate_test = bool(evaluate_test)

    def run(self) -> dict:
        issues = Counter()
        paths = {
            "train": self.train_path,
            "validation": self.validation_path,
        }
        if self.evaluate_test:
            if self.test_path is None:
                raise ValueError("RANKING_TEST_PATH_REQUIRED")
            paths["test"] = self.test_path

        rows_by_split = {
            name: list(self._iter_filtered(path, name, issues))
            for name, path in paths.items()
        }
        events_by_split = {
            name: self._group_events(rows)
            for name, rows in rows_by_split.items()
        }

        status = "EXPERIMENT_COMPLETE"
        if (
            len(rows_by_split["train"]) < self.min_train_rows
            or len(rows_by_split["validation"]) < self.min_eval_rows
            or len(events_by_split["train"]) < self.min_train_events
            or len(events_by_split["validation"]) < self.min_eval_events
            or (
                self.evaluate_test
                and (
                    len(rows_by_split["test"]) < self.min_eval_rows
                    or len(events_by_split["test"]) < self.min_eval_events
                )
            )
        ):
            status = "INSUFFICIENT_DATA"

        report = {
            "schema_version": RANKING_REPORT_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "status": status,
            "phase": RANKING_PHASE,
            "model_family": RANKING_MODEL_FAMILY,
            "target_definition": RANKING_TARGET,
            "training_population": RANKING_POPULATION,
            "champion_baseline": RANKING_CHAMPION_BASELINE,
            "outcome_type": self.outcome_type,
            "ridge_alpha": self.ridge_alpha,
            "context_aware": self.context_aware,
            "rows": {
                name: len(rows)
                for name, rows in rows_by_split.items()
            },
            "market_events": {
                name: len(events)
                for name, events in events_by_split.items()
            },
            "issues": dict(sorted(issues.items())),
            "issue_count": int(sum(issues.values())),
            "artifact_path": str(self.artifact_path),
            "research_only": True,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "paper_promotion_allowed": False,
            "promotion_eligible": False,
            "real_order_authority": "NONE",
            "selected_using_test_data": False,
        }
        if status != "EXPERIMENT_COMPLETE":
            self._write_json(self.report_path, report)
            return report

        patterns = tuple(
            sorted({row["pattern"] for row in rows_by_split["train"]})
        )
        vector_columns = self._vector_columns(patterns)
        train_rows, targets = self._training_targets(events_by_split["train"])
        train_matrix = self._matrix(train_rows, patterns)

        model = make_pipeline(
            StandardScaler(),
            Ridge(alpha=self.ridge_alpha),
        )
        model.fit(train_matrix, targets)

        evaluation = {
            "validation": self._evaluate_events(
                events_by_split["validation"], model, patterns
            )
        }
        if self.evaluate_test:
            evaluation["test"] = self._evaluate_events(
                events_by_split["test"], model, patterns
            )

        artifact = {
            "schema_version": RANKING_ARTIFACT_SCHEMA_VERSION,
            "created_at_ms": int(time.time() * 1000),
            "phase": RANKING_PHASE,
            "model_family": RANKING_MODEL_FAMILY,
            "target_definition": RANKING_TARGET,
            "training_population": RANKING_POPULATION,
            "champion_baseline": RANKING_CHAMPION_BASELINE,
            "outcome_type": self.outcome_type,
            "ridge_alpha": self.ridge_alpha,
            "context_aware": self.context_aware,
            "base_feature_names": tuple(FEATURE_NAMES),
            "context_feature_schema_version": (
                CONTEXT_FEATURE_SCHEMA_VERSION if self.context_aware else None
            ),
            "context_feature_names": (
                tuple(CONTEXT_FEATURE_NAMES) if self.context_aware else ()
            ),
            "pattern_categories": patterns,
            "vector_columns": vector_columns,
            "direction_interactions": True,
            "model": model,
            "research_only": True,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "paper_promotion_allowed": False,
            "promotion_eligible": False,
            "real_order_authority": "NONE",
            "selected_using_test_data": False,
        }
        self._write_pickle(self.artifact_path, artifact)

        report.update({
            "evaluation": evaluation,
            "vector_columns": vector_columns,
            "direction_interactions": True,
        })
        self._write_json(self.report_path, report)
        return report

    @staticmethod
    def _group_events(rows: list[dict]) -> list[tuple[str, list[dict]]]:
        grouped = defaultdict(list)
        order = []
        for row in rows:
            event_id = row["market_event_id"]
            if event_id not in grouped:
                order.append(event_id)
            grouped[event_id].append(row)
        return [
            (event_id, grouped[event_id])
            for event_id in order
            if len(grouped[event_id]) >= 2
        ]

    @staticmethod
    def _training_targets(events):
        rows = []
        targets = []
        for _event_id, members in events:
            event_mean = float(np.mean([row["_ranking_target_r"] for row in members]))
            for row in members:
                rows.append(row)
                targets.append(float(row["_ranking_target_r"] - event_mean))
        return rows, np.asarray(targets, dtype=float)

    def _evaluate_events(self, events, model, patterns) -> dict:
        selected_r = []
        rule_r = []
        deltas = []
        same_candidate = 0

        for _event_id, members in events:
            matrix = self._matrix(members, patterns)
            scores = model.predict(matrix)
            ranking = min(
                zip(members, scores),
                key=lambda pair: (
                    -float(pair[1]),
                    str(pair[0].get("symbol") or ""),
                    str(pair[0].get("direction") or ""),
                    str(pair[0].get("candidate_observation_id") or ""),
                ),
            )[0]
            rule = self._rule_choice(members)
            ranking_value = float(ranking["_ranking_target_r"])
            rule_value = float(rule["_ranking_target_r"])
            selected_r.append(ranking_value)
            rule_r.append(rule_value)
            deltas.append(ranking_value - rule_value)
            if (
                str(ranking.get("candidate_observation_id") or "")
                == str(rule.get("candidate_observation_id") or "")
            ):
                same_candidate += 1

        delta = np.asarray(deltas, dtype=float)
        ranking_values = np.asarray(selected_r, dtype=float)
        rule_values = np.asarray(rule_r, dtype=float)
        positive = delta[delta > 1e-12]
        negative = delta[delta < -1e-12]
        return {
            "events": int(len(delta)),
            "ranking_average_r": float(np.mean(ranking_values)),
            "rule_average_r": float(np.mean(rule_values)),
            "paired_average_r_lift": float(np.mean(delta)),
            "ranking_win_rate": float(np.mean(ranking_values > 0.0)),
            "rule_win_rate": float(np.mean(rule_values > 0.0)),
            "ranking_better_events": int(np.sum(delta > 1e-12)),
            "ranking_worse_events": int(np.sum(delta < -1e-12)),
            "ranking_tied_events": int(np.sum(np.abs(delta) <= 1e-12)),
            "same_candidate_selections": int(same_candidate),
            "large_loss_events_le_minus_1r": int(np.sum(delta <= -1.0)),
            "large_gain_events_ge_plus_1r": int(np.sum(delta >= 1.0)),
            "average_gain_when_better_r": (
                float(np.mean(positive)) if len(positive) else None
            ),
            "average_loss_when_worse_r": (
                float(np.mean(negative)) if len(negative) else None
            ),
            "delta_r_p10": float(np.quantile(delta, 0.10)),
            "delta_r_median": float(np.quantile(delta, 0.50)),
            "delta_r_p90": float(np.quantile(delta, 0.90)),
        }

    @staticmethod
    def _rule_choice(members):
        return min(
            members,
            key=lambda row: (
                -float(row.get("final_score", 0.0)),
                str(row.get("symbol") or ""),
                str(row.get("direction") or ""),
                str(row.get("candidate_observation_id") or ""),
            ),
        )

    def _matrix(self, rows, patterns):
        return np.asarray(
            [self._vector(row, patterns) for row in rows],
            dtype=float,
        )

    def _vector(self, row, patterns):
        features = row["features"]
        base = (
            [float(features[name]) for name in FEATURE_NAMES]
            + [
                float(row.get("rule_score", 0.0)),
                float(row.get("final_score", 0.0)),
                1.0 if row["direction"] == "LONG" else 0.0,
            ]
            + [
                1.0 if row["pattern"] == pattern else 0.0
                for pattern in patterns
            ]
        )
        if self.context_aware:
            base += context_feature_vector(market_context_from_row(row))

        # Phase 7.5C.6 showed that direction-conditioned mistakes dominated
        # tail losses.  A signed interaction copy lets the fixed linear model
        # learn that the same structure/context can behave differently LONG
        # versus SHORT without hard-coding a ban on either direction.
        sign = 1.0 if row["direction"] == "LONG" else -1.0
        interaction_source = list(base)
        interactions = [sign * value for value in interaction_source]
        return base + interactions

    def _vector_columns(self, patterns):
        base = (
            tuple(FEATURE_NAMES)
            + ("rule_score", "final_score", "direction_long")
            + tuple(f"pattern::{pattern}" for pattern in patterns)
            + (tuple(CONTEXT_FEATURE_NAMES) if self.context_aware else ())
        )
        return base + tuple(f"direction_x::{name}" for name in base)

    def _iter_filtered(self, path, split, issues):
        path = Path(path)
        if not path.exists():
            issues[f"{split}_file_missing"] += 1
            return
        seen = set()
        with path.open("r") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    issues[f"{split}_malformed_json"] += 1
                    continue
                if not isinstance(row, dict):
                    issues[f"{split}_row_not_object"] += 1
                    continue
                if row.get("outcome_type") != self.outcome_type:
                    continue
                candidate_id = str(row.get("candidate_observation_id") or "").strip()
                if not candidate_id:
                    issues[f"{split}_candidate_id_invalid"] += 1
                    continue
                if candidate_id in seen:
                    issues[f"{split}_candidate_duplicate"] += 1
                    continue
                if row.get("execution_eligible") is not True:
                    issues[f"{split}_execution_ineligible_excluded"] += 1
                    continue
                event_id = str(row.get("market_event_id") or "").strip()
                if not event_id:
                    issues[f"{split}_market_event_id_invalid"] += 1
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
                    values = [float(features[name]) for name in FEATURE_NAMES]
                    values.extend([
                        float(row.get("rule_score", 0.0)),
                        float(row.get("final_score", 0.0)),
                    ])
                    target_r = float(row.get("target_r"))
                except (KeyError, TypeError, ValueError):
                    issues[f"{split}_feature_or_target_invalid"] += 1
                    continue
                if not math.isfinite(target_r) or not all(
                    math.isfinite(value) for value in values
                ):
                    issues[f"{split}_feature_or_target_invalid"] += 1
                    continue
                if self.context_aware and not is_complete_market_context(
                    market_context_from_row(row)
                ):
                    issues[f"{split}_market_context_incomplete"] += 1
                    continue
                normalized = dict(row)
                normalized["market_event_id"] = event_id
                normalized["pattern"] = pattern
                normalized["_ranking_target_r"] = target_r
                seen.add(candidate_id)
                yield normalized

    @staticmethod
    def _write_pickle(path, document):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                pickle.dump(document, handle, protocol=pickle.HIGHEST_PROTOCOL)
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
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
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
