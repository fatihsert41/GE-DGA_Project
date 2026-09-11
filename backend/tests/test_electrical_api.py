"""Elektriksel test servisi ve uç noktaları. — Faz 8.6

Çekirdek motorun testleri ``test_electrical.py`` içinde (saf hesap).
Burada test edilen şey farklı: **künye ile ölçümün birleşmesi.** Aynı
ölçüm, farklı künyeyle farklı hüküm alır — bu katmanın işi tam olarak bu.
"""
from __future__ import annotations

import pytest

from app import database
from app.services import electrical as el_service


# --- Test kimliği ---------------------------------------------------------
# Yazma uç noktaları artık kimlik istiyor (Faz 9.0c). Test, .NET'in
# ürettiğine denk bir belirteci AYNI paylaşılan anahtarla kendisi imzalar.
# Gerçek sistemde imzayı yalnızca .NET atar; burada amaç .NET'i ayağa
# kaldırmadan uç nokta davranışını sınamak.

def _token(employee_no="10502", name="Test Kullanıcı", role="Supervisor",
           valid_seconds=3600):
    import base64, hashlib, hmac, json, time
    from app import auth as auth_module

    payload = {
        "employee_no": employee_no, "name": name, "role": role,
        "expires_at_unix": int(time.time()) + valid_seconds,
        "nonce": "test",
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")).decode().rstrip("=")
    sig = hmac.new(auth_module._secret().encode("utf-8"),
                   body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def _auth(**kwargs):
    return {"Authorization": f"Bearer {_token(**kwargs)}"}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Her test kendi geçici veritabanını alır."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    # 154/34.5 kV YNd11 → beklenen oran (154/34.5)×√3 = 7.7315
    database.upsert_transformer(
        "TR-TEST", "Test Trafosu", "Laboratuvar",
        asset_class="LPT", mva=150.0,
        hv_kv=154.0, lv_kv=34.5, vector_group="YNd11",
        winding_material="Cu", tap_changer_type="OLTC",
        tap_min=-9, tap_max=9, tap_step_percent=1.25,
    )
    return database


# --- Künye bağlamı -------------------------------------------------------

def test_beklenen_oran_kunyeden_hesaplanir(db):
    assert el_service.expected_ratio("TR-TEST") == pytest.approx(7.7315,
                                                                 abs=0.001)


def test_kademe_beklentiyi_kaydirir(db):
    """+4 kademe, beklenen oranı %5 yukarı taşır (4 × %1.25)."""
    base = el_service.expected_ratio("TR-TEST")
    at_tap = el_service.expected_ratio("TR-TEST", tap=4)
    assert at_tap == pytest.approx(base * 1.05, abs=0.001)


def test_ayni_olcum_kademeye_gore_farkli_hukum_alir(db):
    """Bu, bu katmanın var oluş sebebi.

    +4 kademede ölçülmüş bir trafo, kademe 0 sanılırsa "arızalı" görünür.
    """
    measured = el_service.expected_ratio("TR-TEST", tap=4)
    test = {"ttr_a": measured, "ttr_b": measured, "ttr_c": measured}

    dogru = el_service.assess_test("TR-TEST", {**test, "tap_position": 4})
    yanlis = el_service.assess_test("TR-TEST", {**test, "tap_position": 0})

    assert dogru["overall"] == "iyi"
    assert yanlis["overall"] == "kötü"
    # Ama sistem bunun sargı arızası olmadığını söyleyebilmeli:
    assert any("KADEME" in w for w in yanlis["warnings"])


def test_sargi_malzemesi_kunyeden_okunur(db):
    test = {"rw_a_ohm": 0.512, "rw_b_ohm": 0.514, "rw_c_ohm": 0.513,
            "winding_temp_c": 30.0}
    r = el_service.assess_test("TR-TEST", test)
    section = r["sections"]["winding_resistance"]
    assert section["winding_material"] == "Cu"


# --- Kayıt ve geçmiş -----------------------------------------------------

def test_kayit_ve_gecmis(db):
    database.save_electrical_test("TR-TEST", {
        "tap_position": 0, "ttr_a": 7.7315, "ttr_b": 7.7320, "ttr_c": 7.7310,
        "rw_a_ohm": 0.512, "rw_b_ohm": 0.514, "rw_c_ohm": 0.513,
    }, tested_at="2025-03-01T10:00:00+00:00")

    h = el_service.history("TR-TEST")
    assert h["available"] is True
    assert h["n_tests"] == 1
    assert h["latest_assessment"]["overall"] == "iyi"


def test_test_yoksa_guvenli_cevap(db):
    h = el_service.history("TR-TEST")
    assert h["available"] is False
    assert h["reason"] == "no_electrical_tests"


def test_dengesizlik_serisi_zaman_icinde_gelisimi_gosterir(db):
    """Tek ölçüm 'iyi' olsa bile eğilim uyarı verebilmeli."""
    database.save_electrical_test("TR-TEST", {
        "rw_a_ohm": 0.5120, "rw_b_ohm": 0.5122, "rw_c_ohm": 0.5121,
    }, tested_at="2023-03-01T10:00:00+00:00")
    database.save_electrical_test("TR-TEST", {
        "rw_a_ohm": 0.5120, "rw_b_ohm": 0.5210, "rw_c_ohm": 0.5121,
    }, tested_at="2025-03-01T10:00:00+00:00")

    series = el_service.history("TR-TEST")["imbalance_series"]
    assert len(series) == 2
    assert series[1]["imbalance_pct"] > series[0]["imbalance_pct"]


def test_filo_ozeti_hic_test_edilmemisleri_sayar(db):
    database.upsert_transformer("TR-BOS", "Testsiz", "X")
    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3})

    s = el_service.fleet_summary()
    assert s["tested"] == 1
    assert "TR-BOS" in s["never_tested"]


def test_kart_ozeti_testsiz_trafoda_patlamaz(db):
    card = el_service.electrical_card("TR-TEST", None)
    assert card["has_electrical_test"] is False
    assert card["electrical_overall"] is None


# --- Uç nokta kuralları --------------------------------------------------

def test_kademeli_trafoda_ttr_icin_kademe_zorunlu(db, monkeypatch):
    """Yaşanmış saha hatası kurala dönüştü: kademe bilinmeden TTR yorumlanamaz."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-TEST/electrical-tests",
                    json={"ttr_a": 7.73, "ttr_b": 7.73, "ttr_c": 7.73},
                    headers=_auth())
    assert r.status_code == 400
    assert "kademe" in r.json()["detail"].lower()


def test_sadece_kademe_girmek_kayit_olusturmaz(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-TEST/electrical-tests",
                    json={"tap_position": 3}, headers=_auth())
    assert r.status_code == 400
    assert el_service.history("TR-TEST")["available"] is False


def test_olmayan_trafo_404(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    assert client.get("/transformers/YOK/electrical-tests").status_code == 404
    assert client.get("/transformers/YOK/expected-ratio").status_code == 404


# --- Geçersiz işaretleme: silme YOK --------------------------------------
# Ölçüm kayıtları bir varlığın denetlenebilir geçmişidir. Hatalı bir test
# raporu sahada imha edilmez, "geçersiz" damgası vurulur ve dosyada kalır.

def test_silme_uc_noktasi_YOKTUR(db):
    """Bilinçli bir tasarım kararı; yanlışlıkla eklenirse test uyarsın."""
    from fastapi.testclient import TestClient
    from app.main import app

    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3})
    test_id = database.get_electrical_tests("TR-TEST")[0]["id"]

    client = TestClient(app)
    r = client.delete(f"/transformers/TR-TEST/electrical-tests/{test_id}")
    assert r.status_code in (404, 405)      # böyle bir uç nokta yok
    assert len(database.get_electrical_tests("TR-TEST")) == 1


def test_gecersiz_isaretlenen_kayit_silinmez_ama_hukum_uretmez(db):
    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3})
    test_id = database.get_electrical_tests("TR-TEST")[0]["id"]

    assert database.void_test("electrical_tests", "TR-TEST", test_id,
                              "basamak hatası") is True

    # Kayıt DURUYOR:
    tests = database.get_electrical_tests("TR-TEST")
    assert len(tests) == 1
    assert tests[0]["void_reason"] == "basamak hatası"

    # Ama hüküm üretmiyor:
    assert database.latest_electrical_tests().get("TR-TEST") is None
    h = el_service.history("TR-TEST")
    assert h["available"] is False
    assert h["reason"] == "all_voided"
    # Geçmişte yine de GÖRÜNÜYOR, gerekçesiyle:
    assert h["summaries"][0]["voided"] is True


def test_gecersiz_kayit_saglik_endeksine_girmez(db):
    """Hatalı ölçüm skoru bozmamalı — ama 'ölçüm yok' da demeli."""
    from app.services import health as health_service

    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 4.0})  # kötü
    test_id = database.get_electrical_tests("TR-TEST")[0]["id"]

    before = health_service.transformer_health("TR-TEST")["health"]
    database.void_test("electrical_tests", "TR-TEST", test_id, "cihaz arızası")
    after = health_service.transformer_health("TR-TEST")["health"]

    el_before = next(d for d in before["dimensions"] if d["key"] == "electrical")
    el_after = next(d for d in after["dimensions"] if d["key"] == "electrical")
    assert el_before["available"] is True
    assert el_after["available"] is False      # artık ölçüm sayılmıyor


def test_gecersiz_isareti_geri_alinabilir(db):
    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3})
    test_id = database.get_electrical_tests("TR-TEST")[0]["id"]

    database.void_test("electrical_tests", "TR-TEST", test_id, "yanlışlıkla")
    database.void_test("electrical_tests", "TR-TEST", test_id, "")

    assert database.latest_electrical_tests().get("TR-TEST") is not None
    assert el_service.history("TR-TEST")["available"] is True


def test_gecersiz_isaretlemede_gerekce_zorunlu(db):
    """Gerekçesiz damga, silmekten pek farklı olmazdı."""
    from fastapi.testclient import TestClient
    from app.main import app

    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3})
    test_id = database.get_electrical_tests("TR-TEST")[0]["id"]

    client = TestClient(app)
    r = client.post(f"/transformers/TR-TEST/electrical-tests/{test_id}/void",
                    json={"reason": "kısa"}, headers=_auth())
    assert r.status_code == 422                # min_length=5


def test_gecersiz_kayit_son_test_olarak_gosterilmez(db):
    """Yaşanan hata: geçersiz kaydın bulgusu ekranda "son test" görünüyordu.

    Geçersiz işaretlemenin tüm amacı o kaydın hüküm üretmemesi; başlıkta
    onu göstermek amacı boşa çıkarırdı.
    """
    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3},
                                  tested_at="2026-09-10T10:00:00+00:00")
    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 4.0},
                                  tested_at="2026-09-11T10:00:00+00:00")
    tests = database.get_electrical_tests("TR-TEST")
    database.void_test("electrical_tests", "TR-TEST", tests[-1]["id"],
                       "cihaz kalibrasyonu şüpheli")

    h = el_service.history("TR-TEST")
    assert h["available"] is True
    # Geçerli son test 10 Eylül'deki; hüküm ondan gelmeli:
    assert h["latest_valid_id"] == tests[0]["id"]
    assert h["latest_assessment"]["overall"] == "iyi"
    assert h["n_tests"] == 2 and h["n_valid"] == 1


# --- Kimlik zorunluluğu (Faz 9.0c) ---------------------------------------

def test_kimliksiz_yazma_reddedilir(db):
    """Sorumlusu bilinmeyen bir ölçüm kaydı oluşturulmamalı."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-TEST/electrical-tests",
                    json={"tan_delta_pct": 0.3})
    assert r.status_code == 401
    assert el_service.history("TR-TEST")["available"] is False


def test_kimlik_kayda_islenir(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-TEST/electrical-tests",
                    json={"tan_delta_pct": 0.3},
                    headers=_auth(employee_no="10247", name="Ahmet Yılmaz"))
    assert r.status_code == 200

    saved = database.get_electrical_tests("TR-TEST")[0]
    assert saved["recorded_by_id"] == "10247"
    assert saved["recorded_by_name"] == "Ahmet Yılmaz"


def test_kurcalanmis_belirtec_reddedilir(db):
    """İmzası bozulmuş belirteçle rol yükseltilememeli."""
    from fastapi.testclient import TestClient
    from app.main import app

    token = _token()
    body, sig = token.split(".")
    client = TestClient(app)
    r = client.post("/transformers/TR-TEST/electrical-tests",
                    json={"tan_delta_pct": 0.3},
                    headers={"Authorization": f"Bearer {body}.{'A' * len(sig)}"})
    assert r.status_code == 401


def test_suresi_dolmus_belirtec_reddedilir(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/transformers/TR-TEST/electrical-tests",
                    json={"tan_delta_pct": 0.3},
                    headers=_auth(valid_seconds=-10))
    assert r.status_code == 401


def test_gecersiz_isaretleyen_kisi_kaydedilir(db):
    """Kimin geçersiz saydığı da denetim izinin parçası."""
    from fastapi.testclient import TestClient
    from app.main import app

    database.save_electrical_test("TR-TEST", {"tan_delta_pct": 0.3})
    test_id = database.get_electrical_tests("TR-TEST")[0]["id"]

    client = TestClient(app)
    r = client.post(f"/transformers/TR-TEST/electrical-tests/{test_id}/void",
                    json={"reason": "cihaz kalibrasyonu şüpheli"},
                    headers=_auth(employee_no="10318", name="Elif Demir"))
    assert r.status_code == 200

    saved = database.get_electrical_tests("TR-TEST")[0]
    assert saved["voided_by_id"] == "10318"
    assert saved["voided_by_name"] == "Elif Demir"
