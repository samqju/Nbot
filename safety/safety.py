# ================================
# SAFETY MODULE
# ================================
# This module decides IF the bot is allowed to trade.
# It does NOT decide how to trade.


# ================================
# IMPORTS
# ================================

from config import GLOBAL_KILL_SWITCH


# ================================
# SAFETY MANAGER CLASS
# ================================

class SafetyManager:
    """
    SafetyManager controls the emergency stop of the bot.
    If safety is violated, trading must stop immediately.
    """

    # ----------------------------
    # INITIALIZATION
    # ----------------------------
    def __init__(self):
        """
        Initialize safety state.
        """
        self._halted = False
        self._reason = None

    # ----------------------------
    # CHECK SAFETY STATUS
    # ----------------------------
    def is_safe(self):
        """
        Returns True if trading is allowed.
        Returns False if trading must stop.
        """

        # Global kill switch from config
        if GLOBAL_KILL_SWITCH:
            self._halted = True
            self._reason = "GLOBAL_KILL_SWITCH_ENABLED"
            return False

        # Internal halt flag
        if self._halted:
            return False

        return True

    # ----------------------------
    # HALT BOT MANUALLY
    # ----------------------------
    def halt(self, reason):
        """
        Force bot into unsafe state.
        """
        self._halted = True
        self._reason = reason

    # ----------------------------
    # GET HALT REASON
    # ----------------------------
    def get_reason(self):
        """
        Return the reason why bot was halted.
        """
        return self._reason
