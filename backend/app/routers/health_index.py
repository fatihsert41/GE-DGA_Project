"""Sağlık endeksi uç noktaları. — Faz 8.5"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core import health_index as core_health
from ..services import health as health_service

router = APIRouter(tags=["health"])


@router.get("/health-index/schema")
def schema() -> dict:
    """Boyutlar, ağırlıklar ve bantlar — arayüz açıklamayı buradan alır.

    Ağırlıkları frontend'e sabit yazmak, formül değiştiğinde arayüzün
    yalan söylemesine yol açardı (künye şemasında da aynı gerekçeyle
    seçenekler tek yerden veriliyor).
    """
    return {
        "dimensions": [core_health.DIMENSIONS[k]
                       for k in core_health.DIMENSION_ORDER],
        "bands": [{"min": lo, "band": code, "band_tr": label, "action": act}
                  for lo, code, label, act in core_health.BANDS],
        "formula": "Σ(ağırlık × puan) ÷ Σ(ağırlık)",
        "critical_cap": core_health.CRITICAL_CAP,
        "dga_scores": core_health.DGA_SCORES,
        "oil_scores": core_health.OIL_SCORES,
    }


@router.get("/health-index/fleet")
def fleet() -> dict:
    """Filo geneli sağlık listesi — en kötü durumdaki varlık başta."""
    return health_service.fleet_health()


@router.get("/transformers/{transformer_id}/health")
def transformer(transformer_id: str) -> dict:
    """Tek trafonun sağlık endeksi, boyut boyut açılmış hâliyle."""
    result = health_service.transformer_health(transformer_id)
    if not result.get("found"):
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return result
