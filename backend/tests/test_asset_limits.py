"""Varlığa özel eşik — kayıtlı mühendislik istisnası. (Faz 12.4)

Bu özelliğin hatası da sessizdir: yanlış işleyen bir istisna hiçbir ekranda
hata vermez, sadece kötü bir sonucu "kabul" gösterir. Bu yüzden her kural
hem "izin verir" hem "engeller" yönüyle ayrı test edildi.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import database
from app.core import asset_limits as al
from app.core import oil_quality
from app.main import app
from tests.test_electrical_api import _auth
from tests.test_reviews import ENGINEER, ENGINEER_2, LAB

TODAY = date(2026, 9, 15)
VC = "72.5-170kV"          # nem standardı: iyi ≤15, kabul ≤20
REASON = "Serbest solunumlu eski konservatör tasarımı; nem tarihsel olarak yüksek."


def _prop(**kw):
    p = dict(parameter="water_ppm", good=20.0, acceptable=25.0,
             valid_from=TODAY, valid_until=TODAY + timedelta(days=180),
             reason=REASON)
    p.update(kw)
    return al.validate_proposal(p["parameter"], p["good"], p["acceptable"], VC,
                                p["valid_from"], p["valid_until"], p["reason"],
                                TODAY)


def _row(**kw):
    r = dict(id=1, transformer_id="TR-L", parameter="water_ppm",
             good_limit=20.0, acceptable_limit=25.0,
             standard_good_limit=15.0, standard_acceptable_limit=20.0,
             valid_from="2026-09-15", valid_until="2026-12-31",
             status=al.ACTIVE, proposed_by_id="10833", reason=REASON)
    r.update(kw)
    return r


# --- Öneri kuralları ------------------------------------------------------

def test_gecerli_oneri_kabul_edilir():
    assert _prop() is None


def test_elektriksel_esik_istisna_alamaz():
    """Arıza imzası gevşetilemez: kısa devre spir tasarıma bakmaz."""
    code, msg = _prop(parameter="ttr_deviation_pct")
    assert code == 400
    assert "arıza imzası" in msg


def test_sinir_sirasi_parametre_yonune_gore_denetlenir():
    # Nem: düşük iyidir → iyi < kabul olmalı.
    assert _prop(good=25.0, acceptable=20.0)[0] == 400
    # Delinme gerilimi: yüksek iyidir → iyi > kabul olmalı (standart 55/47).
    assert _prop(parameter="bdv_kv", good=42.0, acceptable=50.0)[0] == 400
    assert _prop(parameter="bdv_kv", good=50.0, acceptable=42.0) is None


def test_standartla_ayni_oneri_reddedilir():
    code, msg = _prop(good=15.0, acceptable=20.0)
    assert code == 400 and "standartla aynı" in msg


def test_yazim_hatasi_korumasi():
    """25 yerine 250: trafoyu fiilen izlemeden çıkarırdı."""
    code, msg = _prop(acceptable=250.0)
    assert code == 400
    assert "standart değişikliğidir" in msg
    # Sıkılaştırma yönündeki büyük sapma da reddedilir (kuyruğu şişirir).
    assert _prop(good=5.0, acceptable=8.0)[0] == 400


def test_sure_ve_tarih_kurallari():
    assert _prop(valid_until=TODAY + timedelta(days=366))[0] == 400
    assert _prop(valid_until=TODAY + timedelta(days=365)) is None
    assert _prop(valid_from=TODAY - timedelta(days=1))[0] == 400    # geçmişe uzanmaz
    assert _prop(valid_from=TODAY + timedelta(days=10),
                 valid_until=TODAY + timedelta(days=5))[0] == 400
    assert _prop(valid_until=None)[0] == 400
    assert _prop(valid_until="15.09.2026")[0] == 400                 # yanlış biçim


def test_gerekce_zorunlu():
    assert _prop(reason="eski tasarım")[0] == 400
    assert _prop(reason=None)[0] == 400


def test_degisim_yonu():
    assert al.change_direction("water_ppm", 20, 25, 15, 20) == "loosen"
    assert al.change_direction("water_ppm", 12, 18, 15, 20) == "tighten"
    assert al.change_direction("water_ppm", 18, 19, 15, 20) == "mixed"
    # Delinme geriliminde sınırı DÜŞÜRMEK gevşetmedir.
    assert al.change_direction("bdv_kv", 50, 42, 55, 47) == "loosen"


# --- Uygulama ---------------------------------------------------------------

def test_istisna_yalnizca_tarih_penceresinde_ve_yururlukteyken_uygulanir():
    row = _row()
    assert al.is_in_effect(row, "2026-10-01T08:00:00+00:00")
    assert al.is_in_effect(row, "2026-12-31")                  # sınır dahil
    assert not al.is_in_effect(row, "2026-09-14")
    assert not al.is_in_effect(row, "2027-01-01")
    assert not al.is_in_effect(_row(status=al.PENDING), "2026-10-01")
    assert not al.is_in_effect(row, "bozuk-tarih")             # şüphede standart


def test_degerlendirme_hem_uygulanan_hem_standart_hukmu_tasir():
    """Sessiz eşik değişikliği yasak: iki hüküm de görünür olmalı."""
    test = {"water_ppm": 22.0, "bdv_kv": 72.0}

    plain = oil_quality.assess(test)
    assert plain["overall"] == "kötü"
    assert plain["overall_standard"] == "kötü"
    assert plain["overrides_applied"] == []
    assert plain["warnings"] == []

    r = oil_quality.assess(test, overrides={"water_ppm": _row()})
    assert r["overall"] == "kabul"
    assert r["overall_standard"] == "kötü"
    assert r["overrides_applied"] == ["water_ppm"]
    assert len(r["warnings"]) == 1 and "'kötü' olurdu" in r["warnings"][0]

    water = next(p for p in r["parameters"] if p["parameter"] == "water_ppm")
    assert water["limit_source"] == "asset_override"
    assert water["condition"] == "kabul"
    assert water["standard_condition"] == "kötü"
    assert water["standard_acceptable_limit"] == 20.0
    assert water["override"]["reason"] == REASON


# --- Karar ve geri çekme ---------------------------------------------------

def test_dort_goz_oneren_karar_veremez():
    pending = _row(status=al.PENDING)
    code, _ = al.validate_decision(pending, "approve", None, "10833", TODAY)
    assert code == 403
    assert al.validate_decision(pending, "approve", None, "10921", TODAY) is None


def test_karar_kurallari():
    pending = _row(status=al.PENDING)
    assert al.validate_decision(pending, "reject", "kısa", "10921", TODAY)[0] == 400
    assert al.validate_decision(pending, "maybe", None, "10921", TODAY)[0] == 400
    assert al.validate_decision(_row(), "approve", None, "10921", TODAY)[0] == 409
    expired = _row(status=al.PENDING, valid_until="2026-09-01")
    assert al.validate_decision(expired, "approve", None, "10921", TODAY)[0] == 409


def test_geri_cekme_dort_goz_istemez_ama_gerekce_ister():
    """Standarda dönmek korumacıdır; öneren de geri çekebilir."""
    assert al.validate_revoke(_row(), "Konservatör yenilendi, standart geçerli.") is None
    assert al.validate_revoke(_row(), "yok")[0] == 400
    assert al.validate_revoke(_row(status=al.PENDING), "Gerekçe yeterince uzun.")[0] == 409


# --- Uç noktalar -----------------------------------------------------------

def _today_utc():
    return datetime.now(timezone.utc).date()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "limits.db")
    database.init_db()
    # hv_kv yok → 72.5-170 kV varsayımı: nem iyi ≤15, kabul ≤20.
    database.upsert_transformer("TR-L", "İstisna Trafosu", "X",
                                asset_class="LPT", mva=150.0)
    return TestClient(app)


def _propose(client, who, **kw):
    body = dict(parameter="water_ppm", good_limit=20.0, acceptable_limit=25.0,
                valid_until=(_today_utc() + timedelta(days=180)).isoformat(),
                reason=REASON)
    body.update(kw)
    return client.post("/transformers/TR-L/limits", json=body, headers=_auth(**who))


def _post_wet_oil(client, sampled_at=None):
    body = {"water_ppm": 22.0, "bdv_kv": 72.0}
    if sampled_at:
        body["sampled_at"] = sampled_at
    r = client.post("/transformers/TR-L/oil-tests", json=body, headers=_auth(**LAB))
    assert r.status_code == 200, r.text
    return r.json()


def _latest(client):
    return client.get("/transformers/TR-L/oil-tests").json()["latest_assessment"]


def test_istisna_icin_yetki_gerekir(client):
    r = client.post("/transformers/TR-L/limits", json={"parameter": "water_ppm"})
    assert r.status_code == 401
    assert _propose(client, LAB).status_code == 403


def test_uctan_uca_oneri_onay_ve_uygulama(client):
    assert _post_wet_oil(client)["assessment"]["overall"] == "kötü"

    r = _propose(client, ENGINEER)
    assert r.status_code == 200, r.text
    item = r.json()["item"]
    assert item["status"] == "pending"
    assert item["change_direction"] == "loosen"
    assert item["standard_acceptable_limit"] == 20.0
    # Onaylayan neyi değiştirdiğini görmeli.
    assert item["impact"]["changes_verdict"] is True
    assert item["impact"]["overall_standard"] == "kötü"
    assert item["impact"]["overall_override"] == "kabul"

    # Bekleyen istisna UYGULANMAZ.
    assert _latest(client)["overall"] == "kötü"

    oid = item["id"]
    r = client.post(f"/limits/{oid}/decision", json={"decision": "approve"},
                    headers=_auth(**ENGINEER))
    assert r.status_code == 403                                   # dört göz

    r = client.post(f"/limits/{oid}/decision", json={"decision": "approve"},
                    headers=_auth(**ENGINEER_2))
    assert r.status_code == 200, r.text
    assert r.json()["item"]["status"] == "active"
    assert r.json()["item"]["decided_by_name"] == ENGINEER_2["name"]

    latest = _latest(client)
    assert latest["overall"] == "kabul"
    assert latest["overall_standard"] == "kötü"
    assert latest["warnings"]

    # Sağlık endeksi de istisnalı hükmü görür (kötü 25 → kabul 65).
    from app.services import health as health_service
    dims = health_service.transformer_health("TR-L")["health"]["dimensions"]
    assert next(d for d in dims if d["key"] == "oil")["score"] == 65.0

    listing = client.get("/transformers/TR-L/limits").json()
    assert [i["id"] for i in listing["active"]] == [oid]


def test_ayni_parametreye_ikinci_acik_istisna_409(client):
    assert _propose(client, ENGINEER).status_code == 200
    assert _propose(client, ENGINEER_2).status_code == 409
    # Farklı parametre engellenmez (delinme gerilimi standardı 55/47).
    r = _propose(client, ENGINEER, parameter="bdv_kv",
                 good_limit=50.0, acceptable_limit=42.0)
    assert r.status_code == 200, r.text


def test_reddedilen_istisna_uygulanmaz_ve_yeni_oneriye_yer_acar(client):
    _post_wet_oil(client)
    oid = _propose(client, ENGINEER).json()["item"]["id"]

    r = client.post(f"/limits/{oid}/decision", json={"decision": "reject"},
                    headers=_auth(**ENGINEER_2))
    assert r.status_code == 400                                   # gerekçesiz

    r = client.post(f"/limits/{oid}/decision",
                    json={"decision": "reject",
                          "note": "Nem yüksekliği tasarımdan değil, conta kaçağından."},
                    headers=_auth(**ENGINEER_2))
    assert r.status_code == 200
    assert r.json()["item"]["status"] == "rejected"
    assert _latest(client)["overall"] == "kötü"
    assert _propose(client, ENGINEER).status_code == 200


def test_geri_cekince_standart_esik_doner(client):
    _post_wet_oil(client)
    oid = _propose(client, ENGINEER).json()["item"]["id"]
    client.post(f"/limits/{oid}/decision", json={"decision": "approve"},
                headers=_auth(**ENGINEER_2))
    assert _latest(client)["overall"] == "kabul"

    # Öneren kendisi geri çekebilir: standarda dönmek korumacıdır.
    r = client.post(f"/limits/{oid}/revoke",
                    json={"note": "Konservatör yenilendi; standart geçerli."},
                    headers=_auth(**ENGINEER))
    assert r.status_code == 200, r.text
    assert r.json()["item"]["status"] == "revoked"
    assert _latest(client)["overall"] == "kötü"

    r = client.post(f"/limits/{oid}/revoke",
                    json={"note": "İkinci kez geri çekme denemesi."},
                    headers=_auth(**ENGINEER))
    assert r.status_code == 409


def test_istisna_gecmis_teste_uygulanmaz(client):
    """Bugün onaylanan istisna, geçen yılki testin hükmünü değiştirmez."""
    _post_wet_oil(client, sampled_at="2025-01-10T10:00:00")
    oid = _propose(client, ENGINEER).json()["item"]["id"]
    client.post(f"/limits/{oid}/decision", json={"decision": "approve"},
                headers=_auth(**ENGINEER_2))

    from app.services import oil as oil_service
    old = database.get_oil_tests("TR-L")[0]
    assert oil_service.assess_test("TR-L", old)["overall"] == "kötü"


def test_suresi_dolan_istisna_kapanir_ve_yer_acar(client):
    oid = database.create_limit_override("TR-L", {
        "parameter": "water_ppm", "voltage_class": VC,
        "good_limit": 20.0, "acceptable_limit": 25.0,
        "standard_good_limit": 15.0, "standard_acceptable_limit": 20.0,
        "valid_from": "2025-01-01", "valid_until": "2025-06-30",
        "reason": REASON}, {"employee_no": "10833", "name": "Deniz Koç"})
    assert database.decide_limit_override(
        oid, "active", None, {"employee_no": "10921", "name": "Can Yıldız"})

    active = client.get("/limits/queue", params={"folder": "active"}).json()
    assert active["items"] == []
    assert database.get_limit_override(oid)["status"] == "expired"
    assert _propose(client, ENGINEER).status_code == 200


def test_gecersiz_klasor_400(client):
    assert client.get("/limits/queue", params={"folder": "yok"}).status_code == 400
