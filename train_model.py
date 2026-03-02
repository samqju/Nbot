import os
import json
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

DATA_PATH = "ml_dataset.jsonl"
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "edge_model.pkl")

MIN_ROWS = 200
MIN_AUC = 0.60


def load_dataset():
    X = []
    y = []

    if not os.path.exists(DATA_PATH):
        raise RuntimeError("DATASET_NOT_FOUND")

    with open(DATA_PATH, "r") as f:
        for line in f:
            row = json.loads(line)

            features = [
                row["short_range"],
                row["long_range"],
                row["trend_score"],
                row["wick_ratio_recent"],
                row["body_ratio_recent"],
                row["range_acceleration"],
                row["dist_high"],
                row["dist_low"],
                row["directional_consistency"],
            ]

            X.append(features)
            y.append(row["label"])

    return np.array(X), np.array(y)


def train():
    X, y = load_dataset()

    if len(X) < MIN_ROWS:
        raise RuntimeError("NOT_ENOUGH_DATA")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        random_state=42,
    )

    model.fit(X_train, y_train)

    probs = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, probs)

    print("AUC:", auc)

    if auc < MIN_AUC:
        raise RuntimeError("MODEL_PERFORMANCE_TOO_LOW")

    os.makedirs(MODEL_DIR, exist_ok=True)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump((scaler, model), f)

    print("MODEL_UPDATED")


if __name__ == "__main__":
    train()

import os
import json
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

DATA_PATH = "ml_dataset.jsonl"
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "edge_model.pkl")

MIN_ROWS = 150
MIN_AUC = 0.60


def load_dataset():
    X = []
    y = []

    if not os.path.exists(DATA_PATH):
        raise RuntimeError("DATASET_NOT_FOUND")

    with open(DATA_PATH, "r") as f:
        for line in f:
            row = json.loads(line)

            features = [
                row["short_range"],
                row["long_range"],
                row["trend_score"],
                row["wick_ratio_recent"],
                row["body_ratio_recent"],
                row["range_acceleration"],
                row["dist_high"],
                row["dist_low"],
                row["directional_consistency"],
            ]

            X.append(features)
            y.append(row["label"])

    return np.array(X), np.array(y)


def train():
    X, y = load_dataset()

    if len(X) < MIN_ROWS:
        raise RuntimeError("NOT_ENOUGH_DATA")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        random_state=42,
    )

    model.fit(X_train, y_train)

    probs = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, probs)

    print("AUC:", auc)

    if auc < MIN_AUC:
        raise RuntimeError("MODEL_PERFORMANCE_TOO_LOW")

    os.makedirs(MODEL_DIR, exist_ok=True)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump((scaler, model), f)

    print("MODEL_UPDATED")


if __name__ == "__main__":
    train()
