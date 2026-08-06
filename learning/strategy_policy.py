"""Automatic, research-only recommendations from approved strategy variants.

This layer consumes completed Phase 5.6 virtual strategy outcomes and writes an
atomic pattern -> approved variant recommendation. It cannot modify a candidate,
a paper stop, risk sizing, registry authority, or exchange execution.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from strategy.strategy_lab import VirtualStrategyVariant, variants_for_pattern


STRATEGY_POLICY_SCHEMA_VERSION = 1


class StrategyPolicyRecommendationError(RuntimeError):
    pass


class StrategyPolicyRecommender:
    def __init__(
        self,
        *,
        outcomes_path: str,
        recommendation_path: str,
        catalog_version: str,
        approved_catalog: Iterable[VirtualStrategyVariant],
        min_independent_events: int,
        min_average_net_r: float,
    ):
        self.outcomes_path = Path(outcomes_path)
        self.recommendation_path = Path(recommendation_path)
        self.catalog_version = str(catalog_version or "").strip().upper()
        self.catalog = tuple(approved_catalog)
        self.catalog_by_id = {row.variant_id: row for row in self.catalog}
        self.min_independent_events = int(min_independent_events)
        self.min_average_net_r = float(min_average_net_r)
        if not self.catalog_version:
            raise ValueError("STRATEGY_POLICY_CATALOG_VERSION_REQUIRED")
        if not self.catalog or len(self.catalog_by_id) != len(self.catalog):
            raise ValueError("STRATEGY_POLICY_APPROVED_CATALOG_INVALID")
        if self.min_independent_events < 1:
            raise ValueError("STRATEGY_POLICY_MIN_EVENTS_INVALID")

    def refresh(self) -> dict:
        rows, issues = self._load_rows()
        patterns = sorted({row["pattern"] for row in rows})
        recommendations = {
            pattern: self._recommend_pattern(pattern, rows)
            for pattern in patterns
        }
        report = {
            "schema_version": STRATEGY_POLICY_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "status": "READY" if rows else "COLLECT_MORE_DATA",
            "catalog_version": self.catalog_version,
            "approved_variant_ids": sorted(self.catalog_by_id),
            "recommendations": recommendations,
            "input": {
                "outcomes_path": str(self.outcomes_path),
                "eligible_outcomes": len(rows),
                "pattern_count": len(patterns),
            },
            "thresholds": {
                "min_independent_events": self.min_independent_events,
                "min_average_net_r": self.min_average_net_r,
            },
            "activation": "RESEARCH_RECOMMENDATION_ONLY",
            "candidate_selection_authority": "NONE",
            "stop_authority": "NONE",
            "risk_authority": "NONE",
            "paper_authority": "UNCHANGED",
            "rules_benchmark": "PERMANENT",
            "real_order_authority": "NONE",
            "issues": dict(sorted(issues.items())),
            "recommendation_path": str(self.recommendation_path),
        }
        self._atomic_write(report)
        return report

    def _load_rows(self):
        issues = defaultdict(int)
        if not self.outcomes_path.exists():
            issues["outcomes_file_missing"] += 1
            return [], issues
        rows = []
        seen = set()
        with self.outcomes_path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    issues["malformed_json"] += 1
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("outcome_type") or "").upper() not in {
                    "VIRTUAL_TRADE",
                    "VIRTUAL_STRATEGY_VARIANT",
                }:
                    continue
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                if str(
                    payload.get("strategy_lab_catalog_version") or ""
                ).strip().upper() != self.catalog_version:
                    continue
                variant_id = str(
                    row.get("outcome_variant_id")
                    or payload.get("outcome_variant_id")
                    or ""
                ).strip().upper()
                if variant_id not in self.catalog_by_id:
                    issues["unapproved_variant_ignored"] += 1
                    continue
                pattern = str(payload.get("pattern") or "").strip().upper()
                candidate_id = str(
                    row.get("candidate_observation_id") or ""
                ).strip()
                event_id = str(
                    row.get("market_event_id") or candidate_id or ""
                ).strip()
                try:
                    net_r = float(payload.get("net_exit_r"))
                except (TypeError, ValueError):
                    issues["net_exit_r_missing"] += 1
                    continue
                if not pattern or not candidate_id or not event_id or not math.isfinite(net_r):
                    issues["identity_or_value_invalid"] += 1
                    continue
                variant = self.catalog_by_id[variant_id]
                if not variant.applies_to(pattern):
                    issues["variant_pattern_mismatch"] += 1
                    continue
                key = (candidate_id, variant_id)
                if key in seen:
                    issues["duplicate_candidate_variant"] += 1
                    continue
                seen.add(key)
                rows.append({
                    "candidate_observation_id": candidate_id,
                    "market_event_id": event_id,
                    "recorded_at_ms": int(row.get("recorded_at_ms", 0) or 0),
                    "pattern": pattern,
                    "variant_id": variant_id,
                    "net_exit_r": net_r,
                })
        return rows, issues

    def _recommend_pattern(self, pattern: str, rows: list[dict]) -> dict:
        approved = variants_for_pattern(self.catalog, pattern)
        approved_ids = {row.variant_id for row in approved}
        grouped = defaultdict(lambda: defaultdict(list))
        for row in rows:
            if row["pattern"] == pattern and row["variant_id"] in approved_ids:
                grouped[row["variant_id"]][row["market_event_id"]].append(
                    row["net_exit_r"]
                )
        variants = {}
        eligible = []
        baseline = next(row for row in approved if row.baseline)
        for variant in approved:
            event_values = [
                statistics.fmean(values)
                for _, values in sorted(grouped[variant.variant_id].items())
            ]
            average = statistics.fmean(event_values) if event_values else None
            metrics = {
                "independent_market_events": len(event_values),
                "average_net_r": average,
                "positive_event_rate": (
                    sum(value > 0 for value in event_values) / len(event_values)
                    if event_values
                    else None
                ),
                "eligible": (
                    len(event_values) >= self.min_independent_events
                    and average is not None
                    and average >= self.min_average_net_r
                ),
            }
            variants[variant.variant_id] = metrics
            if metrics["eligible"]:
                eligible.append((variant.variant_id, metrics))
        eligible.sort(
            key=lambda item: (
                -float(item[1]["average_net_r"]),
                -int(item[1]["independent_market_events"]),
                item[0],
            )
        )
        selected = eligible[0][0] if eligible else baseline.variant_id
        if selected not in approved_ids:
            raise StrategyPolicyRecommendationError(
                "STRATEGY_POLICY_SELECTED_VARIANT_NOT_APPROVED"
            )
        return {
            "pattern": pattern,
            "selected_variant_id": selected,
            "status": "RECOMMENDED" if eligible else "COLLECT_MORE_DATA",
            "reason": (
                "BEST_APPROVED_AFTER_COST_INDEPENDENT_EXPECTANCY"
                if eligible
                else "APPROVED_BASELINE_RETAINED_PENDING_EVIDENCE"
            ),
            "approved_variant_ids": sorted(approved_ids),
            "variants": variants,
            "activation": "RESEARCH_RECOMMENDATION_ONLY",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
        }

    def _atomic_write(self, document: dict) -> None:
        self.recommendation_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.recommendation_path.name}.",
            suffix=".tmp",
            dir=str(self.recommendation_path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.recommendation_path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
