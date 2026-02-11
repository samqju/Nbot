from risk.decisions import EntryDecision, PositionDecision, DailyDecision
from dataclasses import dataclass

@dataclass(frozen=True)
class EntryPlanData:
    quantity: float
    initial_sl: float
    risk_r: float

class RiskManager:
    """
    Canonical Risk Manager.

    Responsibilities:
    - Entry-time risk checks and initial SL placement
    - Trade-level profit protection (unrealised PnL)
    - Daily Loss Floor (DLF) enforcement (realised PnL)
    - Detection of true risk contract violations

    Design principles:
    - All core logic is expressed in R-units
    - Trade-level protection uses unrealised PnL only
    - Daily protection uses realised PnL only
    - Risk tolerance applies ONLY post-fill (never to SL placement)
    """

    # ------------------------------------------------------
    # Initialization
    # ------------------------------------------------------

    def __init__(
        self,
        NOTIONAL_TARGET: float,
        NOTIONAL_TOLERANCE_PCT: float,
        RISK_PER_TRADE_USD: float,
        RISK_TOLERANCE_PCT: float,
    ):
        # --- Notional policy ---
        self.NOTIONAL_TARGET = NOTIONAL_TARGET
        self.NOTIONAL_TOLERANCE = NOTIONAL_TOLERANCE_PCT / 100.0

        # --- Risk unit ---
        self.RISK_PER_TRADE_USD = RISK_PER_TRADE_USD
        self.MAX_RISK_USD = RISK_PER_TRADE_USD  # 1R

        # --- Execution tolerance (post-fill only) ---
        self.RISK_TOLERANCE = RISK_TOLERANCE_PCT / 100.0

        # --- Sanity checks ---
        assert self.NOTIONAL_TARGET > 0, "RISK_NOTIONAL_TARGET_INVALID"
        assert 0 <= self.NOTIONAL_TOLERANCE <= 0.02, (
            f"RISK_NOTIONAL_TOLERANCE_INVALID value={self.NOTIONAL_TOLERANCE}"
        )
        assert self.MAX_RISK_USD > 0, "RISK_MAX_RISK_USD_INVALID"
        assert 0 <= self.RISK_TOLERANCE <= 0.20, (
            f"RISK_TOLERANCE_INVALID value={self.RISK_TOLERANCE}"
        )

    # ------------------------------------------------------
    # Entry Evaluation
    # ------------------------------------------------------

    def evaluate_entry(self, price: float, side: str) -> EntryDecision:
        """
        Decide whether a new trade may be opened and compute initial SL.

        Policy:
        - Initial SL is placed at −0.9R (intentional bias).
        - Risk tolerance does NOT affect SL placement.
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

        # Initial risk = 0.9R (policy)
        initial_risk_usd = 0.9 * self.MAX_RISK_USD

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
            reason="OK",
            daily_loss_floor=0.0,
        )

    # ------------------------------------------------------
    # Trade-Level Risk Evaluation
    # ------------------------------------------------------

    def evaluate_position(self, position: dict, price: float) -> PositionDecision:
        """
        Evaluate an open position.

        Trade-Level Profit Protection Staircase (unrealised PnL):

        Initial SL:
        - −0.9R

        Tight regime (1R → 6R):
        - SL = highest_R − 0.9R

        Loose regime (≥ 7R):
        - SL = highest_R − 2R + 0.1R
        """

        side = position["side"]
        entry_price = position["entry_price"]
        qty = position["qty"]
        current_sl = position["stop_loss"]
        highest_profit_usd = position.get("highest_profit_usd", 0.0)

        # Canonical risk unit for THIS position
        risk_usd = position.get("risk_usd")
        assert risk_usd is not None and risk_usd > 0, "POSITION_RISK_INVALID"

        # --- Unrealised PnL ---
        if side == "LONG":
            unrealised_pnl = (price - entry_price) * qty
        else:
            unrealised_pnl = (entry_price - price) * qty

        highest_profit_usd = max(highest_profit_usd, unrealised_pnl)
        highest_R = highest_profit_usd / risk_usd

        updated_stop_loss = None

        # --- Trailing SL logic ---
        if highest_R >= 1:
            if highest_R < 7:
                locked_R = highest_R - 0.9
            else:
                locked_R = highest_R - 2 + 0.1

            locked_profit_usd = locked_R * risk_usd

            if side == "LONG":
                candidate_sl = entry_price + (locked_profit_usd / qty)
                if candidate_sl > current_sl:
                    updated_stop_loss = candidate_sl
            else:
                candidate_sl = entry_price - (locked_profit_usd / qty)
                if candidate_sl < current_sl:
                    updated_stop_loss = candidate_sl

        # --- Post-fill risk contract validation ---
        max_allowed_loss = risk_usd * (1 + self.RISK_TOLERANCE)

        if unrealised_pnl < -max_allowed_loss:
            return PositionDecision(
                violation=True,
                normal_exit=False,
                updated_stop_loss=None,
                highest_profit_usd=highest_profit_usd,
                reason="RISK_CONTRACT_BREACH",
            )

        return PositionDecision(
            violation=False,
            normal_exit=False,
            updated_stop_loss=updated_stop_loss,
            highest_profit_usd=highest_profit_usd,
            reason=None,
        )

    # ------------------------------------------------------
    # Daily Risk Evaluation (DLF)
    # ------------------------------------------------------

    def evaluate_daily(
        self,
        daily_realized_pnl: float,
        daily_peak_pnl: float,
    ) -> DailyDecision:
        """
        Daily Loss Floor (DLF).

        Based on realised PnL only.
        NO tolerance is applied.

        Early day (peak < 7R):
        - DLF = daily_peak − 5R

        Strong day (peak ≥ 7R):
        - DLF = daily_peak − 3R

        Trading halts ONLY if realised PnL breaches DLF.
        """

        peak_R = daily_peak_pnl / self.MAX_RISK_USD
        realized_R = daily_realized_pnl / self.MAX_RISK_USD

        if peak_R >= 7:
            allowed_giveback_R = 3
        else:
            allowed_giveback_R = 5

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

    # --------------------------------------------------
    # Build Entry Plan (NO EXECUTION)
    # --------------------------------------------------

    def build_entry_plan(
        self,
        *,
        direction: str,
        entry_price: float,
    ) -> EntryPlanData:
        """
        Build sizing + SL for an entry attempt.
        LONG-only for now.

        This does NOT:
        - place orders
        - decide allow/deny
        - modify state
        """

        assert direction == "LONG", "SHORT not enabled yet"

        # Reuse existing SL logic
        decision = self.evaluate_entry(
            price=entry_price,
            side="BUY",
        )

        if not decision.allowed or decision.stop_loss is None:
            raise RuntimeError(
                f"ENTRY_PLAN_BLOCKED | reason={decision.reason}"
            )

        sl = decision.stop_loss

        # Risk per unit
        risk_per_unit = entry_price - sl
        assert risk_per_unit > 0, "Invalid SL for LONG"

        # Capital at risk (USD)
        risk_usd = self.MAX_RISK_USD

        quantity = risk_usd / risk_per_unit

        return EntryPlanData(
            quantity=quantity,
            initial_sl=sl,
            risk_r=1.0,
        )
