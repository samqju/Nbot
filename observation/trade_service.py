"""Local trade-request service for the Observation Worker."""

from __future__ import annotations

import time

from communication.protocol import ProtocolValidationError
from communication.responses import TradeResponse
from communication.trade_request import TradeRequest
from observation.recommendation import LatestRecommendationStore


class ObservationTradeService:
    """Answer TradeRequest from an already-computed recommendation snapshot."""

    def __init__(
        self,
        *,
        recommendation_store: LatestRecommendationStore,
        environment: str,
        execution_mode: str,
        system_log=None,
    ):
        self.recommendation_store = recommendation_store
        self.environment = str(environment or "").strip().upper()
        self.execution_mode = str(execution_mode or "").strip().upper()
        self.system_log = system_log

    def handle_trade_request(
        self,
        request: TradeRequest,
        *,
        now_ms: int | None = None,
    ) -> TradeResponse:
        if not isinstance(request, TradeRequest):
            raise TypeError("OBSERVATION_TRADE_REQUEST_INVALID")
        if request.environment != self.environment:
            raise ProtocolValidationError(
                "OBSERVATION_REQUEST_ENVIRONMENT_MISMATCH"
            )
        if request.execution_mode != self.execution_mode:
            raise ProtocolValidationError(
                "OBSERVATION_REQUEST_EXECUTION_MODE_MISMATCH"
            )

        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)

        if (
            request.previous_proposal_id
            and (
                request.previous_rejection_reason is not None
                or str(
                    request.previous_proposal_result or ""
                ).upper().startswith("REJECT")
            )
        ):
            self.recommendation_store.reject(
                request.previous_proposal_id,
                reason=(
                    request.previous_rejection_reason
                    or request.previous_proposal_result
                    or "EXECUTION_REJECTED_PROPOSAL"
                ),
            )

        ready, readiness_reason = self.recommendation_store.readiness()
        if not ready:
            return TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at=now_ms,
                reason=readiness_reason or "OBSERVATION_NOT_READY",
            )

        proposal, reason = self.recommendation_store.current(now_ms=now_ms)
        if proposal is None:
            return TradeResponse.no_trade(
                request_id=request.request_id,
                responded_at=now_ms,
                reason=reason,
            )

        return TradeResponse.proposal_response(
            request_id=request.request_id,
            responded_at=now_ms,
            proposal=proposal,
        )
