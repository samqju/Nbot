# ==========================================================
# SAFETY MODULE
# ==========================================================

"""
Stabilized Safety Manager

Purpose:
- Provide is_safe() guard for legacy code.
- Allow halt() to mark unsafe state.
- DOES NOT exit engine.
- DOES NOT disable trading directly.
- DOES NOT send telegram.

Core remains sole authority.
"""


class SafetyManager:

    def __init__(self) -> None:
        self._halted = False
        self._reason = None

    def is_safe(self) -> bool:
        return not self._halted

    def is_halted(self) -> bool:
        return self._halted

    def get_reason(self):
        return self._reason

    def halt(self, reason: str) -> None:
        """
        Mark system unsafe.
        Does NOT exit engine.
        """
        if not reason:
            raise ValueError("SAFETY_HALT_REQUIRES_REASON")

        self._halted = True
        self._reason = reason

    def reset(self) -> None:
        """
        Operator-authorized safety reset.
        Clears halted state and reason.
        Does NOT exit engine.
        """
        self._halted = False
        self._reason = None
