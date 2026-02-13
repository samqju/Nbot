# ==========================================================
# SAFETY MODULE
# ==========================================================
# Controls whether trading is allowed.
# Does NOT execute trades.
# Does NOT contain risk logic.
#
# Invariants:
# - Halt is idempotent
# - Halt reason is preserved
# - Alerts are sent only once
# ==========================================================

from config import GLOBAL_KILL_SWITCH
from utils.telegram_notifier import send_critical
from utils.logger import system_logger

class SafetyManager:
    """
    Controls emergency stop of the bot.
    """

    def __init__(self):
        self._halted = False
        self._reason = None

    # --------------------------------------------------
    # Safety Check
    # --------------------------------------------------
    def is_safe(self) -> bool:

        # Global kill switch (config boundary)
        if GLOBAL_KILL_SWITCH:
            self._trigger_halt("GLOBAL_KILL_SWITCH_ENABLED")
            return False

        return not self._halted

    # --------------------------------------------------
    # External Halt
    # --------------------------------------------------
    def halt(self, reason: str) -> None:
        """
        Public halt entrypoint.
        Idempotent.
        """
        self._trigger_halt(reason)

    # --------------------------------------------------
    # Internal Halt Logic
    # --------------------------------------------------
    def _trigger_halt(self, reason: str) -> None:

        if self._halted:
            return  # Idempotent

        if not reason:
            raise ValueError("SAFETY_HALT_REQUIRES_REASON")

        self._halted = True
        self._reason = reason

        # Log to file
        system_logger().critical(f"ENGINE HALTED | reason={reason}")

        # Notify operator
        send_critical(
            "ENGINE HALTED",
            f"Reason: {reason}\n\n"
            "Trading stopped.\n"
            "Manual intervention required."
        )

    # --------------------------------------------------
    # Read-only access
    # --------------------------------------------------
    def get_reason(self):
        return self._reason
