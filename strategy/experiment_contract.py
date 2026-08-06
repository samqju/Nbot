"""Versioned experiment metadata shared by learning and paper execution.

Phase 5.5 does not change candidate ranking or trade authority. It gives every
new experiment enough identity and context to be reproduced, joined, compared,
and safely migrated by later automatic-learning phases.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import Any

from strategy.features import CANDIDATE_FEATURE_SCHEMA_VERSION


EXPERIMENT_CONTRACT_VERSION = 1
MARKET_CONTEXT_SCHEMA_VERSION = 1
COST_MODEL_SCHEMA_VERSION = 1
POLICY_SCHEMA_VERSION = 1
CANDLE_INTERVAL = "5m"

_REQUIRED_CONTEXT_KEYS = {
    "contract_version",
    "decision_batch_id",
    "market_event_id",
    "strategy_version",
    "strategy_variant_id",
    "selection_model_version",
    "feature_schema_version",
    "environment",
    "execution_mode",
    "candle_interval",
    "candle_bucket",
    "market_context",
    "cost_model",
    "virtual_policy",
    "paper_policy",
}


def new_decision_batch_id() -> str:
    """Return one opaque ID shared by all candidates in one decision batch."""
    return uuid.uuid4().hex


def build_market_event_id(
    *,
    environment: str,
    candle_bucket: int,
    candle_interval: str = CANDLE_INTERVAL,
) -> str:
    """Group same-interval candidates into one broad market event."""
    source = (
        f"{str(environment).strip().upper()}|"
        f"{str(candle_interval).strip().lower()}|"
        f"{int(candle_bucket)}"
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]
    return f"market-{digest}"


def build_model_version_from_bytes(data: bytes) -> str:
    """Create a stable model identity without exposing artifact contents."""
    digest = hashlib.sha256(bytes(data)).hexdigest()[:16]
    return f"sha256:{digest}"


def build_market_context(structure_fingerprint: Any) -> dict:
    """Normalize currently available context and explicitly mark gaps.

    BTC regime, market breadth, quote volume, and spread are not available at
    candidate-generation time in Phase 5.5. They are represented as null rather
    than invented. Later feature phases may populate them without changing the
    surrounding contract.
    """
    structure = (
        copy.deepcopy(dict(structure_fingerprint))
        if isinstance(structure_fingerprint, Mapping)
        else None
    )
    return {
        "schema_version": MARKET_CONTEXT_SCHEMA_VERSION,
        "symbol_structure": structure,
        "market_regime": (
            structure.get("structure") if structure else None
        ),
        "trend_regime": structure.get("trend") if structure else None,
        "volatility_regime": (
            structure.get("volatility") if structure else None
        ),
        "compression": (
            structure.get("compression") if structure else None
        ),
        "btc_regime": None,
        "market_breadth": None,
        "liquidity": {
            "spread_pct": None,
            "quote_volume_usd": None,
        },
        "completeness": "PARTIAL_PHASE5_5",
    }


def build_experiment_context(
    *,
    decision_batch_id: str,
    market_event_id: str,
    strategy_version: str,
    strategy_variant_id: str,
    selection_model_version: str,
    environment: str,
    execution_mode: str,
    candle_bucket: int,
    structure_fingerprint: Any,
    paper_taker_fee_rate: float,
    paper_entry_slippage_pct: float,
    paper_exit_slippage_pct: float,
    virtual_variant_id: str,
    virtual_target_r: float,
    virtual_max_candles: int,
    paper_variant_id: str,
    candle_interval: str = CANDLE_INTERVAL,
) -> dict:
    context = {
        "contract_version": EXPERIMENT_CONTRACT_VERSION,
        "decision_batch_id": str(decision_batch_id).strip(),
        "market_event_id": str(market_event_id).strip(),
        "strategy_version": str(strategy_version).strip(),
        "strategy_variant_id": str(strategy_variant_id).strip(),
        "selection_model_version": str(
            selection_model_version
        ).strip(),
        "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
        "environment": str(environment).strip().upper(),
        "execution_mode": str(execution_mode).strip().upper(),
        "candle_interval": str(candle_interval).strip().lower(),
        "candle_bucket": int(candle_bucket),
        "market_context": build_market_context(structure_fingerprint),
        "cost_model": {
            "schema_version": COST_MODEL_SCHEMA_VERSION,
            "paper_taker_fee_rate": float(paper_taker_fee_rate),
            "paper_entry_slippage_pct": float(
                paper_entry_slippage_pct
            ),
            "paper_exit_slippage_pct": float(
                paper_exit_slippage_pct
            ),
            "spread_included_in_virtual_outcome": False,
            "fees_included_in_virtual_outcome": False,
            "funding_included": False,
        },
        "virtual_policy": {
            "schema_version": POLICY_SCHEMA_VERSION,
            "variant_id": str(virtual_variant_id).strip(),
            "stop_r": 1.0,
            "target_r": float(virtual_target_r),
            "max_candles": int(virtual_max_candles),
            "ambiguous_touch_policy": "STOP_FIRST",
        },
        "paper_policy": {
            "schema_version": POLICY_SCHEMA_VERSION,
            "variant_id": str(paper_variant_id).strip(),
            "entry_execution": "ADVERSE_SLIPPAGE_MARKET_FILL",
            "exit_execution": "ADVERSE_SLIPPAGE_OBSERVED_STOP",
            "trailing_stop_policy": "INTEGER_R_STEP",
            "single_position": True,
        },
    }
    validate_experiment_context(context)
    return context


def validate_experiment_context(context: Any) -> None:
    if not isinstance(context, dict):
        raise ValueError("EXPERIMENT_CONTEXT_NOT_OBJECT")
    missing = sorted(_REQUIRED_CONTEXT_KEYS.difference(context))
    if missing:
        raise ValueError(
            "EXPERIMENT_CONTEXT_MISSING_KEYS:" + ",".join(missing)
        )
    if context.get("contract_version") != EXPERIMENT_CONTRACT_VERSION:
        raise ValueError("EXPERIMENT_CONTRACT_VERSION_UNSUPPORTED")
    for key in (
        "decision_batch_id",
        "market_event_id",
        "strategy_version",
        "strategy_variant_id",
        "selection_model_version",
        "environment",
        "execution_mode",
        "candle_interval",
    ):
        if not str(context.get(key) or "").strip():
            raise ValueError(f"EXPERIMENT_CONTEXT_{key.upper()}_INVALID")
    if int(context.get("feature_schema_version", -1)) <= 0:
        raise ValueError("EXPERIMENT_CONTEXT_FEATURE_SCHEMA_INVALID")
    if int(context.get("candle_bucket", -1)) < 0:
        raise ValueError("EXPERIMENT_CONTEXT_CANDLE_BUCKET_INVALID")
    for key in ("market_context", "cost_model", "virtual_policy", "paper_policy"):
        if not isinstance(context.get(key), dict):
            raise ValueError(f"EXPERIMENT_CONTEXT_{key.upper()}_INVALID")
    if not str(
        context["virtual_policy"].get("variant_id") or ""
    ).strip():
        raise ValueError("EXPERIMENT_CONTEXT_VIRTUAL_VARIANT_INVALID")
    if not str(
        context["paper_policy"].get("variant_id") or ""
    ).strip():
        raise ValueError("EXPERIMENT_CONTEXT_PAPER_VARIANT_INVALID")


def copy_experiment_context(context: Any) -> dict | None:
    if context is None:
        return None
    validate_experiment_context(context)
    # JSON round-trip guarantees a detached, JSON-safe copy.
    return json.loads(json.dumps(context, sort_keys=True, default=str))


def experiment_projection(context: dict | None) -> dict:
    """Return query-friendly top-level fields for append-only records."""
    if context is None:
        return {
            "experiment_contract_version": 0,
            "decision_batch_id": None,
            "market_event_id": None,
            "strategy_version": None,
            "strategy_variant_id": None,
            "model_version": None,
            "feature_schema_version": None,
            "legacy_record": True,
        }
    validate_experiment_context(context)
    return {
        "experiment_contract_version": context["contract_version"],
        "decision_batch_id": context["decision_batch_id"],
        "market_event_id": context["market_event_id"],
        "strategy_version": context["strategy_version"],
        "strategy_variant_id": context["strategy_variant_id"],
        "model_version": context["selection_model_version"],
        "feature_schema_version": context["feature_schema_version"],
        "legacy_record": False,
    }
