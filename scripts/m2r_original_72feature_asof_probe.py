"""V6 original NbotV6 feature-family FreqAI frozen-model as-of audit.

Strictly offline. Uses exactly the native FreqaiDataKitchen feature generator
and original NbotV6 feature_engineering_* / entry and exit strategy methods.
Fresh models are trained once on the original &-forward_return price target
and native FreqAI LightGBMRegressor 2026.9. Full-vs-prefix prediction reuses
the identical fitted model/pipelines. This is NOT official backtesting engine
or original model artifact replay. All models are ephemeral in memory.

By default all 25 frozen markets and 4 observations per market; config as-is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "user_data" / "strategies"))
from NbotV6 import NbotV6
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen
from freqtrade.freqai.prediction_models.LightGBMRegressor import LightGBMRegressor

CUTOFF = pd.Timestamp("2026-10-08T00:00:00Z")
TRAIN_START = CUTOFF - pd.Timedelta(days=30)
RAW_START = TRAIN_START - pd.Timedelta(days=17)
END = CUTOFF + pd.Timedelta(days=1)
TEST_MINUTES = (5, 180, 215, 540, 565, 900, 955, 1260, 1300, 1435)
MODEL_FILE_SUFFIXES = {"5m": "-5m-futures.feather", "1h": "-1h-futures.feather"}


def json_safe(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def get_frames(data_dir, pair):
    token = pair.replace("/", "_").replace(":", "_")
    result = {}
    for tf, suffix in MODEL_FILE_SUFFIXES.items():
        d = pd.read_feather(data_dir / (token + suffix))
        d["date"] = pd.to_datetime(d.date, utc=True)
        d = d.loc[(d.date >= RAW_START) & (d.date < END)].reset_index(drop=True)
        assert d.date.is_unique and d.date.is_monotonic_increasing, (pair, tf)
        assert not d.empty and d.date.iloc[0] <= RAW_START, (pair, tf, d.date.iloc[0])
        result[tf] = d
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--limit-pairs", type=int, default=25)
    args = p.parse_args()

    cfg = json.loads(args.config.read_text())
    assert cfg["dry_run"] is True, "DRY_RUN_ONLY"
    assert not cfg["exchange"]["key"] and not cfg["exchange"]["secret"], "NO_KEYS"
    assert cfg["freqai"]["enabled"] is True
    assert cfg["freqai"]["train_period_days"] == 30
    assert cfg["freqai"]["feature_parameters"]["include_timeframes"] == ["5m", "1h"]
    assert cfg["freqai"]["feature_parameters"]["include_corr_pairlist"] == ["BTC/USDT:USDT"]
    assert cfg["freqai"]["feature_parameters"]["include_shifted_candles"] == 1
    assert cfg["freqai"]["feature_parameters"]["indicator_periods_candles"] == [14, 28]
    assert cfg["freqai"]["feature_parameters"]["label_period_candles"] == 12
    assert cfg["freqai"]["data_split_parameters"] == {"test_size": 0.2, "shuffle": False}
    assert cfg["freqai"]["model_training_parameters"]["n_estimators"] == 150
    assert cfg["freqai"]["model_training_parameters"]["n_jobs"] == 1
    assert cfg["freqai"]["save_backtest_models"] is False

    # Freqtrade's Config object fills these implicit defaults before native DataKitchen.
    cfg["freqai"]["feature_parameters"].setdefault("shuffle_after_split", False)
    cfg["freqai"]["feature_parameters"].setdefault("reverse_train_test_order", False)
    cfg["freqai"]["feature_parameters"].setdefault("weight_factor", 0)
    cfg["timerange"] = "20261008-20261009"
    cfg["config_files"] = [str(args.config)]
    cfg["user_data_dir"] = args.output.parent / "original_72feature_ephemeral_userdir"
    cfg["user_data_dir"].mkdir(parents=True, exist_ok=True)
    cfg["freqai"]["identifier"] = "nbot-v6-original-72feature-frozen-asof-20261017"
    cfg["freqai"]["activate_tensorboard"] = False
    cfg["freqai"]["data_kitchen_thread_count"] = 2
    cfg["freqai"]["save_backtest_models"] = False

    pairs = cfg["exchange"]["pair_whitelist"][:args.limit_pairs]
    assert 1 <= len(pairs) <= 25
    btc = get_frames(args.data, "BTC/USDT:USDT")
    corr = {"BTC/USDT:USDT": btc}
    report = {
        "scope": "original 5m/1h/BTC-correlated feature generator and original forward-return native FreqAI 2026.9 LightGBM + NbotV6 signal functions; fresh ephemeral model fitted once",
        "training_cutoff_utc": str(CUTOFF),
        "tested_day_utc": "2026-10-08",
        "fresh_fits": 0, "pairs_tested": 0, "asof_comparisons": 0,
        "feature_mismatches": 0, "prediction_mismatches": 0,
        "prediction_filter_mismatches": 0, "entry_exit_mismatches": 0,
        "model_hash_changes": 0, "feature_count_failures": 0,
        "per_pair": [], "no_money_trades": True, "no_live_service": True,
        "limitations": [
            "newly fit original-strategy 30-day native models; not reused from previous cached backtest artifacts",
            "fixed-model invariance only, not original full-engine FreqAI lookahead diagnostic, funding/stop-fill truth, or profit",
            "ten as-of five-minute candle CLOSE instants per pair including 1h/5m co-close boundary; not every historical bar",
            "not an independently purged internal 80/20 validation split",
        ],
    }
    class FixedPrediction:
        def __init__(self, date, prediction, gate):
            self.date, self.prediction, self.gate = date, prediction, gate
        def start(self, dataframe, metadata, strategy):
            f = dataframe.copy()
            f["&-forward_return"] = np.nan
            f["do_predict"] = 0
            ix = f["date"] == self.date
            assert ix.sum() == 1
            f.loc[ix, "&-forward_return"] = self.prediction
            f.loc[ix, "do_predict"] = self.gate
            return f

    for pair in pairs:
        base = get_frames(args.data, pair)
        strat = NbotV6(cfg)
        strat.freqai_info = cfg["freqai"]
        model = LightGBMRegressor(deepcopy(cfg))
        model.live = False
        dk = FreqaiDataKitchen(model.config, live=False, pair=pair)
        dk.set_paths(pair, int(CUTOFF.timestamp()))
        full = dk.use_strategy_to_populate_indicators(
            strat, corr_dataframes=corr, base_dataframes=base,
            pair=pair, do_corr_pairs=True,
        )
        # Match native start_backtesting lines 361-362 before find_features/train.
        full = dk.remove_special_chars_from_feature_names(full)
        full["date"] = pd.to_datetime(full.date, utc=True)
        if pair == "BTC/USDT:USDT":
            expected_features = 36
        else:
            expected_features = 72
        feature_cols = [x for x in full.columns if x.startswith("%")]
        if len(feature_cols) != expected_features:
            report["feature_count_failures"] += 1
            raise AssertionError((pair, expected_features, len(feature_cols), feature_cols))
        train = full.loc[(full.date >= TRAIN_START) & (full.date < CUTOFF)].copy().reset_index(drop=True)
        assert len(train) == 8640, (pair, len(train))
        train = strat.set_freqai_targets(train)
        assert train["&-forward_return"].iloc[-12:].isna().all(), pair
        dk.find_features(train)
        dk.find_labels(train)
        model.model = model.train(train, pair, dk)
        report["fresh_fits"] += 1
        model_before = hashlib.sha256(model.model.booster_.model_to_string().encode()).hexdigest()
        pdetail = {
            "pair": pair, "feature_count": len(feature_cols), "model_sha256": model_before,
            "train_last_date": str(train.date.iloc[-1]),
            "valid_target_count": int(train["&-forward_return"].notna().sum()),
            "samples": [],
        }
        for minute in TEST_MINUTES:
            target = CUTOFF + pd.Timedelta(minutes=minute)
            idx = full.index[full["date"] == target]
            assert len(idx) == 1, (pair, str(target))
            ix = idx[0]
            full_one = full.iloc[[ix]].reset_index(drop=True)
            reduced = {}
            # Make the TRUE as-of dataframe: no future 5m candle, nor an
            # unfinished/inaccessible 1h OHLCV candle at the decision time.
            for tf in MODEL_FILE_SUFFIXES:
                f = base[tf]
                if tf == "5m":
                    f = f.loc[f.date <= target]
                else:
                    # Native Freqtrade merges a 1h informative candle opened at HH:00
                    # into the 5m HH:55 row, because the decision is made
                    # AFTER the 5m HH:55 candle closes at HH+1:00. The 1h
                    # candle also closes then, so it is as-of AVAILABLE.
                    # Excluding it at HH:55 was an overstrict audit-harness
                    # error (found in deliberately expanded off-hour probes).
                    f = f.loc[f.date + pd.Timedelta(hours=1)
                              <= target + pd.Timedelta(minutes=5)]
                reduced[tf] = f.reset_index(drop=True)
            btc_reduced = {}
            for tf in MODEL_FILE_SUFFIXES:
                f = btc[tf]
                if tf == "5m":
                    f = f.loc[f.date <= target]
                else:
                    # Native Freqtrade merges a 1h informative candle opened at HH:00
                    # into the 5m HH:55 row, because the decision is made
                    # AFTER the 5m HH:55 candle closes at HH+1:00. The 1h
                    # candle also closes then, so it is as-of AVAILABLE.
                    # Excluding it at HH:55 was an overstrict audit-harness
                    # error (found in deliberately expanded off-hour probes).
                    f = f.loc[f.date + pd.Timedelta(hours=1)
                              <= target + pd.Timedelta(minutes=5)]
                btc_reduced[tf] = f.reset_index(drop=True)
            assert reduced["5m"].date.iloc[-1] == target
            asof_dk = FreqaiDataKitchen(model.config, live=False, pair=pair)
            asof_dk.set_paths(pair, int(CUTOFF.timestamp()))
            prefix = asof_dk.use_strategy_to_populate_indicators(
                strat, corr_dataframes={"BTC/USDT:USDT": btc_reduced},
                base_dataframes=reduced, pair=pair, do_corr_pairs=True
            )
            assert prefix.date.iloc[-1] == target
            asof_one = asof_dk.remove_special_chars_from_feature_names(
                prefix.iloc[[-1]].reset_index(drop=True))
            assert set(feature_cols).issubset(asof_one), (pair, set(feature_cols) - set(asof_one))
            v1 = full_one[feature_cols].to_numpy(dtype=float)
            v2 = asof_one[feature_cols].to_numpy(dtype=float)
            feature_diff_cols = [
                col for k, col in enumerate(feature_cols)
                if not np.allclose(v1[:, k], v2[:, k], rtol=1e-11, atol=1e-11, equal_nan=True)
            ]
            pred1, gate1 = model.predict(full_one, dk)
            di1 = dk.DI_values.copy()
            pred2, gate2 = model.predict(asof_one, dk)
            di2 = dk.DI_values.copy()
            prediction_diff = not np.allclose(pred1.values, pred2.values,
                                              rtol=1e-10, atol=1e-10, equal_nan=True)
            gate_diff = not (np.array_equal(gate1, gate2) and np.allclose(
                di1, di2, rtol=1e-10, atol=1e-10, equal_nan=True))
            def signals(df, pred, gate):
                strat.freqai = FixedPrediction(target, float(pred.iloc[0,0]), int(gate[0]))
                populated = strat.populate_indicators(df.copy(), {"pair": pair})
                populated = strat.populate_entry_trend(populated, {"pair": pair})
                populated = strat.populate_exit_trend(populated, {"pair": pair})
                r = populated.loc[populated["date"] == target].iloc[-1]
                return {k: json_safe(r[k]) if pd.notna(r.get(k)) else None for k in
                        ("enter_long", "enter_short", "exit_long", "exit_short", "enter_tag")}
            # Original downstream entry/exit code, but injected identical frozen
            # inference instead of calling FreqAI's re-train-on-each-run start().
            sig_full = signals(base["5m"], pred1, gate1)
            sig_asof = signals(reduced["5m"], pred2, gate2)
            signal_diff = sig_full != sig_asof
            report["asof_comparisons"] += 1
            report["feature_mismatches"] += int(bool(feature_diff_cols))
            report["prediction_mismatches"] += int(prediction_diff)
            report["prediction_filter_mismatches"] += int(gate_diff)
            report["entry_exit_mismatches"] += int(signal_diff)
            pdetail["samples"].append({
                "time_utc": str(target), "features_equal": not feature_diff_cols,
                "feature_mismatch_count": len(feature_diff_cols),
                "first_feature_mismatches": feature_diff_cols[:8],
                "prediction_equal": not prediction_diff,
                "predict_filter_equal": not gate_diff,
                "strategy_signals_equal": not signal_diff,
                "full_forecast": float(pred1.iloc[0,0]),
                "asof_forecast": float(pred2.iloc[0,0]),
                "full_gate": int(gate1[0]), "asof_gate": int(gate2[0]),
                "signals_full": sig_full, "signals_asof": sig_asof
            })
        model_after = hashlib.sha256(model.model.booster_.model_to_string().encode()).hexdigest()
        report["model_hash_changes"] += int(model_before != model_after)
        report["pairs_tested"] += 1
        report["per_pair"].append(pdetail)
        print("CHECK", pair, "features",len(feature_cols),
              "mismatches",sum(not x["features_equal"] for x in pdetail["samples"]),
              "prediction",sum(not x["prediction_equal"] for x in pdetail["samples"]),
              "signals",sum(not x["strategy_signals_equal"] for x in pdetail["samples"]),
              flush=True)
        # Store intermediate audit every pair to preserve partial evidence.
        args.output.write_text(json.dumps(report, indent=2) + "\n")

    report["limited_scope_pass"] = (
        report["pairs_tested"] == len(pairs)
        and report["asof_comparisons"] == len(pairs)*len(TEST_MINUTES)
        and all(report[k] == 0 for k in
                ("feature_mismatches", "prediction_mismatches", "prediction_filter_mismatches",
                 "entry_exit_mismatches", "model_hash_changes","feature_count_failures"))
    )
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print("FINISHED", "limited_scope_pass", report["limited_scope_pass"],
          "pair_count", report["pairs_tested"],
          "full_vs_prefix",report["asof_comparisons"], flush=True)
    return 0 if report["limited_scope_pass"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
