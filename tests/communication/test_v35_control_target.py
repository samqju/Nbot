from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from nbot.communication.contracts import ExecutionOutcome, TradeRequest
from nbot.communication.validation import payload_digest
from nbot.config.profiles import get_profile
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.recommendation import (
    ObservationControlError,
    ObservationControlTarget,
    TESTNET_OPERATIONAL_CANARY_AUTHORITY,
)


NOW = 1_800_000_000_000
SHA = "a" * 40


def database(root: Path, profile_name: str) -> EvidenceDatabase:
    profile = get_profile(profile_name)
    db = EvidenceDatabase(observation_config_for_profile(profile))
    leaf = "testnet" if profile.market_environment == "TESTNET" else "live"
    db.path = root / "data" / "observation" / leaf / "observer.db"
    db.initialize()
    return db


def seed_event(db: EvidenceDatabase, *, captured_at_ms: int = NOW, symbol: str = "BTCUSDT") -> int:
    event_open_ms = ((captured_at_ms // 300_000) - 1) * 300_000
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO market_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event_open_ms,
                event_open_ms + 299_999,
                captured_at_ms,
                1,
                1,
                0,
                "COMPLETE",
                "TEST-COLLECTOR",
                10,
            ),
        )
        conn.execute(
            "INSERT INTO event_provenance VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                event_open_ms,
                "LIVE_POINT_IN_TIME",
                1,
                "POINT_IN_TIME",
                event_open_ms,
                captured_at_ms - 20,
                captured_at_ms - 10,
                captured_at_ms - 30,
                captured_at_ms,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO universe_membership VALUES (?,?,?,?,?)",
            (event_open_ms, symbol, 1, "POINT_IN_TIME", event_open_ms),
        )
        conn.execute(
            "INSERT INTO candles_5m VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_open_ms,
                symbol,
                event_open_ms,
                event_open_ms + 299_999,
                100.0,
                101.0,
                99.0,
                100.5,
                10.0,
                1_005.0,
                100,
                5.0,
                502.5,
            ),
        )
        conn.execute(
            "INSERT INTO market_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_open_ms,
                symbol,
                1,
                10_000_000.0,
                100.4,
                100.6,
                0.1992,
                100.5,
                100.5,
                0.0,
                event_open_ms + 3_600_000,
                captured_at_ms,
            ),
        )
    return event_open_ms


def request(*, request_id="REQ-1", execution_instance_id="EXEC-1", **kwargs):
    values = dict(
        request_id=request_id,
        requested_at_ms=NOW,
        profile="testnet-trade",
        market_environment="TESTNET",
        execution_mode="TRADE",
        execution_state="FLAT",
        execution_instance_id=execution_instance_id,
        execution_release_sha=SHA,
    )
    values.update(kwargs)
    return TradeRequest.create(**values)


def outcome_from(proposal, *, request_id="REQ-1", outcome_id="OUT-1", **kwargs):
    values = dict(
        outcome_id=outcome_id,
        proposal_id=proposal.proposal_id,
        request_id=request_id,
        profile=proposal.profile,
        market_environment=proposal.market_environment,
        execution_mode="TRADE",
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
        entry_price=100.5,
        exit_price=101.0,
        quantity=1.0,
        initial_risk_usd=10.0,
        realized_pnl_usd=0.5,
        r_multiple=0.05,
        mae_usd=-1.0,
        mfe_usd=2.0,
        mae_r=-0.1,
        mfe_r=0.2,
        entry_timestamp_ms=NOW + 1_000,
        closed_timestamp_ms=NOW + 61_000,
        holding_seconds=60,
        exit_reason="TEST_CLOSE",
        close_source="TEST",
        execution_payload_digest="d" * 64,
    )
    values.update(kwargs)
    return ExecutionOutcome.create(**values)


class V35ControlTargetTests(unittest.TestCase):
    def test_live_paper_fails_closed_without_deferred_research_champion(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "live-paper")
            target = ObservationControlTarget(
                db,
                get_profile("live-paper"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            snapshot = target.refresh_recommendation()
            self.assertEqual(snapshot.status, "NOT_READY")
            self.assertEqual(snapshot.reason, "WAIT_FOR_VALID_RESEARCH_CHAMPION")
            health = target.health_snapshot()
            self.assertEqual(health["order_authority"], "NONE")
            self.assertIsNone(health["recommendation_authority"])

    def test_testnet_snapshot_is_explicit_operational_only_canary(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            event = seed_event(db)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            snapshot = target.refresh_recommendation()
            self.assertEqual(snapshot.status, "READY")
            proposal = snapshot.proposal
            self.assertIsNotNone(proposal)
            assert proposal is not None
            self.assertEqual(proposal.entry_authority, TESTNET_OPERATIONAL_CANARY_AUTHORITY)
            self.assertEqual(proposal.selector_version, TESTNET_OPERATIONAL_CANARY_AUTHORITY)
            self.assertEqual(proposal.market_event_id, f"ME-{event}")
            self.assertIsNone(proposal.expected_after_cost_net_r)
            self.assertFalse(proposal.experiment_context["research_evidence"])
            self.assertFalse(proposal.experiment_context["economic_claim"])

    def test_stale_testnet_event_is_not_refreshed_into_a_fresh_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            seed_event(db, captured_at_ms=NOW - 60_000)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            snapshot = target.refresh_recommendation()
            self.assertEqual(snapshot.status, "NOT_READY")
            self.assertEqual(snapshot.reason, "TESTNET_LATEST_CANONICAL_EVENT_STALE")

    def test_release_mismatch_returns_not_ready_without_serving_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            seed_event(db)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            target.refresh_recommendation()
            bad = TradeRequest.create(
                request_id="REQ-BAD",
                requested_at_ms=NOW,
                profile="testnet-trade",
                market_environment="TESTNET",
                execution_mode="TRADE",
                execution_state="FLAT",
                execution_instance_id="EXEC-1",
                execution_release_sha="b" * 40,
            )
            response = target.handle_trade_request(bad)
            self.assertEqual(response.status, "NOT_READY")
            self.assertEqual(response.reason, "RELEASE_MISMATCH")
            self.assertEqual(target.audit()["served_proposals"], 0)

    def test_duplicate_request_id_is_idempotent_and_collision_fails(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            seed_event(db)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            target.refresh_recommendation()
            first = target.handle_trade_request(request())
            second = target.handle_trade_request(request())
            self.assertEqual(first, second)
            with self.assertRaisesRegex(ObservationControlError, "REQUEST_ID_COLLISION"):
                target.handle_trade_request(request(execution_instance_id="EXEC-OTHER"))

    def test_veto_feedback_invalidates_current_proposal_without_recording_loss(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            seed_event(db)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            target.refresh_recommendation()
            first = target.handle_trade_request(request())
            self.assertEqual(first.status, "PROPOSAL")
            assert first.proposal is not None
            rejected = request(
                request_id="REQ-2",
                previous_proposal_id=first.proposal.proposal_id,
                previous_proposal_result="REJECTED",
                previous_rejection_reason="SPREAD_TOO_WIDE",
            )
            second = target.handle_trade_request(rejected)
            self.assertEqual(second.status, "NO_TRADE")
            self.assertEqual(second.reason, "RECOMMENDATION_PREVIOUSLY_REJECTED")
            audit = target.audit()
            self.assertEqual(audit["veto_feedback"], 1)
            self.assertEqual(audit["received_outcomes"], 0)

    def test_outcome_is_idempotent_and_metadata_bound_to_served_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            seed_event(db)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW + 100_000,
                max_request_age_ms=200_000,
            )
            # Build snapshot at original decision time then advance target clock.
            target.recommendations.refresh(now_ms=NOW)
            target._now_ms = lambda: NOW + 10_000
            response = target.handle_trade_request(
                request(requested_at_ms=NOW + 10_000)
            )
            self.assertEqual(response.status, "PROPOSAL")
            assert response.proposal is not None
            item = outcome_from(response.proposal)
            first = target.receive_execution_outcome(item)
            second = target.receive_execution_outcome(item)
            self.assertEqual(first.status, "RECORDED")
            self.assertEqual(second.status, "ALREADY_RECORDED")
            audit = target.audit()
            self.assertTrue(audit["healthy"])
            self.assertEqual(audit["received_outcomes"], 1)
            with self.assertRaisesRegex(ObservationControlError, "OUTCOME_ID_COLLISION"):
                target.receive_execution_outcome(
                    outcome_from(response.proposal, realized_pnl_usd=9.0)
                )

    def test_wrong_proposal_metadata_in_outcome_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            seed_event(db)
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            target.refresh_recommendation()
            response = target.handle_trade_request(request())
            assert response.proposal is not None
            with self.assertRaisesRegex(ObservationControlError, "PROPOSAL_METADATA_MISMATCH"):
                target.receive_execution_outcome(
                    outcome_from(response.proposal, selection_score=response.proposal.selection_score + 1.0)
                )

    def test_control_audit_never_reports_order_authority(self):
        with tempfile.TemporaryDirectory() as td:
            db = database(Path(td), "testnet-trade")
            target = ObservationControlTarget(
                db,
                get_profile("testnet-trade"),
                release_sha=SHA,
                now_ms=lambda: NOW,
            )
            audit = target.audit()
            self.assertTrue(audit["healthy"])
            self.assertEqual(audit["order_authority"], "NONE")
