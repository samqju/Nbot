"""Bounded V6 research: same frozen native FreqAI LightGBM model, full vs as-of prefix.

NO backtesting outcome/PnL; NO model promotion. This is a *4-feature after-cost
model-level* invariant probe, not the original multi-timeframe 72-feature
FreqAI strategy's all-pairs lookahead or execution certification.

The 25 separate models are fitted once at the same Oct 8 2026 cutoff on
existing historical candles (30 day/12 5m label). For each pair, compare
feature and inference values on the same four Oct 8 decision timestamps when
future candles are appended. Native FreqAI 2026.9 pipelines + LightGBM are
reused without retraining, and model SHA-256 is checked pre/post predictions.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "user_data" / "strategies"))

from nbot_trade_outcome import decision_features, training_labels
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen
from freqtrade.freqai.prediction_models.LightGBMRegressor import LightGBMRegressor


CUT = pd.Timestamp("2026-10-08T00:00:00Z")
TRAIN_START = CUT - pd.Timedelta(days=30)
NEXT = CUT + pd.Timedelta(days=1)
TARGET_HOURS = (3, 9, 15, 21)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text())
    assert not cfg["exchange"]["key"] and not cfg["exchange"]["secret"]
    assert cfg["freqai"]["enabled"] is True and cfg["freqai"]["train_period_days"] == 30
    assert cfg["freqai"]["data_split_parameters"] == {"test_size": 0.2, "shuffle": False}
    assert cfg["freqai"]["feature_parameters"]["label_period_candles"] == 12
    cfg["freqai"]["feature_parameters"]["shuffle_after_split"] = False
    cfg["freqai"]["feature_parameters"]["reverse_train_test_order"] = False
    cfg["freqai"]["feature_parameters"]["weight_factor"] = 0
    cfg["freqai"]["feature_parameters"]["DI_threshold"] = 0.9
    cfg["freqai"]["identifier"] = "nbot-v6-offline-native-frozen-prefix-20261017"
    cfg["freqai"]["activate_tensorboard"] = False
    cfg["freqai"]["plot_feature_importances"] = 0
    cfg["freqai"]["save_backtest_models"] = False
    cfg["freqai"]["data_kitchen_thread_count"] = 2
    cfg["timerange"] = "20261008-20261009"
    cfg["user_data_dir"] = args.output.parent / "temporary_native_model_user_data"
    cfg["user_data_dir"].mkdir(parents=True, exist_ok=True)

    output = {"type": "native_FreqAI_2026_9_lightgbm_4feature_frozen_same_model_prefix_comparison",
              "model_fits": 0, "pairs": 0, "comparisons": 0,
              "prediction_mismatches": 0, "model_hash_changes": 0,
              "causal_feature_mismatches": 0, "decision_filter_mismatches": 0,
              "results": [], "not_tested": [
                  "72-feature timeframe/correlation feature expansion",
                  "original raw-price model or separate family models",
                  "entire backtesting engine and observed exchange spreads/fills",
                  "original official lookahead-analysis has_bias status",
              ]}
    for pair in cfg["exchange"]["pair_whitelist"]:
        token = pair.replace("/", "_").replace(":", "_")
        path = args.data / (token + "-5m-futures.feather")
        df = pd.read_feather(path)
        d = pd.to_datetime(df.date, utc=True)
        df = df.loc[(d >= TRAIN_START) & (d < NEXT)].reset_index(drop=True)
        d = pd.to_datetime(df.date, utc=True)
        assert df.date.is_unique and not df.empty
        trainraw = df.loc[d < CUT].reset_index(drop=True)
        assert len(trainraw) == 8640, (pair, len(trainraw))
        train = decision_features(training_labels(trainraw))
        assert train["&-trade_net_return"].iloc[-12:].isna().all()
        testraw = df.loc[d >= CUT].reset_index(drop=True)
        assert len(testraw) == 288
        df_allfeatures = decision_features(df)
        model = LightGBMRegressor(copy.deepcopy(cfg))
        model.live = False
        dk = FreqaiDataKitchen(model.config, live=False, pair=pair)
        dk.set_paths(pair, int(CUT.timestamp()))
        dk.find_features(train)
        dk.find_labels(train)
        model.model = model.train(train, pair, dk)
        output["model_fits"] += 1
        booster_text = model.model.booster_.model_to_string()
        model_hash = hashlib.sha256(booster_text.encode()).hexdigest()
        positions = [(df.index[d == CUT + pd.Timedelta(hours=h)])[0]
                     for h in TARGET_HOURS]
        pair_results = []
        for position in positions:
            target = df.date.iloc[position]
            # Intentionally include all 1-day future candles in full-history
            # features, but make prefix features ONLY through decision time.
            full = df_allfeatures.iloc[[position]].copy().reset_index(drop=True)
            prefix = decision_features(df.iloc[:position + 1].copy()).iloc[[-1]].copy().reset_index(drop=True)
            columns = [x for x in full.columns if x.startswith("%-")]
            diff = not np.allclose(
                full[columns].to_numpy(dtype=float),
                prefix[columns].to_numpy(dtype=float),
                rtol=1e-12, atol=1e-12, equal_nan=True,
            )
            p1, valid1 = model.predict(full, dk)
            di1 = dk.DI_values.copy()
            p2, valid2 = model.predict(prefix, dk)
            di2 = dk.DI_values.copy()
            pred_diff = not np.allclose(p1.values, p2.values, rtol=1e-10, atol=1e-10, equal_nan=True)
            gate_diff = not (np.array_equal(valid1, valid2) and np.allclose(di1, di2, rtol=1e-10, atol=1e-10))
            output["causal_feature_mismatches"] += int(diff)
            output["prediction_mismatches"] += int(pred_diff)
            output["decision_filter_mismatches"] += int(gate_diff)
            output["comparisons"] += 1
            pair_results.append({
                "asof_utc": str(target), "causal_features_equal": not diff,
                "frozen_model_predictions_equal": not pred_diff, "native_do_predict_and_DI_equal": not gate_diff,
                "full_prediction": float(p1.iloc[0, 0]), "asof_prediction": float(p2.iloc[0, 0]),
                "full_do_predict": int(valid1[0]), "asof_do_predict": int(valid2[0]),
                "full_di": float(di1[0]), "asof_di": float(di2[0]),
            })
        after_hash = hashlib.sha256(model.model.booster_.model_to_string().encode()).hexdigest()
        output["model_hash_changes"] += int(after_hash != model_hash)
        output["pairs"] += 1
        output["results"].append({"pair": pair, "model_sha256": model_hash, "checks": pair_results,
                                  "fit_training_end_utc": str(trainraw.date.iloc[-1]),
                                  "label_non_nan": int(train["&-trade_net_return"].notna().sum())})
        print(f"CHECK {pair} {len(pair_results)} prefix comparisons; "
              f"cumulative pred_diff={output['prediction_mismatches']}; "
              f"gate_diff={output['decision_filter_mismatches']}", flush=True)
    output["integrity_pass"] = bool(
        output["pairs"] == 25 and output["comparisons"] == 25 * len(TARGET_HOURS)
        and not output["causal_feature_mismatches"] and not output["prediction_mismatches"]
        and not output["decision_filter_mismatches"] and not output["model_hash_changes"]
    )
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print("FINAL_JSON", args.output, "PASS", output["integrity_pass"],
          "models", output["model_fits"], "comparisons", output["comparisons"], flush=True)
    return 0 if output["integrity_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
