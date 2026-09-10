"""Yağ kalitesi testleri uç noktaları. — Faz 8.3

DGA ölçümlerinden AYRI bir kaynak: farklı laboratuvar testleri, farklı
sıklık, farklı yorum. Aynı uç noktaya sıkıştırmak ikisini de bulandırırdı.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import database
from ..core import oil_quality
from ..schemas import OilTestIn
from ..services import oil as oil_service

router = APIRouter(tags=["oil quality"])


@router.get("/oil/schema")
def oil_schema() -> dict:
    """Parametreler, birimleri, standartları ve eşikleri.

    Veri giriş formunu ve arayüzdeki açıklamaları besler. Eşikleri
    frontend'de tekrar yazmak iki yerde iki farklı gerçek yaratırdı.
    """
    return {
        "parameters": {
            name: {
                "label": spec["label"],
                "unit": spec["unit"],
                "direction": spec["direction"],
                "standard": spec["standard"],
                "meaning": spec["meaning"],
                "thresholds": spec["thresholds"],
            }
            for name, spec in oil_quality.LIMITS.items()
        },
        "voltage_classes": list(oil_quality.VOLTAGE_CLASSES),
        "paper": {
            "model": "Chendong (IEC 61198)",
            "formula": "log10(2FAL) = 1.51 - 0.0035 x DP",
            "dp_new": oil_quality.DP_NEW,
            "dp_end_of_life": oil_quality.DP_END_OF_LIFE,
            "bands": [{"min_dp": lo, "band": name, "description": desc}
                      for lo, name, desc in oil_quality.DP_BANDS],
            "caveat": ("Bağıntı standart kraft kağıt için türetildi; termal "
                       "yükseltilmiş kağıtta (TUK) DP olduğundan yüksek "
                       "görünür."),
        },
        "fields": database.OIL_TEST_FIELDS,
    }


@router.get("/oil/fleet")
def oil_fleet() -> dict:
    """Filo geneli yağ durumu ve en yaşlı kağıtlar."""
    return oil_service.fleet_summary()


@router.get("/transformers/{transformer_id}/oil-tests")
def list_oil_tests(transformer_id: str) -> dict:
    """Trafonun yağ testi geçmişi + en sonun değerlendirmesi."""
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return oil_service.history(transformer_id)


@router.post("/transformers/{transformer_id}/oil-tests")
def create_oil_test(transformer_id: str, test: OilTestIn) -> dict:
    """Yeni bir yağ kalitesi testi kaydeder ve hemen değerlendirir."""
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    values = test.model_dump(exclude_none=True)
    measured = [k for k in database.OIL_TEST_FIELDS if k in values]
    if not measured:
        raise HTTPException(
            status_code=400,
            detail="En az bir test değeri girilmelidir. "
                   f"Alanlar: {', '.join(database.OIL_TEST_FIELDS)}")

    test_id = database.save_oil_test(
        transformer_id, values,
        sampled_at=test.sampled_at, lab=test.lab, notes=test.notes)

    saved = next(t for t in database.get_oil_tests(transformer_id)
                 if t["id"] == test_id)
    return {"ok": True, "id": test_id,
            "assessment": oil_service.assess_test(transformer_id, saved)}
