"""Trafo şeması testleri. — Faz 9.6

Şema kendi başına ölçüm üretmez; ölçümleri parçalara EŞLER. Test edilen
şey bu eşleme: doğru parça, doğru ölçümden beslensin.
"""
from __future__ import annotations

import pytest

from app import database
from app.services import schematic


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    database.upsert_transformer("TR-X", "Test", "X", asset_class="LPT",
                                mva=150.0, tap_changer_type="OLTC")
    return database


def _part(result, code):
    return next(p for p in result["parts"] if p["code"] == code)


def test_olmayan_trafo(db):
    assert schematic.build("YOK")["found"] is False


def test_olcum_yoksa_parcalar_bilinmiyor(db):
    r = schematic.build("TR-X")
    assert r["found"] is True
    assert _part(r, "windings")["condition"] == "bilinmiyor"
    assert _part(r, "bushing_a")["condition"] == "bilinmiyor"
    # "Bilinmiyor" ile "iyi" karıştırılmamalı: ölçümü olmayan bir parça
    # sağlıklı SAYILMAZ.
    assert r["summary"]["known"] == 0


def test_busing_parcasi_bilesen_testinden_beslenir(db):
    database.save_component_test("TR-X", {
        "bushing_a_pf_pct": 0.3, "bushing_a_cap_pf": 410.0,
        "bushing_a_cap_rated_pf": 410.0,
        "bushing_b_pf_pct": 0.3, "bushing_b_cap_pf": 438.0,
        "bushing_b_cap_rated_pf": 410.0,
    })
    r = schematic.build("TR-X")
    assert _part(r, "bushing_a")["condition"] == "iyi"
    assert _part(r, "bushing_b")["condition"] == "kötü"
    assert _part(r, "bushing_b")["source"] == "Buşing testi"
    # Şemadan ölçüme gidilebilmeli:
    assert _part(r, "bushing_b")["tab"] == "components"


def test_sargi_parcasi_DGA_dan_beslenir(db):
    gases = {"H2": 400.0, "CH4": 200.0, "C2H6": 90.0, "C2H4": 300.0,
             "C2H2": 90.0, "CO": 600.0, "CO2": 5000.0}
    database.save_measurement("TR-X", gases, {
        "prediction": "D2", "confidence": 0.95,
        "risk": {"level": "critical", "condition": 4}})

    r = schematic.build("TR-X")
    windings = _part(r, "windings")
    assert windings["condition"] == "kötü"
    assert "DGA" in windings["source"]
    assert windings["tab"] == "measurements"


def test_radyator_ve_koruma_saha_gozleminden_beslenir(db):
    database.save_physical_inspection("TR-X", {
        "cooling": "kötü", "protection": "iyi", "oil_leak": "dikkat",
        "silica_gel": "iyi",
    })
    r = schematic.build("TR-X")
    assert _part(r, "cooling")["condition"] == "kötü"
    assert _part(r, "protection")["condition"] == "iyi"
    assert _part(r, "tank")["condition"] == "kabul"      # dikkat -> kabul
    assert _part(r, "cooling")["tab"] == "inspection"


def test_kademesiz_trafoda_oltc_parcasi_yok_der(db):
    database.upsert_transformer("TR-Z", "Kademesiz", "X")
    r = schematic.build("TR-Z")
    oltc = _part(r, "oltc")
    assert oltc["condition"] == "yok"
    assert "kademe değiştirici yok" in oltc["detail"]


def test_her_parcanin_kaynagi_yazili(db):
    """Renkli bir kutu kendi başına bir iddiadır; kaynağı görünmeli."""
    r = schematic.build("TR-X")
    for p in r["parts"]:
        assert p["source"], p["code"]
        assert p["label"], p["code"]
        assert p["tab"], p["code"]


def test_gecersiz_yag_testi_semaya_girmez(db):
    """Faz 8.6 kararının devamı: geçersiz kayıt hüküm üretmez."""
    database.save_oil_test("TR-X", {"water_ppm": 45.0, "bdv_kv": 22.0})
    test_id = database.get_oil_tests("TR-X")[0]["id"]

    before = _part(schematic.build("TR-X"), "oil")["condition"]
    assert before == "kötü"

    database.void_test("oil_tests", "TR-X", test_id, "numune kirlenmiş")
    after = _part(schematic.build("TR-X"), "oil")["condition"]
    assert after == "bilinmiyor"
