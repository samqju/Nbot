# ==========================================================
# INTENT LIFECYCLE
# ==========================================================
# Owns:
# - Strategy observation
# - TradeIntent validation
# - Intent acceptance
#
# Logging Policy:
# - INFO only (system.log)
# - No anomaly / failure routing
# - No operator notifications
# - No authority mutation
# ==========================================================

from datetime import datetime, timezone
from strategy.trade_intent import TradeIntent

MAX_INTENT_AGE_SECONDS = 30
RUNNING = "RUNNING"

class IntentLifecycle:

    def __init__(
        self,
        *,
        state,
        strategy,
        universe,
        system_log,
        throttle,
        entry_lifecycle,
    ):
        self.state = state
        self.strategy = strategy
        self.universe = universe
        self.system_log = system_log
        self.throttle = throttle
        self.entry_lifecycle = entry_lifecycle

        self._latest_intent = None
        self._accepted_intent = None

    # --------------------------------------------------
    # Public Accessor
    # --------------------------------------------------

    @property
    def accepted_intent(self):
        return self._accepted_intent

    def consume_accepted_intent(self):
        """
        Returns and clears accepted intent.
        """
        intent = self._accepted_intent
        if intent is not None:
            self.system_log.info(
                f"INTENT_CONSUMED | "
                f"symbol={intent.symbol} | "
                f"direction={intent.direction} | "
                f"pattern={intent.pattern}"
            )
        self._accepted_intent = None
        return intent

    def clear_accepted_intent(self):
        if self._accepted_intent is not None:
            self.system_log.info(
                f"INTENT_CLEARED | "
                f"symbol={self._accepted_intent.symbol} | "
                f"direction={self._accepted_intent.direction}"
            )
        self._accepted_intent = None

    # --------------------------------------------------
    # Observe + Accept
    # --------------------------------------------------

    def observe(self, *, market_state):


        # Engine must be idle
        if not self._engine_is_idle():
            return

        intent = self.strategy.propose_intent()

        if intent is None:
            return

        self.system_log.info(
            f"INTENT_PROPOSED | "
            f"symbol={intent.symbol} | "
            f"direction={intent.direction} | "
            f"pattern={intent.pattern}"
        )

        # Market price guard
        if not market_state.has_price(intent.symbol):
            self.system_log.info(
                f"INTENT_REJECTED_NO_PRICE | "
                f"symbol={intent.symbol}"
            )
            return

        # Validate
        is_valid, reason = self._validate(intent)

        if not is_valid:
            self.system_log.info(
                f"INTENT_VALIDATION_FAILED | "
                f"symbol={intent.symbol} | "
                f"direction={intent.direction} | "
                f"reason={reason}"
            )
            return

        # Accept
        self.system_log.info(
            f"INTENT_ACCEPTED | "
            f"symbol={intent.symbol} | "
            f"direction={intent.direction} | "
            f"pattern={intent.pattern}"
        )

        self._accepted_intent = intent

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def _validate(self, intent: TradeIntent):

        # Structural
        if not isinstance(intent, TradeIntent):
            return False, "INVALID_INTENT_TYPE"

        # Freshness
        now = datetime.now(timezone.utc)
        age = (now - intent.generated_at).total_seconds()
        if age > MAX_INTENT_AGE_SECONDS:
            return False, "INTENT_STALE"

        # Engine state
        engine_state = self.state.get_state().get("engine_state")
        if engine_state != RUNNING:
            return False, f"TRADING_DISABLED_{engine_state}"

        # No open position
        if self.state.get_open_position() is not None:
            return False, "POSITION_ALREADY_OPEN"

        # Universe membership
        if intent.symbol not in self.universe.symbols:
            return False, "SYMBOL_NOT_IN_UNIVERSE"

        if intent.direction not in ("LONG", "SHORT"):
            return False, "INVALID_DIRECTION"

        # Strategy warmed
        if not self.strategy.is_warmed_up():
            return False, "STRATEGY_NOT_WARMED"

        return True, "OK"

    # --------------------------------------------------
    # Idle Guard
    # --------------------------------------------------

    def _engine_is_idle(self) -> bool:

        if self.state.get_open_position() is not None:
            self.system_log.info("INTENT_IDLE_BLOCKED_POSITION_OPEN")
            return False

        if self.entry_lifecycle.entry_in_progress:
            self.system_log.info("INTENT_IDLE_BLOCKED_ENTRY_IN_PROGRESS")
            return False

        if self._accepted_intent is not None:
            self.system_log.info("INTENT_IDLE_BLOCKED_PENDING_INTENT")
            return False

        return True
