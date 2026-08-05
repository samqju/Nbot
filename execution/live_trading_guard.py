"""Central live-trading capability gate for Phase 2.5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LiveCapabilityReport:
    environment: str
    execution_mode: str
    adapter_mode: str
    confirmation_present: bool
    arm_file_present: bool
    writes_requested: bool
    writes_available: bool

    @property
    def read_only_safe(self) -> bool:
        return (
            self.environment == "LIVE"
            and self.execution_mode == "TRADE"
            and self.adapter_mode == "READ_ONLY"
            and self.confirmation_present
            and not self.arm_file_present
            and not self.writes_requested
            and not self.writes_available
        )


class LiveTradingGuard:
    REQUIRED_CONFIRMATION = "I_ACCEPT_REAL_MONEY_EXECUTION"

    def __init__(
        self,
        *,
        environment: str,
        execution_mode: str,
        adapter_mode: str,
        confirmation: str,
        writes_requested: bool,
        arm_file: str,
        adapter: Any,
    ):
        self.environment = str(environment).upper()
        self.execution_mode = str(execution_mode).upper()
        self.adapter_mode = str(adapter_mode).upper()
        self.confirmation = str(confirmation)
        self.writes_requested = bool(writes_requested)
        self.arm_file = Path(str(arm_file))
        self.adapter = adapter

    def inspect(self) -> LiveCapabilityReport:
        writes_available = not bool(getattr(self.adapter, "READ_ONLY", True))
        return LiveCapabilityReport(
            environment=self.environment,
            execution_mode=self.execution_mode,
            adapter_mode=self.adapter_mode,
            confirmation_present=(
                self.confirmation == self.REQUIRED_CONFIRMATION
            ),
            arm_file_present=self.arm_file.exists(),
            writes_requested=self.writes_requested,
            writes_available=writes_available,
        )

    def validate_read_only(self) -> LiveCapabilityReport:
        report = self.inspect()
        if report.environment != "LIVE" or report.execution_mode != "TRADE":
            raise RuntimeError("LIVE_GUARD_CONTEXT_INVALID")
        if not report.confirmation_present:
            raise RuntimeError("LIVE_GUARD_CONFIRMATION_MISSING")
        if report.adapter_mode != "READ_ONLY":
            raise RuntimeError("LIVE_GUARD_WRITE_MODE_REJECTED")
        if report.writes_requested:
            raise RuntimeError("LIVE_GUARD_WRITES_REQUESTED")
        if report.writes_available:
            raise RuntimeError("LIVE_GUARD_UNEXPECTED_WRITE_CAPABILITY")
        if report.arm_file_present:
            raise RuntimeError("LIVE_GUARD_STALE_ARM_FILE_PRESENT")
        return report
