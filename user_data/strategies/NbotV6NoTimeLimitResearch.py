"""Nbot V6 isolated NATIVE exit-only A/B: absolutely no 60-minute custom exit.

Research-only. Entry signals, the -2% original stop, +5% ROI, Freqtrade
protective rules and one-slot 25-pair Freqtrade engine are unchanged.

Fixed variant exits only on the native ROI or native stop while prices
are available; at historical BACKTEST END Freqtrade necessarily force
closes unresolved positions. Trailing variant also permits the original
+2% activation / 1% gap trailing stop. Do not trade live or paper.
"""
from NbotV6LibraryResearch import _NbotV6ResearchLibraryBase, _NbotV6TrailingResearchBase
class _NoSixtyMinuteFixed(_NbotV6ResearchLibraryBase):
    minimal_roi = {"0": 0.05}
    stoploss = -0.02
    trailing_stop = False

    def custom_exit(self, pair, trade, current_time, current_rate,
                    current_profit, **kwargs):
        return None

class _NoSixtyMinuteTrailing(_NbotV6TrailingResearchBase):
    minimal_roi = {"0": 0.05}
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    def custom_exit(self, pair, trade, current_time, current_rate,
                    current_profit, **kwargs):
        return None

class NbotV6EmaCrossNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "ema_cross"

class NbotV6EmaCrossNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "ema_cross"

class NbotV6DonchianNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "donchian_breakout"

class NbotV6DonchianNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "donchian_breakout"

class NbotV6BollingerNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "bollinger_reversion"

class NbotV6BollingerNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "bollinger_reversion"

class NbotV6RsiNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "rsi_reversion"

class NbotV6RsiNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "rsi_reversion"

class NbotV6MacdNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "macd_momentum"

class NbotV6MacdNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "macd_momentum"

class NbotV6StochasticNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "stochastic_reversal"

class NbotV6StochasticNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "stochastic_reversal"

class NbotV6AtrBreakoutNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "atr_breakout"

class NbotV6AtrBreakoutNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "atr_breakout"

class NbotV6VolumeTrendNoTimeFixedResearch(_NoSixtyMinuteFixed):
    family = "volume_trend"

class NbotV6VolumeTrendNoTimeTrailingResearch(_NoSixtyMinuteTrailing):
    family = "volume_trend"
