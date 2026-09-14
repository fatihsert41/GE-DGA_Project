"""Departman bazlı yetki kontrolü — Python uç noktaları. (Faz 10)

Yetki haritası .NET'te tanımlı ve belirtece yazılıyor; Python yalnızca
belirteçteki listeye bakıyor. Bu testler .NET'i ayağa kaldırmadan, .NET'in
üreteceğine denk belirteçlerle Python tarafının DOĞRU KAPIYI kapattığını
sınar.

Yetki hataları sessizdir: yanlış açık kalmış bir kapı hiçbir ekranda
hata vermez. Bu yüzden her test türü için hem "girebilir" hem
"giremez" yönü ayrı ayrı yazıldı.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, database
from app.main import app
from tests.test_electrical_api import _auth, _token

# .NET'teki Permissions.For(...) ile aynı listeler — test verisi olarak.
OIL_LAB = dict(department="OilLaboratory", department_name="Yağ Laboratuvarı",
               permissions=["analysis.run", "tests.dga", "tests.oil"])
ELECTRICAL = dict(department="ElectricalTesting",
                  department_name="Elektriksel Test",
                  permissions=["tests.electrical", "tests.components"])
PLANNING = dict(department="MaintenancePlanning",
                department_name="Bakım Planlama",
                permissions=["workorders.plan", "workorders.execute",
                             "notifications.send", "personnel.view"])
FIELD = dict(department="FieldService", department_name="Saha Bakım",
             permissions=["workorders.execute", "tests.inspection"])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "perm.db")
    database.init_db()
    database.upsert_transformer("TR-P", "Yetki Trafosu", "X",
                                asset_class="MPT", mva=50.0)
    return TestClient(app)


def _post_oil(client, **who):
    return client.post("/transformers/TR-P/oil-tests",
                       json={"water_ppm": 12.0}, headers=_auth(**who))


def _post_electrical(client, **who):
    return client.post("/transformers/TR-P/electrical-tests",
                       json={"ir_1min_mohm": 1000.0, "ir_10min_mohm": 2500.0},
                       headers=_auth(**who))


def _post_inspection(client, **who):
    return client.post("/transformers/TR-P/inspections",
                       json={"observations": {"oil_leak": "iyi"}},
                       headers=_auth(**who))


# --- Belirteç ---------------------------------------------------------------

def test_belirtecten_departman_ve_yetkiler_okunur():
    identity = auth.verify_token(_token(**OIL_LAB))
    assert identity is not None
    assert identity.department == "OilLaboratory"
    assert identity.department_name == "Yağ Laboratuvarı"
    assert identity.has("tests.oil")
    assert not identity.has("tests.electrical")


def test_yetki_listesi_olmayan_eski_belirtec_hicbir_sey_yazamaz(client):
    """Güncelleme öncesi açılmış oturum: varsayılan TAM yetki DEĞİL, sıfır."""
    r = _post_oil(client, permissions=[])
    assert r.status_code == 403
    assert "yeniden giriş" in r.json()["detail"]["message"]


def test_yetki_listesi_imzasiz_degistirilemez(client):
    """Yükteki yetki listesini elle genişletmek imzayı bozar → 401."""
    import base64
    import json

    token = _token(**ELECTRICAL)
    body, sig = token.split(".")
    payload = json.loads(auth._b64url_decode(body))
    payload["permissions"].append("tests.oil")
    forged = base64.urlsafe_b64encode(
        json.dumps(payload).encode()).decode().rstrip("=")

    r = client.post("/transformers/TR-P/oil-tests", json={"water_ppm": 12.0},
                    headers={"Authorization": f"Bearer {forged}.{sig}"})
    assert r.status_code == 401


# --- Test türleri: her birinin sahibi ayrı ----------------------------------

def test_yag_laboratuvari_yag_testi_girebilir(client):
    assert _post_oil(client, **OIL_LAB).status_code == 200


def test_yag_laboratuvari_elektriksel_test_giremez(client):
    r = _post_electrical(client, **OIL_LAB)
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["required_permission"] == "tests.electrical"
    assert "Yağ Laboratuvarı" in detail["message"]


def test_elektriksel_test_ekibi_elektriksel_test_girebilir(client):
    assert _post_electrical(client, **ELECTRICAL).status_code == 200


def test_elektriksel_test_ekibi_yag_testi_giremez(client):
    assert _post_oil(client, **ELECTRICAL).status_code == 403


def test_saha_bakim_gozlem_girebilir_ama_test_giremez(client):
    assert _post_inspection(client, **FIELD).status_code == 200
    assert _post_oil(client, **FIELD).status_code == 403
    assert _post_electrical(client, **FIELD).status_code == 403


def test_bakim_planlama_hicbir_test_giremez(client):
    assert _post_oil(client, **PLANNING).status_code == 403
    assert _post_electrical(client, **PLANNING).status_code == 403
    assert _post_inspection(client, **PLANNING).status_code == 403


def test_yonetim_her_testi_girebilir(client):
    assert _post_oil(client).status_code == 200
    assert _post_electrical(client).status_code == 200
    assert _post_inspection(client).status_code == 200


def test_401_ile_403_ayri(client):
    """Kimlik yoksa 401 (giriş ekranı), kimlik var yetki yoksa 403."""
    no_login = client.post("/transformers/TR-P/oil-tests",
                           json={"water_ppm": 12.0})
    assert no_login.status_code == 401
    assert _post_oil(client, **ELECTRICAL).status_code == 403


# --- Varlık kaydı ------------------------------------------------------------

def test_kunye_duzenleme_yetki_ister(client):
    body = {"manufacturer": "GE Vernova"}
    assert client.put("/transformers/TR-P/nameplate", json=body).status_code == 401
    assert client.put("/transformers/TR-P/nameplate", json=body,
                      headers=_auth(**OIL_LAB)).status_code == 403
    assert client.put("/transformers/TR-P/nameplate", json=body,
                      headers=_auth()).status_code == 200


def test_yeni_trafo_kaydi_yetki_ister(client):
    body = {"id": "TR-NEW", "name": "Yeni", "location": "X"}
    assert client.post("/transformers", json=body).status_code == 401
    assert client.post("/transformers", json=body,
                       headers=_auth(**PLANNING)).status_code == 403
    assert database.get_transformer("TR-NEW") is None      # yazılmadı


# --- Numune analizi ----------------------------------------------------------

GASES = {"H2": 60, "CH4": 40, "C2H6": 10, "C2H4": 30, "C2H2": 5,
         "CO": 300, "CO2": 2500}


def test_kaydetmeden_tani_herkese_acik(client):
    r = client.post("/predict", json={"gases": GASES, "persist": False})
    assert r.status_code == 200


def test_olcumu_kaydetmek_dga_yetkisi_ister(client):
    body = {"gases": GASES, "transformer_id": "TR-P", "persist": True}

    assert client.post("/predict", json=body).status_code == 401
    assert client.post("/predict", json=body,
                       headers=_auth(**ELECTRICAL)).status_code == 403
    assert database.get_measurements("TR-P") == []          # hiçbiri yazılmadı

    assert client.post("/predict", json=body,
                       headers=_auth(**OIL_LAB)).status_code == 200
    assert len(database.get_measurements("TR-P")) == 1
