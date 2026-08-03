# ==========================================================
# ML MODEL TRAINER (Production Safe)
# ==========================================================
# - Atomic model save
# - Deterministic split
# - Strict performance gate
# - Compatible with Strategy loader
# ==========================================================

import os
import json
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from pathlib import Path
from config import TRADE_DATASET_PATH

# ==========================================================
# CONFIG
# ==========================================================

DATA_PATH = "ml_dataset.jsonl"

MODEL_DIR = "models"
MODEL_FILENAME = "edge_model.pkl"
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)
ENV_STATS_FILE = "environment_stats.json"

MIN_ROWS = 150
MIN_AUC = 0.60
# --------------------------------------------------
# ENVIRONMENT SCORING THRESHOLDS
# --------------------------------------------------

MIN_ENV_TRADES = 20
MIN_EXPECTANCY = 0.0
MIN_WIN_RATE = 0.45
RANDOM_STATE = 42
MODEL_SCHEMA_VERSION = 2
FEATURE_NAMES = (
    "short_range",
    "long_range",
    "trend_score",
    "wick_ratio_recent",
    "body_ratio_recent",
    "range_acceleration",
    "dist_high",
    "dist_low",
    "directional_consistency",
)


# ==========================================================
# DATA LOADER
# ==========================================================

def load_dataset():
    X = []
    y = []
    rows = []

    if not os.path.exists(DATA_PATH):
        raise RuntimeError("DATASET_NOT_FOUND")

    required_features = FEATURE_NAMES

    with open(DATA_PATH, "r") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"SKIP_INVALID_JSON | line={line_number}")
                continue

            target_r = row.get("target_r")
            if target_r is None:
                # Legacy forward-simulation rows used only `label` and had
                # incompatible semantics. They cannot be converted safely.
                print(f"SKIP_MISSING_TARGET_R | line={line_number}")
                continue

            if any(row.get(name) is None for name in required_features):
                print(f"SKIP_MISSING_FEATURES | line={line_number}")
                continue

            features = [float(row[name]) for name in required_features]

            rows.append(row)
            X.append(features)
            y.append(1 if float(target_r) > 0 else 0)

    if len(X) < MIN_ROWS:
        raise RuntimeError("NOT_ENOUGH_DATA")

    load_dataset.rows = rows
    return np.array(X), np.array(y)

# ==========================================================
# ENVIRONMENT GROUPING
# ==========================================================

def compute_environment_stats(rows):

    groups = {}

    for r in rows:

        key = (
            r.get("structure"),
            r.get("trend"),
            r.get("volatility"),
            r.get("compression"),
        )

        if key not in groups:
            groups[key] = {
                "trades": 0,
                "wins": 0,
                "mae": [],
                "mfe": [],
            }

        g = groups[key]

        g["trades"] += 1

        if float(r.get("target_r", 0)) > 0:
            g["wins"] += 1

        observation_type = r.get("observation_type")

        # Normalize environment statistics to R units. Forward simulations
        # already store mae_3/mfe_3 in R, while executed trades store their
        # canonical values in mae_r/mfe_r. Never mix USD excursion values
        # with R-unit simulation values.
        if observation_type == "EXECUTED_TRADE":
            mae = r.get("mae_r")
            mfe = r.get("mfe_r")
        elif observation_type == "FORWARD_SIMULATION":
            mae = r.get("mae_3")
            mfe = r.get("mfe_3")
        else:
            mae = r.get("mae_r")
            mfe = r.get("mfe_r")

        if mae is not None:
            g["mae"].append(float(mae))
        if mfe is not None:
            g["mfe"].append(float(mfe))

    stats = {}

    for key, g in groups.items():

        trades = g["trades"]
        win_rate = g["wins"] / trades if trades else 0

        avg_mae = float(np.mean(g["mae"])) if g["mae"] else 0
        avg_mfe = float(np.mean(g["mfe"])) if g["mfe"] else 0

        expectancy = avg_mfe - avg_mae

        env_key = "|".join([str(x) for x in key])

        # ENVIRONMENT CONFIDENCE SCORE
        sample_score = min(trades / MIN_ENV_TRADES, 1.0)
        expectancy_score = max(expectancy / 2.0, 0)

        environment_score = (
            sample_score * 0.4 +
            expectancy_score * 0.4 +
            win_rate * 0.2
        )

        environment_allowed = (
            trades >= MIN_ENV_TRADES
            and expectancy >= MIN_EXPECTANCY
            and win_rate >= MIN_WIN_RATE
        )

        stats[env_key] = {
            "trades": trades,
            "win_rate": win_rate,
            "avg_mae": avg_mae,
            "avg_mfe": avg_mfe,
            "expectancy": expectancy,
            "environment_score": environment_score,
            "environment_allowed": environment_allowed,
        }

    with open(ENV_STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

# ==========================================================
# TRAIN
# ==========================================================

def train():

    X, y = load_dataset()
    rows = getattr(load_dataset, "rows", [])

    compute_environment_stats(rows)

    # Chronological holdout: train on older observations and evaluate on
    # newer observations. Random shuffling would leak future market regimes
    # into the training set and produce an unrealistically optimistic score.
    timestamps = np.array([
        int(row.get("timestamp", 0))
        for row in rows
    ])
    order = np.argsort(timestamps, kind="stable")
    X = X[order]
    y = y[order]
    rows = [rows[index] for index in order]

    split_index = int(len(X) * 0.70)
    if split_index <= 0 or split_index >= len(X):
        raise RuntimeError("INVALID_CHRONOLOGICAL_SPLIT")

    X_train = X[:split_index]
    X_test = X[split_index:]
    y_train = y[:split_index]
    y_test = y[split_index:]

    if len(np.unique(y_train)) < 2:
        raise RuntimeError("TRAIN_SET_SINGLE_CLASS")
    if len(np.unique(y_test)) < 2:
        raise RuntimeError("TEST_SET_SINGLE_CLASS")

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model.fit(X_train_scaled, y_train)

    probs = model.predict_proba(X_test_scaled)[:, 1]
    auc = roc_auc_score(y_test, probs)

    print(f"AUC: {auc:.4f}")

    if auc < MIN_AUC:
        raise RuntimeError("MODEL_PERFORMANCE_TOO_LOW")

    # ------------------------------------------------------
    # ATOMIC SAVE (CRITICAL FOR HOT RELOAD SAFETY)
    # ------------------------------------------------------

    os.makedirs(MODEL_DIR, exist_ok=True)

    tmp_path = MODEL_PATH + ".tmp"

    artifact = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "scaler": scaler,
        "model": model,
        "validation_auc": float(auc),
        "training_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
    }

    with open(tmp_path, "wb") as f:
        pickle.dump(artifact, f)

    os.replace(tmp_path, MODEL_PATH)

    print("MODEL_UPDATED")

# Store full environment + features + outcome

DATASET_FILE = "ml_dataset.jsonl"
DATASET_SCHEMA_VERSION = 2

def record_observation(*, symbol, structure, pnl, entry_price, exit_price, qty, mae, mfe, r_multiple=None, mae_r=None, mfe_r=None, holding_time=None):
    # structure fingerprint expected to contain all environment fields
    if not structure:
        return False

    if not isinstance(structure, dict):
        return False

    # Use R multiple as learning target (better than binary win/loss)
    target_r = r_multiple if r_multiple is not None else 0

    observation = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "observation_type": "EXECUTED_TRADE",
        "timestamp": int(__import__("time").time()),
        "symbol": symbol,
        "structure": structure.get("structure"),
        "trend": structure.get("trend"),
        "volatility": structure.get("volatility"),
        "compression": structure.get("compression"),

        # --------------------------------------------------
        # Features (used by ML trainer)
        # --------------------------------------------------
        "short_range": structure.get("short_range"),
        "long_range": structure.get("long_range"),
        "trend_score": structure.get("trend_score", 0),
        "wick_ratio_recent": structure.get("wick_ratio_recent", 0),
        "body_ratio_recent": structure.get("body_ratio_recent", 0),
        "range_acceleration": structure.get("range_acceleration", 0),
        "dist_high": structure.get("dist_high", 0),
        "dist_low": structure.get("dist_low", 0),
        "directional_consistency": structure.get("directional_consistency", 0),

        # --------------------------------------------------
        # Outcome
        # --------------------------------------------------
        "pnl": pnl,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "target_r": target_r,
        "mae_usd": mae,
        "mfe_usd": mfe,
        "r_multiple": r_multiple,
        "mae_r": mae_r,
        "mfe_r": mfe_r,
        "holding_time": holding_time,
    }

    with open(DATASET_FILE, "a") as f:
        f.write(json.dumps(observation) + "\n")
        f.flush()
        os.fsync(f.fileno())

    return True

def store_trade_observation(observation: dict):
    path = Path(TRADE_DATASET_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a") as f:
        f.write(json.dumps(observation) + "\n")

# ==========================================================
# ENTRYPOINT
# ==========================================================

if __name__ == "__main__":
    train()
