# ==========================================================
# EMERGENCY HANDLER
# ==========================================================
# Owns:
# - Verified emergency exit
# - Guaranteed flatten attempt
# - Fatal halt escalation if flatten fails
# ==========================================================

import time

class EmergencyHandler:

    FATAL_HALT = "FATAL_HALT"

    def __init__(
        self,
        *,
        exchange,
        state,
        system_log,
        trade_log,
    ):
        self.exchange = exchange
        self.state = state
        self.system_log = system_log
        self.trade_log = trade_log

        self._exit_in_progress = False

    # --------------------------------------------------
    # Public
    # --------------------------------------------------

    def execute(self, reason: str):
        """
        Verified emergency exit.
        """

        if self._exit_in_progress:
            return

        self._exit_in_progress = True

        # Risk boundary event
        self.system_log.error(
            f"EMERGENCY_EXIT_TRIGGERED | reason={reason}"
        )

        try:
            pos = self.exchange.get_position()
            if pos:
                self.system_log.error(
                    f"EMERGENCY_POSITION | "
                    f"symbol={pos.symbol} | "
                    f"side={pos.side} | "
                    f"qty={pos.qty}"
                )
        except Exception:
            pass

        # Attempt flatten twice
        for attempt in range(2):

            try:
                self.exchange.emergency_exit()
            except Exception as e:
                self.system_log.error(
                    f"EMERGENCY_EXIT_SEND_FAILED | "
                    f"attempt={attempt+1} | error={e}"
                )

            time.sleep(0.5)

            try:
                pos = self.exchange.get_position()
            except Exception:
                continue

            if pos is None:
                self.system_log.info(
                    "EMERGENCY_EXIT_CONFIRMED_FLAT"
                )
                self._exit_in_progress = False
                return

        # --------------------------------------------------
        # If still not flat → FATAL HALT
        # --------------------------------------------------

        self.system_log.error(
            "EMERGENCY_EXIT_FAILED_NOT_FLAT"
        )

        # Capital still exposed (cross-layer logging)
        self.system_log.error(
            "EMERGENCY_EXIT_FAILED_NOT_FLAT | CAPITAL_STILL_EXPOSED"
        )

        self._exit_in_progress = False

        raise RuntimeError("EMERGENCY_EXIT_FAILED")
