# ==========================================================
# RISK MANAGER
# ==========================================================

from dataclasses import dataclass
from risk.decisions import EntryDecision, PositionDecision, DailyDecision


# ==========================================================
# SECTION 1 — DATA STRUCTURES
# ==========================================================

@dataclass(frozen=True)
class EntryPlanData:
    quantity: float
    initial_sl: float
    risk_r: float

# ==========================================================
# SECTION 2 — INITIALIZATION
# ==========================================================

class RiskManager:

    # ------------------------------------------------------
    # Constructor
    # ------------------------------------------------------

    def __init__(
        self,
        NOTIONAL_TARGET: float,
        NOTIONAL_TOLERANCE_PCT: float,
        RISK_PER_TRADE_USD: float,
        RISK_TOLERANCE_PCT: float,
    ):
        # -----------------------------
        # Notional Policy
        # -----------------------------
        self.NOTIONAL_TARGET = NOTIONAL_TARGET
        self.NOTIONAL_TOLERANCE = NOTIONAL_TOLERANCE_PCT / 100.0

        # -----------------------------
        # Risk Unit
        # -----------------------------
        self.RISK_PER_TRADE_USD = RISK_PER_TRADE_USD
        self.MAX_RISK_USD = RISK_PER_TRADE_USD  # 1R

        # -----------------------------
        # Post-Fill Tolerance
        # -----------------------------
        self.RISK_TOLERANCE = RISK_TOLERANCE_PCT / 100.0

        # -----------------------------
        # Sanity Invariants
        # -----------------------------
        assert self.NOTIONAL_TARGET > 0, "RISK_NOTIONAL_TARGET_INVALID"

        assert 0 <= self.NOTIONAL_TOLERANCE <= 0.02, (
            f"RISK_NOTIONAL_TOLERANCE_INVALID value={self.NOTIONAL_TOLERANCE}"
        )

        assert self.MAX_RISK_USD > 0, "RISK_MAX_RISK_USD_INVALID"

        assert 0 <= self.RISK_TOLERANCE <= 0.20, (
            f"RISK_TOLERANCE_INVALID value={self.RISK_TOLERANCE}"
        )

    # ======================================================
    # SECTION 3 — ENTRY RISK
    # ======================================================

    def evaluate_entry(self, price: float, side: str) -> EntryDecision:
        """
        Evaluate whether a new trade may be opened.

        Policy:
        - Fixed notional sizing
        - Initial SL at −1.0R
        - Tolerance does NOT affect SL placement
        """

        intended_qty = self.NOTIONAL_TARGET / price
        intended_notional = price * intended_qty

        min_notional = self.NOTIONAL_TARGET * (1 - self.NOTIONAL_TOLERANCE)
        max_notional = self.NOTIONAL_TARGET * (1 + self.NOTIONAL_TOLERANCE)

        if not (min_notional <= intended_notional <= max_notional):
            return EntryDecision(
                allowed=False,
                stop_loss=None,
                reason="NOTIONAL_CAP_VIOLATION",
                daily_loss_floor=0.0,
            )

        # Initial risk = 1.0R
        initial_risk_usd = self.MAX_RISK_USD

        if side == "LONG":
            stop_loss = price - (initial_risk_usd / intended_qty)
        else:
            stop_loss = price + (initial_risk_usd / intended_qty)

        if stop_loss <= 0:
            return EntryDecision(
                allowed=False,
                stop_loss=None,
                reason="RISK_INFEASIBLE",
                daily_loss_floor=0.0,
            )

        return EntryDecision(
            allowed=True,
            stop_loss=stop_loss,
            reason=None,
            daily_loss_floor=0.0,
        )

    # ======================================================
    # SECTION 4 — POSITION RISK
    # ======================================================

    def evaluate_position(self, position: dict, price: float) -> PositionDecision:
        """
        Evaluate open position risk and trailing logic.
        """

        side = position["side"]
        entry_price = position["entry_price"]
        qty = position["qty"]
        current_sl = position["stop_loss"]
        highest_profit_usd = position.get("highest_profit_usd", 0.0)

        risk_usd = position.get("risk_usd")
        assert risk_usd is not None and risk_usd > 0, "POSITION_RISK_INVALID"

        # -----------------------------
        # Unrealised PnL
        # -----------------------------
        if side == "LONG":
            unrealised_pnl = (price - entry_price) * qty
        else:
            unrealised_pnl = (entry_price - price) * qty

        highest_profit_usd = max(highest_profit_usd, unrealised_pnl)
        highest_R = highest_profit_usd / risk_usd

        updated_stop_loss = None
        next_integer_R = None

        # -----------------------------
        # Trailing SL Logic
        # -----------------------------
        if highest_R >= 1:

            integer_R = int(highest_R)
            last_locked_R = position.get("last_locked_R", 0)

            if integer_R > last_locked_R:

                locked_R = integer_R - 1
                locked_profit_usd = locked_R * risk_usd

                if side == "LONG":
                    candidate_sl = entry_price + (locked_profit_usd / qty)
                    if candidate_sl > current_sl:
                        updated_stop_loss = candidate_sl
                        next_integer_R = integer_R
                else:
                    candidate_sl = entry_price - (locked_profit_usd / qty)
                    if candidate_sl < current_sl:
                        updated_stop_loss = candidate_sl
                        next_integer_R = integer_R

        # -----------------------------
        # Risk Contract Validation
        # -----------------------------
        max_allowed_loss = risk_usd * (1 + self.RISK_TOLERANCE)

        if unrealised_pnl < -max_allowed_loss:
            return PositionDecision(
                violation=True,
                normal_exit=False,
                updated_stop_loss=None,
                highest_profit_usd=highest_profit_usd,
                next_integer_R=None,
                reason="RISK_CONTRACT_BREACH",
            )

        return PositionDecision(
            violation=False,
            normal_exit=False,
            updated_stop_loss=updated_stop_loss,
            highest_profit_usd=highest_profit_usd,
            next_integer_R=next_integer_R,
            reason=None,
        )

    # ======================================================
    # SECTION 5 — DAILY RISK
    # ======================================================

    def evaluate_daily(
        self,
        daily_realized_pnl: float,
        daily_peak_pnl: float,
    ) -> DailyDecision:
        """
        Daily Loss Floor (DLF).

        Based on realised PnL only.
        No tolerance applied.
        """

        peak_R = daily_peak_pnl / self.MAX_RISK_USD
        realized_R = daily_realized_pnl / self.MAX_RISK_USD

        if peak_R >= 100:
            allowed_giveback_R = 3
        else:
            allowed_giveback_R = 95

        dlf_R = peak_R - allowed_giveback_R
        dlf_usd = dlf_R * self.MAX_RISK_USD

        if realized_R < dlf_R:
            return DailyDecision(
                halt=True,
                reason="DAILY_LOSS_FLOOR_BREACH",
                daily_loss_floor=dlf_usd,
            )

        return DailyDecision(
            halt=False,
            reason=None,
            daily_loss_floor=dlf_usd,
        )

    # ======================================================
    # SECTION 6 — ENTRY PLAN BUILDER
    # ======================================================

    def build_entry_plan(
        self,
        *,
        direction: str,
        entry_price: float,
    ) -> EntryPlanData:
        """
        Build sizing and initial SL.
        No state mutation.
        No exchange interaction.
        """

        if direction not in ("LONG", "SHORT"):
            raise RuntimeError(f"INVALID_DIRECTION: {direction}")

        decision = self.evaluate_entry(
            price=entry_price,
            side=direction,
        )

        if not decision.allowed or decision.stop_loss is None:
            raise RuntimeError(
                f"ENTRY_PLAN_BLOCKED | reason={decision.reason}"
            )

        sl = decision.stop_loss

        if direction == "LONG":
            risk_per_unit = entry_price - sl
        else:
            risk_per_unit = sl - entry_price

        if risk_per_unit <= 1e-12:
            raise RuntimeError(
                f"INVALID_SL_DISTANCE | direction={direction} "
                f"entry={entry_price} sl={sl}"
            )

        quantity = self.NOTIONAL_TARGET / entry_price

        return EntryPlanData(
            quantity=quantity,
            initial_sl=sl,
            risk_r=1.0,
        )

