"""NBOT V3.5/V3.6 versioned, authenticated capital-boundary communication."""

from .config import (
    ControlLinkConfig,
    control_link_config_for_profile,
    control_link_environment,
)
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
    "ControlLinkConfig",
    "ExecutionOutcome",
    "ExecutionProposal",
    "OUTCOME_SCHEMA_VERSION",
    "OutcomeAcknowledgement",
    "PROPOSAL_SCHEMA_VERSION",
    "PROTOCOL_VERSION",
    "ProtocolValidationError",
    "TradeRequest",
    "TradeResponse",
    "control_link_config_for_profile",
    "control_link_environment",
]
