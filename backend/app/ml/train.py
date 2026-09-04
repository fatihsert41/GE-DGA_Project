"""Train and compare models, then persist the winner + a leaderboard.

Pillar B (multi-method comparison): several ML models AND the classical
consensus are evaluated on the *same* held-out test set, so the report can
show ML-vs-classical accuracy side by side. Pillar A (explainability) is
served later from the saved tree model via SHAP.

Run:  python -m app.ml.train
Artifacts written to backend/artifacts/:
    model.joblib      - winning pipeline + metadata
    metrics.json      - leaderboard, per-class report, confusion matrix
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from ..core.classify import consensus
from ..core.gases import FAULT_CLASSES
from .features import FEATURE_NAMES, build_features
from .synth import make_dataset

try:  # XGBoost is optional at runtime but expected in requirements.
    from xgboost import XGBClassifier
    _HAS_XGB = True
except Exception:  # pragma: no cover
    _HAS_XGB = False

try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except Exception:  # pragma: no cover
    _HAS_SMOTE = False

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts"
CLASSES = FAULT_CLASSES  # fixed label order


def _candidate_models() -> Dict[str, object]:
    models: Dict[str, object] = {
        "RandomForest": RandomForestClassifier(
            n_estimators=300, max_depth=None, random_state=42, n_jobs=-1),
        "SVM": Pipeline([
            ("scale", StandardScaler()),
            ("svc", SVC(kernel="rbf", C=10, gamma="scale",
                        probability=True, random_state=42)),
        ]),
        "NeuralNet": Pipeline([
            ("scale", StandardScaler()),
            ("mlp", MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=800,
                                  random_state=42)),
        ]),
    }
    if _HAS_XGB:
        models["XGBoost"] = XGBClassifier(
            n_estimators=400, max_depth=5, learning_rate=0.1,
            subsample=0.9, colsample_bytree=0.9, random_state=42,
            tree_method="hist", eval_metric="mlogloss")
    return models


def _classical_accuracy(raw_test: pd.DataFrame) -> float:
    """Consensus of classical methods scored on the same test rows."""
    correct = 0
    for _, row in raw_test.iterrows():
        g = {k: float(row[k]) for k in FEATURE_NAMES if k in row}
        pred = consensus({k: float(row[k]) for k in row.index if k != "label"})
        if pred["prediction"] == row["label"]:
            correct += 1
    return correct / len(raw_test)


def train(n_samples: int = 4000, seed: int = 42) -> Dict[str, object]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    raw = make_dataset(n=n_samples, seed=seed)

    X = build_features(raw.drop(columns=["label"]))
    y_str = raw["label"].astype(str)
    # Encode labels to ints in the fixed CLASSES order (XGBoost requires
    # 0..n-1); the same order is stored so predictions decode consistently.
    label_to_int = {c: i for i, c in enumerate(CLASSES)}
    y = y_str.map(label_to_int)

    X_train, X_test, y_train, y_test, raw_train, raw_test = train_test_split(
        X, y, raw, test_size=0.25, random_state=seed, stratify=y)
    y_test_str = [CLASSES[i] for i in y_test]

    # Balance the training set only (never the test set).
    if _HAS_SMOTE:
        X_train_bal, y_train_bal = SMOTE(random_state=seed).fit_resample(
            X_train, y_train)
    else:  # pragma: no cover
        X_train_bal, y_train_bal = X_train, y_train

    leaderboard: List[Dict[str, object]] = []
    fitted: Dict[str, object] = {}
    for name, model in _candidate_models().items():
        t0 = time.time()
        model.fit(X_train_bal, y_train_bal)
        pred = [CLASSES[int(i)] for i in model.predict(X_test)]
        leaderboard.append({
            "model": name,
            "type": "ML",
            "accuracy": round(float(accuracy_score(y_test_str, pred)), 4),
            "f1_macro": round(float(f1_score(y_test_str, pred,
                                             average="macro")), 4),
            "train_seconds": round(time.time() - t0, 2),
        })
        fitted[name] = model

    # Classical consensus on the identical test set.
    leaderboard.append({
        "model": "Classical Consensus",
        "type": "Classical",
        "accuracy": round(float(_classical_accuracy(raw_test)), 4),
        "f1_macro": None,
        "train_seconds": 0.0,
    })

    leaderboard.sort(key=lambda r: (r["accuracy"] or 0), reverse=True)
    best_ml = max(
        (r for r in leaderboard if r["type"] == "ML"),
        key=lambda r: r["f1_macro"])
    best_name = str(best_ml["model"])
    best_model = fitted[best_name]

    # Detailed report for the winning model.
    best_pred = [CLASSES[int(i)] for i in best_model.predict(X_test)]
    report = classification_report(
        y_test_str, best_pred, labels=CLASSES, output_dict=True,
        zero_division=0)
    cm = confusion_matrix(y_test_str, best_pred, labels=CLASSES).tolist()

    joblib.dump(
        {
            "model": best_model,
            "model_name": best_name,
            "feature_names": FEATURE_NAMES,
            "classes": CLASSES,
        },
        ARTIFACT_DIR / "model.joblib",
    )

    metrics = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_samples": n_samples,
        "n_test": int(len(X_test)),
        "best_model": best_name,
        "leaderboard": leaderboard,
        "classes": CLASSES,
        "confusion_matrix": cm,
        "classification_report": report,
    }
    with open(ARTIFACT_DIR / "metrics.json", "w") as fh:
        json.dump(metrics, fh, indent=2)

    return metrics


if __name__ == "__main__":
    m = train()
    print(f"Best model: {m['best_model']}")
    for row in m["leaderboard"]:
        f1 = row["f1_macro"]
        f1s = f"{f1:.4f}" if isinstance(f1, float) else " n/a "
        print(f"  {row['model']:<22} acc={row['accuracy']:.4f}  f1={f1s}")
