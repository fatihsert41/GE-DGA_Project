"""Varlık yaşam döngüsü testleri. — Faz 9.35"""
from __future__ import annotations

import pytest

from app import database
from app.core import lifecycle
from app.services import fleet as fleet_service


# --- Saf geçiş kuralları --------------------------------------------------

def test_ileri_gecisler_izinli():
    assert lifecycle.validate_transition("manufacturing", "factory_testing") is None
    assert lifecycle.validate_transition("ready_to_ship", "awaiting_transport") is None
    assert lifecycle.validate_transition("in_transit", "on_site") is None
    assert lifecycle.validate_transition("commissioning", "in_service") is None


def test_geriye_atlama_engellenir():
    """Devredeki bir trafo 'üretimde' olamaz."""
    problem = lifecycle.validate_transition("in_service", "manufacturing")
    assert problem is not None
    assert "geçilemez" in problem


def test_asama_atlamak_engellenir():
    """Nakliye bekleyen ünite doğrudan devreye alınamaz."""
    assert lifecycle.validate_transition("awaiting_transport", "in_service")


def test_bakim_sonrasi_donus_izinli():
    """Hizmet dışına alınan bir ünite geri dönebilmeli."""
    assert lifecycle.validate_transition("in_service", "out_of_service") is None
    assert lifecycle.validate_transition("out_of_service", "in_service") is None


def test_hurda_uc_durum():
    assert lifecycle.TRANSITIONS["scrapped"] == []
    assert lifecycle.validate_transition("scrapped", "in_service")


def test_ayni_duruma_gecis_reddedilir():
    problem = lifecycle.validate_transition("in_service", "in_service")
    assert "zaten" in problem


def test_yalnizca_devredeki_varlik_izlenir():
    """Kuralların sorduğu TEK soru bu."""
    assert lifecycle.is_monitored("in_service") is True
    for other in ("manufacturing", "factory_testing", "ready_to_ship",
                  "awaiting_transport", "in_transit", "on_site",
                  "commissioning", "spare", "out_of_service", "scrapped"):
        assert lifecycle.is_monitored(other) is False, other


def test_evreler_dogru_grupluyor():
    assert lifecycle.phase_of("ready_to_ship") == "factory"
    assert lifecycle.phase_of("awaiting_transport") == "transit"
    assert lifecycle.phase_of("commissioning") == "field"
    assert lifecycle.phase_of("scrapped") == "retired"


def test_bilinmeyen_durum_varsayilana_duser():
    assert lifecycle.get("uydurma")["code"] == lifecycle.DEFAULT_STATE


# --- Numune kuralının düzeltilmesi ---------------------------------------

@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    return database


def test_fabrikadaki_unite_numunesi_gecikmis_SAYILMAZ(db):
    """YAŞANAN HATA: sevkiyat bekleyen ünite için numune iş emri.

    Henüz enerjilenmemiş, yağında gaz üretmesi fiziksel olarak mümkün
    olmayan bir trafo için numune alma öneriliyordu. Kural yanlış
    değildi; kurala verilen varlık kümesi yanlıştı.
    """
    database.upsert_transformer("TR-10", "Yeni Ünite", "Fabrika",
                                asset_class="LPT", mva=200.0)
    database.set_lifecycle("TR-10", "factory_testing")
    database.set_lifecycle("TR-10", "ready_to_ship")
    database.set_lifecycle("TR-10", "awaiting_transport")

    card = next(c for c in fleet_service.overview()["transformers"]
                if c["id"] == "TR-10")

    assert card["lifecycle_status"] == "awaiting_transport"
    assert card["sampling_status"] == "not_monitored"
    assert card["sampling_overdue"] is False   # <-- düzeltme


def test_devredeki_olcumsuz_varlik_HALA_isaretlenir(db):
    """Düzeltme fazla geniş olmamalı: sahadaki ölçümsüz varlık acildir."""
    database.upsert_transformer("TR-11", "Devrede Ünite", "İstanbul",
                                asset_class="LPT", mva=150.0)

    card = next(c for c in fleet_service.overview()["transformers"]
                if c["id"] == "TR-11")

    assert card["lifecycle_status"] == "in_service"
    assert card["sampling_status"] == "never_sampled"
    assert card["sampling_overdue"] is True


def test_gecis_gecmisi_kim_yapti_kaydediyor(db):
    database.upsert_transformer("TR-12", "Ünite", "X")
    database.set_lifecycle("TR-12", "out_of_service", "Planlı bakım",
                           changed_by={"employee_no": "10502",
                                       "name": "Zeynep Şahin"})

    events = database.get_lifecycle_events("TR-12")
    assert len(events) == 1
    assert events[0]["from_status"] == "in_service"
    assert events[0]["to_status"] == "out_of_service"
    assert events[0]["changed_by_name"] == "Zeynep Şahin"
    assert events[0]["note"] == "Planlı bakım"


def test_gecersiz_gecis_uc_noktada_400(db):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.test_electrical_api import _auth

    database.upsert_transformer("TR-13", "Ünite", "X")
    client = TestClient(app)

    r = client.put("/transformers/TR-13/lifecycle",
                   json={"status": "manufacturing"}, headers=_auth())
    assert r.status_code == 400
    assert "geçilemez" in r.json()["detail"]


def test_gecis_kimlik_ister(db):
    from fastapi.testclient import TestClient
    from app.main import app

    database.upsert_transformer("TR-14", "Ünite", "X")
    client = TestClient(app)

    r = client.put("/transformers/TR-14/lifecycle",
                   json={"status": "out_of_service"})
    assert r.status_code == 401
