"""Load the trained model once and serve predictions + SHAP explanations.

Kept as a lazy singleton so the FastAPI process loads artifacts a single
time. If no model has been trained yet, ``is_ready`` is False and the API
surfaces a clear "train first" message instead of crashing.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np

from .features import FEATURE_NAMES, features_from_dict

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts"
_MODEL_PATH = ARTIFACT_DIR / "model.joblib"

_lock = threading.Lock()
_bundle: Optional[dict] = None
_explainer = None  # lazily built SHAP explainer


def _load() -> Optional[dict]:
    global _bundle
    if _bundle is None and _MODEL_PATH.exists():
        with _lock:
            if _bundle is None:
                _bundle = joblib.load(_MODEL_PATH)
    return _bundle


def model_info() -> Dict[str, object]:
    """Modelin kimliği ve eşik ölçümü — her tanıya iliştirilir.

    Dış inceleme P0-4: eşiğin hangi modelde ölçüldüğü, eşiğin kendisi kadar
    önemli. Bu bilgi taşınmadığı için başka bir modelde ölçülen 0.90 değeri
    buraya sessizce taşınmıştı.
    """
    art = _load()
    if art is None:
        return {"available": False}
    return {
        "available": True,
        "model_id": art.get("model_id"),
        "model_name": art.get("model_name"),
        "data_profile": art.get("data_profile"),
        "trained_at": art.get("trained_at"),
        "n_features": len(art.get("feature_names") or []),
        "threshold": art.get("threshold"),
    }


def is_ready() -> bool:
    return _load() is not None


def model_name() -> Optional[str]:
    b = _load()
    return b["model_name"] if b else None


def _proba(bundle: dict, x: np.ndarray) -> Dict[str, float]:
    """Class-name -> probability. Models are trained on int labels whose
    value equals the index into ``classes`` (see train.py)."""
    model, classes = bundle["model"], bundle["classes"]
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x)[0]
        order = list(int(c) for c in model.classes_)  # encoded ints present
        return {cls: (float(probs[order.index(idx)]) if idx in order else 0.0)
                for idx, cls in enumerate(classes)}
    pred_idx = int(model.predict(x)[0])
    return {cls: (1.0 if idx == pred_idx else 0.0)
            for idx, cls in enumerate(classes)}


def predict(g: Dict[str, float]) -> Dict[str, object]:
    bundle = _load()
    if bundle is None:
        raise RuntimeError("Model not trained. Run: python -m app.ml.train")
    x = features_from_dict(g)
    probs = _proba(bundle, x)
    prediction = max(probs, key=probs.get)
    return {
        "prediction": prediction,
        "confidence": round(probs[prediction], 4),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "model_name": bundle["model_name"],
    }


def _get_explainer():
    """Build a SHAP explainer for the winning model (tree or kernel)."""
    global _explainer
    if _explainer is not None:
        return _explainer
    import shap  # imported lazily; heavy dependency

    bundle = _load()
    model = bundle["model"]
    inner = model
    # Unwrap sklearn Pipelines to reach the estimator.
    if hasattr(model, "named_steps"):
        inner = list(model.named_steps.values())[-1]
    try:
        _explainer = shap.TreeExplainer(inner)
    except Exception:  # non-tree models -> model-agnostic fallback
        from .synth import make_dataset
        from .features import build_features
        bg = build_features(make_dataset(n=200, seed=1).drop(columns=["label"]))
        _explainer = shap.KernelExplainer(model.predict_proba, bg.iloc[:50])
    return _explainer


def explain(g: Dict[str, float]) -> Dict[str, object]:
    """Per-feature SHAP contributions toward the predicted class."""
    bundle = _load()
    if bundle is None:
        raise RuntimeError("Model not trained. Run: python -m app.ml.train")

    result = predict(g)
    pred = result["prediction"]
    classes = bundle["classes"]
    x = features_from_dict(g)

    explainer = _get_explainer()
    shap_values = explainer.shap_values(x)

    # Normalise SHAP output shape across versions/models to a 1-D vector
    # of contributions for the predicted class.
    class_idx = classes.index(pred) if pred in classes else 0
    contributions = _extract_class_contrib(
        shap_values, class_idx, n_features=len(FEATURE_NAMES),
        n_classes=len(classes))

    contribs: List[Dict[str, object]] = [
        {"feature": name, "value": round(float(x.iloc[0, i]), 3),
         "shap": round(float(contributions[i]), 4)}
        for i, name in enumerate(FEATURE_NAMES)
    ]
    contribs.sort(key=lambda c: abs(c["shap"]), reverse=True)
    return {
        "prediction": pred,
        "confidence": result["confidence"],
        "model_name": bundle["model_name"],
        "contributions": contribs,
    }


def _extract_class_contrib(shap_values, class_idx: int, n_features: int,
                           n_classes: int) -> np.ndarray:
    """Reduce any SHAP output to a 1-D per-feature vector for one class.

    SHAP returns different layouts by version/model. We locate the feature
    axis (== n_features) and the class axis (== n_classes) explicitly, then
    take the single sample and the requested class.
    """
    # Some SHAP versions return a python list, one array per class.
    if isinstance(shap_values, list):
        arr = np.asarray(shap_values[class_idx])
        return arr.reshape(-1)[:n_features] if arr.ndim == 1 else arr[0]

    arr = np.asarray(shap_values)
    if arr.ndim == 1:                         # (n_feat,)
        return arr
    if arr.ndim == 2:                         # (n_samples, n_feat)
        return arr[0, :]
    if arr.ndim == 3:
        # Identify which trailing axes are features vs classes.
        feat_axis = next((a for a in range(3) if arr.shape[a] == n_features), 1)
        class_axis = next(
            (a for a in range(3)
             if a != feat_axis and arr.shape[a] == n_classes), None)
        arr = arr[0] if arr.shape[0] == 1 else arr  # drop sample axis if size 1
        if arr.ndim == 2:  # now (feat, class) or (class, feat)
            if class_axis is not None and class_axis - 1 == 0:
                return arr[class_idx, :]
            return arr[:, class_idx]
    return np.asarray(shap_values).reshape(-1)[:n_features]
