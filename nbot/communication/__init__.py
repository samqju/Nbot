"""NBOT V3.5 versioned, authenticated capital-boundary communication."""

from .contracts import (
    ExecutionOutcome,
    ExecutionProposal,
    OutcomeAcknowledgement,
    TradeRequest,
    TradeResponse,
)
from .validation import (
    OUTCOME_SCHEMA_VERSION,
    PROPOSAL_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    ProtocolValidationError,
)

__all__ = [
    "ExecutionOutcome",
    "ExecutionProposal",
    "OUTCOME_SCHEMA_VERSION",
    "OutcomeAcknowledgement",
    "PROPOSAL_SCHEMA_VERSION",
    "PROTOCOL_VERSION",
    "ProtocolValidationError",
    "TradeRequest",
    "TradeResponse",
]
