"""POST /predict - full diagnosis for a single gas reading."""
from __future__ import annotations

from fastapi import APIRouter

from .. import database
from ..schemas import PredictRequest
from ..services.diagnosis import diagnose

router = APIRouter(tags=["diagnosis"])


@router.post("/predict")
def predict(req: PredictRequest) -> dict:
    gases = req.gases.as_dict()
    result = diagnose(gases)

    if req.persist and req.transformer_id:
        database.upsert_transformer(
            req.transformer_id, req.transformer_name or req.transformer_id)
        mid = database.save_measurement(req.transformer_id, gases, result)
        result["measurement_id"] = mid

    return result
