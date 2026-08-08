"""Build versioned execution outcomes from local execution state."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping

from communication.execution_outcome import ExecutionOutcome


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_optional(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _stable_legacy_proposal_id(
    *,
    open_position: Mapping[str, Any],
    environment: str,
    execution_mode: str,
) -> str:
    explicit = _optional_text(open_position.get("proposal_id"))
    if explicit:
        return explicit

    candidate_id = _optional_text(open_position.get("candidate_observation_id"))
    if candidate_id:
        return f"LEGACY-{candidate_id}"

    client_order_id = _optional_text(open_position.get("entry_client_order_id"))
    if client_order_id:
        return f"LEGACY-{client_order_id}"

    identity = "|".join(
        [
            str(environment).strip().upper(),
            str(execution_mode).strip().upper(),
            str(open_position.get("symbol") or ""),
            str(open_position.get("side") or ""),
            str(open_position.get("entry_timestamp") or ""),
            str(open_position.get("entry_price") or ""),
            str(open_position.get("qty") or ""),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"LEGACY-{digest}"


def _stable_outcome_id(
    *,
    proposal_id: str,
    open_position: Mapping[str, Any],
    environment: str,
    execution_mode: str,
) -> str:
    identity = "|".join(
        [
            str(environment).strip().upper(),
            str(execution_mode).strip().upper(),
            proposal_id,
            str(open_position.get("entry_client_order_id") or ""),
            str(open_position.get("entry_order_id") or ""),
            str(open_position.get("entry_timestamp") or ""),
            str(open_position.get("symbol") or ""),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return f"OUT-{digest}"


def build_execution_outcome(
    *,
    open_position: Mapping[str, Any],
    environment: str,
    execution_mode: str,
    exit_price: float,
    realized_pnl_usd: float,
    exit_reason: str,
    closed_timestamp: int | None = None,
    holding_seconds: int | None = None,
) -> ExecutionOutcome:
    """Create a deterministic, retry-safe outcome for one closed position.

    The outcome ID is derived from immutable entry identity rather than close
    time. If reconciliation rebuilds the same close after a crash, the same
    outcome ID is produced and the Observation receiver can treat it as a
    retry instead of a second trade.
    """

    closed_ms = int(closed_timestamp or int(time.time() * 1000))
    raw_entry_ts = open_position.get("entry_timestamp")
    try:
        entry_ms = int(raw_entry_ts) if raw_entry_ts else closed_ms
    except (TypeError, ValueError):
        entry_ms = closed_ms
    if entry_ms <= 0 or entry_ms > closed_ms:
        entry_ms = closed_ms

    if holding_seconds is None:
        holding = max(0, int((closed_ms - entry_ms) / 1000))
    else:
        holding = max(0, int(holding_seconds))

    initial_risk = float(
        open_position.get(
            "initial_risk_usd",
            open_position.get("risk_usd", 0.0),
        )
        or 0.0
    )
    mae_usd = float(open_position.get("mae", 0.0) or 0.0)
    mfe_usd = float(open_position.get("mfe", 0.0) or 0.0)
    realized = float(realized_pnl_usd or 0.0)

    if initial_risk > 0:
        r_multiple = realized / initial_risk
        mae_r = mae_usd / initial_risk
        mfe_r = mfe_usd / initial_risk
    else:
        r_multiple = 0.0
        mae_r = 0.0
        mfe_r = 0.0

    proposal_id = _stable_legacy_proposal_id(
        open_position=open_position,
        environment=environment,
        execution_mode=execution_mode,
    )
    outcome_id = _stable_outcome_id(
        proposal_id=proposal_id,
        open_position=open_position,
        environment=environment,
        execution_mode=execution_mode,
    )

    return ExecutionOutcome.create(
        outcome_id=outcome_id,
        proposal_id=proposal_id,
        environment=environment,
        execution_mode=execution_mode,
        symbol=str(open_position.get("symbol") or ""),
        side=str(open_position.get("side") or ""),
        entry_price=float(open_position.get("entry_price") or 0.0),
        exit_price=float(exit_price or 0.0),
        quantity=float(open_position.get("qty") or 0.0),
        realized_pnl_usd=realized,
        initial_risk_usd=max(0.0, initial_risk),
        r_multiple=float(r_multiple),
        mae_usd=mae_usd,
        mfe_usd=mfe_usd,
        mae_r=float(mae_r),
        mfe_r=float(mfe_r),
        entry_timestamp=entry_ms,
        closed_timestamp=closed_ms,
        holding_seconds=holding,
        candidate_observation_id=_optional_text(
            open_position.get("candidate_observation_id")
        ),
        decision_batch_id=_optional_text(open_position.get("decision_batch_id")),
        market_event_id=_optional_text(open_position.get("market_event_id")),
        entry_order_id=_optional_text(open_position.get("entry_order_id")),
        entry_client_order_id=_optional_text(
            open_position.get("entry_client_order_id")
        ),
        initial_stop_loss=_positive_optional(
            open_position.get("initial_stop_loss")
        ),
        final_stop_loss=_positive_optional(open_position.get("stop_loss")),
        exit_reason=_optional_text(exit_reason),
        pattern=_optional_text(open_position.get("pattern")),
        strategy_version=_optional_text(open_position.get("strategy_version")),
        strategy_variant_id=_optional_text(
            open_position.get("strategy_variant_id")
        ),
        model_version=_optional_text(open_position.get("model_version")),
        selection_authority=_optional_text(
            open_position.get("selection_authority")
        ),
        experiment_context=open_position.get("experiment_context"),
    )
