"""Comparison endpoints (Pillar B).

* GET  /compare/leaderboard - ML vs classical accuracy from training.
* POST /compare             - run every method on one reading side by side.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..core.classify import classical_methods
from ..ml import predictor
from ..schemas import GasReading

router = APIRouter(prefix="/compare", tags=["comparison"])

_METRICS = Path(__file__).resolve().parents[2] / "artifacts" / "metrics.json"


@router.get("/leaderboard")
def leaderboard() -> dict:
    if not _METRICS.exists():
        return {"available": False,
                "message": "Model henüz eğitilmedi. python -m app.ml.train"}
    with open(_METRICS) as fh:
        metrics = json.load(fh)
    return {"available": True, **metrics}


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
