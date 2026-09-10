"""Trafo künyesi: doğrulama ve türetilmiş büyüklükler (Faz 8.1)."""
from __future__ import annotations

from datetime import date

import pytest

from app.core import nameplate as N

_VALID = {
    "manufacturer": "GE Vernova",
    "year_made": 2015,
    "commissioned_at": "2015-06-01",
    "hv_kv": 154.0,
    "lv_kv": 34.5,
    "vector_group": "YNd11",
    "cooling": "ONAF",
    "oil_volume_l": 28000.0,
    "winding_material": "Cu",
    "insulation_type": "tuk",
    "tap_changer_type": "OLTC",
    "tap_min": -9,
    "tap_max": 9,
    "tap_step_percent": 1.25,
}


def test_gecerli_kunye_sorun_uretmez():
    assert N.validate(_VALID) == []


def test_dogrulama_TUM_sorunlari_birden_dondurur():
    """Tek tek düzelttirmek yerine hepsini birden göstermek gerekir."""
    problems = N.validate({
        "hv_kv": 10.0, "lv_kv": 34.5,      # YG < AG
        "cooling": "XXXX",                  # geçersiz
        "vector_group": "ZZZ",              # geçersiz
        "winding_material": "Altin",        # geçersiz
        "tap_min": 5, "tap_max": -5,        # ters aralık
    })
    assert len(problems) >= 5


def test_yg_ag_geriliminden_buyuk_olmali():
    problems = N.validate({**_VALID, "hv_kv": 20.0, "lv_kv": 34.5})
    assert any("büyük olmalı" in p for p in problems)


@pytest.mark.parametrize("field,value", [
    ("mva", -5),
    ("mva", 0),
    ("oil_volume_l", -100),
])
def test_pozitif_olmasi_gereken_alanlar(field, value):
    problems = N.validate({**_VALID, field: value})
    assert any(field in p for p in problems)


def test_makul_olmayan_uretim_yili_yakalanir():
    assert N.validate({**_VALID, "year_made": 1750})
    assert N.validate({**_VALID, "year_made": 2200})


def test_bos_kunye_sorun_uretmez():
    """Künye parça parça girilir; boş alanlar hata değildir."""
    assert N.validate({}) == []


# --- Türetilmiş büyüklükler ------------------------------------------------

def test_yas_devreye_alma_tarihinden_hesaplanir():
    age = N.age_years({"commissioned_at": "2015-01-01"},
                      today=date(2025, 1, 1))
    assert age == pytest.approx(10.0, abs=0.1)


def test_yas_tarih_yoksa_uretim_yilina_duser():
    age = N.age_years({"year_made": 2000}, today=date(2025, 6, 1))
    assert age == 25


def test_yas_bilgi_yoksa_none():
    assert N.age_years({}) is None


def test_baglanti_grubu_sarim_oranini_degistirir():
    """TTR'nin en kritik ayrıntısı.

    Aynı gerilim oranı, bağlantı grubuna göre farklı FAZ-FAZ oranı verir:
    yıldız-üçgen kombinasyonlarında √3 çarpanı devreye girer. Bu çarpanı
    atlamak sağlam bir trafoyu "arızalı" gösterirdi.
    """
    base = {"hv_kv": 154.0, "lv_kv": 34.5}

    yy = N.rated_turns_ratio({**base, "vector_group": "YNyn0"})
    yd = N.rated_turns_ratio({**base, "vector_group": "YNd11"})
    dy = N.rated_turns_ratio({**base, "vector_group": "Dyn11"})

    assert yy == pytest.approx(154 / 34.5, rel=1e-3)
    assert yd == pytest.approx(yy * 3 ** 0.5, rel=1e-3)
    assert dy == pytest.approx(yy / 3 ** 0.5, rel=1e-3)


def test_gerilim_eksikse_sarim_orani_hesaplanamaz():
    assert N.rated_turns_ratio({"hv_kv": 154.0}) is None
    assert N.rated_turns_ratio({}) is None


def test_sifir_ag_gerilimi_bolme_hatasi_vermez():
    assert N.rated_turns_ratio({"hv_kv": 154.0, "lv_kv": 0}) is None


def test_kademe_pozisyonu_beklenen_orani_kaydirir():
    np = {"hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNyn0",
          "tap_step_percent": 1.25}

    nominal = N.turns_ratio_at_tap(np, 0)
    plus = N.turns_ratio_at_tap(np, 8)
    minus = N.turns_ratio_at_tap(np, -8)

    assert plus > nominal > minus
    # 8 kademe × %1.25 = %10 artış
    assert plus == pytest.approx(nominal * 1.10, rel=1e-3)


def test_kademe_adimi_yoksa_anma_orani_doner():
    np = {"hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNyn0"}
    assert N.turns_ratio_at_tap(np, 5) == N.rated_turns_ratio(np)


def test_ozet_etiketleri_turkcelestirir():
    s = N.summary(_VALID)
    assert s["cooling_label"] == N.COOLING_TYPES["ONAF"]
    assert s["insulation_label"] == N.INSULATION_TYPES["tuk"]
    assert s["tap_changer_label"] == N.TAP_CHANGER_TYPES["OLTC"]
    assert s["rated_turns_ratio"] is not None
