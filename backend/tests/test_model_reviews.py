"""Model inceleme kuyruğu ve uzman etiketi. (Faz 12.3)

İki şey sınanıyor: kuralların kendisi (saf) ve uzman kararının sistemin
geri kalanına doğru yayılması — filo kartında tanının, ciddi arıza
işaretinin ve inceleme bayrağının değişmesi. İkincisi önemli: .NET bakım
planlayıcısı iş emri önerisini bu alanlardan üretiyor.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import database
from app.core import expert_label as core_label
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

GASES = {"H2": 120.0, "CH4": 60.0, "C2H6": 20.0, "C2H4": 80.0,
         "C2H2": 2.0, "CO": 300.0, "CO2": 2500.0}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "model_review.db")
    database.init_db()
    database.upsert_transformer("TR-M", "LPT Trafo", "X", asset_class="LPT", mva=150.0)
    database.upsert_transformer("TR-N", "MPT Trafo", "X", asset_class="MPT", mva=40.0)
    return TestClient(app)


def _measure(tid, prediction, confidence, sampled_at, recorded_by=None):
    return database.save_measurement(
        tid, GASES,
        {"prediction": prediction, "confidence": confidence,
         "risk": {"level": "medium", "condition": 2}},
        sampled_at=sampled_at, recorded_by=recorded_by)


def _label(client, mid, label, who, note=None):
    return client.post(f"/model-reviews/{mid}/label",
                       json={"label": label, "note": note}, headers=_auth(**who))


def _card(tid):
    from app.services import fleet as fleet_service
    o = fleet_service.overview()
    return o, next(c for c in o["transformers"] if c["id"] == tid)


# --- Saf kurallar ------------------------------------------------------------

def test_etiket_kurallari():
    m = {"prediction": "D1", "recorded_by_id": "10455"}
    assert core_label.validate_label(m, "X9", None, "10833", None)[0] == 400
    assert core_label.validate_label(m, "D1", None, "10833",
                                     {"expert_label": "D1"})[0] == 409
    assert core_label.validate_label(m, "D1", None, "10455", None)[0] == 403
    # Modelle aynı fikirde: gerekçe gerekmez.
    assert core_label.validate_label(m, "D1", None, "10833", None) is None
    # Farklı fikir ya da "belirlenemedi": gerekçe zorunlu.
    assert core_label.validate_label(m, "T3", None, "10833", None)[0] == 400
    assert core_label.validate_label(m, "undetermined", "kısa", "10833", None)[0] == 400
    assert core_label.validate_label(m, "T3", "Etilen baskın, termal", "10833", None) is None


def test_uzman_karari_karta_uygulanir_ve_model_tahmini_korunur():
    card = {"prediction": "D1", "severe": False, "needs_review": True}
    core_label.apply_to_card(card, {"expert_label": "T3", "labeled_by_name": "Deniz Koç"})
    assert card["prediction"] == "T3"
    assert card["severe"] is True
    assert card["prediction_family"] == "Termal"
    assert card["prediction_source"] == "expert"
    assert card["model_prediction"] == "D1"
    assert card["needs_review"] is False


def test_belirlenemedi_karari_taniyi_degistirmez_incelemeyi_korur():
    card = {"prediction": "D1", "severe": False, "needs_review": True}
    core_label.apply_to_card(card, {"expert_label": "undetermined"})
    assert card["prediction"] == "D1"
    assert card["prediction_source"] == "model"
    assert card["needs_review"] is True
    assert card["expert_label_tr"] == "Belirlenemedi"


def test_uyum_istatistigi_aileyi_ve_kacirilan_ciddi_arizayi_ayirir():
    rows = [
        {"model_prediction": "T1", "expert_label": "T1"},
        {"model_prediction": "T1", "expert_label": "T2"},      # aile aynı
        {"model_prediction": "D1", "expert_label": "D2"},      # ciddi kaçırıldı
        {"model_prediction": "D1", "expert_label": "undetermined"},
    ]
    s = core_label.agreement_stats(rows)
    assert s["labeled"] == 4 and s["determined"] == 3 and s["undetermined"] == 1
    assert s["agreement_rate"] == round(1 / 3, 3)
    assert s["family_agreement_rate"] == 1.0
    assert s["severe_missed_by_model"] == 1
    assert {(d["model"], d["expert"]) for d in s["disagreements"]} == {("T1", "T2"), ("D1", "D2")}


# --- Kuyruk ------------------------------------------------------------------

def test_kuyruk_dusuk_guvenli_olcumleri_son_olcum_once_listeler(client):
    old = _measure("TR-M", "D1", 0.60, "2026-01-10T00:00:00+00:00")
    latest = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")
    _measure("TR-N", "T1", 0.99, "2026-06-11T00:00:00+00:00")    # emin → kuyrukta değil

    q = client.get("/model-reviews/queue").json()
    assert [i["measurement_id"] for i in q["items"]] == [latest, old]
    assert q["items"][0]["is_latest"] is True
    assert q["items"][1]["is_latest"] is False
    assert q["stats"]["pending"] == 2


def test_etiketlenen_olcum_kuyruktan_cikar(client):
    mid = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")
    r = _label(client, mid, "D1", ENGINEER)
    assert r.status_code == 200
    assert r.json()["item"]["agrees"] is True

    assert client.get("/model-reviews/queue").json()["items"] == []
    labeled = client.get("/model-reviews/queue?folder=labeled").json()["items"]
    assert labeled[0]["labeled_by_name"] == "Deniz Koç"


# --- Yetki ve dört göz -------------------------------------------------------

def test_kaydeden_muhendis_kendi_olcumunu_etiketleyemez(client):
    mid = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00",
                   recorded_by={"employee_no": "10833", "name": "Deniz Koç"})
    assert _label(client, mid, "D1", ENGINEER).status_code == 403
    assert _label(client, mid, "D1", ENGINEER_2).status_code == 200


def test_laboratuvar_etiketleyemez(client):
    mid = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")
    r = _label(client, mid, "D1", LAB)
    assert r.status_code == 403
    assert r.json()["detail"]["required_permission"] == "engineering.review_model"


def test_uzman_karari_bir_kez_verilir(client):
    mid = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")
    assert _label(client, mid, "D1", ENGINEER).status_code == 200
    assert _label(client, mid, "T2", ENGINEER_2,
                  note="Etilen oranı termale işaret ediyor").status_code == 409


# --- Sistemin geri kalanına etkisi -------------------------------------------

def test_uzman_karari_filo_kartini_ve_inceleme_sayisini_degistirir(client):
    _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")

    before, card = _card("TR-M")
    assert card["needs_review"] is True
    assert card["severe"] is False
    assert before["summary"]["needs_review"] == 1

    mid = client.get("/model-reviews/queue").json()["items"][0]["measurement_id"]
    r = _label(client, mid, "T3", ENGINEER,
               note="C2H4 çok baskın, yüksek sıcaklık termal arıza")
    assert r.status_code == 200

    after, card = _card("TR-M")
    # .NET planlayıcısı `severe` ve `needs_review` alanlarını okuyor: uzman
    # kararı artık ACİL iş emri üretecek, "inceleme" önerisi düşecek.
    assert card["prediction"] == "T3"
    assert card["severe"] is True
    assert card["prediction_source"] == "expert"
    assert card["model_prediction"] == "D1"
    assert card["needs_review"] is False
    assert after["summary"]["needs_review"] == 0


def test_belirlenemedi_veri_setine_girmez_ve_inceleme_surer(client):
    a = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")
    b = _measure("TR-N", "T1", 0.65, "2026-06-11T00:00:00+00:00")
    assert _label(client, a, "undetermined", ENGINEER,
                  note="Gazlar çelişkili, yeni numune gerekli").status_code == 200
    assert _label(client, b, "T2", ENGINEER,
                  note="Metan/etilen oranı T2 aralığında").status_code == 200

    _, card = _card("TR-M")
    assert card["needs_review"] is True

    data = client.get("/model-reviews/dataset").json()
    assert data["count"] == 1
    assert data["rows"][0]["expert_label"] == "T2"
    assert data["rows"][0]["H2"] == GASES["H2"]

    csv_text = client.get("/model-reviews/dataset?format=csv").text
    header = csv_text.splitlines()[0]
    assert "H2" in header and "expert_label" in header
    assert len(csv_text.strip().splitlines()) == 2      # başlık + 1 satır


def test_ayrinti_gazlari_ve_klasik_oylari_getirir(client):
    mid = _measure("TR-M", "D1", 0.70, "2026-06-10T00:00:00+00:00")
    d = client.get(f"/model-reviews/{mid}").json()
    assert d["gases"]["C2H4"] == 80.0
    assert d["classical"]["prediction"]
    assert isinstance(d["classical"]["votes"], list)
    assert any(opt["value"] == "undetermined" for opt in d["labels"])
    assert client.get("/model-reviews/999999").status_code == 404


def test_olcum_kaydi_kimin_girdigini_saklar(client):
    """Dört göz kuralının çalışabilmesi için DGA ölçümü de 'kim girdi' taşımalı."""
    body = {"gases": GASES, "transformer_id": "TR-M", "persist": True}
    assert client.post("/predict", json=body, headers=_auth(**LAB)).status_code == 200
    saved = database.get_measurements("TR-M")[-1]
    assert saved["recorded_by_id"] == "10455"
    assert saved["recorded_by_name"] == "Mehmet Kaya"
