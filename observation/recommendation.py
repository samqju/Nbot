"""Thread-safe latest execution recommendation maintained by Observation."""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import timezone

from communication.execution_proposal import ExecutionProposal


DEFAULT_PROPOSAL_TTL_SECONDS = 30


class LatestRecommendationStore:
    """Hold the latest advisory proposal without creating capital exposure."""

    def __init__(
        self,
        *,
        environment: str,
        proposal_ttl_seconds: int = DEFAULT_PROPOSAL_TTL_SECONDS,
        system_log=None,
    ):
        self.environment = str(environment or "").strip().upper()
        self.proposal_ttl_seconds = int(proposal_ttl_seconds)
        if self.environment not in {"TESTNET", "LIVE"}:
            raise ValueError("OBSERVATION_RECOMMENDATION_ENVIRONMENT_INVALID")
        if not (1 <= self.proposal_ttl_seconds <= 300):
            raise ValueError("OBSERVATION_PROPOSAL_TTL_INVALID")
        self.system_log = system_log
        self._lock = threading.Lock()
        self._proposal: ExecutionProposal | None = None
        self._ready = False
        self._reason = "OBSERVATION_STARTUP"

    def set_ready(self, ready: bool, *, reason: str | None = None) -> None:
        with self._lock:
            self._ready = bool(ready)
            if self._ready:
                self._reason = reason or self._reason or "READY_NO_RECOMMENDATION"
            else:
                self._proposal = None
                self._reason = str(reason or "OBSERVATION_NOT_READY")

    def clear(self, *, reason: str) -> None:
        with self._lock:
            self._proposal = None
            self._reason = str(reason or "NO_EXECUTION_ELIGIBLE_CANDIDATE")

    def publish_intent(self, intent) -> ExecutionProposal:
        generated_at = intent.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        generated_ms = int(generated_at.timestamp() * 1000)
        expires_ms = generated_ms + self.proposal_ttl_seconds * 1000

        proposal_id = self._proposal_id(intent, generated_ms=generated_ms)
        proposal = ExecutionProposal.create(
            proposal_id=proposal_id,
            generated_at=generated_ms,
            expires_at=expires_ms,
            environment=self.environment,
            symbol=intent.symbol,
            direction=intent.direction,
            pattern=intent.pattern,
            entry_reference_price=intent.entry_price,
            candidate_observation_id=intent.candidate_observation_id,
            decision_batch_id=intent.decision_batch_id,
            market_event_id=intent.market_event_id,
            strategy_version=intent.strategy_version,
            strategy_variant_id=intent.strategy_variant_id,
            model_version=intent.model_version,
            selection_authority=intent.selection_authority,
            structure_fingerprint=intent.structure_fingerprint,
            advisory_risk_plan=intent.advisory_risk_plan,
            experiment_context=intent.experiment_context,
            paper_canary_model_id=intent.paper_canary_model_id,
            paper_risk_multiplier=intent.paper_risk_multiplier,
            paper_allocation_id=intent.paper_allocation_id,
        )
        with self._lock:
            self._proposal = proposal
            self._ready = True
            self._reason = "RECOMMENDATION_AVAILABLE"
        self._log(
            "info",
            "OBSERVATION_RECOMMENDATION_PUBLISHED | "
            f"proposal_id={proposal.proposal_id} | symbol={proposal.symbol} | "
            f"direction={proposal.direction} | expires_at={proposal.expires_at}",
        )
        return proposal

    def current(
        self,
        *,
        now_ms: int | None = None,
    ) -> tuple[ExecutionProposal | None, str]:
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        with self._lock:
            if not self._ready:
                return None, self._reason or "OBSERVATION_NOT_READY"
            proposal = self._proposal
            if proposal is None:
                return None, self._reason or "NO_EXECUTION_ELIGIBLE_CANDIDATE"
            if proposal.is_expired(now_ms=now_ms):
                self._proposal = None
                self._reason = "RECOMMENDATION_EXPIRED"
                return None, self._reason
            return proposal, "RECOMMENDATION_AVAILABLE"

    def readiness(self) -> tuple[bool, str]:
        with self._lock:
            return self._ready, self._reason

    def status_snapshot(self, *, now_ms: int | None = None) -> dict:
        """Return recommendation telemetry without changing recommendation state."""
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        with self._lock:
            ready = self._ready
            reason = self._reason
            proposal = self._proposal

            if not ready:
                return {
                    "status": "NOT_READY",
                    "reason": reason or "OBSERVATION_NOT_READY",
                    "proposal_present": False,
                    "proposal_id": None,
                    "proposal_age_seconds": None,
                    "expires_in_seconds": None,
                }

            if proposal is None:
                return {
                    "status": "NO_TRADE",
                    "reason": reason or "NO_EXECUTION_ELIGIBLE_CANDIDATE",
                    "proposal_present": False,
                    "proposal_id": None,
                    "proposal_age_seconds": None,
                    "expires_in_seconds": None,
                }

            expired = proposal.is_expired(now_ms=now_ms)
            return {
                "status": "NO_TRADE" if expired else "PROPOSAL",
                "reason": (
                    "RECOMMENDATION_EXPIRED"
                    if expired
                    else "RECOMMENDATION_AVAILABLE"
                ),
                "proposal_present": not expired,
                "proposal_id": (
                    None if expired else proposal.proposal_id
                ),
                "proposal_age_seconds": max(
                    0.0,
                    (now_ms - proposal.generated_at) / 1000.0,
                ),
                "expires_in_seconds": max(
                    0.0,
                    (proposal.expires_at - now_ms) / 1000.0,
                ),
            }

    def reject(self, proposal_id: str, *, reason: str | None = None) -> bool:
        proposal_id = str(proposal_id or "").strip()
        with self._lock:
            if self._proposal is None or self._proposal.proposal_id != proposal_id:
                return False
            self._proposal = None
            self._reason = str(reason or "EXECUTION_REJECTED_PROPOSAL")
        self._log(
            "info",
            "OBSERVATION_RECOMMENDATION_INVALIDATED | "
            f"proposal_id={proposal_id} | reason={self._reason}",
        )
        return True

    def _proposal_id(self, intent, *, generated_ms: int) -> str:
        identity = "|".join(
            [
                self.environment,
                str(intent.decision_batch_id or ""),
                str(intent.candidate_observation_id or ""),
                str(intent.market_event_id or ""),
                str(intent.symbol or ""),
                str(intent.direction or ""),
                str(intent.selection_authority or "RULES"),
                str(generated_ms if not intent.decision_batch_id else ""),
            ]
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24].upper()
        return f"PROP-{digest}"

    def _log(self, level: str, message: str) -> None:
        if self.system_log is None:
            return
        getattr(self.system_log, level, lambda *_args, **_kwargs: None)(message)
