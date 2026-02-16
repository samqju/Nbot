# ==========================================================
# DAILY LIFECYCLE
# ==========================================================
# Owns:
# - UTC day rollover handling
# - Daily Loss Floor evaluation
# - DAILY_HALT enforcement
# ==========================================================

import time
from datetime import datetime, timezone
from utils.telegram_notifier import send_critical


class DailyLifecycle:

    DAILY_HALT = "DAILY_HALT"

    def __init__(
        self,
        *,
        state,
        risk,
        exchange,
        safety,
        system_log,
        daily_log,
    ):
        self.state = state
        self.risk = risk
        self.exchange = exchange
        self.safety = safety
        self.system_log = system_log
        self.daily_log = daily_log

        self._last_utc_day = None

    # --------------------------------------------------
    # Handle
    # --------------------------------------------------

    def handle(self, *, timestamp: int) -> bool:
        """
        Handle UTC rollover + daily risk.
        Returns True if trading may continue.
        Returns False if halted.
        """

        utc_day = time.gmtime(timestamp // 1000).tm_yday

        # --------------------------------------------------
        # Day rollover
        # --------------------------------------------------
        if self._last_utc_day is None:
            self._last_utc_day = utc_day

        elif utc_day != self._last_utc_day:

            self.system_log.info(
                f"UTC_DAY_ROLLOVER | from={self._last_utc_day} to={utc_day}"
            )

            self._last_utc_day = utc_day

            # Cancel pending entries
            self.exchange.cancel_pending_entries()

            # Reset daily state
            self.state.reset_daily(utc_day)
            self.state.save()

        # --------------------------------------------------
        # Evaluate Daily Risk
        # --------------------------------------------------

        state_snapshot = self.state.get_state()

        daily_decision = self.risk.evaluate_daily(
            state_snapshot.get("daily_realized_pnl", 0.0),
            state_snapshot.get("daily_peak_pnl", 0.0),
        )

        self.state.update_daily_loss_floor(
            daily_decision.daily_loss_floor
        )

        # --------------------------------------------------
        # Daily Halt
        # --------------------------------------------------

        if daily_decision.halt:

            self.system_log.critical(
                f"DAILY_HALT | reason={daily_decision.reason}"
            )

            self.state.set_engine_state(
                engine_state=self.DAILY_HALT,
                reason=daily_decision.reason,
            )

            self.state.save()

            send_critical(
                "DAILY HALT",
                f"Reason: {daily_decision.reason}\n"
                f"Daily Loss Floor: "
                f"{daily_decision.daily_loss_floor} USD\n\n"
                f"UTC: {datetime.now(timezone.utc).date()}\n\n"
                "No new trades will be taken today."
            )

            self.state.disable_trading(daily_decision.reason)
            self.state.save()
            self.system_log.critical("TRADING_DISABLED | daily loss floor")

            return False

        return True
