"""Orchestrates a full diagnosis for one gas reading.

Combines the ML prediction (when a model is trained) with the classical
consensus and the IEEE risk assessment into a single response object used
by the /predict endpoint and by persistence.
"""
from __future__ import annotations

from typing import Dict

from ..core import risk
from ..core.classify import consensus
from ..core.gases import FAULT_GROUP, FAULT_LABELS_TR
from ..ml import predictor


def diagnose(gases: Dict[str, float]) -> Dict[str, object]:
    classical = consensus(gases)
    risk_info = classical["risk"]

    if predictor.is_ready():
        ml = predictor.predict(gases)
        prediction = ml["prediction"]
        confidence = ml["confidence"]
        source = "ml"
    else:  # graceful fallback before training
        ml = None
        prediction = classical["prediction"]
        confidence = classical["confidence"]
        source = "classical"

    agreement = (ml is not None
                 and ml["prediction"] == classical["prediction"])

    return {
        "prediction": prediction,
        "prediction_label": FAULT_LABELS_TR.get(prediction, prediction),
        "prediction_group": FAULT_GROUP.get(prediction, "Belirsiz"),
        "confidence": confidence,
        "source": source,
        "ml": ml,
        "classical": {
            "prediction": classical["prediction"],
            "confidence": classical["confidence"],
            "votes": classical["votes"],
        },
        "agreement": agreement,
        "risk": risk_info,
    }
