"""Varlık yaşam döngüsü uç noktaları. — Faz 9.35"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import database
from ..auth import Identity, require_identity
from ..core import lifecycle as core_lifecycle

router = APIRouter(tags=["lifecycle"])


class LifecycleChangeIn(BaseModel):
    """Durum değiştirme isteği."""
    status: str = Field(..., description="Hedef durum kodu")
    note: str | None = Field(None, max_length=300,
                             description="Gerekçe / açıklama")


@router.get("/lifecycle/schema")
def lifecycle_schema() -> dict:
    """Durumlar, evreler ve izinli geçişler.

    Arayüz açılır listeyi ve "buradan nereye gidilebilir" bilgisini
    buradan alır; geçiş kurallarını frontend'de tekrar yazmak iki yerde
    iki farklı gerçek yaratırdı.
    """
    return {
        "states": core_lifecycle.ordered_states(),
        "phases": [core_lifecycle.PHASES[p]
                   for p in core_lifecycle.PHASE_ORDER],
        "default": core_lifecycle.DEFAULT_STATE,
        "note": "Periyodik numune takvimi YALNIZCA 'Devrede' durumunda "
                "işler. Fabrikada ya da yolda bekleyen bir ünite "
                "'numunesi gecikmiş' sayılmaz.",
    }


@router.get("/transformers/{transformer_id}/lifecycle")
def get_lifecycle(transformer_id: str) -> dict:
    """Varlığın güncel durumu ve geçiş geçmişi."""
    record = database.get_transformer(transformer_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    current = record.get("lifecycle_status")
    events = database.get_lifecycle_events(transformer_id)

    return {
        "transformer_id": transformer_id,
        "current": core_lifecycle.summary(current),
        "changed_at": record.get("lifecycle_changed_at"),
        # Geçmiş SİLİNMEZ: "bu ünite ne zaman devreye alındı, ne zaman
        # hizmet dışı kaldı" varlık yönetiminin temel sorularından biri.
        "events": [
            {
                **e,
                "from_label": (core_lifecycle.get(e["from_status"])["label_tr"]
                               if e.get("from_status") else None),
                "to_label": core_lifecycle.get(e["to_status"])["label_tr"],
            }
            for e in events
        ],
    }


@router.put("/transformers/{transformer_id}/lifecycle")
def change_lifecycle(transformer_id: str, body: LifecycleChangeIn,
                     identity: Identity = Depends(require_identity)) -> dict:
    """Durumu değiştirir — kurallı geçiş, kim yaptığı kaydedilir.

    Geçiş kuralı ``core/lifecycle`` içinde; bu uç nokta yalnızca onu
    çağırıp sonucu HTTP'ye çevirir. Kuralı saf modülde tutmak, onu
    doğrudan test edilebilir kılıyor.
    """
    record = database.get_transformer(transformer_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    current = record.get("lifecycle_status")
    problem = core_lifecycle.validate_transition(current, body.status)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    updated = database.set_lifecycle(
        transformer_id, body.status, body.note,
        changed_by={"employee_no": identity.employee_no,
                    "name": identity.name})

    return {
        "ok": True,
        "transformer_id": transformer_id,
        "current": core_lifecycle.summary(
            (updated or {}).get("lifecycle_status")),
    }
