"""Sentetik yağ kalitesi testi üreteci. — Faz 8.3

Faz 6'nın dersi burada da geçerli: üretecin gerçekçiliği **iddia edilmez,
gösterilir**. Bu üreteç fiziksel olarak tutarlı olmayı hedefler:

* **Yaş**, kağıt bozunmasını sürükler. Furan yaşla birlikte artar.
* **Sıcaklık geçmişi** yaşlanmayı hızlandırır — burada arıza senaryosuyla
  temsil ediliyor: termal arızası olan trafo daha çok furan üretir.
* **Nem ve asitlik** yaşla birlikte artar; **BDV ve arayüzey gerilimi** düşer.
* **Nem ile BDV ters ilişkilidir** — bağımsız üretmek fiziksel olarak
  yanlış olurdu.

⚠ Bu üreteç bir simülasyondur, kalibre edilmiş bir model değildir. Ürettiği
değerler standartların makul aralıklarındadır ama gerçek bir trafonun
ölçümü değildir.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np

from ..core import oil_quality

# Termal arızalar kağıdı daha hızlı yaşlandırır: sıcaklık her 6 °C artışta
# yaşlanmayı iki katına çıkarır (IEEE C57.91). Deşarj arızaları ise
# kağıttan çok yağı etkiler.
_FAULT_AGING_FACTOR = {
    "Normal": 1.0,
    "PD": 1.1,
    "D1": 1.2,
    "D2": 1.4,
    "T1": 1.6,
    "T2": 2.2,
    "T3": 3.0,
}

# Termal yükseltilmiş kağıt daha yavaş bozunur ve daha az furan üretir.
_INSULATION_FACTOR = {"kraft": 1.0, "tuk": 0.45}


def make_oil_test(age_years: float,
                  fault_class: str = "Normal",
                  insulation_type: str = "kraft",
                  hv_kv: Optional[float] = None,
                  seed: Optional[int] = None) -> Dict[str, float]:
    """Bir yağ kalitesi testi üretir.

    Args:
        age_years: Trafonun yaşı — ana sürükleyici.
        fault_class: Mevcut DGA tanısı; termal arızalar yaşlanmayı hızlandırır.
        insulation_type: kraft veya tuk.
        hv_kv: Gerilim sınıfı; yüksek gerilimli üniteler daha sıkı bakım
            görür, bu yüzden nem tipik olarak daha düşüktür.
    """
    rng = np.random.default_rng(seed)

    aging = _FAULT_AGING_FACTOR.get(fault_class, 1.0)
    paper_factor = _INSULATION_FACTOR.get(str(insulation_type).lower(), 1.0)

    # --- Kağıt: yaş × arıza şiddeti × kağıt tipi -> DP -----------------
    # DP üstel olarak düşer; yeni kağıt 1100'den başlar.
    effective_years = age_years * aging * paper_factor
    dp_true = oil_quality.DP_NEW * math.exp(-0.030 * effective_years)
    dp_true = max(150.0, dp_true * float(rng.lognormal(0.0, 0.06)))

    # Chendong'u TERSTEN çevirerek furan üret: log10(2FAL) = 1.51 - 0.0035·DP
    furan = 10 ** (oil_quality.CHENDONG_A - oil_quality.CHENDONG_B * dp_true)
    furan *= float(rng.lognormal(0.0, 0.18))    # laboratuvar saçılımı

    # --- Nem: yaşla artar, yüksek gerilimde daha sıkı bakım -----------
    # Artış hızı ölçülü: işletmedeki yağ periyodik olarak kurutulup
    # filtrelenir. Bakımsız bir eğri varsaymak her trafoyu "kötü"
    # göstermiş ve ölçütü işe yaramaz hale getirmişti.
    base_water = 4.5 + 0.35 * age_years
    if hv_kv is not None and hv_kv > 170:
        base_water *= 0.70          # yüksek gerilimde bakım daha sıkı
    water = max(1.0, base_water * float(rng.lognormal(0.0, 0.20)))

    # --- BDV: nemle TERS ilişkili ------------------------------------
    # Bağımsız üretmek fiziksel olarak yanlış olurdu: su, dielektrik
    # dayanımı düşüren ana etkendir.
    bdv = 75.0 - 1.15 * water - 0.25 * age_years
    bdv = max(20.0, bdv * float(rng.normal(1.0, 0.06)))

    # --- Asitlik: oksidasyon, yaşla ve sıcaklıkla artar ---------------
    acidity = 0.010 + 0.0030 * age_years * aging
    acidity = max(0.005, acidity * float(rng.lognormal(0.0, 0.25)))

    # --- Arayüzey gerilimi: asitlikle ters ---------------------------
    ift = 45.0 - 95.0 * acidity
    ift = max(10.0, ift * float(rng.normal(1.0, 0.05)))

    # --- Renk (ASTM D1500): asitlikle birlikte koyulaşır -------------
    color = min(8.0, 0.5 + 22.0 * acidity)

    return {
        "water_ppm": round(water, 1),
        "bdv_kv": round(bdv, 1),
        "acidity_mgkoh_g": round(acidity, 3),
        "ift_mn_m": round(ift, 1),
        "furan_2fal_mgl": round(furan, 3),
        "color_astm": round(color, 1),
    }
