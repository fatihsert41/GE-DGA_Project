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
        # ensure_transformer: kayıt yoksa açar, VARSA DOKUNMAZ.
        # Eskiden upsert_transformer çağrılıyordu ve mevcut trafonun
        # konumunu/sınıfını/gücünü varsayılana düşürüyordu. Ölçüm eklemek
        # varlık kaydını düzenlemek değildir.
        created = database.ensure_transformer(
            req.transformer_id, req.transformer_name)
        mid = database.save_measurement(req.transformer_id, gases, result)
        result["measurement_id"] = mid
        # Yeni bir varlık kaydı açıldıysa kullanıcı bunu bilsin: künyesi
        # boştur ve doldurulması gerekir.
        result["transformer_created"] = created

    return result
