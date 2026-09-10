"""Yağ kalitesi ve kağıt yaşlanması (Faz 8.3)."""
from __future__ import annotations

import math

import pytest

from app.core import oil_quality as oq
from app.ml.synth_oil import make_oil_test


# --- Gerilim sınıfı ve eşikler --------------------------------------------

@pytest.mark.parametrize("hv_kv,expected", [
    (34.5, "<=72.5kV"),
    (72.5, "<=72.5kV"),
    (154.0, "72.5-170kV"),
    (170.0, "72.5-170kV"),
    (400.0, ">170kV"),
    (None, "72.5-170kV"),        # bilinmiyorsa makul orta varsayım
])
def test_gerilim_sinifi(hv_kv, expected):
    assert oq.voltage_class(hv_kv) == expected


def test_esikler_gerilimle_sikilasir():
    """Yüksek gerilimde aynı nem çok daha tehlikelidir."""
    dusuk = oq.assess_parameter("water_ppm", 18.0, "<=72.5kV")
    yuksek = oq.assess_parameter("water_ppm", 18.0, ">170kV")

    assert dusuk["condition"] == "iyi"
    assert yuksek["condition"] == "kötü"


def test_yon_dogru_uygulanir():
    """BDV'de BÜYÜK iyidir, nemde KÜÇÜK iyidir."""
    assert oq.assess_parameter("bdv_kv", 70.0, "72.5-170kV")["condition"] == "iyi"
    assert oq.assess_parameter("bdv_kv", 30.0, "72.5-170kV")["condition"] == "kötü"
    assert oq.assess_parameter("water_ppm", 5.0, "72.5-170kV")["condition"] == "iyi"
    assert oq.assess_parameter("water_ppm", 40.0, "72.5-170kV")["condition"] == "kötü"


def test_olculmeyen_parametre_bilinmiyor():
    """Ölçülmeyen parametre "iyi" sayılmamalı — bilgi yokluğu iyi haber değil."""
    assert oq.assess_parameter("water_ppm", None, ">170kV")["condition"] == "bilinmiyor"


# --- Chendong bağıntısı ----------------------------------------------------

def test_chendong_bagintisi_tersinir():
    """Formülden üretilen furan, geri çevrildiğinde aynı DP'yi vermeli."""
    for dp_true in (300, 500, 800, 1000):
        furan = 10 ** (oq.CHENDONG_A - oq.CHENDONG_B * dp_true)
        assert oq.estimate_dp(furan)["dp_estimate"] == pytest.approx(dp_true, abs=1)


def test_furan_arttikca_dp_duser():
    """Daha çok furan = daha çok bozunmuş kağıt."""
    dp_dusuk = oq.estimate_dp(0.05)["dp_estimate"]
    dp_yuksek = oq.estimate_dp(2.0)["dp_estimate"]
    assert dp_yuksek < dp_dusuk


def test_tespit_siniri_altinda_sifira_bolme_yok():
    """log10(0) tanımsızdır; çok düşük furan kağıdı yeni sayar."""
    r = oq.estimate_dp(0.0)
    assert r["available"] is True
    assert r["dp_estimate"] == oq.DP_NEW
    assert r["life_consumed_pct"] == 0.0


def test_furan_yoksa_hesap_yapilmaz():
    """Ölçüm yoksa uydurma değil, "yok" demek doğrudur."""
    assert oq.estimate_dp(None)["available"] is False


def test_tuketilen_omur_sinirlari_asmaz():
    """Aşırı furan %100'ü geçmemeli, çok az furan negatif olmamalı."""
    assert oq.estimate_dp(50.0)["life_consumed_pct"] <= 100.0
    assert oq.estimate_dp(0.02)["life_consumed_pct"] >= 0.0


def test_tuk_kagitta_guvenilirlik_uyarisi():
    """Künyedeki kağıt tipi burada karşılığını veriyor (Faz 8.1 bağlantısı).

    Chendong standart kraft için türetildi; TUK daha az furan ürettiği için
    DP olduğundan yüksek (trafo olduğundan genç) görünür.
    """
    kraft = oq.estimate_dp(1.0, insulation_type="kraft")
    tuk = oq.estimate_dp(1.0, insulation_type="tuk")

    assert kraft["reliable"] is True and kraft["warnings"] == []
    assert tuk["reliable"] is False
    assert any("TUK" in w for w in tuk["warnings"])
    # Sayısal sonuç aynı; değişen şey GÜVENİLİRLİK beyanı.
    assert kraft["dp_estimate"] == tuk["dp_estimate"]


# --- Bütünsel değerlendirme -------------------------------------------------

def test_genel_durum_EN_KOTU_parametreye_gore():
    """Ortalama almak yanıltıcı olurdu: üç iyi bir kötüyü gizleyemez."""
    test = {"water_ppm": 5.0, "bdv_kv": 70.0, "ift_mn_m": 40.0,
            "acidity_mgkoh_g": 0.9}     # tek başına kötü
    result = oq.assess(test, hv_kv=154.0)

    assert result["overall"] == "kötü"
    assert any("Asitlik" in p for p in result["problems"])


def test_hic_olcum_yoksa_bilinmiyor():
    result = oq.assess({}, hv_kv=154.0)
    assert result["overall"] == "bilinmiyor"
    assert result["measured_count"] == 0


def test_iyi_yag_iyi_doner():
    test = {"water_ppm": 6.0, "bdv_kv": 68.0, "acidity_mgkoh_g": 0.02,
            "ift_mn_m": 40.0}
    assert oq.assess(test, hv_kv=154.0)["overall"] == "iyi"


# --- Sentetik üreteç tutarlılığı --------------------------------------------

def test_yasli_trafo_daha_bozunmus_kagit():
    genc = make_oil_test(5, "Normal", "kraft", 154.0, seed=1)
    yasli = make_oil_test(30, "Normal", "kraft", 154.0, seed=1)

    assert (oq.estimate_dp(yasli["furan_2fal_mgl"])["dp_estimate"]
            < oq.estimate_dp(genc["furan_2fal_mgl"])["dp_estimate"])


def test_termal_ariza_kagidi_hizli_yaslandirir():
    """T3 (>700 °C) aynı yaştaki normal trafodan çok daha fazla bozar."""
    normal = make_oil_test(15, "Normal", "kraft", 154.0, seed=2)
    sicak = make_oil_test(15, "T3", "kraft", 154.0, seed=2)

    assert sicak["furan_2fal_mgl"] > normal["furan_2fal_mgl"]


def test_nem_ve_bdv_ters_iliskili():
    """Bağımsız üretmek fiziksel olarak yanlış olurdu: su BDV'yi düşürür."""
    tests = [make_oil_test(y, "Normal", "kraft", 154.0, seed=y)
             for y in range(2, 40, 2)]
    # Pearson korelasyonu yerine basit kontrol: en nemli örnek en düşük
    # BDV'lerden birine sahip olmalı.
    en_nemli = max(tests, key=lambda t: t["water_ppm"])
    en_kuru = min(tests, key=lambda t: t["water_ppm"])
    assert en_nemli["bdv_kv"] < en_kuru["bdv_kv"]


def test_uretilen_degerler_fiziksel_olarak_makul():
    for yas in (1, 10, 25, 40):
        t = make_oil_test(yas, "Normal", "kraft", 154.0, seed=yas)
        assert 0 < t["water_ppm"] < 100
        assert 15 < t["bdv_kv"] < 100
        assert 0 < t["acidity_mgkoh_g"] < 1.0
        assert 0 < t["furan_2fal_mgl"] < 50
        assert not any(math.isnan(v) for v in t.values())
