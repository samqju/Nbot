"""NBOT V6 independent *exit-policy* experiments. OFFLINE Freqtrade only.

Five frozen variants of each of the eight existing technical entry strategies.
Do not modify the currently running original library batch. This source is
for a subsequent study, with the exact same entry and indicator code as
NbotV6LibraryResearch._NbotV6ResearchLibraryBase.

The initial risk stop remains -2%; native backtest uses 5m candle OHLCV
without intrabar price ordering. Trailing stops lock an idealized gross
price move, NOT a guaranteed realized after-cost profit. Native funding,
0.05% side fees and +25bp extra execution stress are audited separately.
No real/virtual live trading credentials, backtest-only gated by base.
"""

from NbotV6LibraryResearch import _NbotV6ResearchLibraryBase


class _NbotV6ProfitExitBase(_NbotV6ResearchLibraryBase):
    stoploss = -0.02
    minimal_roi = {"0": 0.05}
    trailing_stop = False
    trailing_only_offset_is_reached = True


class _TrailEarlyOne(_NbotV6ProfitExitBase):
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True
    minimal_roi = {"0": 0.05}


class _TrailEarlyOneHalf(_NbotV6ProfitExitBase):
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True
    minimal_roi = {"0": 0.05}


class _TrailTightTwo(_NbotV6ProfitExitBase):
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True
    minimal_roi = {"0": 0.05}


class _TakeProfitTwo(_NbotV6ProfitExitBase):
    trailing_stop = False
    minimal_roi = {"0": 0.02}


class _TakeProfitThree(_NbotV6ProfitExitBase):
    trailing_stop = False
    minimal_roi = {"0": 0.03}


class NbotV6EmaCrossTrailEarlyOneResearch(_TrailEarlyOne):
    family = "ema_cross"


class NbotV6DonchianTrailEarlyOneResearch(_TrailEarlyOne):
    family = "donchian_breakout"


class NbotV6BollingerTrailEarlyOneResearch(_TrailEarlyOne):
    family = "bollinger_reversion"


class NbotV6RsiTrailEarlyOneResearch(_TrailEarlyOne):
    family = "rsi_reversion"


class NbotV6MacdTrailEarlyOneResearch(_TrailEarlyOne):
    family = "macd_momentum"


class NbotV6StochasticTrailEarlyOneResearch(_TrailEarlyOne):
    family = "stochastic_reversal"


class NbotV6AtrBreakoutTrailEarlyOneResearch(_TrailEarlyOne):
    family = "atr_breakout"


class NbotV6VolumeTrendTrailEarlyOneResearch(_TrailEarlyOne):
    family = "volume_trend"


class NbotV6EmaCrossTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "ema_cross"


class NbotV6DonchianTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "donchian_breakout"


class NbotV6BollingerTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "bollinger_reversion"


class NbotV6RsiTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "rsi_reversion"


class NbotV6MacdTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "macd_momentum"


class NbotV6StochasticTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "stochastic_reversal"


class NbotV6AtrBreakoutTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "atr_breakout"


class NbotV6VolumeTrendTrailEarlyOneHalfResearch(_TrailEarlyOneHalf):
    family = "volume_trend"


class NbotV6EmaCrossTrailTightTwoResearch(_TrailTightTwo):
    family = "ema_cross"


class NbotV6DonchianTrailTightTwoResearch(_TrailTightTwo):
    family = "donchian_breakout"


class NbotV6BollingerTrailTightTwoResearch(_TrailTightTwo):
    family = "bollinger_reversion"


class NbotV6RsiTrailTightTwoResearch(_TrailTightTwo):
    family = "rsi_reversion"


class NbotV6MacdTrailTightTwoResearch(_TrailTightTwo):
    family = "macd_momentum"


class NbotV6StochasticTrailTightTwoResearch(_TrailTightTwo):
    family = "stochastic_reversal"


class NbotV6AtrBreakoutTrailTightTwoResearch(_TrailTightTwo):
    family = "atr_breakout"


class NbotV6VolumeTrendTrailTightTwoResearch(_TrailTightTwo):
    family = "volume_trend"


class NbotV6EmaCrossTakeProfitTwoResearch(_TakeProfitTwo):
    family = "ema_cross"


class NbotV6DonchianTakeProfitTwoResearch(_TakeProfitTwo):
    family = "donchian_breakout"


class NbotV6BollingerTakeProfitTwoResearch(_TakeProfitTwo):
    family = "bollinger_reversion"


class NbotV6RsiTakeProfitTwoResearch(_TakeProfitTwo):
    family = "rsi_reversion"


class NbotV6MacdTakeProfitTwoResearch(_TakeProfitTwo):
    family = "macd_momentum"


class NbotV6StochasticTakeProfitTwoResearch(_TakeProfitTwo):
    family = "stochastic_reversal"


class NbotV6AtrBreakoutTakeProfitTwoResearch(_TakeProfitTwo):
    family = "atr_breakout"


class NbotV6VolumeTrendTakeProfitTwoResearch(_TakeProfitTwo):
    family = "volume_trend"


class NbotV6EmaCrossTakeProfitThreeResearch(_TakeProfitThree):
    family = "ema_cross"


class NbotV6DonchianTakeProfitThreeResearch(_TakeProfitThree):
    family = "donchian_breakout"


class NbotV6BollingerTakeProfitThreeResearch(_TakeProfitThree):
    family = "bollinger_reversion"


class NbotV6RsiTakeProfitThreeResearch(_TakeProfitThree):
    family = "rsi_reversion"


class NbotV6MacdTakeProfitThreeResearch(_TakeProfitThree):
    family = "macd_momentum"


class NbotV6StochasticTakeProfitThreeResearch(_TakeProfitThree):
    family = "stochastic_reversal"


class NbotV6AtrBreakoutTakeProfitThreeResearch(_TakeProfitThree):
    family = "atr_breakout"


class NbotV6VolumeTrendTakeProfitThreeResearch(_TakeProfitThree):
    family = "volume_trend"


EXIT_POLICY_IDS = ["trail_1p0_gap_0p5","trail_1p5_gap_0p5","trail_2p0_gap_0p5","take_profit_2p0","take_profit_3p0"]
