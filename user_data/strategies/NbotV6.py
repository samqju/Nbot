"""NBOT V6: deliberately small Freqtrade + FreqAI research/dry-run strategy.

This is a prototype, not an economically validated trading strategy.
No custom order execution, networking, portfolio accounting, or ML model framework.
"""
from __future__ import annotations

import json
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy


# Mounted read-only from a private VPS directory ONLY in the live profile.
# This file never exists in the checked-in dry-run repository.
LIVE_ARM_PATH = Path("/freqtrade/live_private/approval.json")
LIVE_MAX_STAKE_USDT = 1000
LIVE_MAX_APPROVAL_SECONDS = 24 * 60 * 60


def owner_live_authorized(config: dict, now: datetime | None = None) -> bool:
    """Owner-only, expiring second authorization for real-money entries."""
    try:
        if config.get("dry_run") is not False or config.get("nbot_live_mode") is not True:
            return False
        if config.get("nbot_paper_research_mode") is True:
            return False
        if config.get("trading_mode") != "futures" or config.get("margin_mode") != "isolated":
            return False
        if type(config.get("max_open_trades")) is not int or config["max_open_trades"] != 1:
            return False
        stake = config.get("stake_amount")
        if type(stake) not in (int, float) or not 0 < stake <= LIVE_MAX_STAKE_USDT:
            return False
        if config.get("force_entry_enable") is not False:
            return False
        if config.get("api_server", {}).get("enabled") is not False:
            return False
        freqai = config.get("freqai", {})
        if freqai.get("enabled") is not True or freqai.get("expiration_hours", 0) <= 0:
            return False
        exchange = config.get("exchange", {})
        if exchange.get("name") != "binance" or not exchange.get("key") or not exchange.get("secret"):
            return False
        telegram = config.get("telegram", {})
        owner = str(config.get("nbot_owner_telegram_id", ""))
        if not re.fullmatch(r"[1-9]\d{4,19}", owner):
            return False
        if telegram.get("enabled") is not True or not telegram.get("token"):
            return False
        # Never permit group-chat authorization for real-money commands.
        if str(telegram.get("chat_id", "")) != owner:
            return False
        if telegram.get("authorized_users") != [owner]:
            return False
        if LIVE_ARM_PATH.is_symlink():
            return False
        info = LIVE_ARM_PATH.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 2048:
            return False
        approval = json.loads(LIVE_ARM_PATH.read_text(encoding="utf-8"))
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).timestamp()
        issued = approval.get("issued_at")
        expires = approval.get("expires_at")
        if type(issued) not in (int, float) or type(expires) not in (int, float):
            return False
        if not (issued <= current < expires and 0 < expires - issued <= LIVE_MAX_APPROVAL_SECONDS):
            return False
        if approval.get("owner_telegram_id") != owner:
            return False
        if approval.get("model_identifier") != freqai.get("identifier"):
            return False
        return approval.get("approval") == "NBOT_V6_OWNER_ARMED"
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False



class NbotV6(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "5m"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 200

    # Baseline safety envelopes, NOT optimized/validated parameters.
    stoploss = -0.02
    minimal_roi = {"0": 0.05}
    use_exit_signal = True
    exit_profit_only = False
    trailing_stop = False

    # This is a decision-time proxy, not a measured transaction cost.
    # Freqtrade backtests/dry-run model fills separately. Funding and severe
    # slippage can make realized economics worse than this threshold suggests.
    roundtrip_cost_proxy = 0.002
    min_predicted_net_return = 0.004
    prediction_exit_threshold = 0.003

    def bot_start(self, **kwargs) -> None:
        """A real-money bot cannot start without owner approval."""
        mode = self.config.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        if mode in {"backtest", "hyperopt", "edge"}:
            return
        if self.config.get("dry_run") is False:
            if not owner_live_authorized(self.config):
                raise RuntimeError("NBOT_V6_LIVE_OWNER_APPROVAL_REQUIRED")
            return
        if self.config.get("dry_run") is not True:
            raise RuntimeError("NBOT_V6_LIVE_ORDERS_FORBIDDEN")
        limit = self.config.get("max_open_trades")
        if self.config.get("nbot_paper_research_mode") is True:
            # Research can never have private exchange order credentials.
            if type(limit) is not int or not 1 <= limit <= 20:
                raise RuntimeError("NBOT_V6_PAPER_CAP_MUST_BE_1_TO_20")
            exchange = self.config.get("exchange", {})
            if exchange.get("key") or exchange.get("secret"):
                raise RuntimeError("NBOT_V6_PAPER_MUST_NOT_HAVE_EXCHANGE_KEYS")
        elif limit != 1:
            raise RuntimeError("NBOT_V6_REQUIRES_ONE_GLOBAL_POSITION")
        if not self.config.get("freqai", {}).get("enabled", False):
            raise RuntimeError("NBOT_V6_REQUIRES_FREQAI")

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time,
                            entry_tag: str | None, side: str, **kwargs) -> bool:
        """Recheck arm before every live entry, without interrupting exits."""
        if self.config.get("dry_run") is True:
            return True
        return owner_live_authorized(self.config)

    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float,
                 entry_tag: str | None, side: str, **kwargs) -> float:
        """Force 1x even on leveraged futures exchanges."""
        return 1.0

    def feature_engineering_expand_all(self, dataframe: DataFrame,
                                       period: int, **kwargs) -> DataFrame:
        """Past-only features for each configured pair, timeframe and period.

        FreqAI applies this to BTC as well via include_corr_pairlist.
        """
        close = dataframe["close"]
        ema = close.ewm(span=period, adjust=False, min_periods=period).mean()
        dataframe["%-ema_distance"] = close / ema - 1.0
        dataframe["%-volatility"] = close.pct_change().rolling(period, min_periods=period).std()
        dataframe["%-volume_ratio"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period, min_periods=period).mean() - 1.0
        )
        dataframe["%-momentum"] = close.pct_change(periods=period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        dataframe["%-body_fraction"] = (
            (dataframe["close"] - dataframe["open"]) / dataframe["close"].replace(0, np.nan)
        )
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        # Avoid new feature families until the first end-to-end baseline works.
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, **kwargs) -> DataFrame:
        """Predict raw 12-candle close-to-close return (not realized trade PnL).

        Future data is used here *only* as the training label. FreqAI excludes
        the label from decision-time features. The last 12 rows remain NaN.
        """
        horizon = int(self.freqai_info["feature_parameters"]["label_period_candles"])
        if horizon <= 0:
            raise ValueError("LABEL_HORIZON_MUST_BE_POSITIVE")
        dataframe["&-forward_return"] = dataframe["close"].shift(-horizon) / dataframe["close"] - 1.0
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Official FreqAI entry point: triggers training/inference and supplies
        # '&-forward_return' prediction plus 'do_predict'. Never called in a
        # feature_engineering_* method.
        dataframe = self.freqai.start(dataframe, metadata, self)

        close = dataframe["close"]
        dataframe["ema_fast"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
        dataframe["ema_slow"] = close.ewm(span=50, adjust=False, min_periods=50).mean()

        # Previous 20 completed candles only, no current-bar future high/low.
        dataframe["previous_high_20"] = dataframe["high"].shift(1).rolling(20, min_periods=20).max()
        dataframe["previous_low_20"] = dataframe["low"].shift(1).rolling(20, min_periods=20).min()

        uptrend = dataframe["ema_fast"] > dataframe["ema_slow"]
        downtrend = dataframe["ema_fast"] < dataframe["ema_slow"]
        previous_close = close.shift(1)
        previous_fast = dataframe["ema_fast"].shift(1)
        long_breakout = close > dataframe["previous_high_20"]
        short_breakout = close < dataframe["previous_low_20"]
        long_pullback = (previous_close <= previous_fast) & (close > dataframe["ema_fast"])
        short_pullback = (previous_close >= previous_fast) & (close < dataframe["ema_fast"])
        dataframe["long_setup"] = uptrend & (long_breakout | long_pullback)
        dataframe["short_setup"] = downtrend & (short_breakout | short_pullback)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        # FreqAI marks stale/outlier/unavailable model predictions by do_predict != 1.
        pred = dataframe["&-forward_return"]
        valid = (dataframe["do_predict"] == 1) & pred.notna() & np.isfinite(pred)
        valid &= (dataframe["volume"] > 0) & (dataframe["close"] > 0)
        min_return = self.roundtrip_cost_proxy + self.min_predicted_net_return
        long_ok = valid & dataframe["long_setup"].fillna(False) & (pred > min_return)
        short_ok = valid & dataframe["short_setup"].fillna(False) & (pred < -min_return)
        dataframe.loc[long_ok, "enter_long"] = 1
        dataframe.loc[short_ok, "enter_short"] = 1
        dataframe.loc[long_ok, "enter_tag"] = "v6_trend_setup_long"
        dataframe.loc[short_ok, "enter_tag"] = "v6_trend_setup_short"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        pred = dataframe["&-forward_return"]
        valid = (dataframe["do_predict"] == 1) & pred.notna() & np.isfinite(pred)
        # Trend reversal can exit even if model confidence has disappeared;
        # exchange-managed stoploss remains the primary downside protection.
        long_exit = (dataframe["ema_fast"] < dataframe["ema_slow"]) | (
            valid & (pred < -self.prediction_exit_threshold)
        )
        short_exit = (dataframe["ema_fast"] > dataframe["ema_slow"]) | (
            valid & (pred > self.prediction_exit_threshold)
        )
        dataframe.loc[long_exit.fillna(False), "exit_long"] = 1
        dataframe.loc[short_exit.fillna(False), "exit_short"] = 1
        return dataframe
