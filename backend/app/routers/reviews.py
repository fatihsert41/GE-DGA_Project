"""Mühendislik test onay kuyruğu uç noktaları. (Faz 12.2)"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import Identity, require_permission
from ..core import review as core_review
from ..services import review as review_service

router = APIRouter(tags=["engineering review"])


class DecisionIn(BaseModel):
    """Mühendis kararı."""
    decision: str = Field(..., description="approve | reject | retest")
    note: str | None = Field(None, max_length=500,
                             description="Gerekçe (reddet/tekrar için zorunlu)")


@router.get("/reviews/schema")
def schema() -> dict:
    """Durumlar, kararlar ve kurallar — arayüz etiketleri buradan alır."""
    return {
        "statuses": core_review.STATUS_LABELS,
        "decisions": list(core_review.DECISIONS),
        "kinds": {k: v["label"] for k, v in core_review.KINDS.items()},
        "folders": list(review_service.FOLDERS),
        "note_min_length": core_review.NOTE_MIN_LENGTH,
        "trigger": ("Genel hükmü 'kötü' olan yağ, elektriksel ve "
                    "buşing/kademe testleri onay bekler."),
    }


@router.get("/reviews/queue")
def queue(folder: str = core_review.PENDING) -> dict:
    """Onay kuyruğu. Görmek herkese açık; karar vermek yetki ister."""
    if folder not in review_service.FOLDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz klasör. Seçenekler: {', '.join(review_service.FOLDERS)}")
    return review_service.queue(folder)


@router.post("/reviews/{kind}/{test_id}/decision")
def decide(kind: str, test_id: int, body: DecisionIn,
           identity: Identity = Depends(require_permission("engineering.approve"))
           ) -> dict:
    """Onayla / reddet / tekrar ölçülsün."""
    code, payload = review_service.decide(
        kind, test_id, body.decision, body.note,
        {"employee_no": identity.employee_no, "name": identity.name})
    if code != 200:
        raise HTTPException(status_code=code, detail=payload)
    return payload  # type: ignore[return-value]
