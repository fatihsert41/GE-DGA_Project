"""Mühendislik model inceleme kuyruğu (uzman etiketi) uç noktaları. (Faz 12.3)

⚠ Sıra önemli: sabit yollar (/queue, /stats, /dataset) değişkenli yoldan
(/{measurement_id}) ÖNCE tanımlanmalı. Aksi hâlde "stats" bir ölçüm id'si
sanılır ve tam sayıya çevrilemediği için 422 döner.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..auth import Identity, require_permission
from ..services import model_review as service

router = APIRouter(tags=["engineering model review"])


class LabelIn(BaseModel):
    """Mühendisin tanı kararı."""
    label: str = Field(..., description="Normal, PD, D1, D2, T1, T2, T3 ya da undetermined")
    note: str | None = Field(None, max_length=500)


@router.get("/model-reviews/queue")
def queue(folder: str = "pending") -> dict:
    if folder not in service.FOLDERS:
        raise HTTPException(status_code=400,
                            detail=f"Geçersiz klasör. Seçenekler: {', '.join(service.FOLDERS)}")
    return service.queue(folder)


@router.get("/model-reviews/stats")
def stats() -> dict:
    """Model ile uzman kararlarının karşılaştırması."""
    return service.stats()


@router.get("/model-reviews/dataset")
def dataset(format: str = "json"):  # noqa: A002 — sorgu parametresinin adı
    """Uzman etiketli veri seti ('Belirlenemedi' hariç)."""
    if format == "csv":
        return Response(
            content=service.dataset_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition":
                     'attachment; filename="uzman_etiketleri.csv"'})
    if format != "json":
        raise HTTPException(status_code=400, detail="format: json ya da csv")
    rows = service.dataset()
    return {"count": len(rows), "rows": rows}


@router.get("/model-reviews/{measurement_id}")
def detail(measurement_id: int) -> dict:
    result = service.detail(measurement_id)
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"Ölçüm bulunamadı: {measurement_id}")
    return result


@router.post("/model-reviews/{measurement_id}/label")
def label(measurement_id: int, body: LabelIn,
          identity: Identity = Depends(require_permission("engineering.review_model"))
          ) -> dict:
    code, payload = service.label(
        measurement_id, body.label, body.note,
        {"employee_no": identity.employee_no, "name": identity.name})
    if code != 200:
        raise HTTPException(status_code=code, detail=payload)
    return payload  # type: ignore[return-value]
