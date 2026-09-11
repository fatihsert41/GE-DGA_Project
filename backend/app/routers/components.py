"""Bileşen testi uç noktaları: buşing ve kademe değiştirici. — Faz 9.4"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from .. import database
from ..auth import Identity, require_identity
from ..core import components as core_components
from ..schemas import ComponentTestIn
from ..services import components as component_service

router = APIRouter(tags=["components"])


@router.get("/components/schema")
def components_schema() -> dict:
    """Buşing ve kademe değiştirici eşikleri, alanları, anlamları."""
    return core_components.schema()


@router.get("/components/fleet")
def components_fleet() -> dict:
    """Filo geneli bileşen durumu + hiç test edilmemişler."""
    return component_service.fleet_summary()


@router.get("/transformers/{transformer_id}/component-tests")
def list_component_tests(transformer_id: str) -> dict:
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return component_service.history(transformer_id)


@router.post("/transformers/{transformer_id}/component-tests")
def create_component_test(transformer_id: str, test: ComponentTestIn,
                          identity: Identity = Depends(require_identity)
                          ) -> dict:
    """Yeni bir buşing/kademe testi kaydeder ve hemen değerlendirir."""
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    values = test.model_dump(exclude_none=True)
    measured = [k for k in database.COMPONENT_TEST_FIELDS if k in values]
    if not measured:
        raise HTTPException(status_code=400,
                            detail="En az bir ölçüm değeri girilmelidir.")

    # Kapasitans girildiyse künye değeri de istenir.
    #
    # Ölçüt mutlak kapasitans DEĞİL, künyeden sapmadır: mutlak değer
    # buşing tasarımına göre değişir ve tek başına hiçbir şey söylemez.
    # Referans olmadan kaydedilen bir kapasitans, sonradan da
    # yorumlanamaz — o yüzden kayıt anında isteniyor.
    for ph in ("a", "b", "c"):
        if (f"bushing_{ph}_cap_pf" in values
                and f"bushing_{ph}_cap_rated_pf" not in values):
            raise HTTPException(
                status_code=400,
                detail=f"{ph.upper()} buşingi için künye kapasitansı da "
                       "girilmelidir. Ölçüt mutlak değer değil, künyeden "
                       "SAPMADIR; referans olmadan sapma hesaplanamaz.")

    test_id = database.save_component_test(
        transformer_id, values, tested_at=test.tested_at, notes=test.notes,
        recorded_by={"employee_no": identity.employee_no,
                     "name": identity.name})

    saved = next(t for t in database.get_component_tests(transformer_id)
                 if t["id"] == test_id)
    return {"ok": True, "id": test_id,
            "assessment": component_service.assess_test(transformer_id, saved)}
