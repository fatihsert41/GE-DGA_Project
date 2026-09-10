"""Dış inceleme bulgularının düzeltmeleri — gerileme (regression) testleri.

Bu testlerin her biri, GERÇEKTEN YAŞANMIŞ bir hatayı temsil eder. Amaçları
hatanın geri gelmesini engellemek: bir gün biri "ensure_transformer yerine
upsert kullansam ne olur?" derse test kırılır ve sebebini okur.

Bulgular: docs/DIS-INCELEME-DOGRULAMA.md
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import database
from app.services import fleet as fleet_service


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Her test kendi geçici veritabanını alır."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    return database


_GASES = {"H2": 50.0, "CH4": 20.0, "C2H6": 10.0, "C2H4": 15.0,
          "C2H2": 1.0, "CO": 300.0, "CO2": 2500.0}
_DIAG = {"prediction": "Normal", "confidence": 1.0,
         "risk": {"level": "low", "condition": 1}}


# ---------------------------------------------------------------------------
# P0-1 · Ölçüm eklemek varlık kaydını EZMEMELİ
# ---------------------------------------------------------------------------

def test_olcum_eklemek_varlik_kunyesini_bozmaz(db):
    """Yaşanan hata: tek bir /predict çağrısı bir LPT'yi MPT'ye düşürüyordu.

    Öncelik = kondisyon × varlık ağırlığı olduğu için kritik bir trafonun
    önceliği sessizce 4.00'ten 2.80'e iniyordu.
    """
    db.upsert_transformer("TR-X", "Gebze Trafosu", "Gebze",
                          asset_class="LPT", mva=150.0,
                          manufacturer="GE Vernova", hv_kv=154.0, lv_kv=34.5)

    db.ensure_transformer("TR-X", "Gebze Trafosu")   # tahmin yolunun çağrısı

    after = db.get_transformer("TR-X")
    assert after["location"] == "Gebze"
    assert after["asset_class"] == "LPT"
    assert after["mva"] == 150.0
    assert after["nameplate"]["manufacturer"] == "GE Vernova"


def test_ensure_transformer_yoksa_olusturur(db):
    assert db.ensure_transformer("TR-YENI", "Yeni Trafo") is True
    assert db.get_transformer("TR-YENI")["name"] == "Yeni Trafo"
    # İkinci çağrı yeni kayıt açmaz.
    assert db.ensure_transformer("TR-YENI", "Başka Ad") is False
    assert db.get_transformer("TR-YENI")["name"] == "Yeni Trafo"


# ---------------------------------------------------------------------------
# P0-2 · Trend GERÇEK zaman eksenini kullanmalı
# ---------------------------------------------------------------------------

def _seed_series(db, tid: str, interval_days: int, values: list[float]) -> None:
    db.ensure_transformer(tid, tid)
    start = datetime.now(timezone.utc) - timedelta(
        days=interval_days * (len(values) - 1))
    for i, h2 in enumerate(values):
        db.save_measurement(
            tid, {**_GASES, "H2": h2}, _DIAG,
            sampled_at=(start + timedelta(days=interval_days * i)).isoformat())


def test_gaz_uretim_hizi_olcum_araligina_duyarli(db):
    """Yaşanan hata: eksen olarak ölçüm SIRASI kullanılıyordu.

    Bir gün arayla alınan iki numune ile bir ay arayla alınanlar aynı
    "kritik süre" değerini üretiyordu — fiziksel olarak 30 kat hata.
    """
    from app.routers.trend import trend_from_history

    values = [30.0, 40.0, 50.0, 60.0]
    _seed_series(db, "AYLIK", 30, values)
    _seed_series(db, "GUNLUK", 1, values)

    aylik = trend_from_history("AYLIK")
    gunluk = trend_from_history("GUNLUK")

    slope_aylik = aylik["per_gas"]["H2"]["slope"]
    slope_gunluk = gunluk["per_gas"]["H2"]["slope"]

    # Günlük numune alınan trafoda gaz üretim hızı ~30 kat yüksek olmalı.
    assert slope_gunluk > slope_aylik * 20
    assert gunluk["months_to_critical"] < aylik["months_to_critical"]


def test_trend_zaman_ekseni_birimini_bildirir(db):
    """"3.9" sayısının neyin 3.9'u olduğu cevapta yazmalı."""
    from app.routers.trend import trend_from_history

    _seed_series(db, "T", 30, [30.0, 40.0, 50.0, 60.0])
    axis = trend_from_history("T")["time_axis"]

    assert axis["unit"] == "months"
    assert axis["source"] == "sampled_at"
    assert axis["mean_interval_days"] == pytest.approx(30, abs=1)


def test_yetersiz_gecmiste_trend_uretilmez(db):
    """Yetersiz veriyle sayı üretmek, olmayan bir kesinlik iddia etmektir."""
    from app.routers.trend import trend_from_history

    _seed_series(db, "TEK", 30, [30.0, 40.0])   # 2 ölçüm, eşik 3
    result = trend_from_history("TEK")

    assert result["available"] is False
    assert result["reason"] == "insufficient_history"
    # Ölçümler yine de dönmeli: kullanıcı elindekini görebilmeli.
    assert len(result["measurements"]) == 2


# ---------------------------------------------------------------------------
# P0-3 · "Veri yok" ile "güncel" AYNI ŞEY DEĞİL
# ---------------------------------------------------------------------------

def _row(**over):
    base = dict(transformer_id="T", transformer_name="T", location="Bursa",
                asset_class="LPT", mva=150.0, measurement_count=0, gases=None,
                sampled_at=None, prediction=None, confidence=None,
                risk_level=None, risk_condition=None, manufacturer="GE",
                hv_kv=154.0, lv_kv=34.5, cooling="ONAF",
                commissioned_at="2010-01-01", year_made=2010)
    return {**base, **over}


def test_hic_numune_alinmamis_varlik_gorunur(db):
    """Yaşanan hata: 15 yaşında hiç ölçülmemiş LPT hiçbir uyarı üretmiyordu."""
    card = fleet_service._to_card(_row())

    assert card["sampling_status"] == "never_sampled"
    # never_sampled DA bir gecikmedir: temel çizgi numunesi alınmamış.
    assert card["sampling_overdue"] is True


def test_uc_numune_durumu_ayrilir(db):
    now = datetime.now(timezone.utc)
    gec = _row(sampled_at=(now - timedelta(days=400)).isoformat(),
               measurement_count=5)
    guncel = _row(sampled_at=now.isoformat(), measurement_count=5)

    assert fleet_service._to_card(_row())["sampling_status"] == "never_sampled"
    assert fleet_service._to_card(gec)["sampling_status"] == "overdue"
    assert fleet_service._to_card(guncel)["sampling_status"] == "current"
    assert fleet_service._to_card(guncel)["sampling_overdue"] is False


def test_ozet_hic_olculmemis_varliklari_sayar(db):
    db.upsert_transformer("A", "A", asset_class="LPT")
    db.upsert_transformer("B", "B", asset_class="MPT")
    db.save_measurement("B", _GASES, _DIAG)

    summary = fleet_service.overview()["summary"]

    assert summary["never_sampled"] == 1
    assert summary["sampling_overdue"] >= 1
