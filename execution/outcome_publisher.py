"""Execution-side durable publication of completed trade outcomes."""

from __future__ import annotations

from communication.execution_outcome import ExecutionOutcome
from communication.responses import OutcomeAcknowledgement
from execution.outcome_outbox import ExecutionOutcomeOutbox


class ExecutionOutcomePublisher:
    """Persist before delivery; delete only after a valid Observation ACK."""

    def __init__(self, *, outbox: ExecutionOutcomeOutbox, receiver, system_log=None):
        self.outbox = outbox
        self.receiver = receiver
        self.system_log = system_log

    def _log(self, level: str, message: str) -> None:
        if self.system_log is None:
            return
        getattr(self.system_log, level, lambda *_args, **_kwargs: None)(message)

    def publish(self, outcome: ExecutionOutcome) -> bool:
        stored = self.outbox.enqueue(outcome)
        try:
            acknowledgement = self.receiver.receive(stored)
        except Exception as exc:
            self._log(
                "error",
                "EXECUTION_OUTCOME_DELIVERY_FAILED | "
                f"outcome_id={stored.outcome_id} | "
                f"error={type(exc).__name__}:{exc}",
            )
            return False

        if not isinstance(acknowledgement, OutcomeAcknowledgement):
            self._log(
                "error",
                "EXECUTION_OUTCOME_ACK_INVALID | "
                f"outcome_id={stored.outcome_id}",
            )
            return False
        if acknowledgement.outcome_id != stored.outcome_id:
            self._log(
                "error",
                "EXECUTION_OUTCOME_ACK_ID_MISMATCH | "
                f"expected={stored.outcome_id} | "
                f"actual={acknowledgement.outcome_id}",
            )
            return False
        if acknowledgement.status not in {"RECORDED", "ALREADY_RECORDED"}:
            self._log(
                "error",
                "EXECUTION_OUTCOME_ACK_STATUS_INVALID | "
                f"outcome_id={stored.outcome_id} | "
                f"status={acknowledgement.status}",
            )
            return False

        self.outbox.acknowledge(stored.outcome_id)
        self._log(
            "info",
            "EXECUTION_OUTCOME_DELIVERED | "
            f"outcome_id={stored.outcome_id} | "
            f"status={acknowledgement.status}",
        )
        return True

    def retry_pending(self) -> int:
        delivered = 0
        for outcome in self.outbox.pending():
            if self.publish(outcome):
                delivered += 1
        return delivered

    def pending_count(self) -> int:
        return self.outbox.pending_count()
