"""Research-only native Freqtrade regime-aware strategy library router.

Uses as-of timestamped, externally audited historical native scorecards;
never fits or picks winners using future test information. Strategy must run
with explicit no-secret offline config and --enable-protections. Without
independent qualifying scorecards it selects NO TRADE on *every candle*.

Only routes the eight corresponding non-ML library signal families. Do not
pretend this runs all eight LightGBM models simultaneously. Later parallel
model orchestration needs separate native evidence and careful validation.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from pandas import DataFrame

from NbotV6LibraryResearch import (
    _NbotV6ResearchLibraryBase, FAMILIES, library_indicators, library_signals
)

from nbot_v6_library_selector import (
    choose_validated_strategy, parse_blocks,
)


def asof_market_regime(d: DataFrame) -> pd.Series:
    """Use only 5m candles completed through each decision (no hindsight)."""
    strength = d["nb_ema_20"] / d["nb_ema_50"] - 1
    volatility = d["nb_atr_pct"]
    historical_normal = volatility.shift(1).rolling(96, min_periods=96).median()
    high_vol = ((volatility > historical_normal * 2.0) & (volatility > 0.012))
    up = (strength > 0.0015) & (d["nb_ema_50"] > d["nb_ema_50"].shift(6))
    down = (strength < -0.0015) & (d["nb_ema_50"] < d["nb_ema_50"].shift(6))
    result = pd.Series("range", index=d.index, dtype=object)
    result.loc[up] = "trend_up"
    result.loc[down] = "trend_down"
    result.loc[high_vol] = "high_volatility"
    warm = d[["nb_ema_20", "nb_ema_50", "nb_atr_pct"]].notna().all(axis=1)
    warm &= historical_normal.notna()
    result.loc[~warm] = "high_volatility"  # fail closed until enough warmup
    return result


class NbotV6AdaptiveLibraryResearch(_NbotV6ResearchLibraryBase):
    family = "adaptive_library"  # not one of the trainable family names
    startup_candle_count = 300

    def _research_allowed(self) -> bool:
        c = self.config
        mode = c.get("runmode")
        mode = str(getattr(mode, "value", mode)).lower()
        e = c.get("exchange", {})
        return bool(mode == "backtest"
                    and c.get("dry_run") is True
                    and c.get("nbot_v6_library_research_only") is True
                    and c.get("nbot_v6_adaptive_research_only") is True
                    and c.get("nbot_live_mode") is False
                    and c.get("nbot_paper_research_mode") is False
                    and c.get("max_open_trades") == 1
                    and c.get("stake_amount") == 1000
                    and c.get("trading_mode") == "futures"
                    and c.get("margin_mode") == "isolated"
                    and c.get("force_entry_enable") is False
                    and c.get("api_server", {}).get("enabled") is False
                    and c.get("telegram", {}).get("enabled") is False
                    and not e.get("key") and not e.get("secret"))

    def bot_start(self, **kwargs):
        if not self._research_allowed():
            raise RuntimeError("NBOT_V6_ADAPTIVE_SELECTOR_OFFLINE_ONLY")
        raw = self.config.get("nbot_v6_library_scorecards_file")
        if not isinstance(raw, str) or not raw:
            raise RuntimeError("NO_SOURCE_ATTESTED_SCORECARDS_PROVIDED")
        candidate = Path(raw)
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError("SCORECARD_FILE_NOT_READABLE_OR_IS_SYMLINK")
        if candidate.stat().st_size > 2_000_000:
            raise RuntimeError("SCORECARD_FILE_TOO_LARGE")
        manifest = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {"schema", "blocks"}:
            raise RuntimeError("SCORECARD_MANIFEST_SCHEMA_INVALID")
        if manifest["schema"] != "nbot-v6-native-verified-blocks-v1":
            raise RuntimeError("SCORECARD_VERSION_INCOMPATIBLE")
        self._offline_native_scorecards = parse_blocks(manifest["blocks"])

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = library_indicators(dataframe)
        dataframe["nb_market_regime"] = asof_market_regime(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if not self._research_allowed() or not hasattr(self, "_offline_native_scorecards"):
            raise RuntimeError("ADAPTIVE_SELECTION_NEEDS_VERIFIED_BACKTEST_STARTUP")
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        if dataframe.empty:
            return dataframe
        asof = pd.to_datetime(dataframe["date"], utc=True, errors="coerce")
        if asof.isna().any() or not asof.is_monotonic_increasing:
            raise RuntimeError("ADAPTIVE_DECISION_REQUIRES_CHRONOLOGICAL_UTC_DATES")
        if asof.duplicated().any():
            raise RuntimeError("DUPLICATE_CANDLE_FORBIDDEN")
        intervals = asof.dt.floor("8h")
        regimes = dataframe["nb_market_regime"]
        # O(N) mapping across many months of history, not a quadratic scan
        # of every candle for every eight-hour bucket and every regime.
        # At every 8h decision the model uses ONLY previously finished tests.
        keys = list(zip(intervals.tolist(), regimes.tolist()))
        choices = {}
        for key in set(keys):
            timestamp, regime = key
            choices[key] = choose_validated_strategy(
                self._offline_native_scorecards,
                decision_at=timestamp.isoformat(), regime=regime
            ).family
        selected = pd.Series([choices[key] for key in keys],
                             index=dataframe.index, dtype=object)
        if selected.isna().all():
            return dataframe
        for family in FAMILIES:
            mask = selected == family
            if not bool(mask.any()):
                continue
            eligible = library_signals(dataframe, family)
            long = mask & eligible["long"] & (regimes != "trend_down")
            short = mask & eligible["short"] & (regimes != "trend_up")
            dataframe.loc[long, "enter_long"] = 1
            dataframe.loc[short, "enter_short"] = 1
            dataframe.loc[long, "enter_tag"] = "v6_adaptive_" + family + "_long"
            dataframe.loc[short, "enter_tag"] = "v6_adaptive_" + family + "_short"
        return dataframe
