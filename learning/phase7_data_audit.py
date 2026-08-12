"""Phase 7.0 learning-data completeness audit.

This module is intentionally observational.  It does not alter candidates,
models, promotion state, paper selection, or execution authority.  It answers
one question before Phase 7 learning validation begins: do the stored records
contain the market context needed to make regime-robust claims?
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from strategy.experiment_contract import EXPERIMENT_CONTRACT_VERSION
from utils.jsonl_history import iter_jsonl_lines, logical_jsonl_exists


PHASE7_DATA_AUDIT_SCHEMA_VERSION = 1

# These are genuine Phase-7 learning inputs.  They are distinct from optional
# fields that are correctly null when a feature/authority does not apply.
_REQUIRED_CONTEXT_PATHS = (
    "btc_regime",
    "market_breadth",
    "liquidity.spread_pct",
    "liquidity.quote_volume_usd",
)

# Source-level limitations found at the phase6b-final boundary.  Keeping them
# in the report prevents a green runtime-data count from being mistaken for a
# complete Phase-7 learning foundation.
_SOURCE_GAPS = (
    "VIRTUAL_COST_MODEL_EXCLUDES_SPREAD",
    "VIRTUAL_COST_MODEL_EXCLUDES_FUNDING",
)


class Phase7DataAudit:
    def __init__(self, *, observations_path: str, outcomes_path: str):
        self.observations_path = Path(observations_path)
        self.outcomes_path = Path(outcomes_path)

    def run(self) -> dict:
        observation_issues = Counter()
        outcome_issues = Counter()
        completeness = Counter()
        missing_context = Counter()
        cost_completeness = Counter()
        cost_missing = Counter()

        observation_rows = self._read_rows(
            self.observations_path,
            source="observations",
            issues=observation_issues,
        )
        outcome_rows = self._read_rows(
            self.outcomes_path,
            source="outcomes",
            issues=outcome_issues,
        )

        candidate_rows = 0
        current_contract_candidates = 0
        legacy_candidates = 0

        for row in observation_rows:
            if row.get("observation_type") != "STRATEGY_CANDIDATE":
                continue
            candidate_rows += 1
            version = int(row.get("experiment_contract_version", 0) or 0)
            if version != EXPERIMENT_CONTRACT_VERSION:
                legacy_candidates += 1
                continue
            current_contract_candidates += 1
            context = self._market_context(row)
            completeness[str(context.get("completeness") or "UNKNOWN")] += 1
            for path in _REQUIRED_CONTEXT_PATHS:
                if self._path_value(context, path) is None:
                    missing_context[path] += 1

        candidate_outcomes = 0
        current_contract_outcomes = 0
        for row in outcome_rows:
            if row.get("observation_type") != "CANDIDATE_OUTCOME":
                continue
            candidate_outcomes += 1
            version = int(row.get("experiment_contract_version", 0) or 0)
            if version == EXPERIMENT_CONTRACT_VERSION:
                current_contract_outcomes += 1

            payload = row.get("payload")
            if not isinstance(payload, dict):
                outcome_issues["payload_not_object"] += 1
                continue
            breakdown = payload.get("cost_breakdown")
            if not isinstance(breakdown, dict):
                continue
            cost_completeness[
                str(breakdown.get("cost_completeness") or "UNKNOWN")
            ] += 1
            if breakdown.get("spread_r") is None:
                cost_missing["spread_r"] += 1
            if breakdown.get("funding_r") is None:
                cost_missing["funding_r"] += 1

        required_missing_total = sum(missing_context.values())
        runtime_context_ready = (
            current_contract_candidates > 0 and required_missing_total == 0
        )

        blockers = list(_SOURCE_GAPS)
        if current_contract_candidates == 0:
            blockers.append("NO_CURRENT_CONTRACT_CANDIDATES_TO_AUDIT")
        elif required_missing_total:
            blockers.append("CURRENT_MARKET_CONTEXT_INCOMPLETE")

        return {
            "schema_version": PHASE7_DATA_AUDIT_SCHEMA_VERSION,
            "generated_at_ms": int(time.time() * 1000),
            "phase": "7.0",
            "status": "READY_FOR_PHASE7_MODEL_VALIDATION" if not blockers else "BLOCKED",
            "runtime_context_ready": runtime_context_ready,
            "source_gaps": list(_SOURCE_GAPS),
            "blockers": blockers,
            "observations": {
                "path": str(self.observations_path),
                "rows_read": len(observation_rows),
                "candidate_rows": candidate_rows,
                "current_contract_candidates": current_contract_candidates,
                "legacy_or_other_contract_candidates": legacy_candidates,
                "market_context_completeness": dict(sorted(completeness.items())),
                "missing_required_market_context": dict(sorted(missing_context.items())),
                "issues": dict(sorted(observation_issues.items())),
            },
            "outcomes": {
                "path": str(self.outcomes_path),
                "rows_read": len(outcome_rows),
                "candidate_outcomes": candidate_outcomes,
                "current_contract_outcomes": current_contract_outcomes,
                "cost_completeness": dict(sorted(cost_completeness.items())),
                "missing_cost_components": dict(sorted(cost_missing.items())),
                "issues": dict(sorted(outcome_issues.items())),
            },
            "required_market_context_paths": list(_REQUIRED_CONTEXT_PATHS),
            "interpretation": {
                "nulls_to_fix": (
                    "Learning-relevant market context that can be measured reliably."
                ),
                "nulls_to_keep": (
                    "Fields that are genuinely not applicable, unavailable, or belong to old records."
                ),
            },
        }

    @staticmethod
    def _market_context(row: dict) -> dict:
        direct = row.get("market_context")
        if isinstance(direct, dict):
            return direct
        experiment = row.get("experiment_context")
        if isinstance(experiment, dict):
            nested = experiment.get("market_context")
            if isinstance(nested, dict):
                return nested
        return {}

    @staticmethod
    def _path_value(context: dict, path: str) -> Any:
        value: Any = context
        for token in path.split("."):
            if not isinstance(value, dict) or token not in value:
                return None
            value = value[token]
        return value

    @staticmethod
    def _read_rows(path: Path, *, source: str, issues: Counter) -> list[dict]:
        if not logical_jsonl_exists(path):
            issues[f"{source}_file_missing"] += 1
            return []
        rows = []
        try:
            for raw in iter_jsonl_lines(path):
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    issues[f"{source}_malformed_json"] += 1
                    continue
                if not isinstance(row, dict):
                    issues[f"{source}_row_not_object"] += 1
                    continue
                rows.append(row)
        except OSError:
            issues[f"{source}_read_failed"] += 1
        return rows
