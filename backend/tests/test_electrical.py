"""Elektriksel test motoru testleri. — Faz 8.6

Hepsi saf: veritabanı ya da HTTP yok.
"""
import pytest

from app.core import electrical as el
from app.core import nameplate


# --- Sarım oranı (TTR) ---------------------------------------------------

def test_saglam_trafo_ttr_gecer():
    r = el.assess_turns_ratio({"A": 4.464, "B": 4.463, "C": 4.465},
                              expected=4.4638)
    assert r["overall"] == "iyi"
    assert r["problems"] == []


def test_tek_fazda_spir_kaybi_yakalanir():
    """B fazı %1.5 düşük: kısa devre olmuş spir işareti."""
    r = el.assess_turns_ratio({"A": 4.464, "B": 4.397, "C": 4.465},
                              expected=4.4638)
    assert r["overall"] == "kötü"
    b = next(p for p in r["phases"] if p["phase"] == "B")
    assert b["condition"] == "kötü"
    assert b["direction"] == "düşük"
    # Fazlar ayrışmış -> gerçek sargı sorunu uyarısı
    assert "ayrışıyor" in r["note"]


def test_uc_faz_birlikte_kayarsa_kademe_hatasi_denir():
    """Üçü de aynı yönde %1.25 kaymış: bu sargı arızası değil, kademe."""
    shifted = 4.4638 * 1.0125
    r = el.assess_turns_ratio({"A": shifted, "B": shifted, "C": shifted},
                              expected=4.4638)
    assert r["overall"] == "kötü"          # tolerans dışı, evet
    assert r["spread_pct"] <= el.TTR_GOOD_PCT
    assert "KADEME" in r["note"]           # ama sebebi farklı


def test_kunye_eksikse_ttr_degerlendirilmez():
    r = el.assess_turns_ratio({"A": 4.4, "B": 4.4, "C": 4.4}, expected=None)
    assert r["available"] is False


def test_beklenen_oran_kunyeden_geliyor_ve_vektor_grubunu_iceriyor():
    """√3 çarpanı künyede uygulanır; burada TEKRAR uygulanmamalı."""
    np_yn = {"hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNyn0"}
    np_d = {"hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11"}
    exp_yn = nameplate.rated_turns_ratio(np_yn)
    exp_d = nameplate.rated_turns_ratio(np_d)
    assert exp_d == pytest.approx(exp_yn * 3 ** 0.5, abs=0.001)

    # Aynı ölçüm, YNd11 için doğru; YNyn0 beklentisiyle "arızalı" görünür.
    measured = {"A": exp_d, "B": exp_d, "C": exp_d}
    assert el.assess_turns_ratio(measured, exp_d)["overall"] == "iyi"
    assert el.assess_turns_ratio(measured, exp_yn)["overall"] == "kötü"


# --- Sargı direnci -------------------------------------------------------

def test_dengeli_sargi_direnci_gecer():
    r = el.assess_winding_resistance({"A": 0.512, "B": 0.514, "C": 0.513})
    assert r["condition"] == "iyi"
    assert r["imbalance_pct"] < el.RESISTANCE_GOOD_PCT


def test_dengesiz_faz_isaretlenir():
    r = el.assess_winding_resistance({"A": 0.512, "B": 0.560, "C": 0.513})
    assert r["condition"] == "kötü"
    assert r["worst_phase"] == "B"
    assert r["problems"]


def test_sicaklik_duzeltmesi_orani_bozmaz():
    """Üç faz aynı sıcaklıkta olduğu için dengesizlik değişmemeli.

    Düzeltmenin işi mutlak değeri taşımak; oranı DEĞİŞTİRMEMELİ.
    """
    raw = el.assess_winding_resistance({"A": 0.512, "B": 0.560, "C": 0.513})
    hot = el.assess_winding_resistance({"A": 0.512, "B": 0.560, "C": 0.513},
                                       temp_c=60.0)
    assert hot["imbalance_pct"] == pytest.approx(raw["imbalance_pct"], abs=0.01)
    # Ama mutlak değerler 75 °C'ye taşındığı için YÜKSELMELİ.
    assert hot["mean_ohm"] > raw["mean_ohm"]


def test_bakir_ve_aluminyum_farkli_duzeltilir():
    cu = el.correct_resistance(0.5, 20.0, "Cu")
    al = el.correct_resistance(0.5, 20.0, "Al")
    assert cu != al


def test_tek_faz_olcumu_yetmez():
    r = el.assess_winding_resistance({"A": 0.512, "B": None, "C": None})
    assert r["available"] is False


# --- Yalıtım direnci / PI ------------------------------------------------

def test_kuru_yalitimin_pi_si_iyi():
    r = el.assess_insulation(ir_1min_mohm=1000.0, ir_10min_mohm=2500.0)
    assert r["pi"] == 2.5
    assert r["condition"] == "iyi"


def test_islak_yalitim_yakalanir():
    r = el.assess_insulation(ir_1min_mohm=800.0, ir_10min_mohm=880.0)
    assert r["pi"] == 1.1
    assert r["condition"] == "kötü"
    assert r["problems"]


def test_cok_yuksek_dirente_pi_anlamini_yitirir():
    """Kuru ve temiz bir trafo, düşük PI yüzünden suçlanmamalı."""
    r = el.assess_insulation(ir_1min_mohm=20000.0, ir_10min_mohm=22000.0)
    assert r["pi"] < 2.0                 # ham oran "kötü" derdi
    assert r["condition"] == "iyi"       # ama hüküm düzeltildi
    assert any("anlamını yitirir" in w for w in r["warnings"])


def test_on_dakika_olcumu_yoksa_hukum_verilmez():
    r = el.assess_insulation(ir_1min_mohm=1000.0, ir_10min_mohm=None)
    assert r["available"] is True
    assert r["pi"] is None
    assert r["condition"] == "bilinmiyor"


def test_ir_sicaklik_duzeltmesi_on_derecede_iki_kat():
    assert el.correct_insulation_resistance(100.0, 30.0) == pytest.approx(200.0)
    assert el.correct_insulation_resistance(100.0, 10.0) == pytest.approx(50.0)


# --- tan δ ---------------------------------------------------------------

def test_yeni_yalitimin_tand_si_iyi():
    assert el.assess_tan_delta(0.3)["condition"] == "iyi"


def test_yaslanmis_yalitim_tand_ile_yakalanir():
    r = el.assess_tan_delta(1.4)
    assert r["condition"] == "kötü"
    assert r["problems"]


def test_sicaklik_sapmasi_uyarilir_ama_duzeltilmez():
    """Uydurma düzeltme yapmak yerine sınırı söylüyoruz."""
    r = el.assess_tan_delta(0.4, temp_c=55.0)
    assert r["tan_delta_pct"] == 0.4          # değer DEĞİŞMEDİ
    assert any("düzeltme" in w.lower() for w in r["warnings"])


# --- Bütün test ----------------------------------------------------------

def test_genel_hukum_en_kotu_bolume_gore():
    """Üç bölüm iyi, biri kötüyse genel hüküm kötü olmalı."""
    test = {
        "ttr_a": 4.464, "ttr_b": 4.463, "ttr_c": 4.465,
        "rw_a_ohm": 0.512, "rw_b_ohm": 0.514, "rw_c_ohm": 0.513,
        "ir_1min_mohm": 800.0, "ir_10min_mohm": 880.0,     # PI 1.1 -> kötü
        "tan_delta_pct": 0.3,
    }
    r = el.assess(test, expected_ratio=4.4638)
    assert r["overall"] == "kötü"
    assert r["measured_count"] == 4
    assert r["problems"]


def test_hicbir_olcum_yoksa_bilinmiyor():
    r = el.assess({}, expected_ratio=4.4638)
    assert r["overall"] == "bilinmiyor"
    assert r["measured_count"] == 0


# --- İmkânsız sapma: arıza değil, veri hatası ---------------------------
# Bu kural GERÇEKTEN YAŞANMIŞ bir vakadan doğdu: kullanıcı C fazını
# 3.1631 yerine 1.1631 yazdı (basamak atladı) ve sistem %63 sapmayı
# "kısa devre olmuş spir — devreden çıkar" diye raporladı.

def test_imkansiz_sapma_ariza_degil_veri_hatasi_sayilir():
    """%63 sapma fiziksel olarak mümkün değil: sargının 2/3'ü yok demek."""
    r = el.assess_turns_ratio({"A": 3.1625, "B": 3.1608, "C": 1.1631},
                              expected=3.1617)
    assert r["data_suspect"] is True
    assert "fiziksel olarak mümkün değil" in r["note"]
    # Yanlış TEŞHİS artık verilmemeli. ("kısa devre" ifadesi notta
    # açıklama olarak geçiyor — "birkaç spirin kısa devre olması %1'in
    # altında sapma yapar" — o meşru; yasak olan teşhis cümlesi.)
    assert "spir işaretidir" not in r["note"]
    assert "devreden çıkarma sebebidir" not in r["note"]
    assert any("giriş hatası" in p for p in r["problems"])


def test_gercek_spir_kaybi_veri_supheli_sayilmaz():
    """Ayrım işe yaramalı: %1.4 sapma gerçek bir arızadır, şüphe değil."""
    r = el.assess_turns_ratio({"A": 3.1625, "B": 3.1174, "C": 3.1631},
                              expected=3.1617)
    assert r["data_suspect"] is False
    assert "ayrışıyor" in r["note"]


def test_kademe_hatasi_da_veri_supheli_sayilmaz():
    """%5 sapma (2 kademe) imkânsız değil; eşik %10 bunu ayırt etmeli."""
    shifted = 3.1617 * 1.05
    r = el.assess_turns_ratio({"A": shifted, "B": shifted * 0.9999,
                               "C": shifted * 1.0001}, expected=3.1617)
    assert r["data_suspect"] is False
    assert "KADEME" in r["note"]


def test_veri_supheliyken_yayilim_yorumu_yapilmaz():
    """Geçersiz bir sayıdan 'faz deseni' okumaya çalışmak yanlış olur."""
    r = el.assess_turns_ratio({"A": 3.1625, "B": 3.1608, "C": 1.1631},
                              expected=3.1617)
    # Yayılım hâlâ hesaplanır (bilgi), ama yorum imkânsızlık üzerine.
    assert r["spread_pct"] is not None
    assert "tek fazda yoğunlaşmış" not in r["note"]
