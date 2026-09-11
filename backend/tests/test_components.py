"""Buşing ve kademe değiştirici testleri. — Faz 9.4"""
from __future__ import annotations

import pytest

from app import database
from app.core import components as comp


GOOD_BUSHINGS = {
    "bushing_a_pf_pct": 0.31, "bushing_a_cap_pf": 411.0,
    "bushing_a_cap_rated_pf": 410.0,
    "bushing_b_pf_pct": 0.33, "bushing_b_cap_pf": 409.0,
    "bushing_b_cap_rated_pf": 410.0,
    "bushing_c_pf_pct": 0.30, "bushing_c_cap_pf": 412.0,
    "bushing_c_cap_rated_pf": 410.0,
}


# --- Buşing: ölçüt DEĞİŞİM, mutlak değer değil --------------------------

def test_saglam_busingler_gecer():
    r = comp.assess_bushings(GOOD_BUSHINGS)
    assert r["overall"] == "iyi"
    assert r["problems"] == []


def test_kapasitans_sapmasi_katman_kaybi_olarak_raporlanir():
    """%6.8 sapma: kondansatör katmanlarının bir kısmı delinmiş."""
    r = comp.assess_bushings({**GOOD_BUSHINGS, "bushing_b_cap_pf": 438.0})
    assert r["overall"] == "kötü"
    b = next(p for p in r["phases"] if p["phase"] == "B")
    assert b["deviation_pct"] == pytest.approx(6.83, abs=0.1)
    assert any("katman" in p for p in r["problems"])


def test_kunye_degeri_yoksa_sapma_hesaplanamaz():
    """Mutlak kapasitans tek başına bir şey söylemez.

    Referans olmadan ölçüm değerlendirilemez ve sonuç "hüküm yok"tur —
    "iyi" değil. Bu ayrım önemli: değerlendirilemeyen bir ölçümü iyi
    saymak, olmayan bir güvence üretir.
    """
    r = comp.assess_bushings({"bushing_a_cap_pf": 410.0})
    assert r["available"] is False

    # Künye değeri eklenince aynı ölçüm değerlendirilebilir hâle gelir:
    r2 = comp.assess_bushings({"bushing_a_cap_pf": 410.0,
                               "bushing_a_cap_rated_pf": 410.0})
    a = next(p for p in r2["phases"] if p["phase"] == "A")
    assert a["deviation_pct"] == 0.0
    assert a["cap_condition"] == "iyi"


def test_guc_faktoru_ayrica_degerlendirilir():
    r = comp.assess_bushings({**GOOD_BUSHINGS, "bushing_c_pf_pct": 1.6})
    assert r["overall"] == "kötü"
    assert any("güç faktörü" in p for p in r["problems"])


def test_imkansiz_sapma_veri_hatasi_sayilir():
    """TTR'deki %10 kuralıyla aynı mantık."""
    r = comp.assess_bushings({**GOOD_BUSHINGS, "bushing_a_cap_pf": 800.0})
    assert r["data_suspect"] is True
    assert any("açıklanamaz" in p for p in r["problems"])


def test_olcum_yoksa_hukum_yok():
    assert comp.assess_bushings({})["available"] is False


# --- OLTC: ölçüt KULLANIM, durum değil ----------------------------------

def test_isletme_sayisi_sinirinda_revizyon_istenir():
    r = comp.assess_oltc({"oltc_ops_since_overhaul": 52_000})
    assert r["overall"] == "kötü"
    assert any("işletme" in p for p in r["problems"])


def test_az_calismis_oltc_gecer():
    r = comp.assess_oltc({"oltc_ops_since_overhaul": 12_000,
                          "oltc_years_since_overhaul": 2.0})
    assert r["overall"] == "iyi"


def test_az_calissa_bile_sure_dolarsa_uyarir():
    """Sayaç dolmasa da yağ yaşlanır, contalar sertleşir."""
    r = comp.assess_oltc({"oltc_ops_since_overhaul": 3_000,
                          "oltc_years_since_overhaul": 8.0})
    assert r["overall"] == "kötü"
    assert any("süre" in p for p in r["problems"])


def test_kademe_yagi_ana_tanktan_ayri_degerlendirilir():
    """OLTC yağı ark yüzünden çok daha hızlı bozulur; eşiği ayrı."""
    r = comp.assess_oltc({"oltc_oil_bdv_kv": 18.0})
    assert r["overall"] == "kötü"
    # Ana tank için 18 kV zaten kötüdür ama OLTC eşiği daha gevşektir:
    assert comp.OLTC_BDV_ACCEPT < 40.0


def test_kademesiz_trafoda_oltc_degerlendirilmez():
    r = comp.assess_oltc({"oltc_ops_since_overhaul": 90_000},
                         has_tap_changer=False)
    assert r["available"] is False


# --- Bütün ---------------------------------------------------------------

def test_genel_hukum_en_kotu_bolume_gore():
    r = comp.assess({**GOOD_BUSHINGS, "oltc_ops_since_overhaul": 52_000})
    assert r["overall"] == "kötü"
    assert r["measured_count"] == 2


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    database.upsert_transformer("TR-X", "Test", "X", asset_class="LPT",
                                mva=150.0, tap_changer_type="OLTC")
    return database


def test_kayit_ve_saglik_endeksine_giris(db):
    from app.services import health as health_service

    before = health_service.transformer_health("TR-X")["health"]
    d_before = next(d for d in before["dimensions"] if d["key"] == "components")
    assert d_before["available"] is False

    database.save_component_test("TR-X", GOOD_BUSHINGS)
    after = health_service.transformer_health("TR-X")["health"]
    d_after = next(d for d in after["dimensions"] if d["key"] == "components")
    assert d_after["available"] is True
    assert d_after["score"] == 100.0


def test_kunye_kapasitansi_olmadan_kayit_reddedilir(db):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.test_electrical_api import _auth

    client = TestClient(app)
    r = client.post("/transformers/TR-X/component-tests",
                    json={"bushing_a_cap_pf": 410.0}, headers=_auth())
    assert r.status_code == 400
    assert "SAPMADIR" in r.json()["detail"]


def test_bilesen_testi_kimlik_ister(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-X/component-tests",
                    json={"oltc_operations": 1000})
    assert r.status_code == 401
