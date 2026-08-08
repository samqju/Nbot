"""Translate an Observation proposal into the local EntryLifecycle contract."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from communication.execution_proposal import ExecutionProposal


@dataclass(frozen=True)
class ExecutionIntent:
    """Execution-local advisory intent consumed by EntryLifecycle.

    This intentionally lives outside ``strategy``. The Execution Worker must
    not import Strategy merely to pass proposal metadata into proven entry
    validation and order-placement code.
    """

    symbol: str
    direction: str
    pattern: str
    entry_price: float | None
    generated_at: datetime
    proposal_id: str
    structure_fingerprint: dict[str, Any] | None = None
    advisory_risk_plan: dict[str, Any] | None = None
    candidate_observation_id: str | None = None
    decision_batch_id: str | None = None
    market_event_id: str | None = None
    strategy_version: str | None = None
    strategy_variant_id: str | None = None
    model_version: str | None = None
    experiment_context: dict[str, Any] | None = None
    selection_authority: str = "RULES"
    paper_canary_model_id: str | None = None
    paper_risk_multiplier: float = 1.0
    paper_allocation_id: str | None = None


def proposal_to_execution_intent(
    proposal: ExecutionProposal,
) -> ExecutionIntent:
    if not isinstance(proposal, ExecutionProposal):
        raise TypeError("EXECUTION_PROPOSAL_TYPE_INVALID")
    return ExecutionIntent(
        symbol=proposal.symbol,
        direction=proposal.direction,
        pattern=proposal.pattern,
        entry_price=proposal.entry_reference_price,
        generated_at=datetime.fromtimestamp(
            proposal.generated_at / 1000.0,
            tz=timezone.utc,
        ),
        proposal_id=proposal.proposal_id,
        structure_fingerprint=copy.deepcopy(proposal.structure_fingerprint),
        advisory_risk_plan=copy.deepcopy(proposal.advisory_risk_plan),
        candidate_observation_id=proposal.candidate_observation_id,
        decision_batch_id=proposal.decision_batch_id,
        market_event_id=proposal.market_event_id,
        strategy_version=proposal.strategy_version,
        strategy_variant_id=proposal.strategy_variant_id,
        model_version=proposal.model_version,
        experiment_context=copy.deepcopy(proposal.experiment_context),
        selection_authority=proposal.selection_authority,
        paper_canary_model_id=proposal.paper_canary_model_id,
        paper_risk_multiplier=proposal.paper_risk_multiplier,
        paper_allocation_id=proposal.paper_allocation_id,
    )
