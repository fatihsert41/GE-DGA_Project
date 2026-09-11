"""Trafo şeması uç noktası. — Faz 9.6"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import schematic as schematic_service

router = APIRouter(tags=["schematic"])


@router.get("/transformers/{transformer_id}/schematic")
def get_schematic(transformer_id: str) -> dict:
    """Şemadaki her parçanın durumu, kaynağı ve hangi sekmeye gideceği.

    Parça renklerini belirleyen KURALLAR burada; arayüz yalnızca çizer.
    Kuralı iki yerde tutmak, projede baştan beri kaçınılan hata.
    """
    result = schematic_service.build(transformer_id)
    if not result.get("found"):
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return result
