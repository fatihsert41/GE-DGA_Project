"""Fiziksel gözlem uç noktaları. — Faz 9.5"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import database
from ..auth import Identity, require_identity
from ..core import physical as core_physical
from ..services import physical as physical_service

router = APIRouter(tags=["physical inspection"])


class InspectionIn(BaseModel):
    """Gözlem turu girişi.

    ``observations``: {"oil_leak": "iyi", "cooling": "kötü", ...}
    Boş bırakılan maddeler "bakılmadı" sayılır — zorlamak, teknisyeni
    bakmadığı bir maddeye "iyi" demeye iter ve veriyi bozar.
    """
    observations: dict = Field(default_factory=dict)
    inspected_at: str | None = None
    notes: str | None = Field(None, max_length=500)


@router.get("/physical/schema")
def physical_schema() -> dict:
    """Kontrol listesi maddeleri, gruplar ve ne aranacağı."""
    return core_physical.schema()


@router.get("/physical/fleet")
def physical_fleet() -> dict:
    """Filo geneli gözlem durumu + hiç bakılmamışlar."""
    return physical_service.fleet_summary()


@router.get("/transformers/{transformer_id}/inspections")
def list_inspections(transformer_id: str) -> dict:
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return physical_service.history(transformer_id)


@router.post("/transformers/{transformer_id}/inspections")
def create_inspection(transformer_id: str, body: InspectionIn,
                      identity: Identity = Depends(require_identity)) -> dict:
    """Yeni gözlem turu kaydeder."""
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    known = {k: v for k, v in body.observations.items()
             if k in core_physical.ITEMS and v in core_physical.RATINGS}
    checked = {k: v for k, v in known.items() if v != "bakılmadı"}
    if not checked:
        raise HTTPException(
            status_code=400,
            detail="En az bir madde işaretlenmelidir. Hiçbir maddeye "
                   "bakılmamış bir tur, kayda değer bilgi taşımaz.")

    inspection_id = database.save_physical_inspection(
        transformer_id, known, inspected_at=body.inspected_at,
        notes=body.notes,
        recorded_by={"employee_no": identity.employee_no,
                     "name": identity.name})

    saved = next(r for r in database.get_physical_inspections(transformer_id)
                 if r["id"] == inspection_id)
    return {"ok": True, "id": inspection_id,
            "assessment": physical_service.assess_inspection(saved)}
