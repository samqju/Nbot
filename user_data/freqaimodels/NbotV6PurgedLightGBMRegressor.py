"""V6 RESEARCH ONLY native LightGBM with strict internal 12-candle purge.

Does not modify Freqtrade or original NbotV6 strategy. Select explicitly
with --freqaimodel NbotV6PurgedLightGBMRegressor and the separate offline
nbot_m2r_purge_internal=true config. Never activate live or paper.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from freqtrade.exchange import timeframe_to_minutes
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen
from freqtrade.freqai.prediction_models.LightGBMRegressor import LightGBMRegressor


logger = logging.getLogger(__name__)


def apply_strict_training_embargo(
    dataset: dict[str, Any],
    train_dates: pd.Series,
    test_dates: pd.Series,
    horizon: pd.Timedelta,
) -> tuple[dict[str, Any], dict]:
    """Purge train decisions if the *latest possible* label time is at/after test start.

    Align by feature indices that FreqAI preserved after NaN elimination and its
    own train_test_split. The 12-bar horizon is independent of early take/stop
    outcomes and safe for BOTH price and trade-outcome targets.
    """
    if len(dataset["train_features"]) == 0 or len(dataset["test_features"]) == 0:
        raise RuntimeError("V6_PURGE_REQUIRES_NONEMPTY_CHRONOLOGICAL_TRAIN_AND_TEST")
    td = pd.to_datetime(train_dates, utc=True)
    vd = pd.to_datetime(test_dates, utc=True)
    if td.isna().any() or vd.isna().any():
        raise RuntimeError("V6_PURGE_INVALID_TIMESTAMP")
    if not td.is_monotonic_increasing or not vd.is_monotonic_increasing:
        raise RuntimeError("V6_PURGE_REQUIRES_CHRONOLOGICAL_SPLIT")
    cutoff = vd.iloc[0]
    if not (td.iloc[-1] < cutoff):
        raise RuntimeError("V6_PURGE_TRAIN_TEST_ORDER_INVALID")
    keep = ((td + horizon) < cutoff).to_numpy(dtype=bool)
    count = int((~keep).sum())
    dataset["train_features"] = dataset["train_features"].iloc[keep]
    dataset["train_labels"] = dataset["train_labels"].iloc[keep]
    dataset["train_weights"] = np.asarray(dataset["train_weights"])[keep]
    if len(dataset["train_features"]) < 100:
        raise RuntimeError("V6_PURGE_TOO_FEW_SAMPLES")
    remaining_latest_label = (td.iloc[keep] + horizon).max()
    if not remaining_latest_label < cutoff:
        raise RuntimeError("V6_PURGE_POST_EMBARGO_LEAK")
    return dataset, {
        "removed_train_rows": count,
        "remaining_train_rows": len(dataset["train_features"]),
        "first_validation_decision_utc": cutoff.isoformat(),
        "last_train_label_final_utc": remaining_latest_label.isoformat(),
        "label_horizon_seconds": horizon.total_seconds(),
        "post_embargo_boundary_violations": 0,
    }


class NbotV6PurgedLightGBMRegressor(LightGBMRegressor):
    """Explicitly opt-in causal 80/20 split; fail closed outside V6 offline research."""

    def train(self, unfiltered_df, pair: str, dk: FreqaiDataKitchen, **kwargs):
        c = self.config
        e = c.get("exchange", {})
        runmode = c.get("runmode")
        runmode = str(getattr(runmode, "value", runmode)).lower()
        if not (
            c.get("nbot_m2r_purge_internal") is True
            and c.get("nbot_m2r_research_only") is True
            and c.get("nbot_paper_research_mode") is not True
            and c.get("nbot_live_mode") is not True
            and runmode == "backtest"
            and c.get("dry_run") is True
            and not e.get("key")
            and not e.get("secret")
            and c.get("api_server", {}).get("enabled") is False
            and c.get("telegram", {}).get("enabled") is False
            and c.get("freqai", {}).get("data_split_parameters", {}).get("test_size", 0) == 0.2
            and c.get("freqai", {}).get("data_split_parameters", {}).get("shuffle") is False
            and c.get("freqai", {}).get("feature_parameters", {}).get("shuffle_after_split", False) is False
            and c.get("freqai", {}).get("feature_parameters", {}).get("reverse_train_test_order", False) is False
        ):
            raise RuntimeError("V6_PURGED_MODEL_RESEARCH_CONFIG_GUARD_FAILED")

        minutes = timeframe_to_minutes(c["timeframe"])
        candles = self.freqai_info["feature_parameters"]["label_period_candles"]
        if minutes != 5 or candles != 12:
            raise RuntimeError("V6_PURGE_LABEL_TIMEFRAME_GUARD_FAILED")

        horizon = pd.Timedelta(minutes=minutes * candles)
        original = dk.make_train_test_datasets
        audit = {}

        def native_then_purge(features, labels):
            dataset = original(features, labels)
            train_idx = dataset["train_features"].index
            test_idx = dataset["test_features"].index
            if not train_idx.is_unique or not test_idx.is_unique:
                raise RuntimeError("V6_PURGE_DUPLICATE_INDEX")
            if len(set(train_idx) & set(test_idx)):
                raise RuntimeError("V6_PURGE_OVERLAPPING_ROW_INDEX")
            a, stats = apply_strict_training_embargo(
                dataset, dk.train_dates.loc[train_idx], dk.train_dates.loc[test_idx], horizon
            )
            audit.update(stats)
            logger.warning(
                "V6_NATIVE_INTERNAL_PURGE pair=%s removed=%d remaining=%d "
                "test_first=%s latest_train_label=%s boundary_violations=%d",
                pair, stats["removed_train_rows"], stats["remaining_train_rows"],
                stats["first_validation_decision_utc"], stats["last_train_label_final_utc"],
                stats["post_embargo_boundary_violations"],
            )
            return a

        dk.make_train_test_datasets = native_then_purge
        try:
            fitted = super().train(unfiltered_df, pair, dk, **kwargs)
        finally:
            dk.make_train_test_datasets = original
        if not audit or audit.get("post_embargo_boundary_violations") != 0:
            raise RuntimeError("V6_PURGE_NOT_VERIFIED_AFTER_FIT")
        return fitted
