"""Transformer registry + measurement history endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from .. import database
from ..schemas import TransformerCreate

router = APIRouter(prefix="/transformers", tags=["transformers"])


@router.get("")
def list_all() -> dict:
    return {"transformers": database.list_transformers()}


@router.post("")
def create(t: TransformerCreate) -> dict:
    database.upsert_transformer(t.id, t.name, t.location)
    return {"ok": True, "id": t.id}


@router.get("/{transformer_id}/measurements")
def measurements(transformer_id: str) -> dict:
    return {"measurements": database.get_measurements(transformer_id)}


@router.get("/recent/measurements")
def recent(limit: int = 20) -> dict:
    return {"measurements": database.recent_measurements(limit)}
