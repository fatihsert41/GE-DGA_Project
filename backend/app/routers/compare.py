"""Comparison endpoints (Pillar B).

* GET  /compare/leaderboard    - ML vs classical accuracy from training.
* GET  /compare/reality-check  - synthetic-vs-real performance (Faz 6).
* POST /compare                - run every method on one reading side by side.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..core.classify import classical_methods
from ..ml import predictor
from ..schemas import GasReading

router = APIRouter(prefix="/compare", tags=["comparison"])

_ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts"
_METRICS = _ARTIFACTS / "metrics.json"
_SAFETY = _ARTIFACTS / "safety_report.json"


@router.get("/leaderboard")
def leaderboard() -> dict:
    if not _METRICS.exists():
        return {"available": False,
                "message": "Model henüz eğitilmedi. python -m app.ml.train"}
    with open(_METRICS) as fh:
        metrics = json.load(fh)
    return {"available": True, **metrics}


@router.get("/reality-check")
def reality_check() -> dict:
    """Sentetik test ile gerçek veri performansını yan yana verir. — Faz 6

    Arayüzün dürüstlük rozetini besler: "model %96" demek yalnızca
    sentetik test verisi için doğrudur. Gerçek veri sayıları
    `python -m app.ml.safety_eval` ile üretilir.
    """
    synthetic = None
    if _METRICS.exists():
        with open(_METRICS, encoding="utf-8") as fh:
            m = json.load(fh)
        best = next((r for r in m.get("leaderboard", [])
                     if r["model"] == m.get("best_model")), None)
        synthetic = {
            "model": m.get("best_model"),
            "accuracy": (best or {}).get("accuracy"),
            "f1_macro": (best or {}).get("f1_macro"),
            "n_test": m.get("n_test"),
            "note": "Sentetik test verisi (IEC 60599 imzalarından üretildi).",
        }

    if not _SAFETY.exists():
        return {"available": False, "synthetic": synthetic,
                "message": "Gerçek veri değerlendirmesi yok. "
                           "python -m app.ml.safety_eval --real <dosya>"}

    with open(_SAFETY, encoding="utf-8") as fh:
        rep = json.load(fh)

    return {
        "available": True,
        "synthetic": synthetic,
        "real": {
            "generated_at": rep.get("generated_at"),
            "n_test": rep.get("n_test"),
            "seven_class": rep.get("seven_class"),
            "fault_recall": rep["fault_detection"]["recall"],
            "false_alarm_rate": rep["fault_detection"]["false_alarm_rate"],
            "family_accuracy": rep["family"]["accuracy"],
            "severe": rep.get("severe"),
            "selective": rep.get("selective"),
            "note": "Bağımsız gerçek trafo ölçümleri (5 gaz; CO/CO2 yok).",
        },
    }


@router.post("")
def compare(gases: GasReading) -> dict:
    g = gases.as_dict()
    methods = classical_methods(g)
    ml = predictor.predict(g) if predictor.is_ready() else None
    return {
        "gases": g,
        "classical": {
            "duval": methods["duval"],
            "rogers": methods["rogers"],
            "iec": methods["iec"],
            "key_gas": methods["key_gas"],
        },
        "ml": ml,
    }
