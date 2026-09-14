"""POST /predict - full diagnosis for a single gas reading."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header

from .. import database
from ..auth import check_permission, require_identity
from ..schemas import PredictRequest
from ..services.diagnosis import diagnose

router = APIRouter(tags=["diagnosis"])


@router.post("/predict")
def predict(req: PredictRequest,
            authorization: Optional[str] = Header(default=None)) -> dict:
    # Faz 10: TANI KOYMAK serbest, KAYDETMEK yetki ister.
    #
    # Kaydetmeden deneme yapmak (hazır örnekler, "şu değerler ne der?")
    # veriyi değiştirmez; herkes yapabilir. Ama ölçümü trafonun geçmişine
    # yazmak bir test kaydıdır ve DGA yetkisi olan birinin sorumluluğundadır.
    # Yetki kontrolü tanıdan ÖNCE: reddedilecek bir isteğe model çalıştırmak
    # boşa iştir.
    identity = None
    if req.persist and req.transformer_id:
        identity = require_identity(authorization)
        check_permission(identity, "tests.dga")

    gases = req.gases.as_dict()
    result = diagnose(gases)

    if req.persist and req.transformer_id:
        # ensure_transformer: kayıt yoksa açar, VARSA DOKUNMAZ.
        # Eskiden upsert_transformer çağrılıyordu ve mevcut trafonun
        # konumunu/sınıfını/gücünü varsayılana düşürüyordu. Ölçüm eklemek
        # varlık kaydını düzenlemek değildir.
        created = database.ensure_transformer(
            req.transformer_id, req.transformer_name)
        mid = database.save_measurement(
            req.transformer_id, gases, result,
            recorded_by={"employee_no": identity.employee_no,
                         "name": identity.name} if identity else None)
        result["measurement_id"] = mid
        # Yeni bir varlık kaydı açıldıysa kullanıcı bunu bilsin: künyesi
        # boştur ve doldurulması gerekir.
        result["transformer_created"] = created

    return result
