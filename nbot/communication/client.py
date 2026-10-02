"""Execution-side bounded client for the V3 Observation control service.

The adapter implements the transport-neutral ``ProposalClient`` and
``OutcomeClient`` method shapes used by Execution without importing the
Execution worker itself.  Proposal metadata is durably receipted before a
proposal is returned so a later/restarted outcome publisher can reconstruct the
full V3 wire outcome without placing research metadata in capital state.
"""

from __future__ import annotations

import http.client
import json
import math
import os
from pathlib import Path
import ssl
import time
from typing import Any, Mapping
from urllib.parse import urlparse
import uuid

from nbot.common.atomic_io import atomic_write_json
from nbot.execution.entry import EntryProposal

from .auth import bearer_header, validate_control_token
from .authorities import LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY
from .contracts import (
    ExecutionOutcome,
    ExecutionProposal,
    OutcomeAcknowledgement,
    TradeRequest,
    TradeResponse,
)
from .validation import (
    PROFILE_CONTRACTS,
    ProtocolValidationError,
    canonical_json,
    git_sha,
    payload_digest,
    text,
    timestamp_ms,
    validate_profile_contract,
)


_MAX_RESPONSE_BYTES = 1_048_576
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ObservationClientError(RuntimeError):
    """The remote control boundary cannot be used safely."""


class ProposalReceiptStore:
    """Execution-local durable proposal metadata and pending veto feedback."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path, 0o700)
        except OSError:
            pass
        self._feedback_path = self.path / "pending_veto.json"
        # Fail closed immediately if existing receipt/feedback data is corrupt.
        for file_path in sorted(self.path.glob("proposal-*.json")):
            self._read_receipt_file(file_path)
        for file_path in sorted(self.path.glob("entry-context-*.json")):
            self._read_entry_context_file(file_path)
        if self._feedback_path.exists():
            self.pending_feedback()

    @staticmethod
    def _receipt_name(proposal_id: str) -> str:
        import hashlib

        proposal_id = text(proposal_id, "proposal_id")
        return "proposal-" + hashlib.sha256(proposal_id.encode("utf-8")).hexdigest() + ".json"

    def _receipt_path(self, proposal_id: str) -> Path:
        return self.path / self._receipt_name(proposal_id)

    def _entry_context_path(self, proposal_id: str) -> Path:
        import hashlib

        proposal_id = text(proposal_id, "proposal_id")
        digest_value = hashlib.sha256(proposal_id.encode("utf-8")).hexdigest()
        return self.path / f"entry-context-{digest_value}.json"

    def _read_receipt_file(self, path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ObservationClientError("PROPOSAL_RECEIPT_CORRUPT") from exc
        if not isinstance(raw, dict) or set(raw) != {
            "request_id",
            "proposal",
            "recorded_at_ms",
            "receipt_digest",
        }:
            raise ObservationClientError("PROPOSAL_RECEIPT_SCHEMA_INVALID")
        request_id = text(raw["request_id"], "request_id")
        proposal = ExecutionProposal.from_dict(raw["proposal"])
        recorded_at = timestamp_ms(raw["recorded_at_ms"], "recorded_at_ms")
        expected = payload_digest(
            {
                "request_id": request_id,
                "proposal": proposal.to_dict(),
                "recorded_at_ms": recorded_at,
            }
        )
        if raw["receipt_digest"] != expected:
            raise ObservationClientError("PROPOSAL_RECEIPT_DIGEST_MISMATCH")
        if path.name != self._receipt_name(proposal.proposal_id):
            raise ObservationClientError("PROPOSAL_RECEIPT_FILENAME_MISMATCH")
        return {
            "request_id": request_id,
            "proposal": proposal.to_dict(),
            "recorded_at_ms": recorded_at,
            "receipt_digest": expected,
        }

    def record(self, *, request_id: str, proposal: ExecutionProposal, recorded_at_ms: int) -> bool:
        if not isinstance(proposal, ExecutionProposal):
            raise ObservationClientError("PROPOSAL_RECEIPT_PROPOSAL_INVALID")
        request_id = text(request_id, "request_id")
        recorded_at = timestamp_ms(recorded_at_ms, "recorded_at_ms")
        base = {
            "request_id": request_id,
            "proposal": proposal.to_dict(),
            "recorded_at_ms": recorded_at,
        }
        row = dict(base)
        row["receipt_digest"] = payload_digest(base)
        path = self._receipt_path(proposal.proposal_id)
        if path.exists():
            existing = self._read_receipt_file(path)
            if canonical_json(existing["proposal"]) != canonical_json(proposal.to_dict()):
                raise ObservationClientError("PROPOSAL_RECEIPT_ID_COLLISION")
            if existing["request_id"] == request_id:
                return False
            # The same immutable proposal may be re-served under a new request
            # after a lost response/restart.  Retain the most recent request
            # identity so a later outcome is traceable to the request that
            # actually reached this Execution instance.
            atomic_write_json(path, row, mode=0o600)
            return False
        atomic_write_json(path, row, mode=0o600)
        return True

    def get(self, proposal_id: str) -> dict[str, Any]:
        path = self._receipt_path(proposal_id)
        if not path.exists():
            raise ObservationClientError("PROPOSAL_RECEIPT_MISSING")
        return self._read_receipt_file(path)

    def _read_entry_context_file(self, path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_CORRUPT") from exc
        expected_keys = {
            "proposal_id", "observed_at_ms", "quote_timestamp_ms",
            "bid", "ask", "mid", "spread_pct", "expected_entry_price",
            "context_digest",
        }
        if not isinstance(raw, dict) or set(raw) != expected_keys:
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_SCHEMA_INVALID")
        proposal_id = text(raw["proposal_id"], "proposal_id")
        if path != self._entry_context_path(proposal_id):
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_FILENAME_MISMATCH")
        self.get(proposal_id)
        observed = timestamp_ms(raw["observed_at_ms"], "observed_at_ms")
        quote_timestamp = timestamp_ms(raw["quote_timestamp_ms"], "quote_timestamp_ms")
        numbers: dict[str, float] = {}
        for key in ("bid", "ask", "mid", "spread_pct", "expected_entry_price"):
            value = raw[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            value = float(value)
            if not math.isfinite(value):
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            if key == "spread_pct":
                if value < 0:
                    raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            elif value <= 0:
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            numbers[key] = value
        if numbers["ask"] < numbers["bid"]:
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_QUOTE_INVERTED")
        expected_mid = (numbers["bid"] + numbers["ask"]) / 2.0
        if not math.isclose(numbers["mid"], expected_mid, rel_tol=1e-12, abs_tol=1e-12):
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_MID_MISMATCH")
        base = {
            "proposal_id": proposal_id,
            "observed_at_ms": observed,
            "quote_timestamp_ms": quote_timestamp,
            **numbers,
        }
        expected_digest = payload_digest(base)
        if raw["context_digest"] != expected_digest:
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_DIGEST_MISMATCH")
        return {**base, "context_digest": expected_digest}

    def record_entry_context(
        self,
        *,
        proposal_id: str,
        observed_at_ms: int,
        quote_timestamp_ms: int,
        bid: float,
        ask: float,
        mid: float,
        spread_pct: float,
        expected_entry_price: float,
    ) -> None:
        proposal_id = text(proposal_id, "proposal_id")
        self.get(proposal_id)
        numbers = {}
        for key, raw in {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_pct": spread_pct,
            "expected_entry_price": expected_entry_price,
        }.items():
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            value = float(raw)
            if not math.isfinite(value):
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            if key == "spread_pct":
                if value < 0:
                    raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            elif value <= 0:
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_NUMBER_INVALID")
            numbers[key] = value
        if numbers["ask"] < numbers["bid"]:
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_QUOTE_INVERTED")
        expected_mid = (numbers["bid"] + numbers["ask"]) / 2.0
        if not math.isclose(numbers["mid"], expected_mid, rel_tol=1e-12, abs_tol=1e-12):
            raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_MID_MISMATCH")
        base = {
            "proposal_id": proposal_id,
            "observed_at_ms": timestamp_ms(observed_at_ms, "observed_at_ms"),
            "quote_timestamp_ms": timestamp_ms(quote_timestamp_ms, "quote_timestamp_ms"),
            **numbers,
        }
        row = dict(base)
        row["context_digest"] = payload_digest(base)
        path = self._entry_context_path(proposal_id)
        if path.exists():
            existing = self._read_entry_context_file(path)
            if canonical_json(existing) != canonical_json(row):
                raise ObservationClientError("PROPOSAL_ENTRY_CONTEXT_ID_COLLISION")
            return
        atomic_write_json(path, row, mode=0o600)
        self._read_entry_context_file(path)

    def entry_context(self, proposal_id: str) -> dict[str, Any] | None:
        path = self._entry_context_path(proposal_id)
        if not path.exists():
            return None
        return self._read_entry_context_file(path)

    def record_veto(self, *, proposal_id: str, reason: str, rejected_at_ms: int) -> None:
        # A veto can only reference a proposal that this Execution instance
        # durably received from Observation.
        self.get(proposal_id)
        row = {
            "proposal_id": text(proposal_id, "proposal_id"),
            "previous_proposal_result": "REJECTED",
            "previous_rejection_reason": text(reason, "previous_rejection_reason", max_length=300),
            "rejected_at_ms": timestamp_ms(rejected_at_ms, "rejected_at_ms"),
        }
        atomic_write_json(self._feedback_path, row, mode=0o600)

    def pending_feedback(self) -> dict[str, Any] | None:
        if not self._feedback_path.exists():
            return None
        try:
            raw = json.loads(self._feedback_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ObservationClientError("PROPOSAL_VETO_FEEDBACK_CORRUPT") from exc
        if not isinstance(raw, dict) or set(raw) != {
            "proposal_id",
            "previous_proposal_result",
            "previous_rejection_reason",
            "rejected_at_ms",
        }:
            raise ObservationClientError("PROPOSAL_VETO_FEEDBACK_SCHEMA_INVALID")
        if raw["previous_proposal_result"] != "REJECTED":
            raise ObservationClientError("PROPOSAL_VETO_FEEDBACK_RESULT_INVALID")
        return {
            "proposal_id": text(raw["proposal_id"], "proposal_id"),
            "previous_proposal_result": "REJECTED",
            "previous_rejection_reason": text(
                raw["previous_rejection_reason"],
                "previous_rejection_reason",
                max_length=300,
            ),
            "rejected_at_ms": timestamp_ms(raw["rejected_at_ms"], "rejected_at_ms"),
        }

    def acknowledge_feedback(self, proposal_id: str) -> bool:
        feedback = self.pending_feedback()
        if feedback is None or feedback["proposal_id"] != proposal_id:
            return False
        self._feedback_path.unlink()
        # fsync of this non-capital audit helper is not required for safety;
        # losing a veto notification can never create an order by itself.
        return True


def probe_observation_health(
    *,
    base_url: str,
    auth_token: str,
    timeout_seconds: float = 2.0,
    ca_file: str | Path | None = None,
) -> dict[str, Any]:
    """Read-only authenticated health probe with no receipt/state mutation."""

    parsed = urlparse(str(base_url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("NBOT_OBSERVATION_URL_INVALID")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("NBOT_OBSERVATION_URL_INVALID")
    host = parsed.hostname
    if parsed.scheme == "http" and host not in _LOOPBACK_HOSTS:
        raise ValueError("NBOT_OBSERVATION_TLS_REQUIRED_FOR_NON_LOOPBACK")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not (1 <= int(port) <= 65535):
        raise ValueError("NBOT_OBSERVATION_PORT_INVALID")
    timeout = float(timeout_seconds)
    if not (0.1 <= timeout <= 30.0):
        raise ValueError("NBOT_OBSERVATION_TIMEOUT_INVALID")
    token = validate_control_token(auth_token)

    if parsed.scheme == "https":
        context = ssl.create_default_context(
            cafile=None if ca_file is None else str(Path(ca_file))
        )
        connection = http.client.HTTPSConnection(
            host,
            int(port),
            timeout=timeout,
            context=context,
        )
    else:
        connection = http.client.HTTPConnection(host, int(port), timeout=timeout)

    try:
        connection.request(
            "GET",
            "/health",
            headers={"Authorization": bearer_header(token)},
        )
        response = connection.getresponse()
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except TimeoutError as exc:
        raise ObservationClientError("OBSERVATION_CLIENT_TIMEOUT:/health") from exc
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise ObservationClientError("OBSERVATION_CLIENT_UNAVAILABLE:/health") from exc
    finally:
        connection.close()

    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ObservationClientError("OBSERVATION_RESPONSE_TOO_LARGE")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObservationClientError("OBSERVATION_RESPONSE_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ObservationClientError("OBSERVATION_RESPONSE_OBJECT_REQUIRED")
    if response.status != 200:
        detail = str(payload.get("detail") or payload.get("error") or "")
        raise ObservationClientError(
            f"OBSERVATION_HTTP_ERROR:{response.status}:{detail}"
        )
    if payload.get("order_authority") != "NONE":
        raise ObservationClientError("OBSERVATION_HEALTH_ORDER_AUTHORITY_INVALID")
    return payload


class RemoteObservationClient:
    """Bounded synchronous V3 client used only at the flat capital boundary."""

    def __init__(
        self,
        *,
        base_url: str,
        profile: str,
        auth_token: str,
        receipt_directory: str | Path,
        execution_release_sha: str,
        timeout_seconds: float = 2.0,
        ca_file: str | Path | None = None,
    ) -> None:
        parsed = urlparse(str(base_url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("NBOT_OBSERVATION_URL_INVALID")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError("NBOT_OBSERVATION_URL_INVALID")
        host = parsed.hostname
        if parsed.scheme == "http" and host not in _LOOPBACK_HOSTS:
            raise ValueError("NBOT_OBSERVATION_TLS_REQUIRED_FOR_NON_LOOPBACK")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not (1 <= int(port) <= 65535):
            raise ValueError("NBOT_OBSERVATION_PORT_INVALID")
        timeout = float(timeout_seconds)
        if not (0.1 <= timeout <= 30.0):
            raise ValueError("NBOT_OBSERVATION_TIMEOUT_INVALID")
        profile_name = str(profile).strip().lower()
        try:
            environment, execution_mode, evidence_lineage = PROFILE_CONTRACTS[profile_name]
        except KeyError as exc:
            raise ValueError("NBOT_OBSERVATION_PROFILE_INVALID") from exc
        # LIVE real order authority is not enabled by V3.5.
        # Mainnet proposals remain advisory; local explicit trial arming owns order permission.

        self.scheme = parsed.scheme
        self.host = host
        self.port = int(port)
        self.profile = profile_name
        self.market_environment = environment
        self.execution_mode = execution_mode
        self.evidence_lineage = evidence_lineage
        self.auth_token = validate_control_token(auth_token)
        self.timeout_seconds = timeout
        self.execution_release_sha = git_sha(execution_release_sha, "execution_release_sha")
        self.receipts = ProposalReceiptStore(receipt_directory)
        self.ca_file = None if ca_file is None else str(Path(ca_file))

    def _connection(self, *, timeout_seconds: float | None = None):
        timeout = self.timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if not (0.1 <= timeout <= 30.0):
            raise ValueError("NBOT_OBSERVATION_TIMEOUT_INVALID")
        if self.scheme == "https":
            context = ssl.create_default_context(cafile=self.ca_file)
            return http.client.HTTPSConnection(
                self.host,
                self.port,
                timeout=timeout,
                context=context,
            )
        return http.client.HTTPConnection(self.host, self.port, timeout=timeout)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Authorization": bearer_header(self.auth_token)}
        if payload is not None:
            try:
                encoded = canonical_json(dict(payload)).encode("utf-8")
            except ProtocolValidationError as exc:
                raise ObservationClientError("OBSERVATION_REQUEST_JSON_INVALID") from exc
            body = encoded
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(encoded))
        connection = self._connection(timeout_seconds=timeout_seconds)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except TimeoutError as exc:
            raise ObservationClientError(f"OBSERVATION_CLIENT_TIMEOUT:{path}") from exc
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise ObservationClientError(f"OBSERVATION_CLIENT_UNAVAILABLE:{path}") from exc
        finally:
            connection.close()
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ObservationClientError("OBSERVATION_RESPONSE_TOO_LARGE")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObservationClientError("OBSERVATION_RESPONSE_JSON_INVALID") from exc
        if not isinstance(decoded, dict):
            raise ObservationClientError("OBSERVATION_RESPONSE_OBJECT_REQUIRED")
        if response.status != 200:
            detail = str(decoded.get("detail") or decoded.get("error") or "")
            raise ObservationClientError(
                f"OBSERVATION_HTTP_ERROR:{response.status}:{detail}"
            )
        return decoded

    def health(self) -> dict[str, Any]:
        payload = self._request_json("GET", "/health")
        if payload.get("order_authority") != "NONE":
            raise ObservationClientError("OBSERVATION_HEALTH_ORDER_AUTHORITY_INVALID")
        return payload

    def operator_status(self, view: str) -> dict[str, Any]:
        """Read Observation-owned operator status without creating authority."""
        normalized = str(view or "").strip().lower()
        if not normalized or len(normalized) > 64:
            raise ObservationClientError("OBSERVATION_OPERATOR_VIEW_INVALID")
        payload = self._request_json(
            "POST",
            "/operator-status",
            {"view": normalized},
            timeout_seconds=max(self.timeout_seconds, 15.0),
        )
        if payload.get("status") != "OK":
            raise ObservationClientError("OBSERVATION_OPERATOR_STATUS_INVALID")
        if payload.get("view") != normalized:
            raise ObservationClientError("OBSERVATION_OPERATOR_VIEW_MISMATCH")
        if payload.get("order_authority") != "NONE":
            raise ObservationClientError("OBSERVATION_OPERATOR_AUTHORITY_INVALID")
        if not isinstance(payload.get("document"), dict):
            raise ObservationClientError("OBSERVATION_OPERATOR_DOCUMENT_INVALID")
        if not isinstance(payload.get("telegram_body"), str) or not str(payload["telegram_body"]).strip():
            raise ObservationClientError("OBSERVATION_OPERATOR_BODY_INVALID")
        return payload

    def request_proposal(
        self,
        *,
        profile: str,
        market_environment: str,
        execution_instance_id: str,
        requested_at_ms: int,
    ) -> EntryProposal | None:
        if str(profile).strip().lower() != self.profile:
            raise ObservationClientError("OBSERVATION_REQUEST_PROFILE_MISMATCH")
        if str(market_environment).strip().upper() != self.market_environment:
            raise ObservationClientError("OBSERVATION_REQUEST_ENVIRONMENT_MISMATCH")
        requested_at = timestamp_ms(requested_at_ms, "requested_at_ms")
        feedback = self.receipts.pending_feedback()
        request = TradeRequest.create(
            request_id=f"REQ-{uuid.uuid4().hex}",
            requested_at_ms=requested_at,
            profile=self.profile,
            market_environment=self.market_environment,
            execution_mode=self.execution_mode,
            execution_state="FLAT",
            execution_instance_id=text(
                execution_instance_id,
                "execution_instance_id",
                max_length=128,
            ),
            execution_release_sha=self.execution_release_sha,
            previous_proposal_id=(None if feedback is None else feedback["proposal_id"]),
            previous_proposal_result=(
                None if feedback is None else feedback["previous_proposal_result"]
            ),
            previous_rejection_reason=(
                None if feedback is None else feedback["previous_rejection_reason"]
            ),
        )
        raw = self._request_json("POST", "/trade-request", request.to_dict())
        try:
            response = TradeResponse.from_dict(raw)
        except (ProtocolValidationError, TypeError, ValueError) as exc:
            raise ObservationClientError("OBSERVATION_TRADE_RESPONSE_INVALID") from exc
        if response.request_id != request.request_id:
            raise ObservationClientError("OBSERVATION_RESPONSE_REQUEST_ID_MISMATCH")
        if response.status != "PROPOSAL":
            if feedback is not None:
                self.receipts.acknowledge_feedback(feedback["proposal_id"])
            return None
        proposal = response.proposal
        assert proposal is not None
        if proposal.profile != self.profile:
            raise ObservationClientError("OBSERVATION_PROPOSAL_PROFILE_MISMATCH")
        if proposal.market_environment != self.market_environment:
            raise ObservationClientError("OBSERVATION_PROPOSAL_ENVIRONMENT_MISMATCH")
        if proposal.evidence_lineage != self.evidence_lineage:
            raise ObservationClientError("OBSERVATION_PROPOSAL_LINEAGE_MISMATCH")
        if proposal.is_expired(now_ms=int(time.time() * 1000)):
            raise ObservationClientError("OBSERVATION_PROPOSAL_EXPIRED")
        if feedback is not None and proposal.proposal_id == feedback["proposal_id"]:
            raise ObservationClientError("OBSERVATION_REOFFERED_REJECTED_PROPOSAL")
        if feedback is not None:
            self.receipts.acknowledge_feedback(feedback["proposal_id"])
        self.receipts.record(
            request_id=request.request_id,
            proposal=proposal,
            recorded_at_ms=int(time.time() * 1000),
        )
        return EntryProposal(
            proposal_id=proposal.proposal_id,
            generated_at_ms=proposal.generated_at_ms,
            expires_at_ms=proposal.expires_at_ms,
            profile=proposal.profile,
            market_environment=proposal.market_environment,
            symbol=proposal.symbol,
            side=proposal.side,
            reference_price=proposal.reference_price,
            entry_authority=proposal.entry_authority,
            exit_policy_version=proposal.exit_policy_version,
        )

    def record_veto(self, *, proposal_id: str, reason: str, rejected_at_ms: int) -> None:
        self.receipts.record_veto(
            proposal_id=proposal_id,
            reason=reason,
            rejected_at_ms=rejected_at_ms,
        )

    def _wire_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> ExecutionOutcome:
        if not isinstance(payload, Mapping):
            raise ObservationClientError("EXECUTION_OUTCOME_PAYLOAD_INVALID")
        body = dict(payload)
        if body.get("outcome_id") != outcome_id:
            raise ObservationClientError("EXECUTION_OUTCOME_ID_MISMATCH")
        proposal_id = text(body.get("proposal_id"), "proposal_id")
        receipt = self.receipts.get(proposal_id)
        proposal = ExecutionProposal.from_dict(receipt["proposal"])
        if body.get("profile") != proposal.profile or proposal.profile != self.profile:
            raise ObservationClientError("EXECUTION_OUTCOME_PROFILE_MISMATCH")
        if body.get("market_environment") != proposal.market_environment:
            raise ObservationClientError("EXECUTION_OUTCOME_ENVIRONMENT_MISMATCH")
        if body.get("symbol") != proposal.symbol or body.get("side") != proposal.side:
            raise ObservationClientError("EXECUTION_OUTCOME_INSTRUMENT_MISMATCH")
        if body.get("entry_authority") != proposal.entry_authority:
            raise ObservationClientError("EXECUTION_OUTCOME_AUTHORITY_MISMATCH")
        if body.get("exit_policy_version") != proposal.exit_policy_version:
            raise ObservationClientError("EXECUTION_OUTCOME_POLICY_MISMATCH")

        risk = float(body["initial_risk_usd"])
        mae_r = body.get("mae_r")
        mfe_r = body.get("mfe_r")
        mae_usd = None if mae_r is None else float(mae_r) * risk
        mfe_usd = None if mfe_r is None else float(mfe_r) * risk
        entered = int(body["entry_timestamp_ms"])
        closed = int(body["closed_timestamp_ms"])
        operational = self.receipts.entry_context(proposal_id)
        context = dict(proposal.experiment_context or {})
        if proposal.entry_authority == LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY:
            if operational is None:
                raise ObservationClientError("LIVE_PAPER_OPERATIONAL_ENTRY_CONTEXT_MISSING")
            reference = float(proposal.reference_price)
            receive_mid = float(operational["mid"])
            fill_price = float(body["entry_price"])
            expected_quote_entry = float(
                operational["ask"] if proposal.side == "LONG" else operational["bid"]
            )
            if not math.isclose(
                float(operational["expected_entry_price"]), expected_quote_entry,
                rel_tol=1e-12, abs_tol=1e-12,
            ):
                raise ObservationClientError("LIVE_PAPER_OPERATIONAL_EXPECTED_ENTRY_MISMATCH")
            if proposal.side == "LONG":
                receive_deterioration = (receive_mid - reference) / reference * 100.0
                fill_deterioration = (fill_price - reference) / reference * 100.0
                fill_vs_quote = (fill_price - float(operational["expected_entry_price"])) / float(operational["expected_entry_price"]) * 100.0
            else:
                receive_deterioration = (reference - receive_mid) / reference * 100.0
                fill_deterioration = (reference - fill_price) / reference * 100.0
                fill_vs_quote = (float(operational["expected_entry_price"]) - fill_price) / float(operational["expected_entry_price"]) * 100.0
            delivered_at_ms = int(time.time() * 1000)
            context["execution_operational"] = {
                "proposal_received_at_ms": int(receipt["recorded_at_ms"]),
                "proposal_receive_latency_ms": max(0, int(receipt["recorded_at_ms"]) - int(proposal.generated_at_ms)),
                "execution_quote_observed_at_ms": int(operational["observed_at_ms"]),
                "execution_quote_timestamp_ms": int(operational["quote_timestamp_ms"]),
                "execution_bid": float(operational["bid"]),
                "execution_ask": float(operational["ask"]),
                "execution_mid": receive_mid,
                "execution_spread_pct": float(operational["spread_pct"]),
                "execution_expected_entry_price": float(operational["expected_entry_price"]),
                "reference_to_execution_mid_deterioration_pct": receive_deterioration,
                "reference_to_actual_fill_deterioration_pct": fill_deterioration,
                "execution_quote_to_actual_fill_deterioration_pct": fill_vs_quote,
                "outcome_delivery_started_at_ms": delivered_at_ms,
                "outcome_delivery_latency_ms": max(0, delivered_at_ms - int(body["closed_timestamp_ms"])),
                "expected_after_cost_net_r": proposal.expected_after_cost_net_r,
                "actual_paper_r": float(body["r_multiple"]),
                "economic_delta_r": (
                    None
                    if proposal.expected_after_cost_net_r is None
                    else float(body["r_multiple"]) - float(proposal.expected_after_cost_net_r)
                ),
            }

        return ExecutionOutcome.create(
            outcome_id=outcome_id,
            proposal_id=proposal_id,
            request_id=str(receipt["request_id"]),
            profile=proposal.profile,
            market_environment=proposal.market_environment,
            execution_mode=self.execution_mode,
            evidence_lineage=proposal.evidence_lineage,
            symbol=proposal.symbol,
            side=proposal.side,
            market_event_id=proposal.market_event_id,
            feature_version=proposal.feature_version,
            selector_version=proposal.selector_version,
            entry_authority=proposal.entry_authority,
            exit_policy_version=proposal.exit_policy_version,
            reference_price=proposal.reference_price,
            selection_score=proposal.selection_score,
            selection_rank=proposal.selection_rank,
            expected_after_cost_net_r=proposal.expected_after_cost_net_r,
            proposal_source_digest=proposal.source_digest,
            proposal_model_digest=proposal.model_digest,
            entry_price=body["entry_price"],
            exit_price=body["exit_price"],
            quantity=body["quantity"],
            initial_risk_usd=body["initial_risk_usd"],
            realized_pnl_usd=body["realized_pnl_usd"],
            r_multiple=body["r_multiple"],
            mae_usd=mae_usd,
            mfe_usd=mfe_usd,
            mae_r=mae_r,
            mfe_r=mfe_r,
            entry_timestamp_ms=entered,
            closed_timestamp_ms=closed,
            holding_seconds=max(0, (closed - entered) // 1000),
            exit_reason=body.get("exit_reason", "UNKNOWN"),
            close_source=body.get("close_source", "UNKNOWN"),
            execution_payload_digest=payload_digest(body),
            entry_order_id=body.get("entry_order_id"),
            entry_client_order_id=body.get("entry_client_order_id"),
            final_stop_price=body.get("final_stop_price"),
            final_stop_id=body.get("final_stop_id"),
            experiment_context=context,
        )

    def send_outcome(self, *, outcome_id: str, payload: Mapping[str, Any]) -> str:
        # Freeze the complete envelope, including first-delivery telemetry,
        # before network I/O. An ACK can be lost after the receiver commits.
        import hashlib
        key = hashlib.sha256(text(outcome_id, "outcome_id").encode()).hexdigest()
        path = self.receipts.path / f"outcome-wire-{key}.json"
        source_digest = payload_digest(dict(payload))
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("source_digest") != source_digest:
                raise ObservationClientError("OUTCOME_WIRE_SOURCE_COLLISION")
            wire = saved["outcome"]
            if payload_digest(wire) != saved.get("wire_digest"):
                raise ObservationClientError("OUTCOME_WIRE_DIGEST_MISMATCH")
            outcome = ExecutionOutcome.from_dict(wire)
            if outcome.outcome_id != outcome_id:
                raise ObservationClientError("OUTCOME_WIRE_ID_MISMATCH")
        else:
            outcome = self._wire_outcome(outcome_id=outcome_id, payload=payload)
            wire = outcome.to_dict()
            atomic_write_json(path, {"source_digest": source_digest, "wire_digest": payload_digest(wire), "outcome": wire})
        raw = self._request_json("POST", "/execution-outcome", outcome.to_dict())
        try:
            acknowledgement = OutcomeAcknowledgement.from_dict(raw)
        except (ProtocolValidationError, TypeError, ValueError) as exc:
            raise ObservationClientError("OBSERVATION_OUTCOME_ACK_INVALID") from exc
        if acknowledgement.outcome_id != outcome_id:
            raise ObservationClientError("OBSERVATION_OUTCOME_ACK_ID_MISMATCH")
        if acknowledgement.status not in {"RECORDED", "ALREADY_RECORDED"}:
            raise ObservationClientError("OBSERVATION_OUTCOME_ACK_STATUS_INVALID")
        return outcome_id
