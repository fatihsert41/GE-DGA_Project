"""Sağlık endeksi testleri. — Faz 8.5

Hepsi saf: veritabanı ya da HTTP yok, çünkü ``core/health_index.compute``
girdiyi parametre olarak alıyor.
"""
import pytest

from app.core import health_index as hi


def paper(consumed, reliable=True):
    """Test için kısa kağıt değerlendirmesi üretir."""
    return {"available": True, "life_consumed_pct": consumed,
            "dp_estimate": round(1100 - consumed / 100 * 900),
            "reliable": reliable}


def test_mukemmel_trafo_100_e_yakin():
    r = hi.compute(risk_condition=1, oil_overall="iyi", paper=paper(0))
    assert r["available"] is True
    assert r["score"] == 100.0
    assert r["band"] == "excellent"


def test_agirlikli_ortalama_elle_dogrulanir():
    # DGA kondisyon 2 -> 75 (ağırlık 4), kağıt %20 tüketilmiş -> 80 (3),
    # yağ "kabul" -> 65 (2). (4*75 + 3*80 + 2*65) / 9 = 74.4
    r = hi.compute(risk_condition=2, oil_overall="kabul", paper=paper(20))
    assert r["score"] == pytest.approx(74.4, abs=0.1)
    assert r["weight_sum"] == 9.0
    assert r["band"] == "good"


def test_bilinmeyen_boyut_saglikli_sayilmaz():
    """Yağ testi olmayan trafo, yağı iyi olanla aynı skoru ALMAMALI."""
    with_oil = hi.compute(risk_condition=2, oil_overall="iyi",
                          paper=paper(20))
    without = hi.compute(risk_condition=2, oil_overall=None, paper=paper(20))

    assert without["coverage"]["level"] == "partial"
    assert without["coverage"]["measured"] == 2
    assert without["score"] != with_oil["score"]
    # Payda küçüldü: 9 yerine 7 (DGA 4 + kağıt 3).
    assert without["weight_sum"] == 7.0
    assert any("ölçülmemiş" in w for w in without["warnings"])


def test_kritik_boyut_tavani_uygulanir():
    """İki iyi boyut, ark yapan bir trafoyu gizleyememeli."""
    r = hi.compute(risk_condition=4, oil_overall="iyi", paper=paper(0))
    assert r["capped"] is True
    assert r["score"] == hi.CRITICAL_CAP
    assert r["raw_score"] > hi.CRITICAL_CAP      # ham ortalama yüksekti
    assert "DGA riski" in r["critical_dimensions"]
    assert r["band"] == "poor"


def test_omru_bitmis_kagit_da_tavan_uygular():
    r = hi.compute(risk_condition=1, oil_overall="iyi", paper=paper(95))
    assert r["capped"] is True
    assert "Kağıt yalıtım" in r["critical_dimensions"]


def test_tavan_gereksizse_uygulanmaz():
    """Skor zaten tavanın altındaysa 'capped' işaretlenmemeli."""
    r = hi.compute(risk_condition=4, oil_overall="kötü", paper=paper(85))
    assert r["score"] < hi.CRITICAL_CAP
    assert r["capped"] is False


def test_tuk_uyarisi_boyuttan_yukari_tasinir():
    r = hi.compute(risk_condition=1, oil_overall="iyi",
                   paper=paper(30, reliable=False))
    assert any("İYİMSER" in w for w in r["warnings"])


def test_hic_veri_yoksa_skor_uretilmez():
    r = hi.compute(risk_condition=None, oil_overall=None, paper=None)
    assert r["available"] is False
    assert r["reason"] == "no_data"
    assert "score" not in r
    assert r["coverage"]["level"] == "none"


def test_yenileme_onceligi_varlik_agirligiyla_olceklenir():
    """Aynı sağlık durumu, LPT'de MPT'den daha yüksek öncelik almalı."""
    lpt = hi.compute(risk_condition=3, oil_overall="kabul",
                     paper=paper(50), asset_class="LPT")
    mpt = hi.compute(risk_condition=3, oil_overall="kabul",
                     paper=paper(50), asset_class="MPT")
    assert lpt["score"] == mpt["score"]                    # durum aynı
    assert lpt["renewal_priority"] > mpt["renewal_priority"]  # sonuç farklı


def test_boyut_dokumu_formulu_yeniden_kurabiliyor():
    """Arayüz formülü satır satır gösterebilmeli: kara kutu yok."""
    r = hi.compute(risk_condition=2, oil_overall="kabul", paper=paper(20))
    rows = [d for d in r["dimensions"] if d["available"]]
    total = sum(d["contribution"] for d in rows)
    weights = sum(d["weight"] for d in rows)
    assert total / weights == pytest.approx(r["raw_score"], abs=0.1)


def test_bant_sinirlari():
    assert hi._band(85.0)["band"] == "excellent"
    assert hi._band(84.9)["band"] == "good"
    assert hi._band(50.0)["band"] == "fair"
    assert hi._band(29.9)["band"] == "critical"


def test_fleet_stats_bilinmeyeni_ortalamaya_katmaz():
    s = hi.fleet_stats([90.0, 40.0, None])
    assert s["scored"] == 2
    assert s["unknown"] == 1
    assert s["average"] == 65.0
    assert s["worst"] == 40.0
    assert s["band_distribution"]["excellent"] == 1
    assert s["band_distribution"]["poor"] == 1


def test_fleet_stats_bos_liste():
    s = hi.fleet_stats([None, None])
    assert s["average"] is None
    assert s["worst"] is None
    assert s["scored"] == 0


def test_en_zayif_boyut_bildirilir():
    """Ortalama 'orta' görünse bile asıl sorunu gösteren boyut çıkmalı.

    TR-09 senaryosu: DGA sakin, yağ kabul edilebilir, kağıdın %82'si
    tüketilmiş. Skor tek başına bakıldığında yanıltıcıdır.
    """
    r = hi.compute(risk_condition=1, oil_overall="kabul", paper=paper(82))
    assert r["weakest"]["key"] == "paper"
    assert r["weakest"]["score"] == 18.0
