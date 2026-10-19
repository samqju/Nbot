"""Nbot V6 owner-requested EXACT gross price-point trailing rule — OFFLINE RESEARCH.

Activation: favorable price excursion reaches +1% from the entry price.
For any favorable excursion P >= 1%, lock P-1 percentage points gross
relative to ENTRY (not Freqtrade's multiplicative 1% price-relative trail):
+1% -> entry, +2% -> +1%, +3% -> +2%, both LONG and SHORT.
Entry family, native +5% ROI, -2% original initial stop, NO 60-minute exit,
1x leverage and no live/paper guards are inherited unchanged.

Native 5m OHLCV cannot guarantee within-candle favorable-first ordering,
real-time order placement, filling at stop level or profit after costs.
"""
from NbotV6NoTimeLimitResearch import _NoSixtyMinuteFixed
from freqtrade.strategy import stoploss_from_absolute


def exact_trailing_stop_price(open_rate: float, observed_rate: float,
                              is_short: bool) -> float | None:
    """Closed-form stop at ENTRY-relative max favorable excursion minus 1 pp.

    Only called from Freqtrade custom_stoploss with the current favorable
    candle extreme. Freqtrade itself keeps the stop from moving backward.
    """
    if open_rate <= 0 or observed_rate <= 0:
        return None
    favorable = ((open_rate - observed_rate) / open_rate if is_short
                 else (observed_rate - open_rate) / open_rate)
    if favorable < 0.01 - 1e-12:
        return None
    protected = favorable - 0.01
    return open_rate * (1 - protected if is_short else 1 + protected)


class _NbotV6Exact1PctActivation(_NoSixtyMinuteFixed):
    stoploss = -0.02
    minimal_roi = {"0": 0.05}
    trailing_stop = False
    use_custom_stoploss = True

    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, after_fill=False, **kwargs):
        stop = exact_trailing_stop_price(
            float(trade.open_rate),float(current_rate),bool(trade.is_short))
        if stop is None:
            return None  # Preserve initial -2% stop.
        return stoploss_from_absolute(
            stop,current_rate=current_rate,is_short=trade.is_short,
            leverage=trade.leverage)

class NbotV6EmaCrossExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "ema_cross"

class NbotV6DonchianExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "donchian_breakout"

class NbotV6BollingerExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "bollinger_reversion"

class NbotV6RsiExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "rsi_reversion"

class NbotV6MacdExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "macd_momentum"

class NbotV6StochasticExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "stochastic_reversal"

class NbotV6AtrBreakoutExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "atr_breakout"

class NbotV6VolumeTrendExactOneTrailResearch(_NbotV6Exact1PctActivation):
    family = "volume_trend"

