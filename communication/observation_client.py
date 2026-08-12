"""Execution-side client for the Observation Worker control API.

The client remains loopback-only during local hardening. Optional bearer
authentication is supported now so authentication failures can be tested before
cross-VPS exposure; TLS and non-loopback targets remain a deployment step.
"""

from __future__ import annotations

import http.client
import json
import time
import uuid

from communication.execution_outcome import ExecutionOutcome
from communication.protocol import ProtocolValidationError
from communication.responses import OutcomeAcknowledgement, TradeResponse
from communication.trade_request import TradeRequest


_MAX_RESPONSE_BYTES = 1_048_576
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ObservationClientError(RuntimeError):
    """Raised when the Observation control boundary cannot be used safely."""


class ObservationClient:
    """Small synchronous client used only around the capital boundary."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        timeout_seconds: float = 2.0,
        auth_token: str | None = None,
        system_log=None,
    ):
        host = str(host).strip()
        if host not in _LOOPBACK_HOSTS:
            raise ValueError("OBSERVATION_CLIENT_LOCALHOST_ONLY")
        port = int(port)
        timeout_seconds = float(timeout_seconds)
        if not (1 <= port <= 65535):
            raise ValueError("OBSERVATION_CLIENT_PORT_INVALID")
        if not (0.1 <= timeout_seconds <= 30.0):
            raise ValueError("OBSERVATION_CLIENT_TIMEOUT_INVALID")

        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        token = str(auth_token or "").strip()
        self.auth_token = token or None
        self.system_log = system_log

    def request_best_trade(
        self,
        *,
        environment: str,
        execution_mode: str,
        previous_proposal_id: str | None = None,
        previous_proposal_result: str | None = None,
        previous_rejection_reason: str | None = None,
        request_id: str | None = None,
        requested_at: int | None = None,
    ) -> TradeResponse:
        request = TradeRequest.create(
            request_id=request_id or f"REQ-{uuid.uuid4().hex}",
            requested_at=(
                int(time.time() * 1000)
                if requested_at is None
                else int(requested_at)
            ),
            environment=environment,
            execution_mode=execution_mode,
            previous_proposal_id=previous_proposal_id,
            previous_proposal_result=previous_proposal_result,
            previous_rejection_reason=previous_rejection_reason,
        )
        payload = self._post("/trade-request", request.to_dict())
        try:
            response = TradeResponse.from_dict(payload)
        except (ProtocolValidationError, TypeError, ValueError) as exc:
            raise ObservationClientError(
                "OBSERVATION_TRADE_RESPONSE_INVALID"
            ) from exc
        if response.request_id != request.request_id:
            raise ObservationClientError(
                "OBSERVATION_RESPONSE_REQUEST_ID_MISMATCH"
            )
        return response

    def deliver_execution_outcome(
        self,
        outcome: ExecutionOutcome,
    ) -> OutcomeAcknowledgement:
        if not isinstance(outcome, ExecutionOutcome):
            raise TypeError("OBSERVATION_OUTCOME_TYPE_INVALID")
        payload = self._post("/execution-outcome", outcome.to_dict())
        try:
            acknowledgement = OutcomeAcknowledgement.from_dict(payload)
        except (ProtocolValidationError, TypeError, ValueError) as exc:
            raise ObservationClientError(
                "OBSERVATION_OUTCOME_ACK_INVALID"
            ) from exc
        if acknowledgement.outcome_id != outcome.outcome_id:
            raise ObservationClientError(
                "OBSERVATION_OUTCOME_ACK_ID_MISMATCH"
            )
        return acknowledgement

    def receive(self, outcome: ExecutionOutcome) -> OutcomeAcknowledgement:
        """Compatibility surface for ExecutionOutcomePublisher."""
        return self.deliver_execution_outcome(outcome)

    def request_learning_status(self) -> dict:
        """Fetch Observation-owned learning status for operator display only."""
        payload = self._post(
            "/learning-status",
            {"request": "LEARNING_STATUS"},
        )
        if payload.get("status") != "OK":
            raise ObservationClientError(
                "OBSERVATION_LEARNING_STATUS_INVALID"
            )
        if payload.get("order_authority") != "NONE":
            raise ObservationClientError(
                "OBSERVATION_LEARNING_STATUS_AUTHORITY_INVALID"
            )
        body = payload.get("telegram_body")
        document = payload.get("document")
        if not isinstance(body, str) or not body.strip():
            raise ObservationClientError(
                "OBSERVATION_LEARNING_STATUS_BODY_INVALID"
            )
        if not isinstance(document, dict):
            raise ObservationClientError(
                "OBSERVATION_LEARNING_STATUS_DOCUMENT_INVALID"
            )
        return payload

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(
            payload,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        connection = http.client.HTTPConnection(
            self.host,
            self.port,
            timeout=self.timeout_seconds,
        )
        try:
            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            }
            if self.auth_token is not None:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            connection.request(
                "POST",
                path,
                body=body,
                headers=headers,
            )
            response = connection.getresponse()
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except TimeoutError as exc:
            self._log(
                "warning",
                "OBSERVATION_CLIENT_TIMEOUT | "
                f"path={path} | timeout_seconds={self.timeout_seconds}",
            )
            raise ObservationClientError(
                f"OBSERVATION_CLIENT_TIMEOUT:{path}"
            ) from exc
        except (OSError, http.client.HTTPException) as exc:
            self._log(
                "warning",
                "OBSERVATION_CLIENT_UNAVAILABLE | "
                f"path={path} | error={type(exc).__name__}:{exc}",
            )
            raise ObservationClientError(
                f"OBSERVATION_CLIENT_UNAVAILABLE:{path}"
            ) from exc
        finally:
            connection.close()

        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ObservationClientError("OBSERVATION_RESPONSE_TOO_LARGE")

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObservationClientError(
                "OBSERVATION_RESPONSE_JSON_INVALID"
            ) from exc
        if not isinstance(decoded, dict):
            raise ObservationClientError(
                "OBSERVATION_RESPONSE_OBJECT_REQUIRED"
            )
        if response.status != 200:
            detail = str(decoded.get("detail") or decoded.get("error") or "")
            raise ObservationClientError(
                "OBSERVATION_HTTP_ERROR | "
                f"status={response.status} | detail={detail}"
            )
        return decoded

    def _log(self, level: str, message: str) -> None:
        if self.system_log is None:
            return
        getattr(self.system_log, level, lambda *_args, **_kwargs: None)(message)
