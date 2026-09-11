"""Fiziksel gözlem testleri. — Faz 9.5"""
from __future__ import annotations

import pytest

from app import database
from app.core import physical


ALL_GOOD = {code: "iyi" for code in physical.ITEM_ORDER}


# --- Saf değerlendirme ---------------------------------------------------

def test_hepsi_iyiyse_hukum_iyi():
    r = physical.assess(ALL_GOOD)
    assert r["overall"] == "iyi"
    assert r["coverage_pct"] == 100
    assert r["problems"] == []


def test_kritik_madde_tek_basina_yeter():
    """Yağ kaçağı, diğer her şey iyi olsa bile hükmü kötüye çevirir."""
    r = physical.assess({**ALL_GOOD, "oil_leak": "kötü"})
    assert r["overall"] == "kötü"
    assert "Yağ kaçağı" in r["critical_findings"]


def test_kozmetik_bulgu_tek_basina_yetmez():
    """Boyanın dökülmesi ile koruma arızası aynı şey değildir."""
    r = physical.assess({**ALL_GOOD, "corrosion": "kötü"})
    assert r["overall"] == "kabul"
    assert r["critical_findings"] == []


def test_kozmetik_bulgular_birikince_anlam_kazanir():
    """Üç ihmal, ihmal edilmiş bir varlığın işaretidir."""
    r = physical.assess({**ALL_GOOD, "corrosion": "kötü",
                         "noise_vibration": "kötü", "tap_changer": "kötü"})
    assert r["overall"] == "kötü"


def test_dikkat_hukmu_kabule_dusurur():
    r = physical.assess({**ALL_GOOD, "silica_gel": "dikkat"})
    assert r["overall"] == "kabul"
    assert "Silikajel (nem alıcı)" in r["watch_items"]


def test_bakilmayan_madde_iyi_sayilmaz():
    """Boş bırakmak 'sorun yok' demek DEĞİLDİR."""
    r = physical.assess({"oil_leak": "iyi"})
    assert r["available"] is True
    assert r["checked_count"] == 1
    assert r["coverage_pct"] == 10     # 10 maddeden biri


def test_hic_bakilmadiysa_hukum_yok():
    r = physical.assess({})
    assert r["available"] is False


def test_gecersiz_deger_bakilmadi_sayilir():
    r = physical.assess({"oil_leak": "harika"})
    assert r["available"] is False


def test_kritik_maddeler_dogru_isaretlenmis():
    """Koruma ve soğutma kritik, boya değil."""
    assert physical.ITEMS["protection"]["critical"] is True
    assert physical.ITEMS["cooling"]["critical"] is True
    assert physical.ITEMS["oil_leak"]["critical"] is True
    assert physical.ITEMS["corrosion"]["critical"] is False
    assert physical.ITEMS["noise_vibration"]["critical"] is False


# --- Kayıt ve uç nokta ---------------------------------------------------

@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    database.upsert_transformer("TR-X", "Test", "X", asset_class="LPT",
                                mva=150.0)
    return database


def test_kayit_ve_gecmis(db):
    from app.services import physical as svc

    database.save_physical_inspection("TR-X", {**ALL_GOOD, "cooling": "kötü"})
    h = svc.history("TR-X")

    assert h["available"] is True
    assert h["latest"]["overall"] == "kötü"


def test_gozlem_saglik_endeksine_girer(db):
    from app.services import health as health_service

    before = health_service.transformer_health("TR-X")["health"]
    ph_before = next(d for d in before["dimensions"] if d["key"] == "physical")
    assert ph_before["available"] is False

    database.save_physical_inspection("TR-X", ALL_GOOD)
    after = health_service.transformer_health("TR-X")["health"]
    ph_after = next(d for d in after["dimensions"] if d["key"] == "physical")
    assert ph_after["available"] is True
    assert ph_after["score"] == 100.0


def test_bos_tur_reddedilir(db):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.test_electrical_api import _auth

    client = TestClient(app)
    r = client.post("/transformers/TR-X/inspections",
                    json={"observations": {}}, headers=_auth())
    assert r.status_code == 400


def test_gozlem_kimlik_ister(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-X/inspections",
                    json={"observations": {"oil_leak": "iyi"}})
    assert r.status_code == 401


def test_filo_ozeti_hic_gozlenmemisleri_sayar(db):
    from app.services import physical as svc

    database.upsert_transformer("TR-Y", "Gozlemsiz", "X")
    database.save_physical_inspection("TR-X", ALL_GOOD)

    s = svc.fleet_summary()
    assert s["inspected"] == 1
    assert "TR-Y" in s["never_inspected"]
