"""Filo dashboard uç noktaları (Faz 5.2)."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import fleet

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/overview")
def fleet_overview() -> dict:
    """Filo geneli: her trafonun son tanısı + risk/arıza dağılımı."""
    return fleet.overview()
