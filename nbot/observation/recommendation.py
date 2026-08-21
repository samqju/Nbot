"""V3.5 recommendation snapshot and idempotent Observation control target.

The module is Observation-owned and has no exchange/order imports.  TESTNET may
emit an explicitly operational-only canary proposal from the latest complete
point-in-time event.  LIVE/PAPER fails closed until a Research Champion exists;
V3.5 never fabricates that deferred authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import threading
import time
from typing import Any, Callable

from nbot.communication.contracts import (
    ExecutionOutcome,
    ExecutionProposal,
    OutcomeAcknowledgement,
    TradeRequest,
    TradeResponse,
)
from nbot.communication.validation import canonical_json, payload_digest
from nbot.config.profiles import Profile

from .database import EvidenceDatabase


TESTNET_OPERATIONAL_CANARY_AUTHORITY = "TESTNET_OPERATIONAL_CANARY_V1"
TESTNET_OPERATIONAL_CANARY_SELECTOR = TESTNET_OPERATIONAL_CANARY_AUTHORITY
TESTNET_OPERATIONAL_CANARY_FEATURE_VERSION = "TESTNET_OPERATIONAL_CANARY_NO_RESEARCH_FEATURES_V1"
CONTROL_SCHEMA_VERSION = "NBOT_V3_OBSERVATION_CONTROL_V1"
DEFAULT_PROPOSAL_TTL_MS = 30_000
DEFAULT_MAX_REQUEST_AGE_MS = 30_000
DEFAULT_MAX_FUTURE_SKEW_MS = 5_000


CONTROL_SCHEMA = """
CREATE TABLE IF NOT EXISTS observation_recommendation_snapshots (
    profile TEXT PRIMARY KEY,
    market_environment TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('READY','NOT_READY')),
    reason TEXT,
    event_open_ms INTEGER,
    proposal_json TEXT,
    proposal_digest TEXT,
    refreshed_at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS control_trade_requests (
    request_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    execution_instance_id TEXT NOT NULL,
    requested_at_ms INTEGER NOT NULL,
    received_at_ms INTEGER NOT NULL,
    request_json TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    response_json TEXT NOT NULL,
    response_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS served_execution_proposals (
    proposal_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    market_environment TEXT NOT NULL,
    evidence_lineage TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    proposal_digest TEXT NOT NULL,
    first_served_at_ms INTEGER NOT NULL,
    last_served_at_ms INTEGER NOT NULL,
    served_count INTEGER NOT NULL CHECK (served_count > 0),
    invalidated_at_ms INTEGER,
    invalidation_reason TEXT,
    completed_outcome_id TEXT
);
CREATE TABLE IF NOT EXISTS execution_veto_feedback (
    proposal_id TEXT NOT NULL,
    execution_instance_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    received_at_ms INTEGER NOT NULL,
    PRIMARY KEY (proposal_id, execution_instance_id)
);
CREATE TABLE IF NOT EXISTS received_execution_outcomes (
    outcome_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    profile TEXT NOT NULL,
    market_environment TEXT NOT NULL,
    evidence_lineage TEXT NOT NULL,
    received_at_ms INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES served_execution_proposals(proposal_id)
);
CREATE INDEX IF NOT EXISTS idx_control_trade_requests_time
    ON control_trade_requests(received_at_ms);
CREATE INDEX IF NOT EXISTS idx_received_execution_outcomes_proposal
    ON received_execution_outcomes(proposal_id);
"""


class ObservationControlError(RuntimeError):
    """Recommendation/outcome control-plane invariant failed."""


@dataclass(frozen=True, slots=True)
class RecommendationSnapshot:
    status: str
    reason: str | None
    proposal: ExecutionProposal | None
    refreshed_at_ms: int


class RecommendationStore:
    def __init__(
        self,
        database: EvidenceDatabase,
        profile: Profile,
        *,
        proposal_ttl_ms: int = DEFAULT_PROPOSAL_TTL_MS,
    ) -> None:
        self.database = database
        self.profile = profile
        self.proposal_ttl_ms = int(proposal_ttl_ms)
        if self.proposal_ttl_ms <= 0 or self.proposal_ttl_ms > 5 * 60_000:
            raise ValueError("NBOT_RECOMMENDATION_TTL_INVALID")
        if profile.name == "live-trade":
            raise ValueError("NBOT_RECOMMENDATION_LIVE_TRADE_FORBIDDEN_BEFORE_V3_10")
        if database.config.market_environment != profile.market_environment:
            raise ValueError("NBOT_RECOMMENDATION_DATABASE_ENVIRONMENT_MISMATCH")
        self.initialize()

    def initialize(self) -> None:
        self.database.initialize()
        with self.database.connection() as conn:
            conn.executescript(CONTROL_SCHEMA)

    def _save_snapshot(self, snapshot: RecommendationSnapshot) -> None:
        proposal_json = None
        proposal_digest_value = None
        event_open_ms = None
        if snapshot.proposal is not None:
            payload = snapshot.proposal.to_dict()
            proposal_json = canonical_json(payload)
            proposal_digest_value = payload_digest(payload)
            try:
                event_open_ms = int(snapshot.proposal.market_event_id.removeprefix("ME-"))
            except ValueError as exc:
                raise ObservationControlError("RECOMMENDATION_MARKET_EVENT_ID_INVALID") from exc
        with self.database.connection() as conn:
            conn.execute(
                """
                INSERT INTO observation_recommendation_snapshots(
                    profile,market_environment,status,reason,event_open_ms,
                    proposal_json,proposal_digest,refreshed_at_ms
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(profile) DO UPDATE SET
                    market_environment=excluded.market_environment,
                    status=excluded.status,
                    reason=excluded.reason,
                    event_open_ms=excluded.event_open_ms,
                    proposal_json=excluded.proposal_json,
                    proposal_digest=excluded.proposal_digest,
                    refreshed_at_ms=excluded.refreshed_at_ms
                """,
                (
                    self.profile.name,
                    self.profile.market_environment,
                    snapshot.status,
                    snapshot.reason,
                    event_open_ms,
                    proposal_json,
                    proposal_digest_value,
                    snapshot.refreshed_at_ms,
                ),
            )

    def refresh(self, *, now_ms: int | None = None) -> RecommendationSnapshot:
        now = int(time.time() * 1000) if now_ms is None else int(now_ms)
        if now <= 0:
            raise ValueError("NBOT_RECOMMENDATION_NOW_INVALID")
        if self.profile.name == "live-paper":
            snapshot = self._refresh_live_paper_dry(now)
            self._save_snapshot(snapshot)
            return snapshot
        if self.profile.name != "testnet-trade":
            raise ObservationControlError("RECOMMENDATION_PROFILE_UNSUPPORTED")
        snapshot = self._refresh_testnet_canary(now)
        self._save_snapshot(snapshot)
        return snapshot

    def _refresh_live_paper_dry(self, now_ms: int) -> RecommendationSnapshot:
        """Fail closed until a valid Research Champion is explicitly wired.

        V3.8 is allowed to run operationally in non-promotional dry mode while
        research evidence is still maturing.  A Research Champion remains
        RESEARCH_ONLY_NO_EXECUTION and is never silently translated into paper
        execution authority by this foundation patch.
        """
        with self.database.connection() as conn:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_champions'"
            ).fetchone()
            if table is None:
                reason = "WAIT_FOR_VALID_RESEARCH_CHAMPION"
            else:
                row = conn.execute(
                    """
                    SELECT champion_version,selector_version,exit_policy_version,authority
                    FROM research_champions
                    ORDER BY promoted_at_ms DESC,champion_version DESC
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    reason = "WAIT_FOR_VALID_RESEARCH_CHAMPION"
                elif str(row[3]) != "RESEARCH_ONLY_NO_EXECUTION":
                    reason = "RESEARCH_CHAMPION_AUTHORITY_INVALID"
                else:
                    reason = "RESEARCH_CHAMPION_PRESENT_PROMOTIONAL_WIRING_NOT_ENABLED"
        return RecommendationSnapshot(
            status="NOT_READY",
            reason=reason,
            proposal=None,
            refreshed_at_ms=now_ms,
        )

    def _refresh_testnet_canary(self, now_ms: int) -> RecommendationSnapshot:
        with self.database.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    e.event_open_ms,e.event_close_ms,e.captured_at_ms,e.collector_version,
                    p.evidence_mode,p.context_complete,p.membership_quality,
                    u.symbol,u.universe_rank,
                    c.close_price,c.open_price,c.high_price,c.low_price,c.quote_volume,
                    s.bid_price,s.ask_price,s.spread_pct,s.quote_volume_24h_usd
                FROM market_events e
                JOIN event_provenance p ON p.event_open_ms=e.event_open_ms
                JOIN universe_membership u ON u.event_open_ms=e.event_open_ms
                JOIN candles_5m c
                  ON c.event_open_ms=e.event_open_ms AND c.symbol=u.symbol
                JOIN market_snapshots s
                  ON s.event_open_ms=e.event_open_ms AND s.symbol=u.symbol
                WHERE e.status='COMPLETE'
                  AND p.evidence_mode='LIVE_POINT_IN_TIME'
                  AND p.context_complete=1
                ORDER BY e.event_open_ms DESC,u.universe_rank ASC,u.symbol ASC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return RecommendationSnapshot(
                status="NOT_READY",
                reason="TESTNET_CANONICAL_EVENT_NOT_AVAILABLE",
                proposal=None,
                refreshed_at_ms=now_ms,
            )
        (
            event_open_ms,
            event_close_ms,
            captured_at_ms,
            collector_version,
            evidence_mode,
            context_complete,
            membership_quality,
            symbol_value,
            universe_rank,
            close_price,
            open_price,
            high_price,
            low_price,
            quote_volume,
            bid_price,
            ask_price,
            spread_pct,
            quote_volume_24h_usd,
        ) = row
        source_material = {
            "event": [
                int(event_open_ms),
                int(event_close_ms),
                int(captured_at_ms),
                str(collector_version),
                str(evidence_mode),
                int(context_complete),
                str(membership_quality),
            ],
            "universe": [str(symbol_value), int(universe_rank)],
            "candle": [
                float(open_price),
                float(high_price),
                float(low_price),
                float(close_price),
                float(quote_volume),
            ],
            "snapshot": [
                float(bid_price),
                float(ask_price),
                float(spread_pct),
                float(quote_volume_24h_usd),
            ],
            "authority": TESTNET_OPERATIONAL_CANARY_AUTHORITY,
        }
        source_digest = payload_digest(source_material)
        generated_at_ms = int(captured_at_ms)
        expires_at_ms = generated_at_ms + self.proposal_ttl_ms
        if now_ms > expires_at_ms:
            return RecommendationSnapshot(
                status="NOT_READY",
                reason="TESTNET_LATEST_CANONICAL_EVENT_STALE",
                proposal=None,
                refreshed_at_ms=now_ms,
            )
        side_hash = hashlib.sha256(
            f"{event_open_ms}|{symbol_value}|{TESTNET_OPERATIONAL_CANARY_AUTHORITY}".encode("utf-8")
        ).digest()
        side = "LONG" if side_hash[0] % 2 == 0 else "SHORT"
        score = int.from_bytes(side_hash[:8], "big") / float((1 << 64) - 1)
        reference_price = (float(bid_price) + float(ask_price)) / 2.0
        if not math.isfinite(reference_price) or reference_price <= 0:
            raise ObservationControlError("TESTNET_CANARY_REFERENCE_PRICE_INVALID")
        identity = "|".join(
            (
                self.profile.name,
                str(event_open_ms),
                str(symbol_value),
                side,
                TESTNET_OPERATIONAL_CANARY_AUTHORITY,
                source_digest,
            )
        )
        proposal_id = "PROP-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:40]
        proposal = ExecutionProposal.create(
            proposal_id=proposal_id,
            generated_at_ms=generated_at_ms,
            expires_at_ms=expires_at_ms,
            profile=self.profile.name,
            market_environment=self.profile.market_environment,
            evidence_lineage=self.profile.evidence_lineage,
            symbol=str(symbol_value),
            side=side,
            market_event_id=f"ME-{int(event_open_ms)}",
            data_generation_id=(
                f"TESTNET-{int(event_open_ms)}-{source_digest[:16]}"
            ),
            feature_version=TESTNET_OPERATIONAL_CANARY_FEATURE_VERSION,
            selector_version=TESTNET_OPERATIONAL_CANARY_SELECTOR,
            entry_authority=TESTNET_OPERATIONAL_CANARY_AUTHORITY,
            exit_policy_version="INTEGER_R_STEP_CONTROL",
            reference_price=reference_price,
            selection_score=score,
            selection_rank=1,
            expected_after_cost_net_r=None,
            source_digest=source_digest,
            model_digest=None,
            experiment_context={
                "authority_class": "TESTNET_OPERATIONAL_ONLY",
                "research_evidence": False,
                "economic_claim": False,
                "universe_rank": int(universe_rank),
                "reference_bid": float(bid_price),
                "reference_ask": float(ask_price),
                "spread_pct": float(spread_pct),
                "collector_version": str(collector_version),
            },
        )
        return RecommendationSnapshot(
            status="READY",
            reason=None,
            proposal=proposal,
            refreshed_at_ms=now_ms,
        )

    def current(self) -> RecommendationSnapshot:
        with self.database.connection() as conn:
            row = conn.execute(
                """
                SELECT status,reason,proposal_json,proposal_digest,refreshed_at_ms
                FROM observation_recommendation_snapshots
                WHERE profile=?
                """,
                (self.profile.name,),
            ).fetchone()
        if row is None:
            return RecommendationSnapshot("NOT_READY", "SNAPSHOT_NOT_BUILT", None, 1)
        status, reason, proposal_json, proposal_digest_value, refreshed_at_ms = row
        proposal = None
        if proposal_json is not None:
            try:
                payload = json.loads(str(proposal_json))
            except json.JSONDecodeError as exc:
                raise ObservationControlError("RECOMMENDATION_SNAPSHOT_JSON_CORRUPT") from exc
            if payload_digest(payload) != str(proposal_digest_value):
                raise ObservationControlError("RECOMMENDATION_SNAPSHOT_DIGEST_MISMATCH")
            proposal = ExecutionProposal.from_dict(payload)
        return RecommendationSnapshot(str(status), reason, proposal, int(refreshed_at_ms))


class ObservationControlTarget:
    """Small synchronous request target backed by durable Observation tables."""

    def __init__(
        self,
        database: EvidenceDatabase,
        profile: Profile,
        *,
        release_sha: str,
        now_ms: Callable[[], int] | None = None,
        proposal_ttl_ms: int = DEFAULT_PROPOSAL_TTL_MS,
        max_request_age_ms: int = DEFAULT_MAX_REQUEST_AGE_MS,
        max_future_skew_ms: int = DEFAULT_MAX_FUTURE_SKEW_MS,
    ) -> None:
        from nbot.communication.validation import git_sha

        self.database = database
        self.profile = profile
        self.release_sha = git_sha(release_sha, "observation_release_sha")
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.max_request_age_ms = int(max_request_age_ms)
        self.max_future_skew_ms = int(max_future_skew_ms)
        if self.max_request_age_ms <= 0 or self.max_future_skew_ms < 0:
            raise ValueError("NBOT_CONTROL_REQUEST_TIME_LIMIT_INVALID")
        self.recommendations = RecommendationStore(
            database,
            profile,
            proposal_ttl_ms=proposal_ttl_ms,
        )
        self.store_id = "OBS-" + hashlib.sha256(
            f"{database.config.database_path}|{profile.market_environment}|{CONTROL_SCHEMA_VERSION}".encode("utf-8")
        ).hexdigest()[:24]

    def refresh_recommendation(self) -> RecommendationSnapshot:
        return self.recommendations.refresh(now_ms=self._validated_now())

    def _validated_now(self) -> int:
        value = self._now_ms()
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ObservationControlError("CONTROL_NOW_MS_INVALID")
        return value

    def health_snapshot(self) -> dict[str, Any]:
        snapshot = self.recommendations.current()
        return {
            "status": "READY" if snapshot.status == "READY" else "NOT_READY",
            "reason": snapshot.reason,
            "profile": self.profile.name,
            "market_environment": self.profile.market_environment,
            "evidence_lineage": self.profile.evidence_lineage,
            "protocol_version": "NBOT_V3_EXECUTION_V1",
            "release_sha": self.release_sha,
            "recommendation_authority": (
                None if snapshot.proposal is None else snapshot.proposal.entry_authority
            ),
            "order_authority": "NONE",
            "store_id": self.store_id,
        }

    def _stored_request_response(self, request: TradeRequest) -> TradeResponse | None:
        request_payload = request.to_dict()
        request_digest = payload_digest(request_payload)
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT request_digest,response_json,response_digest FROM control_trade_requests WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
        if row is None:
            return None
        if str(row[0]) != request_digest:
            raise ObservationControlError("CONTROL_REQUEST_ID_COLLISION")
        try:
            payload = json.loads(str(row[1]))
        except json.JSONDecodeError as exc:
            raise ObservationControlError("CONTROL_STORED_RESPONSE_CORRUPT") from exc
        if payload_digest(payload) != str(row[2]):
            raise ObservationControlError("CONTROL_STORED_RESPONSE_DIGEST_MISMATCH")
        return TradeResponse.from_dict(payload)

    def _record_request_response(
        self,
        request: TradeRequest,
        response: TradeResponse,
        *,
        received_at_ms: int,
    ) -> None:
        request_payload = request.to_dict()
        response_payload = response.to_dict()
        with self.database.connection() as conn:
            conn.execute(
                """
                INSERT INTO control_trade_requests(
                    request_id,profile,execution_instance_id,requested_at_ms,
                    received_at_ms,request_json,request_digest,response_json,response_digest
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    request.request_id,
                    request.profile,
                    request.execution_instance_id,
                    request.requested_at_ms,
                    received_at_ms,
                    canonical_json(request_payload),
                    payload_digest(request_payload),
                    canonical_json(response_payload),
                    payload_digest(response_payload),
                ),
            )

    def _record_veto(self, request: TradeRequest, now_ms: int) -> None:
        if request.previous_proposal_id is None:
            return
        with self.database.connection() as conn:
            proposal = conn.execute(
                "SELECT proposal_id FROM served_execution_proposals WHERE proposal_id=?",
                (request.previous_proposal_id,),
            ).fetchone()
            if proposal is None:
                raise ObservationControlError("CONTROL_PREVIOUS_PROPOSAL_UNKNOWN")
            conn.execute(
                """
                INSERT INTO execution_veto_feedback(
                    proposal_id,execution_instance_id,request_id,reason,received_at_ms
                ) VALUES (?,?,?,?,?)
                ON CONFLICT(proposal_id,execution_instance_id) DO UPDATE SET
                    request_id=excluded.request_id,
                    reason=excluded.reason,
                    received_at_ms=excluded.received_at_ms
                """,
                (
                    request.previous_proposal_id,
                    request.execution_instance_id,
                    request.request_id,
                    request.previous_rejection_reason or request.previous_proposal_result or "NOT_EXECUTED",
                    now_ms,
                ),
            )
            conn.execute(
                """
                UPDATE served_execution_proposals
                SET invalidated_at_ms=COALESCE(invalidated_at_ms,?),
                    invalidation_reason=COALESCE(invalidation_reason,?)
                WHERE proposal_id=?
                """,
                (
                    now_ms,
                    request.previous_rejection_reason or request.previous_proposal_result,
                    request.previous_proposal_id,
                ),
            )

    def _serve_proposal(self, proposal: ExecutionProposal, now_ms: int) -> None:
        proposal_payload = proposal.to_dict()
        proposal_json = canonical_json(proposal_payload)
        proposal_digest_value = payload_digest(proposal_payload)
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT proposal_digest,invalidated_at_ms,completed_outcome_id FROM served_execution_proposals WHERE proposal_id=?",
                (proposal.proposal_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO served_execution_proposals(
                        proposal_id,profile,market_environment,evidence_lineage,
                        proposal_json,proposal_digest,first_served_at_ms,last_served_at_ms,served_count
                    ) VALUES (?,?,?,?,?,?,?,?,1)
                    """,
                    (
                        proposal.proposal_id,
                        proposal.profile,
                        proposal.market_environment,
                        proposal.evidence_lineage,
                        proposal_json,
                        proposal_digest_value,
                        now_ms,
                        now_ms,
                    ),
                )
                return
            if str(row[0]) != proposal_digest_value:
                raise ObservationControlError("CONTROL_PROPOSAL_ID_COLLISION")
            if row[1] is not None:
                raise ObservationControlError("CONTROL_PROPOSAL_INVALIDATED")
            if row[2] is not None:
                raise ObservationControlError("CONTROL_PROPOSAL_ALREADY_COMPLETED")
            conn.execute(
                """
                UPDATE served_execution_proposals
                SET last_served_at_ms=?, served_count=served_count+1
                WHERE proposal_id=?
                """,
                (now_ms, proposal.proposal_id),
            )

    def handle_trade_request(self, request: TradeRequest) -> TradeResponse:
        if not isinstance(request, TradeRequest):
            raise TypeError("CONTROL_TRADE_REQUEST_TYPE_INVALID")
        existing = self._stored_request_response(request)
        if existing is not None:
            return existing
        now = self._validated_now()
        if request.profile != self.profile.name:
            response = TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="PROFILE_MISMATCH",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        if request.market_environment != self.profile.market_environment or request.execution_mode != self.profile.execution_mode:
            response = TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="ENVIRONMENT_OR_MODE_MISMATCH",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        if request.execution_release_sha != self.release_sha:
            response = TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="RELEASE_MISMATCH",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        if request.requested_at_ms > now + self.max_future_skew_ms:
            response = TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="REQUEST_CLOCK_SKEW_FUTURE",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        if now - request.requested_at_ms > self.max_request_age_ms:
            response = TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="REQUEST_STALE",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        self._record_veto(request, now)
        snapshot = self.recommendations.current()
        if snapshot.status != "READY" or snapshot.proposal is None:
            response = TradeResponse.not_ready(
                request_id=request.request_id,
                responded_at_ms=now,
                reason=snapshot.reason or "RECOMMENDATION_NOT_READY",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        proposal = snapshot.proposal
        if proposal.is_expired(now_ms=now):
            response = TradeResponse.no_trade(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="RECOMMENDATION_EXPIRED",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        with self.database.connection() as conn:
            status = conn.execute(
                "SELECT invalidated_at_ms,completed_outcome_id FROM served_execution_proposals WHERE proposal_id=?",
                (proposal.proposal_id,),
            ).fetchone()
        if status is not None and status[0] is not None:
            response = TradeResponse.no_trade(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="RECOMMENDATION_PREVIOUSLY_REJECTED",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        if status is not None and status[1] is not None:
            response = TradeResponse.no_trade(
                request_id=request.request_id,
                responded_at_ms=now,
                reason="RECOMMENDATION_ALREADY_COMPLETED",
            )
            self._record_request_response(request, response, received_at_ms=now)
            return response
        self._serve_proposal(proposal, now)
        response = TradeResponse.proposal_response(
            request_id=request.request_id,
            responded_at_ms=now,
            proposal=proposal,
        )
        self._record_request_response(request, response, received_at_ms=now)
        return response

    def receive_execution_outcome(self, outcome: ExecutionOutcome) -> OutcomeAcknowledgement:
        if not isinstance(outcome, ExecutionOutcome):
            raise TypeError("CONTROL_EXECUTION_OUTCOME_TYPE_INVALID")
        now = self._validated_now()
        if (
            outcome.profile != self.profile.name
            or outcome.market_environment != self.profile.market_environment
            or outcome.execution_mode != self.profile.execution_mode
            or outcome.evidence_lineage != self.profile.evidence_lineage
        ):
            raise ObservationControlError("CONTROL_OUTCOME_PROFILE_LINEAGE_MISMATCH")
        payload = outcome.to_dict()
        outcome_digest = payload_digest(payload)
        with self.database.connection() as conn:
            prior = conn.execute(
                "SELECT payload_digest FROM received_execution_outcomes WHERE outcome_id=?",
                (outcome.outcome_id,),
            ).fetchone()
            if prior is not None:
                if str(prior[0]) != outcome_digest:
                    raise ObservationControlError("CONTROL_OUTCOME_ID_COLLISION")
                return OutcomeAcknowledgement.create(
                    outcome_id=outcome.outcome_id,
                    status="ALREADY_RECORDED",
                    recorded_at_ms=now,
                    observation_store_id=self.store_id,
                )
            proposal_row = conn.execute(
                """
                SELECT proposal_json,proposal_digest,invalidated_at_ms,completed_outcome_id
                FROM served_execution_proposals WHERE proposal_id=?
                """,
                (outcome.proposal_id,),
            ).fetchone()
            if proposal_row is None:
                raise ObservationControlError("CONTROL_OUTCOME_PROPOSAL_UNKNOWN")
            if proposal_row[2] is not None:
                raise ObservationControlError("CONTROL_OUTCOME_FOR_INVALIDATED_PROPOSAL")
            if proposal_row[3] is not None and str(proposal_row[3]) != outcome.outcome_id:
                raise ObservationControlError("CONTROL_PROPOSAL_MULTIPLE_OUTCOMES")
            try:
                proposal_payload = json.loads(str(proposal_row[0]))
            except json.JSONDecodeError as exc:
                raise ObservationControlError("CONTROL_PROPOSAL_REGISTRY_CORRUPT") from exc
            if payload_digest(proposal_payload) != str(proposal_row[1]):
                raise ObservationControlError("CONTROL_PROPOSAL_REGISTRY_DIGEST_MISMATCH")
            proposal = ExecutionProposal.from_dict(proposal_payload)
            matching = (
                outcome.profile == proposal.profile
                and outcome.market_environment == proposal.market_environment
                and outcome.evidence_lineage == proposal.evidence_lineage
                and outcome.symbol == proposal.symbol
                and outcome.side == proposal.side
                and outcome.market_event_id == proposal.market_event_id
                and outcome.feature_version == proposal.feature_version
                and outcome.selector_version == proposal.selector_version
                and outcome.entry_authority == proposal.entry_authority
                and outcome.exit_policy_version == proposal.exit_policy_version
                and math.isclose(outcome.reference_price, proposal.reference_price, rel_tol=1e-12, abs_tol=1e-12)
                and math.isclose(outcome.selection_score, proposal.selection_score, rel_tol=1e-12, abs_tol=1e-12)
                and outcome.selection_rank == proposal.selection_rank
                and outcome.expected_after_cost_net_r == proposal.expected_after_cost_net_r
                and outcome.proposal_source_digest == proposal.source_digest
                and outcome.proposal_model_digest == proposal.model_digest
            )
            if not matching:
                raise ObservationControlError("CONTROL_OUTCOME_PROPOSAL_METADATA_MISMATCH")
            request_row = conn.execute(
                "SELECT response_json FROM control_trade_requests WHERE request_id=?",
                (outcome.request_id,),
            ).fetchone()
            if request_row is None:
                raise ObservationControlError("CONTROL_OUTCOME_REQUEST_UNKNOWN")
            try:
                response_payload = json.loads(str(request_row[0]))
            except json.JSONDecodeError as exc:
                raise ObservationControlError("CONTROL_OUTCOME_REQUEST_RESPONSE_CORRUPT") from exc
            response = TradeResponse.from_dict(response_payload)
            if response.proposal is None or response.proposal.proposal_id != outcome.proposal_id:
                raise ObservationControlError("CONTROL_OUTCOME_REQUEST_PROPOSAL_MISMATCH")
            conn.execute(
                """
                INSERT INTO received_execution_outcomes(
                    outcome_id,proposal_id,request_id,profile,market_environment,
                    evidence_lineage,received_at_ms,payload_json,payload_digest
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    outcome.outcome_id,
                    outcome.proposal_id,
                    outcome.request_id,
                    outcome.profile,
                    outcome.market_environment,
                    outcome.evidence_lineage,
                    now,
                    canonical_json(payload),
                    outcome_digest,
                ),
            )
            conn.execute(
                "UPDATE served_execution_proposals SET completed_outcome_id=? WHERE proposal_id=?",
                (outcome.outcome_id, outcome.proposal_id),
            )
        return OutcomeAcknowledgement.create(
            outcome_id=outcome.outcome_id,
            status="RECORDED",
            recorded_at_ms=now,
            observation_store_id=self.store_id,
        )

    def audit(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "healthy": False,
            "request_digest_mismatches": 0,
            "response_digest_mismatches": 0,
            "proposal_digest_mismatches": 0,
            "outcome_digest_mismatches": 0,
            "outcomes_without_proposal": 0,
            "multiple_outcomes_per_proposal": 0,
            "order_authority": "NONE",
        }
        with self.database.connection() as conn:
            for row in conn.execute(
                "SELECT request_json,request_digest,response_json,response_digest FROM control_trade_requests"
            ):
                try:
                    request_payload = json.loads(str(row[0]))
                    response_payload = json.loads(str(row[2]))
                except json.JSONDecodeError:
                    report["request_digest_mismatches"] += 1
                    report["response_digest_mismatches"] += 1
                    continue
                if payload_digest(request_payload) != str(row[1]):
                    report["request_digest_mismatches"] += 1
                if payload_digest(response_payload) != str(row[3]):
                    report["response_digest_mismatches"] += 1
            for row in conn.execute(
                "SELECT proposal_json,proposal_digest FROM served_execution_proposals"
            ):
                try:
                    proposal_payload = json.loads(str(row[0]))
                except json.JSONDecodeError:
                    report["proposal_digest_mismatches"] += 1
                    continue
                if payload_digest(proposal_payload) != str(row[1]):
                    report["proposal_digest_mismatches"] += 1
            for row in conn.execute(
                "SELECT proposal_id,payload_json,payload_digest FROM received_execution_outcomes"
            ):
                try:
                    outcome_payload = json.loads(str(row[1]))
                except json.JSONDecodeError:
                    report["outcome_digest_mismatches"] += 1
                    continue
                if payload_digest(outcome_payload) != str(row[2]):
                    report["outcome_digest_mismatches"] += 1
                if conn.execute(
                    "SELECT 1 FROM served_execution_proposals WHERE proposal_id=?",
                    (row[0],),
                ).fetchone() is None:
                    report["outcomes_without_proposal"] += 1
            report["multiple_outcomes_per_proposal"] = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT proposal_id,COUNT(*) AS n
                        FROM received_execution_outcomes
                        GROUP BY proposal_id HAVING n>1
                    )
                    """
                ).fetchone()[0]
            )
            report["requests"] = int(conn.execute("SELECT COUNT(*) FROM control_trade_requests").fetchone()[0])
            report["served_proposals"] = int(conn.execute("SELECT COUNT(*) FROM served_execution_proposals").fetchone()[0])
            report["veto_feedback"] = int(conn.execute("SELECT COUNT(*) FROM execution_veto_feedback").fetchone()[0])
            report["received_outcomes"] = int(conn.execute("SELECT COUNT(*) FROM received_execution_outcomes").fetchone()[0])
        report["healthy"] = all(
            int(report[key]) == 0
            for key in (
                "request_digest_mismatches",
                "response_digest_mismatches",
                "proposal_digest_mismatches",
                "outcome_digest_mismatches",
                "outcomes_without_proposal",
                "multiple_outcomes_per_proposal",
            )
        )
        return report


class RecommendationSupervisor:
    """Tiny periodic snapshot refresher isolated from HTTP request handlers."""

    def __init__(
        self,
        target: ObservationControlTarget,
        *,
        refresh_seconds: float = 1.0,
    ) -> None:
        value = float(refresh_seconds)
        if not (0.2 <= value <= 60.0):
            raise ValueError("NBOT_RECOMMENDATION_REFRESH_INTERVAL_INVALID")
        self.target = target
        self.refresh_seconds = value
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("NBOT_RECOMMENDATION_SUPERVISOR_ALREADY_STARTED")
        self._stop.clear()
        self.target.refresh_recommendation()
        self._thread = threading.Thread(
            target=self._run,
            name="nbot-recommendation-refresh",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.refresh_seconds):
            try:
                self.target.refresh_recommendation()
                self.last_error = None
            except Exception as exc:  # fail closed; HTTP health remains visible
                self.last_error = f"{type(exc).__name__}:{exc}"

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=max(2.0, self.refresh_seconds * 2.0))
