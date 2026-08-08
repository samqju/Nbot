"""Observation-side idempotent receiver for completed execution outcomes."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from communication.execution_outcome import ExecutionOutcome
from communication.responses import OutcomeAcknowledgement
from strategy.candidate_outcome import CandidateOutcomeWriter


class LocalExecutionOutcomeReceiver:
    """Record execution evidence locally using the existing learning writer.

    This is the Phase 6A.0.3 local bridge. A later HTTP receiver can expose the
    same receive(outcome) boundary without changing PositionLifecycle or
    ReconciliationLifecycle.
    """

    def __init__(
        self,
        *,
        candidate_outcomes_path: str,
        environment: str,
        execution_mode: str,
        system_log=None,
    ):
        self.path = Path(candidate_outcomes_path)
        self.environment = str(environment).strip().upper()
        self.execution_mode = str(execution_mode).strip().upper()
        self.system_log = system_log
        self.writer = CandidateOutcomeWriter(
            str(self.path),
            system_log=system_log,
            environment=self.environment,
            execution_mode=self.execution_mode,
        )
        self._lock = threading.Lock()
        self._seen_outcome_ids: set[str] = set()
        self._seen_executed_candidate_ids: set[str] = set()
        self._load_existing_execution_evidence()

    def _load_existing_execution_evidence(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(row.get("outcome_type") or "").upper() != "EXECUTED_TRADE":
                        continue
                    candidate_id = row.get("candidate_observation_id")
                    if candidate_id:
                        self._seen_executed_candidate_ids.add(str(candidate_id))
                    payload = row.get("payload") or {}
                    outcome_id = payload.get("execution_outcome_id")
                    if outcome_id:
                        self._seen_outcome_ids.add(str(outcome_id))
        except OSError:
            return

    def receive(self, outcome: ExecutionOutcome) -> OutcomeAcknowledgement:
        if not isinstance(outcome, ExecutionOutcome):
            raise TypeError("OBSERVATION_EXECUTION_OUTCOME_INVALID")
        if outcome.environment != self.environment:
            raise ValueError("OBSERVATION_OUTCOME_ENVIRONMENT_MISMATCH")
        if outcome.execution_mode != self.execution_mode:
            raise ValueError("OBSERVATION_OUTCOME_EXECUTION_MODE_MISMATCH")

        # ThreadingHTTPServer may deliver the same retry concurrently. Keep
        # duplicate detection and the learning append in one critical section.
        with self._lock:
            already_recorded = outcome.outcome_id in self._seen_outcome_ids
            if (
                outcome.candidate_observation_id
                and outcome.candidate_observation_id
                in self._seen_executed_candidate_ids
            ):
                already_recorded = True

            if already_recorded:
                return OutcomeAcknowledgement.create(
                    outcome_id=outcome.outcome_id,
                    acknowledged_at=int(time.time() * 1000),
                    status="ALREADY_RECORDED",
                )

            if outcome.candidate_observation_id:
                context = outcome.experiment_context
                paper_variant = (
                    (context or {}).get("paper_policy", {}).get("variant_id")
                )
                paper_model_id = outcome.paper_canary_model_id
                if (
                    paper_model_id is None
                    and outcome.selection_authority
                    in {"PAPER_CANARY", "PAPER_CHAMPION"}
                ):
                    paper_model_id = outcome.model_version
                self.writer.append(
                    observation_id=outcome.candidate_observation_id,
                    outcome_type="EXECUTED_TRADE",
                    symbol=outcome.symbol,
                    direction=outcome.side,
                    payload={
                        "entry_price": outcome.entry_price,
                        "exit_price": outcome.exit_price,
                        "qty": outcome.quantity,
                        "realized_pnl_usd": outcome.realized_pnl_usd,
                        "r_multiple": outcome.r_multiple,
                        "net_r": outcome.r_multiple,
                        "mae_r": outcome.mae_r,
                        "mfe_r": outcome.mfe_r,
                        "holding_seconds": outcome.holding_seconds,
                        "closed_at_ms": outcome.closed_timestamp,
                        "decision_batch_id": outcome.decision_batch_id,
                        "market_event_id": outcome.market_event_id,
                        "selection_authority": outcome.selection_authority,
                        "paper_canary_model_id": paper_model_id,
                        "paper_risk_multiplier": outcome.paper_risk_multiplier,
                        "paper_allocation_id": outcome.paper_allocation_id,
                        "profitable": bool(outcome.realized_pnl_usd > 0),
                        "exit_reason": outcome.exit_reason,
                        "pattern": outcome.pattern,
                        "strategy_version": outcome.strategy_version,
                        "strategy_variant_id": outcome.strategy_variant_id,
                        "model_version": outcome.model_version,
                        "execution_outcome_id": outcome.outcome_id,
                        "proposal_id": outcome.proposal_id,
                    },
                    experiment_context=context,
                    outcome_variant_id=paper_variant,
                )
                self._seen_executed_candidate_ids.add(
                    outcome.candidate_observation_id
                )

            self._seen_outcome_ids.add(outcome.outcome_id)
            return OutcomeAcknowledgement.create(
                outcome_id=outcome.outcome_id,
                acknowledged_at=int(time.time() * 1000),
                status="RECORDED",
            )
