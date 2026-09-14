"""Mühendislik test onay akışı. (Faz 12.2)

Onay kurallarının hatası sessizdir: yanlış işleyen bir dört göz kontrolü
hiçbir ekranda hata vermez, sadece bir kişinin kendi ölçümünü onaylamasına
izin verir. Bu yüzden her kural hem "izin verir" hem "engeller" yönüyle
ayrı test edildi.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import database
from app.core import review as core_review
from app.main import app
from tests.test_electrical_api import _auth

LAB = dict(employee_no="10455", name="Mehmet Kaya", role="Technician",
           department="OilLaboratory", department_name="Yağ Laboratuvarı",
           permissions=["analysis.run", "tests.dga", "tests.oil",
                        "notifications.send"])
ENGINEER = dict(employee_no="10833", name="Deniz Koç", role="Engineer",
                department="Engineering", department_name="Mühendislik",
                permissions=["engineering.approve", "engineering.review_model",
                             "engineering.limits", "engineering.rca",
                             "analysis.run", "manager.view",
                             "notifications.send"])
ENGINEER_2 = dict(ENGINEER, employee_no="10921", name="Can Yıldız")
MANAGER = dict(employee_no="10502", name="Zeynep Şahin")    # tam yetki

# Gerilim sınıfı bilinmiyor → 72.5-170 kV varsayımı. Nem 60 ppm > 20 → kötü.
BAD_OIL = {"water_ppm": 60.0, "bdv_kv": 25.0}
GOOD_OIL = {"water_ppm": 8.0, "bdv_kv": 72.0, "acidity_mgkoh_g": 0.03,
            "ift_mn_m": 38.0}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "review.db")
    database.init_db()
    database.upsert_transformer("TR-R", "Onay Trafosu", "X",
                                asset_class="LPT", mva=150.0)
    return TestClient(app)


def _post_oil(client, values, who, sampled_at=None):
    body = dict(values)
    if sampled_at:
        body["sampled_at"] = sampled_at
    r = client.post("/transformers/TR-R/oil-tests", json=body, headers=_auth(**who))
    assert r.status_code == 200, r.text
    return r.json()


def _decide(client, test_id, decision, who, note=None):
    return client.post(f"/reviews/oil/{test_id}/decision",
                       json={"decision": decision, "note": note},
                       headers=_auth(**who))


def _oil_dimension():
    from app.services import health as health_service
    h = health_service.transformer_health("TR-R")["health"]
    return h, next(d for d in h["dimensions"] if d["key"] == "oil")


# --- Saf kurallar ------------------------------------------------------------

def test_yalnizca_kotu_sonuc_onaya_duser():
    assert core_review.initial_status("kötü") == core_review.PENDING
    assert core_review.initial_status("kabul") == core_review.NOT_REQUIRED
    assert core_review.initial_status("iyi") == core_review.NOT_REQUIRED
    assert core_review.initial_status(None) == core_review.NOT_REQUIRED


def test_yag_testi_iki_boyutu_birden_dogrulanmamis_yapar():
    dims = core_review.unverified_dimensions(
        {"oil": "pending", "electrical": "approved", "components": "retest"})
    assert set(dims) == {"oil", "paper", "components"}


def test_reddedilen_ve_gecersiz_kayit_kullanilmaz():
    assert core_review.is_usable({"review_status": "approved"})
    assert core_review.is_usable({"review_status": None})
    assert not core_review.is_usable({"review_status": "rejected"})
    assert not core_review.is_usable({"voided_at": "2026-01-01"})


# --- Kuyruğa düşme ----------------------------------------------------------

def test_sinir_disi_test_onaya_duser(client):
    res = _post_oil(client, BAD_OIL, LAB)
    assert res["review_status"] == "pending"

    q = client.get("/reviews/queue").json()
    assert len(q["items"]) == 1
    item = q["items"][0]
    assert item["transformer_id"] == "TR-R"
    assert item["transformer_name"] == "Onay Trafosu"
    assert item["recorded_by_id"] == "10455"
    assert item["overall"] == "kötü"
    assert q["counts"]["pending"] == 1


def test_normal_sonuc_onaya_girmez(client):
    res = _post_oil(client, GOOD_OIL, LAB)
    assert res["review_status"] == "not_required"
    assert client.get("/reviews/queue").json()["items"] == []
    # Onay beklemeyen teste karar verilemez.
    assert _decide(client, res["id"], "approve", ENGINEER).status_code == 409


# --- Dört göz ve yetki -------------------------------------------------------

def test_dort_goz_kendi_testine_karar_verilemez(client):
    # Yönetim hem test girebilir hem onaylayabilir — kural bu yüzden
    # yetkiye değil KİŞİYE bakıyor.
    res = _post_oil(client, BAD_OIL, MANAGER)
    r = _decide(client, res["id"], "approve", MANAGER)
    assert r.status_code == 403
    assert "Dört göz" in r.json()["detail"]

    assert _decide(client, res["id"], "approve", ENGINEER).status_code == 200


def test_laboratuvar_onay_veremez(client):
    res = _post_oil(client, BAD_OIL, MANAGER)
    r = _decide(client, res["id"], "approve", LAB)
    assert r.status_code == 403
    assert r.json()["detail"]["required_permission"] == "engineering.approve"


def test_red_ve_tekrar_icin_gerekce_zorunlu(client):
    res = _post_oil(client, BAD_OIL, LAB)
    assert _decide(client, res["id"], "reject", ENGINEER).status_code == 400
    assert _decide(client, res["id"], "retest", ENGINEER, note="kısa").status_code == 400
    # Onay gerekçe istemez.
    assert _decide(client, res["id"], "approve", ENGINEER).status_code == 200


def test_karar_bir_kez_verilir(client):
    res = _post_oil(client, BAD_OIL, LAB)
    assert _decide(client, res["id"], "approve", ENGINEER).status_code == 200
    r = _decide(client, res["id"], "reject", ENGINEER_2,
                note="Numune kabı nemliydi, tekrar alınmalı")
    assert r.status_code == 409


def test_gecersiz_karar_reddedilir(client):
    res = _post_oil(client, BAD_OIL, LAB)
    assert _decide(client, res["id"], "onayla", ENGINEER).status_code == 400


# --- Kararın hesaba etkisi ---------------------------------------------------

def test_onay_bekleyen_sonuc_hesaba_isaretli_girer(client):
    """Onay beklerken kritik bulguyu yok saymak tehlikeli: hesapta, ama işaretli."""
    _post_oil(client, BAD_OIL, LAB)
    health, oil = _oil_dimension()
    assert oil["available"] is True
    assert oil["unverified"] is True
    assert "Yağ kalitesi" in health["unverified_dimensions"]
    assert any("Doğrulanmamış" in w for w in health["warnings"])


def test_reddedilen_test_hesaptan_cikar_ama_silinmez(client):
    _post_oil(client, GOOD_OIL, LAB, sampled_at="2026-01-10")
    bad = _post_oil(client, BAD_OIL, LAB, sampled_at="2026-06-10")

    r = _decide(client, bad["id"], "reject", ENGINEER,
                note="Numune kabı nemliydi; ölçüm geçersiz")
    assert r.status_code == 200
    assert r.json()["item"]["review_status"] == "rejected"

    # Son geçerli test yeniden İYİ olan eski test.
    latest = database.latest_oil_tests()["TR-R"]
    assert latest["water_ppm"] == 8.0
    _, oil = _oil_dimension()
    assert oil["score"] == 100.0
    assert not oil.get("unverified")

    # Kayıt silinmedi, gerekçesiyle duruyor.
    rows = database.get_oil_tests("TR-R")
    assert len(rows) == 2
    rejected = next(t for t in rows if t["id"] == bad["id"])
    assert rejected["review_note"].startswith("Numune kabı")
    assert rejected["reviewed_by_name"] == "Deniz Koç"


def test_tekrar_olcum_istenen_sonuc_dogrulanmamis_kalir(client):
    res = _post_oil(client, BAD_OIL, LAB)
    r = _decide(client, res["id"], "retest", ENGINEER,
                note="BDV beklenmedik düşük, numune tekrar alınsın")
    assert r.status_code == 200
    _, oil = _oil_dimension()
    assert oil["unverified"] is True

    q = client.get("/reviews/queue?folder=retest").json()
    assert [i["test_id"] for i in q["items"]] == [res["id"]]


def test_onaylanan_sonuc_dogrulanmis_olur(client):
    res = _post_oil(client, BAD_OIL, LAB)
    _decide(client, res["id"], "approve", ENGINEER)
    _, oil = _oil_dimension()
    assert oil["available"] is True
    assert not oil.get("unverified")


# --- Eski kayıtlar -----------------------------------------------------------

def test_eski_kayitlar_bir_kez_siniflandirilir(client):
    from app.services import review as review_service

    # Onay sütunu yokken kaydedilmiş gibi: doğrudan veritabanına.
    bad_id = database.save_oil_test("TR-R", BAD_OIL)
    good_id = database.save_oil_test("TR-R", GOOD_OIL)

    assert review_service.backfill() == 2
    assert database.get_test_row("oil_tests", bad_id)["review_status"] == "pending"
    assert database.get_test_row("oil_tests", good_id)["review_status"] == "not_required"
    # Yinelenebilir: ikinci çalıştırma hiçbir şeye dokunmaz.
    assert review_service.backfill() == 0


def test_gecersiz_klasor_400(client):
    assert client.get("/reviews/queue?folder=hepsi").status_code == 400
