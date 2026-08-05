"""Fail-closed execution guard for Binance Futures testnet orders."""

from __future__ import annotations

from pathlib import Path
import threading

from execution.exceptions import EntryValidationError


REQUIRED_CONFIRMATION = "I_ACCEPT_TESTNET_ORDER_EXECUTION"
ARM_FILE_CONTENT = "ARM_TESTNET_TRADING"


class TestnetTradingGuard:
    def __init__(
        self,
        *,
        confirmation: str,
        arm_file: str,
        max_session_entries: int,
        max_entry_notional_usd: float,
        require_flat_start: bool,
        system_log=None,
    ):
        self.confirmation = str(confirmation or "").strip()
        self.arm_file = Path(arm_file)
        self.max_session_entries = int(max_session_entries)
        self.max_entry_notional_usd = float(max_entry_notional_usd)
        self.require_flat_start = bool(require_flat_start)
        self.system_log = system_log
        self._session_entries = 0
        self._startup_validated = False
        self._lock = threading.Lock()

    def validate_startup(self, exchange) -> dict:
        self._validate_static_controls()
        position = exchange.get_position()
        if self.require_flat_start and position is not None:
            raise EntryValidationError(
                "TESTNET_START_REQUIRES_FLAT_ACCOUNT"
            )
        self._startup_validated = True
        report = {
            "status": "ARMED",
            "environment": "TESTNET",
            "execution": "TRADE",
            "session_entry_limit": self.max_session_entries,
            "entry_notional_limit_usd": self.max_entry_notional_usd,
            "flat_start_required": self.require_flat_start,
            "real_money": False,
        }
        if self.system_log:
            self.system_log.warning(
                "TESTNET_EXECUTION_GATE_ARMED | "
                f"session_entry_limit={self.max_session_entries} | "
                f"entry_notional_limit_usd="
                f"{self.max_entry_notional_usd:.2f} | "
                f"flat_start_required="
                f"{str(self.require_flat_start).lower()} | "
                "real_money=false"
            )
        return report

    def authorize_entry(
        self,
        *,
        symbol: str,
        qty: float,
        reference_price: float,
        current_position,
    ) -> dict:
        with self._lock:
            self._validate_static_controls()
            if not self._startup_validated:
                raise EntryValidationError(
                    "TESTNET_EXECUTION_STARTUP_NOT_VALIDATED"
                )
            if current_position is not None:
                raise EntryValidationError(
                    "TESTNET_ENTRY_BLOCKED_POSITION_EXISTS"
                )
            if not symbol or qty <= 0 or reference_price <= 0:
                raise EntryValidationError(
                    "TESTNET_ENTRY_PARAMETERS_INVALID"
                )
            notional = float(qty) * float(reference_price)
            if notional > self.max_entry_notional_usd:
                raise EntryValidationError(
                    "TESTNET_ENTRY_NOTIONAL_LIMIT_EXCEEDED | "
                    f"notional={notional:.8f} | "
                    f"limit={self.max_entry_notional_usd:.8f}"
                )
            if self._session_entries >= self.max_session_entries:
                raise EntryValidationError(
                    "TESTNET_SESSION_ENTRY_LIMIT_REACHED"
                )
            self._session_entries += 1
            if self.system_log:
                self.system_log.warning(
                    "TESTNET_ENTRY_AUTHORIZED | "
                    f"symbol={symbol} | qty={qty} | "
                    f"reference_price={reference_price} | "
                    f"notional_usd={notional:.8f} | "
                    f"session_entry={self._session_entries}/"
                    f"{self.max_session_entries} | "
                    "real_money=false"
                )
            return {
                "authorized": True,
                "notional_usd": notional,
                "session_entry_number": self._session_entries,
            }

    def _validate_static_controls(self) -> None:
        if self.confirmation != REQUIRED_CONFIRMATION:
            raise EntryValidationError(
                "TESTNET_TRADING_NOT_CONFIRMED"
            )
        if not self.arm_file.is_file():
            raise EntryValidationError(
                "TESTNET_TRADING_ARM_FILE_MISSING"
            )
        try:
            content = self.arm_file.read_text().strip()
        except OSError as exc:
            raise EntryValidationError(
                f"TESTNET_TRADING_ARM_FILE_UNREADABLE | {exc}"
            ) from exc
        if content != ARM_FILE_CONTENT:
            raise EntryValidationError(
                "TESTNET_TRADING_ARM_FILE_INVALID"
            )
