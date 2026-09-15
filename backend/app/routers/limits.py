"""Varlığa özel eşik uç noktaları — MH03. (Faz 12.4)"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import Identity, require_permission
from ..services import limits as limits_service

router = APIRouter(tags=["asset limits"])


# Alanların çoğu bilerek İSTEĞE BAĞLI: eksik gerekçe ya da tarih için
# FastAPI'nin İngilizce 422 hatası yerine kuralın Türkçe açıklaması
# (core/asset_limits.validate_proposal) dönsün.
class ProposalIn(BaseModel):
    """İstisna önerisi."""
    parameter: str = Field(..., description="water_ppm | bdv_kv | acidity_mgkoh_g | ift_mn_m")
    good_limit: float | None = None
    acceptable_limit: float | None = None
    valid_from: str | None = Field(None, description="YYYY-AA-GG; boşsa bugün")
    valid_until: str | None = Field(None, description="YYYY-AA-GG; en fazla 365 gün")
    reason: str | None = Field(None, max_length=500)


class DecisionIn(BaseModel):
    decision: str = Field(..., description="approve | reject")
    note: str | None = Field(None, max_length=500)


class RevokeIn(BaseModel):
    note: str | None = Field(None, max_length=500)


def _raise_or_return(code: int, payload: object) -> dict:
    if code != 200:
        raise HTTPException(status_code=code, detail=payload)
    return payload  # type: ignore[return-value]


@router.get("/limits/schema")
def schema() -> dict:
    """Parametreler, standart eşikler, kurallar."""
    return limits_service.schema()


@router.get("/limits/queue")
def queue(folder: str = "pending") -> dict:
    """İstisna kuyruğu. Görmek herkese açık: istisna gizli olmamalı."""
    if folder not in limits_service.FOLDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz klasör. Seçenekler: {', '.join(limits_service.FOLDERS)}")
    return limits_service.queue(folder)


@router.get("/transformers/{transformer_id}/limits")
def transformer_limits(transformer_id: str) -> dict:
    """Trafonun yürürlükteki istisnaları ve geçmişi."""
    result = limits_service.for_transformer(transformer_id)
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return result


@router.post("/transformers/{transformer_id}/limits")
def propose(transformer_id: str, body: ProposalIn,
            identity: Identity = Depends(require_permission("engineering.limits"))
            ) -> dict:
    """İstisna öner. Yürürlüğe girmesi için BAŞKA bir mühendisin onayı gerekir."""
    code, payload = limits_service.propose(
        transformer_id, body.model_dump(),
        {"employee_no": identity.employee_no, "name": identity.name})
    return _raise_or_return(code, payload)


@router.post("/limits/{override_id}/decision")
def decide(override_id: int, body: DecisionIn,
           identity: Identity = Depends(require_permission("engineering.limits"))
           ) -> dict:
    """Onayla / reddet (dört göz: öneren karar veremez)."""
    code, payload = limits_service.decide(
        override_id, body.decision, body.note,
        {"employee_no": identity.employee_no, "name": identity.name})
    return _raise_or_return(code, payload)


@router.post("/limits/{override_id}/revoke")
def revoke(override_id: int, body: RevokeIn,
           identity: Identity = Depends(require_permission("engineering.limits"))
           ) -> dict:
    """Yürürlükteki istisnayı geri çek (gerekçe zorunlu, dört göz yok)."""
    code, payload = limits_service.revoke(
        override_id, body.note,
        {"employee_no": identity.employee_no, "name": identity.name})
    return _raise_or_return(code, payload)
