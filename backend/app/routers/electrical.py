"""Elektriksel test uç noktaları. — Faz 8.6

Yağ testlerinden AYRI: bu testler trafo enerjisizken yapılır, çok daha
seyrektir ve yorumları künyeye (gerilim, bağlantı grubu, kademe, sargı
malzemesi) doğrudan bağımlıdır.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import Identity, require_identity

from .. import database
from ..core import electrical as core_electrical
from ..core import nameplate
from ..schemas import ElectricalTestIn, VoidTestIn
from ..services import electrical as electrical_service

router = APIRouter(tags=["electrical tests"])


@router.get("/electrical/schema")
def electrical_schema() -> dict:
    """Testler, birimleri, eşikleri ve anlamları — giriş formunu besler."""
    return {
        "tests": {
            "turns_ratio": {
                "label": "Sarım oranı (TTR)",
                "standard": "IEEE C57.12.00 / IEC 60076-1",
                "tolerance_pct": core_electrical.TTR_GOOD_PCT,
                "acceptable_pct": core_electrical.TTR_ACCEPT_PCT,
                "meaning": "Kısa devre olmuş spiri yakalar. Yağa iz "
                           "bırakması için önce ısınıp gaz üretmesi "
                           "gerekir; TTR aynı gün görür.",
                "fields": ["ttr_a", "ttr_b", "ttr_c", "tap_position"],
            },
            "winding_resistance": {
                "label": "Sargı direnci",
                "standard": "IEEE C57.152",
                "limit_pct": core_electrical.RESISTANCE_GOOD_PCT,
                "acceptable_pct": core_electrical.RESISTANCE_ACCEPT_PCT,
                "meaning": "Fazlar arası DENGESİZLİK bakılır; gevşek "
                           "bağlantı ve kademe kontak aşınmasını gösterir.",
                "reference_temp_c": core_electrical.REFERENCE_TEMP_C,
                "fields": ["rw_a_ohm", "rw_b_ohm", "rw_c_ohm",
                           "winding_temp_c"],
            },
            "insulation": {
                "label": "Yalıtım direnci / PI",
                "standard": "IEEE C57.152",
                "formula": "PI = R(10 dk) / R(1 dk)",
                "bands": [{"min_pi": lo, "condition": cond, "description": d}
                          for lo, cond, d in core_electrical.PI_BANDS],
                "meaningless_above_mohm":
                    core_electrical.PI_MEANINGLESS_ABOVE_MOHM,
                "meaning": "Kuru yalıtımda direnç zamanla yükselir; nemli "
                           "veya kirli yalıtımda sabit kalır.",
                "fields": ["ir_1min_mohm", "ir_10min_mohm",
                           "insulation_temp_c"],
            },
            "tan_delta": {
                "label": "Kayıp faktörü (tan δ)",
                "standard": "IEEE C57.152",
                "good_limit": core_electrical.TAND_GOOD_PCT,
                "acceptable_limit": core_electrical.TAND_ACCEPT_PCT,
                "meaning": "Yalıtımın genel yaşlanma/nem durumu; noktasal "
                           "arıza değil, bütünün durumu.",
                "caveat": "Sıcaklık düzeltmesi UYGULANMAZ (yalıtım tipine "
                          "bağlı ampirik tablo gerektirir); 20 °C dışındaki "
                          "ölçümlerde uyarı verilir.",
                "fields": ["tan_delta_pct", "tan_delta_temp_c"],
            },
        },
        "phases": list(core_electrical.PHASES),
        "temp_constants": core_electrical.TEMP_CONSTANT,
        "fields": database.ELECTRICAL_TEST_FIELDS,
    }


@router.get("/electrical/fleet")
def electrical_fleet() -> dict:
    """Filo geneli elektriksel test durumu + hiç test edilmemişler."""
    return electrical_service.fleet_summary()


@router.get("/transformers/{transformer_id}/expected-ratio")
def expected_ratio(transformer_id: str, tap: int | None = None) -> dict:
    """Beklenen sarım oranı — veri giriş formu ölçümü buna göre gösterir.

    Form, kullanıcı kademeyi seçer seçmez beklenen değeri yazabilsin diye
    ayrı bir uç nokta: teknisyen ölçtüğü sayıyı girerken hedefi görmeli,
    sonucu kaydettikten sonra değil.
    """
    record = database.get_transformer(transformer_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    np = record.get("nameplate") or {}
    rated = nameplate.rated_turns_ratio(np)
    if rated is None:
        return {
            "available": False,
            "reason": "Künyede YG/AG gerilimi eksik; beklenen oran "
                      "hesaplanamıyor. Önce künyeyi tamamlayın.",
        }

    return {
        "available": True,
        "rated_turns_ratio": rated,
        "expected_at_tap": electrical_service.expected_ratio(
            transformer_id, tap),
        "tap": tap,
        "vector_group": np.get("vector_group"),
        "tap_min": np.get("tap_min"),
        "tap_max": np.get("tap_max"),
        "tap_step_percent": np.get("tap_step_percent"),
        "tolerance_pct": core_electrical.TTR_GOOD_PCT,
    }


@router.get("/transformers/{transformer_id}/electrical-tests")
def list_electrical_tests(transformer_id: str) -> dict:
    """Trafonun elektriksel test geçmişi + en sonun değerlendirmesi."""
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")
    return electrical_service.history(transformer_id)


@router.post("/transformers/{transformer_id}/electrical-tests")
def create_electrical_test(
        transformer_id: str,
        test: ElectricalTestIn,
        identity: Identity = Depends(require_identity)) -> dict:
    """Yeni bir elektriksel test kaydeder ve hemen değerlendirir.

    Kimlik ZORUNLU: sorumlusu bilinmeyen bir ölçüm kaydı, denetim izi
    tutmanın amacını boşa çıkarır.
    """
    if database.get_transformer(transformer_id) is None:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    values = test.model_dump(exclude_none=True)

    # tap_position tek başına ölçüm SAYILMAZ: o bağlam bilgisi, sonuç
    # değil. Sadece kademe girilip kaydedilen boş bir test kaydı,
    # geçmişi kirletirdi.
    measured = [k for k in database.ELECTRICAL_TEST_FIELDS
                if k in values and k != "tap_position"]
    if not measured:
        raise HTTPException(
            status_code=400,
            detail="En az bir ölçüm değeri girilmelidir (kademe pozisyonu "
                   "tek başına yeterli değildir).")

    # TTR girildiyse kademe de istenir: kademeyi bilmeden beklenen oran
    # yanlış olur ve sağlam trafo "arızalı" görünür. Bu, kurala dönüşen
    # somut bir saha hatasıdır.
    ttr_given = any(k in values for k in ("ttr_a", "ttr_b", "ttr_c"))
    np = (database.get_transformer(transformer_id) or {}).get("nameplate") or {}
    has_tap_changer = bool(np.get("tap_changer_type"))
    if ttr_given and has_tap_changer and "tap_position" not in values:
        raise HTTPException(
            status_code=400,
            detail="Bu trafoda kademe değiştirici var. Sarım oranı ölçümü "
                   "girerken kademe pozisyonu da verilmelidir; aksi halde "
                   "beklenen oran yanlış hesaplanır.")

    test_id = database.save_electrical_test(
        transformer_id, values, tested_at=test.tested_at,
        tested_by=test.tested_by, notes=test.notes,
        recorded_by={"employee_no": identity.employee_no,
                     "name": identity.name})

    saved = next(t for t in database.get_electrical_tests(transformer_id)
                 if t["id"] == test_id)
    return {"ok": True, "id": test_id,
            "assessment": electrical_service.assess_test(transformer_id,
                                                         saved)}


@router.get("/transformers/{transformer_id}/electrical-tests/{test_id}")
def get_electrical_test(transformer_id: str, test_id: int) -> dict:
    """Tek bir testin değerlendirmesi — geçmişten seçilen kayıt için.

    Panel başlangıçta yalnızca son testi gösteriyordu; kullanıcı kendi
    girdiği bir testin sonucuna bir daha ulaşamıyordu. Sahada geçmiş
    testler tam olarak karşılaştırma yapmak için tutulur.
    """
    tests = database.get_electrical_tests(transformer_id)
    if not tests:
        raise HTTPException(status_code=404,
                            detail=f"Trafo bulunamadı: {transformer_id}")

    test = next((t for t in tests if int(t["id"]) == int(test_id)), None)
    if test is None:
        raise HTTPException(status_code=404,
                            detail=f"Test bulunamadı: {test_id}")

    return {"test": test,
            "assessment": electrical_service.assess_test(transformer_id, test)}


@router.post("/transformers/{transformer_id}/electrical-tests/{test_id}/void")
def void_electrical_test(
        transformer_id: str, test_id: int, body: VoidTestIn,
        identity: Identity = Depends(require_identity)) -> dict:
    """Hatalı bir test kaydını GEÇERSİZ işaretler — silmez.

    Silme uç noktası bilinçli olarak YOKTUR. Ölçüm kayıtları bir varlığın
    denetlenebilir geçmişidir: sahada hatalı çıkan bir test raporu imha
    edilmez, üzerine "geçersiz" damgası vurulur ve dosyada kalır.
    "Ölçüm yapılmadı" ile "yapıldı ama hatalıydı" farklı bilgilerdir.

    Geçersiz kayıt geçmişte görünmeye devam eder ama son test seçilirken
    atlanır ve hüküm/sağlık endeksi hesabına girmez.
    """
    ok = database.void_test("electrical_tests", transformer_id, test_id,
                            body.reason,
                            voided_by={"employee_no": identity.employee_no,
                                       "name": identity.name})
    if not ok:
        raise HTTPException(status_code=404,
                            detail=f"Test bulunamadı: {test_id}")
    return {"ok": True, "voided": True,
            "history": electrical_service.history(transformer_id)}


@router.delete("/transformers/{transformer_id}/electrical-tests/{test_id}/void")
def unvoid_electrical_test(
        transformer_id: str, test_id: int,
        identity: Identity = Depends(require_identity)) -> dict:
    """Geçersiz işaretini kaldırır (yanlışlıkla işaretlenmişse)."""
    ok = database.void_test("electrical_tests", transformer_id, test_id, "")
    if not ok:
        raise HTTPException(status_code=404,
                            detail=f"Test bulunamadı: {test_id}")
    return {"ok": True, "voided": False,
            "history": electrical_service.history(transformer_id)}
