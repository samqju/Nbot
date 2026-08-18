"""Standalone Binance Testnet mechanical-canary helpers for NBOT V3.2.

This module is deliberately execution-only.  It provides a one-shot manual
proposal source and a local outcome sink so V3 Execution mechanics can be
physically exercised before Observation V3 or the V3.5 communication protocol
exists.

Nothing here is research authority.  Every proposal and locally ACKed outcome
is explicitly bound to ``TESTNET_MECHANICAL_ONLY``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Mapping

from nbot.common.ids import new_id
from nbot.exchange.contracts import Quote, Side
from nbot.execution.entry import EntryProposal
from nbot.execution.outcomes import ExecutionHistoryStore
from nbot.execution.position import INTEGER_R_STEP_CONTROL

TESTNET_MECHANICAL_AUTHORITY = "TESTNET_MECHANICAL_ONLY"
TESTNET_MECHANICAL_EVIDENCE_CLASS = "TESTNET_MECHANICAL_ONLY"
TESTNET_MECHANICAL_PROFILE = "testnet-trade"
TESTNET_MECHANICAL_ENVIRONMENT = "TESTNET"
TESTNET_MECHANICAL_PROPOSAL_TTL_MS = 30_000


class MechanicalCanaryError(RuntimeError):
    """The standalone V3.2 canary boundary was used unsafely."""


class OneShotMechanicalProposalClient:
    """Manual proposal source that can yield at most one proposal.

    Consumption happens before the proposal is returned.  Therefore an entry
    rejection or caller retry cannot cause the same manual invocation to be
    offered a second time.  Durable duplicate protection remains enforced by
    the normal EntryLifecycle as an independent safety layer.
    """

    def __init__(self) -> None:
        self._proposal: EntryProposal | None = None
        self._consumed = False

    def offer(self, proposal: EntryProposal) -> None:
        if not isinstance(proposal, EntryProposal):
            raise MechanicalCanaryError("TESTNET_MECHANICAL_PROPOSAL_INVALID")
        if self._proposal is not None or self._consumed:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_PROPOSAL_ALREADY_OFFERED")
        if proposal.profile != TESTNET_MECHANICAL_PROFILE:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_PROFILE_MISMATCH")
        if proposal.market_environment != TESTNET_MECHANICAL_ENVIRONMENT:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_ENVIRONMENT_MISMATCH")
        if proposal.entry_authority != TESTNET_MECHANICAL_AUTHORITY:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_AUTHORITY_MISMATCH")
        self._proposal = proposal

    def request_proposal(
        self,
        *,
        profile: str,
        market_environment: str,
        execution_instance_id: str,
        requested_at_ms: int,
    ) -> EntryProposal | None:
        # Validate the call boundary even though EntryLifecycle independently
        # validates the proposal itself.
        if profile != TESTNET_MECHANICAL_PROFILE:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_REQUEST_PROFILE_MISMATCH")
        if market_environment != TESTNET_MECHANICAL_ENVIRONMENT:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_REQUEST_ENVIRONMENT_MISMATCH")
        if not isinstance(execution_instance_id, str) or not execution_instance_id.strip():
            raise MechanicalCanaryError("TESTNET_MECHANICAL_EXECUTION_INSTANCE_INVALID")
        if isinstance(requested_at_ms, bool) or not isinstance(requested_at_ms, int) or requested_at_ms <= 0:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_REQUEST_TIME_INVALID")
        if self._proposal is None or self._consumed:
            return None
        self._consumed = True
        return self._proposal


class MechanicalCanaryOutcomeClient:
    """Local idempotent Testnet-only outcome sink used before Observation V3.

    The normal Execution outbox remains the source record.  This client ACKs an
    outcome only after an idempotent durable local history write succeeds, so a
    completed mechanical canary does not permanently block later standalone
    canaries merely because V3.5's Observation outcome receiver does not exist.
    """

    def __init__(self, path: str | Path):
        self.store = ExecutionHistoryStore(path)

    def send_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> str:
        if not isinstance(payload, Mapping):
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_INVALID")
        row = dict(payload)
        if row.get("outcome_id") != outcome_id:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_ID_MISMATCH")
        if row.get("profile") != TESTNET_MECHANICAL_PROFILE:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_PROFILE_MISMATCH")
        if row.get("market_environment") != TESTNET_MECHANICAL_ENVIRONMENT:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_ENVIRONMENT_MISMATCH")
        if row.get("entry_authority") != TESTNET_MECHANICAL_AUTHORITY:
            raise MechanicalCanaryError("TESTNET_MECHANICAL_OUTCOME_AUTHORITY_MISMATCH")
        row["evidence_class"] = TESTNET_MECHANICAL_EVIDENCE_CLASS
        row["research_evidence"] = False
        self.store.append(outcome_id, row)
        return outcome_id


def mechanical_outcome_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / "data/execution/testnet/mechanical_canary_outcomes.jsonl"


def make_mechanical_proposal(
    quote: Quote,
    *,
    side: Side,
    now_ms: Callable[[], int] | None = None,
) -> EntryProposal:
    """Create one short-lived manual Testnet proposal from Execution quote truth."""
    if not isinstance(quote, Quote):
        raise MechanicalCanaryError("TESTNET_MECHANICAL_QUOTE_INVALID")
    if side not in {"LONG", "SHORT"}:
        raise MechanicalCanaryError("TESTNET_MECHANICAL_SIDE_INVALID")
    clock = now_ms or (lambda: int(time.time() * 1000))
    generated = clock()
    if isinstance(generated, bool) or not isinstance(generated, int) or generated <= 0:
        raise MechanicalCanaryError("TESTNET_MECHANICAL_TIME_INVALID")
    reference = quote.ask if side == "LONG" else quote.bid
    return EntryProposal(
        proposal_id=new_id("TESTNET_CANARY"),
        generated_at_ms=generated,
        expires_at_ms=generated + TESTNET_MECHANICAL_PROPOSAL_TTL_MS,
        profile=TESTNET_MECHANICAL_PROFILE,
        market_environment=TESTNET_MECHANICAL_ENVIRONMENT,
        symbol=quote.symbol,
        side=side,
        reference_price=reference,
        entry_authority=TESTNET_MECHANICAL_AUTHORITY,
        exit_policy_version=INTEGER_R_STEP_CONTROL,
    )
