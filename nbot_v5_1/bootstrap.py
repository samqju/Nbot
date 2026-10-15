"""G1 restart safety contract: an inspected journal never unlocks a mode.

No process or service is started. No network access, account access, or trading.
The caller must explicitly request append of a restart HOLD event.
"""
from __future__ import annotations

from dataclasses import dataclass

from .core import ObservationAuthority, ObservationDisposition, canonical_digest
from .foundation import RunMode
from .journal import AppendOnlyJournal, JournalEvent, JournalKind, JournalIntegrityError

BOOTSTRAP_SCHEMA_VERSION = "NBOT_V5_1_BOOT_V1"


@dataclass(frozen=True)
class RecoveryAssessment:
    mode: RunMode
    authority: ObservationAuthority
    disposition: ObservationDisposition
    journal_verified: bool
    journal_sequence: int
    journal_head_digest: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if (self.mode is not RunMode.OFFLINE or self.authority is not ObservationAuthority.NONE
                or self.disposition is not ObservationDisposition.HOLD):
            raise ValueError("G1_RESTART_RELEASE_FORBIDDEN")


def inspect_restart(journal: AppendOnlyJournal) -> RecoveryAssessment:
    """Check only the audit chain, never infer market continuity or availability."""
    if type(journal) is not AppendOnlyJournal:
        raise ValueError("G1_RESTART_JOURNAL_INVALID")
    try:
        receipts = journal.replay()
    except (JournalIntegrityError, OSError):
        # Never turn a damaged/missing audit head into permission to resume.
        return RecoveryAssessment(RunMode.OFFLINE, ObservationAuthority.NONE,
                                  ObservationDisposition.HOLD, False, 0, None,
                                  ("AUDIT_JOURNAL_UNVERIFIED", "NEW_SOURCE_REQUIRED",
                                   "RESTART_HOLD", "SOURCE_CONTINUITY_UNKNOWN"))
    return RecoveryAssessment(RunMode.OFFLINE, ObservationAuthority.NONE,
                              ObservationDisposition.HOLD, True, len(receipts),
                              receipts[-1].digest if receipts else None,
                              ("NEW_SOURCE_REQUIRED", "RESTART_HOLD",
                               "SOURCE_CONTINUITY_UNKNOWN"))


def record_restart_hold(journal: AppendOnlyJournal, *, observed_at_ms: int):
    """Explicit, idempotent append. A failed write never returns a PASS."""
    if type(observed_at_ms) is not int or observed_at_ms < 0:
        raise ValueError("G1_RESTART_TIME_INVALID")
    result = inspect_restart(journal)
    if not result.journal_verified:
        raise JournalIntegrityError("G1_RESTART_JOURNAL_UNVERIFIED")
    # Time scoped identity: repeated attempt with same as-of is idempotent.
    ident = canonical_digest("intent", {"domain": BOOTSTRAP_SCHEMA_VERSION,
                                        "observed_at_ms": observed_at_ms})
    return journal.append(JournalEvent(JournalKind.RESTART_HOLD, ident,
                                      observed_at_ms, result.reasons))
