"""Phase 7.3 helpers for trustworthy after-cost learning labels."""

from __future__ import annotations

import math
from typing import Any


PHASE7_COST_EVIDENCE_SCHEMA_VERSION = 1
PHASE7_COMPLETE_COST_BASIS = (
    "FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3"
)


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def cost_breakdown_from_row(row: Any) -> dict:
    if not isinstance(row, dict):
        return {}
    payload = row.get("payload")
    if isinstance(payload, dict):
        breakdown = payload.get("cost_breakdown")
        return breakdown if isinstance(breakdown, dict) else {}
    outcome = row.get("outcome")
    if isinstance(outcome, dict):
        breakdown = outcome.get("cost_breakdown")
        return breakdown if isinstance(breakdown, dict) else {}
    breakdown = row.get("cost_breakdown")
    return breakdown if isinstance(breakdown, dict) else {}


def has_complete_cost_evidence(row: Any) -> bool:
    breakdown = cost_breakdown_from_row(row)
    if breakdown.get("cost_completeness") != PHASE7_COMPLETE_COST_BASIS:
        return False
    for key in ("spread_r", "funding_r", "total_cost_r"):
        if not _finite(breakdown.get(key)):
            return False
    return True
