"""Normalize executed paper evidence for Observation-side governance.

Phase 6A.0 moves execution trade files to the Execution VPS. Observation
governance consumes completed ExecutionOutcome evidence recorded in the
Observation-owned candidate outcomes file. Legacy paper-trade rows remain
accepted so existing tests and historical tools stay backward compatible.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterator

from utils.jsonl_history import iter_jsonl_lines, logical_jsonl_exists


def iter_paper_execution_evidence(path: str | Path) -> Iterator[dict]:
    source = Path(path)
    if not logical_jsonl_exists(source):
        return
    for raw_line in iter_jsonl_lines(source):
            try:
                row = json.loads(raw_line)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            evidence = normalize_paper_execution_evidence(row)
            if evidence is not None:
                yield evidence


def normalize_paper_execution_evidence(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None

    if str(row.get("outcome_type") or "").strip().upper() == "EXECUTED_TRADE":
        return _from_candidate_outcome(row)
    return _from_legacy_paper_trade(row)


def _from_candidate_outcome(row: dict) -> dict | None:
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None

    authority = str(payload.get("selection_authority") or "").strip().upper()
    model_id = str(payload.get("paper_canary_model_id") or "").strip()
    if not model_id and authority in {"PAPER_CANARY", "PAPER_CHAMPION"}:
        model_id = str(payload.get("model_version") or "").strip()

    closed_at_ms = _positive_int(
        payload.get("closed_at_ms", payload.get("closed_timestamp"))
    )
    net_r = _finite_float(payload.get("net_r", payload.get("r_multiple")))
    if closed_at_ms is None or net_r is None:
        return None

    return {
        "trade_id": str(
            payload.get("execution_outcome_id")
            or payload.get("proposal_id")
            or row.get("candidate_observation_id")
            or ""
        ).strip(),
        "closed_at_ms": closed_at_ms,
        "net_r": net_r,
        "selection_authority": authority,
        "paper_canary_model_id": model_id or None,
        "market_event_id": _first_text(
            row.get("market_event_id"), payload.get("market_event_id")
        ),
        "decision_batch_id": _first_text(
            row.get("decision_batch_id"), payload.get("decision_batch_id")
        ),
    }


def _from_legacy_paper_trade(row: dict) -> dict | None:
    closed_at_ms = _positive_int(row.get("closed_at_ms"))
    net_r = _finite_float(row.get("net_r"))
    if closed_at_ms is None or net_r is None:
        return None
    return {
        "trade_id": str(row.get("trade_id") or "").strip(),
        "closed_at_ms": closed_at_ms,
        "net_r": net_r,
        "selection_authority": str(
            row.get("selection_authority") or ""
        ).strip().upper(),
        "paper_canary_model_id": _first_text(
            row.get("paper_canary_model_id")
        ),
        "market_event_id": _first_text(row.get("market_event_id")),
        "decision_batch_id": _first_text(row.get("decision_batch_id")),
    }


def _positive_int(value) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _finite_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _first_text(*values) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None
