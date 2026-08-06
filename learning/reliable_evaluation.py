"""Phase 5.7 reliable offline strategy evaluation.

The engine evaluates Phase 5.6 virtual strategy variants with chronological
holdouts, label-window purging, embargoes, expanding walk-forward tests,
market-event grouping, and regime diagnostics. It is advisory only and cannot
change paper or real-order authority.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


RELIABLE_EVALUATION_SCHEMA_VERSION = 1
_SUPPORTED_OUTCOME_TYPES = {
    "VIRTUAL_TRADE",
    "VIRTUAL_STRATEGY_VARIANT",
}
_ALL_VERDICTS = (
    "REJECT",
    "COLLECT_MORE_DATA",
    "OFFLINE_VALIDATED",
    "SHADOW_ELIGIBLE",
    "PAPER_CANARY_ELIGIBLE",
    "PAPER_CHAMPION_ELIGIBLE",
)


class ReliableEvaluationError(RuntimeError):
    pass


class ReliableEvaluationEngine:
    """Evaluate virtual strategy variants without granting trade authority."""

    def __init__(
        self,
        *,
        dataset_path: str,
        report_path: str,
        catalog_version: str,
        train_ratio: float,
        validation_ratio: float,
        test_ratio: float,
        embargo_seconds: int,
        walk_forward_folds: int,
        min_outcomes: int,
        min_market_events: int,
        min_holdout_events: int,
        min_regime_events: int,
        min_avg_net_r: float,
        min_positive_fold_ratio: float,
        max_drawdown_r: float,
        liquid_max_spread_pct: float,
        liquid_min_quote_volume_usd: float,
    ):
        self.dataset_path = Path(dataset_path)
        self.report_path = Path(report_path)
        self.catalog_version = str(catalog_version or "").strip().upper()
        self.train_ratio = float(train_ratio)
        self.validation_ratio = float(validation_ratio)
        self.test_ratio = float(test_ratio)
        self.embargo_ms = int(embargo_seconds) * 1000
        self.walk_forward_folds = int(walk_forward_folds)
        self.min_outcomes = int(min_outcomes)
        self.min_market_events = int(min_market_events)
        self.min_holdout_events = int(min_holdout_events)
        self.min_regime_events = int(min_regime_events)
        self.min_avg_net_r = float(min_avg_net_r)
        self.min_positive_fold_ratio = float(min_positive_fold_ratio)
        self.max_drawdown_r = float(max_drawdown_r)
        self.liquid_max_spread_pct = float(liquid_max_spread_pct)
        self.liquid_min_quote_volume_usd = float(
            liquid_min_quote_volume_usd
        )
        self._validate_configuration()

    def evaluate(self) -> dict:
        rows, issues = self._load_rows()
        variants: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            variants[row["outcome_variant_id"]].append(row)

        variant_reports = {
            variant_id: self._evaluate_variant(variant_rows)
            for variant_id, variant_rows in sorted(variants.items())
        }
        ranking = sorted(
            variant_reports,
            key=lambda variant_id: self._ranking_key(
                variant_reports[variant_id],
                variant_id,
            ),
        )
        recommended = next(
            (
                variant_id
                for variant_id in ranking
                if variant_reports[variant_id]["verdict"]
                == "SHADOW_ELIGIBLE"
            ),
            None,
        )
        report = {
            "schema_version": RELIABLE_EVALUATION_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "phase": "5.7",
            "status": "READY" if rows else "EMPTY",
            "subject_type": "VIRTUAL_STRATEGY_VARIANT",
            "catalog_version": self.catalog_version,
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
            "maximum_automatic_verdict": "SHADOW_ELIGIBLE",
            "verdict_definitions": {
                "supported": list(_ALL_VERDICTS),
                "offline_engine_can_issue": [
                    "REJECT",
                    "COLLECT_MORE_DATA",
                    "OFFLINE_VALIDATED",
                    "SHADOW_ELIGIBLE",
                ],
                "reserved_for_later_phases": {
                    "PAPER_CANARY_ELIGIBLE": (
                        "Requires fresh forward shadow evidence and the "
                        "Phase 5.10 promotion controller."
                    ),
                    "PAPER_CHAMPION_ELIGIBLE": (
                        "Requires successful paper-canary operation and "
                        "rollback monitoring."
                    ),
                },
            },
            "configuration": {
                "train_ratio": self.train_ratio,
                "validation_ratio": self.validation_ratio,
                "test_ratio": self.test_ratio,
                "embargo_seconds": self.embargo_ms // 1000,
                "walk_forward_folds": self.walk_forward_folds,
                "min_outcomes": self.min_outcomes,
                "min_market_events": self.min_market_events,
                "min_holdout_events": self.min_holdout_events,
                "min_regime_events": self.min_regime_events,
                "min_avg_net_r": self.min_avg_net_r,
                "min_positive_fold_ratio": (
                    self.min_positive_fold_ratio
                ),
                "max_drawdown_r": self.max_drawdown_r,
                "liquid_max_spread_pct": (
                    self.liquid_max_spread_pct
                ),
                "liquid_min_quote_volume_usd": (
                    self.liquid_min_quote_volume_usd
                ),
            },
            "input": {
                "dataset_path": str(self.dataset_path),
                "eligible_rows": len(rows),
                "variant_count": len(variant_reports),
            },
            "recommended_variant": recommended,
            "recommendation": (
                "BEGIN_FORWARD_SHADOW_VALIDATION"
                if recommended
                else "NO_VARIANT_READY_FOR_SHADOW"
            ),
            "ranking": ranking,
            "variants": variant_reports,
            "issues": dict(sorted(issues.items())),
            "issue_count": sum(issues.values()),
        }
        self._write_json_atomic(self.report_path, report)
        return report

    def _evaluate_variant(self, rows: list[dict]) -> dict:
        rows = sorted(
            rows,
            key=lambda row: (
                row["observed_at_ms"],
                row["recorded_at_ms"],
                row["candidate_observation_id"],
            ),
        )
        events = self._group_market_events(rows)
        fixed_split = self._fixed_chronological_split(events)
        walk_forward = self._walk_forward(events)
        regimes = self._regime_report(rows)

        raw_metrics = self._metrics(rows)
        event_metrics = self._metrics(events)
        validation_metrics = self._metrics(
            fixed_split["splits"]["validation"]
        )
        test_metrics = self._metrics(fixed_split["splits"]["test"])

        verdict, reason_codes, explanations = self._verdict(
            rows=rows,
            events=events,
            fixed_split=fixed_split,
            walk_forward=walk_forward,
            regimes=regimes,
            event_metrics=event_metrics,
            validation_metrics=validation_metrics,
            test_metrics=test_metrics,
        )

        return {
            "family": rows[0].get("family", "UNKNOWN") if rows else "UNKNOWN",
            "verdict": verdict,
            "reason_codes": reason_codes,
            "plain_english": explanations,
            "raw": raw_metrics,
            "market_event_grouped": event_metrics,
            "unique_candidates": len({
                row["candidate_observation_id"] for row in rows
            }),
            "unique_market_events": len(events),
            "fixed_chronological_split": {
                "status": fixed_split["status"],
                "boundaries": fixed_split["boundaries"],
                "purging": fixed_split["purging"],
                "embargo": fixed_split["embargo"],
                "train": self._metrics(fixed_split["splits"]["train"]),
                "validation": validation_metrics,
                "test": test_metrics,
            },
            "walk_forward": walk_forward,
            "regimes": regimes,
            "authority": {
                "runtime_activation": "DISABLED",
                "paper_authority": "UNCHANGED",
                "real_order_authority": "NONE",
                "paper_verdicts_blocked": True,
            },
        }

    def _load_rows(self) -> tuple[list[dict], Counter]:
        issues: Counter = Counter()
        if not self.dataset_path.exists():
            issues["dataset_file_missing"] += 1
            return [], issues

        rows = []
        seen = set()
        try:
            raw_lines = self.dataset_path.read_text().splitlines()
        except OSError as exc:
            raise ReliableEvaluationError(
                f"RELIABLE_EVALUATION_DATASET_READ_FAILED | {exc}"
            ) from exc

        for raw_line in raw_lines:
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError:
                issues["malformed_json"] += 1
                continue
            if not isinstance(row, dict):
                issues["row_not_object"] += 1
                continue
            normalized, reason = self._normalize_row(row)
            if reason:
                issues[reason] += 1
                continue
            if normalized is None:
                continue
            dedupe_key = (
                normalized["candidate_observation_id"],
                normalized["outcome_variant_id"],
            )
            if dedupe_key in seen:
                issues["duplicate_candidate_variant"] += 1
                continue
            seen.add(dedupe_key)
            rows.append(normalized)
        return rows, issues

    def _normalize_row(self, row: dict) -> tuple[dict | None, str | None]:
        outcome_type = str(row.get("outcome_type") or "").strip().upper()
        if outcome_type not in _SUPPORTED_OUTCOME_TYPES:
            return None, None
        catalog = str(
            row.get("strategy_lab_catalog_version") or ""
        ).strip().upper()
        if catalog != self.catalog_version:
            return None, None
        if int(row.get("experiment_contract_version", 0) or 0) <= 0:
            return None, "legacy_contract_excluded"

        candidate_id = str(
            row.get("candidate_observation_id") or ""
        ).strip()
        variant_id = str(
            row.get("outcome_variant_id")
            or (row.get("virtual_policy") or {}).get("variant_id")
            or ""
        ).strip().upper()
        event_id = str(row.get("market_event_id") or "").strip()
        if not candidate_id:
            return None, "candidate_id_missing"
        if not variant_id:
            return None, "variant_id_missing"
        if not event_id:
            return None, "market_event_id_missing"
        if not self._finite(row.get("target_r")):
            return None, "target_r_missing"
        try:
            observed_at_ms = int(row["observed_at_ms"])
            recorded_at_ms = int(row["recorded_at_ms"])
        except (KeyError, TypeError, ValueError):
            return None, "timestamp_invalid"
        if observed_at_ms < 0 or recorded_at_ms < observed_at_ms:
            return None, "label_window_invalid"

        direction = str(row.get("direction") or "").strip().upper()
        pattern = str(row.get("pattern") or "").strip().upper()
        if direction not in {"LONG", "SHORT"}:
            return None, "direction_invalid"
        if not pattern:
            return None, "pattern_missing"
        context = row.get("market_context")
        if context is not None and not isinstance(context, dict):
            return None, "market_context_invalid"
        strategy_lab = row.get("strategy_lab") or {}
        return {
            "candidate_observation_id": candidate_id,
            "outcome_variant_id": variant_id,
            "family": str(
                strategy_lab.get("variant", {}).get("family")
                or (row.get("outcome") or {}).get("strategy_lab_family")
                or "UNKNOWN"
            ).strip().upper(),
            "market_event_id": event_id,
            "observed_at_ms": observed_at_ms,
            "recorded_at_ms": recorded_at_ms,
            "net_exit_r": float(row["target_r"]),
            "direction": direction,
            "pattern": pattern,
            "symbol": str(row.get("symbol") or "").strip().upper(),
            "market_context": context or {},
        }, None

    def _group_market_events(self, rows: Iterable[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row["market_event_id"]].append(row)
        events = []
        for event_id, event_rows in grouped.items():
            events.append({
                "market_event_id": event_id,
                "observed_at_ms": min(
                    row["observed_at_ms"] for row in event_rows
                ),
                "recorded_at_ms": max(
                    row["recorded_at_ms"] for row in event_rows
                ),
                "net_exit_r": statistics.fmean(
                    row["net_exit_r"] for row in event_rows
                ),
                "candidate_count": len(event_rows),
            })
        return sorted(
            events,
            key=lambda row: (
                row["observed_at_ms"],
                row["market_event_id"],
            ),
        )

    def _fixed_chronological_split(self, events: list[dict]) -> dict:
        empty = {
            "status": "INSUFFICIENT_DATA",
            "boundaries": {
                "validation_start_ms": None,
                "test_start_ms": None,
            },
            "purging": {"events_excluded": 0},
            "embargo": {"events_excluded": 0},
            "splits": {"train": [], "validation": [], "test": []},
        }
        if len(events) < 3:
            return empty

        train_count = max(1, int(len(events) * self.train_ratio))
        validation_count = max(
            1,
            int(len(events) * self.validation_ratio),
        )
        if train_count + validation_count >= len(events):
            validation_count = max(1, len(events) - train_count - 1)
        if train_count + validation_count >= len(events):
            train_count = max(1, len(events) - validation_count - 1)
        if min(train_count, validation_count) < 1:
            return empty

        test_start_index = train_count + validation_count
        raw_train = events[:train_count]
        raw_validation = events[train_count:test_start_index]
        raw_test = events[test_start_index:]
        if not raw_validation or not raw_test:
            return empty

        validation_start = raw_validation[0]["observed_at_ms"]
        test_start = raw_test[0]["observed_at_ms"]
        train, validation, test = [], [], []
        purged, embargoed = [], []

        for event in raw_train:
            if event["recorded_at_ms"] >= validation_start:
                purged.append(event)
            elif event["observed_at_ms"] >= validation_start - self.embargo_ms:
                embargoed.append(event)
            else:
                train.append(event)
        for event in raw_validation:
            if event["recorded_at_ms"] >= test_start:
                purged.append(event)
            elif (
                event["observed_at_ms"] < validation_start + self.embargo_ms
                or event["observed_at_ms"] >= test_start - self.embargo_ms
            ):
                embargoed.append(event)
            else:
                validation.append(event)
        for event in raw_test:
            if event["observed_at_ms"] < test_start + self.embargo_ms:
                embargoed.append(event)
            else:
                test.append(event)

        status = "READY"
        if not train or not validation or not test:
            status = "INSUFFICIENT_AFTER_PURGE_EMBARGO"
        return {
            "status": status,
            "boundaries": {
                "validation_start_ms": validation_start,
                "test_start_ms": test_start,
            },
            "purging": {
                "policy": "LABEL_WINDOW_MUST_END_BEFORE_NEXT_SPLIT",
                "events_excluded": len(purged),
            },
            "embargo": {
                "milliseconds": self.embargo_ms,
                "events_excluded": len(embargoed),
            },
            "splits": {
                "train": train,
                "validation": validation,
                "test": test,
            },
        }

    def _walk_forward(self, events: list[dict]) -> dict:
        minimum_train = max(
            2,
            min(
                self.min_market_events,
                max(2, len(events) // 2),
            ),
        )
        available = len(events) - minimum_train
        possible_folds = (
            available // max(1, self.min_holdout_events)
        )
        fold_count = min(self.walk_forward_folds, possible_folds)
        if fold_count < 1:
            return {
                "status": "INSUFFICIENT_DATA",
                "requested_folds": self.walk_forward_folds,
                "completed_folds": 0,
                "positive_test_folds": 0,
                "positive_test_fold_ratio": 0.0,
                "folds": [],
            }

        test_size = available // fold_count
        folds = []
        for index in range(fold_count):
            test_start_index = minimum_train + index * test_size
            test_end_index = (
                len(events)
                if index == fold_count - 1
                else test_start_index + test_size
            )
            raw_train = events[:test_start_index]
            raw_test = events[test_start_index:test_end_index]
            if not raw_test:
                continue
            boundary = raw_test[0]["observed_at_ms"]
            train = [
                event for event in raw_train
                if event["recorded_at_ms"] < boundary
                and event["observed_at_ms"] < boundary - self.embargo_ms
            ]
            test = [
                event for event in raw_test
                if event["observed_at_ms"] >= boundary + self.embargo_ms
            ]
            purged_count = sum(
                1 for event in raw_train
                if event["recorded_at_ms"] >= boundary
            )
            embargoed_count = (
                len(raw_train) + len(raw_test)
                - len(train) - len(test) - purged_count
            )
            folds.append({
                "fold": index + 1,
                "train_start_ms": (
                    train[0]["observed_at_ms"] if train else None
                ),
                "train_end_ms": (
                    train[-1]["observed_at_ms"] if train else None
                ),
                "test_start_ms": (
                    test[0]["observed_at_ms"] if test else None
                ),
                "test_end_ms": (
                    test[-1]["observed_at_ms"] if test else None
                ),
                "purged_train_events": purged_count,
                "embargoed_events": max(0, embargoed_count),
                "train": self._metrics(train),
                "test": self._metrics(test),
                "chronological": bool(
                    train and test
                    and train[-1]["recorded_at_ms"]
                    < test[0]["observed_at_ms"]
                ),
            })

        valid_folds = [
            fold for fold in folds
            if fold["train"]["count"] > 0
            and fold["test"]["count"] > 0
            and fold["chronological"]
        ]
        positive = sum(
            1 for fold in valid_folds
            if fold["test"]["average_net_r"] > 0
        )
        return {
            "status": "READY" if valid_folds else "INSUFFICIENT_DATA",
            "requested_folds": self.walk_forward_folds,
            "completed_folds": len(valid_folds),
            "positive_test_folds": positive,
            "positive_test_fold_ratio": (
                positive / len(valid_folds) if valid_folds else 0.0
            ),
            "average_test_net_r": (
                statistics.fmean(
                    fold["test"]["average_net_r"]
                    for fold in valid_folds
                )
                if valid_folds else 0.0
            ),
            "folds": folds,
        }

    def _regime_report(self, rows: list[dict]) -> dict:
        dimensions = {
            "market_direction": defaultdict(list),
            "volatility": defaultdict(list),
            "trade_direction": defaultdict(list),
            "btc_regime": defaultdict(list),
            "liquidity": defaultdict(list),
            "pattern": defaultdict(list),
        }
        for row in rows:
            market_context = row.get("market_context") or {}
            dimensions["market_direction"][
                self._market_direction(market_context)
            ].append(row)
            dimensions["volatility"][
                self._volatility_regime(market_context)
            ].append(row)
            dimensions["trade_direction"][row["direction"]].append(row)
            dimensions["btc_regime"][
                self._normalized_text(market_context.get("btc_regime"))
            ].append(row)
            dimensions["liquidity"][
                self._liquidity_regime(market_context)
            ].append(row)
            dimensions["pattern"][row["pattern"]].append(row)

        report = {}
        for dimension, groups in dimensions.items():
            values = {}
            known_event_count = 0
            for name, group_rows in sorted(groups.items()):
                event_rows = self._group_market_events(group_rows)
                if name != "UNKNOWN":
                    known_event_count += len(event_rows)
                values[name] = {
                    **self._metrics(event_rows),
                    "eligible_for_stability_gate": (
                        name != "UNKNOWN"
                        and len(event_rows) >= self.min_regime_events
                    ),
                }
            report[dimension] = {
                "status": (
                    "AVAILABLE" if known_event_count else "NOT_AVAILABLE"
                ),
                "known_market_events": known_event_count,
                "groups": values,
            }
        return report

    def _verdict(
        self,
        *,
        rows,
        events,
        fixed_split,
        walk_forward,
        regimes,
        event_metrics,
        validation_metrics,
        test_metrics,
    ) -> tuple[str, list[str], list[str]]:
        reasons = []
        explanations = []

        if len(rows) < self.min_outcomes:
            reasons.append("MINIMUM_OUTCOME_SAMPLE_NOT_REACHED")
            explanations.append(
                f"Only {len(rows)} outcomes are available; at least "
                f"{self.min_outcomes} are required."
            )
        if len(events) < self.min_market_events:
            reasons.append("MINIMUM_INDEPENDENT_EVENT_SAMPLE_NOT_REACHED")
            explanations.append(
                f"Only {len(events)} independent market events are "
                f"available; at least {self.min_market_events} are required."
            )
        if reasons:
            return "COLLECT_MORE_DATA", reasons, explanations

        if fixed_split["status"] != "READY":
            return (
                "COLLECT_MORE_DATA",
                ["CHRONOLOGICAL_SPLIT_INSUFFICIENT_AFTER_PURGE_EMBARGO"],
                [
                    "Too few clean train, validation, or test events remain "
                    "after removing overlapping labels and boundary events."
                ],
            )
        if test_metrics["count"] < self.min_holdout_events:
            return (
                "COLLECT_MORE_DATA",
                ["UNTOUCHED_TEST_SAMPLE_NOT_REACHED"],
                [
                    f"The untouched test period has {test_metrics['count']} "
                    f"events; at least {self.min_holdout_events} are required."
                ],
            )

        rejection_reasons = []
        if event_metrics["average_net_r"] <= 0:
            rejection_reasons.append("FULL_SAMPLE_EXPECTANCY_NON_POSITIVE")
        if validation_metrics["average_net_r"] <= 0:
            rejection_reasons.append("VALIDATION_EXPECTANCY_NON_POSITIVE")
        if test_metrics["average_net_r"] <= 0:
            rejection_reasons.append("UNTOUCHED_TEST_EXPECTANCY_NON_POSITIVE")
        if max(
            event_metrics["max_drawdown_r"],
            test_metrics["max_drawdown_r"],
        ) > self.max_drawdown_r:
            rejection_reasons.append("DRAWDOWN_ABOVE_GATE")
        if (
            walk_forward["completed_folds"] > 0
            and walk_forward["positive_test_fold_ratio"] < 0.5
        ):
            rejection_reasons.append("WALK_FORWARD_MOSTLY_NEGATIVE")
        if rejection_reasons:
            explanations = [
                self._reason_text(reason) for reason in rejection_reasons
            ]
            return "REJECT", rejection_reasons, explanations

        robust_reasons = []
        if event_metrics["average_net_r"] < self.min_avg_net_r:
            robust_reasons.append("FULL_SAMPLE_EXPECTANCY_BELOW_SHADOW_GATE")
        if validation_metrics["average_net_r"] < self.min_avg_net_r:
            robust_reasons.append("VALIDATION_EXPECTANCY_BELOW_SHADOW_GATE")
        if test_metrics["average_net_r"] < self.min_avg_net_r:
            robust_reasons.append("UNTOUCHED_TEST_EXPECTANCY_BELOW_SHADOW_GATE")
        if walk_forward["completed_folds"] < self.walk_forward_folds:
            robust_reasons.append("WALK_FORWARD_FOLD_COVERAGE_INCOMPLETE")
        elif (
            walk_forward["positive_test_fold_ratio"]
            < self.min_positive_fold_ratio
        ):
            robust_reasons.append("WALK_FORWARD_STABILITY_BELOW_GATE")

        covered_regimes = sum(
            1
            for dimension in (
                "market_direction",
                "volatility",
                "trade_direction",
                "pattern",
            )
            for group in regimes[dimension]["groups"].values()
            if group["eligible_for_stability_gate"]
        )
        if covered_regimes < 2:
            robust_reasons.append("REGIME_COVERAGE_INSUFFICIENT")

        if robust_reasons:
            return (
                "OFFLINE_VALIDATED",
                robust_reasons,
                [self._reason_text(reason) for reason in robust_reasons]
                + [
                    "The variant is positive out of sample, but it has not "
                    "yet passed every robustness gate needed for shadow use."
                ],
            )

        return (
            "SHADOW_ELIGIBLE",
            ["ALL_RELIABLE_OFFLINE_GATES_PASSED"],
            [
                "The variant remained profitable after costs in validation, "
                "the untouched test period, and the required walk-forward "
                "folds.",
                "This verdict permits forward shadow comparison only; it "
                "does not permit paper or real-order activation.",
            ],
        )

    @staticmethod
    def _reason_text(reason: str) -> str:
        messages = {
            "FULL_SAMPLE_EXPECTANCY_NON_POSITIVE": (
                "Average after-cost expectancy is not positive across the "
                "independent market-event sample."
            ),
            "VALIDATION_EXPECTANCY_NON_POSITIVE": (
                "The later validation period has non-positive expectancy."
            ),
            "UNTOUCHED_TEST_EXPECTANCY_NON_POSITIVE": (
                "The newest untouched test period has non-positive expectancy."
            ),
            "DRAWDOWN_ABOVE_GATE": (
                "Observed drawdown exceeds the configured safety gate."
            ),
            "WALK_FORWARD_MOSTLY_NEGATIVE": (
                "Most completed forward test windows were negative."
            ),
            "FULL_SAMPLE_EXPECTANCY_BELOW_SHADOW_GATE": (
                "Overall event-grouped expectancy is positive but below the "
                "minimum shadow gate."
            ),
            "VALIDATION_EXPECTANCY_BELOW_SHADOW_GATE": (
                "Validation expectancy is positive but below the minimum "
                "shadow gate."
            ),
            "UNTOUCHED_TEST_EXPECTANCY_BELOW_SHADOW_GATE": (
                "Untouched test expectancy is positive but below the minimum "
                "shadow gate."
            ),
            "WALK_FORWARD_FOLD_COVERAGE_INCOMPLETE": (
                "Not all requested expanding walk-forward folds could be "
                "completed with clean samples."
            ),
            "WALK_FORWARD_STABILITY_BELOW_GATE": (
                "Too few walk-forward test windows were profitable."
            ),
            "REGIME_COVERAGE_INSUFFICIENT": (
                "Too few market-condition groups contain enough independent "
                "events for a stability decision."
            ),
        }
        return messages.get(reason, reason.replace("_", " ").title())

    @staticmethod
    def _metrics(rows: list[dict]) -> dict:
        if not rows:
            return {
                "count": 0,
                "average_net_r": 0.0,
                "median_net_r": 0.0,
                "total_net_r": 0.0,
                "win_rate": 0.0,
                "max_drawdown_r": 0.0,
                "first_observed_at_ms": None,
                "last_observed_at_ms": None,
                "last_recorded_at_ms": None,
            }
        values = [float(row["net_exit_r"]) for row in rows]
        return {
            "count": len(rows),
            "average_net_r": statistics.fmean(values),
            "median_net_r": statistics.median(values),
            "total_net_r": sum(values),
            "win_rate": sum(value > 0 for value in values) / len(values),
            "max_drawdown_r": ReliableEvaluationEngine._max_drawdown(values),
            "first_observed_at_ms": min(
                row["observed_at_ms"] for row in rows
            ),
            "last_observed_at_ms": max(
                row["observed_at_ms"] for row in rows
            ),
            "last_recorded_at_ms": max(
                row["recorded_at_ms"] for row in rows
            ),
        }

    @staticmethod
    def _max_drawdown(values: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        maximum = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            maximum = max(maximum, peak - equity)
        return maximum

    @staticmethod
    def _market_direction(context: dict) -> str:
        text = " ".join(
            str(context.get(key) or "").strip().upper()
            for key in ("market_regime", "trend_regime")
        )
        if any(token in text for token in ("BULL", "UP", "RISING")):
            return "BULLISH"
        if any(token in text for token in ("BEAR", "DOWN", "FALLING")):
            return "BEARISH"
        if any(
            token in text
            for token in ("SIDEWAYS", "RANGE", "FLAT", "NEUTRAL")
        ):
            return "SIDEWAYS"
        return "UNKNOWN"

    @staticmethod
    def _volatility_regime(context: dict) -> str:
        text = str(context.get("volatility_regime") or "").strip().upper()
        if any(token in text for token in ("HIGH", "EXPANDED", "EXPANSION")):
            return "HIGH"
        if any(token in text for token in ("LOW", "COMPRESSED", "COMPRESSION")):
            return "LOW"
        if text:
            return "NORMAL"
        return "UNKNOWN"

    def _liquidity_regime(self, context: dict) -> str:
        liquidity = context.get("liquidity")
        if not isinstance(liquidity, dict):
            return "UNKNOWN"
        spread = liquidity.get("spread_pct")
        volume = liquidity.get("quote_volume_usd")
        if not self._finite(spread) or not self._finite(volume):
            return "UNKNOWN"
        if (
            float(spread) <= self.liquid_max_spread_pct
            and float(volume) >= self.liquid_min_quote_volume_usd
        ):
            return "LIQUID"
        return "LESS_LIQUID"

    @staticmethod
    def _normalized_text(value: Any) -> str:
        text = str(value or "").strip().upper()
        return text or "UNKNOWN"

    @staticmethod
    def _finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    def _validate_configuration(self) -> None:
        ratios = (
            self.train_ratio,
            self.validation_ratio,
            self.test_ratio,
        )
        if any(ratio <= 0 or ratio >= 1 for ratio in ratios):
            raise ValueError("RELIABLE_EVALUATION_RATIO_INVALID")
        if abs(sum(ratios) - 1.0) > 1e-9:
            raise ValueError("RELIABLE_EVALUATION_RATIO_SUM_INVALID")
        if not self.catalog_version:
            raise ValueError("RELIABLE_EVALUATION_CATALOG_INVALID")
        if self.embargo_ms < 0:
            raise ValueError("RELIABLE_EVALUATION_EMBARGO_INVALID")
        if self.walk_forward_folds < 1:
            raise ValueError("RELIABLE_EVALUATION_FOLDS_INVALID")
        if min(
            self.min_outcomes,
            self.min_market_events,
            self.min_holdout_events,
            self.min_regime_events,
        ) < 1:
            raise ValueError("RELIABLE_EVALUATION_SAMPLE_GATE_INVALID")
        if not (0 <= self.min_positive_fold_ratio <= 1):
            raise ValueError("RELIABLE_EVALUATION_FOLD_RATIO_INVALID")
        if self.max_drawdown_r <= 0:
            raise ValueError("RELIABLE_EVALUATION_DRAWDOWN_INVALID")
        if self.liquid_max_spread_pct <= 0:
            raise ValueError("RELIABLE_EVALUATION_SPREAD_INVALID")
        if self.liquid_min_quote_volume_usd <= 0:
            raise ValueError("RELIABLE_EVALUATION_VOLUME_INVALID")

    @staticmethod
    def _ranking_key(report: dict, variant_id: str) -> tuple:
        verdict_order = {
            "SHADOW_ELIGIBLE": 0,
            "OFFLINE_VALIDATED": 1,
            "COLLECT_MORE_DATA": 2,
            "REJECT": 3,
        }
        test = report["fixed_chronological_split"]["test"]
        walk = report["walk_forward"]
        return (
            verdict_order.get(report["verdict"], 99),
            -float(test["average_net_r"]),
            -float(walk.get("average_test_net_r", 0.0)),
            variant_id,
        )

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
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
