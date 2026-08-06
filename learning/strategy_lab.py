"""Phase 5.6 strategy-laboratory evaluation.

This evaluator is advisory. It compares approved virtual exit-policy variants
using both raw candidate outcomes and market-event-grouped outcomes so a broad
market move is not counted as hundreds of independent experiments.
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
from typing import Any


STRATEGY_LAB_REPORT_SCHEMA_VERSION = 1
_SUPPORTED_OUTCOME_TYPES = {
    "VIRTUAL_TRADE",
    "VIRTUAL_STRATEGY_VARIANT",
}


class StrategyLabEvaluator:
    def __init__(
        self,
        *,
        outcomes_path: str,
        report_path: str,
        catalog_version: str,
        min_outcomes: int,
        min_market_events: int,
        min_avg_net_r: float,
        max_drawdown_r: float,
    ):
        self.outcomes_path = Path(outcomes_path)
        self.report_path = Path(report_path)
        self.catalog_version = str(catalog_version).strip().upper()
        self.min_outcomes = int(min_outcomes)
        self.min_market_events = int(min_market_events)
        self.min_avg_net_r = float(min_avg_net_r)
        self.max_drawdown_r = float(max_drawdown_r)

    def evaluate(self) -> dict:
        rows, issues = self._load_rows()
        variants: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            variants[row["outcome_variant_id"]].append(row)

        variant_reports = {
            variant_id: self._evaluate_variant(variant_rows)
            for variant_id, variant_rows in sorted(variants.items())
        }
        ranked = sorted(
            variant_reports.items(),
            key=lambda item: (
                -float(item[1]["event_grouped"]["average_net_r"]),
                -float(item[1]["raw"]["average_net_r"]),
                item[0],
            ),
        )
        eligible = [
            (variant_id, report)
            for variant_id, report in ranked
            if report["verdict"] == "SHADOW_ELIGIBLE"
        ]
        report = {
            "schema_version": STRATEGY_LAB_REPORT_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "catalog_version": self.catalog_version,
            "status": "READY" if rows else "EMPTY",
            "runtime_activation": "DISABLED",
            "paper_authority": "UNCHANGED",
            "real_order_authority": "NONE",
            "thresholds": {
                "min_outcomes": self.min_outcomes,
                "min_market_events": self.min_market_events,
                "min_avg_net_r": self.min_avg_net_r,
                "max_drawdown_r": self.max_drawdown_r,
            },
            "input": {
                "outcomes_path": str(self.outcomes_path),
                "eligible_rows": len(rows),
                "variant_count": len(variant_reports),
            },
            "recommended_variant": (
                eligible[0][0] if eligible else None
            ),
            "recommendation": (
                "SHADOW_TEST_RECOMMENDED"
                if eligible else "NO_VARIANT_READY"
            ),
            "variants": variant_reports,
            "ranking": [variant_id for variant_id, _ in ranked],
            "issues": dict(sorted(issues.items())),
        }
        self._write_json_atomic(self.report_path, report)
        return report

    def _load_rows(self) -> tuple[list[dict], defaultdict[str, int]]:
        issues: defaultdict[str, int] = defaultdict(int)
        if not self.outcomes_path.exists():
            issues["outcomes_file_missing"] += 1
            return [], issues

        rows = []
        seen_candidate_variants = set()
        with self.outcomes_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    issues["malformed_json"] += 1
                    continue
                if not isinstance(row, dict):
                    issues["row_not_object"] += 1
                    continue
                outcome_type = str(
                    row.get("outcome_type") or ""
                ).strip().upper()
                if outcome_type not in _SUPPORTED_OUTCOME_TYPES:
                    continue
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    issues["payload_missing"] += 1
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
                if not variant_id:
                    issues["variant_id_missing"] += 1
                    continue
                candidate_id = str(
                    row.get("candidate_observation_id") or ""
                ).strip()
                if not candidate_id:
                    issues["candidate_observation_id_missing"] += 1
                    continue
                if not self._finite(payload.get("net_exit_r")):
                    issues["net_exit_r_missing"] += 1
                    continue
                if not self._finite(payload.get("gross_exit_r")):
                    issues["gross_exit_r_missing"] += 1
                    continue
                dedupe_key = (candidate_id, variant_id)
                if dedupe_key in seen_candidate_variants:
                    issues["duplicate_candidate_variant"] += 1
                    continue
                seen_candidate_variants.add(dedupe_key)
                normalized = {
                    "recorded_at_ms": int(row.get("recorded_at_ms", 0)),
                    "candidate_observation_id": candidate_id,
                    "market_event_id": str(
                        row.get("market_event_id")
                        or row.get("candidate_observation_id")
                        or "UNKNOWN"
                    ),
                    "pattern": str(
                        payload.get("pattern") or "UNKNOWN"
                    ).strip().upper(),
                    "outcome_variant_id": variant_id,
                    "family": str(
                        payload.get("strategy_lab_family") or "UNKNOWN"
                    ).strip().upper(),
                    "gross_exit_r": float(payload["gross_exit_r"]),
                    "net_exit_r": float(payload["net_exit_r"]),
                    "estimated_cost_r": float(
                        payload.get("estimated_cost_r", 0.0) or 0.0
                    ),
                    "profitable": bool(payload.get("profitable", False)),
                    "exit_reason": str(
                        payload.get("exit_reason") or "UNKNOWN"
                    ).strip().upper(),
                }
                rows.append(normalized)
        return rows, issues

    def _evaluate_variant(self, rows: list[dict]) -> dict:
        rows = sorted(
            rows,
            key=lambda row: (
                row["recorded_at_ms"],
                row["candidate_observation_id"],
            ),
        )
        event_groups: dict[str, list[dict]] = defaultdict(list)
        pattern_groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            event_groups[row["market_event_id"]].append(row)
            pattern_groups[row["pattern"]].append(row)

        grouped_rows = []
        for event_id, event_rows in sorted(event_groups.items()):
            grouped_rows.append({
                "market_event_id": event_id,
                "recorded_at_ms": min(
                    row["recorded_at_ms"] for row in event_rows
                ),
                "gross_exit_r": statistics.fmean(
                    row["gross_exit_r"] for row in event_rows
                ),
                "net_exit_r": statistics.fmean(
                    row["net_exit_r"] for row in event_rows
                ),
                "estimated_cost_r": statistics.fmean(
                    row["estimated_cost_r"] for row in event_rows
                ),
            })
        grouped_rows.sort(
            key=lambda row: (row["recorded_at_ms"], row["market_event_id"])
        )

        raw_metrics = self._metrics(rows)
        event_metrics = self._metrics(grouped_rows)
        if len(rows) < self.min_outcomes or len(grouped_rows) < self.min_market_events:
            verdict = "COLLECT_MORE_DATA"
            reason = "MINIMUM_SAMPLE_NOT_REACHED"
        elif (
            raw_metrics["average_net_r"] < self.min_avg_net_r
            or event_metrics["average_net_r"] < self.min_avg_net_r
        ):
            verdict = "REJECT"
            reason = "AFTER_COST_EXPECTANCY_BELOW_GATE"
        elif (
            raw_metrics["max_drawdown_r"] > self.max_drawdown_r
            or event_metrics["max_drawdown_r"] > self.max_drawdown_r
        ):
            verdict = "REJECT"
            reason = "DRAWDOWN_ABOVE_GATE"
        else:
            verdict = "SHADOW_ELIGIBLE"
            reason = "RESEARCH_GATES_PASSED"

        return {
            "family": rows[0]["family"] if rows else "UNKNOWN",
            "verdict": verdict,
            "reason": reason,
            "raw": raw_metrics,
            "event_grouped": event_metrics,
            "unique_candidates": len({
                row["candidate_observation_id"] for row in rows
            }),
            "unique_market_events": len(grouped_rows),
            "patterns": {
                pattern: self._metrics(pattern_rows)
                for pattern, pattern_rows in sorted(pattern_groups.items())
            },
        }

    @staticmethod
    def _metrics(rows: list[dict]) -> dict:
        net_values = [float(row["net_exit_r"]) for row in rows]
        gross_values = [float(row["gross_exit_r"]) for row in rows]
        costs = [float(row.get("estimated_cost_r", 0.0)) for row in rows]
        if not rows:
            return {
                "count": 0,
                "average_gross_r": 0.0,
                "average_net_r": 0.0,
                "median_net_r": 0.0,
                "total_net_r": 0.0,
                "average_cost_r": 0.0,
                "net_win_rate": 0.0,
                "max_drawdown_r": 0.0,
            }
        return {
            "count": len(rows),
            "average_gross_r": statistics.fmean(gross_values),
            "average_net_r": statistics.fmean(net_values),
            "median_net_r": statistics.median(net_values),
            "total_net_r": sum(net_values),
            "average_cost_r": statistics.fmean(costs),
            "net_win_rate": (
                sum(1 for value in net_values if value > 0)
                / len(net_values)
            ),
            "max_drawdown_r": StrategyLabEvaluator._max_drawdown(
                net_values
            ),
        }

    @staticmethod
    def _max_drawdown(values: list[float]) -> float:
        equity = 0.0
        peak = 0.0
        drawdown = 0.0
        for value in values:
            equity += float(value)
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        return drawdown

    @staticmethod
    def _finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

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
