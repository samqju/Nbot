"""Phase 7.5D.2 walk-forward validation for the research-only R-ranking learner.

This module deliberately has no registry, promotion, shadow, paper, or execution
integration. It repeatedly trains only on past execution-eligible virtual
outcomes and evaluates the next chronological market-event block directly
against RULE_SYSTEM_V1.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from learning.ranking_challenger import (
    OfflineRankingChallengerExperiment,
    RANKING_CHAMPION_BASELINE,
    RANKING_MODEL_FAMILY,
    RANKING_POPULATION,
    RANKING_TARGET,
)


WALK_FORWARD_REPORT_SCHEMA_VERSION = 1
WALK_FORWARD_PHASE = "7.5D.2"
WALK_FORWARD_POLICY = "EXPANDING_WINDOW_NEXT_EVENT_BLOCK_V1"
DEFAULT_FOLD_COUNT = 5
DEFAULT_INITIAL_TRAIN_FRACTION = 0.50
DEFAULT_MIN_POSITIVE_FOLDS = 5


class OfflineWalkForwardRankingValidator:
    """Require repeated chronological proof before ranking research can advance.

    The validator uses an expanding training window. For every fold:
    - training events are strictly earlier than evaluation events;
    - pattern vocabulary is learned from that fold's training rows only;
    - the fixed Phase-7.5D.1 Ridge model predicts event-relative net R;
    - only execution-eligible candidates participate;
    - the highest predicted candidate is compared with RULE_SYSTEM_V1's
      highest-final_score candidate in the same market event.

    Phase 7.5D.2 is still research-only. A PASS means only that the design is
    stable enough to justify a later fresh/shadow-validation design. It grants
    no challenger, paper, or real-order authority.
    """

    def __init__(
        self,
        *,
        dataset_path,
        report_path,
        outcome_type="VIRTUAL_TRADE",
        fold_count=DEFAULT_FOLD_COUNT,
        initial_train_fraction=DEFAULT_INITIAL_TRAIN_FRACTION,
        min_positive_folds=DEFAULT_MIN_POSITIVE_FOLDS,
        min_train_rows=200,
        min_eval_rows=40,
        min_train_events=20,
        min_eval_events=10,
        ridge_alpha=10.0,
        context_aware=True,
        embargo_seconds=0,
    ):
        self.dataset_path = Path(dataset_path)
        self.report_path = Path(report_path)
        self.outcome_type = str(outcome_type).upper()
        self.fold_count = int(fold_count)
        self.initial_train_fraction = float(initial_train_fraction)
        self.min_positive_folds = int(min_positive_folds)
        self.min_train_rows = int(min_train_rows)
        self.min_eval_rows = int(min_eval_rows)
        self.min_train_events = int(min_train_events)
        self.min_eval_events = int(min_eval_events)
        self.ridge_alpha = float(ridge_alpha)
        self.context_aware = bool(context_aware)
        self.embargo_seconds = int(embargo_seconds)
        self._validate_configuration()

    def run(self) -> dict:
        issues = Counter()
        helper = OfflineRankingChallengerExperiment(
            train_path=self.dataset_path,
            validation_path=self.dataset_path,
            test_path=None,
            artifact_path=self.report_path.with_suffix(".unused.pkl"),
            report_path=self.report_path.with_suffix(".unused.json"),
            outcome_type=self.outcome_type,
            min_train_rows=self.min_train_rows,
            min_eval_rows=self.min_eval_rows,
            min_train_events=self.min_train_events,
            min_eval_events=self.min_eval_events,
            ridge_alpha=self.ridge_alpha,
            context_aware=self.context_aware,
            evaluate_test=False,
        )

        rows = list(helper._iter_filtered(self.dataset_path, "walk_forward", issues))
        events = self._chronological_events(rows, issues)

        report = {
            "schema_version": WALK_FORWARD_REPORT_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "status": "VALIDATION_COMPLETE",
            "phase": WALK_FORWARD_PHASE,
            "validation_policy": WALK_FORWARD_POLICY,
            "model_family": RANKING_MODEL_FAMILY,
            "target_definition": RANKING_TARGET,
            "training_population": RANKING_POPULATION,
            "champion_baseline": RANKING_CHAMPION_BASELINE,
            "outcome_type": self.outcome_type,
            "fold_count": self.fold_count,
            "initial_train_fraction": self.initial_train_fraction,
            "min_positive_folds": self.min_positive_folds,
            "ridge_alpha": self.ridge_alpha,
            "context_aware": self.context_aware,
            "embargo_seconds": self.embargo_seconds,
            "qualified_rows": len(rows),
            "independent_market_events": len(events),
            "issues": dict(sorted(issues.items())),
            "issue_count": int(sum(issues.values())),
            "research_only": True,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "paper_promotion_allowed": False,
            "promotion_eligible": False,
            "real_order_authority": "NONE",
            "selected_using_future_fold_data": False,
        }

        folds = self._fold_boundaries(len(events))
        if not folds:
            report["status"] = "INSUFFICIENT_DATA"
            report["research_readiness"] = "NOT_READY"
            report["checks"] = {
                "enough_walk_forward_folds": {
                    "actual": 0,
                    "required_min": self.fold_count,
                    "passed": False,
                }
            }
            self._write_json(self.report_path, report)
            return report

        fold_reports = []
        for fold_index, (train_end, eval_end) in enumerate(folds, start=1):
            raw_train_events = events[:train_end]
            eval_events = events[train_end:eval_end]
            train_events, purged_events = self._apply_embargo(
                raw_train_events, eval_events
            )
            fold_report = self._run_fold(
                fold_index=fold_index,
                train_events=train_events,
                eval_events=eval_events,
                helper=helper,
            )
            fold_report["raw_train_events"] = len(raw_train_events)
            fold_report["embargo_purged_train_events"] = int(purged_events)
            fold_reports.append(fold_report)

        complete_folds = [
            fold for fold in fold_reports if fold["status"] == "FOLD_COMPLETE"
        ]
        if len(complete_folds) != self.fold_count:
            report["status"] = "INSUFFICIENT_DATA"

        aggregate = self._aggregate(complete_folds)
        checks = self._stability_checks(complete_folds, aggregate)
        passed = bool(checks) and all(check["passed"] for check in checks.values())

        report.update({
            "folds": fold_reports,
            "aggregate": aggregate,
            "checks": checks,
            "research_readiness": (
                "READY_FOR_FRESH_VALIDATION_DESIGN"
                if passed and report["status"] == "VALIDATION_COMPLETE"
                else "NOT_READY"
            ),
            "walk_forward_passed": (
                passed and report["status"] == "VALIDATION_COMPLETE"
            ),
        })
        self._write_json(self.report_path, report)
        return report

    def _run_fold(self, *, fold_index, train_events, eval_events, helper) -> dict:
        train_pairs = [(event_id, members) for _ts, event_id, members in train_events]
        eval_pairs = [(event_id, members) for _ts, event_id, members in eval_events]
        train_rows = [row for _ts, _event_id, members in train_events for row in members]
        eval_rows = [row for _ts, _event_id, members in eval_events for row in members]

        report = {
            "fold": int(fold_index),
            "status": "FOLD_COMPLETE",
            "train_rows": len(train_rows),
            "train_events": len(train_events),
            "eval_rows": len(eval_rows),
            "eval_events": len(eval_events),
            "train_start_ms": self._event_time(train_events[0]) if train_events else None,
            "train_end_ms": self._event_time(train_events[-1]) if train_events else None,
            "eval_start_ms": self._event_time(eval_events[0]) if eval_events else None,
            "eval_end_ms": self._event_time(eval_events[-1]) if eval_events else None,
        }

        if (
            len(train_rows) < self.min_train_rows
            or len(eval_rows) < self.min_eval_rows
            or len(train_events) < self.min_train_events
            or len(eval_events) < self.min_eval_events
        ):
            report["status"] = "INSUFFICIENT_DATA"
            return report

        if report["train_end_ms"] is not None and report["eval_start_ms"] is not None:
            if report["train_end_ms"] >= report["eval_start_ms"]:
                report["status"] = "TIME_ORDER_VIOLATION"
                return report

        patterns = tuple(sorted({row["pattern"] for row in train_rows}))
        fit_rows, targets = helper._training_targets(train_pairs)
        train_matrix = helper._matrix(fit_rows, patterns)

        model = make_pipeline(
            StandardScaler(),
            Ridge(alpha=self.ridge_alpha),
        )
        model.fit(train_matrix, targets)
        evaluation = helper._evaluate_events(eval_pairs, model, patterns)

        report.update({
            "pattern_categories": list(patterns),
            "pattern_category_count": len(patterns),
            "evaluation": evaluation,
        })
        return report

    def _stability_checks(self, complete_folds, aggregate):
        positive_folds = int(aggregate.get("positive_champion_lift_folds", 0))
        fold_count = len(complete_folds)
        weighted_lift = aggregate.get("weighted_paired_average_r_lift")
        large_losses = int(aggregate.get("large_loss_events_le_minus_1r", 0))
        large_gains = int(aggregate.get("large_gain_events_ge_plus_1r", 0))
        return {
            "enough_walk_forward_folds": {
                "actual": fold_count,
                "required_min": self.fold_count,
                "passed": fold_count >= self.fold_count,
            },
            "positive_champion_lift_folds": {
                "actual": positive_folds,
                "required_min": self.min_positive_folds,
                "passed": positive_folds >= self.min_positive_folds,
            },
            "aggregate_champion_lift": {
                "actual": weighted_lift,
                "required_min_exclusive": 0.0,
                "passed": weighted_lift is not None and weighted_lift > 0.0,
            },
            "tail_event_balance": {
                "large_loss_events": large_losses,
                "large_gain_events": large_gains,
                "policy": "LARGE_LOSSES_MUST_NOT_EXCEED_LARGE_GAINS",
                "passed": large_losses <= large_gains,
            },
        }

    @staticmethod
    def _aggregate(folds):
        if not folds:
            return {
                "folds": 0,
                "events": 0,
                "positive_champion_lift_folds": 0,
                "weighted_paired_average_r_lift": None,
            }
        metrics = [fold["evaluation"] for fold in folds]
        total_events = int(sum(metric["events"] for metric in metrics))
        if total_events <= 0:
            weighted_lift = None
            ranking_average = None
            rule_average = None
        else:
            weighted_lift = float(sum(
                metric["paired_average_r_lift"] * metric["events"]
                for metric in metrics
            ) / total_events)
            ranking_average = float(sum(
                metric["ranking_average_r"] * metric["events"]
                for metric in metrics
            ) / total_events)
            rule_average = float(sum(
                metric["rule_average_r"] * metric["events"]
                for metric in metrics
            ) / total_events)
        lifts = [metric["paired_average_r_lift"] for metric in metrics]
        return {
            "folds": len(folds),
            "events": total_events,
            "positive_champion_lift_folds": int(sum(lift > 0.0 for lift in lifts)),
            "negative_or_zero_champion_lift_folds": int(sum(lift <= 0.0 for lift in lifts)),
            "weighted_paired_average_r_lift": weighted_lift,
            "weighted_ranking_average_r": ranking_average,
            "weighted_rule_average_r": rule_average,
            "worst_fold_lift": float(min(lifts)),
            "best_fold_lift": float(max(lifts)),
            "large_loss_events_le_minus_1r": int(sum(
                metric["large_loss_events_le_minus_1r"] for metric in metrics
            )),
            "large_gain_events_ge_plus_1r": int(sum(
                metric["large_gain_events_ge_plus_1r"] for metric in metrics
            )),
            "ranking_better_events": int(sum(
                metric["ranking_better_events"] for metric in metrics
            )),
            "ranking_worse_events": int(sum(
                metric["ranking_worse_events"] for metric in metrics
            )),
            "same_candidate_selections": int(sum(
                metric["same_candidate_selections"] for metric in metrics
            )),
        }

    @staticmethod
    def _chronological_events(rows, issues):
        grouped = defaultdict(list)
        for row in rows:
            event_id = row["market_event_id"]
            grouped[event_id].append(row)

        events = []
        for event_id, members in grouped.items():
            if len(members) < 2:
                continue
            timestamps = []
            for row in members:
                try:
                    timestamp = int(row.get("observed_at_ms") or 0)
                except (TypeError, ValueError):
                    timestamp = 0
                if timestamp <= 0:
                    issues["walk_forward_observed_at_invalid"] += 1
                    timestamps = []
                    break
                timestamps.append(timestamp)
            if not timestamps:
                continue
            events.append((min(timestamps), event_id, members))

        events.sort(key=lambda item: (item[0], item[1]))
        return events

    def _fold_boundaries(self, event_count):
        if event_count <= 0:
            return []
        train_end = int(event_count * self.initial_train_fraction)
        remaining = event_count - train_end
        if train_end <= 0 or remaining < self.fold_count:
            return []

        boundaries = []
        for fold_index in range(self.fold_count):
            start = train_end + int(remaining * fold_index / self.fold_count)
            end = (
                event_count
                if fold_index == self.fold_count - 1
                else train_end + int(remaining * (fold_index + 1) / self.fold_count)
            )
            if end <= start:
                return []
            boundaries.append((start, end))
        return boundaries


    def _apply_embargo(self, train_events, eval_events):
        if not train_events or not eval_events or self.embargo_seconds <= 0:
            return list(train_events), 0
        eval_start_ms = self._event_time(eval_events[0])
        cutoff_ms = eval_start_ms - self.embargo_seconds * 1000
        kept = [
            event for event in train_events
            if self._event_time(event) < cutoff_ms
        ]
        return kept, len(train_events) - len(kept)

    @staticmethod
    def _event_time(event):
        return int(event[0])

    def _validate_configuration(self):
        if self.fold_count < 2:
            raise ValueError("WALK_FORWARD_FOLD_COUNT_MIN_2")
        if not 0.0 < self.initial_train_fraction < 1.0:
            raise ValueError("WALK_FORWARD_INITIAL_TRAIN_FRACTION_INVALID")
        if not 1 <= self.min_positive_folds <= self.fold_count:
            raise ValueError("WALK_FORWARD_MIN_POSITIVE_FOLDS_INVALID")
        if self.ridge_alpha < 0.0 or not math.isfinite(self.ridge_alpha):
            raise ValueError("WALK_FORWARD_RIDGE_ALPHA_INVALID")
        if self.embargo_seconds < 0:
            raise ValueError("WALK_FORWARD_EMBARGO_SECONDS_INVALID")

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
