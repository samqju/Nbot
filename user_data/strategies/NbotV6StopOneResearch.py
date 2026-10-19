"""Offline-only Nbot V6 STOP -1% versus original STOP -2% experiment.

Only modify hard initial stop to -0.01. Inherit SAME 5m entries, protections,
+5% ROI, original trailing rules and absence of 60min exit.
No paper/live/real money allowed; subclasses retain original bot_start guard.
"""
from NbotV6NoTimeLimitResearch import (
  _NoSixtyMinuteFixed, _NoSixtyMinuteTrailing
)

class _StopOneFixed(_NoSixtyMinuteFixed):
    stoploss = -0.01

class _StopOneTrailing(_NoSixtyMinuteTrailing):
    stoploss = -0.01

class NbotV6EmaCrossStopOneFixedResearch(_StopOneFixed):
    family = "ema_cross"

class NbotV6EmaCrossStopOneTrailingResearch(_StopOneTrailing):
    family = "ema_cross"

class NbotV6DonchianStopOneFixedResearch(_StopOneFixed):
    family = "donchian_breakout"

class NbotV6DonchianStopOneTrailingResearch(_StopOneTrailing):
    family = "donchian_breakout"

class NbotV6BollingerStopOneFixedResearch(_StopOneFixed):
    family = "bollinger_reversion"

class NbotV6BollingerStopOneTrailingResearch(_StopOneTrailing):
    family = "bollinger_reversion"

class NbotV6RsiStopOneFixedResearch(_StopOneFixed):
    family = "rsi_reversion"

class NbotV6RsiStopOneTrailingResearch(_StopOneTrailing):
    family = "rsi_reversion"

class NbotV6MacdStopOneFixedResearch(_StopOneFixed):
    family = "macd_momentum"

class NbotV6MacdStopOneTrailingResearch(_StopOneTrailing):
    family = "macd_momentum"

class NbotV6StochasticStopOneFixedResearch(_StopOneFixed):
    family = "stochastic_reversal"

class NbotV6StochasticStopOneTrailingResearch(_StopOneTrailing):
    family = "stochastic_reversal"

class NbotV6AtrBreakoutStopOneFixedResearch(_StopOneFixed):
    family = "atr_breakout"

class NbotV6AtrBreakoutStopOneTrailingResearch(_StopOneTrailing):
    family = "atr_breakout"

class NbotV6VolumeTrendStopOneFixedResearch(_StopOneFixed):
    family = "volume_trend"

class NbotV6VolumeTrendStopOneTrailingResearch(_StopOneTrailing):
    family = "volume_trend"

