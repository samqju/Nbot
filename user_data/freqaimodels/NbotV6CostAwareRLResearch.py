"""Research-only FreqAI reinforcement learning, with cost/risk-aware reward.

An OFFLINE comparison arm, not a superior replacement for LightGBM.
FreqAI's simulated RL training environment is NOT a Freqtrade native
exchange execution model; eventual native backtests and holdouts decide.
"""
from __future__ import annotations

import math
from freqtrade.freqai.prediction_models.ReinforcementLearner import ReinforcementLearner
from freqtrade.freqai.RL.Base5ActionRLEnv import Actions, Base5ActionRLEnv, Positions


class NbotV6CostAwareRLResearch(ReinforcementLearner):
    """Use native FreqAI PPO and action machinery; change only reward."""

    class MyRLEnv(Base5ActionRLEnv):
        def calculate_reward(self, action: int) -> float:
            # In the training environment a neutral action is the preferred
            # safe default. Never reward activity for its own sake.
            if not self._is_valid(action):
                return -0.02
            if self._position == Positions.Neutral:
                if action == Actions.Neutral.value:
                    return 0.0
                if action in (Actions.Long_enter.value, Actions.Short_enter.value):
                    # Small opportunity cost for opening a position and
                    # immediate expected roundtrip fee/slippage reserve.
                    return -0.002
                return 0.0

            pnl = float(self.get_unrealized_profit())
            if not math.isfinite(pnl):
                return -1.0

            held = max(0, self._current_tick - self._last_trade_tick)
            max_held = 12  # same 60m decision horizon as LightGBM setups
            timeout_cost = min(0.02, max(0, held - max_held) * 0.0005)
            cost_reserve = 0.0021   # fee + slippage + funding proxy
            stop_penalty = 0.02 if pnl < -0.02 else 0.0
            if self._position == Positions.Long and action == Actions.Long_exit.value:
                return float(10.0 * max(-0.10, min(0.10, pnl - cost_reserve - timeout_cost - stop_penalty)))
            if self._position == Positions.Short and action == Actions.Short_exit.value:
                return float(10.0 * max(-0.10, min(0.10, pnl - cost_reserve - timeout_cost - stop_penalty)))
            # Holding has a modest risk/time cost. This keeps neutral actions
            # preferable to forced churn and avoids incentivizing unlimited
            # exposure. Not calibrated to real Binance order fills.
            if action == Actions.Neutral.value:
                return float(-0.0001 - timeout_cost)
            return -0.005
