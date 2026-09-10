"""Varlık kaydı (künye) ve ölçüm geçmişi uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import database
from ..core import assets, nameplate
from ..schemas import NameplateIn, TransformerCreate

router = APIRouter(prefix="/transformers", tags=["transformers"])


@router.get("")
def list_all() -> dict:
    return {"transformers": database.list_transformers()}


@router.get("/schema")
def nameplate_schema() -> dict:
    """Künye alanlarının seçenek listeleri — veri giriş formunu besler.

    Arayüz açılır listeleri buradan doldurur. Seçenekleri frontend'de
    tekrar yazmak, iki yerde iki farklı gerçek yaratırdı.
    """
    return {
        "cooling": nameplate.COOLING_TYPES,
        "vector_groups": {k: {"shift": v["shift"],
                              "phase_factor": round(float(v["phase_factor"]), 4)}
                          for k, v in nameplate.VECTOR_GROUPS.items()},
        "winding_materials": list(nameplate.WINDING_MATERIALS),
        "insulation_types": nameplate.INSULATION_TYPES,
        "tap_changer_types": nameplate.TAP_CHANGER_TYPES,
        "asset_classes": {c: {
            "name_tr": assets.ASSET_CLASSES[c]["name_tr"],
            "mva_min": assets.ASSET_CLASSES[c]["mva_min"],
            "mva_max": assets.ASSET_CLASSES[c]["mva_max"],
            "active": assets.ASSET_CLASSES[c]["active"],
        } for c in assets.CLASS_ORDER},
        "fields": database.NAMEPLATE_FIELDS,
    }


@router.post("")
def create(t: TransformerCreate) -> dict:
    """Trafo ekler veya günceller (künyesiyle birlikte)."""
    np_fields = t.nameplate.model_dump(exclude_none=True) if t.nameplate else {}

    problems = nameplate.validate({**np_fields, "mva": t.mva})
    if problems:
        raise HTTPException(status_code=400,
                            detail={"message": "Künye doğrulaması başarısız",
                                    "problems": problems})

    database.upsert_transformer(t.id, t.name, t.location,
                                asset_class=t.asset_class, mva=t.mva,
                                **np_fields)
    return {"ok": True, "id": t.id, "transformer": database.get_transformer(t.id)}


@router.get("/{transformer_id}")
def get_one(transformer_id: str) -> dict:
    """Tek trafo: künyesi ve türetilmiş büyüklükleriyle."""
    record = database.get_transformer(transformer_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return record


@router.put("/{transformer_id}/nameplate")
def update_nameplate(transformer_id: str, np_in: NameplateIn) -> dict:
    """Künyeyi kısmen günceller — gönderilmeyen alanlar korunur."""
    fields = np_in.model_dump(exclude_none=True)

    existing = database.get_transformer(transformer_id)
    if existing is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    # Doğrulama MEVCUT künyeyle birleştirilmiş hâl üzerinde yapılır:
    # tek başına geçerli görünen bir alan, kayıttaki diğer alanla
    # çelişebilir (ör. sadece lv_kv güncellenip hv_kv'nin altına düşmesi).
    merged = {**(existing.get("nameplate") or {}), **fields}
    problems = nameplate.validate(merged)
    if problems:
        raise HTTPException(status_code=400,
                            detail={"message": "Künye doğrulaması başarısız",
                                    "problems": problems})

    return {"ok": True, "transformer": database.update_nameplate(transformer_id,
                                                                 fields)}


@router.get("/{transformer_id}/measurements")
def measurements(transformer_id: str) -> dict:
    return {"measurements": database.get_measurements(transformer_id)}


@router.get("/recent/measurements")
def recent(limit: int = 20) -> dict:
    return {"measurements": database.recent_measurements(limit)}
