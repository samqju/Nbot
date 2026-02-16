# ==========================================================
# INTENT LIFECYCLE
# ==========================================================
# Owns:
# - Strategy observation
# - TradeIntent validation
# - Intent acceptance
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
        safety,
        universe,
        system_log,
        throttle,
        entry_lifecycle,
    ):
        self.state = state
        self.strategy = strategy
        self.safety = safety
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
        (Matches original engine behavior.)
        """
        intent = self._accepted_intent
        self._accepted_intent = None
        return intent

    def clear_accepted_intent(self):
        self._accepted_intent = None

    # --------------------------------------------------
    # Observe + Accept
    # --------------------------------------------------

    def observe(self, *, market_state):
        """
        Observe strategy and accept valid intent if possible.
        """

        # Engine must be idle
        if not self._engine_is_idle():
            return

        intent = self.strategy.propose_intent()

        if intent is None:
            return

        # Market price guard
        if not market_state.has_price(intent.symbol):
            self.throttle.log(
                key=f"intent_no_price_{intent.symbol}",
                level="info",
                message=(
                    f"INTENT_IGNORED | NO_MARKET_PRICE | "
                    f"symbol={intent.symbol}"
                ),
            )
            return

        # Validate
        is_valid, reason = self._validate(intent)

        if not is_valid:
            self.throttle.log(
                key=f"intent_rejected_{reason}",
                level="info",
                message=(
                    f"INTENT_REJECTED | "
                    f"symbol={intent.symbol} "
                    f"direction={intent.direction} "
                    f"reason={reason}"
                ),
            )
            return

        # Accept
        self.system_log.info(
            f"INTENT_ACCEPTED | "
            f"symbol={intent.symbol} "
            f"direction={intent.direction} "
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
            return False, f"TRADING_DISABLED | {engine_state}"

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
            return False

        if not self.safety.is_safe():
            return False

        if self.entry_lifecycle.entry_in_progress:
            return False

        if self._accepted_intent is not None:
            return False

        # Entry lifecycle guard (original engine behavior)
        if self.state.get_open_position() is not None:
            return False

        return True
