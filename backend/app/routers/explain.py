"""POST /explain - SHAP feature contributions (Pillar A)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..ml import predictor
from ..schemas import GasReading

router = APIRouter(tags=["explainability"])


@router.post("/explain")
def explain(gases: GasReading) -> dict:
    if not predictor.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Model henüz eğitilmedi. python -m app.ml.train")
    try:
        return predictor.explain(gases.as_dict())
    except Exception as exc:  # SHAP can fail on edge inputs
        raise HTTPException(status_code=500, detail=str(exc))
